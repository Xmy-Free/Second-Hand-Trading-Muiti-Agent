"""商品路由：发布 / 详情 / 我的商品 / 重提 / 下架。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.deps import current_user, trading_user
from app.core.database import get_session
from app.core.response import BizError, ok
from app.graph.runner import runner
from app.kernel.dispatch import call_agent, is_paused_reply, paused_message
from app.models import Item, User
from app.schemas.item import ItemPublishIn, to_item_out

router = APIRouter(tags=["items"])


@router.post("/items")
def publish_item(body: ItemPublishIn, user: User = Depends(trading_user),
                 session: Session = Depends(get_session)):
    result = runner.start(
        "publish", user_id=user.id,
        title=body.title, description=body.description,
        price=body.price, image_url=body.image_url or "",
    )
    if result["state"].get("stage") == "agent_paused":
        raise BizError(result["state"]["decisions"][-1].get("error", "商品审核 Agent 已暂停"),
                       code=409, http_status=409)
    item_id = result["state"].get("item_id")
    item = session.get(Item, item_id) if item_id else None
    if item is None:
        raise BizError("商品创建失败")
    data = to_item_out(item, user, result["thread_id"] if result["status"] == "waiting" else None)
    data["flow_status"] = result["status"]
    data["missing"] = result["state"].get("decisions", [{}])[-1].get("missing", [])
    data["pending_human"] = result["pending_human"]
    return ok(data, "商品已提交" if result["status"] != "done" or item.status == "on_sale" else "已提交审核")


@router.get("/items/{item_id}")
def item_detail(item_id: int, session: Session = Depends(get_session),
                _: User = Depends(current_user)):
    item = session.get(Item, item_id)
    if item is None:
        raise BizError("商品不存在", http_status=404)
    seller = session.get(User, item.seller_id)
    return ok(to_item_out(item, seller))


@router.get("/my/items")
def my_items(status: str | None = None, user: User = Depends(current_user),
             session: Session = Depends(get_session)):
    stmt = select(Item).where(Item.seller_id == user.id)
    if status:
        stmt = stmt.where(Item.status == status)
    rows = session.exec(stmt.order_by(Item.id.desc())).all()
    return ok([to_item_out(r, user) for r in rows])


@router.post("/items/{item_id}/resubmit")
def resubmit(item_id: int, body: ItemPublishIn, user: User = Depends(trading_user),
             session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if item is None:
        raise BizError("商品不存在", http_status=404)
    if item.seller_id != user.id:
        raise BizError("只能操作自己的商品", code=403, http_status=403)
    if item.status != "rejected":
        raise BizError("仅被驳回的商品可以修改重提")
    if item.reject_count > 1:
        raise BizError("该商品已使用过一次重提机会，无法再次提交")

    item.title = body.title or item.title
    item.description = body.description
    if body.price is not None:
        item.price = body.price
    item.image_url = body.image_url or item.image_url
    item.status = "pending"
    session.commit()

    result = runner.start("publish", user_id=user.id, item_id=item.id)
    if result["state"].get("stage") == "agent_paused":
        raise BizError(result["state"]["decisions"][-1].get("error", "商品审核 Agent 已暂停"),
                       code=409, http_status=409)
    session.refresh(item)
    data = to_item_out(item, user, result["thread_id"] if result["status"] == "waiting" else None)
    data["flow_status"] = result["status"]
    data["pending_human"] = result["pending_human"]
    return ok(data, "商品已重新提交审核")


@router.post("/items/{item_id}/off-shelf")
def off_shelf(item_id: int, user: User = Depends(trading_user),
              session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if item is None:
        raise BizError("商品不存在", http_status=404)
    if item.seller_id != user.id:
        raise BizError("只能操作自己的商品", code=403, http_status=403)
    # 经 ACL 调商品管理 Agent：仅未锁定的在售商品可下架（锁定/冻结一律拒绝，留 ACL 痕）
    reply = call_agent(
        "commodity", f"off-shelf-{item_id}",
        {"action": "off_shelf", "item_id": item_id},
        summary=f"卖家下架商品 {item_id}",
    )
    if is_paused_reply(reply):
        raise BizError(paused_message(reply), code=409, http_status=409)
    if not reply.payload.get("ok"):
        raise BizError(reply.payload.get("error", "下架失败"))
    session.refresh(item)
    return ok(to_item_out(item, user), "商品已下架")
