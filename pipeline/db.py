"""DuckDB 连接工具：所有模块都通过这里拿数据库连接。"""
import os
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402


def connect(read_only: bool = False, db_path=None) -> duckdb.DuckDBPyConnection:
    """
    打开数据仓库。

    read_only=True：只读模式。看板、AI 问数都用只读，
    这样就算 AI 生成了 DROP/DELETE 之类的语句也改不了数据。

    只读模式还会“锁死”两件事（2026-10 安全审查后加的）：
      1. enable_external_access=false：禁止 SQL 读硬盘上的文件、访问网络。
         只读只保证“改不了数据”，不保证“读不到别的东西”——DuckDB 自带 sniff_csv、read_ndjson
         这类能读任意文件的函数，不关掉的话，AI 被诱导写出读文件的 SQL，就可能读到 .env 里的密钥。
      2. lock_configuration=true：锁定所有设置，之后谁也改不回来（包括上面那条）。
    建仓（build_warehouse.py）用读写模式，需要读 CSV / Parquet，不受影响。
    """
    path = str(db_path or config.DB_PATH)
    os.makedirs(config.DUCKDB_TEMP_DIR, exist_ok=True)
    con = duckdb.connect(path, read_only=read_only)
    if read_only and con.execute("SELECT current_setting('lock_configuration')").fetchone()[0]:
        # 同一个程序里再次打开同一个库时，DuckDB 会复用之前那个已经锁好设置的库，不用（也不能）再设置一遍
        return con
    con.execute(f"SET memory_limit='{config.DUCKDB_MEMORY_LIMIT}'")
    con.execute(f"SET threads={config.DUCKDB_THREADS}")
    con.execute(f"SET temp_directory='{config.DUCKDB_TEMP_DIR}'")   # 必须在关闭文件访问之前设置
    con.execute("SET preserve_insertion_order=false")
    if read_only:
        con.execute("SET enable_external_access=false")
        con.execute("SET lock_configuration=true")
    return con


def new_cursor(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """从共享连接派生一个独立游标。

    DuckDB 的同一个连接对象不能被多个线程同时使用；看板和接口都是多线程的，
    所以每次查询都用 con.cursor() 派生一个新游标：它们共享同一个数据库，但互不干扰，
    超时中断（interrupt）也只影响自己这一个游标。"""
    return con.cursor()
