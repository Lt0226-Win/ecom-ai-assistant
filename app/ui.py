"""界面设计系统（沿用 A 股雷达系统的风格）：配色、排版、组件。

设计原则：
- 克制：一个主色（近黑）+ 红/绿两个语义色（红 = 上升，绿 = 下降），其余全部是灰阶。
- 层次：页头 → 统计卡 → 图表卡片 → 明细表，信息从“结论”到“细节”。
- 留白：卡片之间 20px 以上，表格只保留必要的列。
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------- 设计令牌
INK, INK2, INK3 = "#1d1d1f", "#5f5e5a", "#8e8d88"
LINE, LINE2, CARD = "#e6e5e1", "#f0efeb", "#ffffff"
UP, DOWN, FLAT = "#d9363e", "#15935a", "#8e8d88"
NEUTRAL = "#c9c8c3"

CSS = f"""
<style>
.block-container {{max-width: 1240px; padding-top: 2.6rem; padding-bottom: 5rem;}}
[data-testid="stHeader"] {{background: transparent;}}
[data-testid="stSidebarNavSeparator"] {{margin: .6rem 0;}}

[class*="st-key-card"] {{background: {CARD}; border-radius: 16px !important; padding: 20px 22px !important;}}

.ph {{display:flex; justify-content:space-between; align-items:flex-end; gap:24px; margin: 0 0 6px;}}
.ph .eyebrow {{font-size:11px; letter-spacing:.12em; color:{INK3}; font-weight:600; margin-bottom:8px;}}
.ph h1 {{font-size:28px; line-height:1.15; font-weight:650; letter-spacing:-.02em; margin:0; padding:0; color:{INK};}}
.ph .sub {{font-size:13px; color:{INK2}; margin-top:8px; max-width:760px; line-height:1.6;}}
.ph .meta {{font-size:12px; color:{INK3}; text-align:right; white-space:nowrap; line-height:1.9;}}

.sec {{display:flex; justify-content:space-between; align-items:baseline; margin: 22px 0 2px;}}
.sec .t {{font-size:15px; font-weight:600; color:{INK}; letter-spacing:-.01em;}}
.sec .c {{font-size:12px; color:{INK3};}}
.ct {{font-size:13px; font-weight:600; color:{INK}; margin-bottom:12px; display:flex; justify-content:space-between; gap:12px;}}
.ct span {{font-weight:400; color:{INK3}; font-size:12px; text-align:right;}}

.tag {{display:inline-block; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;
       color:{INK2}; background:#efeeea; vertical-align:middle;}}

.stats {{display:grid; gap:1px; background:{LINE}; border:1px solid {LINE}; border-radius:16px; overflow:hidden;}}
.stat {{background:{CARD}; padding:20px 22px; min-height:124px; box-sizing:border-box;}}
.stat .l {{font-size:12px; color:{INK3};}}
.stat .v {{font-size:26px; font-weight:600; letter-spacing:-.02em; margin-top:8px; color:{INK}; line-height:1.15;}}
.stat .v small {{font-size:13px; font-weight:500; color:{INK3}; margin-left:3px;}}
.stat .s {{font-size:12px; color:{INK3}; margin-top:6px;}}

.tbl {{width:100%; border-collapse:collapse; font-size:13px;}}
.tbl th {{font-weight:500; color:{INK3}; font-size:12px; text-align:left; white-space:nowrap; padding:0 10px 10px; border-bottom:1px solid {LINE};}}
.tbl td {{padding:10px; border-bottom:1px solid {LINE2}; color:{INK}; font-variant-numeric:tabular-nums; white-space:nowrap;}}
.tbl td.wrap {{white-space:normal; color:{INK2}; min-width:220px;}}
.tbl tr:last-child td {{border-bottom:none;}}
.tbl .r {{text-align:right;}}
.tbl .m {{color:{INK3};}}
.tbl td:first-child, .tbl th:first-child {{padding-left:0;}}
.tbl td:last-child, .tbl th:last-child {{padding-right:0;}}
.bar {{display:inline-block; width:56px; height:4px; border-radius:2px; background:{LINE2}; vertical-align:middle; margin-right:8px;}}
.bar b {{display:block; height:4px; border-radius:2px; background:{INK};}}
.up, .tbl td.up {{color:{UP};}} .down, .tbl td.down {{color:{DOWN};}} .muted, .tbl td.muted {{color:{INK3};}}

.note {{font-size:12px; color:{INK3}; line-height:1.8; margin-top:8px;}}
.reasons {{margin:0 !important; padding:0 !important; list-style:none;}}
.reasons li {{font-size:13px; color:{INK2}; padding:8px 0; border-bottom:1px solid {LINE2}; line-height:1.7;}}
.reasons li:last-child {{border-bottom:none;}}
.reasons li b {{color:{INK}; font-weight:600;}}

.plan {{border:1px dashed #d3d2cd; border-radius:14px; padding:16px 20px;}}
.plan .h {{display:flex; align-items:center; gap:10px; font-size:13px; font-weight:600; color:{INK};}}
.plan ul {{margin:10px 0 0 0; padding-left:18px;}}
.plan li {{font-size:12.5px; color:{INK2}; line-height:1.9;}}

.side-l {{font-size:11px; letter-spacing:.12em; color:{INK3}; font-weight:600; margin: 4px 0 2px;}}
.side-m {{font-size:12px; color:{INK3}; line-height:1.8;}}

.tblwrap {{overflow-x:auto; -webkit-overflow-scrolling:touch;}}
@media (max-width: 700px) {{
  .stats {{grid-template-columns: repeat(2, 1fr) !important;}}
  .stat {{min-height: 0; padding: 16px;}}
  .stat .v {{font-size: 22px;}}
  .ph {{flex-direction: column; align-items: flex-start; gap: 8px;}}
  .ph .meta {{text-align: left;}}
}}

.sqlbox {{background:#fafaf8; border:1px solid {LINE}; border-radius:10px; padding:12px 14px;
          font-family: SFMono-Regular, Menlo, monospace; font-size:12px; color:{INK2}; white-space:pre-wrap;}}
</style>
"""


def setup_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def H(s: str) -> None:
    """渲染一段 HTML（组件统一出口）。"""
    st.html(s)


# ---------------------------------------------------------------- 格式化
def na(v) -> bool:
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def esc(s) -> str:
    return html.escape(str(s))


def fmt(v, nd=0, suffix="") -> str:
    return "—" if na(v) else f"{v:,.{nd}f}{suffix}"


def fmt_rate(v, nd=1) -> str:
    """0.6801 → 68.0%"""
    return "—" if na(v) else f"{v * 100:.{nd}f}%"


def fmt_wan(v, nd=1) -> str:
    """大数字用“万”：1234567 → 123.5万"""
    return "—" if na(v) else f"{v / 1e4:,.{nd}f}"


def tone(v) -> str:
    if na(v):
        return "muted"
    return "up" if v > 0 else "down" if v < 0 else "muted"


def delta_html(v, label: str = "") -> str:
    """环比变化：+3.2% 红色，-3.2% 绿色"""
    if na(v):
        return label
    color = UP if v > 0 else DOWN if v < 0 else FLAT
    return f'<span style="color:{color}">{v * 100:+.1f}%</span> {esc(label)}'


# ---------------------------------------------------------------- 组件
def page_header(title: str, sub: str = "", eyebrow: str = "", meta: str = "") -> None:
    H(f'<div class="ph"><div><div class="eyebrow">{esc(eyebrow)}</div><h1>{esc(title)}</h1>'
      + (f'<div class="sub">{sub}</div>' if sub else "")
      + f'</div><div class="meta">{meta}</div></div>')


def section(title: str, caption: str = "") -> None:
    H(f'<div class="sec"><div class="t">{esc(title)}</div><div class="c">{caption}</div></div>')


def card_title(title: str, caption: str = "") -> None:
    H(f'<div class="ct">{esc(title)}<span>{caption}</span></div>')


def card(key: str):
    """白色卡片容器。"""
    return st.container(border=True, key=f"card_{key}")


def stats(items: list[tuple], cols: int = 4) -> None:
    """items: (标签, 数值, 单位, 说明HTML, 颜色或None)"""
    cells = []
    for it in items:
        label, value, unit, sub, color = (list(it) + [None] * 5)[:5]
        st_ = f' style="color:{color}"' if color else ""
        cells.append(f'<div class="stat"><div class="l">{esc(label)}</div>'
                     f'<div class="v"{st_}>{value}{f"<small>{unit}</small>" if unit else ""}</div>'
                     f'<div class="s">{sub or "&nbsp;"}</div></div>')
    H(f'<div class="stats" style="grid-template-columns:repeat({cols},1fr)">{"".join(cells)}</div>')


def bullets(items: list[str]) -> None:
    """要点列表，items 里可以带 <b> 标签"""
    H('<ul class="reasons">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>")


def plan_box(title: str, items: list[str], tag: str = "") -> None:
    li = "".join(f"<li>{i}</li>" for i in items)
    t = f'<span class="tag">{esc(tag)}</span>' if tag else ""
    H(f'<div class="plan"><div class="h">{t}{esc(title)}</div><ul>{li}</ul></div>')


def note(text: str) -> None:
    H(f'<div class="note">{text}</div>')


def table(df: pd.DataFrame, spec: list[tuple]) -> None:
    """轻量 HTML 表格。spec: (列名, 表头, 类型)
    类型：text / muted / wrap / num0 / num1 / num2 / rate / delta / wan / bar（bar 的值是 0~1 的占比）"""
    if df is None or df.empty:
        H('<div class="note">暂无数据</div>')
        return
    head = "".join(f'<th class="{"" if k in ("text", "muted", "wrap") else "r"}">{esc(h)}</th>' for _, h, k in spec)
    rows = []
    for _, r in df.iterrows():
        tds = []
        for col, _, k in spec:
            v = r.get(col)
            if k == "text":
                tds.append(f"<td>{esc('—' if na(v) else v)}</td>")
            elif k == "muted":
                tds.append(f'<td class="m">{esc("—" if na(v) else v)}</td>')
            elif k == "wrap":
                tds.append(f'<td class="wrap">{esc("—" if na(v) else v)}</td>')
            elif k == "rate":
                tds.append(f'<td class="r">{fmt_rate(v)}</td>')
            elif k == "delta":
                tds.append(f'<td class="r {tone(v)}">{"—" if na(v) else f"{v * 100:+.1f}%"}</td>')
            elif k == "wan":
                tds.append(f'<td class="r">{fmt_wan(v)}</td>')
            elif k == "bar":
                w = 0 if na(v) else max(0.0, min(1.0, float(v))) * 100
                tds.append(f'<td class="r"><span class="bar"><b style="width:{w:.0f}%"></b></span>{fmt_rate(v)}</td>')
            else:
                nd = int(k[-1]) if k[-1].isdigit() else 0
                tds.append(f'<td class="r">{fmt(v, nd)}</td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    H(f'<div class="tblwrap"><table class="tbl"><thead><tr>{head}</tr></thead>'
      f'<tbody>{"".join(rows)}</tbody></table></div>')
