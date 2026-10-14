"""流程实例索引辅助：从审计日志聚合等待人工的实例。"""
from __future__ import annotations

from sqlmodel import Session, select

from app.core.database import engine
from app.graph.runner import runner
from app.models import AuditLog


def list_waiting_human(flow: str | None = None) -> list[dict]:
    """返回当前真正挂起等待人工的流程实例（含 interrupt payload）。"""
    with Session(engine) as session:
        stmt = select(AuditLog).where(AuditLog.action == "flow_start")
        rows = session.exec(stmt.order_by(AuditLog.id.desc())).all()

    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        tid = row.graph_thread_id
        if not tid or tid in seen:
            continue
        detail = row.detail or {}
        if flow and detail.get("flow") != flow:
            continue
        try:
            snap = runner.get_state(tid)
        except KeyError:
            continue
        if snap["status"] != "waiting":
            continue
        seen.add(tid)
        out.append({
            "thread_id": tid,
            "flow": detail.get("flow"),
            "business": detail.get("business", {}),
            "pending_human": snap["pending_human"],
            "created_at": row.created_at.isoformat(),
        })
    return out
