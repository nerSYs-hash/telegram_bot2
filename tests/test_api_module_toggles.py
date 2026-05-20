import sqlite3
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from database.migrations.module_toggles import up as up_modules
from api.modules_routes import router as modules_router, _setup as modules_setup


class _DB:
    def __init__(self, conn):
        self.conn = conn


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    up_modules(conn)
    # workspace_members нужен для _check_write_role — создаём минимально:
    conn.execute(
        "CREATE TABLE workspace_members (workspace_id INTEGER, user_id INTEGER, role TEXT)"
    )
    conn.execute("INSERT INTO workspace_members VALUES (1, 100, 'owner')")
    conn.execute("INSERT INTO workspace_members VALUES (1, 200, 'admin')")
    conn.execute("INSERT INTO workspace_members VALUES (1, 300, 'moderator')")
    conn.commit()

    app = FastAPI()

    # Тестовый require_auth: токен = user_id строкой.
    def require_auth(authorization: str) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "no auth")
        return {"user_id": int(authorization.split(" ", 1)[1])}

    modules_setup(_DB(conn), require_auth)
    app.include_router(modules_router)
    return TestClient(app)


def _h(uid):
    return {"Authorization": f"Bearer {uid}"}


def test_list_returns_all_modules_default_disabled(client):
    r = client.get("/api/workspaces/1/modules", headers=_h(100))
    assert r.status_code == 200
    items = r.json()
    assert any(m["id"] == "triggers" for m in items)
    assert all(m["is_enabled"] is False for m in items)


def test_owner_can_enable(client):
    r = client.post("/api/workspaces/1/modules/triggers/enable",
                    headers=_h(100), json={})
    assert r.status_code == 200
    assert r.json()["is_enabled"] is True


def test_admin_can_enable(client):
    r = client.post("/api/workspaces/1/modules/triggers/enable",
                    headers=_h(200), json={})
    assert r.status_code == 200


def test_moderator_cannot_enable(client):
    r = client.post("/api/workspaces/1/modules/triggers/enable",
                    headers=_h(300), json={})
    assert r.status_code == 403


def test_disable_requires_reason(client):
    client.post("/api/workspaces/1/modules/triggers/enable",
                headers=_h(100), json={})
    r = client.post("/api/workspaces/1/modules/triggers/disable",
                    headers=_h(100), json={"reason": ""})
    assert r.status_code == 400


def test_disable_with_reason_ok(client):
    client.post("/api/workspaces/1/modules/triggers/enable",
                headers=_h(100), json={})
    r = client.post("/api/workspaces/1/modules/triggers/disable",
                    headers=_h(100), json={"reason": "не нужен"})
    assert r.status_code == 200
    assert r.json()["is_enabled"] is False


def test_unknown_module_returns_404(client):
    r = client.post("/api/workspaces/1/modules/xxx_nope/enable",
                    headers=_h(100), json={})
    assert r.status_code == 404


def test_history_returns_records(client):
    client.post("/api/workspaces/1/modules/triggers/enable",
                headers=_h(100), json={})
    client.post("/api/workspaces/1/modules/triggers/disable",
                headers=_h(100), json={"reason": "test"})
    r = client.get("/api/workspaces/1/modules/triggers/history",
                   headers=_h(100))
    assert r.status_code == 200
    h = r.json()
    assert [x["action"] for x in h] == ["disable", "enable"]
