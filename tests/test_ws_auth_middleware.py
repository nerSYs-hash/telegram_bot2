# tests/test_ws_auth_middleware.py
"""API-level тесты ws_context_middleware + per-WS profile/owner.

api.py и пакет api/ носят одно имя → `import api` берёт ПАКЕТ.
Поэтому само FastAPI-приложение грузим из файла по пути.
"""
import importlib.util
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_api_app():
    """Грузит api.py (файл с FastAPI app) под именем 'apiapp'."""
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
    create_workspace(conn, "WS1", owner_user_id=42)   # ws1 owner 42
    create_workspace(conn, "WS2", owner_user_id=99)   # ws2 owner 99
    add_member(conn, 1, 100, "moderator")
    conn.commit()

    # permissions.py использует свой pulse_bot.db — направляем на tmp и сидим дефолты
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


# ── Task 2 ──

def test_non_member_blocked_cross_tenant(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 42)}", "X-Workspace-Id": "2"}
    r = c.get("/api/admin/profile/me", headers=h)
    assert r.status_code == 403

def test_member_allowed_in_own_ws(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 42)}", "X-Workspace-Id": "1"}
    r = c.get("/api/admin/profile/me", headers=h)
    assert r.status_code == 200
    assert r.json()["role_raw"] == "owner"

def test_developer_bypasses_membership(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 555)}", "X-Workspace-Id": "2"}
    r = c.get("/api/admin/profile/me", headers=h)
    assert r.status_code == 200
    assert r.json()["role_raw"] == "developer"

def test_auth_endpoints_skip_ws_check(client):
    c, api_mod = client
    r = c.get("/api/auth/config")
    assert r.status_code == 200


# ── Task 3 ──

def test_moderator_sees_admin_role_in_profile(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 100)}", "X-Workspace-Id": "1"}
    r = c.get("/api/admin/profile/me", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["role_raw"] == "admin"          # moderator -> admin mapping
    assert "moderation.view" in body["permissions"]
    assert "economy.cancel" not in body["permissions"]


# ── Task 4 ──

def test_auth_telegram_no_global_owner_for_main_admin(client, monkeypatch):
    c, api_mod = client
    import time as _t
    monkeypatch.setattr(api_mod, "_verify_tg_hash", lambda d: True)
    r = c.post("/api/auth/telegram", json={"id": 12345, "auth_date": int(_t.time())})
    assert r.status_code == 200
    assert r.json()["is_owner"] is False

def test_require_owner_uses_ws_role(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 100)}", "X-Workspace-Id": "1",
         "Content-Type": "application/json"}
    r = c.put("/api/admin/permissions/roles/admin", headers=h,
              json={"permissions": ["triggers.view"]})
    assert r.status_code == 403
    h2 = {"Authorization": f"Bearer {_tok(api_mod, 42)}", "X-Workspace-Id": "1",
          "Content-Type": "application/json"}
    r2 = c.put("/api/admin/permissions/roles/admin", headers=h2,
               json={"permissions": ["triggers.view"]})
    assert r2.status_code == 200


# ── d13: 2-й владелец без X-Workspace-Id резолвится в свой ws (не 403) ──

def test_second_owner_no_header_resolves_own_ws(client):
    """99 — owner ws2, НЕ член ws1. Запрос БЕЗ X-Workspace-Id не должен
    хардкодиться в ws=1 → 403. Должен резолвиться в ws2 (его сообщество)."""
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 99)}"}   # без X-Workspace-Id
    r = c.get("/api/admin/profile/me", headers=h)
    assert r.status_code == 200
    assert r.json()["role_raw"] == "owner"
    # permissions/catalog без заголовка — тоже не 403 (это и был баг d13)
    r2 = c.get("/api/admin/permissions/catalog", headers=h)
    assert r2.status_code == 200

def test_second_owner_explicit_foreign_ws_still_403(client):
    """Защита не ослабла: 99 с явным X-Workspace-Id=1 (чужой ws) → 403."""
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 99)}", "X-Workspace-Id": "1"}
    r = c.get("/api/admin/profile/me", headers=h)
    assert r.status_code == 403
