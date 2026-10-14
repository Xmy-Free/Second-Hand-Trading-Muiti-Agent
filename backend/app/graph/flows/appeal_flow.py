"""申诉流：证据汇总 → 规则裁决（小额直裁 / 否则人工 interrupt）→ 执行裁决。"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlmodel import Session

from app.core.database import engine
from app.graph.checkpoint import get_checkpointer
from app.graph.gates import human_gate
from app.graph.traced import traced
from app.kernel.blackboard import BlackboardState
from app.kernel.dispatch import call_agent
from app.kernel.observe import audit
from app.models import Appeal, Order


@traced("appeal_evidence")
def node_evidence(state: dict[str, Any]) -> dict[str, Any]:
    tid = state["thread_id"]
    appeal_id = state.get("appeal_id")
    # 订单进入申诉中
    with Session(engine) as session:
        appeal = session.get(Appeal, appeal_id)
        order_id = appeal.order_id if appeal else state.get("order_id")
    call_agent(
        "order", f"appeal-mark-{appeal_id}",
        {"action": "mark_appealing", "order_id": order_id,
         "user_id": state["user_id"], "reason": appeal.reason if appeal else "",
         "thread_id": tid},
        summary="订单进入申诉状态", thread_id=tid,
    )
    reply = call_agent(
        "arbitrator", f"evidence-{appeal_id}",
        {"action": "build_evidence", "appeal_id": appeal_id, "thread_id": tid},
        summary="仲裁 Agent 汇总纠纷证据包", thread_id=tid, perf="arbitrate",
    )
    evidence = reply.payload
    with Session(engine) as session:
        appeal = session.get(Appeal, appeal_id)
        if appeal:
            appeal.evidence = evidence
            session.commit()
    return {"stage": "evidence_ready", "order_id": order_id,
            "decisions": [{"node": "appeal_evidence", "result": "evidence_built"}]}


@traced("appeal_rule")
def node_rule(state: dict[str, Any]) -> dict[str, Any]:
    tid = state["thread_id"]
    reply = call_agent(
        "arbitrator", f"rule-{state['appeal_id']}",
        {"action": "rule_appeal", "appeal_id": state["appeal_id"], "thread_id": tid},
        summary="仲裁 Agent 依据规则库做出裁决建议", thread_id=tid, perf="arbitrate",
    )
    ruling = reply.payload
    return {"stage": "rule_ruled", "vote": ruling,
            "decisions": [{"node": "appeal_rule", "result": ruling.get("suggestion"),
                           "action": ruling.get("action"),
                           "responsibility": ruling.get("responsibility"),
                           "direct": ruling.get("direct"), "basis": ruling.get("basis", [])}]}


def route_rule(state: dict[str, Any]) -> str:
    return "apply" if state.get("vote", {}).get("direct") else "gate"


@traced("appeal_human_gate")
def node_gate(state: dict[str, Any]) -> dict[str, Any]:
    decision = human_gate(
        state, "appeal_human_gate", "appeal_final",
        "纠纷需人工终裁：请查看证据包后作出维持/退款裁决",
        {"appeal_id": state.get("appeal_id"), "order_id": state.get("order_id"),
         "rule_suggestion": state.get("vote")},
    )
    return {"stage": "human_ruled", "human_decision": decision,
            "decisions": [{"node": "appeal_human_gate", "result": decision.get("action"),
                           "basis": decision.get("basis")}]}


@traced("apply_ruling")
def node_apply(state: dict[str, Any]) -> dict[str, Any]:
    tid = state["thread_id"]
    if state.get("vote", {}).get("direct"):
        ruling = state["vote"]["suggestion"]
        basis = "；".join(state["vote"].get("basis", []))
        judged_by = "coordinator"
    else:
        d = state.get("human_decision", {})
        ruling = d.get("action", "uphold")
        basis = d.get("basis", "人工终裁")
        judged_by = d.get("admin_id", "admin")

    with Session(engine) as session:
        order = session.get(Order, state["order_id"])
        faulty = order.seller_id if ruling == "refund" else None
    reply = call_agent(
        "order", f"apply-ruling-{state['appeal_id']}",
        {"action": "apply_ruling", "order_id": state["order_id"], "ruling": ruling,
         "faulty_user_id": faulty, "judged_by": judged_by, "thread_id": tid},
        summary=f"执行裁决：{'退款' if ruling == 'refund' else '维持交易'}",
        thread_id=tid, perf="arbitrate",
    )
    data = reply.payload
    # 退款裁决联动信用 Agent 扣罚责任方
    if ruling == "refund" and faulty is not None:
        call_agent(
            "credit", f"penalize-{state['appeal_id']}",
            {"action": "penalize", "user_id": faulty, "order_id": state["order_id"],
             "reason": f"申诉 {state['appeal_id']} 裁决退款：{basis}",
             "judged_by": judged_by, "thread_id": tid},
            perf="arbitrate", summary="裁决联动：扣罚责任方信用", thread_id=tid,
        )
    with Session(engine) as session:
        appeal = session.get(Appeal, state["appeal_id"])
        if appeal:
            appeal.status = "ruled"
            appeal.ruling = ruling
            appeal.ruling_basis = basis
            appeal.judged_by = judged_by
            session.commit()
        audit("admin", judged_by, "appeal_judged", "appeal", appeal.id if appeal else None,
              {"ruling": ruling, "basis": basis}, tid, session=session)
        session.commit()
    return {"stage": "ruled",
            "decisions": [{"node": "apply_ruling", "result": ruling,
                           "applied": data.get("status"), "basis": basis}]}


def build():
    b = StateGraph(BlackboardState)
    b.add_node("appeal_evidence", node_evidence)
    b.add_node("appeal_rule", node_rule)
    b.add_node("appeal_human_gate", node_gate)
    b.add_node("apply_ruling", node_apply)
    b.add_edge(START, "appeal_evidence")
    b.add_edge("appeal_evidence", "appeal_rule")
    b.add_conditional_edges("appeal_rule", route_rule, {"apply": "apply_ruling", "gate": "appeal_human_gate"})
    b.add_edge("appeal_human_gate", "apply_ruling")
    b.add_edge("apply_ruling", END)
    return b.compile(checkpointer=get_checkpointer())
