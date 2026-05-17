"""Срез D (V1.17.0g): единая точка построения LoginUrl-кнопки + флаг.

`login_keyboard()` → одна inline-кнопка `LoginUrl` на GET-двойник
`/api/auth/tg-callback` (см. bot_core.web_auth, api.py). Реюзят
коннект-флоу, команда /login и потом хаб C (DRY).

Флаг `LOGIN_URL_BUTTON` (дефолт OFF) — дом. правило «код+тумблер+FAQ».
OFF = байт-в-байт (текст-ссылки как сейчас, /login неактивен).
"""
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LoginUrl

SITE_URL = os.getenv("SITE_URL", "https://puls-chat.ru").rstrip("/")

_CALLBACK_PATH = "/api/auth/tg-callback"
_TRUTHY = {"1", "true", "yes", "on"}


def callback_url() -> str:
    return f"{SITE_URL}{_CALLBACK_PATH}"


def login_keyboard(text: str = "🔑 Войти в кабинет") -> InlineKeyboardMarkup:
    """Одна inline-кнопка нативного Telegram-логина (LoginUrl)."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(text, login_url=LoginUrl(url=callback_url()))
    ]])


def login_url_enabled() -> bool:
    """Флаг среза D. OFF по умолчанию → байт-в-байт со старым поведением."""
    return os.getenv("LOGIN_URL_BUTTON", "").strip().lower() in _TRUTHY
