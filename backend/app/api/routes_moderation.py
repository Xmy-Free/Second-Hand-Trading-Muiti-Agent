"""管理员：人工复核队列与流程恢复（纠纷终裁在 T12 并入本文件）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.api.deps import admin_user
from app.core.database import get_session
from app.core.response import BizError, ok
from app.graph.runner import runner
from app.models import Item, User
from app.schemas.item import to_item_out
from app.services.flow_index import list_waiting_human

router = APIRouter(prefix="/moderation", tags=["moderation"])


class ResumeIn(BaseModel):
    action: str           # approve/reject（复核）；maintain/unfreeze（veto）；uphold/refund（纠纷）
    basis: str = ""


@router.get("/queue")
def review_queue(_: User = Depends(admin_user), session: Session = Depends(get_session)):
    waiting = list_waiting_human("publish")
    result = []
    for w in waiting:
        payload = (w.get("pending_human") or {}).get("payload", {})
        item_id = payload.get("item_id")
        item = session.get(Item, item_id) if item_id else None
        if item is None:
            continue
        seller = session.get(User, item.seller_id)
        result.append({
            "thread_id": w["thread_id"],
            "kind": (w.get("pending_human") or {}).get("kind"),
            "summary": (w.get("pending_human") or {}).get("summary"),
            "item": to_item_out(item, seller),
            "reasons": payload.get("reasons", []),
            "confidence": payload.get("confidence"),
            "created_at": w["created_at"],
        })
    return ok(result)


@router.post("/flows/{thread_id}/resume")
def resume_flow(thread_id: str, body: ResumeIn,
                admin: User = Depends(admin_user),
                session: Session = Depends(get_session)):
    try:
        result = runner.resume(thread_id, {
            "action": body.action, "basis": body.basis, "admin_id": admin.student_no,
        })
    except KeyError as exc:
        raise BizError(str(exc), http_status=404) from exc
    item_id = result["state"].get("item_id")
    item = session.get(Item, item_id) if item_id else None
    return ok({
        "status": result["status"],
        "item": to_item_out(item, session.get(User, item.seller_id)) if item else None,
        "stage": result["state"].get("stage"),
    }, "裁决已写回")
