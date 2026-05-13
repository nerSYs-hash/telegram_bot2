"""Endpoints: /api/workspaces, /api/workspaces/{id}, /workspaces/{id}/members."""
import logging
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from database.db_workspaces import (
    get_workspaces_for_user, get_workspace_details,
    add_member, remove_member,
)


class MemberAdd(BaseModel):
    user_id: int
    role: str  # 'admin' | 'moderator'

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


@router.post("/{ws_id}/members")
async def add_workspace_member(
    ws_id: int, body: MemberAdd, authorization: str = Header(default=None)
):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    if body.role not in ('admin', 'moderator'):
        raise HTTPException(status_code=400, detail="Роль должна быть admin или moderator")

    target = _db.get_site_user(body.user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail="Этот юзер ещё не логинился на сайте. Попроси его войти через Telegram."
        )

    exists = _db.conn.execute(
        "SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (ws_id, body.user_id)
    ).fetchone()
    if exists:
        raise HTTPException(status_code=409, detail="Юзер уже член этого сообщества")

    add_member(_db.conn, ws_id, body.user_id, body.role)
    return {"ok": True, "user_id": body.user_id, "role": body.role}


@router.delete("/{ws_id}/members/{member_user_id}")
async def remove_workspace_member(
    ws_id: int, member_user_id: int,
    authorization: str = Header(default=None)
):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    if member_user_id == user_id:
        raise HTTPException(status_code=400, detail="Owner не может удалить себя")

    target_role = _db.conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (ws_id, member_user_id)
    ).fetchone()
    if not target_role:
        raise HTTPException(status_code=404, detail="Член сообщества не найден")
    if target_role[0] == 'owner':
        raise HTTPException(status_code=400, detail="Owner нельзя удалить (нужен transfer ownership)")

    remove_member(_db.conn, ws_id, member_user_id)
    return {"ok": True}
