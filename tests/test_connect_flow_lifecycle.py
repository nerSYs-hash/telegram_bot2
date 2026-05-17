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
