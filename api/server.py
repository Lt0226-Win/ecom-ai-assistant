"""对外接口（FastAPI）：把项目能力包装成 HTTP 接口，给 n8n、Dify 或其他系统调用。

启动：uvicorn api.server:app --port 8000      （默认只允许本机访问）
文档：浏览器打开 http://localhost:8000/docs （自动生成，可以直接在网页上试接口）

安全：在 .env 里设置 API_TOKEN 后，除 /health 外的接口都要在请求头带上 X-API-Token: <口令>，
否则返回 401。这样即使接口暴露在局域网里，别人也调不了、刷不了你的大模型额度。

为什么要有接口：看板是给人用的，接口是给“其他系统”用的。
例如 n8n 每周一 9 点调用 /report/weekly 拿到周报，再推送到飞书；
Dify 的工作流可以调用 /tickets/classify 给工单分类。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import config  # noqa: E402
from ai import llm, rag, text2sql, tickets, weekly_report  # noqa: E402
from pipeline.db import connect, new_cursor  # noqa: E402

app = FastAPI(title="电商 AI 运营助手 API", version="1.1")
_con = None


def con():
    """每个请求拿一个独立游标（FastAPI 用线程池处理请求，共享同一个连接会互相干扰）"""
    global _con
    if _con is None:
        if not config.DB_PATH.exists():
            raise HTTPException(503, "数据库不存在，请先运行 python pipeline/build_warehouse.py")
        _con = connect(read_only=True)
    return new_cursor(_con)


def check_token(x_api_token: str | None = Header(default=None)) -> None:
    """设置了 API_TOKEN 时，校验请求头里的口令"""
    if config.API_TOKEN and x_api_token != config.API_TOKEN:
        raise HTTPException(401, "缺少或错误的 X-API-Token")


protected = [Depends(check_token)]


class Question(BaseModel):
    question: str


class Ticket(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"ok": True, "db": config.DB_PATH.exists(), "llm": llm.available(), "feishu": bool(config.FEISHU_WEBHOOK)}


@app.get("/metrics/weekly", dependencies=protected)
def weekly_metrics(end: str = config.DATA_END_DATE):
    """周报用的原始指标（纯 SQL 计算，不调用大模型）"""
    return weekly_report.collect_facts(con(), end)


@app.post("/report/weekly", dependencies=protected)
def make_weekly_report(push: bool = False, use_llm: bool = True):
    """生成周报。push=true 时同时推送飞书；n8n 也可以拿返回的 markdown 自己推送"""
    rep = weekly_report.generate(con(), use_llm=use_llm)
    weekly_report.save(rep)
    if push:
        weekly_report.push_feishu(rep)
    return {k: rep[k] for k in ("title", "markdown", "source", "unverified_numbers")}


@app.post("/ask", dependencies=protected)
def ask_data(q: Question):
    """AI 问数"""
    a = text2sql.ask(con(), q.question)
    return {"question": a.question, "sql": a.sql, "summary": a.summary, "error": a.error,
            "rows": [] if a.data is None else a.data.head(100).astype(str).to_dict("records")}


@app.post("/service/answer", dependencies=protected)
def service_answer(q: Question):
    """智能客服问答（RAG）"""
    return rag.answer(q.question)


@app.post("/tickets/classify", dependencies=protected)
def classify_ticket(t: Ticket):
    """工单分类：有大模型用大模型，没有就用规则"""
    if llm.available():
        return {"method": "llm", **tickets.classify_llm(t.text)}
    return {"method": "rule", **tickets.classify_rule(t.text)}
