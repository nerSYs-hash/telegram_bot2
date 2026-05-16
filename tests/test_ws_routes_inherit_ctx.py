# tests/test_ws_routes_inherit_ctx.py
"""T5: economy/titles/PR роутеры наследуют per-WS роль через ContextVar.

api.py и пакет api/ носят одно имя → грузим app из файла по пути
(как в test_ws_auth_middleware.py).
"""
import importlib.util
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_api_app():
    path = os.path.join(_REPO, "api.py")
    spec = importlib.util.spec_from_file_location("apiapp", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeDB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()

    def get_user(self, user_id):
        return None

    def get_site_user(self, user_id):
        return None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVELOPER_ID", "555")
    monkeypatch.setenv("MAIN_ADMIN_ID", "0")
    monkeypatch.setenv("JWT_SECRET", "testsecret")

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    from database.migrations.multi_tenancy import up_create_workspaces_tables
    from database.db_workspaces import create_workspace, add_member
    up_create_workspaces_tables(conn)
    create_workspace(conn, "WS1", owner_user_id=42)
    add_member(conn, 1, 101, "moderator")
    conn.commit()

    import permissions
    perm_db = str(tmp_path / "pulse_bot.db")
    monkeypatch.setattr(permissions, "_db_path", lambda: perm_db)
    permissions.init_permissions_db(perm_db)
    permissions.invalidate_cache()

    api_mod = _load_api_app()
    api_mod.db = _FakeDB(conn)
    return TestClient(api_mod.app, raise_server_exceptions=False), api_mod


def _tok(api_mod, uid):
    return api_mod._make_jwt({"user_id": uid, "username": "", "first_name": "",
                              "photo_url": "", "is_admin": False, "is_owner": False})


def test_titles_create_denied_for_moderator(client):
    """101 = moderator -> permissions 'admin' -> нет titles create."""
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 101)}", "X-Workspace-Id": "1",
         "Content-Type": "application/json"}
    r = c.post("/api/titles/packages", headers=h, json={"name": "X"})
    assert r.status_code in (403, 422)


def test_titles_route_role_gate_passes_for_owner(client):
    """Owner 42 проходит ролевой гейт (не 401/403 от middleware/permission)."""
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 42)}", "X-Workspace-Id": "1"}
    r = c.get("/api/titles/packages", headers=h)
    # Ролевой гейт пройден: НЕ 401 (auth) и НЕ 403 (membership/permission).
    assert r.status_code not in (401, 403)
