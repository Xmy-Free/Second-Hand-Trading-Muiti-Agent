"""交易支付流：建单预占锁 → 风险意见 → 加权投票/人工 → 等待支付（interrupt）→ 支付/取消。"""
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
from app.models import Order


@traced("order_lock")
def node_lock(state: dict[str, Any]) -> dict[str, Any]:
    tid = state["thread_id"]
    neg_id = state.get("negotiation_id") or state.get("input", {}).get("negotiation_id")
    reply = call_agent(
        "order", f"trade-{neg_id}",
        {"action": "create_order", "negotiation_id": neg_id, "thread_id": tid},
        summary="成交：申请预占锁并建单", thread_id=tid,
    )
    data = reply.payload
    if not data.get("ok"):
        return {
            "stage": "lock_conflict",
            "order": data,
            "decisions": [
                {
                    "node": "order_lock",
                    "result": "conflict",
                    "conflict": data.get("conflict"),
                    "error": data.get("error"),
                }
            ],
        }
    return {
        "stage": "locked",
        "order_id": data["order_id"],
        "order": data,
        "decisions": [
            {
                "node": "order_lock",
                "result": "locked",
                "order_id": data["order_id"],
            }
        ],
    }


def route_lock(state: dict[str, Any]) -> str:
    return "risk" if state.get("stage") == "locked" else "end"


@traced("risk_check")
def node_risk(state: dict[str, Any]) -> dict[str, Any]:
    tid = state["thread_id"]
    reply = call_agent(
        "credit", f"risk-{state['order_id']}",
        {"action": "risk_check", "order_id": state["order_id"], "thread_id": tid},
        summary="支付前买家信用风险评估", thread_id=tid, perf="arbitrate",
    )
    opinion = reply.payload
    return {"stage": "risk_checked", "risk_opinion": opinion,
            "decisions": [{"node": "risk_check", "result": opinion.get("risk_level"),
                           "confidence": opinion.get("confidence"), "basis": opinion.get("basis")}]}


def route_risk(state: dict[str, Any]) -> str:
    opinion = state.get("risk_opinion", {})
    if opinion.get("risk_level") == "high" and opinion.get("confidence", 0) >= 0.6:
        return "vote"
    return "wait_pay"


@traced("weighted_vote")
def node_vote(state: dict[str, Any]) -> dict[str, Any]:
    tid = state["thread_id"]
    try:
        reply = call_agent(
            "coordinator", f"vote-{state['order_id']}",
            {"action": "risk_vote", "order_id": state["order_id"],
             "risk_opinion": state.get("risk_opinion"), "thread_id": tid},
            summary="意见冲突：三方加权投票仲裁", thread_id=tid, perf="arbitrate",
        )
        vote = reply.payload
    except Exception as exc:  # noqa: BLE001 - 协调者未就绪时兜底放行
        vote = {"decision": "allow", "score": 0.6, "details": [],
                "note": f"coordinator unavailable: {type(exc).__name__}"}
    decision = vote.get("decision", "allow")
    if decision == "allow":
        stage = "vote_allowed"
    elif decision == "block":
        stage = "vote_blocked"
    else:
        stage = "vote_manual"
    return {"stage": stage, "vote": vote,
            "decisions": [{"node": "weighted_vote", "result": decision,
                           "score": vote.get("score"), "details": vote.get("details", [])}]}


def route_vote(state: dict[str, Any]) -> str:
    return {"vote_allowed": "wait_pay", "vote_blocked": "cancel",
            "vote_manual": "risk_gate"}.get(state.get("stage", ""), "wait_pay")


@traced("risk_human_gate")
def node_risk_gate(state: dict[str, Any]) -> dict[str, Any]:
    decision = human_gate(
        state, "risk_human_gate", "risk_final",
        "信用风险意见分歧，暂缓支付，等待人工终裁",
        {"order_id": state.get("order_id"), "risk_opinion": state.get("risk_opinion"),
         "vote": state.get("vote")},
    )
    if decision.get("action") == "approve":
        return {"stage": "human_allowed", "human_decision": decision,
                "decisions": [{"node": "risk_human_gate", "result": "approve"}]}
    return {"stage": "human_blocked", "human_decision": decision,
            "decisions": [{"node": "risk_human_gate", "result": "reject"}]}


def route_human(state: dict[str, Any]) -> str:
    return "wait_pay" if state.get("stage") == "human_allowed" else "cancel"


@traced("cancel_order")
def node_cancel(state: dict[str, Any]) -> dict[str, Any]:
    tid = state["thread_id"]
    reason = "风险投票拦截，订单取消并释放锁" if state.get("stage") in (
        "vote_blocked", "human_blocked") else "订单取消"
    call_agent(
        "order", f"cancel-{state['order_id']}",
        {"action": "cancel", "order_id": state["order_id"], "reason": reason, "thread_id": tid},
        summary=reason, thread_id=tid,
    )
    audit("agent", "coordinator", "trade_canceled", "order", state.get("order_id"),
          {"reason": reason, "vote": state.get("vote")}, tid)
    return {"stage": "canceled",
            "decisions": [{"node": "cancel_order", "result": "canceled", "reason": reason}]}


@traced("wait_payment_gate")
def node_wait_pay(state: dict[str, Any]) -> dict[str, Any]:
    order_id = state["order_id"]
    with Session(engine) as session:
        order = session.get(Order, order_id)
        amount = order.deal_price if order else 0
        deadline = order.pay_deadline.isoformat() if order and order.pay_deadline else None
    decision = human_gate(
        state, "wait_payment_gate", "wait_pay",
        f"订单已锁定，请在支付时限内完成沙箱支付（¥{amount:g}）",
        {"order_id": order_id, "amount": amount, "pay_deadline": deadline,
         "risk_opinion": state.get("risk_opinion")},
    )
    return {"stage": "pay_decided", "human_decision": decision,
            "decisions": [{"node": "wait_payment_gate", "result": decision.get("action")}]}


def route_pay_decision(state: dict[str, Any]) -> str:
    return "pay" if state.get("human_decision", {}).get("action") == "pay" else "cancel"


@traced("sandbox_pay")
def node_pay(state: dict[str, Any]) -> dict[str, Any]:
    tid = state["thread_id"]
    reply = call_agent(
        "order", f"pay-{state['order_id']}",
        {"action": "pay", "order_id": state["order_id"], "thread_id": tid,
         "user_id": state["user_id"]},
        summary="沙箱模拟支付", thread_id=tid,
    )
    data = reply.payload
    if data.get("ok"):
        return {"stage": "paid",
                "decisions": [{"node": "sandbox_pay", "result": "paid"}]}
    # 支付失败/超时
    if data.get("status") == "canceled":
        return {"stage": "pay_expired",
                "decisions": [{"node": "sandbox_pay", "result": "expired"}]}
    return {"stage": "pay_failed",
            "decisions": [{"node": "sandbox_pay", "result": "failed", "error": data.get("error")}]}


def build():
    b = StateGraph(BlackboardState)
    b.add_node("order_lock", node_lock)
    b.add_node("risk_check", node_risk)
    b.add_node("weighted_vote", node_vote)
    b.add_node("risk_human_gate", node_risk_gate)
    b.add_node("wait_payment_gate", node_wait_pay)
    b.add_node("cancel_order", node_cancel)
    b.add_node("sandbox_pay", node_pay)

    b.add_edge(START, "order_lock")
    b.add_conditional_edges("order_lock", route_lock, {"risk": "risk_check", "end": END})
    b.add_conditional_edges("risk_check", route_risk, {"vote": "weighted_vote", "wait_pay": "wait_payment_gate"})
    b.add_conditional_edges("weighted_vote", route_vote,
                            {"wait_pay": "wait_payment_gate", "cancel": "cancel_order",
                             "risk_gate": "risk_human_gate"})
    b.add_conditional_edges("risk_human_gate", route_human,
                            {"wait_pay": "wait_payment_gate", "cancel": "cancel_order"})
    b.add_conditional_edges("wait_payment_gate", route_pay_decision,
                            {"pay": "sandbox_pay", "cancel": "cancel_order"})
    b.add_edge("sandbox_pay", END)
    b.add_edge("cancel_order", END)
    return b.compile(checkpointer=get_checkpointer())
