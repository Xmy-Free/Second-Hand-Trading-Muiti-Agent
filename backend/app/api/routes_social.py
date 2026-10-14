"""评价、信用主页、订单审计时间线。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import current_user
from app.core.database import get_session
from app.core.response import BizError, ok
from app.graph.runner import runner
from app.kernel.dispatch import call_agent
from app.models import AuditLog, ConflictEvent, Offer, Order, Review, User

router = APIRouter(tags=["social"])


class ReviewIn(BaseModel):
    order_id: int
    score: int = Field(ge=1, le=5)
    content: str = Field(default="", max_length=500)


@router.post("/reviews")
def submit_review(body: ReviewIn, user: User = Depends(current_user),
                  session: Session = Depends(get_session)):
    reply = call_agent(
        "credit", f"review-{body.order_id}",
        {"action": "review", "order_id": body.order_id, "from_user_id": user.id,
         "score": body.score, "content": body.content},
        summary=f"{user.nickname} 提交 {body.score} 星评价",
    )
    data = reply.payload
    if not data.get("ok"):
        raise BizError(data.get("error", "评价失败"))
    return ok(data, data.get("summary", "评价成功"))


@router.get("/reviews/received")
def received_reviews(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.exec(
        select(Review).where(Review.to_user_id == user.id).order_by(Review.id.desc())
    ).all()
    out = []
    for r in rows:
        order = session.get(Order, r.order_id)
        out.append({
            "id": r.id, "order_id": r.order_id,
            "item_title": _item_title(session, order) if order else "",
            "score": r.score, "content": r.content,
            "from_nickname": session.get(User, r.from_user_id).nickname,
            "created_at": r.created_at.isoformat(),
        })
    return ok(out)


def _item_title(session: Session, order: Order) -> str:
    from app.models import Item
    item = session.get(Item, order.item_id)
    return item.title if item else ""


@router.get("/credit/me")
def my_credit(user: User = Depends(current_user), session: Session = Depends(get_session)):
    reviews_given = session.exec(
        select(Review).where(Review.from_user_id == user.id).order_by(Review.id.desc())
    ).all()
    changes = session.exec(
        select(AuditLog).where(AuditLog.target_type == "user",
                               AuditLog.target_id == str(user.id),
                               AuditLog.action == "credit_change").order_by(AuditLog.id.desc())
    ).all()
    deal_orders = session.exec(select(Order).where(
        ((Order.buyer_id == user.id) | (Order.seller_id == user.id)),
        Order.status.in_(["completed", "reviewed"]),
    )).all()
    return ok({
        "credit_score": user.credit_score,
        "risk_tag": user.risk_tag,
        "deal_count": len(deal_orders),
        "review_count": len(reviews_given),
        "changes": [{"delta": c.detail.get("delta"), "reason": c.detail.get("reason"),
                     "new_score": c.detail.get("new_score"), "created_at": c.created_at.isoformat()}
                    for c in changes[:20]],
    })


@router.get("/audit/orders/{order_id}")
def order_timeline(order_id: int, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if order is None:
        raise BizError("订单不存在", http_status=404)
    if user.id not in (order.buyer_id, order.seller_id) and not user.is_admin:
        raise BizError("无权查看该订单", code=403, http_status=403)

    audits = session.exec(
        select(AuditLog).where(AuditLog.graph_thread_id == order.graph_thread_id)
    ).all() if order.graph_thread_id else []
    conflicts = session.exec(
        select(ConflictEvent).where(ConflictEvent.graph_thread_id == order.graph_thread_id)
    ).all() if order.graph_thread_id else []
    offers = []
    if order.negotiation_id:
        offers = session.exec(
            select(Offer).where(Offer.negotiation_id == order.negotiation_id).order_by(Offer.id)
        ).all()

    decisions = []
    if order.graph_thread_id:
        try:
            snap = runner.get_state(order.graph_thread_id)
            decisions = snap["state"].get("decisions", [])
        except KeyError:
            decisions = []

    return ok({
        "order_id": order.id,
        "thread_id": order.graph_thread_id,
        "node_decisions": decisions,
        "offers": [{"round": o.round, "from_role": o.from_role, "price": o.price,
                    "basis": o.basis} for o in offers],
        "audits": [{"actor_type": a.actor_type, "actor_id": a.actor_id, "action": a.action,
                    "detail": a.detail, "created_at": a.created_at.isoformat()} for a in audits],
        "conflicts": [{"scene": c.scene, "type": c.type, "level": c.level,
                       "payload": c.payload, "result": c.result,
                       "created_at": c.created_at.isoformat()} for c in conflicts],
    })
