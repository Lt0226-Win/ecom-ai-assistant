"""品类分析：哪些品类撑起了成交，哪些品类流量大但转化差。"""
import streamlit as st

from app import charts
from app.data import db_ready, no_db_hint, q
from app.ui import H, card, card_title, fmt, fmt_rate, fmt_wan, note, page_header, stats, table

if not db_ready():
    no_db_hint()

page_header("品类分析", eyebrow="流量 × 转化",
            sub="数据集里品类只有编号（已脱敏），没有名称。这里看品类的集中度，并用四象限找出“流量大但转化差”的机会品类。",
            meta="GMV 基于模拟价格")

rank = q("SELECT * FROM ads_category_rank ORDER BY gmv_rank")
tot = rank["gmv"].sum()
top10 = rank.head(10)["gmv"].sum() / tot
n_cat = len(rank)
n_80 = int((rank["gmv"].cumsum() / tot < 0.8).sum()) + 1

stats([
    ("品类数", fmt(n_cat), "个", f"有成交 {fmt((rank['buy_cnt'] > 0).sum())} 个"),
    ("Top 10 品类 GMV 占比", fmt_rate(top10), "", "按 GMV 排名"),
    ("贡献 80% GMV 的品类", fmt(n_80), "个", f"占全部品类 {fmt_rate(n_80 / n_cat)}"),
    ("整体浏览→购买转化", fmt_rate(rank["buy_cnt"].sum() / rank["pv_cnt"].sum(), 2), "", "所有品类合计"),
], cols=4)

st.write("")
with card("quad"):
    a, b = st.columns([3, 2], vertical_alignment="center")
    a.markdown('<div class="ct">品类四象限<span></span></div>', unsafe_allow_html=True)
    n = b.select_slider("范围", options=[100, 200, 300, 500], value=300, key="cat_n",
                        format_func=lambda v: f"浏览量前 {v} 的品类", label_visibility="collapsed")
    d = rank.sort_values("pv_cnt", ascending=False).head(n).copy()
    d["cat"] = d["category_id"].astype(str)
    x_mid, y_mid = d["pv_cnt"].median(), d["pv_order_rate"].median()
    st.plotly_chart(charts.quadrant_scatter(d, "pv_cnt", "pv_order_rate", "cat", "gmv", x_mid, y_mid),
                    config=charts.CONFIG, width="stretch")
    note("虚线 = 所选品类的中位数；点越大 GMV 越高。右下角“高流量 · 低转化”的品类最值得优化：流量已经有了，"
         "提升详情页、价格、评价等转化因素，带来的增量最大。")

st.write("")
c1, c2 = st.columns(2, gap="medium")
opp = d[(d["pv_cnt"] >= x_mid) & (d["pv_order_rate"] < y_mid)].sort_values("pv_cnt", ascending=False).head(10)
with c1, card("top"):
    card_title("GMV Top 10 品类", "")
    t = rank.head(10).assign(share=lambda x: x["gmv"] / tot, cat=lambda x: x["category_id"].astype(str))
    table(t, [("gmv_rank", "排名", "num0"), ("cat", "品类编号", "text"), ("gmv", "GMV", "num0"),
              ("share", "GMV 占比", "rate"), ("pv_order_rate", "转化率", "rate"), ("pv_rank", "流量排名", "num0")])
with c2, card("opp"):
    card_title("机会品类：高流量 · 低转化", f"浏览量前 {n} 中，按浏览量排序")
    o = opp.assign(cat=opp["category_id"].astype(str), gap=y_mid - opp["pv_order_rate"])
    table(o, [("cat", "品类编号", "text"), ("pv_cnt", "浏览量", "num0"), ("pv_order_rate", "转化率", "rate"),
              ("buy_cnt", "订单", "num0"), ("gmv", "GMV", "num0")])
    if not o.empty:
        extra = (o["pv_cnt"] * (y_mid - o["pv_order_rate"])).sum()
        H(f'<div class="note">如果这 {len(o)} 个品类的转化率提升到中位数，约可多出 '
          f'<b>{fmt_wan(extra, 1)} 万</b>笔订单（粗略估算）。</div>')

st.write("")
with card("drill"):
    a, b = st.columns([3, 2], vertical_alignment="center")
    a.markdown('<div class="ct">单个品类每日走势<span></span></div>', unsafe_allow_html=True)
    cat = b.selectbox("品类", rank.head(50)["category_id"].tolist(), key="cat_pick",
                      format_func=lambda v: f"品类 {v}（GMV 第 {int(rank.loc[rank['category_id'] == v, 'gmv_rank'].iloc[0])}）",
                      label_visibility="collapsed")
    dd = q("""SELECT c.dt, k.weekday, c.pv_cnt, c.buy_cnt, c.gmv, c.buy_cnt / c.pv_cnt AS rate
              FROM dws_category_daily c JOIN ads_daily_kpi k USING (dt)
              WHERE c.category_id = ? ORDER BY c.dt""", (int(cat),))
    x1, x2 = st.columns(2, gap="medium")
    with x1:
        card_title("浏览量", "")
        st.plotly_chart(charts.daily_line(dd, "pv_cnt", height=220), config=charts.CONFIG, width="stretch")
    with x2:
        card_title("GMV（模拟，元）", "")
        st.plotly_chart(charts.daily_line(dd, "gmv", height=220), config=charts.CONFIG, width="stretch")
