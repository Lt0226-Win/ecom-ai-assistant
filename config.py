"""
项目统一配置。

所有路径、密钥、参数都从这里取，其他代码不写死。
密钥放在项目根目录的 .env 文件里（不会提交到 Git），格式见 .env.example。
"""
import os
import tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # 没装 python-dotenv 时也能跑数据部分
    load_dotenv = None

ROOT = Path(__file__).resolve().parent
if load_dotenv:
    load_dotenv(ROOT / ".env")

# ---------- 数据路径 ----------
RAW_CSV = ROOT / "data" / "raw" / "UserBehavior.csv"
WAREHOUSE_DIR = ROOT / "data" / "warehouse"
ODS_PARQUET = WAREHOUSE_DIR / "ods_user_behavior.parquet"
DB_PATH = Path(os.getenv("DB_PATH", str(WAREHOUSE_DIR / "ecom.duckdb")))
SQL_DIR = ROOT / "sql"
REPORT_DIR = ROOT / "reports"

# ---------- DuckDB 运行参数 ----------
# 内存不够时 DuckDB 会把中间结果写到临时目录，所以放在系统临时目录里
DUCKDB_TEMP_DIR = os.getenv("DUCKDB_TEMP_DIR", os.path.join(tempfile.gettempdir(), "duckdb_tmp"))
DUCKDB_MEMORY_LIMIT = os.getenv("DUCKDB_MEMORY_LIMIT", "4GB")
DUCKDB_THREADS = int(os.getenv("DUCKDB_THREADS", "4"))

# ---------- 业务参数 ----------
# 数据集官方说明的时间范围（北京时间），范围外的记录视为脏数据
DATA_START_DATE = "2017-11-25"
DATA_END_DATE = "2017-12-03"

# ---------- 大模型（DeepSeek，兼容 OpenAI 接口） ----------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ---------- 向量模型（可选，用于智能客服的混合检索） ----------
# DeepSeek 没有向量接口，可以用硅基流动等兼容 OpenAI 的服务（例如 BAAI/bge-m3）。不填则只用 BM25 检索。
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

# ---------- 在线演示 ----------
# DEMO_MODE=1：部署到公网的演示版（数据库只有汇总表，AI 调用有每日上限，防止被刷费用）
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
DEMO_DAILY_LIMIT = int(os.getenv("DEMO_DAILY_LIMIT", "0"))   # 每天最多调用大模型多少次，0 = 不限制
USAGE_FILE = ROOT / "data" / "llm_usage.json"
PORTFOLIO_URL = os.getenv("PORTFOLIO_URL", "/")   # 演示版里“返回作品集首页”链接的地址

# ---------- 飞书群机器人 ----------
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
