"""
录制首页交互演示用的数据：真实调用 AI 问数和智能客服，把输出保存下来，供作品网站“回放”。

运行（需要 .env 里的 DEEPSEEK_API_KEY，大约调用大模型 15 次，花费几分钱）：
    python tools/record_demo.py
输出：
    ../portfolio/assets/demo_data.js   （作品网站直接读取）

为什么不在网站上实时调用：首页要求打开就能用、永远不出错、不花钱；
所以首页播放“真实输出的录像”，想自己提问的人再进入在线看板。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from ai import llm, rag, text2sql  # noqa: E402
from pipeline.db import connect  # noqa: E402

ASK_QUESTIONS = [
    "哪一天的GMV最高？",
    "GMV排名前5的品类是哪些？",
    "复购率是多少？",
    "加购过但9天内从没购买的用户有多少？",
]
SERVICE_QUESTIONS = [
    "内裤拆开了能退吗",
    "退款退到银行卡要多久",
    "有个客服打电话要我的验证码，正常吗",
    "你们支持货到付款吗？",
]
OUT = ROOT.parent / "portfolio" / "assets" / "demo_data.js"


def _jsonable(v):
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    if isinstance(v, float):
        return round(v, 4)
    try:
        return int(v) if float(v).is_integer() else round(float(v), 4)
    except (TypeError, ValueError):
        return str(v)


def main() -> None:
    if not llm.available():
        print("没有配置 DEEPSEEK_API_KEY，无法录制。")
        sys.exit(1)
    con = connect(read_only=True)

    ask = []
    for q in ASK_QUESTIONS:
        a = text2sql.ask(con, q)
        if a.error or a.data is None:
            print(f"❌ {q}：{a.error}")
            continue
        ask.append({"q": q, "sql": a.sql, "explanation": a.explanation, "summary": a.summary,
                    "seconds": round(a.seconds, 1), "columns": [str(c) for c in a.data.columns],
                    "rows": [[_jsonable(v) for v in r] for r in a.data.head(10).itertuples(index=False)]})
        print(f"✅ {q}（{a.seconds:.1f} 秒）")

    service = []
    for q in SERVICE_QUESTIONS:
        r = rag.answer(q)
        if r["error"]:
            print(f"❌ {q}：{r['error']}")
            continue
        service.append({"q": q, "answer": r["answer"], "need_human": r["need_human"], "top_score": r["top_score"],
                        "hits": [{"source": h["source"], "text": h["text"], "score": h["score"]} for h in r["hits"]]})
        print(f"✅ {q}")

    k = con.execute("""SELECT strftime(dt, '%m-%d') AS d, weekday, gmv, order_cnt, active_users
                       FROM ads_daily_kpi ORDER BY dt""").fetchall()
    s = con.execute("""SELECT count(*), count(*) FILTER (WHERE buy_cnt > 0), count(*) FILTER (WHERE buy_days >= 2)
                       FROM dws_user_summary""").fetchone()
    board = {
        "daily": [{"d": d, "w": w, "gmv": round(g), "orders": o, "dau": u} for d, w, g, o, u in k],
        "gmv_total": round(sum(r[2] for r in k)), "orders_total": sum(r[3] for r in k),
        "buyers": s[1], "users": s[0], "repeat_rate": round(s[2] / s[1], 4),
        "dau_avg": round(sum(r[4] for r in k) / len(k)),
    }

    data = {"recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "model": config.DEEPSEEK_MODEL,
            "ask": ask, "service": service, "board": board}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("// 由 ecom-ai-assistant/tools/record_demo.py 自动生成：系统真实输出的录像\n"
                   "window.DEMO_DATA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    print(f"\n已保存：{OUT}")


if __name__ == "__main__":
    main()
