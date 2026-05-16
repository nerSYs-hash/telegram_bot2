"""
Все /api/titles/* endpoints.
Подключается в api.py: app.include_router(titles_router)
"""

import logging
import os
import time as _time
from typing import Optional

import httpx
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

# Multi-tenancy placeholder (V1.17.0a17). До подпроекта #3 (web auth) —
# извлекать из JWT через header X-Workspace-Id.
_DEFAULT_WS_ID = 1


def _setup(db, require_auth, resolve_role):
    global _db, _require_auth_fn, _resolve_role_fn
    _db = db
    _require_auth_fn = require_auth
    _resolve_role_fn = resolve_role


def _auth(authorization: str) -> dict:
    return _require_auth_fn(authorization)


def _can_edit(role: str) -> bool:
    return role in ("owner", "developer", "deputy")


# ── Telegram helpers ─────────────────────────────────────────────────────────

async def _apply_title_telegram(user_id: int, title_text: str) -> tuple[bool, str]:
    """Promote user + set custom title via Telegram Bot API (httpx, no PTB context).
    Returns (ok, error_description).
    """
    bot_token = os.getenv("BOT_TOKEN", "")
    chat_id_str = os.getenv("TARGET_CHAT_ID", "0")
    if not bot_token or chat_id_str == "0":
        return False, "BOT_TOKEN или TARGET_CHAT_ID не заданы"
    chat_id = int(chat_id_str)
    tg_url = f"https://api.telegram.org/bot{bot_token}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r1 = await client.post(f"{tg_url}/promoteChatMember", json={
                "chat_id": chat_id,
                "user_id": user_id,
                "can_manage_chat": True,
                "can_post_messages": False,
                "can_edit_messages": False,
                "can_delete_messages": False,
                "can_restrict_members": False,
                "can_promote_members": False,
                "can_change_info": False,
                "can_invite_users": False,
                "can_pin_messages": False,
                "can_manage_video_chats": False,
            })
            data1 = r1.json()
            if not data1.get("ok"):
                return False, data1.get("description", "Ошибка promoteChatMember")

            r2 = await client.post(f"{tg_url}/setChatAdministratorCustomTitle", json={
                "chat_id": chat_id,
                "user_id": user_id,
                "custom_title": title_text,
            })
            data2 = r2.json()
            if not data2.get("ok"):
                return False, data2.get("description", "Ошибка setChatAdministratorCustomTitle")

        return True, ""
    except Exception as e:
        return False, str(e)


def _write_marketplace_service(db, user_id: int, title_text: str, duration_days) -> str:
    """Create or extend active title record in marketplace_services.
    Returns 'created' | 'extended' | 'already_permanent'.
    duration_days: int or None (None = permanent).
    """
    now_ts = _time.time()

    db.cursor.execute(
        "SELECT id, expires_at FROM marketplace_services "
        "WHERE user_id = ? AND service_type = 'title' AND status = 'active' "
        "LIMIT 1",
        (user_id,)
    )
    existing = db.cursor.fetchone()

    if existing:
        try:
            exp = existing["expires_at"]
        except (TypeError, KeyError):
            exp = existing[1]

        is_permanent = exp is None
        if not is_permanent:
            try:
                is_permanent = float(exp) < now_ts  # already expired → treat as no existing
                if not is_permanent:
                    pass  # still active timed title
            except Exception:
                is_permanent = True

        if is_permanent and exp is None:
            return "already_permanent"

        # Extend (or replace expired record)
        if exp is not None:
            try:
                if float(exp) < now_ts:
                    # Expired — update to new window
                    new_expires = (now_ts + duration_days * 86400) if duration_days else None
                else:
                    base = float(exp)
                    new_expires = (base + duration_days * 86400) if duration_days else None
            except Exception:
                new_expires = (now_ts + duration_days * 86400) if duration_days else None
        else:
            new_expires = None  # upgrade to permanent not applicable here

        try:
            row_id = existing["id"]
        except (TypeError, KeyError):
            row_id = existing[0]

        db.cursor.execute(
            "UPDATE marketplace_services SET expires_at = ? WHERE id = ?",
            (new_expires, row_id)
        )
        db.conn.commit()
        return "extended"

    # No existing record — insert new
    new_expires = (now_ts + duration_days * 86400) if duration_days else None
    db.cursor.execute(
        "INSERT INTO marketplace_services "
        "(user_id, service_type, status, content, expires_at, start_time) "
        "VALUES (?, 'title', 'active', ?, ?, ?)",
        (user_id, title_text, new_expires, now_ts)
    )
    db.conn.commit()
    return "created"


# ── Packages ──────────────────────────────────────────────────────────────────

@router.get("/packages")
async def list_packages(authorization: str = Header(default=None)):
    _auth(authorization)
    from database.db_titles import list_title_packages
    return list_title_packages(_db, _DEFAULT_WS_ID)


@router.post("/packages")
async def create_package(body: PackageBody, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    role = _resolve_role_fn(int(payload["user_id"]))
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    from database.db_titles import create_title_package
    new_id = create_title_package(_db, _DEFAULT_WS_ID, body.label, body.duration_days,
                                   body.price_pulses, body.price_rub)
    from database.db_titles import get_title_package
    return get_title_package(_db, _DEFAULT_WS_ID, new_id)


@router.put("/packages/{pkg_id}")
async def update_package(pkg_id: int, body: PackageBody,
                         authorization: str = Header(default=None)):
    payload = _auth(authorization)
    role = _resolve_role_fn(int(payload["user_id"]))
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    from database.db_titles import update_title_package, get_title_package
    if not get_title_package(_db, _DEFAULT_WS_ID, pkg_id):
        raise HTTPException(status_code=404, detail="Пакет не найден")
    update_title_package(_db, _DEFAULT_WS_ID, pkg_id, label=body.label,
                         duration_days=body.duration_days,
                         price_pulses=body.price_pulses,
                         price_rub=body.price_rub)
    return get_title_package(_db, _DEFAULT_WS_ID, pkg_id)


@router.patch("/packages/{pkg_id}/toggle")
async def toggle_package(pkg_id: int, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    role = _resolve_role_fn(int(payload["user_id"]))
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    from database.db_titles import toggle_title_package
    new_val = toggle_title_package(_db, _DEFAULT_WS_ID, pkg_id)
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
    if not get_title_package(_db, _DEFAULT_WS_ID, pkg_id):
        raise HTTPException(status_code=404, detail="Пакет не найден")
    _db.cursor.execute(
        "DELETE FROM title_packages WHERE id = ? AND workspace_id = ?",
        (pkg_id, _DEFAULT_WS_ID)
    )
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
    items = list_title_requests(_db, _DEFAULT_WS_ID, status=status, limit=limit, offset=offset)
    pending = count_title_requests_by_status(_db, _DEFAULT_WS_ID, "pending")
    return {"items": items, "pending_count": pending}


@router.post("/requests/{req_id}/approve")
async def approve_request(req_id: int, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    caller_id = int(payload["user_id"])
    role = _resolve_role_fn(caller_id)
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")

    from database.db_titles import transition_title_request, get_title_request
    ok = transition_title_request(_db, _DEFAULT_WS_ID, req_id, "approved", decided_by=caller_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Уже обработана")

    req = get_title_request(_db, _DEFAULT_WS_ID, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    tg_ok, tg_err = await _apply_title_telegram(req["user_id"], req["title_text"])
    if not tg_ok:
        # Rollback status so admin can retry
        _db.cursor.execute(
            "UPDATE title_rub_requests SET status='pending', decided_at=NULL, decided_by=NULL "
            "WHERE id = ? AND workspace_id = ?",
            (req_id, _DEFAULT_WS_ID)
        )
        _db.conn.commit()
        raise HTTPException(status_code=400, detail=f"Telegram: {tg_err}")

    _write_marketplace_service(
        _db, req["user_id"], req["title_text"], req.get("duration_days")
    )

    return get_title_request(_db, _DEFAULT_WS_ID, req_id)


@router.post("/requests/{req_id}/reject")
async def reject_request(req_id: int, reason: Optional[str] = None,
                         authorization: str = Header(default=None)):
    payload = _auth(authorization)
    caller_id = int(payload["user_id"])
    role = _resolve_role_fn(caller_id)
    if not _can_edit(role):
        raise HTTPException(status_code=403, detail="Нет доступа")
    from database.db_titles import transition_title_request, get_title_request
    ok = transition_title_request(_db, _DEFAULT_WS_ID, req_id, "rejected",
                                   decided_by=caller_id, reject_reason=reason)
    if not ok:
        raise HTTPException(status_code=409, detail="Уже обработана")
    return get_title_request(_db, _DEFAULT_WS_ID, req_id)


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(authorization: str = Header(default=None)):
    _auth(authorization)
    from database.db_titles import count_title_requests_by_status, list_title_packages
    pending  = count_title_requests_by_status(_db, _DEFAULT_WS_ID, "pending")
    approved = count_title_requests_by_status(_db, _DEFAULT_WS_ID, "approved")
    rejected = count_title_requests_by_status(_db, _DEFAULT_WS_ID, "rejected")
    packages = list_title_packages(_db, _DEFAULT_WS_ID)
    enabled  = sum(1 for p in packages if p["is_enabled"])
    return {
        "packages_total":   len(packages),
        "packages_enabled": enabled,
        "requests_pending": pending,
        "requests_approved": approved,
        "requests_rejected": rejected,
    }
