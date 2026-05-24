"""Срез D (V1.17.0g): чистое ядро GET-двойника Telegram-логина.

Веб-виджет (#3, в проде): `api.py` `POST /api/auth/telegram` — JSON-подпись.
Inline `LoginUrl` Telegram отдаёт **GET** с подписью на настроенный домен.
Этот модуль — изолированная, тестируемая логика GET-варианта.

⚠️ Намеренно НЕ переиспользует прод-горячие `api._verify_tg_hash`/
`api._make_jwt` (веб-виджет НЕ за флагом; импорт `api.py` тянет реальную БД).
Алгоритм подписи **идентичен** Telegram Login Widget (тот же расчёт, что в
`api._verify_tg_hash`) — дубль ~5 строк ради нулевого риска для POST-пути.
"""
from __future__ import annotations

import hashlib
import hmac
import html as _html
import json
import time
from typing import Optional

import jwt as _jwt

_JWT_DAYS = 7
_MAX_AUTH_AGE = 86400  # как в api.auth_telegram


def verify_tg_hash(data: dict, bot_token: str) -> bool:
    """Проверка подписи Telegram Login Widget (sorted k=v\\n, HMAC-SHA256,
    secret = sha256(bot_token)). Совпадает с api._verify_tg_hash."""
    received = data.get("hash", "")
    if not received or not bot_token:
        return False
    check = {k: v for k, v in data.items() if k != "hash"}
    data_str = "\n".join(f"{k}={v}" for k, v in sorted(check.items()))
    secret = hashlib.sha256(bot_token.encode()).digest()
    computed = hmac.new(secret, data_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, received)


def auth_date_fresh(data: dict, max_age: int = _MAX_AUTH_AGE,
                    now: Optional[float] = None) -> bool:
    """auth_date не старше max_age секунд (как проверка в api.auth_telegram)."""
    try:
        ad = int(data.get("auth_date", 0))
    except (TypeError, ValueError):
        return False
    cur = time.time() if now is None else now
    return (cur - ad) <= max_age


def make_login_jwt(data: dict, jwt_secret: str, developer_id: int = 0,
                   days: int = _JWT_DAYS) -> str:
    """JWT с тем же payload, что api._make_jwt в POST-ветке (включая
    developer-god-mode по DEVELOPER_ID). Тот же JWT_SECRET → токен валиден
    для существующих /api/auth/me и _decode_jwt."""
    user_id = int(data["id"])
    is_dev = bool(developer_id and user_id == developer_id)
    payload = {
        "user_id": user_id,
        "username": data.get("username", ""),
        "first_name": data.get("first_name", ""),
        "photo_url": data.get("photo_url", ""),
        "is_admin": is_dev,
        "is_owner": is_dev,
        "exp": int(time.time()) + days * 86400,
    }
    return _jwt.encode(payload, jwt_secret, algorithm="HS256")


def render_success_html(token: str) -> str:
    """Мини-страница: кладёт JWT в localStorage['auth_token'] (тот же ключ,
    что виджет в AdminDashboard.jsx) и редиректит в SPA-корень. Ноль
    изменений/пересборки фронта."""
    return (
        "<!doctype html><meta charset=utf-8>"
        "<script>localStorage.setItem('auth_token',"
        f"{json.dumps(token)});location.replace('/')</script>"
        "Входим…"
    )


def render_error_html(bot_username: str) -> str:
    u = _html.escape(bot_username or "")
    return (
        "<!doctype html><meta charset=utf-8>"
        "<p>Ссылка устарела или недействительна. "
        "Вернись в бота и нажми «Войти» ещё раз.</p>"
        f'<p><a href="https://t.me/{u}">Открыть бота</a></p>'
    )


def build_callback(query: dict, bot_token: str, jwt_secret: str,
                   developer_id: int = 0, bot_username: str = "",
                   now: Optional[float] = None) -> tuple[int, str]:
    """Чистое ядро `GET /api/auth/tg-callback`. → (http_status, html)."""
    if not verify_tg_hash(query, bot_token) or not auth_date_fresh(query, now=now):
        return 401, render_error_html(bot_username)
    try:
        token = make_login_jwt(query, jwt_secret, developer_id)
    except (KeyError, ValueError, TypeError):
        return 400, render_error_html(bot_username)
    return 200, render_success_html(token)
