"""演示版每日额度：超出就拒绝；多线程同时调用也不会多放行（评审 P2）。"""
import threading

import pytest

import config
from ai import llm


@pytest.fixture()
def quota(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(config, "DEMO_DAILY_LIMIT", 10)


def test_limit_is_enforced(quota):
    for _ in range(10):
        llm._check_quota()
    with pytest.raises(llm.LLMQuotaExceeded):
        llm._check_quota()


def test_concurrent_calls_never_exceed_limit(quota):
    passed, lock = [], threading.Lock()

    def call():
        try:
            llm._check_quota()
            with lock:
                passed.append(1)
        except llm.LLMQuotaExceeded:
            pass

    threads = [threading.Thread(target=call) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(passed) == 10


def test_unlimited_when_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(config, "DEMO_DAILY_LIMIT", 0)
    for _ in range(50):
        llm._check_quota()
    assert not (tmp_path / "usage.json").exists()
