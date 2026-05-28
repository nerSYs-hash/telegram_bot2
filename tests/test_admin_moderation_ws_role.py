"""Этап A T6: admin_moderation глобальные `user_id == OWNER_ID` через ws_role.

Проверка _is_strict_owner(context, user_id) — гейт для panel_deputy_* и др.
"""
import sqlite3
import pytest


def _make_db(tmp_path, monkeypatch, members=()):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    conn = sqlite3.connect(db_path)
    conn.executescript("""
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


def test_strict_owner_ws_owner_true(monkeypatch, tmp_path):
    """I_WS_RBAC=1: owner ws=1 — strict_owner=True в ws=1."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner')])

    from handlers.admin_moderation import _is_strict_owner
    assert _is_strict_owner(_Ctx(1), 100, conn=conn) is True
    conn.close()


def test_strict_owner_other_ws_owner_false(monkeypatch, tmp_path):
    """owner ws=2 — strict_owner=False в ws=1 (cross-ws)."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner'), (2, 200, 'owner')])

    from handlers.admin_moderation import _is_strict_owner
    assert _is_strict_owner(_Ctx(1), 200, conn=conn) is False
    conn.close()


def test_strict_owner_deputy_false(monkeypatch, tmp_path):
    """admin (моderator-role) — НЕ strict_owner (только владелец назначает замов)."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db(tmp_path, monkeypatch, [(1, 100, 'owner'), (1, 300, 'admin')])

    from handlers.admin_moderation import _is_strict_owner
    assert _is_strict_owner(_Ctx(1), 300, conn=conn) is False
    conn.close()


def test_strict_owner_legacy_fallback(monkeypatch, tmp_path, mocker=None):
    """I_WS_RBAC=0 / нет context: fallback user_id == OWNER_ID."""
    monkeypatch.delenv("I_WS_RBAC", raising=False)
    # OWNER_ID импортируется из config — мокаем
    import config
    monkeypatch.setattr(config, "OWNER_ID", 999, raising=False)

    from handlers.admin_moderation import _is_strict_owner
    assert _is_strict_owner(_Ctx(None), 999) is True
    assert _is_strict_owner(_Ctx(None), 555) is False
