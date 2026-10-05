"""数仓：在合成数据上完整跑一遍 SQL 分层，16 项质量检查必须全部通过。"""
from pipeline import quality_checks


def test_all_quality_checks_pass(con):
    failed = []
    for name, sql, rule, desc in quality_checks.CHECKS:
        v = con.execute(sql).fetchone()[0]
        if not rule(v):
            failed.append(f"{name}: {v}（要求 {desc}）")
    assert not failed, failed


def test_dirty_rows_removed(con):
    # 越界时间戳和未知行为都被清洗掉
    assert con.execute("SELECT count(*) FROM dwd_user_behavior WHERE behavior NOT IN ('pv','cart','fav','buy')").fetchone()[0] == 0
    assert con.execute("SELECT min(event_date), max(event_date) FROM dwd_user_behavior").fetchone() == \
        con.execute("SELECT DATE '2017-11-25', DATE '2017-12-03'").fetchone()


def test_core_tables_exist(con):
    names = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    for t in ["dwd_user_behavior", "dwd_order", "dim_item", "dws_user_summary", "dws_category_daily",
              "ads_daily_kpi", "ads_funnel", "ads_user_rfm", "ads_rfm_segment", "ads_category_rank"]:
        assert t in names, t
