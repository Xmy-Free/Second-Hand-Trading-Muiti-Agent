"""运行事件推送总线（进程内 pub/sub）。

同步业务线程通过 bind_loop + call_soon_threadsafe 向事件循环投递，
WebSocket 协程从各自队列消费；队列满时丢弃最旧事件，保证不阻塞业务线程。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Literal

EventType = Literal["message", "node_trace", "counter", "agent_status", "conflict", "demo_phase"]
QUEUE_MAX = 300


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _fan_out(self, event: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            if q.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()  # 丢最旧
            q.put_nowait(event)

    def publish(self, type: EventType, data: dict[str, Any]) -> None:
        event = {
            "type": type,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        event["data"] = json.loads(json.dumps(event["data"], default=str))
        try:
            loop = self._loop or asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._fan_out, event)
        else:
            # 无循环场景（脚本/测试）直接投递当前线程订阅者
            self._fan_out(event)

    async def stream(self) -> AsyncIterator[dict[str, Any]]:
        q = self.subscribe()
        try:
            while True:
                yield await q.get()
        finally:
            self.unsubscribe(q)


bus = EventBus()
