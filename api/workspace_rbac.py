"""Per-workspace RBAC keystone (Подпроект #3).

resolve_ws_role(conn, user_id, ws_id) — единственное место, где
workspace_members.role превращается в permissions-vocabulary роль.
ContextVar'ы хранят активный ws запроса (ставит middleware в api.py).
"""
from contextvars import ContextVar
import sqlite3

# Активный workspace_id запроса (ставит ws_context_middleware).
WS_ID_CTX: ContextVar[int] = ContextVar("ws_id", default=1)
# Резолвнутая permissions-роль текущего юзера в активном ws.
WS_ROLE_CTX: ContextVar[str] = ContextVar("ws_role", default="user")

# workspace_members.role → permissions.py role
_MEMBER_ROLE_MAP = {
    "owner": "owner",
    "admin": "deputy",
    "moderator": "admin",
}


def resolve_ws_role(
    conn: sqlite3.Connection,
    user_id: int,
    ws_id: int,
    developer_id: int = 0,
) -> str:
    """owner/deputy/admin/developer/user в permissions-словаре.

    developer_id (Илья) — god-mode во всех ws, проверяется ПЕРВЫМ.
    MAIN_ADMIN не имеет спец-кейса: он owner ws=1 только через membership.
    """
    if developer_id and user_id == developer_id:
        return "developer"
    row = conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (ws_id, user_id),
    ).fetchone()
    if not row:
        return "user"
    return _MEMBER_ROLE_MAP.get(row[0], "user")


def default_workspace_for_user(
    conn: sqlite3.Connection,
    user_id: int,
) -> int:
    """ws по умолчанию, когда фронт НЕ прислал X-Workspace-Id.

    Берём личное сообщество юзера из членства (owner → admin → любое),
    НЕ хардкодим ws=1 — иначе второй владелец (не член ws=1) ловит 403
    на всех запросах без заголовка (напр. /permissions/catalog).
    Фолбэк 1: Pulse-владелец член ws=1; developer god-mode разрулит роль.
    """
    row = conn.execute(
        "SELECT workspace_id FROM workspace_members WHERE user_id=? "
        "ORDER BY CASE role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, "
        "workspace_id LIMIT 1",
        (user_id,),
    ).fetchone()
    return row[0] if row else 1
