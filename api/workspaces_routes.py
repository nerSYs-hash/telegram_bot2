"""Endpoints: /api/workspaces, /api/workspaces/{id}, /workspaces/{id}/members."""
import logging
from fastapi import APIRouter, Header, HTTPException

from database.db_workspaces import get_workspaces_for_user, get_workspace_details

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

_db = None
_require_auth_fn = None


def _setup(db, require_auth):
    global _db, _require_auth_fn
    _db = db
    _require_auth_fn = require_auth


def _auth(authorization: str) -> dict:
    return _require_auth_fn(authorization)


def _check_role(workspace_id: int, user_id: int, required_role: str = 'moderator') -> str:
    """Возвращает роль юзера в WS или 403/404."""
    row = _db.conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (workspace_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Сообщество не найдено или вы не член")
    role = row[0]
    rank = {'owner': 3, 'admin': 2, 'moderator': 1}
    if rank.get(role, 0) < rank.get(required_role, 0):
        raise HTTPException(status_code=403, detail=f"Нужна роль {required_role} или выше")
    return role


@router.get("")
async def list_workspaces(authorization: str = Header(default=None)):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    rows = get_workspaces_for_user(_db.conn, user_id)
    return {"workspaces": rows}


@router.get("/{ws_id}")
async def workspace_details(ws_id: int, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'moderator')
    details = get_workspace_details(_db.conn, ws_id)
    if not details:
        raise HTTPException(status_code=404, detail="Сообщество не найдено")
    return details
