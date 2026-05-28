"""Endpoints: /api/workspaces, /api/workspaces/{id}, /workspaces/{id}/members."""
import json as _json
import logging
import os
from typing import Optional
from urllib import request as _urlreq
from urllib.error import URLError, HTTPError
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from bot_core.workspace_icons import workspace_icons_enabled
from database.db_workspaces import (
    get_workspaces_for_user, get_workspace_details,
    add_member, remove_member, update_workspace_name,
    update_bot_chat_role,
    remove_bot_chat, delete_workspace, list_chat_ids_for_workspace,
)


class MemberAdd(BaseModel):
    user_id: int
    role: str  # 'admin' | 'moderator'


class WorkspacePatch(BaseModel):
    name: Optional[str] = None


class ChatPatch(BaseModel):
    role: Optional[str] = None  # 'main' | 'admin' | 'journal' | None


class TopicPut(BaseModel):
    """V1.17.0Q4: установка thread_id для kind в bot_chat_topics.
    chat_id опциональный — по умолчанию main-чат ws.
    """
    thread_id: int
    chat_id: Optional[int] = None

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


@router.get("/{ws_id}/icon.jpg")
async def workspace_icon(ws_id: int, authorization: str = Header(default=None)):
    """V1.17.0j: возвращает кешированную иконку main-чата (auth + flag).

    404 при: флаг WORKSPACE_ICONS=OFF, отсутствии пути в БД, отсутствии файла
    на диске или непривилегированном/нечленящемся пользователе.
    """
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'moderator')
    if not workspace_icons_enabled():
        raise HTTPException(status_code=404, detail="icons disabled")
    row = _db.conn.execute(
        "SELECT icon_local_path FROM workspaces WHERE id=?", (ws_id,)
    ).fetchone()
    if not row or not row[0] or not os.path.exists(row[0]):
        raise HTTPException(status_code=404, detail="no icon cached")
    return FileResponse(
        row[0], media_type='image/jpeg',
        headers={'Cache-Control': 'private, max-age=300'},
    )


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

    # SaaS блокер 3.2: пока бот ещё проверяет права через users.is_admin
    # (Группа 4 переедет на workspace_members) — дублируем флаг для совместимости.
    # Только для роли 'admin': moderator не даёт админских прав в боте.
    if body.role == 'admin':
        try:
            _db.conn.execute(
                "UPDATE users SET is_admin=1 WHERE user_id=?", (body.user_id,)
            )
            _db.conn.commit()
        except Exception as e:
            logger.warning(f"mirror users.is_admin=1 for {body.user_id}: {e}")

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

    was_admin = target_role[0] == 'admin'
    remove_member(_db.conn, ws_id, member_user_id)

    # SaaS блокер 3.2 (зеркало): если юзер БЫЛ admin и больше нигде не остался
    # admin/owner — снимаем users.is_admin для бота (пока бот не переехал на
    # workspace_members). Multi-ws-safe: проверка по всем ws.
    if was_admin:
        try:
            still_admin = _db.conn.execute(
                "SELECT 1 FROM workspace_members "
                "WHERE user_id=? AND role IN ('owner','admin') LIMIT 1",
                (member_user_id,)
            ).fetchone()
            if not still_admin:
                _db.conn.execute(
                    "UPDATE users SET is_admin=0 WHERE user_id=?", (member_user_id,)
                )
                _db.conn.commit()
        except Exception as e:
            logger.warning(f"mirror users.is_admin=0 for {member_user_id}: {e}")

    return {"ok": True}


@router.patch("/{ws_id}")
async def patch_workspace(
    ws_id: int, body: WorkspacePatch, authorization: str = Header(default=None)
):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=400, detail="Имя не может быть пустым")
        if len(body.name) > 100:
            raise HTTPException(status_code=400, detail="Имя слишком длинное")
        update_workspace_name(_db.conn, ws_id, body.name.strip())

    return {"ok": True}


_VALID_CHAT_ROLES = ('main', 'admin', 'journal')


@router.patch("/{ws_id}/chats/{chat_id}")
async def patch_workspace_chat(
    ws_id: int, chat_id: int, body: ChatPatch,
    authorization: str = Header(default=None)
):
    """V1.17.0c (F): обновить роль чата. role: main|admin|journal|null."""
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    if body.role is not None and body.role not in _VALID_CHAT_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role должна быть одной из: {', '.join(_VALID_CHAT_ROLES)} или null",
        )

    chat_row = _db.conn.execute(
        "SELECT workspace_id FROM bot_chats WHERE chat_id=?", (chat_id,)
    ).fetchone()
    if not chat_row:
        raise HTTPException(status_code=404, detail="Чат не найден")
    if chat_row[0] != ws_id:
        raise HTTPException(status_code=403, detail="Чат принадлежит другому сообществу")

    # Если назначаем главного/админа/журнал — снять эту роль с других чатов того же ws
    # (на каждое сообщество максимум 1 чат каждой роли).
    if body.role is not None:
        _db.conn.execute(
            "UPDATE bot_chats SET role=NULL WHERE workspace_id=? AND role=? AND chat_id<>?",
            (ws_id, body.role, chat_id),
        )

    update_bot_chat_role(_db.conn, chat_id, body.role)
    return {"ok": True, "chat_id": chat_id, "role": body.role}


# ── V1.17.0Q4: треды (bot_chat_topics) per-ws ──

# Список kind которые можно настраивать через UI.
# applications/dossier — карточки заявок и досье (admin-чат).
# bbs — главный ББС-тред (объявления знакомств).
# bbs_other — отдельный тред для bbs_other (объявления продаж/аренды).
#             Если не задан — fallback на 'bbs'.
# bug_bot / bug_site — баг-треды (репорты).
_VALID_TOPIC_KINDS = {'applications', 'dossier', 'bbs', 'bbs_other', 'bug_bot', 'bug_site'}


@router.get("/{ws_id}/topics")
async def list_workspace_topics(ws_id: int, authorization: str = Header(default=None)):
    """Возвращает все настроенные треды в bot_chat_topics для ws."""
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'admin')

    rows = _db.conn.execute(
        "SELECT chat_id, thread_id, kind FROM bot_chat_topics WHERE workspace_id=?",
        (ws_id,),
    ).fetchall()
    return {
        "topics": [
            {"chat_id": r[0], "thread_id": r[1], "kind": r[2]}
            for r in rows
        ]
    }


@router.put("/{ws_id}/topics/{kind}")
async def put_workspace_topic(
    ws_id: int, kind: str, body: TopicPut,
    authorization: str = Header(default=None)
):
    """Установить (upsert) thread_id для kind в активном ws.
    chat_id по умолчанию = main-чат ws (если он есть)."""
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    if kind not in _VALID_TOPIC_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"kind должен быть одним из: {', '.join(sorted(_VALID_TOPIC_KINDS))}",
        )

    # Резолвим chat_id: если не передан — берём main-чат ws.
    chat_id = body.chat_id
    if chat_id is None:
        row = _db.conn.execute(
            "SELECT chat_id FROM bot_chats WHERE workspace_id=? AND role='main' LIMIT 1",
            (ws_id,),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=400,
                detail="Нет main-чата в этом сообществе. Сначала привяжи main-чат."
            )
        chat_id = row[0]

    # Upsert через INSERT OR REPLACE по (workspace_id, kind) — уникальная пара.
    # Если у kind уже есть запись с другим chat_id, она будет перезаписана.
    _db.conn.execute(
        "DELETE FROM bot_chat_topics WHERE workspace_id=? AND kind=?",
        (ws_id, kind),
    )
    _db.conn.execute(
        "INSERT INTO bot_chat_topics (workspace_id, chat_id, thread_id, kind) "
        "VALUES (?, ?, ?, ?)",
        (ws_id, chat_id, body.thread_id, kind),
    )
    _db.conn.commit()

    # Сбрасываем кеш резолвера в боте (на след. update пересчитает).
    try:
        from bot_core.ws_resolver import invalidate_resolver_cache
        invalidate_resolver_cache()
    except Exception:
        pass

    return {"ok": True, "ws_id": ws_id, "kind": kind,
            "chat_id": chat_id, "thread_id": body.thread_id}


@router.delete("/{ws_id}/topics/{kind}")
async def delete_workspace_topic(
    ws_id: int, kind: str, authorization: str = Header(default=None)
):
    """Удалить настройку kind. Для bbs_other это означает «fallback на bbs»."""
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    if kind not in _VALID_TOPIC_KINDS:
        raise HTTPException(status_code=400, detail="Неверный kind")

    _db.conn.execute(
        "DELETE FROM bot_chat_topics WHERE workspace_id=? AND kind=?",
        (ws_id, kind),
    )
    _db.conn.commit()

    try:
        from bot_core.ws_resolver import invalidate_resolver_cache
        invalidate_resolver_cache()
    except Exception:
        pass

    return {"ok": True, "ws_id": ws_id, "kind": kind, "removed": True}


# ── V1.17.0c (G): удаление чатов и сообществ ──

def _bot_leave_chat(chat_id: int) -> bool:
    """Дергает Telegram Bot API чтобы бот покинул чат. Возвращает True если успех.
    Не падает на ошибках сети/прав — логируем и идём дальше (DB чистим всё равно).
    Использует stdlib urllib чтобы не зависеть от внешних пакетов.
    """
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.warning('BOT_TOKEN не задан, leaveChat пропускаем')
        return False
    url = f'https://api.telegram.org/bot{token}/leaveChat'
    data = _json.dumps({'chat_id': chat_id}).encode('utf-8')
    req = _urlreq.Request(url, data=data, method='POST',
                          headers={'Content-Type': 'application/json'})
    try:
        with _urlreq.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                logger.warning(f'leaveChat {chat_id} -> {resp.status}')
                return False
            return True
    except (URLError, HTTPError) as e:
        logger.warning(f'leaveChat {chat_id} failed: {e}')
        return False
    except Exception as e:
        logger.warning(f'leaveChat {chat_id} unexpected: {e}')
        return False


@router.delete("/{ws_id}/chats/{chat_id}")
async def disconnect_workspace_chat(
    ws_id: int, chat_id: int,
    authorization: str = Header(default=None)
):
    """G: отключить чат от сообщества. Owner-only. Бот покидает чат + DB чистится."""
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    row = _db.conn.execute(
        "SELECT workspace_id FROM bot_chats WHERE chat_id=?", (chat_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Чат не найден")
    if row[0] != ws_id:
        raise HTTPException(status_code=403, detail="Чат принадлежит другому сообществу")

    _bot_leave_chat(chat_id)  # best-effort
    remove_bot_chat(_db.conn, chat_id)
    return {"ok": True, "chat_id": chat_id}


@router.delete("/{ws_id}")
async def delete_workspace_endpoint(
    ws_id: int, authorization: str = Header(default=None)
):
    """G: удалить сообщество полностью. Owner-only. Pulse-themed запрещено.
    Бот покидает все привязанные чаты, потом каскадно стираются members и сам ws.
    """
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    ws_row = _db.conn.execute(
        "SELECT is_pulse_themed FROM workspaces WHERE id=?", (ws_id,)
    ).fetchone()
    if not ws_row:
        raise HTTPException(status_code=404, detail="Сообщество не найдено")
    if ws_row[0]:
        raise HTTPException(
            status_code=403,
            detail="Это Pulse-сообщество, его нельзя удалить через сайт"
        )

    chat_ids = list_chat_ids_for_workspace(_db.conn, ws_id)
    for cid in chat_ids:
        _bot_leave_chat(cid)
    try:
        delete_workspace(_db.conn, ws_id)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"ok": True, "deleted_workspace_id": ws_id, "left_chats": len(chat_ids)}
