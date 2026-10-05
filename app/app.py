"""电商 AI 运营助手 · 主程序入口

启动：双击“启动看板.command”，或在项目根目录运行
    streamlit run app/app.py

页面结构（先看经营结论，再用 AI 提效）：
  经营分析   经营总览 / 用户转化 / 用户分层 / 品类分析
  AI 助手    AI 问数 / 自动周报 / 智能客服
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="电商 AI 运营助手", page_icon=":material/storefront:", layout="wide")

import config  # noqa: E402
from app import ui  # noqa: E402

pages = {
    "经营分析": [
        st.Page("views/overview.py", title="经营总览", icon=":material/dashboard:", default=True),
        st.Page("views/conversion.py", title="用户转化", icon=":material/filter_alt:"),
        st.Page("views/users.py", title="用户分层", icon=":material/group:"),
        st.Page("views/category.py", title="品类分析", icon=":material/category:"),
    ],
    "AI 助手": [
        st.Page("views/ask.py", title="AI 问数", icon=":material/forum:"),
        st.Page("views/report.py", title="自动周报", icon=":material/article:"),
        st.Page("views/service.py", title="智能客服", icon=":material/support_agent:"),
    ],
}

nav = st.navigation(pages)
ui.setup_page()
if config.DEMO_MODE:
    # 在线演示版：每页顶部放一个返回作品集首页的链接（手机上侧边栏默认收起，所以放在正文里）
    ui.H(f'<a href="{config.PORTFOLIO_URL}" target="_self" style="font-size:13px;color:#8e8e93;'
         f'text-decoration:none">← 返回作品集首页</a>')
with st.sidebar:
    ui.H('<div class="side-l">数据说明</div>')
    ui.H('<div class="side-m">淘宝用户行为数据（阿里天池公开数据集）<br>'
         '2017-11-25 至 12-03 · 约 98.8 万用户 · 1 亿条行为<br>'
         '原始数据没有价格，金额类指标（GMV、客单价等）基于<b>模拟价格</b>，仅用于演示分析方法。</div>')
    if config.DEMO_MODE:
        ui.H('<div class="side-l" style="margin-top:18px">在线演示版</div>')
        ui.H('<div class="side-m">为节省服务器资源，演示版只包含汇总表（不含 1 亿行明细）。'
             f'AI 功能每天限 {config.DEMO_DAILY_LIMIT} 次调用。完整版见 '
             '<a href="https://github.com/Lt0226-Win/ecom-ai-assistant" target="_blank">GitHub</a>。</div>')
nav.run()
