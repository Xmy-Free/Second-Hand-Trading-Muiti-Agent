"""节点轨迹、冲突事件、审计日志的统一记录口（落库 + 实时推送）。"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from app.core.database import engine
from app.kernel.events import bus
from app.models import AuditLog, ConflictEvent

# FR-104：node_trace 进程内环形缓冲（≥100 条），控制台加载即有历史
_TRACE_MAXLEN = 120
_trace_buf: deque[dict[str, Any]] = deque(maxlen=_TRACE_MAXLEN)
_trace_lock = threading.Lock()


def emit_node(*, thread_id: str, flow: str, node: str, status: str,
              summary: str = "", io: dict | None = None) -> None:
    """status: enter / exit / human / error"""
    data = {
        "thread_id": thread_id, "flow": flow, "node": node,
        "status": status, "summary": summary, "io": io or {},
    }
    bus.publish("node_trace", data)
    rec = {**data, "ts": datetime.now(timezone.utc).isoformat()}
    with _trace_lock:
        _trace_buf.append(rec)


def iter_recent_traces(limit: int = 40) -> list[dict[str, Any]]:
    """返回最近的节点轨迹（时间倒序，最新在前）。"""
    limit = max(1, min(int(limit), _TRACE_MAXLEN))
    with _trace_lock:
        return [dict(item) for item in list(_trace_buf)[-limit:]][::-1]


def record_conflict(*, scene: str, ctype: str, level: int,
                    participants: list[str], payload: dict[str, Any],
                    result: str, graph_thread_id: str | None = None,
                    session: Session | None = None) -> dict:
    def _write(s: Session) -> dict:
        row = ConflictEvent(
            scene=scene, type=ctype, level=level, participants=participants,
            payload=payload, result=result, graph_thread_id=graph_thread_id,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return {
            "id": row.id, "scene": row.scene, "type": row.type, "level": row.level,
            "participants": row.participants, "payload": row.payload,
            "result": row.result, "graph_thread_id": row.graph_thread_id,
            "created_at": row.created_at.isoformat(),
        }

    if session is not None:
        # 复用外层事务：先 flush 取 id，不独立 commit
        row = ConflictEvent(
            scene=scene, type=ctype, level=level, participants=participants,
            payload=payload, result=result, graph_thread_id=graph_thread_id,
        )
        session.add(row)
        session.flush()
        out = {
            "id": row.id, "scene": row.scene, "type": row.type, "level": row.level,
            "participants": row.participants, "payload": row.payload,
            "result": row.result, "graph_thread_id": row.graph_thread_id,
            "created_at": row.created_at.isoformat(),
        }
    else:
        with Session(engine) as s:
            out = _write(s)
    bus.publish("conflict", out)
    return out


def audit(actor_type: str = "", actor_id: str | int = "", action: str = "",
          target_type: str = "", target_id: str | int | None = None,
          detail: dict | None = None, graph_thread_id: str | None = None,
          session: Session | None = None) -> None:
    row = AuditLog(
        actor_type=actor_type, actor_id=str(actor_id), action=action,
        target_type=target_type, target_id=str(target_id) if target_id is not None else None,
        detail=detail or {}, graph_thread_id=graph_thread_id,
    )
    if session is not None:
        session.add(row)  # 随外层事务提交
        session.flush()
    else:
        with Session(engine) as s:
            s.add(row)
            s.commit()
