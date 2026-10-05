"""新版看板的后端：同时提供网页（web/dist 静态文件）和网页要调用的 /api 接口。

启动：uvicorn api.web:app --port 8600          然后浏览器打开 http://localhost:8600
线上演示：uvicorn api.web:app --port 8502，并设置环境变量 WEB_BASE_PATH=/demo（让网站挂在 /demo/ 下面）

和 api/server.py 的区别：
  - server.py 给 n8n、Dify 这类“系统”调用，默认只监听本机，并且要口令（X-API-Token）。
  - web.py 给“浏览器里的页面”调用，没有口令（口令放在网页里等于公开），
    所以防刷靠两条：DEMO_DAILY_LIMIT（每天大模型调用上限）+ SQL 只读检查。
    不要把没有设置 DEMO_DAILY_LIMIT 的 web.py 直接暴露到公网。
"""
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import APIRouter, FastAPI, HTTPException  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import config  # noqa: E402
from ai import llm, rag, text2sql, tickets, weekly_report  # noqa: E402
from pipeline.db import connect, new_cursor  # noqa: E402

DIST = config.ROOT / "web" / "dist"
EXAMPLES = ["哪一天的GMV最高？", "复购率是多少？", "GMV排名前5的品类是哪些？",
            "一天中哪个小时的平均购买次数最多？", "重要价值客户有多少人，贡献了多少比例的GMV？",
            "加购过但9天内从没购买的用户有多少？"]
SERVICE_EXAMPLES = ["退款退到银行卡要多久", "内裤拆开了能退吗", "刚买完就降价了，能退差价吗？", "物流三天没动了怎么办",
                    "有个客服打电话要我的验证码，正常吗", "你们支持货到付款吗？"]

_con = None


def _gold() -> dict:
    """评测集里的标准 SQL：没有配置大模型时，用它们展示页面效果"""
    cases = json.loads((config.ROOT / "eval" / "text2sql_cases.json").read_text(encoding="utf-8"))
    return {c["question"]: c["gold_sql"] for c in cases if c["gold_sql"]}


def con():
    """每个请求拿一个独立游标（FastAPI 用线程池处理请求，共享同一个连接会互相干扰）"""
    global _con
    if _con is None:
        if not config.DB_PATH.exists():
            raise HTTPException(503, "数据库不存在，请先运行 python pipeline/build_warehouse.py")
        _con = connect(read_only=True)
    return new_cursor(_con)


def _json_safe(v):
    if v is None:
        return None
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(v, (int, str, bool)):
        return v
    if hasattr(v, "isoformat"):
        return str(v)[:10] if len(str(v)) >= 10 and str(v)[4] == "-" else str(v)
    try:
        f = float(v)
        return int(f) if f.is_integer() and abs(f) < 1e15 and not isinstance(v, float) else f
    except (TypeError, ValueError):
        return str(v)


def _table(df, limit: int = 200) -> dict:
    d = df.head(limit)
    return {"columns": [str(c) for c in d.columns], "rows": [[_json_safe(v) for v in r] for r in d.itertuples(index=False)],
            "total_rows": int(len(df))}


class AskIn(BaseModel):
    question: str
    history: list[dict] = []        # 每项 {"q": 问题, "sql": SQL, "explanation": 思路}


class ServiceIn(BaseModel):
    question: str
    history: list[dict] = []        # 每项 {"question": ..., "answer": ...}


class TicketIn(BaseModel):
    text: str


class ReportIn(BaseModel):
    use_llm: bool = True


api = APIRouter(prefix="/api")


def _accuracy(name: str):
    p = config.REPORT_DIR / name
    if p.exists():
        m = re.search(r"执行准确率：\*{0,2}([\d.]+%)\*{0,2}（(\d+)/(\d+)）", p.read_text(encoding="utf-8"))
        if m:
            return {"accuracy": m.group(1), "correct": int(m.group(2)), "total": int(m.group(3))}
    return None


@api.get("/status")
def status():
    return {"llm": llm.available(), "model": config.DEEPSEEK_MODEL if llm.available() else "", "demo": config.DEMO_MODE,
            "daily_limit": config.DEMO_DAILY_LIMIT, "retriever": rag.get_retriever().mode,
            "ask_examples": EXAMPLES if llm.available() else list(_gold())[:12], "service_examples": SERVICE_EXAMPLES,
            "eval_dev": _accuracy("text2sql_eval.md"), "eval_holdout": _accuracy("text2sql_holdout.md")}


@api.post("/ask")
def ask(q: AskIn):
    question = q.question.strip()
    if not question:
        raise HTTPException(400, "问题不能为空")
    cur = con()
    if not llm.available():
        # 演示模式：没有配置大模型时，只支持评测题里的示例问题（用标准 SQL 展示页面效果）
        gold = _gold()
        if question not in gold:
            return {"question": question, "sql": "", "explanation": "", "summary": "", "attempts": 0, "seconds": 0,
                    "trace": [], "table": None,
                    "error": "当前没有配置大模型，演示模式只能回答评测集里的示例问题。"}
        ans = text2sql.Answer(question=question, sql=gold[question], explanation="演示模式：标准答案 SQL", attempts=1)
        ans.data = text2sql.run_sql(cur, gold[question])
        ans.trace = [{"sql": ans.sql, "error": ""}]
    else:
        history = []
        for h in q.history[-2:]:
            history += [{"role": "user", "content": str(h.get("q", ""))},
                        {"role": "assistant", "content": json.dumps({"sql": h.get("sql", ""),
                                                                     "explanation": h.get("explanation", "")},
                                                                    ensure_ascii=False)}]
        ans = text2sql.ask(cur, question, history=history)
    return {"question": ans.question, "sql": ans.sql, "explanation": ans.explanation, "summary": ans.summary,
            "error": ans.error, "attempts": ans.attempts, "seconds": round(ans.seconds, 1), "trace": ans.trace,
            "table": None if ans.data is None else _table(ans.data)}


@api.post("/report")
def report(r: ReportIn):
    # 只生成、不落盘：公开接口不往服务器写文件（定时周报的存档由 ai/weekly_report.py 负责）
    rep = weekly_report.generate(con(), use_llm=r.use_llm and llm.available())
    return {"title": rep["title"], "markdown": rep["markdown"], "source": rep["source"],
            "unverified_numbers": rep["unverified_numbers"], "error": rep["error"], "facts": rep["facts"]}


@api.post("/service/answer")
def service_answer(q: ServiceIn):
    hist = []
    for it in q.history[-2:]:
        hist += [{"role": "user", "content": str(it.get("question", ""))},
                 {"role": "assistant", "content": str(it.get("answer", ""))}]
    res = rag.answer(q.question.strip(), history=hist)
    res["no_answer_score"] = rag.NO_ANSWER_SCORE
    return res


@api.post("/tickets/classify")
def classify_ticket(t: TicketIn):
    text = t.text.strip()
    if not text:
        raise HTTPException(400, "工单内容不能为空")
    out = {"rule": tickets.classify_rule(text)["category"], "llm": None, "error": ""}
    if llm.available():
        try:
            out["llm"] = tickets.classify_llm(text)
        except Exception as e:  # noqa: BLE001
            out["error"] = f"调用大模型失败：{e}"
    return out


@api.get("/tickets/batch")
def tickets_batch():
    """60 条模拟工单用规则法批量分类（实时计算，不调用大模型）"""
    tk = tickets.load_tickets()
    preds = [tickets.classify_rule(t["text"])["category"] for t in tk]
    dist: dict[str, int] = {}
    for p in preds:
        dist[p] = dist.get(p, 0) + 1
    wrong = [{"text": t["text"], "label": t["label"], "pred": p} for t, p in zip(tk, preds) if t["label"] != p]
    return {"accuracy": sum(t["label"] == p for t, p in zip(tk, preds)) / len(tk), "total": len(tk),
            "dist": sorted([{"category": k, "count": v} for k, v in dist.items()], key=lambda x: -x["count"]),
            "wrong": wrong, "categories": [{"name": k, "desc": v} for k, v in tickets.CATEGORIES.items()],
            "llm": llm.available()}


def build_site() -> FastAPI:
    site = FastAPI(title="电商 AI 运营助手 · 看板")
    site.include_router(api)
    if DIST.exists():
        site.mount("/", StaticFiles(directory=DIST, html=True), name="web")
    else:
        @site.get("/")
        def _missing():
            return JSONResponse({"error": "还没有构建网页：请先在 web/ 目录运行 npm run build，或使用已构建好的 web/dist"},
                                status_code=503)
    return site


def build_app() -> FastAPI:
    base = os.getenv("WEB_BASE_PATH", "").rstrip("/")
    site = build_site()
    if not base:
        return site
    root = FastAPI()
    root.mount(base, site)       # 例如挂在 /demo 下面，保持线上演示地址 /demo/ 不变
    return root


app = build_app()
