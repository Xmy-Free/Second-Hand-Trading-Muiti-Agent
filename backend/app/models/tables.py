"""SQLModel 表模型（spec 第 4 章，共 11 张表）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, UniqueConstraint
from sqlmodel import JSON, Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_no: str = Field(index=True, unique=True, max_length=32)
    password_hash: str
    nickname: str = Field(max_length=64)
    is_buyer: bool = True
    is_seller: bool = True
    is_admin: bool = False
    credit_score: int = 100
    risk_tag: str = Field(default="new", max_length=16)  # normal/new/high_risk
    status: str = Field(default="active", max_length=16)  # active/frozen
    avatar_seed: str = Field(default="", max_length=64)
    # V5：AI 虚拟用户标识与人设（FR-201）
    is_ai: bool = False
    ai_persona: str = Field(default="", max_length=128)
    created_at: datetime = Field(default_factory=utcnow)


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    seller_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(max_length=128)
    category: str = Field(max_length=32, index=True)
    condition_level: str = Field(max_length=16)
    attrs: dict = Field(default_factory=dict, sa_column=Column(JSON))
    description: str = Field(default="", max_length=2000)
    image_url: str = Field(default="", max_length=512)
    price_suggest_min: Optional[float] = None
    price_suggest_max: Optional[float] = None
    price: float = Field(default=0.0)
    status: str = Field(default="pending", index=True)
    # pending/on_sale/locked/dealed/draft/rejected/frozen/off_shelf
    lock_version: int = 0
    reject_count: int = 0
    audit_reason: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class Negotiation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id", index=True)
    buyer_id: int = Field(foreign_key="user.id")
    seller_id: int = Field(foreign_key="user.id")
    buyer_reserve: float
    seller_reserve: float
    nash_price: Optional[float] = None
    max_rounds: int = 5
    deadline_seconds: int = 120
    status: str = Field(default="ongoing", index=True)  # ongoing/deal/terminated
    deal_price: Optional[float] = None
    graph_thread_id: Optional[str] = Field(default=None, max_length=128, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    closed_at: Optional[datetime] = None


class Offer(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("negotiation_id", "round", "from_role", name="uq_offer_seq"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    negotiation_id: int = Field(foreign_key="negotiation.id", index=True)
    round: int
    from_role: str = Field(max_length=16)  # buyer/seller/agent
    price: float
    basis: str = Field(default="", max_length=512)
    created_at: datetime = Field(default_factory=utcnow)


class NegotiationMessage(SQLModel, table=True):
    """议价室自由文本消息（FR-202）：chat=用户/AI 对话，system=成交/出价等居中提示。"""

    id: Optional[int] = Field(default=None, primary_key=True)
    negotiation_id: int = Field(foreign_key="negotiation.id", index=True)
    from_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    kind: str = Field(default="chat", max_length=16)  # chat/system
    content: str = Field(max_length=500)
    created_at: datetime = Field(default_factory=utcnow)


class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_no: str = Field(index=True, unique=True, max_length=40)
    item_id: int = Field(foreign_key="item.id", index=True)
    negotiation_id: Optional[int] = Field(default=None, foreign_key="negotiation.id")
    buyer_id: int = Field(foreign_key="user.id")
    seller_id: int = Field(foreign_key="user.id")
    deal_price: float
    status: str = Field(default="created", index=True)
    # created/unpaid/paid/receiving/completed/appealing/refunded/canceled/reviewed
    lock_token: Optional[str] = Field(default=None, max_length=64)
    pay_deadline: Optional[datetime] = None
    graph_thread_id: Optional[str] = Field(default=None, max_length=128, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Review(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("order_id", "from_user_id", "to_user_id", name="uq_review_once"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    from_user_id: int = Field(foreign_key="user.id")
    to_user_id: int = Field(foreign_key="user.id")
    score: int  # 1-5
    content: str = Field(default="", max_length=500)
    created_at: datetime = Field(default_factory=utcnow)


class Appeal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    appellant_id: int = Field(foreign_key="user.id")
    reason: str = Field(max_length=1000)
    evidence: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="pending", index=True)  # pending/ruled/closed
    ruling: Optional[str] = Field(default=None, max_length=16)  # uphold/refund
    ruling_basis: str = Field(default="", max_length=1000)
    judged_by: Optional[str] = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=utcnow)
    ruled_at: Optional[datetime] = None


class AclMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: str = Field(index=True, max_length=80)
    performative: str = Field(max_length=16, index=True)
    sender: str = Field(max_length=32, index=True)
    receiver: str = Field(max_length=32, index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    confidence: float = 1.0
    timeout: Optional[int] = None
    error_code: Optional[str] = Field(default=None, max_length=32)
    graph_thread_id: Optional[str] = Field(default=None, max_length=128, index=True)
    timestamp: str = Field(default="", max_length=40)  # FR-11 ACL 时间戳（UTC ISO）
    created_at: datetime = Field(default_factory=utcnow)


class ConflictEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scene: str = Field(max_length=8, index=True)  # C1/C2/C6/C8/other
    type: str = Field(max_length=16)  # resource/opinion/safety/goal
    level: int = 1
    participants: list = Field(default_factory=list, sa_column=Column(JSON))
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    result: str = Field(default="", max_length=128)
    graph_thread_id: Optional[str] = Field(default=None, max_length=128, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class AgentStatus(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, max_length=32)
    display_name: str = Field(max_length=64)
    avatar: str = Field(default="Bot", max_length=32)
    capabilities: list = Field(default_factory=list, sa_column=Column(JSON))
    description: str = Field(default="", max_length=512)
    runtime_status: str = Field(default="running", max_length=16)  # running/paused/error
    llm_mode: str = Field(default="rule", max_length=8)  # llm/rule
    accent: str = Field(default="#6366F1", max_length=16)
    msg_handled: int = 0
    tasks_handled: int = 0
    last_active_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=utcnow)


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_type: str = Field(max_length=16)  # user/admin/agent
    actor_id: str = Field(max_length=64)
    action: str = Field(max_length=64, index=True)
    target_type: str = Field(default="", max_length=32)
    target_id: Optional[str] = Field(default=None, max_length=64)
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    graph_thread_id: Optional[str] = Field(default=None, max_length=128, index=True)
    created_at: datetime = Field(default_factory=utcnow)
