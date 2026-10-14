"""订单路由：支付（resume 交易流）/ 交付 / 收货 / 取消 / 列表详情 / 审计时间线。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import current_user, trading_user
from app.core.database import get_session
from app.core.response import BizError, ok
from app.graph.runner import runner
from app.kernel.dispatch import call_agent
from app.kernel.observe import emit_node
from app.models import Order, User
from app.schemas.order import order_view

router = APIRouter(tags=["orders"])


def _participant(order: Order, user: User) -> None:
    if user.id not in (order.buyer_id, order.seller_id) and not user.is_admin:
        raise BizError("无权操作该订单", code=403, http_status=403)


def _resume_if_waiting(order: Order, action: str, user: User, basis: str = "") -> dict | None:
    tid = order.graph_thread_id
    if not tid:
        return None
    try:
        snap = runner.get_state(tid)
    except KeyError:
        return None
    if snap["status"] == "waiting" and (snap["pending_human"] or {}).get("kind") == "wait_pay":
        return runner.resume(tid, {"action": action, "admin_id": user.student_no, "basis": basis})
    return None


@router.get("/orders")
def list_mine(role: str = "", user: User = Depends(current_user),
              session: Session = Depends(get_session)):
    from app.services.order_service import list_orders

    rows = list_orders(session, user.id, role or None)
    return ok([order_view(o, session, user.id) for o in rows])


@router.get("/orders/{order_id}")
def detail(order_id: int, user: User = Depends(current_user),
           session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if order is None:
        raise BizError("订单不存在", http_status=404)
    _participant(order, user)
    return ok(order_view(order, session, user.id))


@router.post("/orders/{order_id}/pay")
def pay(order_id: int, user: User = Depends(trading_user),
        session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if order is None:
        raise BizError("订单不存在", http_status=404)
    _participant(order, user)
    resumed = _resume_if_waiting(order, "pay", user)
    if resumed is None:
        reply = call_agent("order", f"pay-{order_id}",
                           {"action": "pay", "order_id": order_id, "user_id": user.id},
                           summary="沙箱模拟支付")
        payload = reply.payload
        if not payload.get("ok"):
            session.refresh(order)
            if payload.get("status") == "canceled":
                return ok(order_view(order, session, user.id), payload.get("error", "订单已取消"))
            raise BizError(payload.get("error", "支付失败"))
    elif resumed and resumed["state"].get("stage") == "pay_expired":
        session.refresh(order)
        return ok(order_view(order, session, user.id), "支付超时，订单已取消并释放锁")
    session.refresh(order)
    return ok(order_view(order, session, user.id), "支付成功（沙箱模拟）")


@router.post("/orders/{order_id}/cancel")
def cancel(order_id: int, user: User = Depends(trading_user),
           session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if order is None:
        raise BizError("订单不存在", http_status=404)
    _participant(order, user)
    _resume_if_waiting(order, "cancel", user, "买家取消")
    session.refresh(order)
    if order.status not in ("canceled",):
        reply = call_agent("order", f"cancel-{order_id}",
                           {"action": "cancel", "order_id": order_id, "reason": "用户取消"},
                           summary="取消订单")
        if not reply.payload.get("ok"):
            raise BizError(reply.payload.get("error", "取消失败"))
    session.refresh(order)
    return ok(order_view(order, session, user.id), "订单已取消")


@router.post("/orders/{order_id}/deliver")
def deliver(order_id: int, user: User = Depends(trading_user),
            session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if order is None:
        raise BizError("订单不存在", http_status=404)
    if order.seller_id != user.id:
        raise BizError("仅卖家可以确认交付", code=403, http_status=403)
    reply = call_agent("order", f"deliver-{order_id}",
                       {"action": "deliver", "order_id": order_id, "user_id": user.id,
                        "actor_type": "user"},
                       summary="卖家确认交付")
    data = reply.payload
    if not data.get("ok"):
        raise BizError(data.get("error", "操作失败"))
    if order.graph_thread_id:
        emit_node(thread_id=order.graph_thread_id, flow="trade",
                  node="seller_deliver", status="exit", summary="卖家确认校内面交交付")
    session.refresh(order)
    return ok(order_view(order, session, user.id), data.get("summary", "已确认交付"))


@router.post("/orders/{order_id}/receive")
def receive(order_id: int, user: User = Depends(trading_user),
            session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if order is None:
        raise BizError("订单不存在", http_status=404)
    if order.buyer_id != user.id:
        raise BizError("仅买家可以确认收货", code=403, http_status=403)
    reply = call_agent("order", f"receive-{order_id}",
                       {"action": "receive", "order_id": order_id, "user_id": user.id,
                        "actor_type": "user"},
                       summary="买家确认收货")
    data = reply.payload
    if not data.get("ok"):
        raise BizError(data.get("error", "操作失败"))
    if order.graph_thread_id:
        emit_node(thread_id=order.graph_thread_id, flow="trade",
                  node="buyer_receive", status="exit", summary="买家确认收货，交易完成")
    session.refresh(order)
    return ok(order_view(order, session, user.id), data.get("summary", "已确认收货"))
