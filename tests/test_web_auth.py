"""Срез D (V1.17.0g): тесты чистого ядра GET-двойника Telegram-логина.

bot_core/web_auth — изолированная логика, НЕ трогает прод api._verify_tg_hash.
Алгоритм подписи обязан совпадать с Telegram Login Widget (как в api.py).
"""
import hmac
import hashlib
import time

import jwt as _jwt
import pytest

from bot_core import web_auth

BOT_TOKEN = "123456:TESTTOKEN"
JWT_SECRET = "test-secret"
BOT_USERNAME = "Puls_ON_bot"


def _sign(data: dict) -> dict:
    """Подписать payload так же, как Telegram Login Widget."""
    check = {k: str(v) for k, v in data.items()}
    data_str = "\n".join(f"{k}={v}" for k, v in sorted(check.items()))
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    h = hmac.new(secret, data_str.encode(), hashlib.sha256).hexdigest()
    return {**check, "hash": h}


def _payload(**over):
    base = {
        "id": "777",
        "first_name": "Кирилл",
        "username": "groufeed",
        "photo_url": "https://t.me/i/x.jpg",
        "auth_date": str(int(time.time())),
    }
    base.update(over)
    return base


# ── verify_tg_hash ────────────────────────────────────────────────────

def test_verify_valid_signature():
    assert web_auth.verify_tg_hash(_sign(_payload()), BOT_TOKEN) is True


def test_verify_tampered_signature():
    signed = _sign(_payload())
    signed["id"] = "999"  # подменили после подписи
    assert web_auth.verify_tg_hash(signed, BOT_TOKEN) is False


def test_verify_empty_token_or_hash():
    assert web_auth.verify_tg_hash(_sign(_payload()), "") is False
    assert web_auth.verify_tg_hash({"id": "1"}, BOT_TOKEN) is False


# ── auth_date_fresh ───────────────────────────────────────────────────

def test_auth_date_fresh_and_stale():
    now = 1_000_000.0
    assert web_auth.auth_date_fresh({"auth_date": str(int(now - 10))}, now=now) is True
    assert web_auth.auth_date_fresh({"auth_date": str(int(now - 90000))}, now=now) is False
    assert web_auth.auth_date_fresh({"auth_date": "junk"}, now=now) is False


# ── make_login_jwt ────────────────────────────────────────────────────

def test_make_jwt_shape_matches_widget():
    tok = web_auth.make_login_jwt(_payload(id="42"), JWT_SECRET, developer_id=0)
    dec = _jwt.decode(tok, JWT_SECRET, algorithms=["HS256"])
    assert dec["user_id"] == 42
    assert dec["username"] == "groufeed"
    assert dec["is_owner"] is False and dec["is_admin"] is False
    assert dec["exp"] > time.time()


def test_make_jwt_developer_god_mode():
    tok = web_auth.make_login_jwt(_payload(id="555"), JWT_SECRET, developer_id=555)
    dec = _jwt.decode(tok, JWT_SECRET, algorithms=["HS256"])
    assert dec["is_owner"] is True and dec["is_admin"] is True


# ── build_callback (чистое ядро роута) ────────────────────────────────

def test_build_callback_success():
    status, html = web_auth.build_callback(
        _sign(_payload(id="42")), BOT_TOKEN, JWT_SECRET,
        developer_id=0, bot_username=BOT_USERNAME)
    assert status == 200
    assert "localStorage.setItem('auth_token'," in html
    assert "location.replace('/')" in html


def test_build_callback_bad_hash():
    bad = _sign(_payload())
    bad["hash"] = "deadbeef"
    status, html = web_auth.build_callback(
        bad, BOT_TOKEN, JWT_SECRET, bot_username=BOT_USERNAME)
    assert status == 401
    assert "auth_token" not in html
    assert BOT_USERNAME in html  # ссылка назад в бота


def test_build_callback_stale():
    old = _sign(_payload(auth_date=str(int(time.time()) - 90000)))
    status, _ = web_auth.build_callback(
        old, BOT_TOKEN, JWT_SECRET, bot_username=BOT_USERNAME)
    assert status == 401
