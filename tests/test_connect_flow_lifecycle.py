import os
import sqlite3
import pytest
from bot_core.connect_flow import connect_flow_v2_enabled
from database.db_workspaces import (
    soft_remove_bot_chat, get_disconnected_bot_chat, get_workspace_by_chat,
)


def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    assert connect_flow_v2_enabled() is False


def test_flag_on_truthy(monkeypatch):
    for v in ("1", "true", "YES", "on"):
        monkeypatch.setenv("CONNECT_FLOW_V2", v)
        assert connect_flow_v2_enabled() is True


def test_flag_off_falsy(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "0")
    assert connect_flow_v2_enabled() is False


def _conn_with_chat():
    conn = sqlite3.connect(":memory:")
    conn.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT,
        role TEXT, added_at TEXT, removed_at TIMESTAMP
    )''')
    conn.execute("INSERT INTO bot_chats (chat_id, workspace_id, role, removed_at) "
                 "VALUES (-100, 7, 'main', NULL)")
    conn.commit()
    return conn


def test_soft_remove_sets_removed_at_keeps_ws_and_role():
    conn = _conn_with_chat()
    soft_remove_bot_chat(conn, -100)
    row = conn.execute(
        "SELECT workspace_id, role, removed_at FROM bot_chats WHERE chat_id=-100"
    ).fetchone()
    assert row[0] == 7 and row[1] == 'main' and row[2] is not None


def test_get_disconnected_returns_ws_role_only_when_removed():
    conn = _conn_with_chat()
    assert get_disconnected_bot_chat(conn, -100) is None
    soft_remove_bot_chat(conn, -100)
    d = get_disconnected_bot_chat(conn, -100)
    assert d == {'workspace_id': 7, 'role': 'main'}


def test_get_workspace_by_chat_flag_off_unchanged(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    conn = _conn_with_chat()
    soft_remove_bot_chat(conn, -100)
    assert get_workspace_by_chat(conn, -100) == 7


def test_get_workspace_by_chat_flag_on_excludes_removed(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "1")
    conn = _conn_with_chat()
    assert get_workspace_by_chat(conn, -100) == 7
    soft_remove_bot_chat(conn, -100)
    assert get_workspace_by_chat(conn, -100) is None


# --- Task 4: C1 left/kicked soft-remove за флагом ---
from unittest.mock import AsyncMock, MagicMock
from database.migrations.multi_tenancy import up_create_workspaces_tables


def _lifecycle_db():
    conn = sqlite3.connect(":memory:")
    up_create_workspaces_tables(conn)
    conn.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT,
        role TEXT, added_at TEXT, removed_at TIMESTAMP)''')
    conn.execute('''CREATE TABLE users (user_id INTEGER PRIMARY KEY,
        username TEXT, first_name TEXT)''')

    class _DB:
        def __init__(self, c): self.conn = c
        def get_site_user(self, uid):
            r = self.conn.execute("SELECT user_id,username FROM users WHERE user_id=?", (uid,)).fetchone()
            return {'user_id': r[0], 'username': r[1]} if r else None
        def get_workspace_by_chat(self, cid):
            return get_workspace_by_chat(self.conn, cid)
    return _DB(conn)


def _left_update(chat_id):
    u = MagicMock()
    u.my_chat_member.new_chat_member.user.id = 999
    u.my_chat_member.new_chat_member.status = 'kicked'
    u.my_chat_member.chat.id = chat_id
    u.my_chat_member.chat.title = 'X'
    u.my_chat_member.chat.type = 'supergroup'
    u.my_chat_member.from_user.id = 42
    return u


def _ctx():
    c = MagicMock(); c.bot.id = 999
    c.bot.send_message = AsyncMock(); c.bot.leave_chat = AsyncMock()
    return c


@pytest.mark.asyncio
async def test_kicked_flag_off_hard_deletes(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    from handlers.bot_membership import on_bot_added_to_chat
    db = _lifecycle_db()
    db.conn.execute("INSERT INTO bot_chats (chat_id,workspace_id,role) VALUES (-100,1,'main')")
    db.conn.commit()
    await on_bot_added_to_chat(_left_update(-100), _ctx(), db)
    assert db.conn.execute("SELECT COUNT(*) FROM bot_chats WHERE chat_id=-100").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_kicked_flag_on_soft_removes(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "1")
    from handlers.bot_membership import on_bot_added_to_chat
    db = _lifecycle_db()
    db.conn.execute("INSERT INTO bot_chats (chat_id,workspace_id,role) VALUES (-100,1,'main')")
    db.conn.commit()
    await on_bot_added_to_chat(_left_update(-100), _ctx(), db)
    row = db.conn.execute(
        "SELECT workspace_id,role,removed_at FROM bot_chats WHERE chat_id=-100").fetchone()
    assert row == (1, 'main', row[2]) and row[2] is not None
