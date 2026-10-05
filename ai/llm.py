"""大模型调用：DeepSeek（接口和 OpenAI 兼容，所以直接用 openai 这个库）。"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402


class LLMNotConfigured(RuntimeError):
    pass


class LLMQuotaExceeded(RuntimeError):
    pass


def _check_quota() -> None:
    """在线演示版：每天最多调用 DEMO_DAILY_LIMIT 次大模型，超过就拒绝（防止被人刷 API 费用）"""
    limit = config.DEMO_DAILY_LIMIT
    if limit <= 0:
        return
    today = date.today().isoformat()
    path = config.USAGE_FILE
    try:
        usage = json.loads(path.read_text()) if path.exists() else {}
    except ValueError:
        usage = {}
    used = usage.get(today, 0)
    if used >= limit:
        raise LLMQuotaExceeded(f"今天的 AI 在线体验次数已用完（每天 {limit} 次），明天再来，或者看项目页的演示视频。")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({today: used + 1}))


def available() -> bool:
    return bool(config.DEEPSEEK_API_KEY)


def _client():
    if not available():
        raise LLMNotConfigured("没有配置 DEEPSEEK_API_KEY，请在项目根目录的 .env 文件里填写。")
    from openai import OpenAI
    return OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL, timeout=60)


def chat(messages: list[dict], temperature: float = 0.0, json_mode: bool = False, max_tokens: int = 1500) -> str:
    """发送对话，返回模型的文字回复。
    temperature=0：让输出尽量稳定（写 SQL、做分类需要稳定，不需要“创意”）。"""
    kw = {"response_format": {"type": "json_object"}} if json_mode else {}
    _check_quota()
    resp = _client().chat.completions.create(
        model=config.DEEPSEEK_MODEL, messages=messages, temperature=temperature, max_tokens=max_tokens, **kw)
    return resp.choices[0].message.content or ""


def chat_json(messages: list[dict], **kw) -> dict:
    """要求模型返回 JSON，并解析成字典。模型偶尔会在 JSON 外面包一层 ```，这里做兼容。"""
    text = chat(messages, json_mode=True, **kw)
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)
