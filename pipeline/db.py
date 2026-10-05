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
    """
    path = str(db_path or config.DB_PATH)
    os.makedirs(config.DUCKDB_TEMP_DIR, exist_ok=True)
    con = duckdb.connect(path, read_only=read_only)
    con.execute(f"SET memory_limit='{config.DUCKDB_MEMORY_LIMIT}'")
    con.execute(f"SET threads={config.DUCKDB_THREADS}")
    con.execute(f"SET temp_directory='{config.DUCKDB_TEMP_DIR}'")
    con.execute("SET preserve_insertion_order=false")
    return con


def new_cursor(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """从共享连接派生一个独立游标。

    DuckDB 的同一个连接对象不能被多个线程同时使用；看板和接口都是多线程的，
    所以每次查询都用 con.cursor() 派生一个新游标：它们共享同一个数据库，但互不干扰，
    超时中断（interrupt）也只影响自己这一个游标。"""
    return con.cursor()
