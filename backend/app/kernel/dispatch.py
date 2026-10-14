"""协调者 → 专家 Agent 的标准 ACL 调用口（进程内同步，消息双向落库+广播）。

熔断代管（spec 8.4）：agent.handle 抛异常时累计失败计数；连续 N 次（默认 3）
自动 trip_breaker 置 paused，由协调者用确定性规则兜底返回，并记录 level=2
系统事件（action=breaker_takeover），管理员可经 resume 恢复。
"""
from __future__ import annotations

from typing import Any

from app.kernel.acl import AclEnvelope
from app.kernel.post import post_message
from app.kernel.registry import registry

PAUSED_ERROR_CODE = "AGENT_PAUSED"
FAILED_ERROR_CODE = "AGENT_FAILED"
BREAKER_ERROR_CODE = "AGENT_BREAKER"


class AgentPausedError(RuntimeError):
    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        super().__init__(f"AGENT_PAUSED:{agent_name}")


def call_agent(agent_name: str, conversation_id: str, payload: dict[str, Any], *,
               perf: str = "request", summary: str = "", thread_id: str | None = None,
               timeout: int | None = None) -> AclEnvelope:
    agent = registry.get(agent_name)
    if agent is None:
        raise KeyError(f"Agent 未注册：{agent_name}")

    req = AclEnvelope(
        conversation_id=conversation_id,
        performative=perf,
        sender="coordinator",
        receiver=agent_name,
        summary=summary,
        payload=payload,
        timeout=timeout,
        graph_thread_id=thread_id,
    )
    post_message(req)

    if registry.is_paused(agent_name):
        # 不调用已暂停 Agent，直接回一条标准 refuse，业务层按规则友好响应
        refuse = req.reply(
            "refuse",
            {"error": f"该 Agent 已被管理员暂停，服务暂时不可用：{agent_name}",
             "agent": agent_name, "agent_paused": True},
            error_code=PAUSED_ERROR_CODE,
        )
        return post_message(refuse)

    registry.record_task(agent_name)
    try:
        reply = agent.handle(req)
    except Exception as exc:  # noqa: BLE001 - 异常 Agent 不得击穿主流程
        return _on_agent_failure(req, agent_name, exc)
    registry.record_success(agent_name)
    return post_message(reply)


def _on_agent_failure(req: AclEnvelope, agent_name: str, exc: Exception) -> AclEnvelope:
    """异常计数 → 达阈值熔断 → 协调者规则兜底（全程留痕）。"""
    failures = registry.record_failure(agent_name)
    tripped_now = failures >= registry.breaker_limit() and not registry.is_tripped(agent_name)

    if tripped_now:
        registry.trip_breaker(agent_name)
        _record_takeover(agent_name, req.payload, exc, failures)

    if agent_name == "coordinator":
        data = _coordinator_self_fallback(req.payload, exc)
    else:
        from app.agents.coordinator import CoordinatorAgent

        data = CoordinatorAgent.rule_takeover(
            agent_name, req.payload, exc, tripped=tripped_now, failures=failures,
        )
    action = req.payload.get("action", "")
    arb_actions = {"order_vote", "risk_vote", "utility_score", "target_compat_check",
                   "ssot_reconcile", "build_evidence", "rule_appeal", "review_rejection",
                   "risk_opinion", "penalize"}
    reply_perf = "arbitrate" if action in arb_actions else "inform"
    fallback = req.reply(
        reply_perf, data, confidence=0.5,
        summary=f"协调者规则代管：{agent_name}.{action}",
        error_code=BREAKER_ERROR_CODE if tripped_now else FAILED_ERROR_CODE,
    )
    return post_message(fallback)


def _record_takeover(agent_name: str, payload: dict, exc: Exception, failures: int) -> None:
    from app.kernel.observe import record_conflict

    record_conflict(
        scene="SYS", ctype="system", level=2,
        participants=["coordinator", agent_name],
        payload={"action": "breaker_takeover", "agent": agent_name,
                 "business_action": payload.get("action"),
                 "consecutive_failures": failures,
                 "error": f"{type(exc).__name__}: {exc}"[:200]},
        result=f"Agent 连续 {failures} 次异常已熔断，协调者规则代管，等待管理员 resume",
        graph_thread_id=payload.get("thread_id"),
    )


def _coordinator_self_fallback(payload: dict, exc: Exception) -> dict[str, Any]:
    """协调者自身异常时的最小安全兜底（不递归调用任何 Agent）。"""
    note = f"coordinator unavailable: {type(exc).__name__}"
    action = payload.get("action")
    if action == "risk_vote":
        return {"decision": "manual", "score": 0.0, "details": [],
                "note": note, "breaker_takeover": True}
    if action == "utility_score":
        return {"ok": False, "error": note, "breaker_takeover": True}
    return {"ok": False, "error": note, "breaker_takeover": True}


def is_paused_reply(reply: AclEnvelope) -> bool:
    return reply.error_code == PAUSED_ERROR_CODE


def paused_message(reply: AclEnvelope) -> str:
    return reply.payload.get("error", f"Agent 已暂停：{reply.receiver}")
