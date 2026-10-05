"""SQL 执行：行数上限、超时中断，以及多线程同时查询互不干扰（评审 P1-1）。"""
import threading

import pytest

from ai import text2sql

SLOW_SQL = "SELECT count(*) FROM range(100000000) a, range(100000) b WHERE a.range * b.range = 7"


def test_row_limit(con):
    df = text2sql.run_sql(con, "SELECT * FROM range(100000)")
    assert len(df) == text2sql.MAX_ROWS


def test_timeout_interrupts_long_query(con):
    with pytest.raises(TimeoutError):
        text2sql.run_sql(con, SLOW_SQL, timeout=1)


def test_concurrent_queries_on_shared_connection(con):
    """8 个线程同时查询同一个共享连接，其中 1 个超时被中断，另外 7 个结果都应正确"""
    expected = con.execute("SELECT sum(order_cnt) FROM ads_daily_kpi").fetchone()[0]
    results, errors = [], []

    def ok_query():
        try:
            for _ in range(5):
                df = text2sql.run_sql(con, "SELECT sum(order_cnt) AS n FROM ads_daily_kpi")
                results.append(int(df["n"][0]))
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    def slow_query():
        try:
            text2sql.run_sql(con, SLOW_SQL, timeout=1)
        except TimeoutError:
            pass

    threads = [threading.Thread(target=slow_query)] + [threading.Thread(target=ok_query) for _ in range(7)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    assert results == [expected] * 35
