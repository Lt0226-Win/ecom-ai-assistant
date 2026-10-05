"""图表（plotly）：统一的极简风格，和 A 股雷达系统一致。

规则：不在图内放标题（标题放在卡片上）；只用一个纵轴；网格线很淡；
主数据用近黑色，对比数据用浅灰。
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from app.ui import INK, INK3, LINE, LINE2, NEUTRAL

FONT = "-apple-system, BlinkMacSystemFont, PingFang SC, Helvetica Neue, sans-serif"
CONFIG = {"displayModeBar": False}


def _base(fig: go.Figure, height: int = 240, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=0, r=4, t=4 if not legend else 28, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=11, color=INK3),
        hovermode="x unified", showlegend=legend, bargap=0.35,
        hoverlabel=dict(bgcolor="white", bordercolor=LINE, font=dict(family=FONT, size=12, color=INK)),
        legend=dict(orientation="h", x=0, y=1.14, font=dict(size=11, color=INK3), bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(type="category", showgrid=False, showline=True, linecolor=LINE, ticks="",
                     tickfont=dict(size=10, color=INK3))
    fig.update_yaxes(showgrid=True, gridcolor=LINE2, zeroline=False, showline=False, ticks="",
                     tickfont=dict(size=10, color=INK3))
    return fig


def _shade_weekend(fig: go.Figure, dates: list[str], weekdays: list[str]) -> None:
    """周末加一块很淡的底色"""
    for d, w in zip(dates, weekdays):
        if w in ("周六", "周日"):
            fig.add_vrect(x0=dates.index(d) - 0.5, x1=dates.index(d) + 0.5,
                          fillcolor=INK, opacity=0.035, line_width=0, layer="below")


def daily_line(d: pd.DataFrame, y: str, fmt: str = ",.0f", height: int = 260) -> go.Figure:
    """按天走势（单条线），周末淡色底"""
    x = d["dt"].astype(str).str[5:].tolist()
    hover = [f"{a} {w}" for a, w in zip(x, d["weekday"])]
    fig = go.Figure(go.Scatter(
        x=x, y=d[y], mode="lines+markers", line=dict(color=INK, width=2),
        marker=dict(size=8, color=INK, line=dict(width=2, color="white")),
        customdata=hover, hovertemplate=f"%{{customdata}}　%{{y:{fmt}}}<extra></extra>"))
    _shade_weekend(fig, x, d["weekday"].tolist())
    _base(fig, height)
    fig.update_layout(hovermode="closest")
    return fig


def bars(x, y, fmt: str = ",.0f", height: int = 240, highlight=None, xtitle: str = "") -> go.Figure:
    """竖向柱状图。highlight：需要高亮的 x 值列表（深色），其他浅灰"""
    xs = [str(v) for v in x]
    hl = {str(v) for v in (highlight or [])}
    colors = [INK if (not hl or v in hl) else NEUTRAL for v in xs]
    fig = go.Figure(go.Bar(x=xs, y=y, marker=dict(color=colors, cornerradius=3),
                           hovertemplate=f"%{{x}}{xtitle}　%{{y:{fmt}}}<extra></extra>"))
    _base(fig, height)
    fig.update_layout(hovermode="closest")
    return fig


def hbars(labels, values, text, height: int | None = None, color=INK) -> go.Figure:
    """横向柱状图（排名、漏斗）"""
    fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker=dict(color=color, cornerradius=3),
                           text=text, textposition="outside", cliponaxis=False,
                           textfont=dict(size=12, color=INK), hovertemplate="%{y}　%{text}<extra></extra>"))
    _base(fig, height or 44 * len(labels) + 20)
    mx = max(values) if len(values) else 1
    fig.update_layout(hovermode="closest", bargap=0.42)
    fig.update_xaxes(type="linear", range=[0, mx * 1.28], showgrid=False, showline=False, showticklabels=False)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=12, color=INK))
    return fig


def grouped_hbars(labels, a, b, name_a: str, name_b: str, height: int | None = None) -> go.Figure:
    """两组对比的横向柱（例：用户占比 vs GMV 占比），深色 = a，浅灰 = b"""
    fig = go.Figure()
    fig.add_bar(y=labels, x=a, name=name_a, orientation="h", marker=dict(color=INK, cornerradius=3),
                hovertemplate=f"{name_a} %{{x:.1%}}<extra></extra>")
    fig.add_bar(y=labels, x=b, name=name_b, orientation="h", marker=dict(color=NEUTRAL, cornerradius=3),
                hovertemplate=f"{name_b} %{{x:.1%}}<extra></extra>")
    _base(fig, height or 46 * len(labels) + 40, legend=True)
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08, hovermode="y unified")
    fig.update_xaxes(type="linear", tickformat=".0%", showgrid=True, gridcolor=LINE2, showline=False)
    fig.update_yaxes(type="category", autorange="reversed", showgrid=False, tickfont=dict(size=12, color=INK))
    return fig


def line(x, y, fmt: str = ",.0f", height: int = 240, ytickformat: str | None = None) -> go.Figure:
    fig = go.Figure(go.Scatter(x=[str(v) for v in x], y=y, mode="lines", line=dict(color=INK, width=2),
                               hovertemplate=f"%{{x}}　%{{y:{fmt}}}<extra></extra>"))
    _base(fig, height)
    if ytickformat:
        fig.update_yaxes(tickformat=ytickformat)
    return fig


def quadrant_scatter(d: pd.DataFrame, x: str, y: str, label: str, size: str,
                     x_mid: float, y_mid: float, height: int = 420) -> go.Figure:
    """四象限散点：横轴流量（对数），纵轴转化率，点大小 = GMV"""
    s = d[size]
    sizes = 6 + 22 * (s / s.max()) ** 0.5
    fig = go.Figure(go.Scatter(
        x=d[x], y=d[y], mode="markers",
        marker=dict(size=sizes, color=INK, opacity=0.55, line=dict(width=1, color="white")),
        customdata=d[[label, size]].values,
        hovertemplate="品类 %{customdata[0]}<br>浏览 %{x:,.0f}　转化率 %{y:.2%}<br>GMV %{customdata[1]:,.0f} 元<extra></extra>"))
    fig.add_vline(x=x_mid, line=dict(color=LINE, width=1, dash="dot"))
    fig.add_hline(y=y_mid, line=dict(color=LINE, width=1, dash="dot"))
    for tx, ty, t, xa, ya in [(1, 1, "高流量 · 高转化", "right", "top"), (0, 1, "低流量 · 高转化", "left", "top"),
                              (1, 0, "高流量 · 低转化", "right", "bottom"), (0, 0, "低流量 · 低转化", "left", "bottom")]:
        fig.add_annotation(xref="paper", yref="paper", x=tx, y=ty, text=t, showarrow=False,
                           xanchor=xa, yanchor=ya, font=dict(size=11, color=INK3))
    _base(fig, height)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(type="log", dtick=1, showgrid=True, gridcolor=LINE2, title=dict(text="浏览量（对数刻度）", font=dict(size=11)))
    fig.update_yaxes(tickformat=".0%", title=dict(text="浏览→购买转化率", font=dict(size=11)))
    return fig
