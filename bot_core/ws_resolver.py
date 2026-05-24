"""Per-workspace резолверы chat_id/thread_id (Подпроект H).

Аддитивно поверх bot_chats.role (F) и bot_chat_topics. НЕ меняет
поведение существующих хендлеров — их перепроводка в фазах H3/H4.
"""
import os
import sqlite3
from typing import Optional

_TRUTHY = {'1', 'true', 'yes', 'on'}

_role_chat_cache: dict[tuple[int, str], Optional[int]] = {}
_thread_cache: dict[tuple[int, str], Optional[int]] = {}


def resolve_role_chat(
    conn: sqlite3.Connection, workspace_id: int, role: str
) -> Optional[int]:
    """chat_id чата с ролью role (main|admin|journal) в workspace.
    None если в этом ws нет чата с такой ролью."""
    key = (workspace_id, role)
    if key in _role_chat_cache:
        return _role_chat_cache[key]
    row = conn.execute(
        "SELECT chat_id FROM bot_chats WHERE workspace_id=? AND role=? LIMIT 1",
        (workspace_id, role),
    ).fetchone()
    val = row[0] if row else None
    _role_chat_cache[key] = val
    return val


def resolve_thread(
    conn: sqlite3.Connection, workspace_id: int, kind: str
) -> Optional[int]:
    """thread_id топика вида kind (applications|dossier|bug_bot|bug_site|bbs)
    в workspace. Источник — bot_chat_topics.kind. None если не настроен."""
    key = (workspace_id, kind)
    if key in _thread_cache:
        return _thread_cache[key]
    row = conn.execute(
        "SELECT thread_id FROM bot_chat_topics "
        "WHERE workspace_id=? AND kind=? LIMIT 1",
        (workspace_id, kind),
    ).fetchone()
    val = row[0] if row else None
    _thread_cache[key] = val
    return val


def invalidate_resolver_cache() -> None:
    """Сброс кешей (вызывать при смене ролей чатов / топиков с сайта)."""
    _role_chat_cache.clear()
    _thread_cache.clear()


def runtime_ws_enabled() -> bool:
    """H3 feature-flag. Дефолт OFF → поведение прод-бота байт-в-байт
    прежнее (single-tenant Pulse). Включается env H_RUNTIME_WS=1
    только на стейдже/с Ильёй."""
    return os.getenv('H_RUNTIME_WS', '').strip().lower() in _TRUTHY


def resolve_user_primary_workspace(
    conn: sqlite3.Connection, user_id: int
) -> Optional[int]:
    """workspace юзера по членству — для DM-гейта (в ЛС chat.id юзера
    нет в bot_chats, резолв по чату невозможен).

    Приоритет: owner → admin → прочее, затем меньший workspace_id.
    None если членства нет → effective_main_chat отдаст Pulse-safe
    фоллбэк. Не кешируем: членство/владение меняется, staleness опасен."""
    row = conn.execute(
        "SELECT workspace_id FROM workspace_members WHERE user_id=? "
        "ORDER BY CASE role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 "
        "ELSE 2 END, workspace_id LIMIT 1",
        (user_id,),
    ).fetchone()
    return row[0] if row else None


def effective_main_chat(
    conn: sqlite3.Connection,
    ws_ctx,
    fallback_chat_id: int,
    *,
    enabled: bool,
    user_id: Optional[int] = None,
) -> int:
    """Главный chat_id workspace для Pulse-гейта (H3).

    Резолв ws: chat-based (ws_ctx, групповой чат) → если нет, user-based
    (resolve_user_primary_workspace, DM 2-го владельца).

    Pulse-safe фоллбэк (возврат fallback_chat_id, т.е. старое
    single-tenant поведение) когда:
      - enabled=False (флаг OFF, прод-дефолт) — ws_ctx/user игнорируются;
      - ws не зарезолвился (ни по чату, ни по членству юзера);
      - у workspace нет чата с ролью main.
    Иначе — главный чат ИМЕННО этого workspace (изоляция тенантов)."""
    if not enabled:
        return fallback_chat_id
    ws_id = ws_ctx.workspace_id if ws_ctx is not None else None
    if ws_id is None and user_id is not None:
        ws_id = resolve_user_primary_workspace(conn, user_id)
    if ws_id is None:
        return fallback_chat_id
    resolved = resolve_role_chat(conn, ws_id, 'main')
    return resolved if resolved is not None else fallback_chat_id


def resolve_gate_chat(conn, context, fallback_chat_id, *, user_id=None):
    """Context-aware обёртка над effective_main_chat для Pulse-гейта.

    Достаёт ws_ctx из context.chat_data/user_data (кладёт middleware
    bot.py resolve_workspace_middleware) и резолвит эффективный главный
    чат. Флаг OFF → fallback_chat_id байт-в-байт. Единый источник
    логики для message_handler и registration_conversation."""
    ws_ctx = None
    for attr in ('chat_data', 'user_data'):
        store = getattr(context, attr, None)
        if isinstance(store, dict) and store.get('ws_ctx') is not None:
            ws_ctx = store['ws_ctx']
            break
    return effective_main_chat(
        conn, ws_ctx, fallback_chat_id,
        enabled=runtime_ws_enabled(), user_id=user_id,
    )
