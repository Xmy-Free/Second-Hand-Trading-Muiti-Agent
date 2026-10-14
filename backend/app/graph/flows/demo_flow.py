"""T6 占位演示流：submit → (auto_end | human → end)。T7 起由真实业务流替换/增补。"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.checkpoint import get_checkpointer
from app.graph.gates import human_gate
from app.graph.traced import traced
from app.kernel.blackboard import BlackboardState


@traced("demo_submit")
def submit(state: dict) -> dict:
    return {"stage": "audit", "decisions": [{"node": "submit", "result": "received"}]}


@traced("demo_human_gate")
def gate(state: dict) -> dict:
    decision = human_gate(
        state, "demo_human_gate", "demo",
        "T6 占位人工节点：请选择通过或驳回",
        {"item_title": state.get("item", {}).get("title", "演示商品")},
    )
    return {"stage": "human_done", "human_decision": decision,
            "decisions": [{"node": "human", "result": decision.get("action")}]}


def route(state: dict) -> str:
    return "human" if state.get("need_human") else "end"


def build():
    b = StateGraph(BlackboardState)
    b.add_node("demo_submit", submit)
    b.add_node("demo_human_gate", gate)
    b.add_edge(START, "demo_submit")
    b.add_conditional_edges("demo_submit", route, {"human": "demo_human_gate", "end": END})
    b.add_edge("demo_human_gate", END)
    return b.compile(checkpointer=get_checkpointer())
