"""Тесты миграций connect-flow (composite PK, схема таблиц подключения)."""

import sqlite3
from database.db_migrations import add_removed_at_to_bot_chats


class _DB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _cols(conn):
    return {r[1] for r in conn.execute("PRAGMA table_info(bot_chats)").fetchall()}


def test_adds_removed_at_when_missing():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, workspace_id INTEGER)")
    db = _DB(conn)
    assert "removed_at" not in _cols(conn)
    add_removed_at_to_bot_chats(db)
    assert "removed_at" in _cols(conn)


def test_idempotent_when_already_present():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, removed_at TIMESTAMP)")
    db = _DB(conn)
    add_removed_at_to_bot_chats(db)
    add_removed_at_to_bot_chats(db)
    assert "removed_at" in _cols(conn)


def test_no_bot_chats_table_is_safe():
    conn = sqlite3.connect(":memory:")
    db = _DB(conn)
    add_removed_at_to_bot_chats(db)
