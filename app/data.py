"""看板的数据读取：只读连接 + 缓存。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from pipeline.db import connect


def db_ready() -> bool:
    return config.DB_PATH.exists()


@st.cache_resource
def _con():
    return connect(read_only=True)


@st.cache_data(ttl=600, show_spinner=False)
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
