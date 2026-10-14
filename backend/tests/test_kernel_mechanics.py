"""内核机制新增覆盖：FR-11 ACL timestamp、6.3 全局效用快照、8.4 熔断代管、
AC-9 Agent 可插拔、FR-2 用户代理、C7 SSOT 纠正。"""
from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.agents.base import BaseAgent
from app.core import database
from app.kernel.acl import AclEnvelope
from app.kernel.dispatch import call_agent
from app.kernel.post import post_message
from app.kernel.registry import registry
from app.models import AclMessage, ConflictEvent


# ---------------- FR-11 ACL timestamp ----------------
def test_acl_envelope_carries_timestamp() -> None:
    msg = AclEnvelope(conversation_id="ts-contract", performative="inform",
                      sender="a", receiver="b")
    assert isinstance(msg.timestamp, str) and len(msg.timestamp) >= 20
    # reply 生成独立时间戳
    rep = msg.reply("accept", {"ok": True})
    assert isinstance(rep.timestamp, str) and rep.timestamp >= msg.timestamp


def test_acl_timestamp_persisted(app_client) -> None:
    msg = AclEnvelope(conversation_id="ts-persist", performative="inform",
                      sender="coordinator", receiver="credit")
    post_message(msg, count=False)
    with Session(database.engine) as session:
        row = session.exec(
            select(AclMessage).where(AclMessage.conversation_id == "ts-persist")
        ).first()
    assert row is not None and row.timestamp == msg.timestamp


# ---------------- 6.3 全局效用函数（数值快照 + 可复现） ----------------
def test_utility_score_numeric_snapshot(app_client) -> None:
    r1 = call_agent("coordinator", "util-snap-1", {
        "action": "utility_score",
        "satisfaction": 0.6, "success": 0.8, "safety": 1.0,
        "fairness": 0.5, "cost": 0.2,
    })
    # 0.25*0.6 + 0.20*0.8 + 0.30*1.0 + 0.15*0.5 - 0.10*0.2 = 0.665
    assert r1.payload["u"] == 0.665
    assert r1.payload["contributions"]["safety"] == 0.3

    r2 = call_agent("coordinator", "util-snap-2", {
        "action": "utility_score",
        "satisfaction": 1.0, "success": 1.0, "safety": 1.0,
        "fairness": 1.0, "cost": 1.0,
    })
    # 0.25+0.20+0.30+0.15-0.10 = 0.80
    assert r2.payload["u"] == 0.8

    # 同输入同输出（可复现）
    r3 = call_agent("coordinator", "util-snap-3", {
        "action": "utility_score",
        "satisfaction": 0.6, "success": 0.8, "safety": 1.0,
        "fairness": 0.5, "cost": 0.2,
    })
    assert r3.payload["u"] == r1.payload["u"]


def test_utility_score_rejects_out_of_range(app_client) -> None:
    r = call_agent("coordinator", "util-bad", {
        "action": "utility_score",
        "satisfaction": 1.5, "success": 0.8, "safety": 1.0,
        "fairness": 0.5, "cost": 0.2,
    })
    assert r.payload.get("ok") is False


# ---------------- 8.4 熔断代管 ----------------
class _ExplodingAgent(BaseAgent):
    name = "breaker_probe"
    display_name = "熔断探针"
    capabilities = ["probe"]
    description = "每次处理都抛异常的测试探针"

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        raise RuntimeError("boom")


def test_breaker_trips_after_three_failures_and_resume(app_client) -> None:
    registry.register(_ExplodingAgent())
    r1 = call_agent("breaker_probe", "bp-1", {"action": "ping"})
    assert r1.error_code == "AGENT_FAILED"
    assert r1.payload.get("breaker_takeover") is True
    assert r1.payload.get("tripped") is False

    call_agent("breaker_probe", "bp-2", {"action": "ping"})
    r3 = call_agent("breaker_probe", "bp-3", {"action": "ping"})
    assert r3.payload.get("tripped") is True
    assert registry.is_paused("breaker_probe")

    # 第四次：已熔断 → 标准暂停 refuse，不再调 handle
    r4 = call_agent("breaker_probe", "bp-4", {"action": "ping"})
    assert r4.error_code == "AGENT_PAUSED"

    with Session(database.engine) as session:
        events = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "SYS")).all()
    assert len(events) == 1
    assert (events[0].payload or {}).get("action") == "breaker_takeover"

    # 管理员 resume 可恢复（计数清零）
    registry.resume("breaker_probe")
    assert registry.is_paused("breaker_probe") is False
    assert registry.is_tripped("breaker_probe") is False


# ---------------- AC-9 可插拔：新 Agent 不改协调者核心即可被编排调用 ----------------
class _PluggableAgent(BaseAgent):
    name = "demo_pluggable"
    display_name = "可插拔示例"
    capabilities = ["echo"]
    description = "测试用可插拔 Agent"

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        return msg.reply("inform", {"echo": msg.payload.get("text")})


def test_new_agent_pluggable_with_dispatch(app_client) -> None:
    agent = _PluggableAgent()
    registry.register(agent)
    assert registry.get("demo_pluggable") is agent
    r = call_agent("demo_pluggable", "plug-1", {"action": "echo", "text": "hello-ac9"})
    assert r.payload["echo"] == "hello-ac9"
    assert r.sender == "demo_pluggable" and r.receiver == "coordinator"


# ---------------- FR-2 用户代理 Agent ----------------
def test_user_agent_parse_intent_and_clarify(app_client) -> None:
    r = call_agent("user_agent", "intent-1",
                   {"action": "parse_intent", "user_id": 99001,
                    "text": "帮我找一本20元以内的高数教材"})
    assert r.payload["intent"] == "search"
    assert r.payload["buyer_reserve"] == 20.0
    assert r.payload["first_offer"] == 16.0
    assert r.payload["clarify_questions"] == []

    r2 = call_agent("user_agent", "intent-2",
                    {"action": "parse_intent", "user_id": 99002, "text": "你好呀"})
    assert r2.payload["intent"] == "clarify"
    assert len(r2.payload["clarify_questions"]) >= 1


def test_user_agent_auto_bid_respects_authorization_and_deal_confirm(
        app_client, login_factory) -> None:
    buyer = login_factory("20240004")
    seller = login_factory("20240001")
    start = app_client.post("/api/negotiations", headers=buyer,
                            json={"item_id": 1, "buyer_reserve": 18})
    nid = start.json()["data"]["id"]

    # 无卖家要价：授权区间内自动出价（首价 14.4 → 16.2），无需确认
    r1 = call_agent("user_agent", f"auto-bid-{nid}",
                    {"action": "auto_bid", "negotiation_id": nid, "authorized_max": 18})
    assert r1.payload["need_confirm"] is False
    assert r1.payload["bid"] == 16.2

    # 卖家让价至 15 → 下一出价即成交：成交前必须 need_confirm
    app_client.post(f"/api/negotiations/{nid}/offers", headers=seller,
                    json={"price": 15, "confirm": True})
    r2 = call_agent("user_agent", f"auto-bid-{nid}-deal",
                    {"action": "auto_bid", "negotiation_id": nid, "authorized_max": 18})
    assert r2.payload["need_confirm"] is True
    assert r2.payload["bid"] == 15


# ---------------- C7 SSOT 纠正（内核直调） ----------------
def test_ssot_reconcile_corrects_and_records_source(app_client) -> None:
    r = call_agent("coordinator", "ssot-pytest", {
        "action": "ssot_reconcile", "entity_type": "item", "entity_id": 1,
        "source": "search", "private_view": {"id": 1, "status": "locked"},
    }, perf="arbitrate")
    assert r.payload["drifted"] is True
    assert r.payload["corrected"]["status"] == "on_sale"
    assert r.payload["drifts"][0]["field"] == "status"
    with Session(database.engine) as session:
        c7 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C7")).all()
    assert len(c7) == 1
    assert (c7[0].payload or {}).get("source") == "search"


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
