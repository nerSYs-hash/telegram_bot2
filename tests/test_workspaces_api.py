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
        added_by_user_id INTEGER, title TEXT, chat_type TEXT,
        role TEXT CHECK (role IS NULL OR role IN ('main','admin','journal')),
        added_at TEXT
    )''')
    conn.execute('''CREATE TABLE users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT
    )''')

    create_workspace(conn, 'My WS', owner_user_id=42)
    create_workspace(conn, 'Other WS', owner_user_id=99)
    add_member(conn, 1, 100, 'admin')   # 100 — admin в My WS
    add_bot_chat(conn, -100, 1, 42, 'My Main', 'supergroup')
    # site_users: 42 (owner), 100 (admin), 200 (потенциальный invitee) логинились на сайте
    conn.execute("INSERT INTO users (user_id, username, first_name) VALUES (42, 'vitya', 'Витя')")
    conn.execute("INSERT INTO users (user_id, username, first_name) VALUES (100, 'helper', 'Помощник')")
    conn.execute("INSERT INTO users (user_id, username, first_name) VALUES (200, 'newbie', 'Новенький')")
    conn.commit()

    from api.workspaces_routes import router, _setup

    class _DB:
        def __init__(self, c):
            self.conn = c
            self.cursor = c.cursor()

        def get_workspace_by_chat(self, chat_id):
            from database.db_workspaces import get_workspace_by_chat
            return get_workspace_by_chat(self.conn, chat_id)

        def get_site_user(self, user_id):
            row = self.conn.execute(
                "SELECT user_id, username, first_name FROM users WHERE user_id=?",
                (user_id,)
            ).fetchone()
            if not row:
                return None
            return {'user_id': row[0], 'username': row[1], 'first_name': row[2]}

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


def test_get_workspace_details(client):
    r = client.get('/api/workspaces/1', headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    data = r.json()
    assert data['workspace']['name'] == 'My WS'
    assert len(data['members']) == 2
    assert len(data['chats']) == 1
    assert data['chats'][0]['title'] == 'My Main'


def test_get_workspace_details_non_member_forbidden(client):
    r = client.get('/api/workspaces/1', headers={'Authorization': 'Bearer fake-555'})
    assert r.status_code == 404


def test_owner_can_add_admin(client):
    r = client.post(
        '/api/workspaces/1/members',
        json={'user_id': 200, 'role': 'admin'},
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 200


def test_non_owner_cannot_add_member(client):
    r = client.post(
        '/api/workspaces/1/members',
        json={'user_id': 300, 'role': 'admin'},
        headers={'Authorization': 'Bearer fake-100'}
    )
    assert r.status_code == 403


def test_add_member_invalid_role(client):
    r = client.post(
        '/api/workspaces/1/members',
        json={'user_id': 200, 'role': 'superadmin'},
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 400


def test_add_member_unknown_user(client):
    r = client.post(
        '/api/workspaces/1/members',
        json={'user_id': 999, 'role': 'admin'},
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 404


def test_owner_can_remove_admin(client):
    client.post(
        '/api/workspaces/1/members',
        json={'user_id': 200, 'role': 'admin'},
        headers={'Authorization': 'Bearer fake-42'}
    )
    r = client.delete(
        '/api/workspaces/1/members/200',
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 200


def test_owner_cannot_remove_self(client):
    r = client.delete(
        '/api/workspaces/1/members/42',
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 400


def test_owner_can_rename(client):
    r = client.patch(
        '/api/workspaces/1',
        json={'name': 'Renamed'},
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 200
    r2 = client.get('/api/workspaces/1', headers={'Authorization': 'Bearer fake-42'})
    assert r2.json()['workspace']['name'] == 'Renamed'


def test_admin_cannot_rename(client):
    r = client.patch(
        '/api/workspaces/1',
        json={'name': 'X'},
        headers={'Authorization': 'Bearer fake-100'}
    )
    assert r.status_code == 403


def test_rename_empty_name_400(client):
    r = client.patch(
        '/api/workspaces/1',
        json={'name': ''},
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 400


# ── V1.17.0c (F): PATCH /chats/{chat_id} role ──

def test_owner_can_set_chat_role(client):
    r = client.patch(
        '/api/workspaces/1/chats/-100',
        json={'role': 'main'},
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 200
    d = client.get('/api/workspaces/1', headers={'Authorization': 'Bearer fake-42'}).json()
    assert d['chats'][0]['role'] == 'main'


def test_owner_can_clear_chat_role(client):
    client.patch('/api/workspaces/1/chats/-100', json={'role': 'admin'},
                 headers={'Authorization': 'Bearer fake-42'})
    r = client.patch('/api/workspaces/1/chats/-100', json={'role': None},
                     headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    d = client.get('/api/workspaces/1', headers={'Authorization': 'Bearer fake-42'}).json()
    assert d['chats'][0]['role'] is None


def test_admin_cannot_set_chat_role(client):
    r = client.patch('/api/workspaces/1/chats/-100', json={'role': 'main'},
                     headers={'Authorization': 'Bearer fake-100'})
    assert r.status_code == 403


def test_invalid_chat_role_400(client):
    r = client.patch('/api/workspaces/1/chats/-100', json={'role': 'boss'},
                     headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 400


def test_chat_role_chat_not_found(client):
    r = client.patch('/api/workspaces/1/chats/-99999', json={'role': 'main'},
                     headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 404

