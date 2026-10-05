"""自动周报：SQL 算数 → 大模型写分析 → 数字核对 → 推送飞书。

运行：
    python ai/weekly_report.py            # 生成周报，保存到 reports/weekly/
    python ai/weekly_report.py --push     # 生成并推送到飞书群

设计要点（面试可讲）：
  1. 数字全部由 SQL 计算，大模型只负责“写字”，不负责“算数”——大模型算数不可靠。
  2. 生成后自动核对：把文中出现的数字和 SQL 算出的数字比对，对不上的标出来（防止模型编数字）。
  3. 没有 API Key 或调用失败时，退回到模板生成，保证周报每周都能发出去。
"""
from __future__ import annotations

import argparse
import json
import math
import numbers
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from ai import llm  # noqa: E402

REPORT_DIR = config.REPORT_DIR / "weekly"


def _r(x, nd=2):
    return None if x is None else round(float(x), nd)


def _clean(x):
    """把 NaN 换成 None、numpy 数字换成 Python 数字，保证能转成 JSON"""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_clean(v) for v in x]
    if isinstance(x, numbers.Number) and not isinstance(x, bool):
        x = float(x) if not isinstance(x, int) else x
        return None if isinstance(x, float) and math.isnan(x) else x
    return x


def collect_facts(con, end: str = config.DATA_END_DATE) -> dict:
    """用 SQL 计算周报需要的所有数字。end = 周报截止日期（含），统计最近 7 天。"""
    end_d = date.fromisoformat(end)
    start_d = end_d - timedelta(days=6)
    s, e = start_d.isoformat(), end_d.isoformat()
    # 用来对比的“上周末”：本周最后两天 vs 7 天前的同两天
    w_now = [(end_d - timedelta(days=1)).isoformat(), e]
    w_prev = [(end_d - timedelta(days=8)).isoformat(), (end_d - timedelta(days=7)).isoformat()]

    def one(sql, params=()):
        return con.execute(sql, list(params)).fetchone()

    tot = one("""SELECT sum(gmv), sum(order_cnt), sum(pv_cnt), avg(active_users)
                 FROM ads_daily_kpi WHERE dt BETWEEN ? AND ?""", (s, e))
    uniq = one("""SELECT count(DISTINCT user_id), count(DISTINCT user_id) FILTER (WHERE buy_cnt > 0)
                  FROM dws_user_daily WHERE dt BETWEEN ? AND ?""", (s, e))
    daily = con.execute("""SELECT strftime(dt, '%m-%d') AS dt, weekday, active_users, order_cnt, round(gmv) AS gmv,
                                  pay_user_rate, pv_order_rate
                           FROM ads_daily_kpi WHERE dt BETWEEN ? AND ? ORDER BY dt""", [s, e]).df()

    def wk(days):
        r = one(f"""SELECT sum(active_users), sum(order_cnt), sum(gmv), sum(order_cnt) / sum(pv_cnt)
                    FROM ads_daily_kpi WHERE dt IN ({",".join("?" * len(days))})""", days)
        return {"active_users": int(r[0] or 0), "orders": int(r[1] or 0), "gmv": _r(r[2]), "pv_order_rate": _r(r[3], 4)}

    now, prev = wk(w_now), wk(w_prev)
    comp = None
    if prev["orders"]:
        comp = {k: _r(now[k] / prev[k] - 1, 4) for k in ("active_users", "orders", "gmv")}
        comp["pv_order_rate_pp"] = _r((now["pv_order_rate"] - prev["pv_order_rate"]) * 100, 2)  # 百分点

    # 品类变化：最近两天 vs 上周同两天，只看有一定规模的品类
    movers = con.execute(f"""
        WITH a AS (SELECT category_id, sum(gmv) g FROM dws_category_daily WHERE dt IN (?, ?) GROUP BY 1),
             b AS (SELECT category_id, sum(gmv) g FROM dws_category_daily WHERE dt IN (?, ?) GROUP BY 1)
        SELECT a.category_id, round(b.g) AS gmv_prev, round(a.g) AS gmv_now, round(a.g / b.g - 1, 4) AS change
        FROM a JOIN b USING (category_id)
        WHERE b.g >= 50000
        ORDER BY change DESC""", w_now + w_prev).df()
    best = daily.loc[daily["gmv"].idxmax()]
    worst = daily.loc[daily["gmv"].idxmin()]
    funnel = con.execute("SELECT step_name, users, conv_from_prev FROM ads_funnel ORDER BY step_no").df()
    rfm = con.execute("SELECT segment, users, user_share, gmv_share FROM ads_rfm_segment ORDER BY gmv DESC LIMIT 3").df()
    hour = one("SELECT hour, avg_pv FROM ads_hourly_behavior ORDER BY avg_pv DESC LIMIT 1")

    return _clean({
        "period": {"start": s, "end": e},
        "summary": {"gmv": _r(tot[0]), "orders": int(tot[1]), "pv": int(tot[2]), "avg_daily_active": int(tot[3]),
                    "active_users": int(uniq[0]), "buyers": int(uniq[1]),
                    "pay_user_rate": _r(uniq[1] / uniq[0], 4), "pv_order_rate": _r(tot[1] / tot[2], 4)},
        "best_day": {"dt": best["dt"], "weekday": best["weekday"], "gmv": float(best["gmv"])},
        "worst_day": {"dt": worst["dt"], "weekday": worst["weekday"], "gmv": float(worst["gmv"])},
        "weekend_compare": {"this": w_now, "prev": w_prev, "now": now, "before": prev, "change": comp},
        "daily": daily.to_dict("records"),
        "category_up": movers.head(5).to_dict("records"),
        "category_down": movers.tail(5).iloc[::-1].to_dict("records"),
        "funnel": funnel.to_dict("records"),
        "rfm_top": rfm.to_dict("records"),
        "peak_hour": {"hour": int(hour[0]), "avg_pv": int(hour[1])},
        "notes": ["金额基于模拟价格", "数据集只有 9 天，周对比使用“本周末 vs 上周末”同两天"],
    })


PROMPT = """你是电商公司的数据分析师，请根据下面的数据（JSON）写一份给运营团队看的周报。

数据：
{facts}

要求：
1. 用 Markdown，包含 4 个小节：## 一、核心结论（3 条，每条一句话，带关键数字）、## 二、指标表现、## 三、值得关注、## 四、下周建议（3 条，要具体可执行）。
2. 所有数字必须直接来自上面的数据，不要自己计算新数字（数据里没有的就不写）。比率用百分比表示，保留 1 位小数；金额用“万元”，保留 1 位小数。
3. “值得关注”要结合品类涨跌、漏斗、用户分层来写，指出原因的可能性时用“可能”，不要下绝对结论。
4. 在结尾注明：金额基于模拟价格。
5. 语言简洁专业，总长度 400-600 字。不要写标题以外的寒暄。"""


def _pct(x, nd=1):
    return "—" if x is None else f"{x * 100:+.{nd}f}%" if abs(x) < 10 else f"{x * 100:.{nd}f}%"


def template_report(f: dict) -> str:
    """不依赖大模型的模板周报（兜底方案）"""
    s, c = f["summary"], f["weekend_compare"]["change"] or {}
    up = "、".join(f"{r['category_id']}（{r['change'] * 100:+.0f}%）" for r in f["category_up"][:3])
    down = "、".join(f"{r['category_id']}（{r['change'] * 100:+.0f}%）" for r in f["category_down"][:3])
    top = f["rfm_top"][0]
    return f"""## 一、核心结论
- 本周 GMV {s['gmv'] / 1e4:,.1f} 万元，订单 {s['orders'] / 1e4:.1f} 万笔，付费用户 {s['buyers'] / 1e4:.1f} 万人。
- 本周末与上周末相比：活跃用户 {_pct(c.get('active_users'))}，订单 {_pct(c.get('orders'))}，GMV {_pct(c.get('gmv'))}。
- 浏览转化率 {s['pv_order_rate'] * 100:.1f}%，本周末比上周末变化 {c.get('pv_order_rate_pp', 0):+.2f} 个百分点。

## 二、指标表现
- 日均活跃用户 {s['avg_daily_active'] / 1e4:.1f} 万；本周活跃用户中付费率 {s['pay_user_rate'] * 100:.1f}%。
- GMV 最高的一天是 {f['best_day']['dt']}（{f['best_day']['weekday']}），{f['best_day']['gmv'] / 1e4:.1f} 万元；最低是 {f['worst_day']['dt']}，{f['worst_day']['gmv'] / 1e4:.1f} 万元。
- 浏览高峰在 {f['peak_hour']['hour']} 点。

## 三、值得关注
- 增长最快的品类：{up}。
- 下滑最多的品类：{down}。
- {top['segment']}占付费用户 {top['user_share'] * 100:.1f}%，贡献 {top['gmv_share'] * 100:.1f}% 的 GMV。

## 四、下周建议
- 对下滑品类排查价格、库存和详情页，确认下滑原因。
- 对加购未购买的用户做购物车提醒，提升转化。
- 针对{top['segment']}做专属权益，防止核心用户流失。

> 金额基于模拟价格。本周报由模板自动生成。"""


def _allowed_numbers(f: dict) -> dict[int, set[float]]:
    """把数据里所有数字按常见写法展开（原值、百分比、万），按小数位数分别保存：
    {0: 取整后的集合, 1: 保留 1 位小数的集合, 2: 保留 2 位小数的集合}，用来核对文中的数字。"""
    nums: dict[int, set[float]] = {0: set(), 1: set(), 2: set()}

    def add(v: float):
        for nd in (0, 1, 2):
            nums[nd].add(round(v, nd))

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, numbers.Number) and not isinstance(x, bool):
            x = float(x)
            if math.isnan(x):
                return
            for v in (x, x * 100, x / 1e4):
                add(abs(v))
        elif isinstance(x, str):
            for m in re.findall(r"\d+(?:\.\d+)?", x):
                add(float(m))
    walk(f)
    return nums


def verify_numbers(text: str, f: dict) -> list[str]:
    """找出文中“数据里查不到”的数字（可能是模型编的或自己算的）。

    按文中数字自己的精度核对：写 87.3 就必须能在数据里找到四舍五入到 1 位小数等于 87.3 的值，
    不能因为数据里有个 87 就放过（旧版就是这样，随机编造的小数有一半能混过去）。"""
    allowed = _allowed_numbers(f)
    suspicious = []
    for m in re.finditer(r"(?<![\w.])(\d+(?:,\d{3})*(?:\.(\d+))?)", text):
        v = float(m.group(1).replace(",", ""))
        nd = min(len(m.group(2) or ""), 2)
        if nd == 0 and v < 10:           # 1、2、3 这类序号/小整数不检查
            continue
        if round(v, nd) not in allowed[nd]:
            suspicious.append(m.group(1))
    return sorted(set(suspicious), key=suspicious.index)


def generate(con, end: str = config.DATA_END_DATE, use_llm: bool = True) -> dict:
    facts = collect_facts(con, end)
    source, body, err = "template", "", ""
    if use_llm and llm.available():
        try:
            body = llm.chat([{"role": "user", "content": PROMPT.format(
                facts=json.dumps(facts, ensure_ascii=False, default=str))}], temperature=0.3, max_tokens=1500)
            source = "llm"
        except Exception as e:  # noqa: BLE001
            err = str(e)
    if not body:
        body = template_report(facts)
    p = facts["period"]
    title = f"电商经营周报（{p['start'][5:]} 至 {p['end'][5:]}）"
    return {"title": title, "markdown": f"# {title}\n\n{body.strip()}\n", "facts": facts, "source": source,
            "unverified_numbers": verify_numbers(body, facts) if source == "llm" else [], "error": err}


def save(report: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"weekly_{report['facts']['period']['end']}.md"
    path.write_text(report["markdown"], encoding="utf-8")
    return path


def _to_feishu_md(md: str) -> str:
    """飞书卡片的 markdown 不支持 # 标题，转成加粗"""
    md = re.sub(r"^#{1,6}\s*(.+)$", r"**\1**", md, flags=re.M)
    return md.replace("> ", "")


def push_feishu(report: dict, webhook: str | None = None) -> dict:
    """推送到飞书群机器人（消息卡片）。群机器人安全设置里建议加关键词“周报”。"""
    url = webhook or config.FEISHU_WEBHOOK
    if not url:
        raise RuntimeError("没有配置 FEISHU_WEBHOOK，请在 .env 里填写飞书群机器人的 Webhook 地址。")
    body = report["markdown"].split("\n", 1)[1]   # 去掉第一行大标题，标题放到卡片头里
    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": report["title"]}, "template": "grey"},
            "elements": [
                {"tag": "markdown", "content": _to_feishu_md(body)},
                {"tag": "note", "elements": [{"tag": "plain_text",
                                              "content": f"自动生成于 {datetime.now():%Y-%m-%d %H:%M} · 电商 AI 运营助手"}]},
            ],
        },
    }
    r = requests.post(url, json=card, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("code", 0) != 0:
        raise RuntimeError(f"飞书返回错误：{data}")
    return data


def main() -> None:
    from pipeline.db import connect
    ap = argparse.ArgumentParser(description="生成电商经营周报")
    ap.add_argument("--end", default=config.DATA_END_DATE, help="周报截止日期，默认数据最后一天")
    ap.add_argument("--push", action="store_true", help="生成后推送到飞书")
    ap.add_argument("--no-llm", action="store_true", help="不调用大模型，用模板生成")
    args = ap.parse_args()

    con = connect(read_only=True)
    rep = generate(con, args.end, use_llm=not args.no_llm)
    path = save(rep)
    print(rep["markdown"])
    print(f"\n已保存：{path}（生成方式：{'大模型' if rep['source'] == 'llm' else '模板'}）")
    if rep["error"]:
        print(f"大模型调用失败，已改用模板：{rep['error']}")
    if rep["unverified_numbers"]:
        print(f"⚠️ 以下数字在数据中找不到，请人工核对：{', '.join(rep['unverified_numbers'])}")
    if args.push:
        push_feishu(rep)
        print("已推送到飞书。")


if __name__ == "__main__":
    main()
