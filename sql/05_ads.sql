-- =====================================================================
-- ADS 层：应用层指标表，直接给看板、周报、AI 问数使用
-- =====================================================================

-- ---------- 1. 每日核心指标 ----------
CREATE OR REPLACE TABLE ads_daily_kpi AS
WITH beh AS (
    SELECT
        dt,
        count(*)                                               AS active_users,   -- 日活（当天有任意行为的用户）
        sum(pv_cnt)::BIGINT                                    AS pv_cnt,
        sum(cart_cnt)::BIGINT                                  AS cart_cnt,
        sum(fav_cnt)::BIGINT                                   AS fav_cnt,
        sum(buy_cnt)::BIGINT                                   AS order_cnt,
        count(*) FILTER (WHERE buy_cnt > 0)                    AS buyers
    FROM dws_user_daily
    GROUP BY dt
),
ord AS (
    SELECT order_date AS dt, sum(amount) AS gmv
    FROM dwd_order
    GROUP BY order_date
)
SELECT
    beh.dt,
    ['周日','周一','周二','周三','周四','周五','周六'][dayofweek(beh.dt) + 1] AS weekday,
    beh.active_users,
    beh.pv_cnt,
    beh.cart_cnt,
    beh.fav_cnt,
    beh.order_cnt,
    beh.buyers,
    round(ord.gmv, 2)                                          AS gmv,             -- 模拟金额
    round(beh.buyers / beh.active_users, 4)                    AS pay_user_rate,   -- 用户口径转化率
    round(beh.order_cnt / beh.pv_cnt, 4)                       AS pv_order_rate,   -- 次数口径转化率
    round(ord.gmv / beh.order_cnt, 2)                          AS avg_order_amount, -- 笔单价
    round(ord.gmv / beh.buyers, 2)                             AS arppu,           -- 客单价（每个付费用户贡献）
    round(beh.pv_cnt / beh.active_users, 1)                    AS pv_per_user
FROM beh
JOIN ord USING (dt)
ORDER BY dt;

-- ---------- 2. 分时段行为（9 天平均到每天） ----------
CREATE OR REPLACE TABLE ads_hourly_behavior AS
SELECT
    event_hour                                                       AS hour,
    round(count(*) FILTER (WHERE behavior = 'pv')   / count(DISTINCT event_date)) AS avg_pv,
    round(count(*) FILTER (WHERE behavior = 'cart') / count(DISTINCT event_date)) AS avg_cart,
    round(count(*) FILTER (WHERE behavior = 'fav')  / count(DISTINCT event_date)) AS avg_fav,
    round(count(*) FILTER (WHERE behavior = 'buy')  / count(DISTINCT event_date)) AS avg_buy,
    round(count(*) FILTER (WHERE behavior = 'buy') / count(*) FILTER (WHERE behavior = 'pv'), 4) AS pv_order_rate
FROM dwd_user_behavior
GROUP BY event_hour
ORDER BY hour;

-- ---------- 3. 用户转化漏斗（用户口径，逐级包含） ----------
-- 第 1 步：有浏览的用户
-- 第 2 步：其中有加购或收藏的用户
-- 第 3 步：其中最终购买的用户
CREATE OR REPLACE TABLE ads_funnel AS
WITH flags AS (
    SELECT
        pv_cnt > 0                                AS s1,
        pv_cnt > 0 AND (cart_cnt + fav_cnt) > 0   AS s2,
        pv_cnt > 0 AND (cart_cnt + fav_cnt) > 0 AND buy_cnt > 0 AS s3
    FROM dws_user_summary
),
steps AS (
    SELECT 1 AS step_no, '浏览' AS step_name, count(*) FILTER (WHERE s1) AS users FROM flags
    UNION ALL
    SELECT 2, '加购/收藏', count(*) FILTER (WHERE s2) FROM flags
    UNION ALL
    SELECT 3, '购买', count(*) FILTER (WHERE s3) FROM flags
)
SELECT
    step_no,
    step_name,
    users,
    round(users / lag(users) OVER (ORDER BY step_no), 4)          AS conv_from_prev,
    round(users / first_value(users) OVER (ORDER BY step_no), 4)  AS conv_from_first
FROM steps
ORDER BY step_no;

-- 购买路径：买过的用户里，多少人加购/收藏过，多少人直接购买
CREATE OR REPLACE TABLE ads_buy_path AS
SELECT
    CASE
        WHEN cart_cnt > 0 AND fav_cnt > 0 THEN '加购+收藏后购买'
        WHEN cart_cnt > 0                 THEN '加购后购买'
        WHEN fav_cnt > 0                  THEN '收藏后购买'
        ELSE                                   '直接购买'
    END                                         AS path,
    count(*)                                    AS buyers,
    round(count(*) / sum(count(*)) OVER (), 4)  AS share
FROM dws_user_summary
WHERE buy_cnt > 0
GROUP BY 1
ORDER BY buyers DESC;

-- ---------- 4. 留存：某天活跃的用户，第 N 天后是否还活跃 ----------
CREATE OR REPLACE TABLE ads_retention AS
WITH base AS (
    SELECT dt, count(*) AS active_users
    FROM dws_user_daily
    GROUP BY dt
),
pairs AS (
    SELECT a.dt, date_diff('day', a.dt, b.dt) AS n, count(*) AS retained
    FROM dws_user_daily AS a
    JOIN dws_user_daily AS b
      ON a.user_id = b.user_id AND b.dt > a.dt
    GROUP BY 1, 2
)
SELECT
    base.dt,
    base.active_users,
    -- 超出数据范围的天数还看不到结果，记为 NULL
    round(max(retained) FILTER (WHERE n = 1) / base.active_users, 4) AS d1_retention,
    round(max(retained) FILTER (WHERE n = 3) / base.active_users, 4) AS d3_retention,
    round(max(retained) FILTER (WHERE n = 7) / base.active_users, 4) AS d7_retention
FROM base
LEFT JOIN pairs USING (dt)
GROUP BY base.dt, base.active_users
ORDER BY base.dt;

-- ---------- 5. 复购：按“购买天数”分布 ----------
CREATE OR REPLACE TABLE ads_repurchase AS
SELECT
    CASE WHEN buy_days >= 5 THEN '5天及以上' ELSE buy_days::VARCHAR || '天' END AS buy_days_bucket,
    count(*)                                                       AS buyers,
    round(count(*) / sum(count(*)) OVER (), 4)                     AS share
FROM dws_user_summary
WHERE buy_days > 0
GROUP BY 1
ORDER BY min(buy_days);

-- ---------- 6. RFM 用户分层 ----------
-- R（最近一次购买距 12-04 的天数，越小越好）
-- F（购买天数，>=2 天算高，即复购用户）
-- M（消费金额，高于付费用户中位数算高）
-- R 也以付费用户中位数为界。三个维度高/低组合成 8 类。
CREATE OR REPLACE TABLE ads_user_rfm AS
WITH buyers AS (
    SELECT
        user_id,
        date_diff('day', CAST(last_buy_time AS DATE), DATE '${END_DATE}' + 1) AS recency_days,
        buy_days                                                               AS frequency,
        gmv                                                                    AS monetary
    FROM dws_user_summary
    WHERE buy_cnt > 0
),
th AS (
    SELECT median(recency_days) AS r_med, median(monetary) AS m_med FROM buyers
),
scored AS (
    SELECT
        b.*,
        b.recency_days <= th.r_med AS r_high,
        b.frequency    >= 2        AS f_high,
        b.monetary     >= th.m_med AS m_high
    FROM buyers b CROSS JOIN th
)
SELECT
    user_id, recency_days, frequency, round(monetary, 2) AS monetary,
    (CASE WHEN r_high THEN 'R高' ELSE 'R低' END) ||
    (CASE WHEN f_high THEN 'F高' ELSE 'F低' END) ||
    (CASE WHEN m_high THEN 'M高' ELSE 'M低' END)        AS rfm_code,
    CASE
        WHEN     r_high AND     f_high AND     m_high THEN '重要价值客户'
        WHEN     r_high AND NOT f_high AND     m_high THEN '重要发展客户'
        WHEN NOT r_high AND     f_high AND     m_high THEN '重要保持客户'
        WHEN NOT r_high AND NOT f_high AND     m_high THEN '重要挽留客户'
        WHEN     r_high AND     f_high AND NOT m_high THEN '一般价值客户'
        WHEN     r_high AND NOT f_high AND NOT m_high THEN '一般发展客户'
        WHEN NOT r_high AND     f_high AND NOT m_high THEN '一般保持客户'
        ELSE                                               '一般挽留客户'
    END                                                AS segment
FROM scored;

CREATE OR REPLACE TABLE ads_rfm_segment AS
SELECT
    segment,
    count(*)                                         AS users,
    round(count(*) / sum(count(*)) OVER (), 4)       AS user_share,
    round(sum(monetary), 2)                          AS gmv,
    round(sum(monetary) / sum(sum(monetary)) OVER (), 4) AS gmv_share,
    round(avg(recency_days), 2)                      AS avg_recency_days,
    round(avg(frequency), 2)                         AS avg_frequency,
    round(avg(monetary), 2)                          AS avg_monetary
FROM ads_user_rfm
GROUP BY segment
ORDER BY gmv DESC;

-- ---------- 7. 品类排行（全周期） ----------
CREATE OR REPLACE TABLE ads_category_rank AS
SELECT
    category_id,
    sum(pv_cnt)::BIGINT                             AS pv_cnt,
    sum(cart_cnt)::BIGINT                           AS cart_cnt,
    sum(fav_cnt)::BIGINT                            AS fav_cnt,
    sum(buy_cnt)::BIGINT                            AS buy_cnt,
    round(sum(gmv), 2)                              AS gmv,
    round(sum(buy_cnt) / nullif(sum(pv_cnt), 0), 4) AS pv_order_rate,
    rank() OVER (ORDER BY sum(gmv) DESC)            AS gmv_rank,
    rank() OVER (ORDER BY sum(pv_cnt) DESC)         AS pv_rank
FROM dws_category_daily
GROUP BY category_id;
