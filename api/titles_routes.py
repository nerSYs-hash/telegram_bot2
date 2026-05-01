"""
Все /api/titles/* endpoints.
Подключается в api.py: app.include_router(titles_router)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/titles", tags=["titles"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class PackageBody(BaseModel):
    label: str
    duration_days: Optional[int] = None
    price_pulses: int
    price_rub: Optional[int] = None


class SettingsBody(BaseModel):
    rename_price_pulses: Optional[int] = None
    request_ttl_hours: Optional[int] = None


# ── Helpers (инжектируются из api.py) ─────────────────────────────────────────

_db = None
_require_auth_fn = None
_resolve_role_fn = None


def _setup(db, require_auth, resolve_role):
    global _db, _require_auth_fn, _resolve_role_fn
    _db = db
    _require_auth_fn = require_auth
    _resolve_role_fn = resolve_role


def _auth(authorization: str) -> dict:
    return _require_auth_fn(authorization)


def _can_edit(role: str) -> bool:
    return role in ("owner", "developer", "deputy")


# ── Packages ──────────────────────────────────────────────────────────────────

@router.get("/packages")
async def list_packages(authorization: str = Header(default=None)):
    _auth(authorization)
    from database.db_titles import list_title_packages
    return list_title_packages(_db)


@router.post("/packages")
async def create_package(body: PackageBody, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    role = _resolve_role_fn(int(payload["user_id"]))
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    from database.db_titles import create_title_package
    new_id = create_title_package(_db, body.label, body.duration_days,
                                   body.price_pulses, body.price_rub)
    from database.db_titles import get_title_package
    return get_title_package(_db, new_id)


@router.put("/packages/{pkg_id}")
async def update_package(pkg_id: int, body: PackageBody,
                         authorization: str = Header(default=None)):
    payload = _auth(authorization)
    role = _resolve_role_fn(int(payload["user_id"]))
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    from database.db_titles import update_title_package, get_title_package
    if not get_title_package(_db, pkg_id):
        raise HTTPException(status_code=404, detail="Пакет не найден")
    update_title_package(_db, pkg_id, label=body.label,
                         duration_days=body.duration_days,
                         price_pulses=body.price_pulses,
                         price_rub=body.price_rub)
    return get_title_package(_db, pkg_id)


@router.patch("/packages/{pkg_id}/toggle")
async def toggle_package(pkg_id: int, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    role = _resolve_role_fn(int(payload["user_id"]))
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    from database.db_titles import toggle_title_package
    new_val = toggle_title_package(_db, pkg_id)
    if new_val is None:
        raise HTTPException(status_code=404, detail="Пакет не найден")
    return {"id": pkg_id, "is_enabled": new_val}


@router.delete("/packages/{pkg_id}")
async def delete_package(pkg_id: int, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    role = _resolve_role_fn(int(payload["user_id"]))
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    from database.db_titles import get_title_package
    if not get_title_package(_db, pkg_id):
        raise HTTPException(status_code=404, detail="Пакет не найден")
    _db.cursor.execute("DELETE FROM title_packages WHERE id = ?", (pkg_id,))
    _db.conn.commit()
    return {"deleted": True}


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(authorization: str = Header(default=None)):
    _auth(authorization)
    _db.cursor.execute(
        "SELECT key, value FROM settings WHERE key IN "
        "('title_rename_price_pulses', 'title_request_ttl_hours')"
    )
    rows = {r["key"]: r["value"] for r in _db.cursor.fetchall()}
    return {
        "rename_price_pulses": int(rows.get("title_rename_price_pulses", 50)),
        "request_ttl_hours":   int(rows.get("title_request_ttl_hours", 48)),
    }


@router.put("/settings")
async def update_settings(body: SettingsBody, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    role = _resolve_role_fn(int(payload["user_id"]))
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    if body.rename_price_pulses is not None:
        _db.cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("title_rename_price_pulses", str(body.rename_price_pulses))
        )
    if body.request_ttl_hours is not None:
        _db.cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("title_request_ttl_hours", str(body.request_ttl_hours))
        )
    _db.conn.commit()
    return {"ok": True}


# ── Requests (заявки на рублёвую оплату) ─────────────────────────────────────

@router.get("/requests")
async def list_requests(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    authorization: str = Header(default=None),
):
    _auth(authorization)
    from database.db_titles import list_title_requests, count_title_requests_by_status
    items = list_title_requests(_db, status=status, limit=limit, offset=offset)
    pending = count_title_requests_by_status(_db, "pending")
    return {"items": items, "pending_count": pending}


@router.post("/requests/{req_id}/approve")
async def approve_request(req_id: int, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    caller_id = int(payload["user_id"])
    role = _resolve_role_fn(caller_id)
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    from database.db_titles import transition_title_request, get_title_request
    ok = transition_title_request(_db, req_id, "approved", decided_by=caller_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Уже обработана")
    return get_title_request(_db, req_id)


@router.post("/requests/{req_id}/reject")
async def reject_request(req_id: int, reason: Optional[str] = None,
                         authorization: str = Header(default=None)):
    payload = _auth(authorization)
    caller_id = int(payload["user_id"])
    role = _resolve_role_fn(caller_id)
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    from database.db_titles import transition_title_request, get_title_request
    ok = transition_title_request(_db, req_id, "rejected",
                                   decided_by=caller_id, reject_reason=reason)
    if not ok:
        raise HTTPException(status_code=409, detail="Уже обработана")
    return get_title_request(_db, req_id)


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(authorization: str = Header(default=None)):
    _auth(authorization)
    from database.db_titles import count_title_requests_by_status, list_title_packages
    pending  = count_title_requests_by_status(_db, "pending")
    approved = count_title_requests_by_status(_db, "approved")
    rejected = count_title_requests_by_status(_db, "rejected")
    packages = list_title_packages(_db)
    enabled  = sum(1 for p in packages if p["is_enabled"])
    return {
        "packages_total":   len(packages),
        "packages_enabled": enabled,
        "requests_pending": pending,
        "requests_approved": approved,
        "requests_rejected": rejected,
    }
