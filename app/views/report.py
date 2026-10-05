"""自动周报：一键生成 + 数字核对 + 推送飞书。"""
import re

import streamlit as st

import config
from ai import llm, weekly_report
from app.data import _con, db_ready, no_db_hint
from app.ui import H, card, card_title, esc, note, page_header, plan_box

if not db_ready():
    no_db_hint()

page_header("自动周报", eyebrow="SQL 算数 · AI 写分析 · 飞书推送",
            sub="数字全部由 SQL 计算，大模型只负责把数字写成分析文字；生成后自动核对文中数字，对不上的会标出来。"
                "每周一早上可由 n8n 定时触发，自动推送到飞书群。",
            meta=("大模型已配置" if llm.available() else "未配置大模型：使用模板") + " · "
                 + ("飞书已配置" if config.FEISHU_WEBHOOK else "未配置飞书"))

c1, c2, c3 = st.columns([2, 2, 3], vertical_alignment="bottom")
use_llm = c1.toggle("用大模型写分析", value=llm.available(), disabled=not llm.available(),
                    help="关闭时用固定模板生成（不调用大模型）")
if c2.button("生成本周周报", type="primary", width="stretch"):
    with st.spinner("正在计算指标并生成周报…"):
        rep = weekly_report.generate(_con().cursor(), use_llm=use_llm)
        weekly_report.save(rep)
        st.session_state["weekly"] = rep

rep = st.session_state.get("weekly")
if not rep:
    st.write("")
    plan_box("周报包含什么", [
        "核心结论：本周 GMV、订单、付费用户，以及和上周同期的对比",
        "指标表现：日活、付费率、最好 / 最差的一天、浏览高峰时段",
        "值得关注：增长和下滑最快的品类、漏斗、核心用户群",
        "下周建议：具体可执行的运营动作",
    ])
    st.stop()

st.write("")
c1, c2 = st.columns([7, 4], gap="medium")
with c1, card("doc"):
    card_title(rep["title"], "大模型生成" if rep["source"] == "llm" else "模板生成")
    body = re.sub(r"^#{1,6}\s*(.+)$", r"**\1**", rep["markdown"].split("\n", 1)[1], flags=re.M)
    st.markdown(body)

with c2:
    with card("check"):
        card_title("数字核对", "")
        if rep["source"] != "llm":
            note("模板生成的周报，数字直接来自 SQL，不需要核对。")
        elif rep["unverified_numbers"]:
            H('<div style="font-size:13px;color:#d9363e;line-height:1.8">以下数字在计算结果里找不到，'
              '可能是模型自己算的或编的，发出前请人工确认：<br><b>'
              + "、".join(esc(n) for n in rep["unverified_numbers"]) + "</b></div>")
        else:
            H('<div style="font-size:13px;color:#15935a">✓ 文中所有数字都能在计算结果中找到</div>')
        if rep.get("error"):
            note(f"大模型调用失败，已改用模板：{esc(rep['error'][:200])}")
    st.write("")
    with card("send"):
        card_title("发送", "")
        if st.button("推送到飞书群", width="stretch", disabled=not config.FEISHU_WEBHOOK):
            try:
                weekly_report.push_feishu(rep)
                st.success("已推送到飞书")
            except Exception as e:  # noqa: BLE001
                st.error(f"推送失败：{e}")
        if not config.FEISHU_WEBHOOK:
            note("在 .env 里填写 FEISHU_WEBHOOK（飞书群 → 设置 → 群机器人 → 自定义机器人）后可推送。")
        st.download_button("下载 Markdown", rep["markdown"], file_name=f"weekly_{rep['facts']['period']['end']}.md",
                           width="stretch")
    st.write("")
    with st.expander("查看 SQL 计算出的原始数据（给大模型的输入）"):
        st.json(rep["facts"], expanded=False)
