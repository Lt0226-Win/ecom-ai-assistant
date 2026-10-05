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
