"""通用房间 WebSocket 广播中心（议价室按会话房间推送）。"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class RoomHub:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, room: str, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms.setdefault(room, set()).add(ws)

    def disconnect(self, room: str, ws: WebSocket) -> None:
        self._rooms.get(room, set()).discard(ws)

    async def broadcast(self, room: str, data: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._rooms.get(room, set())):
            try:
                await ws.send_json(data)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(room, ws)

    def broadcast_threadsafe(self, loop: asyncio.AbstractEventLoop, room: str, data: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.broadcast(room, data)))


hub = RoomHub()
