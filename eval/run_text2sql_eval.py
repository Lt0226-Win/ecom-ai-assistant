"""AI 问数评测：用 23 道有标准答案的题，量化“问数准不准”。

运行：python eval/run_text2sql_eval.py              23 道开发集 → reports/text2sql_eval.md
      python eval/run_text2sql_eval.py --holdout    10 道独立测试集 → reports/text2sql_holdout.md

开发集 vs 独立测试集：
  开发集的错题被拿来改进过语义层说明，所以它的准确率偏乐观；
  独立测试集是另外出的题，提示词和语义层不针对它做任何修改，它的准确率才代表“没见过的问题”上的真实水平。

评分方法 —— 执行准确率（Execution Accuracy）：
  不比较 SQL 写法（同一个问题有很多种正确写法），而是比较“执行结果”。
  规则：标准答案的每一列，都能在模型结果里找到数值一致的一列（允许 0.5% 误差、不看列名），且行数相同。
  拒答 / 安全题：模型应该不生成 SQL，或者生成的 SQL 被安全检查拦下。
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from ai import llm, text2sql  # noqa: E402
from pipeline.db import connect  # noqa: E402


def _norm_col(s: pd.Series) -> list:
    """把一列转换成可比较的形式：数值保留 4 位有效差异，日期转字符串"""
    out = []
    for v in s.tolist():
        if v is None or (isinstance(v, float) and pd.isna(v)):
            out.append(None)
        elif isinstance(v, (int, float)) or hasattr(v, "__float__") and not isinstance(v, str):
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                out.append(str(v))
        else:
            out.append(str(v)[:10] if hasattr(v, "year") else str(v))
    return out


def _col_equal(a: list, b: list, ordered: bool) -> bool:
    if len(a) != len(b):
        return False
    if not ordered:
        key = lambda x: (x is None, str(type(x)), x if x is not None else 0)  # noqa: E731
        a, b = sorted(a, key=key), sorted(b, key=key)
    for x, y in zip(a, b):
        if isinstance(x, float) and isinstance(y, float):
            if abs(x - y) > max(0.005 * abs(y), 1e-4):
                return False
        elif x != y:
            return False
    return True


def results_match(pred: pd.DataFrame, gold: pd.DataFrame, ordered: bool) -> bool:
    if pred is None or len(pred) != len(gold):
        return False
    pcols = [_norm_col(pred[c]) for c in pred.columns]
    for gc in gold.columns:
        g = _norm_col(gold[gc])
        # 比率题：模型可能把 0.55 写成 55（百分比），两种都算对
        if not any(_col_equal(p, g, ordered) or _col_equal(p, [None if v is None else v * 100 if isinstance(v, float)
                                                                 else v for v in g], ordered) for p in pcols):
            return False
    return True


def main() -> None:
    if not llm.available():
        print("没有配置 DEEPSEEK_API_KEY，请先在 .env 里填写。")
        sys.exit(1)
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true", help="跑独立测试集（eval/text2sql_holdout.json）")
    args = ap.parse_args()
    case_file, out_name = ("text2sql_holdout.json", "text2sql_holdout.md") if args.holdout else \
        ("text2sql_cases.json", "text2sql_eval.md")
    cases = json.loads((ROOT / "eval" / case_file).read_text(encoding="utf-8"))
    con = connect(read_only=True)
    rows = []
    for c in cases:
        t = time.time()
        ans = text2sql.ask(con, c["question"], summarize=False)
        if not c["gold_sql"]:     # 拒答 / 安全题
            ok = (not ans.sql) or ans.error.startswith("安全检查")
        else:
            gold = con.execute(c["gold_sql"]).df()
            ordered = c.get("ordered", "order by" in c["gold_sql"].lower()) and len(gold) > 1
            ok = not ans.error and results_match(ans.data, gold, ordered)
        rows.append({**c, "ok": ok, "pred_sql": ans.sql, "error": ans.error, "attempts": ans.attempts,
                     "seconds": round(time.time() - t, 1)})
        print(f"{'✅' if ok else '❌'} [{c['type']}] {c['question']}  （{rows[-1]['seconds']}s，尝试 {ans.attempts} 次）")

    df = pd.DataFrame(rows)
    acc = df["ok"].mean()
    by_type = df.groupby("type", sort=False)["ok"].agg(["sum", "count"])
    title = "# AI 问数评测报告：独立测试集" if args.holdout else "# AI 问数评测报告"
    intro = ["> 这 10 道题由项目作者另行出题，与开发集文字零重叠，其中 6 道用到开发集从未涉及的表。",
             "> 提示词和语义层说明**没有针对这些题做任何修改**，所以这里的准确率代表模型在“没见过的问题”上的水平。", ""] \
        if args.holdout else []
    lines = [
        title, "", *intro,
        f"- 评测时间：{datetime.now():%Y-%m-%d %H:%M}",
        f"- 模型：{config.DEEPSEEK_MODEL}",
        f"- 题目数：{len(df)}",
        f"- **执行准确率：{acc:.1%}**（{int(df['ok'].sum())}/{len(df)}）",
        f"- 平均耗时：{df['seconds'].mean():.1f} 秒；需要自我修正（重试）的题：{int((df['attempts'] > 1).sum())} 道", "",
        "## 分类型结果", "", "| 类型 | 正确 / 总数 |", "|---|---|",
    ]
    lines += [f"| {t} | {int(r['sum'])} / {int(r['count'])} |" for t, r in by_type.iterrows()]
    lines += ["", "## 逐题明细", "", "| # | 类型 | 问题 | 结果 | 模型 SQL / 错误 |", "|---|---|---|---|---|"]
    for r in rows:
        detail = (r["error"] or r["pred_sql"] or "（未生成 SQL，拒答）").replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {r['id']} | {r['type']} | {r['question']} | {'✅' if r['ok'] else '❌'} | `{detail[:300]}` |")
    notes = [r for r in rows if r.get("note")]
    if notes:
        lines += ["", "## 题目说明", ""] + [f"- 第 {r['id']} 题：{r['note']}" for r in notes]
    lines += ["", "## 错题分析（手动填写）", "", "- 错在哪：", "- 原因：（语义层没写清？口径歧义？模型能力？）", "- 改进：", ""]
    config.REPORT_DIR.mkdir(exist_ok=True)
    (config.REPORT_DIR / out_name).write_text("\n".join(lines), encoding="utf-8")
    print(f"\n执行准确率 {acc:.1%}，报告已保存到 reports/{out_name}")


if __name__ == "__main__":
    main()
