"""在线演示的三道防护（2026-10 代码审查后加的），给 api/web.py 用。

1. 每个 IP 的次数限制：每分钟、每天各有上限。
   只在内存里临时计数（服务重启就清零），不写硬盘，也不写进日志。
   目的：防止一个人就把全站当天的 AI 次数（DEMO_DAILY_LIMIT）用完，后面来的 HR 用不了。

2. 周报缓存：数据集是固定的，同一份数据写出来的周报不需要每次都让大模型重写。
   缓存跟“数据指纹”（数据库文件的路径、大小、修改时间 + 统计截止日 + 模型名）绑定：
   换了数据、重建了数据库，指纹就变了，旧缓存自动作废，不用手动清。

3. 运行日志：每次 AI 请求记一行（时间、问题、生成的 SQL、成功与否、耗时），
   写到 data/logs/app.log，每天零点换一个新文件，保留 30 天。
   不记 IP、不记密钥。作用：线上出问题能查到卡在哪一步；被人试探攻击时（比如安全检查拦下的 SQL）也能看出来。
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import deque
from datetime import date, datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Callable

from fastapi import HTTPException, Request

import config

# ---------------------------------------------------------------- 1. 每个 IP 的次数限制
_ip_lock = threading.Lock()
_recent: dict[str, deque] = {}      # IP → 最近 60 秒内每次请求的时间
_today: dict[str, int] = {}         # IP → 今天已用次数
_today_date = ""


def check_ip_limit(request: Request, api: str) -> None:
    """超过上限就返回 429（网页会直接显示 detail 里的提示）。两个上限都是 0 时不限制（本地运行默认不限制）。"""
    per_min, per_day = config.DEMO_IP_PER_MINUTE, config.DEMO_IP_DAILY_LIMIT
    if per_min <= 0 and per_day <= 0:
        return
    # 线上经过 Caddy 转发，uvicorn 会从 X-Forwarded-For 取出访客的真实 IP
    ip = request.client.host if request.client else "unknown"
    now, today = time.time(), date.today().isoformat()
    global _today_date
    with _ip_lock:
        if _today_date != today:            # 过了零点，所有计数清零
            _recent.clear()
            _today.clear()
            _today_date = today
        q = _recent.setdefault(ip, deque())
        while q and now - q[0] >= 60:
            q.popleft()
        if per_min > 0 and len(q) >= per_min:
            log_event(api, limited="per_minute")
            raise HTTPException(429, "操作太频繁了，请过一分钟再试。")
        if per_day > 0 and _today.get(ip, 0) >= per_day:
            log_event(api, limited="per_day")
            raise HTTPException(429, f"你今天的 AI 体验次数已用完（每人每天 {per_day} 次），明天再来吧。")
        q.append(now)
        _today[ip] = _today.get(ip, 0) + 1


# ---------------------------------------------------------------- 2. 周报缓存
_report_lock = threading.Lock()
_report_cache: dict[str, dict] = {}


def data_fingerprint() -> str:
    st = config.DB_PATH.stat()
    return f"{config.DB_PATH}|{st.st_size}|{st.st_mtime_ns}|{config.DATA_END_DATE}|{config.DEEPSEEK_MODEL}"


def cached_llm_report(generate: Callable[[], dict], on_miss: Callable[[], None] = lambda: None) -> tuple[dict, bool]:
    """返回 (周报, 是否来自缓存)。

    没有缓存时先调用 on_miss()（用来检查次数限制），再调用 generate() 真正生成。
    只缓存大模型成功写出的周报；大模型调用失败、退回模板的不缓存，下次再试。
    加锁：两个人同时点“生成”，也只会调用一次大模型，后到的人直接拿缓存。"""
    key = data_fingerprint()
    with _report_lock:
        hit = _report_cache.get(key)
        if hit is not None:
            return hit, True
        on_miss()
        rep = generate()
        if rep.get("source") == "llm" and not rep.get("error"):
            rep = {**rep, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
            _report_cache.clear()           # 只保留当前数据对应的那一份
            _report_cache[key] = rep
        return rep, False


# ---------------------------------------------------------------- 3. 运行日志
_logger: logging.Logger | None = None
_CUT = {"question": 100, "text": 100, "sql": 1000, "error": 300}     # 各字段最多记多少字，其余字段最多 300 字
_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-*]{6,}")


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        lg = logging.getLogger("ecom.demo")
        lg.setLevel(logging.INFO)
        lg.propagate = False
        handler = TimedRotatingFileHandler(config.LOG_DIR / "app.log", when="midnight", backupCount=30, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        lg.handlers = [handler]
        _logger = lg
    return _logger


def _scrub(text: str) -> str:
    """去掉可能混进报错信息里的密钥"""
    if config.DEEPSEEK_API_KEY:
        text = text.replace(config.DEEPSEEK_API_KEY, "***")
    return _KEY_PATTERN.sub("sk-***", text)


def log_event(api: str, **fields) -> None:
    """写一行 JSON 日志。写日志失败不影响接口本身。"""
    try:
        rec: dict = {"api": api}
        for k, v in fields.items():
            if isinstance(v, str):
                v = _scrub(v)[:_CUT.get(k, 300)]
            elif isinstance(v, float):
                v = round(v, 2)
            rec[k] = v
        _get_logger().info(json.dumps(rec, ensure_ascii=False, default=str))
    except Exception:  # noqa: BLE001
        pass
