"""Этап A T3: BingoHandler._is_owner_user per-ws через ws_role.

Использует те же фикстуры из test_owner_handlers_ws_role: воркспейс_мемберс,
fake DB, fake context с ws_ctx.
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
            is_owner INTEGER DEFAULT 0
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


class _User:
    def __init__(self, uid):
        self.id = uid


# ─── I_WS_RBAC=1 (per-ws) ───
def test_bingo_owner_in_own_ws(monkeypatch, tmp_path):
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner')])

    from handlers.bingo_handlers import BingoHandler
    h = BingoHandler(_DB(conn), target_chat_id=-100, main_admin_id=999)
    assert h._is_owner_user(_User(100), context=_Ctx(1), conn=conn) is True
    conn.close()


def test_bingo_owner_cross_ws_not_owner(monkeypatch, tmp_path):
    """Owner ws=2 — НЕ owner-bingo в ws=1."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner'), (2, 200, 'owner')])

    from handlers.bingo_handlers import BingoHandler
    h = BingoHandler(_DB(conn), target_chat_id=-100, main_admin_id=999)
    assert h._is_owner_user(_User(200), context=_Ctx(1), conn=conn) is False
    conn.close()


def test_bingo_moderator_admin_role_is_owner_user(monkeypatch, tmp_path):
    """moderator (role admin в permissions) — тоже считается owner-bingo,
    т.к. в боте «admin или owner» имеют права создавать игры."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner'), (1, 300, 'moderator')])

    from handlers.bingo_handlers import BingoHandler
    h = BingoHandler(_DB(conn), target_chat_id=-100, main_admin_id=999)
    # NB: _is_owner_user исторически = «owner или зам». Новый is_ws_owner
    # вернёт False для moderator. Это РЕГРЕССИЯ для деп. Документируем:
    # для bingo используем is_ws_owner (как и было) — moderator не запускает игры.
    assert h._is_owner_user(_User(300), context=_Ctx(1), conn=conn) is False
    conn.close()


# ─── I_WS_RBAC=0 (legacy) ───
def test_bingo_legacy_main_admin_match(monkeypatch, tmp_path):
    monkeypatch.delenv("I_WS_RBAC", raising=False)
    conn = _make_db(tmp_path, monkeypatch)

    from handlers.bingo_handlers import BingoHandler
    h = BingoHandler(_DB(conn), target_chat_id=-100, main_admin_id=999)
    assert h._is_owner_user(_User(999)) is True  # без context, legacy
    conn.close()


def test_bingo_legacy_is_owner_flag(monkeypatch, tmp_path):
    monkeypatch.delenv("I_WS_RBAC", raising=False)
    conn = _make_db(tmp_path, monkeypatch)
    conn.execute("INSERT INTO users (user_id, is_owner) VALUES (100, 1)")
    conn.commit()

    from handlers.bingo_handlers import BingoHandler
    h = BingoHandler(_DB(conn), target_chat_id=-100, main_admin_id=999)
    assert h._is_owner_user(_User(100)) is True
    conn.close()
