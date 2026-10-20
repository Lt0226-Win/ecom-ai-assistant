"""数仓：在合成数据上完整跑一遍 SQL 分层，16 项质量检查必须全部通过。"""
import config
from pipeline import quality_checks


def test_all_quality_checks_pass(warehouse):
    """16 项检查在建仓时（读写连接）已经真实跑过，结果写在 data_quality.md 里，这里核对全部通过。
    不在只读连接上重跑：其中一项要读 ODS 的 Parquet 文件，而只读连接已经禁止读文件（见 pipeline/db.py）。"""
    report = (config.REPORT_DIR / "data_quality.md").read_text(encoding="utf-8")
    rows = [line for line in report.splitlines() if "✅" in line or "❌" in line]
    assert len(rows) == len(quality_checks.CHECKS) == 16
    assert all("✅ 通过" in r for r in rows), [r for r in rows if "❌" in r]


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
