# tests/test_ws_role.py
import sqlite3
import pytest
from bot_core.ws_role import i_ws_rbac_enabled, resolve_bot_role, is_ws_owner, is_ws_admin


class _Ctx:
    """Фейк telegram context: ws_ctx в chat_data, как кладёт middleware."""
    def __init__(self, ws_id=None):
        self.chat_data = {}
        self.user_data = {}
        if ws_id is not None:
            self.chat_data['ws_ctx'] = type('WS', (), {'workspace_id': ws_id})()


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.execute("CREATE TABLE workspace_members (workspace_id INTEGER, user_id INTEGER, role TEXT)")
    c.execute("INSERT INTO workspace_members VALUES (1, 7536752126, 'owner')")
    c.execute("INSERT INTO workspace_members VALUES (7, 8376708692, 'owner')")
    c.execute("INSERT INTO workspace_members VALUES (7, 555, 'moderator')")
    c.commit()
    yield c
    c.close()


def test_flag_off_default(monkeypatch):
    monkeypatch.delenv('I_WS_RBAC', raising=False)
    assert i_ws_rbac_enabled() is False

@pytest.mark.parametrize('val', ['1', 'true', 'YES', 'on'])
def test_flag_on_truthy(monkeypatch, val):
    monkeypatch.setenv('I_WS_RBAC', val)
    assert i_ws_rbac_enabled() is True

def test_flag_off_resolve_returns_user(monkeypatch, conn):
    monkeypatch.delenv('I_WS_RBAC', raising=False)
    assert resolve_bot_role(_Ctx(7), 8376708692, conn=conn) == 'user'
    assert is_ws_owner(_Ctx(7), 8376708692, conn=conn) is False

def test_owner_in_own_ws_group(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    assert resolve_bot_role(_Ctx(7), 8376708692, conn=conn) == 'owner'
    assert is_ws_owner(_Ctx(7), 8376708692, conn=conn) is True

def test_owner_cross_ws_is_user(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    # Кирилл (owner ws=7) в Pulse-чате ws=1 → не owner
    assert resolve_bot_role(_Ctx(1), 8376708692, conn=conn) == 'user'

def test_pulse_owner_ws1(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    assert is_ws_owner(_Ctx(1), 7536752126, conn=conn) is True

def test_developer_god_mode(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    monkeypatch.setenv('DEVELOPER_ID', '999')
    # 999 не член ни одного ws, но developer → god-mode в любом ws
    assert resolve_bot_role(_Ctx(7), 999, conn=conn) == 'developer'
    assert is_ws_owner(_Ctx(7), 999, conn=conn) is True

def test_dm_resolves_ws_by_membership(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    # ЛС: ws_ctx нет → resolve_user_primary_workspace по членству → ws=7
    assert is_ws_owner(_Ctx(None), 8376708692, conn=conn) is True

def test_non_member_is_user(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    assert resolve_bot_role(_Ctx(7), 424242, conn=conn) == 'user'

def test_moderator_is_not_owner(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    # workspace_members.role='moderator' → resolve_ws_role -> 'admin'
    assert resolve_bot_role(_Ctx(7), 555, conn=conn) == 'admin'
    assert is_ws_owner(_Ctx(7), 555, conn=conn) is False


# ─── is_ws_admin (Этап A, V1.17.0L1) ───
def test_is_ws_admin_owner_true(monkeypatch, conn):
    """owner ws=7 — is_ws_admin=True в ws=7."""
    monkeypatch.setenv('I_WS_RBAC', '1')
    assert is_ws_admin(_Ctx(7), 8376708692, conn=conn) is True


def test_is_ws_admin_moderator_true(monkeypatch, conn):
    """moderator (= admin в permissions) ws=7 — is_ws_admin=True в ws=7."""
    monkeypatch.setenv('I_WS_RBAC', '1')
    assert is_ws_admin(_Ctx(7), 555, conn=conn) is True


def test_is_ws_admin_user_false(monkeypatch, conn):
    """plain user — is_ws_admin=False."""
    monkeypatch.setenv('I_WS_RBAC', '1')
    assert is_ws_admin(_Ctx(7), 424242, conn=conn) is False


def test_is_ws_admin_cross_ws_false(monkeypatch, conn):
    """owner ws=7 — is_ws_admin=False в ws=1 (он там не член)."""
    monkeypatch.setenv('I_WS_RBAC', '1')
    assert is_ws_admin(_Ctx(1), 8376708692, conn=conn) is False


def test_is_ws_admin_developer_true(monkeypatch, conn):
    """developer god-mode — is_ws_admin=True везде."""
    monkeypatch.setenv('I_WS_RBAC', '1')
    monkeypatch.setenv('DEVELOPER_ID', '999')
    assert is_ws_admin(_Ctx(7), 999, conn=conn) is True
    assert is_ws_admin(_Ctx(1), 999, conn=conn) is True


def test_is_ws_admin_flag_off_returns_false(monkeypatch, conn):
    """I_WS_RBAC=0 → is_ws_admin=False (caller уходит в legacy fallback)."""
    monkeypatch.delenv('I_WS_RBAC', raising=False)
    assert is_ws_admin(_Ctx(7), 8376708692, conn=conn) is False
