"""流程运行器：多流图注册、启动、interrupt 挂起/恢复、状态查询。"""
from __future__ import annotations

import uuid
from typing import Any, Callable

from langgraph.types import Command

from app.kernel.blackboard import new_state
from app.kernel.observe import audit


class GraphRunner:
    def __init__(self) -> None:
        self._builders: dict[str, Callable] = {}
        self._graphs: dict[str, Any] = {}
        self._thread_flow: dict[str, str] = {}

    def _resolve_flow(self, thread_id: str) -> str:
        """thread_id → flow：内存缓存 + AuditLog 持久化回查。"""
        flow = self._thread_flow.get(thread_id)
        if flow:
            return flow
        from sqlmodel import Session, select

        from app.core.database import engine
        from app.models import AuditLog

        with Session(engine) as session:
            row = session.exec(
                select(AuditLog)
                .where(AuditLog.graph_thread_id == thread_id, AuditLog.action == "flow_start")
                .order_by(AuditLog.id.desc())
            ).first()
        if not row:
            raise KeyError(f"找不到流程实例：{thread_id}")
        flow = (row.detail or {}).get("flow")
        if not flow:
            raise KeyError(f"流程实例缺少 flow 标记：{thread_id}")
        self._thread_flow[thread_id] = flow
        return flow

    def register(self, flow: str, builder: Callable) -> None:
        self._builders[flow] = builder

    def _graph(self, flow: str):
        if flow not in self._graphs:
            if flow not in self._builders:
                raise KeyError(f"未注册的流程：{flow}")
            self._graphs[flow] = self._builders[flow]()
        return self._graphs[flow]

    def start(self, flow: str, *, user_id: int, **context: Any) -> dict[str, Any]:
        thread_id = context.pop("thread_id", None) or f"{flow}-{uuid.uuid4().hex[:10]}"
        self._thread_flow[thread_id] = flow
        # 业务主键提顶层（图/条件边可读），其余全部进入 input（防止被 TypedDict 过滤）
        top_level = {"item_id", "negotiation_id", "order_id", "appeal_id"}
        tops = {k: context.pop(k) for k in list(context) if k in top_level and context[k] is not None}
        state = new_state(flow, user_id, thread_id=thread_id, input=context, **tops)
        cfg = {"configurable": {"thread_id": thread_id}}
        graph = self._graph(flow)
        values = graph.invoke(state, config=cfg)
        snap = graph.get_state(cfg)
        interrupted = bool(snap.next)
        pending = (snap.tasks[0].interrupts[0].value
                   if interrupted and snap.tasks and snap.tasks[0].interrupts else None)
        audit(
            actor_type="agent", actor_id="coordinator", action="flow_start",
            target_type="flow", target_id=thread_id,
            detail={"flow": flow, "user_id": user_id, "status": "waiting" if interrupted else "done",
                    "business": {k: values.get(k) for k in ("item_id", "negotiation_id", "order_id", "appeal_id")}},
            graph_thread_id=thread_id,
        )
        return {
            "thread_id": thread_id,
            "status": "waiting" if interrupted else "done",
            "next": list(snap.next),
            "pending_human": pending,
            "state": values,
        }

    def resume(self, thread_id: str, decision: dict[str, Any]) -> dict[str, Any]:
        flow = self._resolve_flow(thread_id)
        graph = self._graph(flow)
        values = graph.invoke(Command(resume=decision),
                              config={"configurable": {"thread_id": thread_id}})
        snap = graph.get_state({"configurable": {"thread_id": thread_id}})
        interrupted = bool(snap.next)
        audit(
            actor_type="admin", actor_id=str(decision.get("admin_id", "admin")),
            action="flow_resume", target_type="flow", target_id=thread_id,
            detail={"flow": flow, "decision": {k: v for k, v in decision.items() if k != "admin_id"},
                    "status": "waiting" if interrupted else "done"},
            graph_thread_id=thread_id,
        )
        return {
            "thread_id": thread_id,
            "status": "waiting" if interrupted else "done",
            "next": list(snap.next),
            "state": values,
        }

    def get_state(self, thread_id: str) -> dict[str, Any]:
        flow = self._resolve_flow(thread_id)
        snap = self._graph(flow).get_state({"configurable": {"thread_id": thread_id}})
        if not snap.values:
            raise KeyError(f"找不到流程实例：{thread_id}")
        pending = None
        if snap.next and snap.tasks and snap.tasks[0].interrupts:
            pending = snap.tasks[0].interrupts[0].value
        return {
            "thread_id": thread_id,
            "flow": snap.values.get("flow"),
            "status": "waiting" if snap.next else "done",
            "next": list(snap.next),
            "pending_human": pending,
            "state": _jsonable(snap.values),
        }


def _jsonable(obj: Any) -> Any:
    import json
    return json.loads(json.dumps(obj, default=str, ensure_ascii=False))


runner = GraphRunner()
