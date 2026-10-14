"""申诉路由：发起 / 我的申诉 / 管理员终裁队列 / 证据包。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import admin_user, current_user
from app.core.database import get_session
from app.core.response import BizError, ok
from app.graph.runner import runner
from app.models import Appeal, Item, Order, User
from app.services.flow_index import list_waiting_human

router = APIRouter(tags=["appeals"])


class AppealIn(BaseModel):
    order_id: int
    reason: str = Field(min_length=5, max_length=1000)


@router.post("/appeals")
def submit_appeal(body: AppealIn, user: User = Depends(current_user),
                  session: Session = Depends(get_session)):
    """发起申诉。FR-1：冻结账号禁止交易类操作，但保留申诉权，故仅要求登录（current_user），
    交易参与方校验在下方完成。"""
    order = session.get(Order, body.order_id)
    if order is None:
        raise BizError("订单不存在", http_status=404)
    if user.id not in (order.buyer_id, order.seller_id):
        raise BizError("只有交易双方可以发起申诉", code=403, http_status=403)
    if order.status not in ("paid", "receiving", "appealing"):
        raise BizError("当前订单状态不允许申诉")
    dup = session.exec(select(Appeal).where(
        Appeal.order_id == order.id, Appeal.status == "pending"
    )).first()
    if dup:
        raise BizError("该订单已有进行中的申诉", code=409, http_status=409)

    appeal = Appeal(order_id=order.id, appellant_id=user.id, reason=body.reason,
                    evidence={}, status="pending")
    session.add(appeal)
    session.commit()
    session.refresh(appeal)

    result = runner.start("appeal", user_id=user.id, appeal_id=appeal.id, order_id=order.id)
    return ok({
        "appeal_id": appeal.id,
        "thread_id": result["thread_id"],
        "status": result["status"],
        "pending_human": result["pending_human"],
        "stage": result["state"].get("stage"),
        "rule": result["state"].get("vote"),
    }, "申诉已提交")


@router.get("/appeals/mine")
def my_appeals(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Appeal).where(Appeal.appellant_id == user.id)
                        .order_by(Appeal.id.desc())).all()
    out = []
    for a in rows:
        order = session.get(Order, a.order_id)
        item = session.get(Item, order.item_id) if order else None
        out.append({
            "id": a.id, "order_id": a.order_id,
            "item_title": item.title if item else "",
            "reason": a.reason, "status": a.status, "ruling": a.ruling,
            "ruling_basis": a.ruling_basis, "judged_by": a.judged_by,
            "created_at": a.created_at.isoformat(),
            "ruled_at": a.ruled_at.isoformat() if a.ruled_at else None,
        })
    return ok(out)


def _queue_row(*, thread_id: str, appeal: Appeal, order: Order | None,
               item: Item | None, appellant: User | None,
               rule_suggestion, created_at: str) -> dict:
    return {
        "thread_id": thread_id,
        "appeal_id": appeal.id,
        "reason": appeal.reason,
        "appellant_nickname": appellant.nickname if appellant else "",
        "order_id": order.id if order else None,
        "order_no": order.order_no if order else "",
        "deal_price": order.deal_price if order else None,
        "item_title": item.title if item else "",
        "rule_suggestion": rule_suggestion,
        "evidence": appeal.evidence or {},
        "created_at": created_at,
    }


@router.get("/appeals/queue")
def appeal_queue(_: User = Depends(admin_user), session: Session = Depends(get_session)):
    """纠纷终裁台队列：
    1) 实时部分——挂在 appeal_human_gate 等待人工的流程实例（含规则裁决建议）；
    2) 台账补全——数据库中 status=pending 但无等待流程实例支撑的申诉（历史播种/
       流程归档后的待办），保证终裁台不遗漏真实待办。
    """
    out: list[dict] = []
    live_appeal_ids: set[int] = set()
    waiting = list_waiting_human("appeal")
    for w in waiting:
        payload = (w.get("pending_human") or {}).get("payload", {})
        appeal_id = payload.get("appeal_id")
        appeal = session.get(Appeal, appeal_id) if appeal_id else None
        if appeal is None:
            continue
        live_appeal_ids.add(appeal.id)
        order = session.get(Order, appeal.order_id)
        item = session.get(Item, order.item_id) if order else None
        appellant = session.get(User, appeal.appellant_id)
        out.append(_queue_row(
            thread_id=w["thread_id"], appeal=appeal, order=order, item=item,
            appellant=appellant, rule_suggestion=payload.get("rule_suggestion"),
            created_at=w["created_at"],
        ))

    pending_rows = session.exec(
        select(Appeal).where(Appeal.status == "pending").order_by(Appeal.id.desc())
    ).all()
    for appeal in pending_rows:
        if appeal.id in live_appeal_ids:
            continue
        order = session.get(Order, appeal.order_id)
        item = session.get(Item, order.item_id) if order else None
        appellant = session.get(User, appeal.appellant_id)
        out.append(_queue_row(
            thread_id="", appeal=appeal, order=order, item=item,
            appellant=appellant, rule_suggestion=None,
            created_at=appeal.created_at.isoformat(),
        ))

    out.sort(key=lambda r: r["created_at"], reverse=True)
    return ok(out)


@router.get("/appeals/{appeal_id}")
def appeal_detail(appeal_id: int, user: User = Depends(current_user),
                  session: Session = Depends(get_session)):
    appeal = session.get(Appeal, appeal_id)
    if appeal is None:
        raise BizError("申诉不存在", http_status=404)
    order = session.get(Order, appeal.order_id)
    if not user.is_admin and user.id not in (appeal.appellant_id,
                                            order.buyer_id if order else -1,
                                            order.seller_id if order else -1):
        raise BizError("无权查看该申诉", code=403, http_status=403)
    return ok({
        "id": appeal.id, "order_id": appeal.order_id, "reason": appeal.reason,
        "status": appeal.status, "ruling": appeal.ruling,
        "ruling_basis": appeal.ruling_basis, "judged_by": appeal.judged_by,
        "evidence": appeal.evidence or {},
        "created_at": appeal.created_at.isoformat(),
    })
