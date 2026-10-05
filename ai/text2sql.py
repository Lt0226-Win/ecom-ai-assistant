"""AI 问数：自然语言 → SQL → 查询结果 → 文字结论。

流程（面试时可以按这 5 步讲）：
  1. 拼提示词：表结构说明（语义层） + 业务口径 + 写 SQL 的规则 + 用户问题
  2. 大模型生成 SQL（要求返回 JSON：sql + 思路）
  3. 安全检查：只允许单条 SELECT；数据库本身也是只读连接；限制返回行数和执行时间
  4. 执行 SQL；如果报错，把错误信息发回给模型让它自己修（最多重试 2 次）
  5. 把结果（前几十行）交给模型，生成一段中文结论
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

import pandas as pd

from ai import llm
from ai.schema import BUSINESS_RULES, schema_text

MAX_ROWS = 500          # 最多返回多少行
TIMEOUT_SECONDS = 30    # 单条 SQL 最长执行时间
MAX_RETRIES = 2         # SQL 报错后最多让模型修几次

SYSTEM_PROMPT = """你是一名资深电商数据分析师，负责把业务问题翻译成 DuckDB SQL。

## 数据库表结构
{schema}

## 业务口径
{rules}

## 写 SQL 的规则
1. 只能写一条 SELECT 查询（可以用 WITH），禁止任何修改数据的语句。
2. 使用 DuckDB 语法。日期常量写成 DATE '2017-12-01'。
3. 优先使用 ads_ / dws_ 开头的汇总表；只有汇总表答不了时才用 dwd_user_behavior（1 亿行）。
4. 比率保留 4 位小数，金额保留 2 位小数（用 round）。
5. 结果列名用中文别名（例如 AS "付费用户数"），方便业务看懂。
6. 返回明细时加 LIMIT（不超过 100）；排名类问题要 ORDER BY。
7. 如果问题和这份数据无关、或数据里没有对应信息（比如城市、性别、商品名称），sql 返回空字符串，并在 explanation 里说明原因。

## 输出格式
只返回 JSON：{{"sql": "...", "explanation": "一句话说明你的思路和使用的口径"}}
"""

FIX_PROMPT = """上面的 SQL 执行报错了：
{error}

请修正后重新返回 JSON：{{"sql": "...", "explanation": "..."}}"""

SUMMARY_PROMPT = """用户问题：{question}

执行的 SQL：
{sql}

查询结果（共 {n} 行，下面最多展示 30 行）：
{table}

请用 2-4 句中文回答用户的问题：先直接给结论和关键数字，再补充一句值得注意的地方。
数字写法：超过 1 万的数用“万”表示并保留 1 位小数（例如 4198.5 万元）；0-1 之间的比率换成百分比（例如 0.5507 写成 55.1%）。
如果涉及金额，提醒“金额基于模拟价格”。不要编造结果里没有的数字。"""

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|truncate|copy|attach|detach|install|load|pragma|set|reset|"
    r"export|import|call|checkpoint|vacuum|grant|revoke|use)\b"
    r"|read_csv|read_parquet|read_json|read_text|read_blob|glob\s*\(|parquet_scan|httpfs|getenv",
    re.I)


class UnsafeSQL(ValueError):
    pass


def check_sql(sql: str) -> str:
    """安全检查：只允许一条只读查询。返回清理后的 SQL，不安全就抛异常。"""
    s = re.sub(r"--[^\n]*", "", sql)                 # 去掉注释
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S).strip().rstrip(";").strip()
    if not s:
        raise UnsafeSQL("SQL 为空")
    if ";" in s:
        raise UnsafeSQL("只允许一条 SQL 语句")
    if not re.match(r"^(select|with)\b", s, re.I):
        raise UnsafeSQL("只允许 SELECT 查询")
    # 先去掉字符串常量再检查关键字，避免 WHERE segment = '一般挽留客户' 之类被误判
    body = re.sub(r"'(?:[^']|'')*'", "''", s)
    m = FORBIDDEN.search(body)
    if m:
        raise UnsafeSQL(f"包含不允许的操作：{m.group(0)}")
    return s


def run_sql(con, sql: str, timeout: int = TIMEOUT_SECONDS) -> pd.DataFrame:
    """执行查询，超时自动中断，最多返回 MAX_ROWS 行。"""
    cur = con.cursor()
    timer = threading.Timer(timeout, cur.interrupt)
    timer.start()
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        df = pd.DataFrame(cur.fetchmany(MAX_ROWS), columns=cols)   # 只取前 MAX_ROWS 行，不改写 SQL，保留原来的排序
    except Exception as e:  # noqa: BLE001
        if "interrupt" in str(e).lower():
            raise TimeoutError(f"查询超过 {timeout} 秒，已中断。可以把问题问得更具体一些。") from e
        raise
    finally:
        timer.cancel()
    return df


@dataclass
class Answer:
    question: str
    sql: str = ""
    explanation: str = ""
    data: pd.DataFrame | None = None
    summary: str = ""
    error: str = ""
    attempts: int = 0
    seconds: float = 0.0
    trace: list = field(default_factory=list)   # 每次尝试的 SQL 和报错，方便排查


def _df_to_text(df: pd.DataFrame, n: int = 30) -> str:
    return df.head(n).to_csv(index=False)


def generate_sql(con, question: str, history: list[dict] | None = None) -> tuple[list[dict], dict]:
    """第 1-2 步：拼提示词并让模型写 SQL。history 用来支持“接着上一个问题追问”。"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(schema=schema_text(con), rules=BUSINESS_RULES)}]
    messages += history or []
    messages.append({"role": "user", "content": question})
    return messages, llm.chat_json(messages)


def ask(con, question: str, history: list[dict] | None = None, summarize: bool = True) -> Answer:
    """完整流程：问题 → SQL → 结果 → 结论"""
    t0 = time.time()
    ans = Answer(question=question)
    try:
        messages, out = generate_sql(con, question, history)
        for attempt in range(MAX_RETRIES + 1):
            ans.attempts = attempt + 1
            ans.sql, ans.explanation = (out.get("sql") or "").strip(), out.get("explanation", "")
            if not ans.sql:                       # 模型判断数据回答不了
                ans.summary = ans.explanation or "这个问题无法用现有数据回答。"
                break
            try:
                sql = check_sql(ans.sql)
                ans.data = run_sql(con, sql)
                ans.trace.append({"sql": ans.sql, "error": ""})
                break
            except UnsafeSQL as e:                # 不安全的 SQL 不重试，直接拒绝
                ans.error = f"安全检查未通过：{e}"
                ans.trace.append({"sql": ans.sql, "error": ans.error})
                break
            except Exception as e:  # noqa: BLE001  —— SQL 写错了：把错误发回去让模型修
                ans.trace.append({"sql": ans.sql, "error": str(e)})
                if attempt == MAX_RETRIES:
                    ans.error = f"SQL 执行失败：{e}"
                    break
                messages += [{"role": "assistant", "content": f'{{"sql": {ans.sql!r}}}'},
                             {"role": "user", "content": FIX_PROMPT.format(error=str(e)[:800])}]
                out = llm.chat_json(messages)
        if summarize and ans.data is not None and not ans.error:
            ans.summary = llm.chat([{"role": "user", "content": SUMMARY_PROMPT.format(
                question=question, sql=ans.sql, n=len(ans.data), table=_df_to_text(ans.data))}],
                temperature=0.3, max_tokens=400)
    except llm.LLMNotConfigured as e:
        ans.error = str(e)
    except Exception as e:  # noqa: BLE001
        ans.error = f"调用大模型失败：{e}"
    ans.seconds = time.time() - t0
    return ans
