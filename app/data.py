"""看板的数据读取：只读连接 + 缓存。"""
from __future__ import annotations

import threading

import pandas as pd
import streamlit as st

import config
from pipeline.db import connect


def db_ready() -> bool:
    return config.DB_PATH.exists()


def _warm(con) -> None:
    """预加载：提前导入画图库、把所有表读一遍（数据进入内存缓存），后面打开各页面更快"""
    try:
        import plotly.graph_objects  # noqa: F401  第一次导入约 0.5 秒
        for (t,) in con.execute("SELECT table_name FROM information_schema.tables").fetchall():
            con.cursor().execute(f"SELECT * FROM {t} LIMIT 200000").fetchall()
    except Exception:  # noqa: BLE001  预加载失败不影响正常使用
        pass


@st.cache_resource
def _con():
    con = connect(read_only=True)
    # 第一次打开时在后台预加载，不阻塞当前页面
    threading.Thread(target=_warm, args=(con,), daemon=True).start()
    return con


# 数据是静态的（9 天历史数据），查询结果一直缓存到服务重启，不设过期时间
@st.cache_data(show_spinner=False)
def q(sql: str, params: tuple | None = None) -> pd.DataFrame:
    """执行查询并返回 DataFrame。每次用一个新游标，多人同时访问也不会互相干扰。"""
    return _con().cursor().execute(sql, list(params or [])).df()


def no_db_hint() -> None:
    from app.ui import plan_box
    plan_box("还没有数据库", [
        "第一次使用请在项目根目录运行：<b>python pipeline/build_warehouse.py</b>",
        "大约 1 分钟，完成后刷新本页面。",
    ])
    st.stop()
