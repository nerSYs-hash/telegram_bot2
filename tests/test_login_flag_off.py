"""Срез D (V1.17.0g): флаг OFF = байт-в-байт; /login поведение по флагу."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import InlineKeyboardMarkup

from handlers.bot_membership import _login_kb
from handlers.commands.login_command import login_command


# ── _login_kb(): None при OFF (≡ нет reply_markup → байт-в-байт) ───────

def test_login_kb_none_when_flag_off(monkeypatch):
    monkeypatch.delenv("LOGIN_URL_BUTTON", raising=False)
    assert _login_kb() is None


def test_login_kb_keyboard_when_flag_on(monkeypatch):
    monkeypatch.setenv("LOGIN_URL_BUTTON", "1")
    assert isinstance(_login_kb(), InlineKeyboardMarkup)


# ── /login: OFF молчит, ON шлёт кнопку ────────────────────────────────

def _update():
    upd = MagicMock()
    upd.effective_message = MagicMock()
    upd.effective_message.reply_text = AsyncMock()
    return upd


def test_faq_text_byte_for_byte_when_off(monkeypatch):
    monkeypatch.delenv("LOGIN_URL_BUTTON", raising=False)
    from handlers.commands.system_commands import (
        faq_commands_user_text, FAQ_COMMANDS_USER,
    )
    assert faq_commands_user_text() == FAQ_COMMANDS_USER  # ни байта лишнего


def test_faq_text_mentions_login_when_on(monkeypatch):
    monkeypatch.setenv("LOGIN_URL_BUTTON", "on")
    from handlers.commands.system_commands import (
        faq_commands_user_text, FAQ_COMMANDS_USER,
    )
    txt = faq_commands_user_text()
    assert txt.startswith(FAQ_COMMANDS_USER)
    assert "/login" in txt


@pytest.mark.asyncio
async def test_login_command_silent_when_off(monkeypatch):
    monkeypatch.delenv("LOGIN_URL_BUTTON", raising=False)
    upd = _update()
    await login_command(upd, MagicMock())
    upd.effective_message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_login_command_sends_keyboard_when_on(monkeypatch):
    monkeypatch.setenv("LOGIN_URL_BUTTON", "true")
    upd = _update()
    await login_command(upd, MagicMock())
    upd.effective_message.reply_text.assert_called_once()
    kwargs = upd.effective_message.reply_text.call_args.kwargs
    assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)
    btn = kwargs["reply_markup"].inline_keyboard[0][0]
    assert btn.login_url.url.endswith("/api/auth/tg-callback")
