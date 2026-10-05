"""
一键构建数据仓库。

运行：python pipeline/build_warehouse.py

流程：
  原始 CSV ──① 转格式──▶ ODS（Parquet）
          ──② 清洗────▶ DWD（明细）
          ──③ 汇总────▶ DWS（轻度汇总）
          ──④ 指标────▶ ADS（应用指标）
          ──⑤ 质量检查─▶ reports/data_quality.md
"""
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from pipeline.db import connect  # noqa: E402
from pipeline.quality_checks import run_checks  # noqa: E402

BEIJING = timezone(timedelta(hours=8))


def _beijing_epoch(date_str: str) -> int:
    """'2017-11-25' → 北京时间当天 0 点对应的 Unix 秒数"""
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=BEIJING)
    return int(d.timestamp())


def build_ods(con) -> None:
    """① 原始 CSV → Parquet。Parquet 是列式压缩格式：3.5GB 变成约 650MB，查询快很多。"""
    if config.ODS_PARQUET.exists():
        print(f"[ODS] 已存在，跳过：{config.ODS_PARQUET.name}")
        return
    if not config.RAW_CSV.exists():
        raise FileNotFoundError(f"找不到原始数据：{config.RAW_CSV}")
    config.WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    print("[ODS] CSV → Parquet ...")
    con.execute(f"""
        COPY (
            SELECT * FROM read_csv('{config.RAW_CSV.as_posix()}', header = false,
                columns = {{'user_id': 'BIGINT', 'item_id': 'BIGINT', 'category_id': 'BIGINT',
                            'behavior': 'VARCHAR', 'ts': 'BIGINT'}})
        ) TO '{config.ODS_PARQUET.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
    """)


def render_sql(text: str) -> str:
    """把 SQL 文件里的 ${变量} 替换成实际值"""
    end_next_day = (datetime.strptime(config.DATA_END_DATE, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    params = {
        "ODS_PATH": config.ODS_PARQUET.as_posix(),
        "START_TS": str(_beijing_epoch(config.DATA_START_DATE)),
        "END_TS": str(_beijing_epoch(end_next_day)),
        "END_DATE": config.DATA_END_DATE,
    }
    for k, v in params.items():
        text = text.replace("${" + k + "}", v)
    return text


def main() -> None:
    t0 = time.time()
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = connect(read_only=False)

    build_ods(con)

    for sql_file in sorted(config.SQL_DIR.glob("*.sql")):
        t = time.time()
        con.execute(render_sql(sql_file.read_text(encoding="utf-8")))
        print(f"[SQL] {sql_file.name} 完成，用时 {time.time() - t:.1f}s")

    passed = run_checks(con)
    con.execute("CHECKPOINT")
    con.close()
    print(f"\n全部完成，总用时 {time.time() - t0:.1f}s，数据库：{config.DB_PATH}")
    if not passed:
        print("⚠️ 有数据质量检查未通过，详见 reports/data_quality.md")
        sys.exit(1)


if __name__ == "__main__":
    main()
