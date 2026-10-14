"""市场路由：搜索推荐（经 SearchAgent，ACL 留痕）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import current_user
from app.core.response import BizError, ok
from app.kernel.dispatch import call_agent, is_paused_reply, paused_message
from app.models import User


def _guard(reply):
    if is_paused_reply(reply):
        raise BizError(paused_message(reply), code=409, http_status=409)

router = APIRouter(tags=["market"])


@router.get("/market/items")
def search(keyword: str = "", category: str = "",
           min_price: float | None = None, max_price: float | None = None,
           user: User = Depends(current_user)):
    reply = call_agent(
        "search", f"search-{user.id}",
        {"action": "search", "keyword": keyword, "category": category or None,
         "min_price": min_price, "max_price": max_price},
        summary=f"搜索：{keyword or '全部'}",
    )
    _guard(reply)
    return ok(reply.payload, reply.payload.get("summary", "ok"))


@router.get("/market/recommend")
def recommend(item_id: int, category: str = "", user: User = Depends(current_user)):
    reply = call_agent(
        "search", f"recommend-{user.id}-{item_id}",
        {"action": "recommend", "exclude_item_id": item_id, "category": category or None},
        summary="同类替代推荐",
    )
    _guard(reply)
    return ok(reply.payload)
