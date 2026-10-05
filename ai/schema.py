"""语义层：告诉大模型“有哪些表、每列什么意思、指标怎么算”。

AI 问数准不准，七成取决于这里写得清不清楚。模型不认识我们的表，
它只能根据这里的说明去写 SQL。经验：
  1. 每张表写清楚“粒度”（一行代表什么）
  2. 每个指标写清楚“口径”（怎么算）
  3. 优先让模型用汇总表，少碰 1 亿行的明细表
"""
from __future__ import annotations

TABLES: dict[str, dict] = {
    "ads_daily_kpi": {
        "desc": "每日核心指标，一行 = 一天（共 9 天）",
        "cols": {
            "dt": "日期", "weekday": "星期（周一…周日）", "active_users": "日活跃用户数",
            "pv_cnt": "浏览次数", "cart_cnt": "加购次数", "fav_cnt": "收藏次数", "order_cnt": "订单数（购买次数）",
            "buyers": "付费用户数", "gmv": "成交额（元，模拟价格）", "pay_user_rate": "付费率 = buyers / active_users",
            "pv_order_rate": "浏览转化率 = order_cnt / pv_cnt", "avg_order_amount": "笔单价 = gmv / order_cnt",
            "arppu": "客单价 = gmv / buyers", "pv_per_user": "人均浏览次数",
        },
    },
    "ads_hourly_behavior": {
        "desc": "分小时行为，一行 = 一个小时（0-23 点），数值为 9 天平均到每天",
        "cols": {"hour": "小时 0-23", "avg_pv": "日均浏览次数", "avg_cart": "日均加购次数", "avg_fav": "日均收藏次数",
                 "avg_buy": "日均购买次数", "pv_order_rate": "该小时浏览转化率"},
    },
    "ads_funnel": {
        "desc": "用户转化漏斗（全周期，用户口径），3 行：浏览 → 加购/收藏 → 购买",
        "cols": {"step_no": "步骤序号", "step_name": "步骤名", "users": "用户数",
                 "conv_from_prev": "相对上一步转化率", "conv_from_first": "相对第一步转化率"},
    },
    "ads_buy_path": {
        "desc": "购买用户的购买路径分布（全周期）",
        "cols": {"path": "路径：加购后购买 / 收藏后购买 / 加购+收藏后购买 / 直接购买", "buyers": "用户数", "share": "占比"},
    },
    "ads_retention": {
        "desc": "活跃留存，一行 = 一天。注意 12-02、12-03 活跃用户异常多，落在这两天的留存率偏高",
        "cols": {"dt": "日期", "active_users": "当天活跃用户", "d1_retention": "次日留存率",
                 "d3_retention": "3 日留存率", "d7_retention": "7 日留存率（超出数据范围为 NULL）"},
    },
    "ads_repurchase": {
        "desc": "付费用户按购买天数分布",
        "cols": {"buy_days_bucket": "购买天数分组（1天…5天及以上）", "buyers": "用户数", "share": "占比"},
    },
    "ads_rfm_segment": {
        "desc": "RFM 人群汇总，一行 = 一类人群（共 8 类）",
        "cols": {"segment": "人群名称（重要价值客户、重要发展客户、重要保持客户、重要挽留客户、一般价值客户、一般发展客户、一般保持客户、一般挽留客户）",
                 "users": "人数", "user_share": "人数占比", "gmv": "GMV（元）", "gmv_share": "GMV 占比",
                 "avg_recency_days": "平均 R（最近购买距今天数）", "avg_frequency": "平均 F（购买天数）",
                 "avg_monetary": "平均 M（消费金额）"},
    },
    "ads_user_rfm": {
        "desc": "每个付费用户的 RFM 分层，一行 = 一个付费用户",
        "cols": {"user_id": "用户ID", "recency_days": "最近一次购买距 12-04 天数", "frequency": "购买天数",
                 "monetary": "消费金额（元）", "rfm_code": "如 R高F低M高", "segment": "人群名称"},
    },
    "ads_category_rank": {
        "desc": "品类全周期汇总排名，一行 = 一个品类。品类只有编号，没有名称",
        "cols": {"category_id": "品类ID", "pv_cnt": "浏览次数", "cart_cnt": "加购次数", "fav_cnt": "收藏次数",
                 "buy_cnt": "购买次数", "gmv": "GMV（元）", "pv_order_rate": "浏览转化率",
                 "gmv_rank": "GMV 排名（1 最高）", "pv_rank": "浏览量排名"},
    },
    "dws_category_daily": {
        "desc": "品类 × 天汇总，一行 = 一个品类在一天的数据",
        "cols": {"dt": "日期", "category_id": "品类ID", "pv_cnt": "浏览次数", "cart_cnt": "加购次数",
                 "fav_cnt": "收藏次数", "buy_cnt": "购买次数", "buyers": "付费用户数", "gmv": "GMV（元）"},
    },
    "dws_user_summary": {
        "desc": "用户全周期汇总，一行 = 一个用户（约 98.8 万）",
        "cols": {"user_id": "用户ID", "first_active_date": "首次活跃日期", "last_active_date": "最后活跃日期",
                 "active_days": "活跃天数", "pv_cnt": "浏览次数", "cart_cnt": "加购次数", "fav_cnt": "收藏次数",
                 "buy_cnt": "购买次数", "buy_days": "有购买的天数", "first_buy_time": "首次购买时间",
                 "last_buy_time": "最近购买时间", "gmv": "消费金额（元）"},
    },
    "dws_user_daily": {
        "desc": "用户 × 天汇总，一行 = 一个用户在一天的行为次数（约 680 万行）",
        "cols": {"user_id": "用户ID", "dt": "日期", "pv_cnt": "浏览次数", "cart_cnt": "加购次数",
                 "fav_cnt": "收藏次数", "buy_cnt": "购买次数"},
    },
    "dws_item_summary": {
        "desc": "商品全周期汇总，一行 = 一个商品（约 416 万）",
        "cols": {"item_id": "商品ID", "category_id": "品类ID", "price": "模拟价格（元）", "pv_cnt": "浏览次数",
                 "cart_cnt": "加购次数", "fav_cnt": "收藏次数", "buy_cnt": "购买次数", "buyers": "购买人数",
                 "gmv": "GMV（元）"},
    },
    "dwd_order": {
        "desc": "订单明细，一行 = 一笔订单（一次购买，1 件商品，约 200 万行）",
        "cols": {"user_id": "用户ID", "item_id": "商品ID", "category_id": "品类ID", "order_time": "下单时间",
                 "order_date": "下单日期", "order_hour": "下单小时", "amount": "订单金额（元）"},
    },
    "dim_item": {
        "desc": "商品维度表，一行 = 一个商品",
        "cols": {"item_id": "商品ID", "category_id": "品类ID", "category_base_price": "品类基准价",
                 "price": "模拟售价（元）", "is_simulated_price": "是否模拟价格（全部为 TRUE）"},
    },
    "dwd_user_behavior": {
        "desc": "用户行为明细（约 1 亿行，查询慢）。只有汇总表回答不了时才用，比如需要具体小时 + 具体日期 + 行为的组合",
        "cols": {"user_id": "用户ID", "item_id": "商品ID", "category_id": "品类ID",
                 "behavior": "行为：pv 浏览 / cart 加购 / fav 收藏 / buy 购买", "ts": "Unix 时间戳",
                 "event_time": "北京时间", "event_date": "日期", "event_hour": "小时 0-23"},
    },
}

BUSINESS_RULES = """
- 数据范围：2017-11-25（周六）至 2017-12-03（周日），共 9 天，北京时间。年份是 2017。
- “上周”“本周”等相对时间：以 2017-12-03 为“今天”。本周 = 11-27 至 12-03，上周 = 11-25 至 11-26（只有 2 天）。
- 金额（GMV、客单价、消费金额）都是模拟价格，回答时要提醒“金额为模拟”。
- 转化率有两种口径：次数口径（订单数 / 浏览次数）和用户口径（付费用户 / 活跃用户）。用户没说清时，默认用户口径，并在说明里写明口径。
- 复购用户：有 2 天及以上下过单的付费用户（buy_days >= 2）。复购率 = 复购用户 / 付费用户。
- 品类没有名称，只能用 category_id 表示。
- 问“某一天的某个小时”时，ads_hourly_behavior 是 9 天平均值，不能用；要用 dwd_order（order_date + order_hour）或 dwd_user_behavior（event_date + event_hour）按条件统计。
"""


def schema_text(con=None) -> str:
    """生成给大模型看的表结构说明。传入连接时会附上真实的列类型。"""
    types: dict[tuple, str] = {}
    if con is not None:
        for t, c, ty in con.execute(
                "SELECT table_name, column_name, data_type FROM information_schema.columns").fetchall():
            types[(t, c)] = ty
    existing = {t for t, _ in types} if types else set(TABLES)
    parts = []
    for t, info in TABLES.items():
        if t not in existing:      # 在线演示版数据库没有 1 亿行的明细表，就不告诉模型
            continue
        cols = "\n".join(f"    - {c} {types.get((t, c), '')}：{d}" for c, d in info["cols"].items())
        parts.append(f"表 {t}：{info['desc']}\n{cols}")
    return "\n\n".join(parts)
