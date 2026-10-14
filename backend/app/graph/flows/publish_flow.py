"""发布审核流：结构化 → 审核 →（通过/驳回/人工复核/veto 人工门）。"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlmodel import Session

from app.core.database import engine
from app.graph.checkpoint import get_checkpointer
from app.graph.gates import human_gate
from app.graph.traced import traced
from app.kernel.blackboard import BlackboardState
from app.kernel.dispatch import call_agent, is_paused_reply
from app.kernel.observe import audit, record_conflict
from app.models import Item


@traced("goods_structure")
def node_structure(state: dict[str, Any]) -> dict[str, Any]:
    item_id = state.get("item_id")
    tid = state["thread_id"]
    body = state.get("input", {})
    if not item_id:
        reply = call_agent(
            "commodity", f"publish-{state['user_id']}",
            {"action": "structure", "seller_id": state["user_id"],
             "title": body.get("title"), "description": body.get("description", ""),
             "price": body.get("price"), "image_url": body.get("image_url", ""),
             "thread_id": tid},
            summary="请求结构化新商品", thread_id=tid,
        )
        data = reply.payload
        if is_paused_reply(reply):
            return {"stage": "agent_paused",
                    "decisions": [{"node": "goods_structure", "result": "agent_paused",
                                   "error": data.get("error")}]}
        item_id = data["item_id"]
        # 仅"描述过短"视为严重缺失并退回；类目识别失败等提示不阻断（防止违禁品逃逸审核）
        serious_missing = [m for m in data.get("missing", []) if "过短" in m]
        if serious_missing:
            with Session(engine) as session:
                item = session.get(Item, item_id)
                item.status = "draft"
                session.commit()
            return {"stage": "need_info", "item_id": item_id,
                    "decisions": [{"node": "structure", "result": "need_info", "missing": serious_missing}]}
        return {"stage": "structured", "item_id": item_id,
                "decisions": [{"node": "structure", "result": "ok", "data": data}]}
    return {"stage": "structured", "item_id": item_id}


@traced("goods_moderate")
def node_moderate(state: dict[str, Any]) -> dict[str, Any]:
    tid = state["thread_id"]
    reply = call_agent(
        "moderation", f"publish-{state['item_id']}",
        {"action": "moderate", "item_id": state["item_id"], "thread_id": tid},
        summary="请求审核商品", thread_id=tid,
    )
    data = reply.payload
    if is_paused_reply(reply):
        return {"stage": "agent_paused",
                "decisions": [{"node": "goods_moderate", "result": "agent_paused",
                               "error": data.get("error")}]}
    return {"stage": "moderated", "item_id": state["item_id"],
            "item": {"id": state["item_id"], **data},
            "decisions": [{"node": "moderate", "result": data["decision"],
                           "confidence": data["confidence"], "reasons": data["reasons"]}]}


def route_moderate(state: dict[str, Any]) -> str:
    if state.get("stage") == "agent_paused":
        return "paused"
    decision = state.get("item", {}).get("decision")
    return {"approve": "end", "reject": "end", "manual": "gate_review",
            "veto": "gate_veto"}.get(decision, "end")


@traced("human_review_gate")
def node_gate_review(state: dict[str, Any]) -> dict[str, Any]:
    item = state.get("item", {})
    # C3 三级人工门：经 arbitrator 规则复核升级的商品，在挂起前记录 level=3 事件（仅一次）
    with Session(engine) as session:
        row = session.get(Item, item.get("id"))
        if row is not None and (row.attrs or {}).get("c3_escalated") \
                and not (row.attrs or {}).get("c3_gate_recorded"):
            record_conflict(
                scene="C3", ctype="rule", level=3,
                participants=["arbitrator", "moderation", "admin"],
                payload={"item_id": row.id, "stage": "human_gate",
                         "action": "appeal_human_gate"},
                result="卖家不服驳回经一级协商、二级规则复核后升级三级人工终裁",
                graph_thread_id=state["thread_id"], session=session,
            )
            row.attrs = {**(row.attrs or {}), "c3_gate_recorded": True}
            session.commit()
    decision = human_gate(
        state, "human_review_gate", "item_review",
        "商品审核存疑，等待人工复核",
        {"item_id": item.get("id"), "reasons": item.get("reasons", []),
         "confidence": item.get("confidence")},
    )
    action = decision.get("action", "reject")
    basis = decision.get("basis", "人工复核")
    with Session(engine) as session:
        row = session.get(Item, item["id"])
        row.status = "on_sale" if action == "approve" else "rejected"
        row.audit_reason = row.audit_reason + [{"rule": "human_review", "detail": basis}]
        if action != "approve":
            row.reject_count += 1
        session.commit()
    audit(actor_type="admin", actor_id=str(decision.get("admin_id", "admin")),
          action="admin_review", target_type="item", target_id=item["id"],
          detail={"action": action, "basis": basis}, graph_thread_id=state["thread_id"])
    return {"stage": "human_reviewed",
            "human_decision": decision,
            "decisions": [{"node": "human_review", "result": action, "basis": basis}]}


@traced("veto_gate")
def node_gate_veto(state: dict[str, Any]) -> dict[str, Any]:
    item = state.get("item", {})
    decision = human_gate(
        state, "veto_gate", "veto_review",
        "安全否决：商品已冻结，仅可在证据推翻违禁判定时解除冻结",
        {"item_id": item.get("id"), "reasons": item.get("reasons", [])},
    )
    action = decision.get("action", "maintain")  # maintain / unfreeze
    basis = decision.get("basis", "")
    with Session(engine) as session:
        row = session.get(Item, item["id"])
        if action == "unfreeze" and basis:
            row.status = "on_sale"
        else:
            row.status = "frozen"
        row.audit_reason = row.audit_reason + [
            {"rule": "human_veto_review", "detail": f"{'解除冻结' if action == 'unfreeze' and basis else '维持冻结'}：{basis}"}]
        session.commit()
    audit(actor_type="admin", actor_id=str(decision.get("admin_id", "admin")),
          action="admin_veto_review", target_type="item", target_id=item["id"],
          detail={"action": action, "basis": basis}, graph_thread_id=state["thread_id"])
    return {"stage": "veto_reviewed", "human_decision": decision,
            "decisions": [{"node": "veto_gate", "result": action}]}


def build():
    b = StateGraph(BlackboardState)
    b.add_node("goods_structure", node_structure)
    b.add_node("goods_moderate", node_moderate)
    b.add_node("human_review_gate", node_gate_review)
    b.add_node("veto_gate", node_gate_veto)
    b.add_edge(START, "goods_structure")
    b.add_conditional_edges(
        "goods_structure",
        lambda s: "moderate" if s.get("stage") == "structured" else "end",
        {"moderate": "goods_moderate", "end": END},
    )
    b.add_conditional_edges("goods_moderate", route_moderate,
                            {"end": END, "gate_review": "human_review_gate",
                             "gate_veto": "veto_gate", "need_info": END,
                             "paused": END})
    b.add_edge("human_review_gate", END)
    b.add_edge("veto_gate", END)
    return b.compile(checkpointer=get_checkpointer())
