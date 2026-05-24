"""H3/e6: pulse_only DM-фоллбэк по членству юзера (за флагом H_RUNTIME_WS).

Чинит регрессию: @pulse_only-хендлеры (BBS-кнопка, donate, exit_survey,
horoscope, anketa_edit) в ЛС молча возвращали None — в личке chat.id не
в bot_chats, ws_ctx=None, pulse_only делал silent skip. Теперь при флаге
ON ws резолвится по workspace_members юзера. Флаг OFF → байт-в-байт старо.
"""
import sqlite3

import pytest

from bot_core.workspace_context import (
    WorkspaceContext,
    build_context_for_user,
    pulse_only,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.executescript(
        """
        CREATE TABLE workspaces (id INTEGER PRIMARY KEY,
            is_pulse_themed INTEGER NOT NULL DEFAULT 0, plan TEXT);
        CREATE TABLE workspace_members (workspace_id INTEGER, user_id INTEGER,
            role TEXT);
        INSERT INTO workspaces (id, is_pulse_themed, plan) VALUES
            (1, 1, 'pro'),     -- Pulse
            (2, 0, 'free');    -- не-Pulse тенант
        INSERT INTO workspace_members (workspace_id, user_id, role) VALUES
            (1, 500, 'owner'),     -- юзер Pulse
            (2, 600, 'owner');     -- юзер не-Pulse
        """
    )
    return c


class _FakeDB:
    def __init__(self, conn):
        self.conn = conn


class _FakeQuery:
    """Похож на telegram.CallbackQuery: .from_user.id."""
    def __init__(self, user_id):
        self.from_user = type('U', (), {'id': user_id})()


class _FakeContext:
    """Похож на PTB context: .bot_data['db'], .user_data/.chat_data."""
    def __init__(self, db):
        self.bot_data = {'db': db}
        self.user_data = {}
        self.chat_data = {}


# ── build_context_for_user (unit) ──────────────────────────────────────

def test_build_context_for_user_pulse(conn):
    ctx = build_context_for_user(conn, 500)
    assert ctx is not None
    assert ctx.workspace_id == 1
    assert ctx.is_pulse_themed is True
    assert ctx.member_role == 'owner'


def test_build_context_for_user_non_pulse(conn):
    ctx = build_context_for_user(conn, 600)
    assert ctx is not None
    assert ctx.workspace_id == 2
    assert ctx.is_pulse_themed is False


def test_build_context_for_user_no_membership(conn):
    assert build_context_for_user(conn, 999) is None


# ── pulse_only DM-фоллбэк за флагом ────────────────────────────────────

@pytest.fixture
def handler():
    @pulse_only
    async def h(query, context):
        return 'RAN'
    return h


@pytest.mark.asyncio
async def test_flag_off_dm_skips_byte_identical(conn, handler, monkeypatch):
    """Флаг OFF: даже если юзер — owner Pulse, в ЛС ws_ctx=None →
    silent skip как было до e6 (регресс невозможен)."""
    monkeypatch.delenv('H_RUNTIME_WS', raising=False)
    q, c = _FakeQuery(500), _FakeContext(_FakeDB(conn))
    assert await handler(q, c) is None


@pytest.mark.asyncio
async def test_flag_on_dm_pulse_user_runs(conn, handler, monkeypatch):
    """Флаг ON: owner Pulse в ЛС → ws резолвится по членству → handler РАБОТАЕТ."""
    monkeypatch.setenv('H_RUNTIME_WS', '1')
    q, c = _FakeQuery(500), _FakeContext(_FakeDB(conn))
    assert await handler(q, c) == 'RAN'


@pytest.mark.asyncio
async def test_flag_on_dm_non_pulse_user_skips(conn, handler, monkeypatch):
    """Флаг ON: юзер не-Pulse тенанта → is_pulse_themed=False → skip."""
    monkeypatch.setenv('H_RUNTIME_WS', '1')
    q, c = _FakeQuery(600), _FakeContext(_FakeDB(conn))
    assert await handler(q, c) is None


@pytest.mark.asyncio
async def test_flag_on_dm_no_membership_skips(conn, handler, monkeypatch):
    """Флаг ON: юзер без членства → Pulse-safe skip (нет утечки)."""
    monkeypatch.setenv('H_RUNTIME_WS', '1')
    q, c = _FakeQuery(999), _FakeContext(_FakeDB(conn))
    assert await handler(q, c) is None


@pytest.mark.asyncio
async def test_flag_on_existing_chat_ctx_unchanged(conn, handler, monkeypatch):
    """Флаг ON, но ws_ctx уже есть из чата (групповой Pulse) → штатный путь,
    user-резолв НЕ дергается."""
    monkeypatch.setenv('H_RUNTIME_WS', '1')
    q = _FakeQuery(500)
    c = _FakeContext(_FakeDB(conn))
    c.chat_data['ws_ctx'] = WorkspaceContext(
        workspace_id=1, is_pulse_themed=True, plan='pro')
    assert await handler(q, c) == 'RAN'
