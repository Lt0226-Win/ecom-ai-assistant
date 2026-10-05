"""智能客服：检索命中正确的规则条款；知识库里没有的问题直接转人工（不调用大模型）。"""
import json

import config
from ai import rag, tickets

CASES = json.loads((config.ROOT / "eval" / "rag_cases.json").read_text(encoding="utf-8"))


def test_retrieval_hits_expected_source(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_API_KEY", "")
    rag.get_retriever.cache_clear()
    r = rag.get_retriever()
    with_source = [c for c in CASES if c.get("source")]
    hit = sum(any(ch.source == c["source"] for ch, _ in r.search(c["question"], 3)) for c in with_source)
    assert hit / len(with_source) >= 0.9, f"命中 {hit}/{len(with_source)}"


def test_out_of_scope_question_goes_to_human(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_API_KEY", "")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "")
    rag.get_retriever.cache_clear()
    for q in [c["question"] for c in CASES if not c.get("source")]:
        out = rag.answer(q)
        assert out["need_human"], q


def test_rule_based_ticket_classifier_accuracy():
    data = tickets.load_tickets()
    right = sum(tickets.classify_rule(t["text"])["category"] == t["label"] for t in data)
    assert right / len(data) >= 0.9, f"{right}/{len(data)}"
