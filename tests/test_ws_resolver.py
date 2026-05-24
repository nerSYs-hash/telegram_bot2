"""Тесты ws_resolver — резолв workspace_id по chat_id / thread_id."""

import sqlite3
import pytest
from bot_core.ws_resolver import resolve_role_chat, resolve_thread, invalidate_resolver_cache


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.executescript('''
        CREATE TABLE bot_chats (
            chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
            role TEXT
        );
        CREATE TABLE bot_chat_topics (
            workspace_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            thread_id INTEGER NOT NULL, name TEXT, source TEXT,
            kind TEXT
        );
    ''')
    c.execute("INSERT INTO bot_chats VALUES (-100, 1, 'main')")
    c.execute("INSERT INTO bot_chats VALUES (-200, 1, 'admin')")
    c.execute("INSERT INTO bot_chats VALUES (-300, 2, 'main')")
    c.execute("INSERT INTO bot_chat_topics VALUES (1, -200, 241, 'Заявки', 'manual', 'applications')")
    c.commit()
    yield c
    c.close()
    invalidate_resolver_cache()


def test_resolve_main_chat(conn):
    assert resolve_role_chat(conn, 1, 'main') == -100

def test_resolve_admin_chat(conn):
    assert resolve_role_chat(conn, 1, 'admin') == -200

def test_resolve_role_chat_other_ws(conn):
    assert resolve_role_chat(conn, 2, 'main') == -300

def test_resolve_role_chat_missing_returns_none(conn):
    assert resolve_role_chat(conn, 1, 'journal') is None

def test_resolve_thread_by_kind(conn):
    assert resolve_thread(conn, 1, 'applications') == 241

def test_resolve_thread_missing_returns_none(conn):
    assert resolve_thread(conn, 1, 'dossier') is None

def test_resolve_thread_other_ws_isolated(conn):
    assert resolve_thread(conn, 2, 'applications') is None
