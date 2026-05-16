"""Per-workspace резолверы chat_id/thread_id (Подпроект H).

Аддитивно поверх bot_chats.role (F) и bot_chat_topics. НЕ меняет
поведение существующих хендлеров — их перепроводка в фазах H3/H4.
"""
import sqlite3
from typing import Optional

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
