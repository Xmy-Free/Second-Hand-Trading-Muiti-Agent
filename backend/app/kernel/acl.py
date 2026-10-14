"""FIPA ACL 风格统一消息契约。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Performative(str, Enum):
    REQUEST = "request"
    INFORM = "inform"
    PROPOSE = "propose"
    ACCEPT = "accept"
    REJECT = "reject"
    REFUSE = "refuse"
    ARBITRATE = "arbitrate"
    VETO = "veto"
    INTERRUPT = "interrupt"


Perf = Literal[
    "request", "inform", "propose", "accept", "reject",
    "refuse", "arbitrate", "veto", "interrupt",
]


class AclEnvelope(BaseModel):
    """Agent 间唯一合法通信单元，出站必须经此模型校验。"""

    conversation_id: str = Field(min_length=1, max_length=80)
    performative: Perf
    sender: str = Field(min_length=1, max_length=32)
    receiver: str = Field(min_length=1, max_length=32)
    summary: str = Field(default="", max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    timeout: int | None = None
    error_code: str | None = Field(default=None, max_length=32)
    graph_thread_id: str | None = Field(default=None, max_length=128)
    msg_id: str = Field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:12]}")
    # FR-11：消息时间戳（UTC ISO 字符串，默认创建时刻）
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        min_length=1, max_length=40,
    )

    def reply(self, perf: Perf, payload: dict | None = None, *,
              confidence: float = 1.0, summary: str = "",
              error_code: str | None = None) -> "AclEnvelope":
        return AclEnvelope(
            conversation_id=self.conversation_id,
            performative=perf,
            sender=self.receiver,
            receiver=self.sender,
            summary=summary,
            payload=payload or {},
            confidence=confidence,
            timeout=self.timeout,
            error_code=error_code,
            graph_thread_id=self.graph_thread_id,
        )
