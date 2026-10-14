"""RuleLLM：确定性规则策略，输出结构与真实 LLM 完全一致，无 Key 可全量运行。"""
from __future__ import annotations

import re
from typing import Any

from app.seeds.banned_words import (
    BANNED_WORDS,
    CATEGORY_KEYWORDS,
    CONDITION_KEYWORDS,
    SUSPICIOUS_WORDS,
)


# ---------- 商品结构化 ----------
def structure_item(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    category = "其他"
    matched_kw: list[str] = []
    for cat, kws in CATEGORY_KEYWORDS.items():
        hit = [w for w in kws if w in text]
        if hit:
            category = cat
            matched_kw = hit
            break

    condition = "八成新"
    for cond, kws in CONDITION_KEYWORDS.items():
        if any(w in text for w in kws):
            condition = cond
            break

    # 标题：首行或前 24 字
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), text)
    title = first_line[:24]

    # 价格线索
    price_kw = re.search(r"(\d{2,4}(?:\.\d{1,2})?)\s*(?:元|块|￥|¥)", text)

    missing: list[str] = []
    if len(text) < 8:
        missing.append("商品描述过短，请补充品牌/型号/使用情况")
    # 类目未识别不阻断流程（以「其他」继续走审核，避免违禁品在结构化阶段逃逸）

    return {
        "title": title,
        "category": category,
        "condition_level": condition,
        "attrs": {"keywords": matched_kw[:5], "price_hint": float(price_kw.group(1)) if price_kw else None},
        "missing": missing,
        "engine": "rule",
    }


# ---------- 建议价 ----------
def suggest_price(category: str, reference_prices: list[float], declared: float | None = None) -> tuple[float, float]:
    base = declared
    if not base:
        same = [p for p in reference_prices if p > 0]
        base = round(sum(same) / len(same), 1) if same else 30.0
    low = round(base * 0.85, 1)
    high = round(base * 1.15, 1)
    return low, high


# ---------- 审核 ----------
def moderate(title: str, description: str) -> dict[str, Any]:
    reasons: list[dict] = get_reasons(title, description)
    banned_hits = [r for r in reasons if r["rule"] == "banned_word"]
    suspect_hits = [r for r in reasons if r["rule"] == "suspicious_word"]

    if banned_hits:
        return {
            "decision": "veto",
            "confidence": 0.98,
            "reasons": banned_hits + suspect_hits,
            "engine": "rule",
        }
    if suspect_hits:
        return {
            "decision": "manual",
            "confidence": 0.72,
            "reasons": suspect_hits,
            "engine": "rule",
        }
    if len(description.strip()) < 5:
        return {
            "decision": "reject",
            "confidence": 0.8,
            "reasons": [{"rule": "incomplete", "detail": "商品描述不足 5 个字，无法判断实物情况"}],
            "engine": "rule",
        }
    return {
        "decision": "approve",
        "confidence": 0.9,
        "reasons": [{"rule": "default", "detail": "未命中违禁/高风险词库，描述完整，允许上架"}],
        "engine": "rule",
    }


def get_reasons(title: str, description: str) -> list[dict]:
    text = f"{title} {description}"
    reasons: list[dict] = []
    for w in BANNED_WORDS:
        if w in text:
            reasons.append({"rule": "banned_word", "detail": f"命中校园禁售/危险物品词：『{w}』，触发安全否决"})
    for w in SUSPICIOUS_WORDS:
        if w in text:
            reasons.append({"rule": "suspicious_word", "detail": f"含高风险描述：『{w}』，需人工核实真伪与来源"})
    return reasons


# ---------- 推荐理由 ----------
def recommend_reason(item: dict, query: str, buyer_pref: dict | None = None) -> str:
    parts: list[str] = []
    if query and query in item.get("title", ""):
        parts.append("标题与搜索词高度相关")
    if item.get("condition_level") in ("全新", "九成新"):
        parts.append(f"成色为{item['condition_level']}")
    price = item.get("price")
    if price is not None:
        parts.append(f"标价 ¥{price:g}，性价比不错")
    credit = item.get("seller_credit")
    if credit is not None and credit >= 100:
        parts.append(f"卖家信用 {credit} 分，交易可靠")
    if not parts:
        parts.append("与你的需求较为匹配")
    return "；".join(parts)


# ---------- 议价依据文案 ----------
def offer_basis(role: str, price: float, round_no: int, nash: float | None = None,
                reason: str = "") -> str:
    if reason:
        return reason
    if nash is not None and round_no >= 2:
        return f"第 {round_no} 轮{('买方' if role == 'buyer' else '卖方')}让步出价，参考纳什价 ¥{nash:g}"
    return f"第 {round_no} 轮{('买方' if role == 'buyer' else '卖方')}出价"


# ---------------------------------------------------------------------------
# AI 议价虚拟用户兜底（FR-203/FR-204/FR-205）：无 Key 时确定性产出
# ---------------------------------------------------------------------------

def _stable_pick(options: list[str], incoming: str, salt: int = 0) -> str:
    """进程无关的稳定选择（同输入同输出，避免 hash() 随机盐）。"""
    idx = (sum(ord(ch) for ch in (incoming or "")) + salt) % len(options)
    return options[idx]


def chat_reply(role: str, item_title: str, neg_info: dict[str, Any], incoming: str,
               last_buyer_price: float | None, last_seller_price: float | None) -> str:
    """AI 议价口语短回复（大学生微信语气，1-2 句）。

    依据对方出价相对纳什价/己方保留价的偏离程度切换话术；纯函数确定性，
    同输入同输出（无 Key 全功能降级 NFR-5）。
    """
    info = neg_info or {}
    nash = info.get("nash_price")
    br = float(info.get("buyer_reserve") or 0)
    sr = float(info.get("seller_reserve") or 0)
    if nash is None:
        nash = (br + sr) / 2 if br and sr else 0
    nash = float(nash)
    round_count = int(info.get("round_count") or 1)
    planned = info.get("planned_price")
    salt = int(round((last_buyer_price or 0) * 10 + (last_seller_price or 0) * 3 + round_count))
    peer = last_buyer_price if role == "seller" else last_seller_price
    title = item_title or "这件"

    # 本轮将发起策略出价：话术须与出价一致（FR-204，先说价再出价）
    if planned is not None and (peer is None or abs(float(planned) - float(peer)) >= 0.05):
        p = float(planned)
        if role == "seller":
            pool = [
                f"行，我让一步，{p:g} 给你吧，这价真的很实在了～",
                f"那 {p:g} 吧，再低我宁可自留了，诚心要就直接拍～",
                f"这样，{p:g} 一口价，同学之间交个朋友～",
            ]
        else:
            pool = [
                f"那我出 {p:g}，这基本是我预算上限了～",
                f"{p:g} 行吗？可以的话我现在就付款～",
                f"我再加点，{p:g}，真的不能再多啦～",
            ]
        return _stable_pick(pool, incoming, salt)

    if role == "seller":
        if peer is None:
            pool = [
                f"哈喽，{title}还在的哈，东西保养得挺好，你可以先看看细节图～",
                "在的在的，诚心要的话价格好商量，你先出个价我看看～",
                "你好呀，这东西我平时用得很爱惜，你预算大概多少呀？",
            ]
            return _stable_pick(pool, incoming, salt)
        if peer >= sr > 0:
            pool = [
                f"行吧，{peer:g} 这个价可以接受，咱们交个朋友，我这就改价～",
                f"成交，{peer:g} 给你了，约个校内面交时间就行～",
                f"这价我基本不赚了，{peer:g} 行吧，你拍我马上确认。",
            ]
            return _stable_pick(pool, incoming, salt)
        ratio = peer / nash if nash else 1
        if ratio >= 0.97:
            pool = [
                f"就差一点点了，{peer:g} 真的接近我底线了，再补个零头呗？",
                f"这个价很有诚意了，我再让一口，按纳什价附近 {nash:g} 走吧～",
                f"{peer:g} 我稍微有点亏，要不咱们取个中间价？",
            ]
        elif ratio >= 0.85:
            pool = [
                f"{peer:g} 还是低了点，我这成色挂着很好出的，再加点呗～",
                f"再加点嘛，{peer:g} 我连原价一半都收不回来呀。",
                f"价格可以小刀，但 {peer:g} 这刀有点狠了，往 {nash:g} 附近靠靠？",
            ]
        else:
            pool = [
                f"啊这，{peer:g} 也太狠了吧，我买的时候贵好多呢，真出不了～",
                f"哈哈你这砍得我心痛，{peer:g} 不行不行，咱正经点还价？",
                "这个价真的收不到的，我自留都比这强，预算能再提提不？",
            ]
        return _stable_pick(pool, incoming, salt)

    # buyer
    if peer is None:
        pool = [
            f"你好，{title}我挺想要的，学生党预算有限，希望能便宜点～",
            "在吗？东西我看过了，成色合适的话我可以很快拍，价格好说不？",
            f"哈喽，{title}还在吗？我诚心要，你给个学生价呗～",
        ]
        return _stable_pick(pool, incoming, salt)
    if 0 < peer <= br:
        pool = [
            f"{peer:g} 在我预算内，行，那我按这个价拍啦～",
            f"好耶，{peer:g} 可以接受，什么时候方便面交？",
            f"成交，{peer:g} 我这边没问题，你确认一下我就付款～",
        ]
        return _stable_pick(pool, incoming, salt)
    ratio = peer / nash if nash else 1
    if ratio <= 1.03:
        pool = [
            f"{peer:g} 有点超预算了，能不能再便宜一点点？就一点点～",
            f"东西是喜欢的，但 {peer:g} 对我来说小贵，{nash:g} 左右行吗？",
            f"再让个奶茶钱呗，{peer:g} 我这周伙食就紧了～",
        ]
    elif ratio <= 1.15:
        pool = [
            f"{peer:g} 稍微有点贵呀，我看同款都更便宜些，能再降降不？",
            f"学长/学姐，{peer:g} 超出我预算了，{nash:g} 我立马拍～",
            f"便宜点嘛，我还是学生没什么收入，{peer:g} 真顶不住。",
        ]
    else:
        pool = [
            f"{peer:g} 也太贵了吧，这价我不如买新的了～",
            f"哈哈这报价把我劝退了，{peer:g} 完全超出学生预算呀。",
            f"能不能真诚一点，{peer:g} 挂太高啦，打个对折再聊？",
        ]
    return _stable_pick(pool, incoming, salt)


def next_ai_price(role: str, buyer_reserve: float, seller_reserve: float,
                  nash_price: float | None, last_buyer_price: float | None,
                  last_seller_price: float | None, round_count: int,
                  max_rounds: int) -> float | None:
    """AI 策略出价（FR-204）：朝纳什价严格单调收敛，绝不越过己方保留价。

    - buyer：出价严格递增，目标 min(纳什价, 买家保留价)；
    - seller：要价严格递减，目标 max(纳什价, 卖家保留价)；
    - 对方最新价已进入可成交区间时直接应价成交；
    - round_count=1 且己方尚未出价时返回 None（首轮只聊天，也可不出价）；
    - 返回 None 表示本轮不出价。任何返回价格都满足议价 Agent 的单调/保留价约束。
    """
    br = round(float(buyer_reserve), 1)
    sr = round(float(seller_reserve), 1)
    nash = round(float(nash_price), 1) if nash_price is not None else round((br + sr) / 2, 1)
    lb = round(float(last_buyer_price), 1) if last_buyer_price is not None else None
    ls = round(float(last_seller_price), 1) if last_seller_price is not None else None
    r = max(1, int(round_count))
    mr = max(1, int(max_rounds))

    if role == "buyer":
        target = min(nash, br) if br else nash
        # 卖家要价已进入授权区间且严格高于己方上次出价 → 应价即成交
        if ls is not None and sr <= ls <= br and (lb is None or ls > lb):
            return ls
        if lb is None:
            if r <= 1:
                return None  # 首轮只聊天
            # 第二次回应仍无出价记录：在纳什价下方礼貌开第一价
            opener = round(nash - max(1.0, (br - nash) * 0.2), 1) if br else round(nash * 0.9, 1)
            return opener if 0 < opener <= br else None
        if lb >= target:
            return None  # 再出价必违反单调递增或越过保留价
        frac = 1.0 if r >= mr else (0.75 if r >= 3 else 0.5)
        nxt = round(lb + (target - lb) * frac, 1)
        if r >= mr:
            nxt = target
        return nxt if nxt > lb and nxt <= br else None

    # seller
    target = max(nash, sr) if sr else nash
    # 买家出价已达保留价且严格低于己方上次要价 → 接受出价即成交
    if lb is not None and lb >= sr and (ls is None or lb < ls):
        return lb
    if ls is None:
        if r <= 1:
            return None  # 首轮只聊天
        opener = round(nash + max(1.0, (nash - sr) * 0.2), 1) if sr else round(nash * 1.1, 1)
        return opener if opener >= sr else None
    if ls <= target:
        return None
    frac = 1.0 if r >= mr else (0.75 if r >= 3 else 0.5)
    nxt = round(ls - (ls - target) * frac, 1)
    if r >= mr:
        nxt = target
    return nxt if nxt < ls and nxt >= sr else None
