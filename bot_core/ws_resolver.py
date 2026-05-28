"""Per-workspace резолверы chat_id/thread_id (Подпроект H).

Аддитивно поверх bot_chats.role (F) и bot_chat_topics. НЕ меняет
поведение существующих хендлеров — их перепроводка в фазах H3/H4.
"""
import os
import sqlite3
from typing import Optional

_TRUTHY = {'1', 'true', 'yes', 'on'}
_FALSY = {'0', 'false', 'no', 'off'}

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
    """H3 feature-flag. **С M2 (V1.17.0k10): дефолт ON** — multi-tenant
    gate работает по умолчанию, без явной H_RUNTIME_WS=1.

    Флаг остаётся как kill-switch: `H_RUNTIME_WS=0/false/no/off`
    явно вернёт single-tenant Pulse-fallback (только для аварийного
    отката). Любое другое значение / отсутствие env → ON.

    После M8 (e2e + снятие блокера) можно удалить вовсе.
    """
    raw = os.getenv('H_RUNTIME_WS', '').strip().lower()
    if raw in _FALSY:
        return False
    return True


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
    ws_ctx = _ws_ctx_from_context(context)
    return effective_main_chat(
        conn, ws_ctx, fallback_chat_id,
        enabled=runtime_ws_enabled(), user_id=user_id,
    )


def _ws_ctx_from_context(context):
    """Helper: достаёт ws_ctx из context.chat_data / user_data."""
    for attr in ('chat_data', 'user_data'):
        store = getattr(context, attr, None)
        if isinstance(store, dict) and store.get('ws_ctx') is not None:
            return store['ws_ctx']
    return None


def _effective_role_chat(
    conn: sqlite3.Connection,
    ws_ctx,
    role: str,
    fallback_chat_id: int,
    *,
    enabled: bool,
    user_id: Optional[int] = None,
) -> int:
    """Общая логика для role-based чата (admin/journal/main).
    Аналог effective_main_chat, но с произвольной ролью."""
    if not enabled:
        return fallback_chat_id
    ws_id = ws_ctx.workspace_id if ws_ctx is not None else None
    if ws_id is None and user_id is not None:
        ws_id = resolve_user_primary_workspace(conn, user_id)
    if ws_id is None:
        return fallback_chat_id
    resolved = resolve_role_chat(conn, ws_id, role)
    return resolved if resolved is not None else fallback_chat_id


def effective_admin_chat(
    conn: sqlite3.Connection, ws_ctx, fallback_chat_id: int,
    *, enabled: bool, user_id: Optional[int] = None,
) -> int:
    """ADMIN_CHAT_ID workspace-а или fallback. Подпроект H, расширение
    для админ-чата (Группа 4 блокера)."""
    return _effective_role_chat(
        conn, ws_ctx, 'admin', fallback_chat_id,
        enabled=enabled, user_id=user_id,
    )


def effective_journal_chat(
    conn: sqlite3.Connection, ws_ctx, fallback_chat_id: int,
    *, enabled: bool, user_id: Optional[int] = None,
) -> int:
    """JOURNAL_CHANNEL_ID workspace-а или fallback. Дублирует часть логики
    journal_handlers._get_journal_channel — но без silent skip для ws≠1
    (используется когда journal обязателен)."""
    return _effective_role_chat(
        conn, ws_ctx, 'journal', fallback_chat_id,
        enabled=enabled, user_id=user_id,
    )


def resolve_admin_chat(conn, context, fallback_chat_id, *, user_id=None):
    """Context-aware effective_admin_chat. Аналог resolve_gate_chat."""
    ws_ctx = _ws_ctx_from_context(context)
    return effective_admin_chat(
        conn, ws_ctx, fallback_chat_id,
        enabled=runtime_ws_enabled(), user_id=user_id,
    )


def resolve_admin_thread(conn, context, kind, fallback_thread_id, *, user_id=None):
    """Резолвит thread_id топика по kind (applications/dossier/bug_bot/...)
    для workspace из context. Fallback — старая константа из .env."""
    if not runtime_ws_enabled():
        return fallback_thread_id
    ws_ctx = _ws_ctx_from_context(context)
    ws_id = ws_ctx.workspace_id if ws_ctx is not None else None
    if ws_id is None and user_id is not None:
        ws_id = resolve_user_primary_workspace(conn, user_id)
    if ws_id is None:
        return fallback_thread_id
    resolved = resolve_thread(conn, ws_id, kind)
    return resolved if resolved is not None else fallback_thread_id
