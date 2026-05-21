"""FastAPI endpoints: /api/workspaces/{ws_id}/modules/...

Используется и сайтом (через React-хук useModules), и потенциально
другими клиентами. Бот не ходит через эту HTTP-обёртку — он работает
напрямую через database/db_module_toggles.
"""
import logging
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from database.db_module_toggles import (
    VALID_MODULE_IDS, get_modules, set_module_state, list_history,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workspaces", tags=["modules"])

_db = None
_require_auth_fn = None


def _setup(db, require_auth):
    """Внедряет shared DB и функцию авторизации.
    Вызывается из api.py при сборке приложения."""
    global _db, _require_auth_fn
    _db = db
    _require_auth_fn = require_auth


def _auth(authorization: str) -> dict:
    return _require_auth_fn(authorization)


def _check_write_role(ws_id: int, user_id: int) -> str:
    """owner+admin могут писать, moderator — только читать."""
    row = _db.conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (ws_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "workspace not found or no membership")
    role = row[0]
    if role not in ("owner", "admin"):
        raise HTTPException(403, "owner or admin required")
    return role


class DisableBody(BaseModel):
    reason: str


@router.get("/{ws_id}/modules")
def list_modules(ws_id: int, authorization: str = Header(default="")):
    _auth(authorization)
    return get_modules(_db.conn, ws_id)


@router.post("/{ws_id}/modules/{module_id}/enable")
def enable_module(ws_id: int, module_id: str,
                  authorization: str = Header(default="")):
    user = _auth(authorization)
    if module_id not in VALID_MODULE_IDS:
        raise HTTPException(404, "unknown module")
    _check_write_role(ws_id, user["user_id"])
    set_module_state(_db.conn, ws_id, module_id, True,
                     reason=None, user_id=user["user_id"])
    return {"is_enabled": True}


@router.post("/{ws_id}/modules/{module_id}/disable")
def disable_module(
    ws_id: int, module_id: str, body: DisableBody,
    authorization: str = Header(default=""),
):
    user = _auth(authorization)
    if module_id not in VALID_MODULE_IDS:
        raise HTTPException(404, "unknown module")
    if not body.reason or not body.reason.strip():
        raise HTTPException(400, "reason required")
    _check_write_role(ws_id, user["user_id"])
    set_module_state(_db.conn, ws_id, module_id, False,
                     reason=body.reason.strip(), user_id=user["user_id"])
    return {"is_enabled": False}


@router.get("/{ws_id}/modules/{module_id}/history")
def module_history(ws_id: int, module_id: str, limit: int = 20,
                   authorization: str = Header(default="")):
    _auth(authorization)
    if module_id not in VALID_MODULE_IDS:
        raise HTTPException(404, "unknown module")
    return list_history(_db.conn, ws_id, module_id, limit=limit)
