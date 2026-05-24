"""
WebSocket-менеджер для уведомлений об изменениях в экономике.

Multi-tenant: каждое подключение помнит свой workspace_id (приходит
query-параметром `?ws=<id>` при connect, валидируется в /api/ws/economy
по членству перед accept). Broadcast рассылает только подписчикам того
же workspace — кросс-тенант лик закрыт.

NB: ws_context_middleware на WebSocket НЕ срабатывает (это HTTP-only
ASGI middleware), поэтому ws_id передаётся в connect явно, а не через
ContextVar. Шаблон копируется на любой будущий per-modular WS-канал
(метрики, кузница, гримуар и т.п.).
"""

import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EconomyWSManager:
    def __init__(self):
        # WebSocket → workspace_id подписчика
        self.subs: Dict[WebSocket, int] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, ws_id: int) -> None:
        await ws.accept()
        async with self._lock:
            self.subs[ws] = ws_id
        logger.info(
            f"Economy WS: подключение ws_id={ws_id}, всего клиентов {len(self.subs)}"
        )

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self.subs.pop(ws, None)
        logger.info(f"Economy WS: отключение, осталось клиентов {len(self.subs)}")

    async def broadcast(self, ws_id: int, event: dict) -> None:
        """Рассылка события подписчикам конкретного workspace.

        Идентификатор workspace добавляется в payload, чтобы клиент мог
        ещё раз свериться (defense-in-depth) и игнорировать чужое, если
        вдруг при гонке состояний пришло не своё.
        """
        payload = {**event, "workspace_id": ws_id}
        async with self._lock:
            dead = []
            for sock, sub_ws_id in self.subs.items():
                if sub_ws_id != ws_id:
                    continue
                try:
                    await sock.send_json(payload)
                except Exception:
                    dead.append(sock)
            for sock in dead:
                self.subs.pop(sock, None)

    def active_workspace_ids(self) -> Set[int]:
        """Множество ws_id, у которых есть хотя бы один активный подписчик.

        Используется фоновым `_metrics_broadcaster` чтобы не считать
        метрики для пустых тенантов."""
        return set(self.subs.values())


# Глобальный синглтон
manager = EconomyWSManager()
