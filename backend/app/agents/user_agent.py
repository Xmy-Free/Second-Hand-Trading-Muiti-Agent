"""② 用户代理 Agent：自然语言意图结构化、画像/保留价维护、授权区间内代客出价。

铁律（FR-2）：
- 意图不清返回 clarify 引导问题，禁止猜测后执行资金相关动作；
- auto_bid 仅在用户授权区间内出价；越界或成交前一律 need_confirm=true，不自动成交。
"""
from __future__ import annotations

import re
from typing import Any

from sqlmodel import Session, select

from app.agents.base import BaseAgent
from app.core.database import engine
from app.kernel.acl import AclEnvelope
from app.models import Negotiation, Offer

_PRICE_RE = re.compile(r"(\d{2,5}(?:\.\d{1,2})?)\s*(?:元|块|￥|¥)")

INTENT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("publish", ("发布", "上架", "我要卖", "出售", "出一个", "卖个")),
    ("appeal", ("申诉", "退款", "维权", "货不对板")),
    ("offer", ("出价", "砍价", "议价", "便宜点", "还价")),
    ("buy", ("下单", "买了", "要了", "付款", "支付")),
    ("search", ("推荐", "搜索", "找一", "有没有", "想买", "收一", "求")),
]

INTENT_LABEL = {
    "publish": "发布商品", "search": "搜索商品", "buy": "下单购买",
    "offer": "议价出价", "accept": "接受报价", "reject": "拒绝报价",
    "appeal": "发起申诉", "clarify": "意图待澄清",
}


class UserAgent(BaseAgent):
    name = "user_agent"
    display_name = "用户代理 Agent"
    avatar = "UserRound"
    accent = "#60A5FA"
    capabilities = ["意图结构化", "用户画像", "保留价维护", "授权区间代客出价", "成交前确认"]
    description = "用户数字分身：把自然语言解析为结构化意图，维护画像与保留价，在授权区间内代客出价，越界或成交前请求确认。"

    def __init__(self) -> None:
        super().__init__()
        # 用户画像/授权区间（进程内；重启后由后续交互重建，不涉及资金状态）
        self._profiles: dict[int, dict[str, Any]] = {}

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        self.ensure_running()
        action = msg.payload.get("action")
        handlers = {
            "parse_intent": self.do_parse_intent,
            "auto_bid": self.do_auto_bid,
            "update_profile": self.do_update_profile,
        }
        fn = handlers.get(action)
        if not fn:
            return msg.reply("refuse", {"error": f"unknown action {action}"}, error_code="BAD_ACTION")
        data = fn(msg.payload)
        return msg.reply("inform", data, confidence=data.get("confidence", 0.85),
                         summary=data.get("summary", INTENT_LABEL.get(data.get("intent"), action)))

    # ---------------- 意图结构化 ----------------
    def do_parse_intent(self, p: dict[str, Any]) -> dict[str, Any]:
        text = (p.get("text") or "").strip()
        user_id = p.get("user_id")
        profile = self._profiles.get(user_id, {}) if user_id else {}

        intent = "clarify"
        for cand, kws in INTENT_RULES:
            if any(k in text for k in kws):
                intent = cand
                break

        prices = [float(m) for m in _PRICE_RE.findall(text)]
        buyer_reserve = prices[0] if prices else profile.get("buyer_reserve")
        first_offer = round(buyer_reserve * 0.8, 1) if buyer_reserve else None

        clarify_questions: list[str] = []
        if not text:
            clarify_questions.append("请告诉我你想做什么，例如：找一本 20 元以内的高数教材")
        elif intent == "clarify":
            clarify_questions.append("你是想搜索商品、发起议价，还是发布/申诉？可以再描述具体一些")
        if intent in ("buy", "offer", "search") and not prices and buyer_reserve is None:
            clarify_questions.append("预算是多少？例如「20 元以内」")
        if intent == "publish" and not any(k in text for k in ("出", "卖", "发布")):
            clarify_questions.append("请补充要出售商品的描述、成色与价格")

        if user_id and buyer_reserve is not None:
            profile = {**profile, "buyer_reserve": buyer_reserve,
                       "last_intent": intent}
            self._profiles[user_id] = profile

        ok = intent != "clarify" and not clarify_questions
        return {
            "ok": ok, "intent": intent,
            "intent_label": INTENT_LABEL.get(intent, "意图待澄清"),
            "buyer_reserve": buyer_reserve,
            "first_offer": first_offer,
            "clarify_questions": clarify_questions,
            "profile": profile,
            "confidence": 0.9 if ok else 0.55,
            "summary": f"意图识别：{INTENT_LABEL.get(intent, '待澄清')}"
                       + ("（需澄清）" if clarify_questions else ""),
        }

    # ---------------- 授权区间代客出价 ----------------
    def do_auto_bid(self, p: dict[str, Any]) -> dict[str, Any]:
        neg_id = p["negotiation_id"]
        authorized_max = float(p["authorized_max"])
        with Session(engine) as session:
            neg = session.get(Negotiation, neg_id)
            if neg is None:
                return {"ok": False, "error": "议价会话不存在", "confidence": 1.0}
            offers = session.exec(select(Offer).where(
                Offer.negotiation_id == neg_id).order_by(Offer.id)).all()
            buyer_bids = [o.price for o in offers if o.from_role == "buyer"]
            seller_asks = sorted(o.price for o in offers if o.from_role == "seller")

        last_bid = buyer_bids[-1] if buyer_bids else round(authorized_max * 0.8, 1)
        # 朝授权上限单调让步（半步收敛）
        next_bid = round(min(last_bid + (authorized_max - last_bid) * 0.5, authorized_max), 1)

        need_confirm = False
        reasons: list[str] = []
        if next_bid > authorized_max:
            need_confirm = True
            reasons.append(f"建议出价 ¥{next_bid:g} 超出授权区间上限 ¥{authorized_max:g}")
        if seller_asks and next_bid >= seller_asks[0]:
            # 出价即成交 → 成交前必须用户确认
            need_confirm = True
            next_bid = seller_asks[0]
            reasons.append(f"接受卖家要价 ¥{seller_asks[0]:g} 将立即成交，成交前需你确认")
        if not reasons:
            reasons.append(f"在授权区间内代客出价 ¥{next_bid:g}（纳什参考 ¥{neg.nash_price:g}）")

        return {
            "ok": True, "bid": next_bid,
            "need_confirm": need_confirm,
            "auto_sent": not need_confirm and bool(p.get("execute")),
            "reasons": reasons,
            "nash_price": neg.nash_price,
            "summary": "需要用户确认后再出价" if need_confirm else f"可自动出价 ¥{next_bid:g}",
            "confidence": 0.88,
        }

    # ---------------- 画像维护 ----------------
    def do_update_profile(self, p: dict[str, Any]) -> dict[str, Any]:
        user_id = p["user_id"]
        prof = dict(self._profiles.get(user_id, {}))
        for k in ("buyer_reserve", "preferences", "risk_appetite"):
            if k in p:
                prof[k] = p[k]
        self._profiles[user_id] = prof
        return {"ok": True, "user_id": user_id, "profile": prof,
                "summary": "用户画像已更新", "confidence": 1.0}
