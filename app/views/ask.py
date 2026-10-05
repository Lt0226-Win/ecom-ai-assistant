"""AI 问数：用中文提问，AI 写 SQL 查数并给出结论。"""
import json
import re

import pandas as pd
import streamlit as st

import config
from ai import llm, text2sql
from app import charts
from app.data import _con, db_ready, no_db_hint
from app.ui import H, card, card_title, esc, note, page_header, plan_box

if not db_ready():
    no_db_hint()

page_header("AI 问数", eyebrow="自然语言 → SQL → 结论",
            sub="不会写 SQL 也能查数：直接用中文提问，AI 根据数据表说明写出 SQL、在只读数据库里执行，再用几句话总结结果。"
                "每一步的 SQL 都可以展开检查。",
            meta=f"模型 {config.DEEPSEEK_MODEL}" if llm.available() else "演示模式")

EXAMPLES = ["哪一天的GMV最高？", "复购率是多少？", "GMV排名前5的品类是哪些？",
            "一天中哪个小时的平均购买次数最多？", "重要价值客户有多少人，贡献了多少比例的GMV？",
            "加购过但9天内从没购买的用户有多少？"]

rep = config.REPORT_DIR / "text2sql_eval.md"
if rep.exists():
    m = re.search(r"执行准确率：([\d.]+%)", rep.read_text(encoding="utf-8"))
    if m:
        note(f"离线评测：23 道标准题，执行准确率 <b>{m.group(1)}</b>（详见 reports/text2sql_eval.md）")

if "chat" not in st.session_state:
    st.session_state.chat = []   # 每一项：{"q": 问题, "ans": Answer}


def _auto_chart(df: pd.DataFrame):
    """结果是“一个维度 + 一个数值”、行数适中时，自动画图"""
    if df is None or len(df) < 2 or len(df) > 40 or df.shape[1] != 2:
        return None
    x, y = df.columns
    if not pd.api.types.is_numeric_dtype(df[y]):
        return None
    xs = df[x].astype(str).str[:10]
    if re.match(r"\d{4}-\d{2}-\d{2}$", xs.iloc[0]):
        return charts.line(xs.str[5:], df[y], fmt=",.4g")
    return charts.bars(xs, df[y], fmt=",.4g")


def _show(ans) -> None:
    if ans.error:
        st.error(ans.error)
    if ans.summary:
        H(f'<div style="font-size:14px;line-height:1.8;color:#1d1d1f">{esc(ans.summary)}</div>')
    if ans.data is not None and not ans.data.empty:
        fig = _auto_chart(ans.data)
        if fig is not None:
            st.plotly_chart(fig, config=charts.CONFIG, width="stretch")
        num_cols = {c: st.column_config.NumberColumn(format="localized")
                    for c in ans.data.columns if pd.api.types.is_numeric_dtype(ans.data[c])
                    and not str(c).lower().endswith("id")}
        st.dataframe(ans.data, hide_index=True, width="stretch", column_config=num_cols)
    if ans.sql:
        with st.expander(f"查看 SQL · {ans.seconds:.1f} 秒 · 尝试 {ans.attempts} 次"):
            if ans.explanation:
                note(f"思路：{esc(ans.explanation)}")
            H(f'<div class="sqlbox">{esc(ans.sql)}</div>')
            if len(ans.trace) > 1:
                note("第一次生成的 SQL 执行报错，AI 根据报错信息自动修正：")
                for t in ans.trace[:-1]:
                    H(f'<div class="sqlbox" style="opacity:.6">{esc(t["sql"])}\n\n-- 报错：{esc(t["error"][:300])}</div>')


def _history() -> list[dict]:
    """把最近 2 轮问答带给模型，支持追问（比如“那 12 月 1 日呢？”）"""
    h = []
    for item in st.session_state.chat[-2:]:
        a = item["ans"]
        h += [{"role": "user", "content": item["q"]},
              {"role": "assistant", "content": json.dumps({"sql": a.sql, "explanation": a.explanation},
                                                          ensure_ascii=False)}]
    return h


# ---------------- 演示模式：没有配置 API Key 时，用评测题的标准 SQL 展示页面效果
if not llm.available():
    plan_box("还没有配置大模型 API Key，当前是演示模式", [
        "在项目根目录新建 <b>.env</b> 文件，写入一行：<b>DEEPSEEK_API_KEY=你的密钥</b>，然后重启看板。",
        "演示模式下点击示例问题，会执行预先写好的标准 SQL，只用来展示页面效果。",
    ], tag="提示")
    cases = json.loads((config.ROOT / "eval" / "text2sql_cases.json").read_text(encoding="utf-8"))
    gold = {c["question"]: c["gold_sql"] for c in cases if c["gold_sql"]}
    st.write("")
    with card("demo"):
        q = st.pills("示例问题", list(gold)[:12], key="demo_q")
        if q:
            ans = text2sql.Answer(question=q, sql=gold[q], explanation="演示模式：标准答案 SQL", attempts=1)
            ans.data = text2sql.run_sql(_con(), gold[q])
            card_title(q, "")
            _show(ans)
    st.stop()


# ---------------- 正常模式
def _pick() -> None:
    """点了示例问题：记下来作为待提问，并清空选择（点一次只问一次）"""
    st.session_state["_pending"] = st.session_state.get("ex_q")
    st.session_state["ex_q"] = None


c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
c1.pills("试试这些问题", EXAMPLES, key="ex_q", on_change=_pick)
if c2.button("清空对话", width="stretch"):
    st.session_state.chat = []
    st.rerun()

for item in st.session_state.chat:
    with st.chat_message("user"):
        st.write(item["q"])
    with st.chat_message("assistant"):
        _show(item["ans"])

question = st.chat_input("用中文提问，例如：12月1日的付费用户比11月30日多多少？") or st.session_state.pop("_pending", None)
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("AI 正在写 SQL 并查询…"):
            ans = text2sql.ask(_con(), question, history=_history())
        _show(ans)
    st.session_state.chat.append({"q": question, "ans": ans})
