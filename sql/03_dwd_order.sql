-- =====================================================================
-- DWD 层：订单明细表（购买行为 + 模拟价格）
-- 约定：一条 buy 记录 = 一笔订单 = 购买 1 件商品。
-- 单独拆出来是因为订单只有约 200 万行，后面算金额时不用每次扫 1 亿行。
-- 品类沿用行为记录里的 category_id，和其他按品类统计的表保持同一口径。
-- =====================================================================
CREATE OR REPLACE TABLE dwd_order AS
SELECT
    b.user_id,
    b.item_id,
    b.category_id,
    b.event_time  AS order_time,
    b.event_date  AS order_date,
    b.event_hour  AS order_hour,
    i.price       AS amount        -- 订单金额（模拟价格）
FROM dwd_user_behavior AS b
JOIN dim_item AS i USING (item_id)
WHERE b.behavior = 'buy';
