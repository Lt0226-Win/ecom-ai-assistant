"""周报存档 + “数字核对”演示。

做两件事：
  1. 调用大模型生成一份真正的大模型版周报，存到 reports/weekly/weekly_<日期>_llm.md，
     并在文末附上自动核对的结果（reports/weekly/ 里原来只有模板版）。
  2. 数字核对演示：把周报里的真实数字改成错误数字，看核对程序能不能拦住：
       - 3 个固定例子（随机种子固定，可复现）→ reports/weekly/guard_demo.md
       - 500 次随机篡改的拦截率（同一份周报、同一个种子）

运行：
    python eval/run_weekly_guard_demo.py              # 需要 DEEPSEEK_API_KEY
    python eval/run_weekly_guard_demo.py --reuse      # 不重新调大模型，复用已存档的周报，只重新核对并重出演示报告
    python eval/run_weekly_guard_demo.py --no-llm     # 调试用：用模板版文字代替，不调大模型，输出到 --out 指定目录

说明：核对的是“文中数字能不能在 SQL 算出的数据里找到”，不是判断分析写得对不对。
伪造的数字恰好等于数据里另一个数时拦不住，所以拦截率不是 100%，这里如实统计。
"""
import argparse
import random
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from ai import weekly_report as wr  # noqa: E402
from pipeline.db import connect  # noqa: E402

NUM_RE = re.compile(r"(?<![\w.])(\d+(?:,\d{3})*(?:\.(\d+))?)")
SEED = 42
TRIALS = 500


def decimal_numbers(text: str) -> list:
    """周报里所有带小数的数字（整数序号、年份之类不算）"""
    return [m for m in NUM_RE.finditer(text) if m.group(2)]


def fake_number(m: re.Match, rng: random.Random) -> str:
    """把数字改成偏离 10%~50% 的假数字，小数位数、千分位写法保持不变"""
    s, nd = m.group(1), len(m.group(2))
    new = float(s.replace(",", "")) * (1 + rng.choice([-1, 1]) * rng.uniform(0.1, 0.5))
    return f"{new:,.{nd}f}" if "," in s else f"{new:.{nd}f}"


def replace_number(text: str, m: re.Match, new: str) -> str:
    return text[:m.start(1)] + new + text[m.end(1):]


def context(text: str, m: re.Match, width: int = 14) -> str:
    return text[max(0, m.start() - width):m.end() + width].replace("\n", " ")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="调试用：用模板文字，不调大模型")
    ap.add_argument("--reuse", action="store_true", help="复用已存档的大模型周报，不重新调用大模型")
    ap.add_argument("--out", default=str(wr.REPORT_DIR), help="输出目录，默认 reports/weekly")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    con = connect(read_only=True)
    facts = wr.collect_facts(con, config.DATA_END_DATE)
    end = facts["period"]["end"]
    archive = out / f"weekly_{end}_llm.md"
    if args.reuse:
        old = archive.read_text(encoding="utf-8")
        body, _, footer = old.partition("\n\n---\n")
        gen_line = footer.splitlines()[0].lstrip("> ").strip()   # 沿用原来的“生成方式、生成时间”
        who = gen_line.split("，生成时间")[0].replace("生成方式：", "")
    else:
        rep = wr.generate(con, config.DATA_END_DATE, use_llm=not args.no_llm)
        if not args.no_llm and rep["source"] != "llm":
            print(f"大模型没有调用成功：{rep['error'] or '没有配置 DEEPSEEK_API_KEY'}")
            sys.exit(1)
        body = rep["markdown"]
        who = f"大模型（{config.DEEPSEEK_MODEL}）" if rep["source"] == "llm" else "模板（调试，不是大模型）"
        gen_line = f"生成方式：{who}，生成时间 {datetime.now():%Y-%m-%d %H:%M}。"
    unverified = wr.verify_numbers(body, facts)

    # ---- 1. 大模型版周报存档（原文不改，只更新文末的核对结果）----
    check = "全部通过：文中每个数字都能在 SQL 算出的数据里找到" if not unverified else \
        f"以下数字在数据里找不到，需要人工核对：{', '.join(unverified)}（人工复核结论见 review_notes.md）"
    archive.write_text(body.rstrip() + f"\n\n---\n> {gen_line}\n> 数字核对：{check}。\n", encoding="utf-8")

    # ---- 2. 篡改演示 ----
    cands = decimal_numbers(body)
    cands = [m for m in cands if m.group(1) not in unverified]   # 只改原本核对通过的数字
    if len(cands) < 3:
        print("周报里带小数的数字太少，无法演示")
        sys.exit(1)
    rng = random.Random(SEED)
    picks = [cands[len(cands) * i // 3] for i in range(3)]       # 前、中、后各取一个
    rows = []
    for m in picks:
        new = fake_number(m, rng)
        bad = wr.verify_numbers(replace_number(body, m, new), facts)
        rows.append((context(body, m), m.group(1), new, new in bad))

    caught = 0
    for _ in range(TRIALS):
        m = rng.choice(cands)
        new = fake_number(m, rng)
        caught += new in wr.verify_numbers(replace_number(body, m, new), facts)

    lines = [
        "# 周报数字核对演示", "",
        f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M}",
        f"- 被改动的周报：`weekly_{end}_llm.md`（{who}），原稿核对结果：{check}",
        "- 原稿里被标出的数字，人工复核的结论见 [review_notes.md](review_notes.md)", "",
        "核对程序做的事：把周报里出现的数字，和 SQL 算出来的数据逐个比对，**数据里找不到的数字会被标出来**，提醒人工审核。", "",
        "## 例子：把周报里的真实数字改成错的", "",
        "| 原文片段 | 真实数字 | 改成 | 是否被拦住 |", "|---|---|---|---|",
    ]
    for ctx, old, new, hit in rows:
        lines.append(f"| …{ctx}… | {old} | {new} | {'✅ 拦住' if hit else '❌ 没拦住'} |")
    lines += [
        "", f"## {TRIALS} 次随机篡改的拦截率", "",
        f"随机挑一个带小数的数字，改成偏离 10%~50% 的假数字（随机种子 {SEED}，可复现）：",
        f"**拦住 {caught} / {TRIALS} 次（{caught / TRIALS:.1%}）**", "",
        "## 局限（如实说明）", "",
        "- 核对的是“数字在不在数据里”，不是判断分析写得对不对：假数字恰好等于数据里另一个数时拦不住，所以拦截率不是 100%。",
        "- 大模型自己算出来的派生数（比如两个数之差）也会被标记，需要人工确认。",
        "- 整数且小于 10 的数字（序号、“3 条建议”）不检查。", ""]
    (out / "guard_demo.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"周报存档：{archive}（{who}）\n核对结果：{check}")
    for ctx, old, new, hit in rows:
        print(f"  {'✅' if hit else '❌'} …{ctx}…  {old} → {new}")
    print(f"随机篡改拦截率：{caught}/{TRIALS} = {caught / TRIALS:.1%}\n演示报告：{out / 'guard_demo.md'}")


if __name__ == "__main__":
    main()
