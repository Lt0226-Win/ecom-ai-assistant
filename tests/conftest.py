"""测试公共准备：在临时目录里用一份小的合成数据，跑一遍真实的数仓流程。

为什么不用真实数据：真实数据 3.5GB，GitHub 上的自动测试环境放不下也跑不动。
合成数据只有约 1.8 万行，但字段、时间范围、脏数据类型都和真实数据一致，
所以 SQL 分层、16 项质量检查、周报、接口都能在上面完整跑一遍（几秒钟）。
"""
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

BJ = timezone(timedelta(hours=8))
START = datetime(2017, 11, 25, tzinfo=BJ)


def _ts(day: int, rng: random.Random) -> int:
    return int((START + timedelta(days=day, seconds=rng.randint(0, 86399))).timestamp())


def make_synthetic_csv(path: Path, seed: int = 7) -> int:
    """生成与淘宝数据集同格式的 CSV：user_id,item_id,category_id,behavior,ts（无表头）"""
    rng = random.Random(seed)
    rows = []
    for u in range(1, 401):
        for _ in range(rng.randint(30, 60)):
            item = rng.randint(1, 300)
            cat = 1000 + item % 25
            day = rng.randint(0, 8)
            rows.append((u, item, cat, "pv", _ts(day, rng)))
            r = rng.random()
            if r < 0.15:
                rows.append((u, item, cat, "cart", _ts(day, rng)))
                if rng.random() < 0.5:
                    rows.append((u, item, cat, "buy", _ts(day, rng)))
            elif r < 0.2:
                rows.append((u, item, cat, "fav", _ts(day, rng)))
    # 每天保证有购买，避免周报里出现空的一天
    for day in range(9):
        rows.append((1, 1, 1001, "buy", _ts(day, rng)))
    # 脏数据：时间越界、未知行为、完全重复行（合计远小于 0.1%，与质量检查规则一致）
    rows += [(9, 9, 1009, "pv", 0), (9, 9, 1009, "pv", 2_100_000_000), (9, 9, 1009, "click", _ts(3, rng))]
    rows += rows[:5]
    rng.shuffle(rows)
    path.write_text("\n".join(",".join(map(str, r)) for r in rows) + "\n")
    return len(rows)


@pytest.fixture(scope="session")
def warehouse(tmp_path_factory):
    """建好的测试数据库路径（整个测试过程只建一次）"""
    tmp = tmp_path_factory.mktemp("wh")
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "RAW_CSV", tmp / "UserBehavior.csv")
    mp.setattr(config, "WAREHOUSE_DIR", tmp)
    mp.setattr(config, "ODS_PARQUET", tmp / "ods_user_behavior.parquet")
    mp.setattr(config, "DB_PATH", tmp / "test.duckdb")
    mp.setattr(config, "REPORT_DIR", tmp / "reports")
    mp.setattr(config, "DUCKDB_MEMORY_LIMIT", "1GB")
    mp.setattr(config, "DEEPSEEK_API_KEY", "")      # 测试不调用大模型
    mp.setattr(config, "EMBEDDING_API_KEY", "")
    make_synthetic_csv(config.RAW_CSV)

    import importlib
    from pipeline import build_warehouse, quality_checks
    importlib.reload(quality_checks)                # 质量检查里的路径在导入时就确定了，换路径后重新加载
    importlib.reload(build_warehouse)
    build_warehouse.main()
    yield config.DB_PATH
    mp.undo()


@pytest.fixture()
def con(warehouse):
    from pipeline.db import connect
    c = connect(read_only=True, db_path=warehouse)
    yield c
    c.close()
