"""H3 e4: тест проводки гейта message_handler через _gate_target_chat.

Доказывает: флаг OFF → self.target_chat_id (байт-в-байт старое
поведение). Флаг ON → главный чат workspace (по чату ИЛИ по юзеру в ЛС).
"""
import sqlite3
import pytest
from types import SimpleNamespace

from handlers.message_handler import MessageHandler
from bot_core.ws_resolver import invalidate_resolver_cache


class _FakeDB:
    def __init__(self, conn):
        self.conn = conn


@pytest.fixture
def mh():
    c = sqlite3.connect(':memory:')
    c.executescript('''
        CREATE TABLE bot_chats (
            chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, role TEXT
        );
        CREATE TABLE workspace_members (
            workspace_id INTEGER NOT NULL, user_id INTEGER NOT NULL, role TEXT
        );
    ''')
    c.execute("INSERT INTO bot_chats VALUES (-100, 1, 'main')")
    c.execute("INSERT INTO bot_chats VALUES (-300, 2, 'main')")
    c.execute("INSERT INTO workspace_members VALUES (2, 500, 'owner')")
    c.commit()
    handler = MessageHandler(_FakeDB(c), target_chat_id=-100, main_admin_id=999)
    yield handler
    c.close()
    invalidate_resolver_cache()


def _ctx(ws_ctx=None):
    return SimpleNamespace(chat_data={'ws_ctx': ws_ctx}, user_data={'ws_ctx': ws_ctx})


def _ws(workspace_id):
    return SimpleNamespace(workspace_id=workspace_id, is_pulse_themed=True)


def test_flag_off_returns_target_chat(monkeypatch, mh):
    """Kill-switch H_RUNTIME_WS=0: явный откат на single-tenant target.
    С M2 дефолт ON — для теста OFF-пути ставим явно."""
    monkeypatch.setenv('H_RUNTIME_WS', '0')
    # даже с ws_ctx другого ws — флаг OFF → старый target
    assert mh._gate_target_chat(_ctx(_ws(2))) == -100


def test_flag_on_group_resolves_ws_chat(monkeypatch, mh):
    monkeypatch.setenv('H_RUNTIME_WS', '1')
    # групповой чат привязан к ws=2 (ws_ctx в chat_data) → главный чат ws=2
    assert mh._gate_target_chat(_ctx(_ws(2))) == -300


def test_flag_on_dm_resolves_by_user(monkeypatch, mh):
    monkeypatch.setenv('H_RUNTIME_WS', '1')
    # ЛС: ws_ctx=None, но user 500 = owner ws=2 → главный чат ws=2 (Кирилл)
    assert mh._gate_target_chat(_ctx(None), user_id=500) == -300


def test_flag_on_unresolved_falls_back(monkeypatch, mh):
    monkeypatch.setenv('H_RUNTIME_WS', '1')
    # ничего не резолвится → Pulse-safe fallback на self.target_chat_id
    assert mh._gate_target_chat(_ctx(None), user_id=888) == -100
