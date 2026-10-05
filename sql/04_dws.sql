-- =====================================================================
-- DWS 层：轻度汇总表
-- 目的：把 1 亿行明细压缩成几百万、几万行，后面的分析和 AI 问数都基于这些表，速度快很多。
--
-- 性能小技巧：先按“用户×天”聚合一次（1 亿行 → 几百万行），
-- 后面的用户汇总、日活、留存都从这张小表算，避免对 1 亿行反复做 COUNT(DISTINCT)。
-- =====================================================================

-- ---------- 用户 × 天：每个用户每天一行 ----------
CREATE OR REPLACE TABLE dws_user_daily AS
SELECT
    user_id,
    event_date                                             AS dt,
    count(*) FILTER (WHERE behavior = 'pv')                AS pv_cnt,
    count(*) FILTER (WHERE behavior = 'cart')              AS cart_cnt,
    count(*) FILTER (WHERE behavior = 'fav')               AS fav_cnt,
    count(*) FILTER (WHERE behavior = 'buy')               AS buy_cnt
FROM dwd_user_behavior
GROUP BY user_id, event_date;

-- ---------- 用户汇总：每个用户一行 ----------
CREATE OR REPLACE TABLE dws_user_summary AS
WITH beh AS (
    SELECT
        user_id,
        min(dt)                                            AS first_active_date,
        max(dt)                                            AS last_active_date,
        count(*)                                           AS active_days,
        sum(pv_cnt)::BIGINT                                AS pv_cnt,
        sum(cart_cnt)::BIGINT                              AS cart_cnt,
        sum(fav_cnt)::BIGINT                               AS fav_cnt,
        sum(buy_cnt)::BIGINT                               AS buy_cnt,
        count(*) FILTER (WHERE buy_cnt > 0)                AS buy_days
    FROM dws_user_daily
    GROUP BY user_id
),
ord AS (
    SELECT
        user_id,
        min(order_time)                                    AS first_buy_time,
        max(order_time)                                    AS last_buy_time,
        sum(amount)                                        AS gmv
    FROM dwd_order
    GROUP BY user_id
)
SELECT
    beh.*,
    ord.first_buy_time,
    ord.last_buy_time,
    coalesce(ord.gmv, 0)                                   AS gmv
FROM beh
LEFT JOIN ord USING (user_id);

-- ---------- 商品汇总：每个商品一行 ----------
CREATE OR REPLACE TABLE dws_item_summary AS
WITH beh AS (
    SELECT
        item_id,
        count(*) FILTER (WHERE behavior = 'pv')            AS pv_cnt,
        count(*) FILTER (WHERE behavior = 'cart')          AS cart_cnt,
        count(*) FILTER (WHERE behavior = 'fav')           AS fav_cnt,
        count(*) FILTER (WHERE behavior = 'buy')           AS buy_cnt
    FROM dwd_user_behavior
    GROUP BY item_id
),
ord AS (
    SELECT item_id, count(DISTINCT user_id) AS buyers
    FROM dwd_order
    GROUP BY item_id
)
SELECT
    beh.item_id,
    i.category_id,
    i.price,
    beh.pv_cnt, beh.cart_cnt, beh.fav_cnt, beh.buy_cnt,
    coalesce(ord.buyers, 0)                                AS buyers,
    beh.buy_cnt * i.price                                  AS gmv
FROM beh
JOIN dim_item AS i USING (item_id)
LEFT JOIN ord USING (item_id);

-- ---------- 品类 × 天 汇总 ----------
CREATE OR REPLACE TABLE dws_category_daily AS
WITH beh AS (
    SELECT
        event_date                                         AS dt,
        category_id,
        count(*) FILTER (WHERE behavior = 'pv')            AS pv_cnt,
        count(*) FILTER (WHERE behavior = 'cart')          AS cart_cnt,
        count(*) FILTER (WHERE behavior = 'fav')           AS fav_cnt,
        count(*) FILTER (WHERE behavior = 'buy')           AS buy_cnt
    FROM dwd_user_behavior
    GROUP BY 1, 2
),
ord AS (
    SELECT order_date AS dt, category_id,
           count(DISTINCT user_id) AS buyers,
           sum(amount)             AS gmv
    FROM dwd_order
    GROUP BY 1, 2
)
SELECT
    beh.*,
    coalesce(ord.buyers, 0)                                AS buyers,
    coalesce(ord.gmv, 0)                                   AS gmv
FROM beh
LEFT JOIN ord USING (dt, category_id);
