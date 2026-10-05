# AI 问数评测报告：独立测试集

> 这 10 道题由项目作者另行出题，与开发集文字零重叠，其中 6 道用到开发集从未涉及的表。
> 提示词和语义层说明**没有针对这些题做任何修改**，所以这里的准确率代表模型在“没见过的问题”上的水平。

- 评测时间：2026-10-06 03:14
- 模型：deepseek-chat
- 题目数：10
- **执行准确率：100.0%**（10/10）
- 平均耗时：1.5 秒；需要自我修正（重试）的题：1 道

## 分类型结果

| 类型 | 正确 / 总数 |
|---|---|
| 具体时刻×明细表 | 1 / 1 |
| 留存 | 1 / 1 |
| 购买路径 | 1 / 1 |
| 复购分布 | 1 / 1 |
| RFM分位数 | 1 / 1 |
| 用户×天筛选 | 1 / 1 |
| 列间比较 | 1 / 1 |
| 跨天对比 | 1 / 1 |
| 多表子查询 | 1 / 1 |
| 拒答 | 1 / 1 |

## 逐题明细

| # | 类型 | 问题 | 结果 | 模型 SQL / 错误 |
|---|---|---|---|---|
| 1 | 具体时刻×明细表 | 12月3日上午10点有多少次浏览？ | ✅ | `SELECT COUNT(*) AS "浏览次数" FROM dwd_user_behavior WHERE behavior = 'pv' AND event_date = DATE '2017-12-03' AND event_hour = 10` |
| 2 | 留存 | 次日留存率最高的是哪一天？ | ✅ | `SELECT dt AS "日期", active_users AS "活跃用户数", round(d1_retention, 4) AS "次日留存率" FROM ads_retention WHERE d1_retention IS NOT NULL ORDER BY d1_retention DESC LIMIT 1` |
| 3 | 购买路径 | 直接购买用户占全部购买用户的比例？ | ✅ | `SELECT round(100.0 * SUM(CASE WHEN path = '直接购买' THEN buyers ELSE 0 END) / SUM(buyers), 4) AS "直接购买用户占比(%)" FROM ads_buy_path` |
| 4 | 复购分布 | 购买天数正好 3 天的付费用户多少人？ | ✅ | `SELECT buyers AS "购买天数正好3天的付费用户数" FROM ads_repurchase WHERE buy_days_bucket = '3天'` |
| 5 | RFM分位数 | 消费金额前 10% 的门槛是多少元？ | ✅ | `WITH t AS (SELECT monetary, NTILE(10) OVER (ORDER BY monetary DESC) AS decile FROM ads_user_rfm) SELECT round(MIN(monetary), 2) AS "消费金额前10%门槛_元" FROM t WHERE decile = 1` |
| 6 | 用户×天筛选 | 12月2日浏览超 100 次的用户多少人？ | ✅ | `SELECT COUNT(*) AS "浏览超100次用户数" FROM (SELECT user_id FROM dws_user_daily WHERE dt = DATE '2017-12-02' GROUP BY user_id HAVING SUM(pv_cnt) > 100) t` |
| 7 | 列间比较 | 收藏次数比购买次数多的商品多少个？ | ✅ | `SELECT COUNT(*) AS "收藏次数多于购买次数的商品数" FROM dws_item_summary WHERE fav_cnt > buy_cnt` |
| 8 | 跨天对比 | GMV 最高的一天比最低的一天高多少？ | ✅ | `SELECT round(MAX(daily_gmv) - MIN(daily_gmv), 2) AS "GMV最高与最低之差(元)", round(MAX(daily_gmv), 2) AS "最高日GMV(元)", round(MIN(daily_gmv), 2) AS "最低日GMV(元)" FROM (SELECT dt, SUM(gmv) AS daily_gmv FROM dws_category_daily GROUP BY dt) t` |
| 9 | 多表子查询 | 收藏最多的 3 个品类各有多少商品？ | ✅ | `SELECT category_id AS "品类ID", fav_cnt AS "收藏次数", (SELECT COUNT(*) FROM dws_item_summary i WHERE i.category_id = c.category_id) AS "商品数" FROM ads_category_rank c ORDER BY fav_cnt DESC LIMIT 3` |
| 10 | 拒答 | 退货率是多少？ | ✅ | `（未生成 SQL，拒答）` |

## 题目说明

- 第 2 题：字面答案是 12-01（98.25%）。分析报告认为 12-01/12-02 的留存跳升是数据集抽样造成的异常，但这道题考的是“按字面查数”
- 第 5 题：连续分位数与离散分位数结果相差在 0.5% 以内都判对

## 错题分析（手动填写）

- 错在哪：
- 原因：（语义层没写清？口径歧义？模型能力？）
- 改进：
