"""新版看板的后端：同时提供网页（web/dist 静态文件）和网页要调用的 /api 接口。

启动：uvicorn api.web:app --port 8600          然后浏览器打开 http://localhost:8600
线上演示：uvicorn api.web:app --port 8502，并设置环境变量 WEB_BASE_PATH=/demo（让网站挂在 /demo/ 下面）

和 api/server.py 的区别：
  - server.py 给 n8n、Dify 这类“系统”调用，默认只监听本机，并且要口令（X-API-Token）。
  - web.py 给“浏览器里的页面”调用，没有口令（口令放在网页里等于公开），所以靠下面几条防护：
      · DEMO_DAILY_LIMIT：全站每天大模型调用上限
      · 每个 IP 每分钟 / 每天的次数上限，周报同一份数据只生成一次（见 api/demo_guard.py）
      · 问题和对话记录的长度上限；网页传回来的历史 SQL 也要重新过一遍安全检查（防止伪造对话记录）
      · SQL 安全检查 + 只读连接禁止读文件（见 ai/text2sql.py、pipeline/db.py）
    不要把没有设置 DEMO_MODE=1 和 DEMO_DAILY_LIMIT 的 web.py 直接暴露到公网。
"""
import json
import math
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import APIRouter, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import config  # noqa: E402
from ai import llm, rag, text2sql, tickets, weekly_report  # noqa: E402
from api.demo_guard import cached_llm_report, check_ip_limit, log_event  # noqa: E402
from pipeline.db import connect, new_cursor  # noqa: E402

MAX_QUESTION_CHARS = 300        # 问题最长多少字
MAX_TICKET_CHARS = 500          # 工单最长多少字
MAX_HISTORY_CHARS = 500         # 对话记录里每段文字最多保留多少字（超出部分截掉）
MAX_BODY_BYTES = 32 * 1024      # 一次请求最大 32KB（正常提问加两轮对话记录只有几 KB）

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


def _check_text(text: str, limit: int, what: str) -> str:
    text = text.strip()
    if not text:
        raise HTTPException(400, f"{what}不能为空")
    if len(text) > limit:
        raise HTTPException(400, f"{what}太长了，请控制在 {limit} 字以内")
    return text


def _cut(v) -> str:
    return str(v or "")[:MAX_HISTORY_CHARS]


def _ask_history(items: list[dict]) -> list[dict]:
    """网页传回来的问数对话记录：只用最近 2 轮，每段截断；SQL 必须重新通过安全检查，否则丢掉。
    对话记录是浏览器发来的，别人可以伪造一段“AI 之前写过的 SQL”来诱导模型照着写，所以不能直接相信。"""
    out = []
    for h in items[-2:]:
        sql = str(h.get("sql") or "")[:2000]
        try:
            sql = text2sql.check_sql(sql) if sql.strip() else ""
        except text2sql.UnsafeSQL:
            sql = ""
        out += [{"role": "user", "content": _cut(h.get("q"))},
                {"role": "assistant", "content": json.dumps({"sql": sql, "explanation": _cut(h.get("explanation"))},
                                                            ensure_ascii=False)}]
    return out


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
def ask(q: AskIn, request: Request):
    question = _check_text(q.question, MAX_QUESTION_CHARS, "问题")
    t0 = time.time()
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
        check_ip_limit(request, "ask")
        ans = text2sql.ask(cur, question, history=_ask_history(q.history))
    log_event("ask", question=question, sql=ans.sql, ok=not ans.error, error=ans.error,
              blocked=ans.error.startswith("安全检查未通过"), attempts=ans.attempts, seconds=time.time() - t0)
    return {"question": ans.question, "sql": ans.sql, "explanation": ans.explanation, "summary": ans.summary,
            "error": ans.error, "attempts": ans.attempts, "seconds": round(ans.seconds, 1), "trace": ans.trace,
            "table": None if ans.data is None else _table(ans.data)}


@api.post("/report")
def report(r: ReportIn, request: Request):
    # 只生成、不落盘：公开接口不往服务器写文件（定时周报的存档由 ai/weekly_report.py 负责）
    t0, cur = time.time(), con()
    if r.use_llm and llm.available():
        # 同一份数据只让大模型写一次，之后直接返回缓存；只有真正要调用大模型时才计入 IP 次数
        rep, cached = cached_llm_report(lambda: weekly_report.generate(cur, use_llm=True),
                                        on_miss=lambda: check_ip_limit(request, "report"))
    else:
        rep, cached = weekly_report.generate(cur, use_llm=False), False
    log_event("report", source=rep["source"], cached=cached, unverified=len(rep["unverified_numbers"]),
              ok=not rep["error"], error=rep["error"], seconds=time.time() - t0)
    return {"title": rep["title"], "markdown": rep["markdown"], "source": rep["source"],
            "unverified_numbers": rep["unverified_numbers"], "error": rep["error"], "facts": rep["facts"],
            "cached": cached, "generated_at": rep.get("generated_at", "")}


@api.post("/service/answer")
def service_answer(q: ServiceIn, request: Request):
    question = _check_text(q.question, MAX_QUESTION_CHARS, "问题")
    t0 = time.time()
    if llm.available():
        check_ip_limit(request, "service")
    hist = []
    for it in q.history[-2:]:
        hist += [{"role": "user", "content": _cut(it.get("question"))},
                 {"role": "assistant", "content": _cut(it.get("answer"))}]
    res = rag.answer(question, history=hist)
    res["no_answer_score"] = rag.NO_ANSWER_SCORE
    log_event("service", question=question, need_human=res["need_human"], top_score=res["top_score"],
              ok=not res["error"], error=res["error"], seconds=time.time() - t0)
    return res


@api.post("/tickets/classify")
def classify_ticket(t: TicketIn, request: Request):
    text = _check_text(t.text, MAX_TICKET_CHARS, "工单内容")
    t0 = time.time()
    out = {"rule": tickets.classify_rule(text)["category"], "llm": None, "error": ""}
    if llm.available():
        check_ip_limit(request, "ticket")
        try:
            out["llm"] = tickets.classify_llm(text)
        except Exception as e:  # noqa: BLE001
            out["error"] = f"调用大模型失败：{e}"
    log_event("ticket", text=text, rule=out["rule"], llm=(out["llm"] or {}).get("category", ""),
              ok=not out["error"], error=out["error"], seconds=time.time() - t0)
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

    @site.middleware("http")
    async def limit_body_size(request: Request, call_next):
        """超大的请求直接拒绝，不让它进到后面的解析和大模型调用"""
        try:
            size = int(request.headers.get("content-length") or 0)
        except ValueError:
            size = 0
        if size > MAX_BODY_BYTES:
            return JSONResponse({"detail": "请求内容太大"}, status_code=413)
        return await call_next(request)

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
