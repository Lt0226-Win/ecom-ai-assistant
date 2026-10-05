"""
生成在线演示用的精简数据库：复制除 1 亿行明细表以外的所有表。

运行：python pipeline/build_demo_db.py
输出：data/warehouse/ecom_demo.duckdb（约几百 MB，上传到服务器用）

为什么要精简：完整库约 2GB，服务器只有 2GB 内存、上传也慢；
看板和 AI 功能用到的都是汇总表，去掉明细表不影响演示。
"""
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

SKIP = {"dwd_user_behavior"}


def main(out: Path = config.WAREHOUSE_DIR / "ecom_demo.duckdb") -> None:
    if out.exists():
        out.unlink()
    con = duckdb.connect(str(out))
    con.execute(f"ATTACH '{config.DB_PATH.as_posix()}' AS src (READ_ONLY)")
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_catalog = 'src' ORDER BY 1").fetchall()]
    for t in tables:
        if t in SKIP:
            continue
        con.execute(f"CREATE TABLE main.{t} AS SELECT * FROM src.{t}")
        n = con.execute(f"SELECT count(*) FROM main.{t}").fetchone()[0]
        print(f"  {t}: {n:,} 行")
    con.execute("DETACH src")
    con.execute("CHECKPOINT")
    con.close()
    print(f"完成：{out}（{out.stat().st_size / 1e6:.0f} MB）")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else config.WAREHOUSE_DIR / "ecom_demo.duckdb")
