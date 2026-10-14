"""⑨ 纠纷仲裁 Agent：证据链聚合、规则直裁、结构化裁决书、超阈值/涉安全升级人工。

裁决书结构（FR-9）：{responsibility(buyer/seller/none), basis[], action(refund/uphold/manual), confidence}
同时保留 suggestion/direct 字段以兼容申诉流条件边。
另承担 C3 卖家不服驳回的二级「规则库复核」。
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.database import engine
from app.kernel.acl import AclEnvelope
from app.kernel.observe import audit, record_conflict
from app.llm import rule_llm
from app.models import Appeal, Item, Offer, Order, Review, User

REFUND_KEYWORDS = ("未交付", "没发货", "未发货", "没收到", "未收到", "货不对板", "假货", "虚假", "欺骗")
UPHOLD_KEYWORDS = ("恶意退款", "已签收", "已收到货", "买家反悔", "不想要了")


class ArbitratorAgent(BaseAgent):
    name = "arbitrator"
    display_name = "纠纷仲裁 Agent"
    avatar = "Gavel"
    accent = "#FB923C"
    capabilities = ["证据链汇总", "规则库裁决", "结构化裁决书", "驳回复核", "升级人工"]
    description = "线上小法官：汇总商品档案/议价/订单节点/评价/信用证据包，输出结构化裁决书，超阈值升级人工并联动信用。"

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        self.ensure_running()
        action = msg.payload.get("action")
        if action == "build_evidence":
            data = self.do_build_evidence(msg.payload)
            return msg.reply("inform", data, summary="纠纷证据包已汇总")
        if action == "rule_appeal":
            data = self.do_rule_appeal(msg.payload)
            return msg.reply("arbitrate", data, confidence=data.get("confidence", 0.8),
                             summary=f"规则裁决建议：{data['suggestion']}（责任方：{data['responsibility']}）")
        if action == "review_rejection":
            data = self.do_review_rejection(msg.payload)
            return msg.reply("arbitrate", data, confidence=data.get("confidence", 0.8),
                             summary=f"二级规则复核：{data['decision']}")
        return msg.reply("refuse", {"error": f"unknown action {action}"}, error_code="BAD_ACTION")

    # ---------------- 证据包（档案/议价/订单节点/评价/信用） ----------------
    def do_build_evidence(self, p: dict[str, Any]) -> dict[str, Any]:
        appeal_id = p["appeal_id"]
        with Session(engine) as session:
            appeal = session.get(Appeal, appeal_id)
            if appeal is None:
                return {"ok": False, "error": "申诉不存在"}
            order = session.get(Order, appeal.order_id)
            item = session.get(Item, order.item_id) if order else None
            buyer = session.get(User, order.buyer_id) if order else None
            seller = session.get(User, order.seller_id) if order else None
            offers = []
            reviews = []
            if order and order.negotiation_id:
                offers = session.exec(select(Offer).where(
                    Offer.negotiation_id == order.negotiation_id
                ).order_by(Offer.id)).all()
            if order:
                reviews = session.exec(select(Review).where(
                    Review.order_id == order.id
                ).order_by(Review.id)).all()
            return {
                "ok": True,
                "appeal": {"id": appeal.id, "reason": appeal.reason,
                           "appellant_id": appeal.appellant_id, "created_at": appeal.created_at.isoformat()},
                "order": {"id": order.id, "order_no": order.order_no, "status": order.status,
                          "deal_price": order.deal_price,
                          "created_at": order.created_at.isoformat()} if order else None,
                "item": {"id": item.id, "title": item.title, "audit_reason": item.audit_reason,
                         "condition_level": item.condition_level,
                         "description": item.description} if item else None,
                "buyer": {"id": buyer.id, "nickname": buyer.nickname,
                          "credit": buyer.credit_score, "risk_tag": buyer.risk_tag} if buyer else None,
                "seller": {"id": seller.id, "nickname": seller.nickname,
                           "credit": seller.credit_score, "risk_tag": seller.risk_tag} if seller else None,
                "offers": [{"round": o.round, "from_role": o.from_role, "price": o.price,
                            "basis": o.basis} for o in offers],
                "reviews": [{"from_user_id": r.from_user_id, "to_user_id": r.to_user_id,
                             "score": r.score, "content": r.content} for r in reviews],
            }

    # ---------------- 规则裁决 + 结构化裁决书 ----------------
    def do_rule_appeal(self, p: dict[str, Any]) -> dict[str, Any]:
        appeal_id = p["appeal_id"]
        with Session(engine) as session:
            appeal = session.get(Appeal, appeal_id)
            order = session.get(Order, appeal.order_id) if appeal else None
            text = appeal.reason if appeal else ""
            amount = order.deal_price if order else 0.0
            appellant_id = appeal.appellant_id if appeal else None
            buyer_id = order.buyer_id if order else None

        hit_refund = [w for w in REFUND_KEYWORDS if w in text]
        hit_uphold = [w for w in UPHOLD_KEYWORDS if w in text]

        if amount <= settings.direct_ruling_max_amount:
            if hit_refund and not hit_uphold:
                data = {
                    "suggestion": "refund", "direct": True, "confidence": 0.82,
                    "action": "refund",
                    "responsibility": "seller" if appellant_id and appellant_id == buyer_id else "buyer",
                    "basis": [f"金额 ¥{amount:g} ≤ 直裁阈值 ¥{settings.direct_ruling_max_amount:g}",
                              f"申诉理由命中：{'、'.join(hit_refund)}",
                              "证据包含议价与订单节点，规则裁决退款并联动信用扣罚"],
                }
            elif hit_uphold and not hit_refund:
                data = {
                    "suggestion": "uphold", "direct": True, "confidence": 0.8,
                    "action": "uphold",
                    "responsibility": "buyer" if appellant_id and appellant_id != buyer_id else "none",
                    "basis": [f"金额 ¥{amount:g} ≤ 直裁阈值",
                              f"申诉理由命中：{'、'.join(hit_uphold)}", "规则裁决维持交易"],
                }
            else:
                data = self._manual_ruling(amount, "规则无法覆盖该申诉类型", responsibility="none")
        else:
            data = self._manual_ruling(
                amount, f"金额 ¥{amount:g} 超过直裁阈值 ¥{settings.direct_ruling_max_amount:g}",
                responsibility="none")

        record_conflict(
            scene="C4", ctype="goal",
            level=2 if data["direct"] else 3,
            participants=["arbitrator", "credit", "order"],
            payload={"appeal_id": appeal_id, "amount": amount,
                     "action": data["action"], "responsibility": data["responsibility"],
                     "confidence": data["confidence"], "basis": data["basis"],
                     "human_required": not data["direct"]},
            result=("二级规则直裁：" + data["action"]) if data["direct"] else "规则无法直裁，升级三级人工终裁",
            graph_thread_id=p.get("thread_id"),
        )
        return data

    def _manual_ruling(self, amount: float, reason: str, *, responsibility: str) -> dict[str, Any]:
        return {"suggestion": "manual", "direct": False, "confidence": 0.6,
                "action": "manual", "responsibility": responsibility,
                "basis": [reason, "升级三级人工：由管理员查看证据包终裁"]}

    # ---------------- C3 二级规则库复核（卖家不服驳回） ----------------
    def do_review_rejection(self, p: dict[str, Any]) -> dict[str, Any]:
        item_id = p["item_id"]
        with Session(engine) as session:
            item = session.get(Item, item_id)
            if item is None:
                return {"ok": False, "error": "商品不存在", "confidence": 1.0}
            rule_result = rule_llm.moderate(item.title, item.description)
            decision = rule_result["decision"]
            escalated = decision in ("manual", "veto")
            if escalated and decision == "manual":
                # 标记进入三级人工门（publish 流 human_review_gate 识别）
                item.status = "manual"
                attrs = dict(item.attrs or {})
                attrs["c3_escalated"] = True
                item.attrs = attrs
            audit("agent", "arbitrator", "c3_rule_review", "item", item_id,
                  {"decision": decision, "escalated": escalated,
                   "reasons": rule_result["reasons"]}, p.get("thread_id"), session=session)
            record_conflict(
                scene="C3", ctype="opinion", level=2,
                participants=["arbitrator", "moderation", "seller"],
                payload={"item_id": item_id, "stage": "rule_review",
                         "decision": decision, "escalated": escalated,
                         "reasons": rule_result["reasons"]},
                result=(f"二级规则复核：维持 {decision}，升级三级人工门"
                        if escalated else f"二级规则复核：{decision}（卖家申诉成立）"),
                graph_thread_id=p.get("thread_id"), session=session,
            )
            session.commit()
        return {"ok": True, "decision": "escalate" if escalated else decision,
                "escalated": escalated, "reasons": rule_result["reasons"],
                "confidence": rule_result["confidence"],
                "summary": "规则库复核完成", "stage": "rule_review"}
