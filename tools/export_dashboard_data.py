"""把看板需要的数据从数仓导出成 JSON，给新版前端（web/，shadcn 模板）使用。

运行：python tools/export_dashboard_data.py
输出：web/public/data/{overview,conversion,users,category}.json（每加一页，在这里加一个导出函数）

“关键发现”的文字由这里用 SQL 结果自动计算。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.db import connect  # noqa: E402

OUT = ROOT / "web" / "public" / "data"


def wan(v, nd=1):
    return f"{v / 1e4:,.{nd}f}"


def rate(v, nd=1):
    return f"{v * 100:.{nd}f}%"


def records(df):
    df = df.copy()
    for c in df.columns:
        if str(df[c].dtype).startswith("datetime"):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
    return json.loads(df.to_json(orient="records", force_ascii=False))


def overview(con):
    k = con.execute("SELECT * FROM ads_daily_kpi ORDER BY dt").df()
    u = con.execute("""SELECT count(*) AS users, count(*) FILTER (WHERE buy_cnt > 0) AS buyers,
                              count(*) FILTER (WHERE buy_days >= 2) AS repeat_buyers FROM dws_user_summary""").df().iloc[0]
    hourly = con.execute("SELECT * FROM ads_hourly_behavior ORDER BY hour").df()
    rfm = con.execute("SELECT * FROM ads_rfm_segment").df()

    last, wk = k.iloc[-1], k.iloc[-8]
    wow = lambda c: float(last[c] / wk[c] - 1)  # noqa: E731
    sat = k[k["weekday"] == "周六"]
    sat1, sat2 = sat.iloc[0], sat.iloc[-1]
    peak = hourly.loc[hourly["avg_pv"].idxmax()]
    best = hourly.loc[hourly["pv_order_rate"].idxmax()]
    top = rfm.iloc[0]
    findings = [
        {"title": "次数口径和用户口径差很多",
         "text": f"每 100 次浏览只有 {k['order_cnt'].sum() / k['pv_cnt'].sum() * 100:.1f} 次购买，"
                 f"但 9 天内有 {rate(u['buyers'] / u['users'], 0)} 的用户买过东西。"},
        {"title": "12 月第一个周末流量明显放大",
         "text": f"周六日活 {wan(sat2['active_users'])} 万，比上周六高 {rate(sat2['active_users'] / sat1['active_users'] - 1, 0)}，"
                 f"但转化率没有同步提升（{rate(sat2['pv_order_rate'], 2)} vs {rate(sat1['pv_order_rate'], 2)}）。"},
        {"title": "晚上是流量高峰",
         "text": f"{int(peak['hour'])} 点平均浏览量最高；转化率最高的是 {int(best['hour'])} 点"
                 f"（{rate(best['pv_order_rate'], 2)}），夜间高峰反而转化偏低。"},
        {"title": "头部用户贡献大部分成交",
         "text": f"{top['segment']}占付费用户 {rate(top['user_share'], 0)}，贡献 {rate(top['gmv_share'], 0)} 的 GMV。"},
    ]
    return {
        "period": {"start": str(k["dt"].iloc[0])[:10], "end": str(k["dt"].iloc[-1])[:10]},
        "wow_label": f"{str(last['dt'])[5:10]} vs 上周{last['weekday'][-1]}",
        "totals": {"gmv": float(k["gmv"].sum()), "orders": int(k["order_cnt"].sum()),
                   "avg_active": float(k["active_users"].mean()), "users": int(u["users"]), "buyers": int(u["buyers"]),
                   "repeat_buyers": int(u["repeat_buyers"])},
        "wow": {c: wow(c) for c in ("gmv", "order_cnt", "active_users")},
        "daily": records(k),
        "hourly": records(hourly),
        "findings": findings,
    }


def conversion(con):
    f = con.execute("SELECT * FROM ads_funnel ORDER BY step_no").df()
    path = con.execute("SELECT * FROM ads_buy_path").df()
    ret = con.execute("SELECT * FROM ads_retention ORDER BY dt").df()
    cnt = con.execute("SELECT sum(pv_cnt) pv, sum(cart_cnt) + sum(fav_cnt) cf, sum(order_cnt) buy FROM ads_daily_kpi").df().iloc[0]
    return {"funnel": records(f), "path": records(path), "retention": records(ret),
            "counts": {"pv": float(cnt["pv"]), "cart_fav": float(cnt["cf"]), "buy": float(cnt["buy"])}}


def users(con):
    seg = con.execute("SELECT * FROM ads_rfm_segment").df()
    rep = con.execute("SELECT * FROM ads_repurchase").df()
    th = con.execute("""SELECT median(recency_days) r_med, median(monetary) m_med, count(*) n,
                               avg(monetary) m_avg, count(*) FILTER (WHERE frequency >= 2) / count(*) rep
                        FROM ads_user_rfm""").df().iloc[0]
    return {"segments": records(seg), "repurchase": records(rep),
            "threshold": {k: float(th[k]) for k in ("r_med", "m_med", "n", "m_avg", "rep")}}


def category(con):
    rank = con.execute("SELECT * FROM ads_category_rank ORDER BY gmv_rank").df()
    tot = float(rank["gmv"].sum())
    n_80 = int((rank["gmv"].cumsum() / tot < 0.8).sum()) + 1
    by_pv = rank.sort_values("pv_cnt", ascending=False).head(500)
    top50 = rank.head(50)
    ids = ",".join(str(int(c)) for c in top50["category_id"])
    daily = con.execute(f"""SELECT c.category_id, c.dt, k.weekday, c.pv_cnt, c.buy_cnt, c.gmv
                            FROM dws_category_daily c JOIN ads_daily_kpi k USING (dt)
                            WHERE c.category_id IN ({ids}) ORDER BY c.category_id, c.dt""").df()
    return {"stats": {"n_cat": int(len(rank)), "n_buy": int((rank["buy_cnt"] > 0).sum()),
                      "top10_share": float(rank.head(10)["gmv"].sum() / tot), "n_80": n_80,
                      "conv": float(rank["buy_cnt"].sum() / rank["pv_cnt"].sum()), "gmv_total": tot},
            "top10": records(rank.head(10)),
            "by_pv": records(by_pv[["category_id", "pv_cnt", "buy_cnt", "gmv", "pv_order_rate", "gmv_rank", "pv_rank"]]),
            "top50": records(top50[["category_id", "gmv_rank"]]),
            "daily": records(daily)}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect(read_only=True)
    for name, fn in [("overview", overview), ("conversion", conversion), ("users", users), ("category", category)]:
        (OUT / f"{name}.json").write_text(json.dumps(fn(con), ensure_ascii=False), encoding="utf-8")
        print("已导出", OUT / f"{name}.json")
