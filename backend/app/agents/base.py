"""Agent 统一契约基类。所有专家 Agent 继承本类并注册到 registry。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.kernel.acl import AclEnvelope, Perf
from app.kernel.post import post_message
from app.kernel.registry import registry


class BaseAgent(ABC):
    name: str = "base"
    display_name: str = "Base Agent"
    avatar: str = "Bot"
    accent: str = "#6366F1"
    capabilities: list[str] = []
    description: str = ""

    def __init__(self) -> None:
        self._llm_mode = "rule"

    @property
    def llm_mode(self) -> str:
        return self._llm_mode

    def set_llm_mode(self, mode: str) -> None:
        self._llm_mode = mode
        registry.set_llm_mode(self.name, mode)

    def ensure_running(self) -> None:
        if registry.is_paused(self.name):
            from app.kernel.dispatch import AgentPausedError

            raise AgentPausedError(self.name)

    def say(self, perf: Perf, receiver: str, payload: dict[str, Any], *,
            conversation_id: str, summary: str = "", confidence: float = 1.0,
            timeout: int | None = None, error_code: str | None = None,
            graph_thread_id: str | None = None, count: bool = True) -> AclEnvelope:
        msg = AclEnvelope(
            conversation_id=conversation_id,
            performative=perf,
            sender=self.name,
            receiver=receiver,
            summary=summary,
            payload=payload,
            confidence=confidence,
            timeout=timeout,
            error_code=error_code,
            graph_thread_id=graph_thread_id,
        )
        return post_message(msg, count=count)

    @abstractmethod
    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        """处理一条入站消息并返回回复（回复由调用方决定是否再次 post）。"""
