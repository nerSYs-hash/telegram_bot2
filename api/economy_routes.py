"""
Все /api/economy/* endpoints.
Подключается в api.py: app.include_router(economy_router)
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Union

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/economy", tags=["economy"])

# Активный workspace_id берём из ws_context_middleware (валидирует членство
# по заголовку X-Workspace-Id, отбивает cross-tenant 403). Один импорт —
# один источник правды; смена транспорта (header → JWT-claim) не трогает
# роутеры. См. api/workspace_rbac.py:current_ws_id().
from api.workspace_rbac import current_ws_id as _ws


# ── Pydantic models ───────────────────────────────────────────────────────────

class EditSettingBody(BaseModel):
    value: Union[float, int, str]
    comment: str

class ToggleBody(BaseModel):
    comment: str

class RollbackBody(BaseModel):
    comment: str

class PointwiseCancelBody(BaseModel):
    tx_id: int
    mode: str          # deduct / debt / log_only
    comment: str

class MassCancelBody(BaseModel):
    category: str
    date_from: str
    date_to: str
    user_ids: Optional[list] = None
    mode: str = "log_only"
    comment: str

class TopicsBody(BaseModel):
    topics: list = []   # список thread_id; пусто = весь чат


# ── Helpers (будут инжектированы из api.py при include_router) ────────────────

_db = None
_require_auth_fn = None
_resolve_role_fn = None
_ws_manager = None


def _setup(db, require_auth, resolve_role, ws_manager):
    global _db, _require_auth_fn, _resolve_role_fn, _ws_manager
    _db = db
    _require_auth_fn = require_auth
    _resolve_role_fn = resolve_role
    _ws_manager = ws_manager


def _auth(authorization: str):
    payload = _require_auth_fn(authorization)
    user_id = int(payload.get("user_id", 0))
    role = _resolve_role_fn(user_id)
    return payload, user_id, role


def _check_comment(comment: str):
    if not comment or len(comment.strip()) < 5:
        raise HTTPException(400, detail="Комментарий обязателен (5-500 символов)")
    if len(comment) > 500:
        raise HTTPException(400, detail="Комментарий обязателен (5-500 символов)")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories(authorization: str = Header(default=None)):
    _payload, _uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.view"):
        raise HTTPException(403, detail="Нет доступа к экономике")
    from database.db_economy import get_econ_categories
    return get_econ_categories(_db, _ws())


@router.get("/settings")
async def list_settings(
    category: Optional[str] = Query(default=None),
    subcategory: Optional[str] = Query(default=None),
    authorization: str = Header(default=None),
):
    _payload, _uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.view"):
        raise HTTPException(403, detail="Нет доступа к экономике")
    from database.db_economy import get_econ_settings
    return get_econ_settings(_db, _ws(), category=category, subcategory=subcategory)


@router.patch("/settings/{key}")
async def update_setting(
    key: str,
    body: EditSettingBody,
    authorization: str = Header(default=None),
):
    payload, uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.edit"):
        raise HTTPException(403, detail="Нет прав на редактирование экономики")
    _check_comment(body.comment)

    from database.db_economy import set_econ
    try:
        result = set_econ(_db, _ws(), key, body.value, body.comment.strip(), uid, role)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    await _ws_manager.broadcast(_ws(), {
        "event":     "setting_changed",
        "key":       key,
        "old_value": result["old_value"],
        "new_value": result["new_value"],
        "by":        payload.get("username") or payload.get("first_name", ""),
        "comment":   body.comment.strip(),
        "at":        datetime.utcnow().isoformat(),
    })
    return result


@router.patch("/settings/{key}/toggle")
async def toggle_setting(
    key: str,
    body: ToggleBody,
    authorization: str = Header(default=None),
):
    payload, uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.toggle"):
        raise HTTPException(403, detail="Нет прав на вкл/выкл экономики")
    _check_comment(body.comment)

    from database.db_economy import toggle_econ
    try:
        result = toggle_econ(_db, _ws(), key, body.comment.strip(), uid, role)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    await _ws_manager.broadcast(_ws(), {
        "event":      "setting_toggled",
        "key":        key,
        "is_enabled": result["is_enabled"],
        "by":         payload.get("username") or payload.get("first_name", ""),
        "comment":    body.comment.strip(),
        "at":         datetime.utcnow().isoformat(),
    })
    return result


@router.patch("/settings/{key}/topics")
async def update_setting_topics(
    key: str,
    body: TopicsBody,
    authorization: str = Header(default=None),
):
    """Топики, в которых работает параметр (penalty / combo / sprint).
    Пустой список = весь чат. История не пишется — это не изменение значения."""
    _payload, _uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.edit"):
        raise HTTPException(403, detail="Нет прав на редактирование экономики")
    from database.db_economy import set_econ_topics
    return set_econ_topics(_db, _ws(), key, body.topics)


@router.patch("/categories/{key}/toggle")
async def toggle_category(
    key: str,
    body: ToggleBody,
    authorization: str = Header(default=None),
):
    payload, uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.toggle"):
        raise HTTPException(403, detail="Нет прав на вкл/выкл экономики")
    _check_comment(body.comment)

    from database.db_economy import toggle_section
    try:
        result = toggle_section(_db, _ws(), key, body.comment.strip(), uid, role)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    await _ws_manager.broadcast(_ws(), {
        "event":    "section_toggled",
        "category": key,
        "enabled":  result["is_enabled"],
        "by":       payload.get("username") or payload.get("first_name", ""),
        "comment":  body.comment.strip(),
        "at":       datetime.utcnow().isoformat(),
    })
    return result


@router.get("/settings/{key}/history")
async def get_setting_history(
    key: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    authorization: str = Header(default=None),
):
    _payload, _uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.view"):
        raise HTTPException(403, detail="Нет доступа к экономике")
    from database.db_economy_history import get_history_for_key
    return get_history_for_key(_db, _ws(), key, limit=limit, offset=offset)


@router.post("/settings/{key}/rollback/{history_id}")
async def rollback_setting(
    key: str,
    history_id: int,
    body: RollbackBody,
    authorization: str = Header(default=None),
):
    payload, uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.rollback"):
        raise HTTPException(403, detail="Нет прав на откат изменений")
    _check_comment(body.comment)

    from database.db_economy import rollback_econ
    try:
        result = rollback_econ(_db, _ws(), history_id, body.comment.strip(), uid, role)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    await _ws_manager.broadcast(_ws(), {
        "event":      "rollback",
        "key":        key,
        "to_value":   result["restored_to"],
        "from_value": result["from_value"],
        "by":         payload.get("username") or payload.get("first_name", ""),
        "comment":    body.comment.strip(),
        "at":         datetime.utcnow().isoformat(),
    })
    return result


@router.post("/cancellations/pointwise")
async def cancel_pointwise_endpoint(
    body: PointwiseCancelBody,
    authorization: str = Header(default=None),
):
    payload, uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.cancel"):
        raise HTTPException(403, detail="Только владелец может отменять выплаты")
    _check_comment(body.comment)

    if body.mode not in ("deduct", "debt", "log_only"):
        raise HTTPException(400, detail="mode должен быть: deduct / debt / log_only")

    from database.db_economy import cancel_pointwise
    try:
        result = cancel_pointwise(_db, _ws(), body.tx_id, body.mode, body.comment.strip(), uid, role)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    await _ws_manager.broadcast(_ws(), {
        "event":  "cancellation",
        "type":   "pointwise",
        "tx_id":  body.tx_id,
        "mode":   body.mode,
        "amount": result["amount"],
        "by":     payload.get("username") or payload.get("first_name", ""),
        "at":     datetime.utcnow().isoformat(),
    })
    return result


@router.post("/cancellations/mass")
async def cancel_mass_endpoint(
    body: MassCancelBody,
    authorization: str = Header(default=None),
):
    payload, uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.cancel"):
        raise HTTPException(403, detail="Только владелец может отменять выплаты")
    _check_comment(body.comment)

    filter_dict = {
        "category":  body.category,
        "date_from": body.date_from,
        "date_to":   body.date_to,
        "user_ids":  body.user_ids,
    }

    from database.db_economy import cancel_mass
    try:
        result = cancel_mass(_db, _ws(), filter_dict, "log_only", body.comment.strip(), uid, role)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

    await _ws_manager.broadcast(_ws(), {
        "event":          "cancellation",
        "type":           "mass",
        "affected_users": result["affected_users"],
        "total":          result["total"],
        "by":             payload.get("username") or payload.get("first_name", ""),
        "at":             datetime.utcnow().isoformat(),
    })
    return result


@router.get("/cancellations")
async def list_cancellations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    authorization: str = Header(default=None),
):
    _payload, _uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.view"):
        raise HTTPException(403, detail="Нет доступа к экономике")
    from database.db_economy import get_cancellations
    return get_cancellations(_db, _ws(), limit=limit, offset=offset)


@router.get("/metrics")
async def get_metrics(authorization: str = Header(default=None)):
    _payload, _uid, role = _auth(authorization)
    from permissions import has_permission
    if not has_permission(role, "economy.view"):
        raise HTTPException(403, detail="Нет доступа к экономике")
    from database.db_economy import get_economy_metrics
    return get_economy_metrics(_db, _ws())
