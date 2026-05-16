"""
Все /api/press-releases/*, /api/bot-chats, /api/branding, /api/press-release-templates endpoints.
Подключается в api.py: app.include_router(press_release_router)

V1.16.14d (2026-05-07).
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["press-release"])


# ── Helpers (инжектируются из api.py) ─────────────────────────────────────────

_db = None
_require_auth_fn = None
_resolve_role_fn = None

# Multi-tenancy placeholder (V1.17.0a14). Сейчас API всегда работает с
# workspace=1 (Pulse Москва). После подпроекта #3 (web auth) — извлекать
# из JWT-токена через header X-Workspace-Id.
_DEFAULT_WS_ID = 1


def _setup(db, require_auth, resolve_role):
    global _db, _require_auth_fn, _resolve_role_fn
    _db = db
    _require_auth_fn = require_auth
    _resolve_role_fn = resolve_role


def _auth(authorization: str) -> dict:
    payload = _require_auth_fn(authorization)
    return payload


def _user_id(authorization: str) -> int:
    return int(_auth(authorization).get("user_id", 0))


def _check(authorization: str, action: str) -> int:
    """Проверка прав на press_release.<action>. Возвращает user_id."""
    payload = _auth(authorization)
    uid = int(payload.get("user_id", 0))
    role = _resolve_role_fn(uid)
    from permissions import has_permission
    if not has_permission(role, f"press_release.{action}"):
        raise HTTPException(status_code=403, detail=f"Нет прав press_release.{action}")
    return uid


# ── Pydantic models ───────────────────────────────────────────────────────────

class TargetItem(BaseModel):
    chat_id: int
    thread_id: Optional[int] = None


class PressReleaseBody(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    photo_file_id: Optional[str] = None        # формат "photo:fid|video:fid"
    publish_at: Optional[str] = None           # ISO datetime МСК
    status: Optional[str] = None               # draft / scheduled
    signature: Optional[str] = None
    bold_header: Optional[int] = None
    add_signature: Optional[int] = None
    inline_keyboard: Optional[list] = None
    settings_json: Optional[dict] = None
    pre_publish_reminder: Optional[int] = None
    template_id: Optional[int] = None
    targets: Optional[list[TargetItem]] = None


class TemplateBody(BaseModel):
    name: str
    text: Optional[str] = None
    photo_file_id: Optional[str] = None
    inline_keyboard: Optional[list] = None
    settings_json: Optional[dict] = None
    bold_header: Optional[int] = 1
    add_signature: Optional[int] = 1
    signature: Optional[str] = None


class TopicBody(BaseModel):
    chat_id: int
    thread_id: int
    name: Optional[str] = None


class BrandingBody(BaseModel):
    key: str
    value: str


class ChatLookupBody(BaseModel):
    chat_id_or_username: str


# ════════════════════════════════════════════════════════════════════
# bot_chats — каталог чатов
# ════════════════════════════════════════════════════════════════════

@router.get("/api/bot-chats")
async def list_bot_chats(authorization: str = Header(default=None)):
    """Список чатов где есть бот, с подгруженными топиками для форумов."""
    _check(authorization, "view")
    from database.db_press_release import get_bot_chats, get_bot_chat_topics
    chats = get_bot_chats(_db, _DEFAULT_WS_ID)
    for c in chats:
        if c.get('is_forum'):
            c['topics'] = get_bot_chat_topics(_db, _DEFAULT_WS_ID, c['chat_id'])
        else:
            c['topics'] = []
    return chats


@router.post("/api/bot-chats/lookup")
async def add_chat_manually(body: ChatLookupBody, authorization: str = Header(default=None)):
    """Ручное добавление чата по @username или chat_id (бот делает get_chat и сохраняет)."""
    _check(authorization, "edit")
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN не задан")
    raw = body.chat_id_or_username.strip()
    chat_param = raw if raw.startswith('@') else (raw if raw.startswith('-') else f"@{raw}")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getChat",
                params={"chat_id": chat_param}
            )
            data = r.json()
        if not data.get("ok"):
            raise HTTPException(status_code=400, detail=data.get("description", "getChat failed"))
        result = data["result"]
        from database.db_press_release import upsert_bot_chat
        upsert_bot_chat(
            _db,
            _DEFAULT_WS_ID,
            chat_id=int(result["id"]),
            chat_type=result.get("type", "supergroup"),
            title=result.get("title", ""),
            username=result.get("username", ""),
            is_forum=bool(result.get("is_forum", False)),
        )
        return {"ok": True, "chat": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/bot-chats/topics")
async def add_topic_manually(body: TopicBody, authorization: str = Header(default=None)):
    """Ручное добавление топика форума (когда авто-захват ещё не сработал)."""
    _check(authorization, "edit")
    from database.db_press_release import upsert_bot_chat_topic
    upsert_bot_chat_topic(_db, _DEFAULT_WS_ID, body.chat_id, body.thread_id, body.name, source='manual')
    return {"ok": True}


@router.delete("/api/bot-chats/topics/{chat_id}/{thread_id}")
async def delete_topic(chat_id: int, thread_id: int, authorization: str = Header(default=None)):
    _check(authorization, "edit")
    from database.db_press_release import delete_bot_chat_topic
    ok = delete_bot_chat_topic(_db, _DEFAULT_WS_ID, chat_id, thread_id)
    return {"ok": ok}


# ════════════════════════════════════════════════════════════════════
# Press releases — CRUD
# ════════════════════════════════════════════════════════════════════

def _serialize_post(post: dict) -> dict:
    """Готовит JSON-friendly представление поста для фронта."""
    if not post:
        return {}
    out = dict(post)
    # JSON-поля декодируем
    for k in ('inline_keyboard', 'settings_json'):
        v = out.get(k)
        if v and isinstance(v, str):
            try:
                out[k] = json.loads(v)
            except (ValueError, TypeError):
                out[k] = None
    return out


@router.get("/api/press-releases")
async def list_press(status: Optional[str] = None, authorization: str = Header(default=None)):
    """Список пресс-релизов. status: draft/scheduled/published/failed/cancelled (или нет = все)."""
    _check(authorization, "view")
    from database.db_press_release import list_press_releases
    posts = list_press_releases(_db, _DEFAULT_WS_ID, status=status, limit=300)
    return [_serialize_post(p) for p in posts]


@router.get("/api/press-releases/{post_id}")
async def get_press(post_id: int, authorization: str = Header(default=None)):
    _check(authorization, "view")
    from database.db_press_release import get_press_release
    post = get_press_release(_db, _DEFAULT_WS_ID, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Не найден")
    return _serialize_post(post)


@router.post("/api/press-releases")
async def create_press(body: PressReleaseBody, authorization: str = Header(default=None)):
    """Создать пресс-релиз. По умолчанию status=draft."""
    uid = _check(authorization, "create")
    from database.db_press_release import create_press_release, replace_targets
    fields = body.dict(exclude_none=True)
    targets = fields.pop("targets", None)
    if "inline_keyboard" in fields and fields["inline_keyboard"] is not None:
        fields["inline_keyboard"] = json.dumps(fields["inline_keyboard"], ensure_ascii=False)
    if "settings_json" in fields and fields["settings_json"] is not None:
        fields["settings_json"] = json.dumps(fields["settings_json"], ensure_ascii=False)
    # Throttling: не более N релизов за час (если settings.throttle.enabled)
    settings = body.settings_json or {}
    throttle = settings.get("throttle", {})
    if throttle.get("enabled") and body.status == "scheduled":
        from database.db_press_release import count_recent_press_releases
        since = (datetime.utcnow() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        n = count_recent_press_releases(_db, _DEFAULT_WS_ID, uid, since)
        limit = int(throttle.get("limit_per_hour", 5))
        if n >= limit:
            raise HTTPException(status_code=429, detail=f"Лимит {limit} релизов в час исчерпан")
    pid = create_press_release(_db, _DEFAULT_WS_ID, uid, **fields)
    if targets:
        replace_targets(_db, _DEFAULT_WS_ID, pid, [t.dict() if hasattr(t, "dict") else t for t in targets])
    from database.db_press_release import get_press_release
    return _serialize_post(get_press_release(_db, _DEFAULT_WS_ID, pid))


@router.put("/api/press-releases/{post_id}")
async def update_press(post_id: int, body: PressReleaseBody, authorization: str = Header(default=None)):
    """Обновить пресс-релиз. Сохраняет версию в press_release_versions."""
    uid = _check(authorization, "edit")
    from database.db_press_release import (
        get_press_release, update_press_release, replace_targets, save_version
    )
    existing = get_press_release(_db, _DEFAULT_WS_ID, post_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Не найден")
    # Сохраняем снимок текущей версии перед обновлением
    save_version(_db, _DEFAULT_WS_ID, post_id, _serialize_post(existing), uid)

    fields = body.dict(exclude_none=True)
    targets = fields.pop("targets", None)
    if "inline_keyboard" in fields and fields["inline_keyboard"] is not None:
        fields["inline_keyboard"] = json.dumps(fields["inline_keyboard"], ensure_ascii=False)
    if "settings_json" in fields and fields["settings_json"] is not None:
        fields["settings_json"] = json.dumps(fields["settings_json"], ensure_ascii=False)
    update_press_release(_db, _DEFAULT_WS_ID, post_id, **fields)
    if targets is not None:
        replace_targets(_db, _DEFAULT_WS_ID, post_id, [t.dict() if hasattr(t, "dict") else t for t in targets])
    return _serialize_post(get_press_release(_db, _DEFAULT_WS_ID, post_id))


@router.delete("/api/press-releases/{post_id}")
async def delete_press(post_id: int, authorization: str = Header(default=None)):
    _check(authorization, "delete")
    from database.db_press_release import delete_press_release
    ok = delete_press_release(_db, _DEFAULT_WS_ID, post_id)
    return {"ok": ok}


@router.post("/api/press-releases/{post_id}/cancel")
async def cancel_press(post_id: int, authorization: str = Header(default=None)):
    """Отменить запланированный пресс-релиз. Можно восстановить через /restore."""
    uid = _check(authorization, "edit")
    from database.db_press_release import cancel_press_release
    ok = cancel_press_release(_db, _DEFAULT_WS_ID, post_id, uid)
    if not ok:
        raise HTTPException(status_code=400, detail="Нельзя отменить (статус не scheduled/draft)")
    return {"ok": True}


@router.post("/api/press-releases/{post_id}/restore")
async def restore_press(post_id: int, authorization: str = Header(default=None)):
    """cancelled/failed → draft (для редактирования и повторной публикации)."""
    _check(authorization, "edit")
    from database.db_press_release import restore_press_release
    ok = restore_press_release(_db, _DEFAULT_WS_ID, post_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Нельзя восстановить (только из cancelled/failed)")
    return {"ok": True}


@router.post("/api/press-releases/{post_id}/clone")
async def clone_press(post_id: int, authorization: str = Header(default=None)):
    """Создать копию пресс-релиза (status=draft)."""
    uid = _check(authorization, "create")
    from database.db_press_release import clone_press_release, get_press_release
    new_id = clone_press_release(_db, _DEFAULT_WS_ID, post_id, uid)
    if not new_id:
        raise HTTPException(status_code=404, detail="Оригинал не найден")
    return _serialize_post(get_press_release(_db, _DEFAULT_WS_ID, new_id))


@router.post("/api/press-releases/{post_id}/publish-now")
async def publish_now(post_id: int, authorization: str = Header(default=None)):
    """Немедленная публикация: ставим publish_at=now, status=scheduled, ждём пикапа планировщика."""
    _check(authorization, "publish_now")
    from database.db_press_release import update_press_release, get_press_release
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    ok = update_press_release(_db, _DEFAULT_WS_ID, post_id, status='scheduled', publish_at=now)
    if not ok:
        raise HTTPException(status_code=404, detail="Не найден")
    return _serialize_post(get_press_release(_db, _DEFAULT_WS_ID, post_id))


@router.delete("/api/press-releases/{post_id}/from-telegram")
async def delete_from_telegram(post_id: int, authorization: str = Header(default=None)):
    """Бот удалит опубликованные сообщения из Telegram (по published target.message_ids)."""
    _check(authorization, "delete")
    from database.db_press_release import get_press_release, get_targets
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN не задан")
    post = get_press_release(_db, _DEFAULT_WS_ID, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Не найден")
    deleted_total, errors = 0, []
    async with httpx.AsyncClient(timeout=10) as client:
        for t in post.get('targets', []):
            for mid in t.get('message_ids', []):
                try:
                    r = await client.post(
                        f"https://api.telegram.org/bot{bot_token}/deleteMessage",
                        json={"chat_id": t['chat_id'], "message_id": mid}
                    )
                    if r.json().get("ok"):
                        deleted_total += 1
                    else:
                        errors.append(f"chat={t['chat_id']} msg={mid}: {r.json().get('description')}")
                except Exception as e:
                    errors.append(f"chat={t['chat_id']} msg={mid}: {e}")
    return {"deleted": deleted_total, "errors": errors}


# ════════════════════════════════════════════════════════════════════
# Versions
# ════════════════════════════════════════════════════════════════════

@router.get("/api/press-releases/{post_id}/versions")
async def get_versions(post_id: int, authorization: str = Header(default=None)):
    _check(authorization, "view")
    from database.db_press_release import list_versions
    return list_versions(_db, _DEFAULT_WS_ID, post_id)


@router.get("/api/press-releases/versions/{version_id}")
async def get_version(version_id: int, authorization: str = Header(default=None)):
    _check(authorization, "view")
    from database.db_press_release import get_version_snapshot
    snap = get_version_snapshot(_db, _DEFAULT_WS_ID, version_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Версия не найдена")
    return snap


# ════════════════════════════════════════════════════════════════════
# Templates
# ════════════════════════════════════════════════════════════════════

@router.get("/api/press-release-templates")
async def list_templates_ep(authorization: str = Header(default=None)):
    _check(authorization, "view")
    from database.db_press_release import list_templates
    rows = list_templates(_db, _DEFAULT_WS_ID)
    return [_serialize_post(r) for r in rows]


@router.post("/api/press-release-templates")
async def create_template_ep(body: TemplateBody, authorization: str = Header(default=None)):
    uid = _check(authorization, "create")
    from database.db_press_release import create_template, get_template
    fields = body.dict(exclude_none=True)
    name = fields.pop("name")
    if "inline_keyboard" in fields and fields["inline_keyboard"] is not None:
        fields["inline_keyboard"] = json.dumps(fields["inline_keyboard"], ensure_ascii=False)
    if "settings_json" in fields and fields["settings_json"] is not None:
        fields["settings_json"] = json.dumps(fields["settings_json"], ensure_ascii=False)
    tid = create_template(_db, _DEFAULT_WS_ID, name, uid, **fields)
    return _serialize_post(get_template(_db, _DEFAULT_WS_ID, tid))


@router.put("/api/press-release-templates/{template_id}")
async def update_template_ep(template_id: int, body: TemplateBody, authorization: str = Header(default=None)):
    _check(authorization, "edit")
    from database.db_press_release import update_template, get_template
    fields = body.dict(exclude_none=True)
    if "inline_keyboard" in fields and fields["inline_keyboard"] is not None:
        fields["inline_keyboard"] = json.dumps(fields["inline_keyboard"], ensure_ascii=False)
    if "settings_json" in fields and fields["settings_json"] is not None:
        fields["settings_json"] = json.dumps(fields["settings_json"], ensure_ascii=False)
    update_template(_db, _DEFAULT_WS_ID, template_id, **fields)
    return _serialize_post(get_template(_db, _DEFAULT_WS_ID, template_id))


@router.delete("/api/press-release-templates/{template_id}")
async def delete_template_ep(template_id: int, authorization: str = Header(default=None)):
    _check(authorization, "delete")
    from database.db_press_release import delete_template
    ok = delete_template(_db, _DEFAULT_WS_ID, template_id)
    return {"ok": ok}


# ════════════════════════════════════════════════════════════════════
# Branding (signature и пр.)
# ════════════════════════════════════════════════════════════════════

@router.get("/api/branding")
async def get_branding_ep(authorization: str = Header(default=None)):
    _auth(authorization)  # любой авторизованный — для отображения подписи
    from database.db_press_release import get_all_branding
    return get_all_branding(_db, _DEFAULT_WS_ID)


@router.put("/api/branding")
async def set_branding_ep(body: BrandingBody, authorization: str = Header(default=None)):
    """Изменить ключ брендинга. Требуется press_release.edit или owner."""
    uid = _user_id(authorization)
    role = _resolve_role_fn(uid)
    from permissions import has_permission
    if role not in ("owner", "developer") and not has_permission(role, "press_release.edit"):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    from database.db_press_release import set_branding
    set_branding(_db, _DEFAULT_WS_ID, body.key, body.value, uid)
    return {"ok": True, "key": body.key, "value": body.value}
