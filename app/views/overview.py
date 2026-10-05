"""经营总览：一屏看清整体经营情况。"""
import streamlit as st

from app import charts
from app.data import db_ready, no_db_hint, q
from app.ui import (H, bullets, card, card_title, delta_html, fmt, fmt_rate, fmt_wan, note, page_header, stats,
                    table)

if not db_ready():
    no_db_hint()

page_header("经营总览", eyebrow="淘宝用户行为 · 2017-11-25 至 12-03",
            sub="9 天、约 98.8 万用户、1 亿条浏览 / 加购 / 收藏 / 购买记录。先看整体规模和趋势，再看用户在哪个环节流失。",
            meta="金额类指标基于模拟价格")

k = q("SELECT * FROM ads_daily_kpi ORDER BY dt")
users = q("""SELECT count(*) AS users, count(*) FILTER (WHERE buy_cnt > 0) AS buyers,
                    count(*) FILTER (WHERE buy_days >= 2) AS repeat_buyers FROM dws_user_summary""").iloc[0]
hourly = q("SELECT * FROM ads_hourly_behavior ORDER BY hour")
rfm = q("SELECT * FROM ads_rfm_segment")

last, wk = k.iloc[-1], k.iloc[-8]  # 最后一天 vs 上周同一天
def wow(col):
    return last[col] / wk[col] - 1
wow_label = f"{str(last['dt'])[5:10]} vs 上周{last['weekday'][-1]}"

stats([
    ("GMV（模拟）", fmt_wan(k["gmv"].sum(), 0), "万元", delta_html(wow("gmv"), wow_label)),
    ("订单数", fmt_wan(k["order_cnt"].sum(), 1), "万", delta_html(wow("order_cnt"), wow_label)),
    ("付费用户", fmt_wan(users["buyers"], 1), "万", f"占全部用户 {fmt_rate(users['buyers'] / users['users'])}"),
    ("日均活跃用户", fmt_wan(k["active_users"].mean(), 1), "万", delta_html(wow("active_users"), wow_label)),
    ("复购率", fmt_rate(users["repeat_buyers"] / users["buyers"]), "", "付费用户中，2 天及以上有购买"),
], cols=5)

# ---------------- 第二行：趋势 + 要点
st.write("")
c1, c2 = st.columns([7, 5], gap="medium")
metrics = {"GMV（模拟，元）": ("gmv", ",.0f"), "订单数": ("order_cnt", ",.0f"), "日活跃用户": ("active_users", ",.0f"),
           "用户付费率": ("pay_user_rate", ".2%"), "浏览→购买转化率": ("pv_order_rate", ".2%"), "客单价（元）": ("arppu", ",.2f")}
with c1, card("trend"):
    a, b = st.columns([3, 2], vertical_alignment="center")
    a.markdown('<div class="ct">每日走势<span></span></div>', unsafe_allow_html=True)
    m = b.selectbox("指标", list(metrics), label_visibility="collapsed", key="ov_metric")
    col, f = metrics[m]
    st.plotly_chart(charts.daily_line(k, col, f), config=charts.CONFIG, width="stretch")
    note("灰色底 = 周末。")

with c2, card("obs"):
    card_title("关键发现", "由数据自动计算")
    sat1, sat2 = k[k["weekday"] == "周六"].iloc[0], k[k["weekday"] == "周六"].iloc[-1]
    peak = hourly.loc[hourly["avg_pv"].idxmax()]
    best = hourly.loc[hourly["pv_order_rate"].idxmax()]
    top = rfm.iloc[0]
    bullets([
        f"<b>次数口径和用户口径差很多</b>：每 100 次浏览只有 {k['order_cnt'].sum() / k['pv_cnt'].sum() * 100:.1f} 次购买，"
        f"但 9 天内有 {fmt_rate(users['buyers'] / users['users'], 0)} 的用户买过东西。",
        f"<b>12 月第一个周末流量明显放大</b>：周六日活 {fmt_wan(sat2['active_users'])} 万，"
        f"比上周六高 {fmt_rate(sat2['active_users'] / sat1['active_users'] - 1, 0)}，但转化率没有同步提升"
        f"（{fmt_rate(sat2['pv_order_rate'], 2)} vs {fmt_rate(sat1['pv_order_rate'], 2)}）。",
        f"<b>晚上是流量高峰</b>：{int(peak['hour'])} 点平均浏览量最高；"
        f"转化率最高的是 {int(best['hour'])} 点（{fmt_rate(best['pv_order_rate'], 2)}），夜间高峰反而转化偏低。",
        f"<b>头部用户贡献大部分成交</b>：{top['segment']}占付费用户 {fmt_rate(top['user_share'], 0)}，"
        f"贡献 {fmt_rate(top['gmv_share'], 0)} 的 GMV。",
    ])

# ---------------- 第三行：分时段
st.write("")
c1, c2 = st.columns(2, gap="medium")
with c1, card("hour_pv"):
    card_title("各时段平均浏览量", "9 天平均到每天 · 深色 = 晚高峰 19–23 点")
    st.plotly_chart(charts.bars(hourly["hour"], hourly["avg_pv"], highlight=range(19, 24), xtitle=" 点"),
                    config=charts.CONFIG, width="stretch")
with c2, card("hour_rate"):
    card_title("各时段浏览→购买转化率", "购买次数 ÷ 浏览次数")
    st.plotly_chart(charts.line(hourly["hour"].astype(str) + "点", hourly["pv_order_rate"], fmt=".2%",
                                ytickformat=".1%"), config=charts.CONFIG, width="stretch")

# ---------------- 第四行：明细
st.write("")
with card("detail"):
    card_title("每日明细", "金额单位：元（模拟）")
    d = k.copy()
    d["date"] = d["dt"].astype(str)
    table(d, [("date", "日期", "text"), ("weekday", "", "muted"), ("active_users", "日活", "num0"),
              ("pv_cnt", "浏览", "num0"), ("cart_cnt", "加购", "num0"), ("fav_cnt", "收藏", "num0"),
              ("order_cnt", "订单", "num0"), ("buyers", "付费用户", "num0"), ("gmv", "GMV", "num0"),
              ("pay_user_rate", "付费率", "rate"), ("pv_order_rate", "浏览转化", "rate"), ("arppu", "客单价", "num1")])
    H('<div class="note">付费率 = 当天付费用户 ÷ 当天活跃用户；浏览转化 = 订单数 ÷ 浏览次数；客单价 = GMV ÷ 付费用户。</div>')
