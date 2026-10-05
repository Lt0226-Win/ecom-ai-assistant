-- =====================================================================
-- DWD 层：清洗后的用户行为明细表
-- 来源：ODS 层原始数据（CSV 转成的 Parquet，未做任何处理）
-- 清洗规则：
--   1. 只保留 4 种合法行为：pv(浏览) cart(加购) fav(收藏) buy(购买)
--   2. 只保留数据集声明的时间范围（北京时间 2017-11-25 ~ 2017-12-03），
--      范围外的时间戳是脏数据（原始数据里有 1901 年、2037 年这种）
--   3. 完全相同的重复行只保留一条
--   4. Unix 时间戳 → 北京时间，并拆出日期、小时，方便后续按天/按小时统计
-- =====================================================================
CREATE OR REPLACE TABLE dwd_user_behavior AS
WITH cleaned AS (
    SELECT DISTINCT user_id, item_id, category_id, behavior, ts
    FROM read_parquet('${ODS_PATH}')
    WHERE behavior IN ('pv', 'cart', 'fav', 'buy')
      AND ts >= ${START_TS}
      AND ts <  ${END_TS}
      AND user_id IS NOT NULL
      AND item_id IS NOT NULL
      AND category_id IS NOT NULL
)
SELECT
    user_id,
    item_id,
    category_id,
    behavior,
    ts,
    -- ts 是 UTC 秒数，加 8 小时（28800 秒）得到北京时间
    make_timestamp((ts + 28800) * 1000000)                   AS event_time,
    CAST(make_timestamp((ts + 28800) * 1000000) AS DATE)     AS event_date,
    hour(make_timestamp((ts + 28800) * 1000000))             AS event_hour
FROM cleaned;
