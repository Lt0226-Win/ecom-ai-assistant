"""用户分层：RFM 模型 + 复购。"""
import streamlit as st

from app import charts
from app.data import db_ready, no_db_hint, q
from app.ui import H, card, card_title, fmt, fmt_rate, fmt_wan, note, page_header, stats, table

if not db_ready():
    no_db_hint()

page_header("用户分层", eyebrow="RFM 模型",
            sub="把付费用户按 R（最近一次购买距今几天）、F（有购买的天数）、M（消费金额）分成 8 类，"
                "不同人群用不同的运营动作。",
            meta="M 基于模拟价格")

seg = q("SELECT * FROM ads_rfm_segment")
rep = q("SELECT * FROM ads_repurchase")
th = q("""SELECT median(recency_days) r_med, median(monetary) m_med, count(*) n,
                 avg(monetary) m_avg, count(*) FILTER (WHERE frequency >= 2) / count(*) rep FROM ads_user_rfm""").iloc[0]

stats([
    ("付费用户", fmt_wan(th["n"], 1), "万", "9 天内至少买过一次"),
    ("复购率", fmt_rate(th["rep"]), "", "2 天及以上有购买"),
    ("人均消费（模拟）", fmt(th["m_avg"], 0), "元", f"中位数 {fmt(th['m_med'], 0)} 元"),
    ("重要价值客户", fmt_rate(seg.loc[seg["segment"] == "重要价值客户", "user_share"].sum()), "",
     f"贡献 {fmt_rate(seg.loc[seg['segment'] == '重要价值客户', 'gmv_share'].sum())} 的 GMV"),
], cols=4)

ACTION = {
    "重要价值客户": "核心用户：会员权益、专属客服、新品优先体验，重点防流失",
    "重要发展客户": "买得多但只买过一次：引导复购，推荐关联商品、发复购券",
    "重要保持客户": "以前常买、最近没来：推送召回消息、个性化推荐",
    "重要挽留客户": "高价值但沉默：大额优惠券召回，了解流失原因",
    "一般价值客户": "常买但金额低：凑单满减、推荐高客单价商品",
    "一般发展客户": "新客或低频：新人专享、小额券培养购买习惯",
    "一般保持客户": "频次尚可、近期不活跃：低成本推送提醒",
    "一般挽留客户": "价值低且沉默：低成本触达，不投入重资源",
}

st.write("")
with card("seg"):
    card_title("各人群画像和运营建议", "R / F / M 为人群平均值")
    d = seg.assign(action=seg["segment"].map(ACTION))
    table(d, [("segment", "人群", "text"), ("users", "人数", "num0"), ("user_share", "人数占比", "rate"),
              ("gmv_share", "GMV 占比", "rate"), ("avg_recency_days", "R（天）", "num1"),
              ("avg_frequency", "F（天）", "num1"), ("avg_monetary", "M（元）", "num0"), ("action", "运营建议", "wrap")])

st.write("")
c1, c2 = st.columns(2, gap="medium")
with c1, card("share"):
    card_title("人数占比 vs 成交占比", "按 GMV 从高到低")
    st.plotly_chart(charts.grouped_hbars(seg["segment"], seg["user_share"], seg["gmv_share"], "人数占比", "GMV 占比"),
                    config=charts.CONFIG, width="stretch")
with c2, card("rep"):
    card_title("购买天数分布", "付费用户 9 天内有几天下过单")
    st.plotly_chart(charts.bars(rep["buy_days_bucket"], rep["buyers"], height=400), config=charts.CONFIG,
                    width="stretch")

st.write("")
with card("rule"):
    card_title("分层规则", "")
    H(f"""<ul class="reasons">
    <li><b>R 高</b>：最近一次购买距 12-04 不超过 {th['r_med']:.0f} 天（付费用户中位数）</li>
    <li><b>F 高</b>：有 2 天及以上下过单（即复购用户）。只有 9 天数据，按“天数”比按“次数”更能代表购买习惯</li>
    <li><b>M 高</b>：消费金额不低于 {th['m_med']:.0f} 元（付费用户中位数）</li>
    <li>三个维度各分高/低，组合成 2×2×2 = 8 类。阈值用中位数而不是平均数，因为消费金额是长尾分布，平均数会被少数大户拉高。</li>
    </ul>""")
    note("真实业务通常用 1–3 个月的数据、按五分位打分（每个维度 1–5 分）；这里数据只有 9 天，用简化的高/低两档。")
