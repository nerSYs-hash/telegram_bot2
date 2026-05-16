# bot_core/ws_role.py
"""Per-workspace owner-распознавание для бота (Подпроект I).

Бот-keystone: роль юзера в ЕГО workspace через #3-keystone
api.workspace_rbac.resolve_ws_role + ws-машинерию H. За флагом
I_WS_RBAC (дефолт OFF → бот-owner логика single-tenant байт-в-байт).
"""
import os
import sqlite3
from typing import Optional

_TRUTHY = {'1', 'true', 'yes', 'on'}


def i_ws_rbac_enabled() -> bool:
    """I feature-flag. OFF (дефолт) → бот-owner логика прежняя
    single-tenant. Включается env I_WS_RBAC=1 (с Ильёй, как H)."""
    return os.getenv('I_WS_RBAC', '').strip().lower() in _TRUTHY


def _ws_from_context(context) -> Optional[int]:
    """ws_id из ws_ctx (кладёт resolve_workspace_middleware в bot.py
    в context.chat_data/user_data). None если нет (напр. ЛС)."""
    for attr in ('chat_data', 'user_data'):
        store = getattr(context, attr, None)
        if isinstance(store, dict) and store.get('ws_ctx') is not None:
            ws_id = getattr(store['ws_ctx'], 'workspace_id', None)
            if ws_id is not None:
                return ws_id
    return None


def resolve_bot_role(context, user_id: int,
                     conn: Optional[sqlite3.Connection] = None) -> str:
    """'developer'|'owner'|'deputy'|'admin'|'user' для user_id в его ws.

    Флаг OFF → всегда 'user' (вызывающий уходит на старую single-tenant
    логику — байт-в-байт). ws: группа → ws_ctx; ЛС → членство (H).
    conn=None → открываем свой к DB_PATH (и закрываем)."""
    if not i_ws_rbac_enabled():
        return 'user'
    own = conn is None
    if own:
        conn = sqlite3.connect(os.getenv('DB_PATH', 'database/bot_database.db'))
    try:
        ws_id = _ws_from_context(context)
        if ws_id is None:
            from bot_core.ws_resolver import resolve_user_primary_workspace
            ws_id = resolve_user_primary_workspace(conn, user_id)
        if ws_id is None:
            return 'user'
        # Читаем DEVELOPER_ID из env напрямую — чтобы monkeypatch в тестах
        # работал надёжно (config модуль кешируется при первом импорте).
        _dev_id_raw = os.getenv('DEVELOPER_ID', '')
        try:
            developer_id = int(_dev_id_raw) if _dev_id_raw.strip() else 0
        except (ValueError, AttributeError):
            developer_id = 0
        if not developer_id:
            # Фоллбэк: берём из config если env не выставлен
            try:
                from config import DEVELOPER_ID as _cfg_dev
                developer_id = _cfg_dev or 0
            except Exception:
                developer_id = 0
        from api.workspace_rbac import resolve_ws_role
        return resolve_ws_role(conn, user_id, ws_id, developer_id)
    except Exception:
        return 'user'  # Pulse-safe: любая ошибка → старая логика у вызывающего
    finally:
        if own:
            conn.close()


def is_ws_owner(context, user_id: int,
                conn: Optional[sqlite3.Connection] = None) -> bool:
    """MVP-предикат: владелец (или developer god-mode) своего ws."""
    return resolve_bot_role(context, user_id, conn) in ('owner', 'developer')
