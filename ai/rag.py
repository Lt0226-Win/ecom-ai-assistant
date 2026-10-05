"""智能客服：RAG（检索增强生成）。

流程：
  1. 切分：把 kb/docs/ 里的规则文档按“## 小节”切成片段（chunk），每段带上“文档名 / 小节名”
  2. 检索：用户提问 → 找出最相关的 3 段
       - 默认 BM25 关键词检索（中文按“相邻两个字”切词，不需要额外的分词库）
       - 如果配置了向量模型（EMBEDDING_API_KEY），同时做向量检索，两路结果用 RRF 融合（混合检索）
  3. 生成：把这 3 段资料和问题一起交给大模型，要求“只根据资料回答、标注来源”，资料里没有就建议转人工

为什么要 RAG：大模型不知道“我们店”的规则，直接问会编；把规则文档检索出来塞进提示词，回答就有依据。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from ai import llm  # noqa: E402

KB_DIR = config.ROOT / "kb" / "docs"
EMB_CACHE = config.ROOT / "data" / "kb_embeddings.npz"
NO_ANSWER_SCORE = 4.0     # BM25 最高分低于这个值，认为知识库里没有相关内容（根据评测集调出来的）

# 同义词表：顾客的口语说法 → 规则文档里的正式说法。
# 关键词检索只认字面，顾客说“内裤拆了能退吗”，文档里写的是“贴身衣物”，不扩展就搜不到。
# （真实项目里这张表来自历史工单的高频说法；接入向量检索后可以减少对它的依赖。）
SYNONYMS = {
    "内裤": "贴身衣物 内衣", "袜子": "贴身衣物", "不喜欢": "无理由退货", "不想要": "无理由退货",
    "退钱": "退款", "到账": "退款到账", "多久": "时间", "专票": "增值税专用发票", "报销": "发票",
    "降价": "价保 降价 差价", "差价": "价保", "补差": "价保", "验证码": "验证码 账户安全", "被盗": "账户安全 异常登录",
    "坏了": "质量问题 保修", "杂音": "质量问题", "没声音": "质量问题", "褪色": "质量问题",
    "过期": "保质期 临期", "没动": "物流信息 没有更新 催件", "催": "催件", "晚上": "16:00 后", "下单": "付款",
    "两张": "每笔订单 1 张", "叠加": "每笔订单 1 张", "金卡": "金卡 会员等级", "银卡": "银卡 会员等级",
    "包邮": "包邮 运费", "运费": "运费", "改地址": "修改地址", "顺丰": "顺丰配送",
}


def expand_query(q: str) -> str:
    """查询扩展：在原问题后面追加同义词"""
    return q + " " + " ".join(v for k, v in SYNONYMS.items() if k in q)


@dataclass
class Chunk:
    id: int
    doc: str
    section: str
    text: str

    @property
    def source(self) -> str:
        return f"{self.doc} / {self.section}"


def load_chunks(kb_dir: Path = KB_DIR) -> list[Chunk]:
    """按 ## 小节切分文档"""
    chunks: list[Chunk] = []
    for path in sorted(kb_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^#\s+(.+)$", text, re.M)
        doc = m.group(1).strip() if m else path.stem
        for part in re.split(r"^##\s+", text, flags=re.M)[1:]:
            title, _, body = part.partition("\n")
            chunks.append(Chunk(len(chunks), doc, title.strip(), body.strip()))
    return chunks


def tokenize(text: str) -> list[str]:
    """中文切词的简单做法：连续汉字按“相邻两个字”切（bigram），英文和数字按整词。
    例：“七天无理由退货” → 七天 天无 无理 理由 由退 退货"""
    tokens = []
    for seg in re.findall(r"[一-鿿]+|[a-zA-Z]+|\d+", text.lower()):
        if re.match(r"[一-鿿]", seg):
            tokens += [seg[i:i + 2] for i in range(len(seg) - 1)] or [seg]
        else:
            tokens.append(seg)
    return tokens


# ---------------------------------------------------------------- 向量检索（可选）
def _embed(texts: list[str]) -> np.ndarray:
    from openai import OpenAI
    cli = OpenAI(api_key=config.EMBEDDING_API_KEY, base_url=config.EMBEDDING_BASE_URL, timeout=60)
    out = []
    for i in range(0, len(texts), 32):
        resp = cli.embeddings.create(model=config.EMBEDDING_MODEL, input=texts[i:i + 32])
        out += [d.embedding for d in resp.data]
    v = np.array(out, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)   # 归一化后，点积 = 余弦相似度


def _chunk_vectors(chunks: list[Chunk]) -> np.ndarray:
    """知识库向量只算一次，存到 data/kb_embeddings.npz；文档改了会自动重算"""
    texts = [f"{c.source}\n{c.text}" for c in chunks]
    key = hashlib.md5((config.EMBEDDING_MODEL + "".join(texts)).encode()).hexdigest()
    if EMB_CACHE.exists():
        z = np.load(EMB_CACHE)
        if str(z["key"]) == key:
            return z["vecs"]
    vecs = _embed(texts)
    EMB_CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(EMB_CACHE, key=key, vecs=vecs)
    return vecs


# ---------------------------------------------------------------- 检索
class Retriever:
    def __init__(self, chunks: list[Chunk] | None = None):
        self.chunks = chunks or load_chunks()
        # 文档名、小节名也参与检索（权重高一些：重复一次）
        corpus = [tokenize(f"{c.doc} {c.section} {c.section} {c.text}") for c in self.chunks]
        self.bm25 = BM25Okapi(corpus)
        self.vecs = None
        if config.EMBEDDING_API_KEY:
            try:
                self.vecs = _chunk_vectors(self.chunks)
            except Exception as e:  # noqa: BLE001  向量服务不可用时退回纯 BM25
                print(f"向量检索不可用，改用 BM25：{e}")

    @property
    def mode(self) -> str:
        return "混合检索（BM25 + 向量）" if self.vecs is not None else "BM25 关键词检索"

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        """返回 [(片段, 分数)]。分数是 BM25 分数（混合检索时排序用 RRF，但分数仍给 BM25 分，便于判断“有没有相关内容”）"""
        bm = self.bm25.get_scores(tokenize(expand_query(query)))
        order_bm = list(np.argsort(-bm))
        if self.vecs is None:
            ranked = order_bm
        else:
            qv = _embed([query])[0]
            order_vec = list(np.argsort(-(self.vecs @ qv)))
            # RRF 融合：每路结果按名次打分 1/(60+名次)，两路相加。好处是不用管两种分数的量纲是否一致
            rrf = {i: 1 / (60 + order_bm.index(i)) + 1 / (60 + order_vec.index(i)) for i in range(len(self.chunks))}
            ranked = sorted(rrf, key=rrf.get, reverse=True)
        return [(self.chunks[i], float(bm[i])) for i in ranked[:k]]


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()


# ---------------------------------------------------------------- 生成
PROMPT = """你是“示例好物旗舰店”的客服助手。请只根据下面的【参考资料】回答顾客问题。

【参考资料】
{context}

【回答要求】
1. 只用参考资料里的信息，不要编造政策、时间、金额。资料里没有的内容，回答“这个问题我需要帮您转人工客服确认”。
2. 语气亲切简洁，先直接回答，再补充必要的条件或操作步骤，控制在 120 字以内。
3. 在用到的信息后面标注来源编号，例如 [1]。
4. 遇到以下情况，need_human 设为 true：顾客要投诉、情绪激动、涉及账户安全或诈骗、资料无法回答。

只返回 JSON：{{"answer": "...", "need_human": true/false}}"""


def answer(question: str, history: list[dict] | None = None, k: int = 3) -> dict:
    r = get_retriever()
    hits = r.search(question, k)
    if r.vecs is None:                # 纯关键词检索时，0 分的片段和问题没有任何共同词，去掉
        hits = [h for h in hits if h[1] > 0] or hits[:1]
    top_score = hits[0][1] if hits else 0.0
    result = {"question": question, "hits": [{"source": c.source, "text": c.text, "score": round(s, 2)} for c, s in hits],
              "top_score": round(top_score, 2), "mode": r.mode, "answer": "", "need_human": False, "error": ""}
    if top_score < NO_ANSWER_SCORE:   # 知识库里没有相关内容：不调用模型，直接转人工，避免模型硬编
        result.update(answer="这个问题我暂时没有找到相关规定，帮您转接人工客服确认，请稍等。", need_human=True,
                      hits=[])
        return result
    if not llm.available():           # 没配置大模型：只返回检索结果
        return result
    context = "\n\n".join(f"[{i + 1}] {c.source}\n{c.text}" for i, (c, _) in enumerate(hits))
    messages = [{"role": "system", "content": PROMPT.format(context=context)}]
    messages += (history or [])[-4:]
    messages.append({"role": "user", "content": question})
    try:
        out = llm.chat_json(messages, temperature=0.2, max_tokens=500)
        result.update(answer=out.get("answer", ""), need_human=bool(out.get("need_human")))
    except llm.LLMNotConfigured as e:
        result["error"] = str(e)
    except Exception as e:  # noqa: BLE001
        result["error"] = f"调用大模型失败：{e}"
    return result


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "退款多久到账"
    print(json.dumps(answer(q), ensure_ascii=False, indent=2))
