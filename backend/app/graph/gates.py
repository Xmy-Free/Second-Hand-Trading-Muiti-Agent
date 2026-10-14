"""人工介入门：LangGraph interrupt 统一封装。"""
from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.kernel.observe import emit_node


def human_gate(state: dict[str, Any], node: str, kind: str, summary: str,
               payload: dict[str, Any]) -> dict[str, Any]:
    """在节点内调用：挂起流程等待管理员 resume；resume 内容作为返回值。"""
    thread_id = state.get("thread_id", "unknown")
    flow = state.get("flow", "unknown")
    emit_node(thread_id=thread_id, flow=flow, node=node, status="human", summary=summary,
              io={"kind": kind, "payload": payload})
    decision = interrupt({
        "kind": kind,
        "node": node,
        "summary": summary,
        "payload": payload,
        "thread_id": thread_id,
    })
    return decision if isinstance(decision, dict) else {"action": str(decision)}
