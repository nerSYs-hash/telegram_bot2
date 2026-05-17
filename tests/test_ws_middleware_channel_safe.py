"""V1.17.0h14-fix: resolve_workspace_middleware не должен падать на канале.

На канале PTB отдаёт context.user_data=None (нет effective_user). Прямое
присваивание None['ws_ctx'] роняло middleware на каждом апдейте канала
(ошибка `'NoneType' object does not support item assignment`).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import bot as bot_module


@pytest.mark.asyncio
async def test_middleware_channel_user_data_none_no_crash():
    fake = SimpleNamespace(db=SimpleNamespace(conn=None))
    update = MagicMock()
    update.effective_chat = None      # путь без build_context
    update.effective_user = None
    ctx = MagicMock()
    ctx.user_data = None              # канал → PTB отдаёт None
    ctx.chat_data = {}

    # не должно бросить (раньше падало дважды: try и except)
    await bot_module.TelegramBot.resolve_workspace_middleware(fake, update, ctx)

    assert ctx.chat_data.get('ws_ctx') is None


@pytest.mark.asyncio
async def test_middleware_chat_data_none_no_crash():
    fake = SimpleNamespace(db=SimpleNamespace(conn=None))
    update = MagicMock()
    update.effective_chat = None
    update.effective_user = None
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.chat_data = None              # тоже допустимо None

    await bot_module.TelegramBot.resolve_workspace_middleware(fake, update, ctx)

    assert ctx.user_data.get('ws_ctx') is None
