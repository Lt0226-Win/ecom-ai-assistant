"""接口：健康检查免口令；设置 API_TOKEN 后，没带口令的请求被拒绝（评审 P1-2）。"""
import pytest
from fastapi.testclient import TestClient

import config


@pytest.fixture()
def client(warehouse, monkeypatch):
    from api import server
    monkeypatch.setattr(server, "_con", None)
    monkeypatch.setattr(config, "API_TOKEN", "test-token")
    return TestClient(server.app)


def test_health_needs_no_token(client):
    assert client.get("/health").status_code == 200


def test_rejects_missing_or_wrong_token(client):
    assert client.get("/metrics/weekly").status_code == 401
    assert client.get("/metrics/weekly", headers={"X-API-Token": "wrong"}).status_code == 401


def test_accepts_correct_token(client):
    r = client.get("/metrics/weekly", headers={"X-API-Token": "test-token"})
    assert r.status_code == 200
    assert r.json()["period"]["end"] == "2017-12-03"


def test_no_token_configured_allows_local_only(warehouse, monkeypatch):
    """没设口令时：本机可以调用；其他设备（包括 Docker 里的 n8n）被拒绝，防止忘了设口令就把接口开放出去"""
    from api import server
    monkeypatch.setattr(server, "_con", None)
    monkeypatch.setattr(config, "API_TOKEN", "")
    local = TestClient(server.app, client=("127.0.0.1", 50000))
    remote = TestClient(server.app, client=("192.168.65.2", 50000))
    assert local.get("/metrics/weekly").status_code == 200
    assert remote.get("/metrics/weekly").status_code == 403
    assert remote.get("/health").status_code == 200
