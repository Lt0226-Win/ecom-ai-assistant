"""新版看板的后端接口（api/web.py）：不调大模型的部分全部可测。"""
import pytest
from fastapi.testclient import TestClient

import config


@pytest.fixture()
def client(warehouse, monkeypatch):
    from api import web
    monkeypatch.setattr(web, "_con", None)
    return TestClient(web.build_site())


def test_status_without_llm(client):
    s = client.get("/api/status").json()
    assert s["llm"] is False and s["ask_examples"] and s["service_examples"]


def test_ask_demo_mode_runs_example_question_only(client):
    q = client.get("/api/status").json()["ask_examples"][0]
    ok = client.post("/api/ask", json={"question": q}).json()
    assert ok["error"] == "" and ok["table"]["rows"] and ok["sql"]
    other = client.post("/api/ask", json={"question": "随便问一个不在评测集里的问题"}).json()
    assert other["error"] and other["table"] is None


def test_ask_rejects_empty_question(client):
    assert client.post("/api/ask", json={"question": "  "}).status_code == 400


def test_report_template_when_no_llm(client):
    weekly = config.REPORT_DIR / "weekly"
    snap = lambda: sorted((p.name, p.stat().st_mtime_ns) for p in weekly.glob("*")) if weekly.exists() else []  # noqa: E731
    before = snap()
    r = client.post("/api/report", json={"use_llm": True}).json()
    assert r["source"] == "template" and r["unverified_numbers"] == [] and "核心结论" in r["markdown"]
    assert snap() == before   # 接口只返回周报，不往 reports/weekly/ 写文件（避免覆盖真实存档）


def test_service_answer_retrieves_without_llm(client):
    r = client.post("/api/service/answer", json={"question": "退款退到银行卡要多久"}).json()
    assert r["hits"] and r["mode"]


def test_tickets_classify_and_batch(client):
    c = client.post("/api/tickets/classify", json={"text": "等了一周还没到，再不到我就要退款了"}).json()
    assert c["rule"] and c["llm"] is None
    b = client.get("/api/tickets/batch").json()
    assert b["total"] == 60 and 0 < b["accuracy"] <= 1 and len(b["categories"]) == 8
    assert sum(x["count"] for x in b["dist"]) == 60


def test_base_path_mount(warehouse, monkeypatch):
    from api import web
    monkeypatch.setattr(web, "_con", None)
    monkeypatch.setenv("WEB_BASE_PATH", "/demo")
    assert TestClient(web.build_app()).get("/demo/api/status").status_code == 200
