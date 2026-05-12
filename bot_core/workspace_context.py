"""WorkspaceContext — рантайм-объект, описывающий контекст текущего workspace.
Создаётся при входе в каждый handler (резолв через chat_id → workspace_id).
"""
import functools
import logging
import sqlite3
from dataclasses import dataclass
from typing import Optional


logger = logging.getLogger(__name__)


@dataclass
class WorkspaceContext:
    workspace_id: int
    is_pulse_themed: bool
    plan: str
    member_role: Optional[str] = None  # роль текущего юзера в WS


_chat_to_ws_cache: dict[int, int] = {}


def resolve_workspace_for_chat(
    conn: sqlite3.Connection, chat_id: int
) -> Optional[int]:
    """По telegram chat_id находит workspace_id из bot_chats. Кеширует."""
    cached = _chat_to_ws_cache.get(chat_id)
    if cached is not None:
        return cached
    row = conn.execute(
        'SELECT workspace_id FROM bot_chats WHERE chat_id=?', (chat_id,)
    ).fetchone()
    if row:
        _chat_to_ws_cache[chat_id] = row[0]
        return row[0]
    return None


def build_context(
    conn: sqlite3.Connection, chat_id: int, user_id: Optional[int] = None
) -> Optional[WorkspaceContext]:
    """Собирает WorkspaceContext для входящего update-а.
    Возвращает None если chat не привязан к workspace (бот в новом чате)."""
    ws_id = resolve_workspace_for_chat(conn, chat_id)
    if ws_id is None:
        return None
    ws_row = conn.execute(
        'SELECT is_pulse_themed, plan FROM workspaces WHERE id=?', (ws_id,)
    ).fetchone()
    if not ws_row:
        return None
    member_role = None
    if user_id is not None:
        m_row = conn.execute(
            'SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?',
            (ws_id, user_id)
        ).fetchone()
        if m_row:
            member_role = m_row[0]
    return WorkspaceContext(
        workspace_id=ws_id,
        is_pulse_themed=bool(ws_row[0]),
        plan=ws_row[1],
        member_role=member_role,
    )


def invalidate_cache(chat_id: Optional[int] = None) -> None:
    """Сброс кеша при изменении привязки чата к workspace."""
    if chat_id is None:
        _chat_to_ws_cache.clear()
    else:
        _chat_to_ws_cache.pop(chat_id, None)


def pulse_only(handler):
    """Декоратор: handler выполняется только если ws_ctx.is_pulse_themed.
    Иначе silent skip с логом.

    Применять к Pulse-специфичным handlers (BBS, реактор, anketa, shipper).

    Сигнатура handler-а: (update, ctx, ws_ctx, ...) — ws_ctx должен быть
    в kwargs или 3-м позиционным.

    V1.17.0a19 (multi-tenancy middleware): для PTB-handlers с сигнатурой
    `async def handler(update, context)` декоратор автоматически достаёт
    ws_ctx из `context.user_data['ws_ctx']` или `context.chat_data['ws_ctx']`
    которые middleware (bot.py resolve_workspace_middleware) кладёт туда
    перед запуском handler'а.
    """
    @functools.wraps(handler)
    async def wrapper(*args, **kwargs):
        ws_ctx = kwargs.get('ws_ctx')
        if ws_ctx is None and len(args) >= 3:
            ws_ctx = args[2]
        # PTB-fallback: достаём из context.user_data / context.chat_data
        if ws_ctx is None and len(args) >= 2:
            context = args[1]
            for attr in ('user_data', 'chat_data'):
                store = getattr(context, attr, None)
                if isinstance(store, dict):
                    ws_ctx = store.get('ws_ctx')
                    if ws_ctx is not None:
                        break
        if ws_ctx is None or not ws_ctx.is_pulse_themed:
            logger.debug(
                'pulse_only skip: handler=%s ws=%s',
                handler.__name__,
                ws_ctx.workspace_id if ws_ctx else 'None'
            )
            return None
        return await handler(*args, **kwargs)
    return wrapper
