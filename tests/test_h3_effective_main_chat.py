"""H3: тесты резолвера effective_main_chat + флага runtime_ws_enabled
+ resolve_user_primary_workspace (DM-путь 2-го владельца).

Доказывают: флаг OFF (прод-дефолт) → поведение байт-в-байт прежнее
(возврат fallback). Флаг ON → главный чат ИМЕННО workspace входящего
чата (group) ИЛИ workspace юзера по членству (DM, его chat.id нет в
bot_chats), с Pulse-safe фоллбэком при любой неоднозначности.
"""
import sqlite3
import pytest
from types import SimpleNamespace

from bot_core.ws_resolver import (
    effective_main_chat,
    runtime_ws_enabled,
    resolve_user_primary_workspace,
    resolve_gate_chat,
    invalidate_resolver_cache,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.executescript('''
        CREATE TABLE bot_chats (
            chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
            role TEXT
        );
        CREATE TABLE workspace_members (
            workspace_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            role TEXT
        );
    ''')
    c.execute("INSERT INTO bot_chats VALUES (-100, 1, 'main')")
    c.execute("INSERT INTO bot_chats VALUES (-300, 2, 'main')")
    c.execute("INSERT INTO bot_chats VALUES (-400, 3, 'admin')")  # ws=3 без main
    # 500 = owner ws=2 (Кирилл-кейс); 600 = только moderator ws=2;
    # 700 = owner ws=2 И moderator ws=1 (проверка приоритета owner);
    # 800 = без членства.
    c.execute("INSERT INTO workspace_members VALUES (2, 500, 'owner')")
    c.execute("INSERT INTO workspace_members VALUES (2, 600, 'moderator')")
    c.execute("INSERT INTO workspace_members VALUES (1, 700, 'moderator')")
    c.execute("INSERT INTO workspace_members VALUES (2, 700, 'owner')")
    c.commit()
    yield c
    c.close()
    invalidate_resolver_cache()


def _ws(workspace_id):
    return SimpleNamespace(workspace_id=workspace_id)


# ── resolve_user_primary_workspace ───────────────────────────────

def test_user_ws_owner(conn):
    assert resolve_user_primary_workspace(conn, 500) == 2


def test_user_ws_member_only(conn):
    assert resolve_user_primary_workspace(conn, 600) == 2


def test_user_ws_owner_precedence_over_other_membership(conn):
    # 700: owner ws=2 + moderator ws=1 → owner-роль выигрывает → ws=2
    assert resolve_user_primary_workspace(conn, 700) == 2


def test_user_ws_no_membership_returns_none(conn):
    assert resolve_user_primary_workspace(conn, 800) is None


# ── effective_main_chat: chat-based (group) ──────────────────────

def test_flag_off_returns_fallback_even_with_ws(conn):
    assert effective_main_chat(conn, _ws(2), -999, enabled=False) == -999


def test_flag_off_none_ws_returns_fallback(conn):
    assert effective_main_chat(conn, None, -999, enabled=False) == -999


def test_flag_on_none_ws_no_user_returns_fallback(conn):
    assert effective_main_chat(conn, None, -999, enabled=True) == -999


def test_flag_on_resolves_own_ws_main(conn):
    assert effective_main_chat(conn, _ws(1), -999, enabled=True) == -100


def test_flag_on_isolates_other_ws(conn):
    assert effective_main_chat(conn, _ws(2), -999, enabled=True) == -300


def test_flag_on_ws_without_main_falls_back(conn):
    assert effective_main_chat(conn, _ws(3), -999, enabled=True) == -999


# ── effective_main_chat: user-based (DM, ws_ctx=None) ────────────

def test_flag_on_dm_resolves_user_ws_main(conn):
    # Кирилл в ЛС: ws_ctx=None (его chat.id нет в bot_chats),
    # но он owner ws=2 → главный чат ws=2, НЕ Pulse
    assert effective_main_chat(
        conn, None, -999, enabled=True, user_id=500
    ) == -300


def test_flag_off_dm_user_ignored(conn):
    assert effective_main_chat(
        conn, None, -999, enabled=False, user_id=500
    ) == -999


def test_flag_on_dm_user_no_membership_falls_back(conn):
    assert effective_main_chat(
        conn, None, -999, enabled=True, user_id=800
    ) == -999


def test_ws_ctx_takes_precedence_over_user_id(conn):
    # Групповой чат привязан к ws=1 → используем ws чата,
    # даже если юзер owner другого ws
    assert effective_main_chat(
        conn, _ws(1), -999, enabled=True, user_id=500
    ) == -100


# ── resolve_gate_chat (context-aware обёртка) ────────────────────

def _ctx(ws_ctx=None, *, no_attrs=False):
    if no_attrs:
        return object()  # ни chat_data ни user_data
    return SimpleNamespace(
        chat_data={'ws_ctx': ws_ctx}, user_data={'ws_ctx': ws_ctx}
    )


def test_gate_chat_flag_off_fallback(conn, monkeypatch):
    monkeypatch.setenv('H_RUNTIME_WS', '0')
    assert resolve_gate_chat(conn, _ctx(_ws(2)), -999) == -999


def test_gate_chat_flag_on_chat_based(conn, monkeypatch):
    monkeypatch.setenv('H_RUNTIME_WS', '1')
    assert resolve_gate_chat(conn, _ctx(_ws(2)), -999) == -300


def test_gate_chat_flag_on_user_based_dm(conn, monkeypatch):
    monkeypatch.setenv('H_RUNTIME_WS', '1')
    # ЛС регистрации: ws_ctx=None, user 500 owner ws=2
    assert resolve_gate_chat(conn, _ctx(None), -999, user_id=500) == -300


def test_gate_chat_context_without_attrs(conn, monkeypatch):
    monkeypatch.setenv('H_RUNTIME_WS', '1')
    # context без chat_data/user_data → ws_ctx None → user/fallback путь
    assert resolve_gate_chat(conn, _ctx(no_attrs=True), -999, user_id=500) == -300
    assert resolve_gate_chat(conn, _ctx(no_attrs=True), -999) == -999


# ── runtime_ws_enabled ───────────────────────────────────────────
# С M2 (V1.17.0k10) дефолт ON: multi-tenant gate работает без явной env.
# Флаг остался как kill-switch: H_RUNTIME_WS=0/false/no/off → принудительно OFF.

def test_flag_default_on(monkeypatch):
    monkeypatch.delenv('H_RUNTIME_WS', raising=False)
    assert runtime_ws_enabled() is True


@pytest.mark.parametrize('val', ['1', 'true', 'TRUE', 'yes', 'on', ' On '])
def test_flag_truthy_values(monkeypatch, val):
    monkeypatch.setenv('H_RUNTIME_WS', val)
    assert runtime_ws_enabled() is True


@pytest.mark.parametrize('val', ['0', 'false', 'FALSE', 'no', 'off', ' Off '])
def test_flag_killswitch_falsy_values(monkeypatch, val):
    monkeypatch.setenv('H_RUNTIME_WS', val)
    assert runtime_ws_enabled() is False


@pytest.mark.parametrize('val', ['', 'garbage', 'maybe'])
def test_flag_unknown_values_default_on(monkeypatch, val):
    """Пустое или мусорное значение трактуется как «не указано» → ON."""
    monkeypatch.setenv('H_RUNTIME_WS', val)
    assert runtime_ws_enabled() is True
