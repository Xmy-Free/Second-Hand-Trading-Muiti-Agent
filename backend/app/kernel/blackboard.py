"""全局状态黑板：LangGraph 类型化 State（SSOT）。"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class BlackboardState(TypedDict, total=False):
    # 上下文
    flow: str                     # publish / search / negotiate / trade / appeal
    action: str
    user_id: int
    item_id: int
    negotiation_id: int
    order_id: int
    appeal_id: int
    thread_id: str

    # 流程控制
    stage: str
    need_human: bool
    human_payload: dict[str, Any]
    human_decision: dict[str, Any]

    # 数据载体
    input: dict[str, Any]        # 业务输入（标题/描述/价格等未建模字段统一放这里）
    item: dict[str, Any]
    negotiation: dict[str, Any]
    order: dict[str, Any]
    risk_opinion: dict[str, Any]
    vote: dict[str, Any]

    # 累积轨迹（reducer：自动拼接）
    decisions: Annotated[list[dict[str, Any]], operator.add]
    traces: Annotated[list[dict[str, Any]], operator.add]


def new_state(flow: str, user_id: int, **kw: Any) -> dict:
    return {
        "flow": flow,
        "user_id": user_id,
        "stage": "init",
        "need_human": False,
        "human_payload": {},
        "human_decision": {},
        "decisions": [],
        "traces": [],
        **kw,
    }
