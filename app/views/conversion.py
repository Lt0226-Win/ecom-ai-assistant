"""用户转化：漏斗、购买路径、留存。"""
import streamlit as st

from app import charts
from app.data import db_ready, no_db_hint, q
from app.ui import H, NEUTRAL, bullets, card, card_title, fmt_rate, fmt_wan, note, page_header, stats, table

if not db_ready():
    no_db_hint()

page_header("用户转化", eyebrow="用户在哪一步流失",
            sub="用“用户口径”看漏斗：每一步统计做过这个动作的人数（逐级包含）。再看买过的人走了哪条路径、活跃用户第二天还回不回来。")

f = q("SELECT * FROM ads_funnel ORDER BY step_no")
path = q("SELECT * FROM ads_buy_path")
ret = q("SELECT * FROM ads_retention ORDER BY dt")
cnt = q("SELECT sum(pv_cnt) pv, sum(cart_cnt) + sum(fav_cnt) cf, sum(order_cnt) buy FROM ads_daily_kpi").iloc[0]

stats([
    ("浏览用户", fmt_wan(f.iloc[0]["users"], 1), "万", "9 天内浏览过商品"),
    ("加购 / 收藏用户", fmt_wan(f.iloc[1]["users"], 1), "万", f"浏览用户的 {fmt_rate(f.iloc[1]['conv_from_prev'])}"),
    ("购买用户", fmt_wan(f.iloc[2]["users"], 1), "万", f"加购/收藏用户的 {fmt_rate(f.iloc[2]['conv_from_prev'])}"),
    ("整体转化", fmt_rate(f.iloc[2]["conv_from_first"]), "", "浏览用户 → 购买用户"),
], cols=4)

st.write("")
c1, c2 = st.columns(2, gap="medium")
with c1, card("funnel"):
    card_title("用户漏斗", "人数 · 括号内为上一步转化率")
    text = [f"{u / 1e4:.1f} 万" + ("" if i == 0 else f"（{r * 100:.1f}%）")
            for i, (u, r) in enumerate(zip(f["users"], f["conv_from_prev"]))]
    st.plotly_chart(charts.hbars(f["step_name"], f["users"], text, height=200), config=charts.CONFIG, width="stretch")
    card_title("同样三步，换成“次数口径”", "")
    t2 = [f"{v / 1e4:,.0f} 万次" for v in (cnt["pv"], cnt["cf"], cnt["buy"])]
    st.plotly_chart(charts.hbars(["浏览", "加购/收藏", "购买"], [cnt["pv"], cnt["cf"], cnt["buy"]], t2,
                                 height=200, color=NEUTRAL), config=charts.CONFIG, width="stretch")
    note(f"次数口径下，浏览 → 购买只有 {cnt['buy'] / cnt['pv'] * 100:.1f}%；用户口径是 {fmt_rate(f.iloc[2]['conv_from_first'])}。"
         "两个数都对，回答的问题不同：前者看“流量效率”，后者看“用户最终有没有买”。")

with c2, card("path"):
    card_title("买过的用户走了哪条路径", "按是否加购、收藏划分")
    table(path, [("path", "购买路径", "text"), ("buyers", "人数", "num0"), ("share", "占比", "bar")])
    st.write("")
    bullets([
        f"<b>加购是最主要的购买前动作</b>：{fmt_rate(path.loc[path['path'].str.contains('加购'), 'share'].sum(), 0)} "
        "的购买用户加购过商品，购物车是促成下单的关键环节。",
        f"<b>约 {fmt_rate(path.loc[path['path'] == '直接购买', 'share'].sum(), 0)} 的人直接下单</b>：多为目标明确的复购或低价商品，"
        "适合用“再次购买”入口缩短路径。",
        "<b>可以做的事</b>：针对“加购未购买”的用户做购物车提醒、限时优惠，是最直接的转化抓手。",
    ])

st.write("")
with card("ret"):
    card_title("活跃留存", "某天活跃的用户，N 天后是否再次活跃")
    r = ret.copy()
    r["date"] = r["dt"].astype(str)
    table(r, [("date", "日期", "text"), ("active_users", "当天活跃用户", "num0"),
              ("d1_retention", "次日留存", "rate"), ("d3_retention", "3 日留存", "rate"),
              ("d7_retention", "7 日留存", "rate")])
    H('<div class="plan" style="margin-top:14px"><div class="h"><span class="tag">数据解读</span>'
      '留存数字为什么在 12-02 前后突然跳到 98%？</div><ul>'
      '<li>只要“N 天后”那一天落在 12-02 或 12-03，留存率就会跳到 98% 左右。</li>'
      '<li>这两天的活跃用户比前一周同期多了约 35%，几乎所有用户都出现了。'
      '这更像是<b>数据集的抽样方式</b>（抽取在这段时间有行为的用户）或大促预热造成的，不代表真实留存能力。</li>'
      '<li>结论：评估留存只看 11-25 至 11-30 的次日留存（约 78%–80%）更可靠。'
      '分析时先怀疑异常值，再下结论。</li></ul></div>')
