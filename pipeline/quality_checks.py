"""
数据质量检查：建完表自动跑一遍，确认数据“对得上”。

思路：每条检查 = 一句 SQL 算出一个值 + 一个判断规则。
真实工作里这类检查通常放在调度任务的最后一步，不通过就报警、不让下游用。
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

# (检查名称, SQL, 判断规则, 规则说明)
CHECKS = [
    ("DWD 无空值",
     "SELECT count(*) FROM dwd_user_behavior WHERE user_id IS NULL OR item_id IS NULL "
     "OR category_id IS NULL OR behavior IS NULL OR event_time IS NULL",
     lambda v: v == 0, "= 0"),
    ("DWD 行为类型只有 4 种",
     "SELECT count(DISTINCT behavior) FROM dwd_user_behavior",
     lambda v: v == 4, "= 4"),
    ("DWD 日期范围正确（天数）",
     "SELECT count(DISTINCT event_date) FROM dwd_user_behavior "
     f"WHERE event_date BETWEEN DATE '{config.DATA_START_DATE}' AND DATE '{config.DATA_END_DATE}'",
     lambda v: v == 9, "= 9"),
    ("DWD 无日期越界",
     "SELECT count(*) FROM dwd_user_behavior "
     f"WHERE event_date < DATE '{config.DATA_START_DATE}' OR event_date > DATE '{config.DATA_END_DATE}'",
     lambda v: v == 0, "= 0"),
    ("DWD 无完全重复行",
     "SELECT count(*) - (SELECT count(*) FROM (SELECT DISTINCT user_id, item_id, category_id, behavior, ts "
     "FROM dwd_user_behavior)) FROM dwd_user_behavior",
     lambda v: v == 0, "= 0"),
    ("清洗剔除比例（ODS→DWD）",
     f"SELECT 1 - (SELECT count(*) FROM dwd_user_behavior) / "
     f"(SELECT count(*) FROM read_parquet('{config.ODS_PARQUET.as_posix()}'))",
     lambda v: 0 <= v < 0.001, "< 0.1%"),
    ("商品维度表覆盖全部商品",
     "SELECT (SELECT count(DISTINCT item_id) FROM dwd_user_behavior) - (SELECT count(*) FROM dim_item)",
     lambda v: v == 0, "差值 = 0"),
    ("商品维度表主键唯一",
     "SELECT count(*) - count(DISTINCT item_id) FROM dim_item",
     lambda v: v == 0, "= 0"),
    ("模拟价格全部为正",
     "SELECT count(*) FROM dim_item WHERE price IS NULL OR price <= 0",
     lambda v: v == 0, "= 0"),
    ("订单表行数 = 明细表购买行数",
     "SELECT (SELECT count(*) FROM dwd_order) - "
     "(SELECT count(*) FROM dwd_user_behavior WHERE behavior = 'buy')",
     lambda v: v == 0, "差值 = 0"),
    ("每日订单数之和 = 订单表行数",
     "SELECT (SELECT sum(order_cnt) FROM ads_daily_kpi) - (SELECT count(*) FROM dwd_order)",
     lambda v: v == 0, "差值 = 0"),
    ("品类日表 GMV 之和 = 订单 GMV",
     "SELECT abs((SELECT sum(gmv) FROM dws_category_daily) - (SELECT sum(amount) FROM dwd_order))",
     lambda v: v < 0.01, "误差 < 0.01"),
    ("用户汇总表用户数 = 明细去重用户数",
     "SELECT (SELECT count(*) FROM dws_user_summary) - (SELECT count(DISTINCT user_id) FROM dwd_user_behavior)",
     lambda v: v == 0, "差值 = 0"),
    ("漏斗逐级递减",
     "SELECT count(*) FROM (SELECT users, lag(users) OVER (ORDER BY step_no) AS prev FROM ads_funnel) "
     "WHERE prev IS NOT NULL AND users > prev",
     lambda v: v == 0, "违反数 = 0"),
    ("RFM 用户数 = 付费用户数",
     "SELECT (SELECT count(*) FROM ads_user_rfm) - (SELECT count(*) FROM dws_user_summary WHERE buy_cnt > 0)",
     lambda v: v == 0, "差值 = 0"),
    ("每日 PV 波动（最大/最小）",
     "SELECT max(pv_cnt) / min(pv_cnt) FROM ads_daily_kpi",
     lambda v: v < 2, "< 2 倍"),
]


def run_checks(con) -> bool:
    lines = [
        "# 数据质量检查报告",
        "",
        f"生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "| 检查项 | 结果值 | 规则 | 状态 |",
        "|---|---|---|---|",
    ]
    all_ok = True
    print("\n[质量检查]")
    for name, sql, rule, rule_text in CHECKS:
        value = con.execute(sql).fetchone()[0]
        value = float(value) if value is not None else None
        ok = value is not None and rule(value)
        all_ok &= ok
        shown = f"{value:.4%}" if "比例" in name else (f"{value:,.4g}" if value is not None else "NULL")
        status = "✅ 通过" if ok else "❌ 未通过"
        print(f"  {status}  {name}: {shown}（规则 {rule_text}）")
        lines.append(f"| {name} | {shown} | {rule_text} | {status} |")

    # 附上各层表行数，方便核对
    lines += ["", "## 各表行数", "", "| 表 | 行数 |", "|---|---|"]
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name"
    ).fetchall()
    for (t,) in tables:
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        lines.append(f"| {t} | {n:,} |")

    config.REPORT_DIR.mkdir(exist_ok=True)
    (config.REPORT_DIR / "data_quality.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return all_ok
