"""节点轨迹装饰器：进入/退出自动发射 node_trace 事件。"""
from __future__ import annotations

import functools
from typing import Any, Callable

from app.kernel.observe import emit_node


def traced(node: str) -> Callable:
    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(state: dict[str, Any]) -> dict[str, Any]:
            thread_id = state.get("thread_id", "unknown")
            flow = state.get("flow", "unknown")
            emit_node(thread_id=thread_id, flow=flow, node=node, status="enter",
                      summary=f"进入节点：{node}")
            try:
                result = fn(state) or {}
            except Exception as exc:
                emit_node(thread_id=thread_id, flow=flow, node=node, status="error",
                          summary=f"节点异常：{exc}")
                raise
            patch = result if isinstance(result, dict) else {}
            emit_node(thread_id=thread_id, flow=flow, node=node, status="exit",
                      summary=str(patch.get("stage") or node),
                      io={"out_keys": list(patch.keys())})
            return result

        return wrapper

    return deco
