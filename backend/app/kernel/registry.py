"""Agent 注册表：实例发现 + agent_status 持久化 + 健康/计数/熔断管理。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.kernel.events import bus
from app.models import AgentStatus


class Registry:
    def __init__(self) -> None:
        self._agents: dict[str, object] = {}
        # 内存级熔断器：连续异常计数 + 已熔断标记（不持久化，重启自愈）
        self._failures: dict[str, int] = {}
        self._tripped: set[str] = set()

    # ---------- 注册 / 发现 ----------
    def register(self, agent) -> None:  # noqa: ANN001
        self._agents[agent.name] = agent
        with Session(engine) as session:
            row = session.exec(
                select(AgentStatus).where(AgentStatus.name == agent.name)
            ).first()
            if row is None:
                row = AgentStatus(name=agent.name)
                session.add(row)
            row.display_name = agent.display_name
            row.avatar = agent.avatar
            row.capabilities = list(agent.capabilities)
            row.description = agent.description
            row.accent = getattr(agent, "accent", "#6366F1")
            session.commit()

    def get(self, name: str):
        return self._agents.get(name)

    def names(self) -> list[str]:
        return list(self._agents.keys())

    # ---------- 计数 / 活跃 ----------
    def record_message(self, name: str) -> None:
        self._bump(name, msg=True)

    def record_task(self, name: str) -> None:
        self._bump(name, task=True)

    def _bump(self, name: str, *, msg: bool = False, task: bool = False) -> None:
        snapshot: dict | None = None
        with Session(engine) as session:
            row = session.exec(
                select(AgentStatus).where(AgentStatus.name == name)
            ).first()
            if row is None:
                return
            if msg:
                row.msg_handled += 1
            if task:
                row.tasks_handled += 1
            row.last_active_at = datetime.now(timezone.utc)
            session.commit()
            snapshot = self._to_dict(row)
        if snapshot:
            bus.publish("counter", {"agent": name, "msg": msg, "task": task,
                                    "msg_handled": snapshot["msg_handled"],
                                    "tasks_handled": snapshot["tasks_handled"],
                                    "last_active_at": snapshot["last_active_at"]})

    # ---------- 状态 / 引擎 / 暂停 ----------
    def set_runtime_status(self, name: str, status: str) -> None:
        self._update(name, runtime_status=status)

    def set_llm_mode(self, name: str, mode: str) -> None:
        self._update(name, llm_mode=mode)

    def pause(self, name: str) -> None:
        self._update(name, runtime_status="paused")

    def resume(self, name: str) -> None:
        """管理员恢复：清熔断计数/标记并置 running。"""
        self._failures.pop(name, None)
        self._tripped.discard(name)
        self._update(name, runtime_status="running")

    def is_paused(self, name: str) -> bool:
        with Session(engine) as session:
            row = session.exec(
                select(AgentStatus).where(AgentStatus.name == name)
            ).first()
            return bool(row and row.runtime_status == "paused")

    # ---------- 熔断器（内存级，连续 N 次异常自动暂停）----------
    def record_failure(self, name: str) -> int:
        """记录一次 Agent 处理异常，返回连续失败次数。"""
        count = self._failures.get(name, 0) + 1
        self._failures[name] = count
        return count

    def record_success(self, name: str) -> None:
        """一次成功处理即清零连续失败计数。"""
        if self._failures.get(name):
            self._failures.pop(name, None)

    def trip_breaker(self, name: str) -> None:
        """熔断：标记 + 置 paused（管理员可 resume）。"""
        self._tripped.add(name)
        self._update(name, runtime_status="paused")

    def is_tripped(self, name: str) -> bool:
        return name in self._tripped

    def breaker_limit(self) -> int:
        return settings.breaker_fail_limit

    def breaker_info(self, name: str) -> dict:
        return {
            "consecutive_failures": self._failures.get(name, 0),
            "tripped": name in self._tripped,
            "limit": settings.breaker_fail_limit,
        }

    def _update(self, name: str, **fields) -> None:
        with Session(engine) as session:
            row = session.exec(
                select(AgentStatus).where(AgentStatus.name == name)
            ).first()
            if row is None:
                return
            for k, v in fields.items():
                setattr(row, k, v)
            session.commit()
            snapshot = self._to_dict(row)
        bus.publish("agent_status", snapshot)

    # ---------- 查询 ----------
    def list_status(self) -> list[dict]:
        with Session(engine) as session:
            rows = session.exec(select(AgentStatus).order_by(AgentStatus.id)).all()
            return [self._to_dict(r) for r in rows]

    @staticmethod
    def _to_dict(row: AgentStatus) -> dict:
        return {
            "name": row.name,
            "display_name": row.display_name,
            "avatar": row.avatar,
            "accent": row.accent,
            "capabilities": row.capabilities,
            "description": row.description,
            "runtime_status": row.runtime_status,
            "llm_mode": row.llm_mode,
            "msg_handled": row.msg_handled,
            "tasks_handled": row.tasks_handled,
            "last_active_at": row.last_active_at.isoformat() if row.last_active_at else None,
            "breaker_tripped": row.name in registry._tripped,
            "consecutive_failures": registry._failures.get(row.name, 0),
        }


registry = Registry()
