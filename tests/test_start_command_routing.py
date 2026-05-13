"""Тесты роутинга /start join_<ws_id> в registration_conversation.start_reg."""
import sqlite3
import pytest
from unittest.mock import AsyncMock, MagicMock

from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import create_workspace


@pytest.fixture
def db_with_workspaces():
    """Минимальный фейк Database с .conn + workspaces table."""
    conn = sqlite3.connect(':memory:')
    up_create_workspaces_tables(conn)
    # Pulse (ws=1, is_pulse_themed=True)
    conn.execute(
        "INSERT INTO workspaces (id, name, owner_user_id, is_pulse_themed, plan) "
        "VALUES (1, 'Pulse Москва', 1, 1, 'free')"
    )
    # Other (ws=2, is_pulse_themed=False)
    conn.execute(
        "INSERT INTO workspaces (id, name, owner_user_id, is_pulse_themed, plan) "
        "VALUES (2, 'Other WS', 99, 0, 'free')"
    )
    conn.commit()

    class _DB:
        def __init__(self, c):
            self.conn = c
    return _DB(conn)


def _make_update():
    upd = MagicMock()
    upd.effective_user.id = 555
    upd.effective_user.first_name = 'Bob'
    upd.message.reply_text = AsyncMock()
    upd.message = AsyncMock()
    upd.message.reply_text = AsyncMock()
    return upd


def _make_context(args, db):
    ctx = MagicMock()
    ctx.args = args
    ctx.bot_data = {'db': db}
    return ctx


@pytest.mark.asyncio
async def test_join_unknown_ws_replies_not_found(db_with_workspaces):
    from handlers.registration_conversation import start_reg
    upd = _make_update()
    ctx = _make_context(args=['join_999'], db=db_with_workspaces)
    result = await start_reg(upd, ctx)
    # Должен ответить "не найдено" и завершить
    upd.message.reply_text.assert_called()
    call_text = upd.message.reply_text.call_args[0][0]
    assert 'не найдено' in call_text.lower()


@pytest.mark.asyncio
async def test_join_nonpulse_shows_welcome(db_with_workspaces):
    from handlers.registration_conversation import start_reg
    upd = _make_update()
    ctx = _make_context(args=['join_2'], db=db_with_workspaces)
    result = await start_reg(upd, ctx)
    upd.message.reply_text.assert_called()
    call_text = upd.message.reply_text.call_args[0][0]
    assert 'Other WS' in call_text
    assert 'добро пожаловать' in call_text.lower()


@pytest.mark.asyncio
async def test_join_invalid_arg_replies_error(db_with_workspaces):
    from handlers.registration_conversation import start_reg
    upd = _make_update()
    ctx = _make_context(args=['join_abc'], db=db_with_workspaces)
    result = await start_reg(upd, ctx)
    upd.message.reply_text.assert_called()
    call_text = upd.message.reply_text.call_args[0][0]
    assert 'некорректная' in call_text.lower()
