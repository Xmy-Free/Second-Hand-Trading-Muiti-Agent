"""⑦ 交易履约 Agent：预占锁 + 乐观版本 + 超时点、订单状态机、沙箱支付、抢单三优先裁决。

抢单优先级（spec FR-7）：下单时间 → 信用分 → 支付完成；败者释放并给替代推荐。
信用扣罚拆分给 credit Agent；本 Agent 只负责订单状态与锁。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.agents.base import BaseAgent
from app.core.database import engine
from app.kernel.acl import AclEnvelope
from app.kernel.dispatch import call_agent
from app.kernel.observe import audit, record_conflict
from app.models import Item, Negotiation, Order, User
from app.services import order_service

ARBITRATION_RULE = "裁决依据：下单时间优先 → 信用分优先 → 支付完成优先"


class OrderAgent(BaseAgent):
    name = "order"
    display_name = "交易履约 Agent"
    avatar = "ClipboardList"
    accent = "#FBBF24"
    capabilities = ["订单状态机", "预占锁", "乐观版本", "抢单三优先裁决", "模拟支付", "超时释放"]
    description = "账房调度：成交瞬间预占锁建单，按三优先级裁决并发抢单，跟踪沙箱支付/交付/超时与裁决执行。"

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        self.ensure_running()
        action = msg.payload.get("action")
        handlers = {
            "create_order": self.do_create_order,
            "pay": self.do_pay,
            "deliver": self.do_deliver,
            "receive": self.do_receive,
            "cancel": self.do_cancel,
            "mark_appealing": self.do_mark_appealing,
            "apply_ruling": self.do_apply_ruling,
        }
        fn = handlers.get(action)
        if not fn:
            return msg.reply("refuse", {"error": f"unknown action {action}"}, error_code="BAD_ACTION")
        data = fn(msg.payload)
        return msg.reply("inform", data, confidence=data.get("confidence", 0.9),
                         summary=data.get("summary", action))

    # ---------------- 建单 / 抢单裁决 ----------------
    def do_create_order(self, p: dict[str, Any]) -> dict[str, Any]:
        result = order_service.create_order_from_negotiation(
            p["negotiation_id"], p.get("thread_id")
        )
        if result.get("ok"):
            audit("agent", "order", "order_created", "order", result.get("order_id"),
                  {"negotiation_id": p["negotiation_id"]}, p.get("thread_id"))
            return {**result, "summary": "预占锁成功，订单已创建，等待支付", "confidence": 1.0}

        if result.get("error") == "RESOURCE_LOCKED":
            with Session(engine) as session:
                neg = session.get(Negotiation, p["negotiation_id"])
                item_id = neg.item_id if neg else None
                winner = None
                loser_buyer_id = neg.buyer_id if neg else None
                if item_id:
                    winner_order = session.exec(select(Order).where(
                        Order.item_id == item_id
                    ).order_by(Order.created_at, Order.id)).first()
                    if winner_order:
                        w_user = session.get(User, winner_order.buyer_id)
                        winner = {
                            "order_id": winner_order.id, "order_no": winner_order.order_no,
                            "buyer_id": winner_order.buyer_id,
                            "buyer_nickname": w_user.nickname if w_user else "",
                            "credit_score": w_user.credit_score if w_user else None,
                            "created_at": winner_order.created_at.isoformat(),
                            "paid": winner_order.status in ("paid", "receiving", "completed", "reviewed"),
                        }
                cat = session.get(Item, item_id).category if item_id else None
                basis = self._arbitration_basis(session, winner, loser_buyer_id)
                rec = record_conflict(
                    scene="C2", ctype="resource", level=2,
                    participants=["order", "buyer_a", "buyer_b"],
                    payload={"negotiation_id": p["negotiation_id"],
                             "rule": "时间优先→信用优先→支付完成优先",
                             "winner": winner, "loser_buyer_id": loser_buyer_id,
                             "arbitration_basis": basis},
                    result="预占锁裁决：仅一单成交，失败方释放并获得替代推荐",
                    graph_thread_id=p.get("thread_id"), session=session,
                )
                session.commit()
            # 经 ACL 向搜索 Agent 请求替代推荐（多 Agent 消息留痕）
            alt: list[dict] = []
            try:
                alt_reply = call_agent(
                    "search", f"c2-alt-{p['negotiation_id']}",
                    {"action": "recommend", "exclude_item_id": item_id, "category": cat},
                    summary="资源冲突：为失败买家推荐同类替代商品",
                )
                alt = alt_reply.payload.get("items", [])
            except Exception:  # noqa: BLE001 - 推荐失败不影响裁决结论
                alt = []
            return {"ok": False, "conflict": "C2", "conflict_id": rec["id"],
                    "error": "手慢一步！商品已被其他买家锁定", "alternatives": alt,
                    "arbitration_basis": basis, "winner": winner,
                    "confidence": 1.0}
        return {**result, "confidence": 1.0}

    def _arbitration_basis(self, session: Session, winner: dict | None,
                           loser_buyer_id: int | None) -> str:
        parts = [ARBITRATION_RULE]
        if winner and loser_buyer_id:
            loser = session.get(User, loser_buyer_id)
            parts.append(
                f"胜出买家『{winner['buyer_nickname']}』(信用 {winner['credit_score']}，"
                f"下单时刻 {winner['created_at']}) 先于失败买家"
                f"『{loser.nickname if loser else loser_buyer_id}』(信用 {loser.credit_score if loser else '-'})"
                "完成预占锁；同时间再比信用分，信用相同则已支付者优先")
        return "；".join(parts)

    # ---------------- 支付（幂等 + 超时取消释放） ----------------
    def do_pay(self, p: dict[str, Any]) -> dict[str, Any]:
        with Session(engine) as session:
            order = session.get(Order, p["order_id"])
            if order is None:
                return {"ok": False, "error": "订单不存在", "confidence": 1.0}
            if order.status == "paid":
                return {"ok": True, "idempotent": True, "status": "paid",
                        "summary": "订单已支付，请勿重复操作", "confidence": 1.0}
            if order.status != "unpaid":
                return {"ok": False, "error": f"当前状态 {order.status} 不允许支付", "confidence": 1.0}
            if order_service.is_pay_expired(order):
                self._cancel_locked(session, order, "支付超时，系统自动取消并释放商品锁")
                session.commit()
                return {"ok": False, "status": "canceled", "error": "支付超时，订单已取消",
                        "confidence": 1.0}
            order.status = "paid"
            order.updated_at = datetime.utcnow()
            audit("user", p.get("user_id", order.buyer_id), "pay", "order", order.id,
                  {"deal_price": order.deal_price}, order.graph_thread_id, session=session)
            session.commit()
            session.refresh(order)
            return {"ok": True, "status": "paid", "summary": "支付成功（沙箱模拟）",
                    "confidence": 1.0}

    def do_deliver(self, p: dict[str, Any]) -> dict[str, Any]:
        return self._move(p, "paid", "receiving", "卖家确认已面交交付")

    def do_receive(self, p: dict[str, Any]) -> dict[str, Any]:
        return self._move(p, "receiving", "completed", "买家确认收货，交易完成")

    def do_cancel(self, p: dict[str, Any]) -> dict[str, Any]:
        with Session(engine) as session:
            order = session.get(Order, p["order_id"])
            if order is None:
                return {"ok": False, "error": "订单不存在", "confidence": 1.0}
            if order.status in order_service.TERMINAL:
                return {"ok": True, "idempotent": True, "status": order.status, "confidence": 1.0}
            self._cancel_locked(session, order, p.get("reason", "订单取消"))
            session.commit()
            return {"ok": True, "status": "canceled", "summary": "订单已取消，商品锁已释放",
                    "confidence": 1.0}

    def _move(self, p: dict[str, Any], old: str, new: str, summary: str) -> dict[str, Any]:
        with Session(engine) as session:
            order = session.get(Order, p["order_id"])
            if order is None:
                return {"ok": False, "error": "订单不存在", "confidence": 1.0}
            try:
                order_service.assert_transition(order.status, new)
            except ValueError as exc:
                return {"ok": False, "error": str(exc), "confidence": 1.0}
            order.status = new
            order.updated_at = datetime.utcnow()
            if new == "completed":
                order_service.release_item(session, order.item_id, dealed=True)
            audit(p.get("actor_type", "user"), p.get("user_id", ""), f"order_{new}",
                  "order", order.id, {"from": old}, order.graph_thread_id, session=session)
            session.commit()
            return {"ok": True, "status": new, "summary": summary, "confidence": 1.0}

    def _cancel_locked(self, session: Session, order: Order, reason: str) -> None:
        if order.status in ("unpaid", "created"):
            order.status = "canceled"
            order.updated_at = datetime.utcnow()
            order_service.release_item(session, order.item_id, dealed=False)
            audit("agent", "order", "order_canceled", "order", order.id,
                  {"reason": reason}, order.graph_thread_id, session=session)

    def do_mark_appealing(self, p: dict[str, Any]) -> dict[str, Any]:
        with Session(engine) as session:
            order = session.get(Order, p["order_id"])
            if order is None:
                return {"ok": False, "error": "订单不存在", "confidence": 1.0}
            if order.status == "appealing":
                return {"ok": True, "idempotent": True, "status": "appealing", "confidence": 1.0}
            try:
                order_service.assert_transition(order.status, "appealing")
            except ValueError as exc:
                return {"ok": False, "error": str(exc), "confidence": 1.0}
            order.status = "appealing"
            order.updated_at = datetime.utcnow()
            session.commit()
            audit("user", p.get("user_id", ""), "appeal_submit", "order", order.id,
                  {"reason": p.get("reason", "")}, order.graph_thread_id, session=session)
            session.commit()
            return {"ok": True, "status": "appealing", "confidence": 1.0}

    # ---------------- 裁决执行（仅订单状态机；信用扣罚由 credit Agent 执行） ----------------
    def do_apply_ruling(self, p: dict[str, Any]) -> dict[str, Any]:
        with Session(engine) as session:
            order = session.get(Order, p["order_id"])
            if order is None or order.status != "appealing":
                return {"ok": False, "error": "订单不在申诉中", "confidence": 1.0}
            if p["ruling"] == "uphold":
                order.status = "completed"
                order_service.release_item(session, order.item_id, dealed=True)
            else:
                order.status = "refunded"
                order_service.release_item(session, order.item_id, dealed=False)
            order.updated_at = datetime.utcnow()
            audit("admin", p.get("judged_by", "admin"), "ruling_applied", "order", order.id,
                  {"ruling": p["ruling"]}, order.graph_thread_id, session=session)
            session.commit()
            return {"ok": True, "status": order.status, "summary": "裁决已执行（订单状态）",
                    "confidence": 1.0}
