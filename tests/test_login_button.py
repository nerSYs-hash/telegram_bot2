"""Срез D (V1.17.0g): тесты login_keyboard() + флаг LOGIN_URL_BUTTON."""
import importlib

import pytest
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from bot_core import login_button


def test_login_keyboard_single_loginurl_button():
    kb = login_button.login_keyboard()
    assert isinstance(kb, InlineKeyboardMarkup)
    rows = kb.inline_keyboard
    assert len(rows) == 1 and len(rows[0]) == 1
    btn = rows[0][0]
    assert isinstance(btn, InlineKeyboardButton)
    assert btn.login_url is not None
    assert btn.login_url.url == "https://puls-chat.ru/api/auth/tg-callback"


def test_login_keyboard_respects_site_url(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://example.org")
    importlib.reload(login_button)
    btn = login_button.login_keyboard().inline_keyboard[0][0]
    assert btn.login_url.url == "https://example.org/api/auth/tg-callback"
    monkeypatch.delenv("SITE_URL", raising=False)
    importlib.reload(login_button)


def test_login_keyboard_custom_text():
    btn = login_button.login_keyboard("Открыть кабинет").inline_keyboard[0][0]
    assert btn.text == "Открыть кабинет"


@pytest.mark.parametrize("val,expected", [
    ("1", True), ("true", True), ("TRUE", True), ("yes", True),
    ("on", True), ("  On ", True),
    ("0", False), ("false", False), ("", False), ("off", False),
    ("nope", False),
])
def test_login_url_enabled_flag(monkeypatch, val, expected):
    monkeypatch.setenv("LOGIN_URL_BUTTON", val)
    assert login_button.login_url_enabled() is expected


def test_login_url_enabled_default_off(monkeypatch):
    monkeypatch.delenv("LOGIN_URL_BUTTON", raising=False)
    assert login_button.login_url_enabled() is False
