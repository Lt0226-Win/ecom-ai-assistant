"""智能客服评测：检索准不准、回答对不对、工单分得准不准。

运行：python eval/run_service_eval.py           # 不调用大模型的部分（检索 + 规则分类）
     python eval/run_service_eval.py --llm     # 加上大模型回答和大模型分类
输出：reports/service_eval.md

指标说明：
  - 检索命中率 Hit@1 / Hit@3：正确的规则小节是否排在第 1 / 前 3 位
  - 拒答准确率：知识库里没有的问题，系统是否正确转人工
  - 回答关键信息命中率：回答里是否包含标准答案的关键信息（如“7 天”“59 元”）
  - 分类准确率：60 条模拟工单，预测类别 = 人工标注类别 的比例
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from ai import llm, rag, tickets  # noqa: E402


def eval_retrieval(cases):
    r = rag.get_retriever()
    rows = []
    for c in cases:
        hits = r.search(c["question"], 3)
        srcs = [h[0].source for h in hits]
        refused = hits[0][1] < rag.NO_ANSWER_SCORE
        if c["source"]:
            rows.append({**c, "hit1": srcs[0] == c["source"], "hit3": c["source"] in srcs, "refused": refused,
                         "top": srcs[0], "score": round(hits[0][1], 2)})
        else:
            rows.append({**c, "hit1": None, "hit3": None, "refused": refused, "top": srcs[0],
                         "score": round(hits[0][1], 2)})
    return rows, r.mode


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="同时评测大模型回答和大模型分类（需要 API Key）")
    args = ap.parse_args()
    if args.llm and not llm.available():
        print("没有配置 DEEPSEEK_API_KEY，只跑不需要大模型的部分。")
        args.llm = False

    cases = json.loads((ROOT / "eval" / "rag_cases.json").read_text(encoding="utf-8"))
    ret, mode = eval_retrieval(cases)
    pos = [r for r in ret if r["source"]]
    neg = [r for r in ret if not r["source"]]
    hit1 = sum(r["hit1"] for r in pos) / len(pos)
    hit3 = sum(r["hit3"] for r in pos) / len(pos)
    refuse_ok = (sum(r["refused"] for r in neg) + sum(not r["refused"] for r in pos)) / len(ret)
    print(f"检索（{mode}）Hit@1 {hit1:.1%}  Hit@3 {hit3:.1%}  拒答判断准确率 {refuse_ok:.1%}")

    tk = tickets.load_tickets()
    rule_pred = [tickets.classify_rule(t["text"])["category"] for t in tk]
    rule_acc = sum(p == t["label"] for p, t in zip(rule_pred, tk)) / len(tk)
    print(f"工单分类（规则法）准确率 {rule_acc:.1%}")

    lines = ["# 智能客服评测报告", "", f"- 评测时间：{datetime.now():%Y-%m-%d %H:%M}",
             f"- 知识库：{len(rag.get_retriever().chunks)} 个规则片段；检索方式：{mode}", "",
             "## 1. 检索", "",
             f"- 有答案的问题 {len(pos)} 道：**Hit@1 {hit1:.1%}，Hit@3 {hit3:.1%}**",
             f"- 拒答判断（有答案的不拒答、没答案的转人工）准确率：**{refuse_ok:.1%}**（阈值 BM25 分数 < {rag.NO_ANSWER_SCORE}）",
             "", "| # | 问题 | 期望来源 | 第 1 条检索结果 | 分数 | Hit@3 |", "|---|---|---|---|---|---|"]
    for r in ret:
        h = "—（应转人工：" + ("✅" if r["refused"] else "❌") + "）" if not r["source"] else ("✅" if r["hit3"] else "❌")
        lines.append(f"| {r['id']} | {r['question']} | {r['source'] or '（知识库没有）'} | {r['top']} | {r['score']} | {h} |")

    llm_acc = None
    if args.llm:
        # 回答质量
        kw_hits, ans_rows = 0, []
        for c in cases:
            a = rag.answer(c["question"])
            if c["source"]:
                ok = all(k.replace(" ", "") in a["answer"].replace(" ", "") for k in c["keywords"])
            else:
                ok = a["need_human"]
            kw_hits += ok
            ans_rows.append((c, a, ok))
            print(f"{'✅' if ok else '❌'} {c['question']} → {a['answer'][:60]}")
        lines += ["", "## 2. 回答质量（大模型）", "",
                  f"- 关键信息命中 / 正确转人工：**{kw_hits}/{len(cases)}（{kw_hits / len(cases):.1%}）**", "",
                  "| # | 问题 | 回答 | 结果 |", "|---|---|---|---|"]
        for c, a, ok in ans_rows:
            lines.append(f"| {c['id']} | {c['question']} | {a['answer'].replace('|', '/')[:120]} | {'✅' if ok else '❌'} |")
        # 大模型分类
        llm_pred = []
        for t in tk:
            try:
                llm_pred.append(tickets.classify_llm(t["text"])["category"])
            except Exception as e:  # noqa: BLE001
                llm_pred.append(f"错误：{e}")
        llm_acc = sum(p == t["label"] for p, t in zip(llm_pred, tk)) / len(tk)
        print(f"工单分类（大模型）准确率 {llm_acc:.1%}")

    lines += ["", "## 3. 工单分类", "", f"- 60 条模拟工单（8 个类别，人工标注）",
              f"- 规则法（关键词）准确率：**{rule_acc:.1%}**"]
    if llm_acc is not None:
        lines.append(f"- 大模型准确率：**{llm_acc:.1%}**")
    lines += ["", "### 规则法分错的工单", "", "| 工单 | 标注 | 规则法 |" + (" 大模型 |" if llm_acc is not None else ""),
              "|---|---|---|" + ("---|" if llm_acc is not None else "")]
    for i, t in enumerate(tk):
        if rule_pred[i] != t["label"] or (llm_acc is not None and llm_pred[i] != t["label"]):
            extra = f" {llm_pred[i]} |" if llm_acc is not None else ""
            lines.append(f"| {t['text']} | {t['label']} | {rule_pred[i]} |{extra}")
    lines += ["", "### 规则法预测分布", "", "| 类别 | 条数 |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in Counter(rule_pred).most_common()]
    config.REPORT_DIR.mkdir(exist_ok=True)
    (config.REPORT_DIR / "service_eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("报告已保存到 reports/service_eval.md")


if __name__ == "__main__":
    main()
