"""商品 API 契约与序列化。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models import Item, User

STATUS_TEXT = {
    "draft": "待补充",
    "pending": "待审核",
    "manual": "待人工复核",
    "on_sale": "在售",
    "locked": "已锁定",
    "dealed": "已成交",
    "rejected": "已驳回",
    "frozen": "已冻结",
    "off_shelf": "已下架",
}


class ItemPublishIn(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    description: str = Field(min_length=5, max_length=2000)
    price: float | None = Field(default=None, ge=0, le=100000)
    image_url: str | None = None


class ItemOut(BaseModel):
    id: int
    seller_id: int
    seller_nickname: str = ""
    seller_credit: int = 100
    seller_is_ai: bool = False
    title: str
    category: str
    condition_level: str
    attrs: dict[str, Any] = {}
    description: str
    image_url: str
    price: float
    price_suggest_min: float | None = None
    price_suggest_max: float | None = None
    status: str
    status_text: str
    reject_count: int
    audit_reason: list[Any] = []
    graph_thread_id: str | None = None
    reason_text: str = ""

def to_item_out(item: Item, seller: User | None = None, graph_thread_id: str | None = None) -> dict:
    reasons = item.audit_reason or []
    reason_text = "；".join(
        r.get("detail", str(r)) if isinstance(r, dict) else str(r) for r in reasons
    )
    return {
        "id": item.id,
        "seller_id": item.seller_id,
        "seller_nickname": seller.nickname if seller else "",
        "seller_credit": seller.credit_score if seller else 100,
        "seller_is_ai": bool(seller and getattr(seller, "is_ai", False)),
        "title": item.title,
        "category": item.category,
        "condition_level": item.condition_level,
        "attrs": item.attrs or {},
        "description": item.description,
        "image_url": item.image_url or "",
        "price": item.price,
        "price_suggest_min": item.price_suggest_min,
        "price_suggest_max": item.price_suggest_max,
        "status": item.status,
        "status_text": STATUS_TEXT.get(item.status, item.status),
        "reject_count": item.reject_count,
        "audit_reason": reasons,
        "graph_thread_id": graph_thread_id,
        "reason_text": reason_text,
    }
