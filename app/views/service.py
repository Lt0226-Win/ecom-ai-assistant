"""智能客服：RAG 知识库问答 + 工单自动分类。"""
import pandas as pd
import streamlit as st

from ai import llm, rag, tickets
from app import charts
from app.ui import H, card, card_title, esc, note, page_header, plan_box, table

page_header("智能客服", eyebrow="RAG 知识库问答 · 工单分类",
            sub="顾客提问时，先从店铺规则文档里检索相关条款，再让大模型只根据这些条款回答，并标注来源；查不到的问题直接转人工。"
                "工单进来自动分类、判断紧急程度，方便分派。",
            meta=rag.get_retriever().mode)

tab1, tab2 = st.tabs(["知识库问答", "工单分类"])

# ---------------------------------------------------------------- 知识库问答
with tab1:
    if not llm.available():
        plan_box("未配置大模型：只展示检索结果", ["在 .env 填写 DEEPSEEK_API_KEY 后，会基于检索结果生成回答。"], tag="提示")
    if "cs_chat" not in st.session_state:
        st.session_state.cs_chat = []

    examples = ["退款退到银行卡要多久", "内裤拆开了能退吗", "刚买完就降价了，能退差价吗？", "物流三天没动了怎么办",
                "有个客服打电话要我的验证码，正常吗", "你们支持货到付款吗？"]

    def _pick():
        st.session_state["_cs_pending"] = st.session_state.get("cs_ex")
        st.session_state["cs_ex"] = None

    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    c1.pills("常见问题", examples, key="cs_ex", on_change=_pick)
    if c2.button("清空", width="stretch", key="cs_clear"):
        st.session_state.cs_chat = []
        st.rerun()

    def _show(res: dict) -> None:
        if res["error"]:
            st.error(res["error"])
        if res["answer"]:
            H(f'<div style="font-size:14px;line-height:1.8">{esc(res["answer"])}</div>')
        if res["need_human"]:
            H('<span class="tag" style="color:#d9363e;background:#d9363e17">建议转人工</span>')
        if res["hits"]:
            with st.expander(f"检索到的参考资料（{res['mode']}，最高分 {res['top_score']}）",
                             expanded=not llm.available()):
                for i, h in enumerate(res["hits"], 1):
                    H(f'<div class="note"><b>[{i}] {esc(h["source"])}</b>　分数 {h["score"]}</div>'
                      f'<div class="sqlbox" style="font-family:inherit">{esc(h["text"])}</div>')
        else:
            note(f"知识库里没有找到相关内容（最高分 {res['top_score']} < 阈值 {rag.NO_ANSWER_SCORE}），没有调用大模型，直接转人工。")

    for item in st.session_state.cs_chat:
        with st.chat_message("user"):
            st.write(item["question"])
        with st.chat_message("assistant"):
            _show(item)

    q = st.chat_input("输入顾客的问题，例如：买的衣服不喜欢还能退吗？") or st.session_state.pop("_cs_pending", None)
    if q:
        with st.chat_message("user"):
            st.write(q)
        with st.chat_message("assistant"):
            hist = []
            for it in st.session_state.cs_chat[-2:]:
                hist += [{"role": "user", "content": it["question"]}, {"role": "assistant", "content": it["answer"]}]
            with st.spinner("检索规则并生成回答…"):
                res = rag.answer(q, history=hist)
            _show(res)
        st.session_state.cs_chat.append(res)

# ---------------------------------------------------------------- 工单分类
with tab2:
    tk = pd.DataFrame(tickets.load_tickets())
    c1, c2 = st.columns([7, 5], gap="medium")
    with c1, card("tk_one"):
        card_title("分类一条工单", "大模型" if llm.available() else "规则法（未配置大模型）")
        text = st.text_area("工单内容", "等了一周还没到，再不到我就要退款了，气死了", height=90,
                            label_visibility="collapsed")
        if st.button("分类", type="primary"):
            rule = tickets.classify_rule(text)
            if llm.available():
                try:
                    out = tickets.classify_llm(text)
                    table(pd.DataFrame([{"类别": out.get("category"), "紧急程度": out.get("urgency"),
                                         "情绪": out.get("sentiment"), "摘要": out.get("summary"),
                                         "转人工": "是" if out.get("need_human") else "否"}]),
                          [("类别", "类别", "text"), ("紧急程度", "紧急程度", "text"), ("情绪", "情绪", "text"),
                           ("摘要", "摘要", "wrap"), ("转人工", "转人工", "text")])
                except Exception as e:  # noqa: BLE001
                    st.error(f"调用大模型失败：{e}")
            note(f"规则法（关键词匹配）结果：<b>{esc(rule['category'])}</b>")
    with c2, card("tk_cats"):
        card_title("类别定义", "8 类")
        table(pd.DataFrame([{"c": k, "d": v} for k, v in tickets.CATEGORIES.items()]),
              [("c", "类别", "text"), ("d", "包含", "wrap")])

    st.write("")
    with card("tk_batch"):
        card_title("批量分类：60 条模拟工单", "规则法，实时计算")
        tk["pred"] = [tickets.classify_rule(t)["category"] for t in tk["text"]]
        acc = (tk["pred"] == tk["label"]).mean()
        dist = tk["pred"].value_counts()
        a, b = st.columns([2, 3], gap="medium")
        with a:
            st.plotly_chart(charts.hbars(dist.index.tolist(), dist.values.tolist(), [f"{v} 条" for v in dist.values],
                                         height=320), config=charts.CONFIG, width="stretch")
            note(f"规则法准确率 <b>{acc:.1%}</b>。注意：工单和关键词都是项目作者写的，这个准确率偏乐观；"
                 "真实工单说法更多样，规则法会明显下降，这正是用大模型分类的理由。大模型准确率见 reports/service_eval.md。")
        with b:
            wrong = tk[tk["pred"] != tk["label"]]
            card_title("分错的工单", f"{len(wrong)} 条")
            table(wrong, [("text", "工单", "wrap"), ("label", "标注", "text"), ("pred", "规则法", "text")])
