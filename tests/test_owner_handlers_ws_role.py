"""Этап A T2: handlers/owner_handlers._is_owner per-ws через bot_core.ws_role.

Проверяет что:
- I_WS_RBAC=1: per-ws (owner ws=1 — owner; owner ws=2 — НЕ owner в ws=1).
- I_WS_RBAC=0: legacy (admin_id из .env, DEVELOPER_ID, users.is_owner=1).
"""
import sqlite3
import pytest


def _make_db(tmp_path, monkeypatch, members=()):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            is_admin INTEGER DEFAULT 0,
            is_owner INTEGER DEFAULT 0,
            username TEXT,
            first_name TEXT
        );
        CREATE TABLE workspace_members (
            workspace_id INTEGER,
            user_id INTEGER,
            role TEXT,
            PRIMARY KEY(workspace_id, user_id)
        );
    """)
    for ws_id, uid, role in members:
        conn.execute("INSERT INTO workspace_members VALUES (?, ?, ?)", (ws_id, uid, role))
    conn.commit()
    return conn


class _Ctx:
    """Фейк telegram context: ws_ctx в chat_data, как кладёт middleware."""
    def __init__(self, ws_id=None):
        self.chat_data = {}
        self.user_data = {}
        if ws_id is not None:
            self.chat_data['ws_ctx'] = type('WS', (), {'workspace_id': ws_id})()


class _DB:
    def __init__(self, conn):
        self.cursor = conn.cursor()
        self.conn = conn

    def get_user(self, uid):
        row = self.cursor.execute(
            "SELECT user_id, is_admin, is_owner FROM users WHERE user_id=?", (uid,)
        ).fetchone()
        if not row:
            return None
        return {'user_id': row[0], 'is_admin': row[1], 'is_owner': row[2]}


# ─── I_WS_RBAC=1 (per-ws) ───
def test_owner_in_own_ws_can_open_panel(monkeypatch, tmp_path):
    """Owner ws=1 (Илья) — _is_owner=True в ws=1."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner'), (2, 200, 'owner')])

    from handlers.owner_handlers import _is_owner
    ctx = _Ctx(1)
    assert _is_owner(_DB(conn), 100, admin_id=999, context=ctx, conn=conn) is True
    conn.close()


def test_owner_of_other_ws_cant_open_panel_here(monkeypatch, tmp_path):
    """Owner ws=2 в чате ws=1 — _is_owner=False (cross-ws изоляция)."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner'), (2, 200, 'owner')])

    from handlers.owner_handlers import _is_owner
    ctx_ws1 = _Ctx(1)
    assert _is_owner(_DB(conn), 200, admin_id=999, context=ctx_ws1, conn=conn) is False
    conn.close()


def test_plain_user_not_owner(monkeypatch, tmp_path):
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner')])

    from handlers.owner_handlers import _is_owner
    ctx = _Ctx(1)
    assert _is_owner(_DB(conn), 500, admin_id=999, context=ctx, conn=conn) is False
    conn.close()


# ─── I_WS_RBAC=0 (legacy) ───
def test_legacy_admin_id_match(monkeypatch, tmp_path):
    """I_WS_RBAC=0: user_id == admin_id → True (как раньше)."""
    monkeypatch.delenv("I_WS_RBAC", raising=False)
    conn = _make_db(tmp_path, monkeypatch)

    from handlers.owner_handlers import _is_owner
    ctx = _Ctx(None)
    assert _is_owner(_DB(conn), 999, admin_id=999, context=ctx, conn=conn) is True
    conn.close()


def test_legacy_is_owner_flag(monkeypatch, tmp_path):
    """I_WS_RBAC=0: users.is_owner=1 → True."""
    monkeypatch.delenv("I_WS_RBAC", raising=False)
    conn = _make_db(tmp_path, monkeypatch)
    conn.execute("INSERT INTO users (user_id, is_owner) VALUES (100, 1)")
    conn.commit()

    from handlers.owner_handlers import _is_owner
    ctx = _Ctx(None)
    assert _is_owner(_DB(conn), 100, admin_id=999, context=ctx, conn=conn) is True
    conn.close()


def test_legacy_no_context_still_works(monkeypatch, tmp_path):
    """Backward-compat: вызов без context= должен работать (legacy)."""
    monkeypatch.delenv("I_WS_RBAC", raising=False)
    conn = _make_db(tmp_path, monkeypatch)
    conn.execute("INSERT INTO users (user_id, is_owner) VALUES (100, 1)")
    conn.commit()

    from handlers.owner_handlers import _is_owner
    assert _is_owner(_DB(conn), 100, admin_id=999) is True  # без context
    conn.close()
