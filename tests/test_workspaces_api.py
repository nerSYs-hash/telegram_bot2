"""Тесты API /api/workspaces/*."""
import sqlite3
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import create_workspace, add_member, add_bot_chat


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / 'test.db'
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    up_create_workspaces_tables(conn)
    conn.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL DEFAULT 1,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT, added_at TEXT
    )''')
    conn.execute('''CREATE TABLE users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT
    )''')

    create_workspace(conn, 'My WS', owner_user_id=42)
    create_workspace(conn, 'Other WS', owner_user_id=99)
    add_member(conn, 1, 100, 'admin')   # 100 — admin в My WS
    add_bot_chat(conn, -100, 1, 42, 'My Main', 'supergroup')
    conn.commit()

    from api.workspaces_routes import router, _setup

    class _DB:
        def __init__(self, c):
            self.conn = c
            self.cursor = c.cursor()

        def get_workspace_by_chat(self, chat_id):
            from database.db_workspaces import get_workspace_by_chat
            return get_workspace_by_chat(self.conn, chat_id)

    fake_db = _DB(conn)

    def fake_require_auth(authorization):
        if not authorization:
            raise HTTPException(status_code=401, detail="No auth")
        token = authorization.replace('Bearer ', '')
        if not token.startswith('fake-'):
            raise HTTPException(status_code=401, detail="Bad token")
        return {'user_id': int(token[5:])}

    _setup(fake_db, fake_require_auth)

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_get_workspaces_returns_only_user_membered(client):
    r = client.get('/api/workspaces', headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    data = r.json()
    assert len(data['workspaces']) == 1
    assert data['workspaces'][0]['name'] == 'My WS'
    assert data['workspaces'][0]['role'] == 'owner'


def test_get_workspaces_admin_role(client):
    r = client.get('/api/workspaces', headers={'Authorization': 'Bearer fake-100'})
    assert r.status_code == 200
    data = r.json()
    assert len(data['workspaces']) == 1
    assert data['workspaces'][0]['role'] == 'admin'


def test_get_workspaces_no_auth(client):
    r = client.get('/api/workspaces')
    assert r.status_code == 401


def test_get_workspaces_empty_for_new_user(client):
    r = client.get('/api/workspaces', headers={'Authorization': 'Bearer fake-555'})
    assert r.status_code == 200
    assert r.json()['workspaces'] == []
