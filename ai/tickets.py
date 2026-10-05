"""客服工单自动分类：判断类别、紧急程度、情绪，并给出一句话摘要。

两种方法，评测时做对比：
  - 规则法（基线）：关键词匹配。简单、免费、可解释，但遇到没见过的说法就分错。
  - 大模型法：把类别定义写进提示词，让模型判断，并输出结构化 JSON。

用途：工单进来先自动分好类，分派给对应的客服小组；“高紧急 + 负面情绪”的优先处理。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from ai import llm  # noqa: E402

CATEGORIES = {
    "物流查询": "发货时间、快递进度、催件、改地址、指定快递、快递员服务、丢件",
    "退换货": "申请退货、换货（尺码、颜色、款式）、退货运费、退货地址、售后审核",
    "退款进度": "退款什么时候到账、退款金额不对、部分退款、取消订单后退款、退款后优惠券",
    "商品质量": "商品损坏、故障、褪色开胶、真假货、食品变质、保修",
    "发票": "开票、专票、发票抬头或税号错误、补开发票、发票下载",
    "优惠价保": "优惠券用不了或过期、降价补差价（价保）、满减规则、赠品",
    "账户支付": "支付失败、重复扣款、账户安全、诈骗电话、积分、会员等级",
    "其他咨询": "商品参数、活动时间、补货、门店、包装、客服时间等",
}

# 规则法：每个类别的关键词（顺序有意义：先匹配到的类别优先）
RULES = [
    ("退款进度", ["退款", "到账", "退回来", "少退", "钱还没"]),
    ("发票", ["发票", "专票", "税号", "抬头"]),
    ("优惠价保", ["优惠券", "券", "降价", "差价", "价保", "满减", "赠品"]),
    ("账户支付", ["支付", "扣款", "账号", "验证码", "积分", "会员", "登录"]),
    ("商品质量", ["坏", "裂", "褪色", "发烫", "正品", "怪味", "保修", "开胶", "没声音", "质量"]),
    ("退换货", ["退货", "换", "退掉", "退吗", "售后", "无理由"]),
    ("物流查询", ["快递", "物流", "发货", "催", "地址", "顺丰", "签收", "到"]),
]


def classify_rule(text: str) -> dict:
    for cat, kws in RULES:
        if any(k in text for k in kws):
            return {"category": cat}
    return {"category": "其他咨询"}


PROMPT = """你是电商客服工单分类助手。请分析下面这条顾客消息。

类别定义（只能选一个，选最主要的诉求）：
{cats}

输出 JSON：
{{"category": "类别名", "urgency": "高/中/低", "sentiment": "负面/中性/正面",
  "summary": "不超过 20 字的诉求摘要", "need_human": true/false}}

判断标准：
- urgency 高：涉及资金损失、账户安全、投诉、明确表示很急；低：一般咨询。
- need_human：投诉、情绪激烈、诈骗风险、需要核实订单的情况为 true。

顾客消息：{text}"""


def classify_llm(text: str) -> dict:
    cats = "\n".join(f"- {k}：{v}" for k, v in CATEGORIES.items())
    out = llm.chat_json([{"role": "user", "content": PROMPT.format(cats=cats, text=text)}], max_tokens=300)
    if out.get("category") not in CATEGORIES:   # 模型输出了不在列表里的类别，归到“其他咨询”
        out["category"] = "其他咨询"
    return out


def load_tickets() -> list[dict]:
    return json.loads((config.ROOT / "kb" / "tickets.json").read_text(encoding="utf-8"))
