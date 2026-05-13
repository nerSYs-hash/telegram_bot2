"""Тест: /setup_welcome — owner-only гейт + happy path."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

from handlers.commands.system_commands import setup_welcome_command


@pytest.mark.asyncio
async def test_setup_welcome_blocks_non_owner():
    upd = MagicMock()
    upd.effective_user.id = 999  # not owner
    upd.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()
    db = MagicMock()

    await setup_welcome_command(upd, ctx, db, main_admin_id=1283941769)

    upd.message.reply_text.assert_called_once_with(
        "❌ Команда доступна только владельцу.", parse_mode='HTML'
    )
    ctx.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_setup_welcome_requires_target_chat_id(monkeypatch):
    monkeypatch.delenv('TARGET_CHAT_ID', raising=False)
    monkeypatch.setenv('TARGET_CHAT_ID', '0')
    upd = MagicMock()
    upd.effective_user.id = 42
    upd.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()
    db = MagicMock()

    await setup_welcome_command(upd, ctx, db, main_admin_id=42)

    upd.message.reply_text.assert_called_once_with("❌ TARGET_CHAT_ID не настроен в .env")
    ctx.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_setup_welcome_happy_path(monkeypatch):
    monkeypatch.setenv('TARGET_CHAT_ID', '-1001234567')
    monkeypatch.setenv('BOT_USERNAME', 'TestBot')
    upd = MagicMock()
    upd.effective_user.id = 42
    upd.message.reply_text = AsyncMock()

    sent_msg = MagicMock()
    sent_msg.message_id = 555
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock(return_value=sent_msg)
    ctx.bot.pin_chat_message = AsyncMock()
    db = MagicMock()

    await setup_welcome_command(upd, ctx, db, main_admin_id=42)

    # send_message с deep-link
    ctx.bot.send_message.assert_called_once()
    args, kwargs = ctx.bot.send_message.call_args
    assert args[0] == -1001234567
    keyboard = kwargs['reply_markup'].inline_keyboard
    assert keyboard[0][0].url == "https://t.me/TestBot?start=join_1"

    # pin был вызван
    ctx.bot.pin_chat_message.assert_called_once()

    # ответ владельцу с message_id
    upd.message.reply_text.assert_called_once()
    assert "555" in upd.message.reply_text.call_args[0][0]
