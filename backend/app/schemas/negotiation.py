"""议价会话视图（对双方隐藏对方保留价）。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import Item, Negotiation, Offer, Order, User


def negotiation_view(neg: Negotiation, session: Session, viewer_id: int) -> dict:
    item = session.get(Item, neg.item_id)
    buyer = session.get(User, neg.buyer_id)
    seller = session.get(User, neg.seller_id)
    offers = session.exec(
        select(Offer).where(Offer.negotiation_id == neg.id).order_by(Offer.id)
    ).all()
    order = session.exec(
        select(Order).where(Order.negotiation_id == neg.id)
    ).first()

    if viewer_id == neg.buyer_id:
        my_role = "buyer"
    elif viewer_id == neg.seller_id:
        my_role = "seller"
    else:
        my_role = "observer"

    # V5 FR-201：AI 虚拟用户透传（对方信息用于议价室 AI 徽章/在线态/人设展示）
    counterpart_id = neg.seller_id if my_role == "buyer" else (
        neg.buyer_id if my_role == "seller" else None)
    counterpart = seller if my_role == "buyer" else (buyer if my_role == "seller" else None)

    created = neg.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    remaining = max(0, int(neg.deadline_seconds - (datetime.now(timezone.utc) - created).total_seconds()))

    return {
        "id": neg.id,
        "item_id": neg.item_id,
        "item_title": item.title if item else "",
        "item_image": item.image_url if item else "",
        "item_price": item.price if item else None,
        "buyer_id": neg.buyer_id,
        "buyer_nickname": buyer.nickname if buyer else "",
        "buyer_is_ai": bool(buyer and buyer.is_ai),
        "seller_id": neg.seller_id,
        "seller_nickname": seller.nickname if seller else "",
        "seller_is_ai": bool(seller and seller.is_ai),
        "counterpart_user_id": counterpart_id,
        "counterpart_nickname": counterpart.nickname if counterpart else "",
        "counterpart_is_ai": bool(counterpart and counterpart.is_ai),
        "counterpart_ai_persona": counterpart.ai_persona if counterpart else "",
        "nash_price": neg.nash_price,
        "max_rounds": neg.max_rounds,
        "deadline_seconds": neg.deadline_seconds,
        "remaining_seconds": remaining,
        "status": neg.status,
        "deal_price": neg.deal_price,
        "order_id": order.id if order else None,
        "order_status": order.status if order else None,
        "my_role": my_role,
        "my_reserve": neg.buyer_reserve if my_role == "buyer"
        else (neg.seller_reserve if my_role == "seller" else None),
        "seller_risk": {"tag": seller.risk_tag, "credit": seller.credit_score} if seller else None,
        "offers": [
            {"id": o.id, "round": o.round, "from_role": o.from_role, "price": o.price,
             "basis": o.basis, "mine": o.from_role == my_role,
             "created_at": o.created_at.isoformat()}
            for o in offers
        ],
        "created_at": neg.created_at.isoformat(),
        "closed_at": neg.closed_at.isoformat() if neg.closed_at else None,
    }
