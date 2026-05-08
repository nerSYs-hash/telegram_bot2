"""Тесты WorkspaceContext, резолвера и @pulse_only декоратора."""
import sqlite3
import pytest

from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import create_workspace, add_member
from bot_core.workspace_context import (
    WorkspaceContext, resolve_workspace_for_chat, build_context,
    invalidate_cache, pulse_only,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    up_create_workspaces_tables(c)
    c.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1
    )''')
    c.commit()
    yield c
    c.close()
    invalidate_cache()


def test_resolve_returns_workspace_id(conn):
    create_workspace(conn, 'WS1', owner_user_id=1)
    conn.execute(
        'INSERT INTO bot_chats (chat_id, workspace_id) VALUES (?, ?)', (-100, 1)
    )
    conn.commit()
    assert resolve_workspace_for_chat(conn, -100) == 1


def test_resolve_unknown_chat_returns_none(conn):
    assert resolve_workspace_for_chat(conn, -999) is None


def test_resolve_caches_result(conn):
    create_workspace(conn, 'WS1', owner_user_id=1)
    conn.execute(
        'INSERT INTO bot_chats (chat_id, workspace_id) VALUES (?, ?)', (-100, 1)
    )
    conn.commit()
    resolve_workspace_for_chat(conn, -100)
    conn.execute('DELETE FROM bot_chats WHERE chat_id=?', (-100,))
    conn.commit()
    assert resolve_workspace_for_chat(conn, -100) == 1
    invalidate_cache(-100)
    assert resolve_workspace_for_chat(conn, -100) is None


def test_build_context_full(conn):
    create_workspace(conn, 'WS1', owner_user_id=1, is_pulse_themed=True)
    add_member(conn, 1, 42, 'admin')
    conn.execute(
        'INSERT INTO bot_chats (chat_id, workspace_id) VALUES (?, ?)', (-100, 1)
    )
    conn.commit()
    ctx = build_context(conn, chat_id=-100, user_id=42)
    assert ctx.workspace_id == 1
    assert ctx.is_pulse_themed is True
    assert ctx.member_role == 'admin'


def test_build_context_unknown_chat_returns_none(conn):
    ctx = build_context(conn, chat_id=-999, user_id=42)
    assert ctx is None


@pulse_only
async def _pulse_handler(update, ctx, ws_ctx):
    return 'ran'


@pytest.mark.asyncio
async def test_pulse_only_runs_when_themed():
    ws = WorkspaceContext(workspace_id=1, is_pulse_themed=True, plan='free')
    result = await _pulse_handler(None, None, ws)
    assert result == 'ran'


@pytest.mark.asyncio
async def test_pulse_only_skips_when_not_themed():
    ws = WorkspaceContext(workspace_id=2, is_pulse_themed=False, plan='free')
    result = await _pulse_handler(None, None, ws)
    assert result is None


@pytest.mark.asyncio
async def test_pulse_only_skips_when_no_context():
    result = await _pulse_handler(None, None, None)
    assert result is None
