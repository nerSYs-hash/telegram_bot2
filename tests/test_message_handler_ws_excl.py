"""Этап A T7: message_handler.is_user_excluded per-ws.

Сейчас exclusion использует глобальные user_data['is_admin']/['is_owner']
из БД — что для multi-tenant неправильно (админ ws=1 не должен быть
excluded в ws=2). Переводим на is_ws_admin(context, user_id) при I_WS_RBAC=1.
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
            workspace_id INTEGER, user_id INTEGER, role TEXT,
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


def _make_mh(conn, main_admin_id=999, excluded=()):
    """Лёгкая фабрика MessageHandler — без реального бота."""
    from handlers.message_handler import MessageHandler
    # MessageHandler.__init__ требует много — обходим, создаём как proxy
    mh = MessageHandler.__new__(MessageHandler)
    mh.db = _DB(conn)
    mh.main_admin_id = main_admin_id
    mh.excluded_user_ids = set(excluded)
    return mh


def test_excluded_owner_in_own_ws_via_ws_role(monkeypatch, tmp_path):
    """I_WS_RBAC=1: owner ws=1 — excluded в ws=1 (his own chat)."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner')])
    mh = _make_mh(conn)
    excluded, reason = mh.is_user_excluded(100, mh.db.get_user(100), context=_Ctx(1), conn=conn)
    assert excluded is True
    conn.close()


def test_excluded_owner_of_other_ws_not_in_this_ws(monkeypatch, tmp_path):
    """Cross-ws: owner ws=2 в чате ws=1 — НЕ excluded (он там гость)."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner'), (2, 200, 'owner')])
    # user_data НЕ имеет is_admin/is_owner — это plain row.
    conn.execute("INSERT INTO users (user_id, is_admin, is_owner) VALUES (200, 0, 0)")
    conn.commit()
    mh = _make_mh(conn)
    excluded, reason = mh.is_user_excluded(200, mh.db.get_user(200), context=_Ctx(1), conn=conn)
    assert excluded is False  # КРИТЕРИЙ: cross-ws владелец НЕ excluded в чужом чате
    conn.close()


def test_excluded_main_admin_id_legacy_still_works(monkeypatch, tmp_path):
    """main_admin_id из конструктора всё ещё excluded (Илья god-mode)."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch)
    mh = _make_mh(conn, main_admin_id=999)
    excluded, reason = mh.is_user_excluded(999, None, context=_Ctx(1), conn=conn)
    assert excluded is True
    assert reason in ("main_admin_id", "ws_role")  # любой положительный результат
    conn.close()


def test_excluded_explicit_list(monkeypatch, tmp_path):
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch)
    mh = _make_mh(conn, excluded={555})
    excluded, reason = mh.is_user_excluded(555, None, context=_Ctx(1), conn=conn)
    assert excluded is True
    assert reason == "excluded_list"
    conn.close()


def test_legacy_flag_off_uses_db_flags(monkeypatch, tmp_path):
    """I_WS_RBAC=0: старая логика — user_data['is_admin']/['is_owner']."""
    monkeypatch.delenv("I_WS_RBAC", raising=False)
    conn = _make_db(tmp_path, monkeypatch)
    conn.execute("INSERT INTO users (user_id, is_admin, is_owner) VALUES (100, 1, 0)")
    conn.commit()
    mh = _make_mh(conn)
    excluded, reason = mh.is_user_excluded(100, mh.db.get_user(100))
    assert excluded is True
    assert reason == "database_flag"
    conn.close()


def test_no_context_uses_db_flags_too(monkeypatch, tmp_path):
    """Backward-compat: вызов без context работает (legacy путь)."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch)
    conn.execute("INSERT INTO users (user_id, is_admin, is_owner) VALUES (100, 0, 1)")
    conn.commit()
    mh = _make_mh(conn)
    excluded, reason = mh.is_user_excluded(100, mh.db.get_user(100))  # без context
    assert excluded is True
    assert reason == "database_flag"
    conn.close()
