# 项目最早的一步：第一次用 DuckDB 打开 1 亿行原始 CSV，看数据长什么样（学习记录，不参与项目运行）
import duckdb

data = duckdb.read_csv(
    "data/raw/UserBehavior.csv",
    header=False,
    names=["user_id", "item_id", "category_id", "behavior", "ts"]
)
print(duckdb.sql("SELECT * FROM data LIMIT 10"))
print(duckdb.sql("SELECT COUNT(*) FROM data"))
print(duckdb.sql("SELECT behavior, COUNT(*) FROM data GROUP BY behavior"))
print(duckdb.sql("SELECT COUNT(DISTINCT user_id) FROM data"))
print(duckdb.sql("SELECT COUNT(DISTINCT user_id) FROM data where behavior = 'buy'"))