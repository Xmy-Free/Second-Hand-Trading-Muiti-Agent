"""Agent 实例化与注册：1 协调者 + 8 专家，共 9 类可插拔 Agent。"""
from __future__ import annotations

from app.kernel.registry import registry

# (模块, 类名, 注册名)
AGENT_SPECS = (
    ("app.agents.user_agent", "UserAgent", "user_agent"),
    ("app.agents.commodity", "CommodityAgent", "commodity"),
    ("app.agents.moderation", "ModerationAgent", "moderation"),
    ("app.agents.search", "SearchAgent", "search"),
    ("app.agents.negotiation", "NegotiationAgent", "negotiation"),
    ("app.agents.order", "OrderAgent", "order"),
    ("app.agents.credit", "CreditAgent", "credit"),
    ("app.agents.arbitrator", "ArbitratorAgent", "arbitrator"),
    ("app.agents.coordinator", "CoordinatorAgent", "coordinator"),
)


def bootstrap_agents() -> None:
    import importlib

    for mod_name, cls_name, agent_name in AGENT_SPECS:
        if registry.get(agent_name) is not None:
            continue
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name)
        registry.register(cls())
