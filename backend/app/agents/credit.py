"""⑧ 信用评价 Agent：带置信度风险意见、双向评价聚合、信用分动态更新、裁决信用扣罚。

向审核/议价/订单/仲裁输出 risk_opinion；一单仅可评价一次；处罚由仲裁/安全事件联动。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.database import engine
from app.kernel.acl import AclEnvelope
from app.kernel.observe import audit
from app.models import Order, Review, User


class CreditAgent(BaseAgent):
    name = "credit"
    display_name = "信用评价 Agent"
    avatar = "BadgeCheck"
    accent = "#F472B6"
    capabilities = ["风险意见", "置信度评估", "双向评价聚合", "信用分动态更新", "裁决信用扣罚"]
    description = "信用局：输出带置信度的风险意见，聚合一单一次的双向评价并动态更新信用分，执行裁决联动的信用扣罚。"

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        self.ensure_running()
        action = msg.payload.get("action")
        handlers = {
            "risk_check": self.do_risk_check,
            "risk_opinion": self.do_risk_opinion_action,
            "review": self.do_review,
            "penalize": self.do_penalize,
        }
        fn = handlers.get(action)
        if not fn:
            return msg.reply("refuse", {"error": f"unknown action {action}"}, error_code="BAD_ACTION")
        data = fn(msg.payload)
        return msg.reply("inform", data, confidence=data.get("confidence", 0.9),
                         summary=data.get("summary", action))

    # ---------------- 风险意见 ----------------
    def do_risk_check(self, p: dict[str, Any]) -> dict[str, Any]:
        with Session(engine) as session:
            order = session.get(Order, p["order_id"])
            if order is None:
                return {"ok": False, "error": "订单不存在", "confidence": 1.0}
            opinion = self.risk_opinion(session, order.buyer_id)
            audit("agent", "credit", "risk_opinion", "order", order.id,
                  opinion, p.get("thread_id"), session=session)
            session.commit()
            return {"ok": True, "order_id": order.id, **opinion, "confidence": opinion["confidence"]}

    def do_risk_opinion_action(self, p: dict[str, Any]) -> dict[str, Any]:
        with Session(engine) as session:
            opinion = self.risk_opinion(session, int(p["user_id"]))
        return {"ok": True, **opinion, "confidence": opinion["confidence"]}

    def risk_opinion(self, session: Session, user_id: int) -> dict[str, Any]:
        user = session.get(User, user_id)
        factors: list[str] = []
        if user is None:
            return {"risk_level": "high", "confidence": 0.99, "basis": ["用户不存在"],
                    "factors": [], "credit_score": 0, "risk_tag": "unknown"}
        if user.risk_tag == "high_risk" or user.credit_score < settings.high_risk_threshold:
            confidence = 0.9
            factors.append("credit_below_threshold")
            factors.append("risk_tag_high")
            factors.append(f"信用分 {user.credit_score} 低于安全阈值 {settings.high_risk_threshold}")
            level = "high"
        elif user.risk_tag == "new":
            confidence = 0.6
            factors.append("new_account")
            factors.append("新账号，尚无成交记录")
            level = "medium"
        else:
            confidence = 0.8
            factors.append(f"信用分 {user.credit_score}，历史记录良好")
            level = "low"
        return {"risk_level": level, "confidence": confidence,
                "basis": factors, "factors": factors,
                "credit_score": user.credit_score, "risk_tag": user.risk_tag}

    # ---------------- 评价（一单一次） ----------------
    def do_review(self, p: dict[str, Any]) -> dict[str, Any]:
        with Session(engine) as session:
            order = session.get(Order, p["order_id"])
            if order is None:
                return {"ok": False, "error": "订单不存在", "confidence": 1.0}
            if order.status not in ("completed", "reviewed"):
                return {"ok": False, "error": "仅已完成的订单可以评价", "confidence": 1.0}
            from_id = p["from_user_id"]
            if from_id not in (order.buyer_id, order.seller_id):
                return {"ok": False, "error": "只有交易双方可以评价", "confidence": 1.0}
            to_id = order.seller_id if from_id == order.buyer_id else order.buyer_id
            dup = session.exec(select(Review).where(
                Review.order_id == order.id, Review.from_user_id == from_id
            )).first()
            if dup:
                return {"ok": False, "error": "每笔订单只能评价一次", "confidence": 1.0}

            score = int(p["score"])
            session.add(Review(order_id=order.id, from_user_id=from_id, to_user_id=to_id,
                               score=score, content=p.get("content", "")[:500]))
            delta = self._score_delta(score)
            target = session.get(User, to_id)
            if target:
                self._change_credit(session, target, delta, f"订单 {order.order_no} 收到 {score} 星评价")
            reviews = session.exec(select(Review).where(Review.order_id == order.id)).all()
            order.status = "reviewed" if len({r.from_user_id for r in reviews} &
                                             {order.buyer_id, order.seller_id}) == 2 else "completed"
            order.updated_at = datetime.utcnow()
            audit("user", from_id, "review", "order", order.id,
                  {"score": score, "delta": delta}, order.graph_thread_id, session=session)
            session.commit()
            return {"ok": True, "summary": f"评价成功，对方信用变化 {delta:+d}",
                    "credit_delta": delta, "confidence": 1.0}

    # ---------------- 仲裁联动的信用扣罚 ----------------
    def do_penalize(self, p: dict[str, Any]) -> dict[str, Any]:
        with Session(engine) as session:
            user = session.get(User, int(p["user_id"]))
            if user is None:
                return {"ok": False, "error": "用户不存在", "confidence": 1.0}
            delta = int(p.get("delta", settings.credit_fault_penalty))
            reason = p.get("reason") or f"订单 {p.get('order_id', '')} 仲裁判定责任"
            self._change_credit(session, user, delta, reason)
            audit("admin", p.get("judged_by", "arbitrator"), "credit_penalize", "user", user.id,
                  {"delta": delta, "reason": reason, "order_id": p.get("order_id")},
                  p.get("thread_id"), session=session)
            session.commit()
            return {"ok": True, "user_id": user.id, "credit_delta": delta,
                    "credit_score": user.credit_score, "risk_tag": user.risk_tag,
                    "summary": f"责任方信用扣罚 {delta:+d}，当前信用 {user.credit_score}",
                    "confidence": 1.0}

    # ---------------- 信用工具 ----------------
    def _score_delta(self, score: int) -> int:
        if score >= 4:
            return settings.credit_good_review
        if score == 3:
            return settings.credit_mid_review
        return settings.credit_bad_review

    def _change_credit(self, session: Session, user: User, delta: int, reason: str) -> None:
        user.credit_score = max(0, user.credit_score + delta)
        self.refresh_tag(session, user)
        audit("agent", "credit", "credit_change", "user", user.id,
              {"delta": delta, "reason": reason, "new_score": user.credit_score},
              session=session)

    def refresh_tag(self, session: Session, user: User) -> None:
        deal_count = len(session.exec(select(Order).where(
            (Order.buyer_id == user.id) | (Order.seller_id == user.id),
            Order.status.in_(["completed", "reviewed"]),
        )).all())
        faulty_count = len(session.exec(select(Order).where(
            (Order.buyer_id == user.id) | (Order.seller_id == user.id),
            Order.status == "refunded",
        )).all())
        if user.credit_score < settings.high_risk_threshold or (deal_count >= 1 and faulty_count >= 1):
            user.risk_tag = "high_risk"
        elif deal_count == 0:
            user.risk_tag = "new"
        else:
            user.risk_tag = "normal"
