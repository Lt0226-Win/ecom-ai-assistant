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
    # 2026-10 安全审查发现的漏网写法：能读服务器上的任意文件
    "SELECT * FROM read_ndjson('/etc/passwd')",
    "SELECT * FROM sniff_csv('/home/ubuntu/ecom-ai-assistant/.env')",
    "SELECT * FROM parquet_metadata('x.parquet')",
    "SELECT * FROM query('SELECT * FROM read_text(''/etc/passwd'')')",   # 把语句藏进字符串
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


@pytest.mark.parametrize("template", [
    "SELECT * FROM sniff_csv('{p}')",
    "SELECT * FROM read_ndjson('{p}')",
    "SELECT * FROM read_csv('{p}')",
    "SELECT * FROM read_text('{p}')",
    "SELECT * FROM query('SELECT * FROM sniff_csv(''{p}'')')",
])
def test_read_only_connection_cannot_read_files(con, tmp_path, template):
    """即使禁用词名单漏掉了，只读连接也读不到硬盘上的文件（比如 .env 里的密钥）"""
    secret = tmp_path / ".env"
    secret.write_text("DEEPSEEK_API_KEY=sk-test-should-never-leak\n")
    with pytest.raises(duckdb.Error) as e:
        con.execute(template.format(p=secret.as_posix())).fetchall()
    assert "sk-test" not in str(e.value)


def test_read_only_settings_are_locked(con):
    """锁定后，SQL 不能把文件访问再打开，也不能改内存等设置"""
    for sql in ["SET enable_external_access=true", "SET memory_limit='100GB'"]:
        with pytest.raises(duckdb.Error):
            con.execute(sql)


def test_reopen_read_only_in_same_process(warehouse, con):
    """同一个程序里第二次打开只读连接（例如网页接口 + 定时任务）不能因为“设置已锁定”而报错"""
    from pipeline.db import connect
    c2 = connect(read_only=True, db_path=warehouse)
    assert c2.execute("SELECT count(*) FROM ads_daily_kpi").fetchone()[0] > 0
    c2.close()


def test_read_only_queries_still_work(con):
    """锁定后正常查询照常：汇总、排序、转成表格"""
    df = con.execute("SELECT dt, gmv FROM ads_daily_kpi ORDER BY gmv DESC").df()
    assert len(df) == 9


def test_eval_gold_sql_passes_safety_check():
    """两套评测集的标准答案 SQL 本身也必须是安全的只读查询（防止评测集写错）"""
    import json

    import config
    for name in ["text2sql_cases.json", "text2sql_holdout.json"]:
        for c in json.loads((config.ROOT / "eval" / name).read_text(encoding="utf-8")):
            if c["gold_sql"]:
                check_sql(c["gold_sql"])
