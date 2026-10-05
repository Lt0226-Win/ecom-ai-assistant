-- =====================================================================
-- DIM 层：商品维度表（含【模拟】价格）
--
-- 为什么要模拟价格？
--   原始数据只有行为、没有价格，算不出 GMV（成交额）。
--   为了演示完整的电商指标体系，这里给每个商品生成一个模拟价格。
--   所有和金额相关的指标（GMV、客单价、RFM 里的 M）都基于模拟价格，
--   只用来演示方法，不代表真实业务。
--
-- 模拟规则（可复现：同一个商品每次运行价格都一样）：
--   1. 用 md5 把 id 变成 0~1 之间的固定“随机数”
--   2. 每个品类一个基准价：15 ~ 600 元之间（对数均匀分布）
--   3. 品类内每个商品在基准价上下浮动（对数正态分布，Box-Muller 变换）
--   4. 尾数处理成 x9.9 这种常见标价
--
-- 另外：极少数商品（约 1400 个）在数据里对应多个品类，取出现次数最多的品类。
-- =====================================================================
CREATE OR REPLACE TABLE dim_item AS
WITH item_cat_cnt AS (
    SELECT item_id, category_id, count(*) AS n
    FROM dwd_user_behavior
    GROUP BY item_id, category_id
),
item_cat AS (
    SELECT item_id, arg_max(category_id, n) AS category_id
    FROM item_cat_cnt
    GROUP BY item_id
),
rand AS (
    SELECT
        item_id,
        category_id,
        -- 品类级随机数 → 品类基准价
        (md5_number('c' || category_id::VARCHAR) % 1000000) / 1000000.0            AS u_cat,
        -- 商品级两个随机数 → 正态分布扰动（+0.5/1e6 避免取到 0 导致 ln(0)）
        ((md5_number('i' || item_id::VARCHAR) % 1000000) + 0.5) / 1000000.0        AS u1,
        ((md5_number('j' || item_id::VARCHAR) % 1000000) + 0.5) / 1000000.0        AS u2
    FROM item_cat
),
priced AS (
    SELECT
        item_id,
        category_id,
        exp(ln(15) + u_cat * ln(40))                                   AS cat_base_price,
        sqrt(-2 * ln(u1)) * cos(2 * pi() * u2)                         AS z
    FROM rand
)
SELECT
    item_id,
    category_id,
    round(cat_base_price, 2)                                           AS category_base_price,
    greatest(round(cat_base_price * exp(0.4 * z)) - 0.1, 1.9)         AS price,   -- 模拟售价（元）
    TRUE                                                               AS is_simulated_price
FROM priced;
