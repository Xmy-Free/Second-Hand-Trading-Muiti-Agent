"""订单/评价视图。"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import Item, Order, Review, User

ORDER_STATUS_TEXT = {
    "created": "已创建",
    "unpaid": "待支付",
    "paid": "已支付",
    "receiving": "待收货",
    "completed": "已完成",
    "appealing": "申诉中",
    "refunded": "已退款",
    "canceled": "已取消",
    "reviewed": "已评价",
}


def order_view(order: Order, session: Session, viewer_id: int) -> dict:
    item = session.get(Item, order.item_id)
    buyer = session.get(User, order.buyer_id)
    seller = session.get(User, order.seller_id)
    my_role = "buyer" if viewer_id == order.buyer_id else "seller"
    counterparty = seller if my_role == "buyer" else buyer
    reviews = session.exec(select(Review).where(Review.order_id == order.id)).all()
    i_reviewed = any(r.from_user_id == viewer_id for r in reviews)
    return {
        "id": order.id,
        "order_no": order.order_no,
        "item_id": order.item_id,
        "item_title": item.title if item else "",
        "item_image": item.image_url if item else "",
        "negotiation_id": order.negotiation_id,
        "buyer_id": order.buyer_id,
        "seller_id": order.seller_id,
        "my_role": my_role,
        "counterparty_nickname": counterparty.nickname if counterparty else "",
        "counterparty_id": counterparty.id if counterparty else None,
        "deal_price": order.deal_price,
        "status": order.status,
        "status_text": ORDER_STATUS_TEXT.get(order.status, order.status),
        "lock_token": order.lock_token,
        "graph_thread_id": order.graph_thread_id,
        "i_reviewed": i_reviewed,
        "review_count": len(reviews),
        "pay_deadline": order.pay_deadline.isoformat() if order.pay_deadline else None,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }
