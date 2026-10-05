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


def test_no_token_configured_means_open(warehouse, monkeypatch):
    from api import server
    monkeypatch.setattr(server, "_con", None)
    monkeypatch.setattr(config, "API_TOKEN", "")
    assert TestClient(server.app).get("/metrics/weekly").status_code == 200
