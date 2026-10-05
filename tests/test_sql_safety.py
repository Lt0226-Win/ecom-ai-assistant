"""AI 问数的安全防线：只允许一条只读查询。"""
import duckdb
import pytest

from ai.text2sql import UnsafeSQL, check_sql


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "select dt, gmv from ads_daily_kpi order by gmv desc limit 1;",
    "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
    "SELECT segment FROM ads_rfm_segment WHERE segment = '一般挽留客户'",
    "SELECT 'drop table x' AS note",                 # 关键字在字符串里，不算危险
    "-- 注释\nSELECT 1 /* 注释 */",
])
def test_allows_read_only_queries(sql):
    assert check_sql(sql)


@pytest.mark.parametrize("sql", [
    "DROP TABLE ads_daily_kpi",
    "DELETE FROM dwd_order",
    "UPDATE dim_item SET price = 0",
    "SELECT 1; DROP TABLE ads_daily_kpi",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM read_parquet('x.parquet')",
    "ATTACH 'other.db'",
    "COPY ads_daily_kpi TO 'out.csv'",
    "PRAGMA database_list",
    "SET memory_limit='100GB'",
    "INSTALL httpfs",
    "SELECT getenv('DEEPSEEK_API_KEY')",
    "",
    "-- 只有注释",
])
def test_rejects_dangerous_sql(sql):
    with pytest.raises(UnsafeSQL):
        check_sql(sql)


def test_read_only_connection_is_second_line_of_defence(con):
    # 即使安全检查漏掉了，只读连接也写不进去
    with pytest.raises(duckdb.Error):
        con.execute("CREATE TABLE hacked AS SELECT 1")
