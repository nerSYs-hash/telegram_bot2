"""
WebSocket-менеджер для уведомлений об изменениях в экономике.
"""

import asyncio
import logging
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class EconomyWSManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.active.add(ws)
        logger.info(f"Economy WS: подключено клиентов {len(self.active)}")

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self.active.discard(ws)
        logger.info(f"Economy WS: подключено клиентов {len(self.active)}")

    async def broadcast(self, event: dict) -> None:
        async with self._lock:
            dead = []
            for ws in self.active:
                try:
                    await ws.send_json(event)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active.discard(ws)


# Глобальный синглтон
manager = EconomyWSManager()
