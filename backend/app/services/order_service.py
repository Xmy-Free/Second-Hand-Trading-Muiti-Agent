"""订单领域服务：预占锁、状态机、超时释放（功能正确性优先，不做并发优化）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import update
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.models import Item, Negotiation, Order

# 合法状态迁移（3.3 状态机）
TRANSITIONS: dict[str, set[str]] = {
    "created": {"unpaid", "canceled"},
    "unpaid": {"paid", "canceled"},
    "paid": {"receiving", "appealing"},
    "receiving": {"completed", "appealing"},
    "appealing": {"completed", "refunded"},
    "completed": {"reviewed"},
    "canceled": set(),
    "refunded": set(),
    "reviewed": set(),
}

TERMINAL = {"canceled", "refunded", "reviewed"}


def gen_order_no() -> str:
    import time
    return f"ORD{time.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6]}"


def try_lock_item(session: Session, item_id: int) -> bool:
    """乐观锁：仅在售商品可被锁定一次。"""
    result = session.exec(
        select(Item).where(Item.id == item_id, Item.status == "on_sale")
    ).first()
    if result is None:
        return False
    stmt = (
        update(Item)
        .where(Item.id == item_id, Item.status == "on_sale", Item.lock_version == result.lock_version)
        .values(status="locked", lock_version=Item.lock_version + 1)
    )
    cursor = session.execute(stmt)
    rowcount = getattr(cursor, "rowcount", 0)
    if not rowcount:
        session.rollback()
        return False
    return True


def release_item(session: Session, item_id: int, *, dealed: bool) -> None:
    item = session.get(Item, item_id)
    if item and item.status == "locked":
        item.status = "dealed" if dealed else "on_sale"
        if dealed:
            item.lock_version += 1


def assert_transition(old: str, new: str) -> None:
    if new not in TRANSITIONS.get(old, set()):
        raise ValueError(f"非法订单状态迁移：{old} → {new}")


def is_pay_expired(order: Order, now: datetime | None = None) -> bool:
    if order.status != "unpaid" or not order.pay_deadline:
        return False
    deadline = order.pay_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return now > deadline


def get_order(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)


def list_orders(session: Session, user_id: int, role: str | None = None) -> list[Order]:
    stmt = select(Order)
    if role == "buyer":
        stmt = stmt.where(Order.buyer_id == user_id)
    elif role == "seller":
        stmt = stmt.where(Order.seller_id == user_id)
    else:
        stmt = stmt.where((Order.buyer_id == user_id) | (Order.seller_id == user_id))
    return list(session.exec(stmt.order_by(Order.id.desc())).all())


def create_order_from_negotiation(negotiation_id: int, thread_id: str | None = None) -> dict[str, Any]:
    """成交建单入口（由 trade flow 的锁节点调用）。"""
    with Session(engine) as session:
        neg = session.get(Negotiation, negotiation_id)
        if neg is None or neg.status != "deal":
            return {"ok": False, "error": "议价未成交，无法建单"}

        existed = session.exec(
            select(Order).where(Order.negotiation_id == negotiation_id)
        ).first()
        if existed:
            return {"ok": True, "order_id": existed.id, "idempotent": True,
                    "status": existed.status}

        if not try_lock_item(session, neg.item_id):
            session.commit()
            return {"ok": False, "error": "RESOURCE_LOCKED",
                    "message": "商品已被其他买家抢先锁定（并发抢单冲突）"}

        order = Order(
            order_no=gen_order_no(), item_id=neg.item_id, negotiation_id=neg.id,
            buyer_id=neg.buyer_id, seller_id=neg.seller_id,
            deal_price=neg.deal_price or 0.0, status="unpaid",
            lock_token=uuid.uuid4().hex,
            pay_deadline=datetime.utcnow() + timedelta(minutes=settings.pay_timeout_minutes),
            graph_thread_id=thread_id,
        )
        session.add(order)
        session.commit()
        session.refresh(order)
        return {"ok": True, "order_id": order.id, "status": order.status,
                "pay_deadline": order.pay_deadline.isoformat()}
