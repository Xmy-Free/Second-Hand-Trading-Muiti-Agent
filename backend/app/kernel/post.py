"""ACL 消息出站：校验 → 落库 → 事件总线推送 → 计数。"""
from __future__ import annotations

from sqlmodel import Session

from app.core.database import engine
from app.kernel.acl import AclEnvelope
from app.kernel.events import bus
from app.kernel.registry import registry
from app.models import AclMessage


def _persist(msg: AclEnvelope) -> None:
    with Session(engine) as session:
        session.add(AclMessage(
            conversation_id=msg.conversation_id,
            performative=msg.performative,
            sender=msg.sender,
            receiver=msg.receiver,
            payload=msg.payload,
            confidence=msg.confidence,
            timeout=msg.timeout,
            error_code=msg.error_code,
            graph_thread_id=msg.graph_thread_id,
            timestamp=msg.timestamp,
        ))
        session.commit()


def post_message(msg: AclEnvelope, *, count: bool = True) -> AclEnvelope:
    """唯一合法出站口：Pydantic 已在构造时校验；此处落库并广播。"""
    _persist(msg)
    bus.publish("message", {
        "msg_id": msg.msg_id,
        "conversation_id": msg.conversation_id,
        "performative": msg.performative,
        "sender": msg.sender,
        "receiver": msg.receiver,
        "summary": msg.summary,
        "payload": msg.payload,
        "confidence": msg.confidence,
        "error_code": msg.error_code,
        "graph_thread_id": msg.graph_thread_id,
    })
    if count:
        registry.record_message(msg.sender)
        registry.record_message(msg.receiver)
    return msg
