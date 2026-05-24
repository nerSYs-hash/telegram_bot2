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


# ── V1.17.0c (G): DELETE chat + DELETE workspace ──

def _disable_leave_chat(monkeypatch):
    """Замокать leaveChat чтобы не дёргать Telegram API во время тестов."""
    from api import workspaces_routes
    monkeypatch.setattr(workspaces_routes, '_bot_leave_chat', lambda cid: True)


def test_owner_can_disconnect_chat(client, monkeypatch):
    _disable_leave_chat(monkeypatch)
    r = client.delete('/api/workspaces/1/chats/-100',
                      headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    d = client.get('/api/workspaces/1', headers={'Authorization': 'Bearer fake-42'}).json()
    assert d['chats'] == []


def test_admin_cannot_disconnect_chat(client, monkeypatch):
    _disable_leave_chat(monkeypatch)
    r = client.delete('/api/workspaces/1/chats/-100',
                      headers={'Authorization': 'Bearer fake-100'})
    assert r.status_code == 403


def test_disconnect_chat_not_found(client, monkeypatch):
    _disable_leave_chat(monkeypatch)
    r = client.delete('/api/workspaces/1/chats/-99999',
                      headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 404


def test_owner_can_delete_workspace(client, monkeypatch):
    """Удаление НЕ-pulse сообщества. ws=2 (Other WS, не pulse-themed) с owner=99."""
    _disable_leave_chat(monkeypatch)
    r = client.delete('/api/workspaces/2',
                      headers={'Authorization': 'Bearer fake-99'})
    assert r.status_code == 200
    r2 = client.get('/api/workspaces/2', headers={'Authorization': 'Bearer fake-99'})
    assert r2.status_code == 404


def test_non_owner_cannot_delete_workspace(client, monkeypatch):
    _disable_leave_chat(monkeypatch)
    r = client.delete('/api/workspaces/1',
                      headers={'Authorization': 'Bearer fake-100'})
    assert r.status_code == 403


def test_delete_pulse_themed_forbidden(client, monkeypatch):
    """Pulse-themed ws нельзя удалить через API. Помечаем ws=1 как pulse-themed."""
    _disable_leave_chat(monkeypatch)
    from api import workspaces_routes
    workspaces_routes._db.conn.execute(
        "UPDATE workspaces SET is_pulse_themed=1 WHERE id=1"
    )
    workspaces_routes._db.conn.commit()
    r = client.delete('/api/workspaces/1',
                      headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 403


# ── V1.17.0i (P4): API отдаёт is_primary, active_chats_count, removed_at ──

def test_list_workspaces_exposes_new_keys(client):
    """Sanity: новые ключи присутствуют в JSON-ответе списка сообществ."""
    r = client.get('/api/workspaces', headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    ws_list = r.json()['workspaces']
    assert ws_list, "ожидаем хотя бы один workspace"
    sample = ws_list[0]
    for k in ('is_primary', 'active_chats_count', 'chats_count'):
        assert k in sample, f"ключ {k} обязан быть в API-ответе"


def test_workspace_details_chats_expose_removed_at_key(client):
    """Sanity: ключ removed_at присутствует у каждого чата (None на старой схеме)."""
    r = client.get('/api/workspaces/1', headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    for c in r.json()['chats']:
        assert 'removed_at' in c


def test_list_workspaces_primary_first_via_api():
    """C8: главное сообщество отдаётся первым через API даже если создано позже."""
    # Свежий клиент с двумя ws — secondary создан раньше, primary помечен флагом
    db_conn = sqlite3.connect(':memory:', check_same_thread=False)
    up_create_workspaces_tables(db_conn)
    db_conn.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT,
        role TEXT, added_at TEXT, removed_at TIMESTAMP
    )''')
    db_conn.execute('''CREATE TABLE users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT
    )''')
    db_conn.execute("INSERT INTO users VALUES (42, 'i', 'Илья')")
    secondary = create_workspace(db_conn, 'Доп', owner_user_id=42, is_pulse_themed=False)
    primary = create_workspace(db_conn, 'Главный', owner_user_id=42, is_pulse_themed=True)
    add_bot_chat(db_conn, -2, secondary, 42, 'B', 'group')
    add_bot_chat(db_conn, -1, primary, 42, 'A', 'group')
    db_conn.commit()

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
            return {'user_id': row[0], 'username': row[1], 'first_name': row[2]} if row else None

    def fake_require_auth(authorization):
        if not authorization:
            raise HTTPException(status_code=401, detail="No auth")
        token = authorization.replace('Bearer ', '')
        return {'user_id': int(token[5:])}

    _setup(_DB(db_conn), fake_require_auth)
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)

    r = c.get('/api/workspaces', headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    ids = [w['id'] for w in r.json()['workspaces']]
    assert ids == [primary, secondary], f"primary={primary} должен быть первым, получили {ids}"
    assert r.json()['workspaces'][0]['is_primary'] is True
    assert r.json()['workspaces'][1]['is_primary'] is False


def test_workspace_details_removed_chat_active_first_via_api():
    """C6: через API soft-removed чат идёт после активного + removed_at не None."""
    from database.db_workspaces import soft_remove_bot_chat
    db_conn = sqlite3.connect(':memory:', check_same_thread=False)
    up_create_workspaces_tables(db_conn)
    db_conn.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT,
        role TEXT, added_at TEXT, removed_at TIMESTAMP
    )''')
    db_conn.execute('CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT)')
    db_conn.execute("INSERT INTO users VALUES (42,'i','И')")
    ws = create_workspace(db_conn, 'X', owner_user_id=42)
    add_bot_chat(db_conn, -1, ws, 42, 'Removed', 'group', role='main')
    add_bot_chat(db_conn, -2, ws, 42, 'Active',  'group', role='admin')
    soft_remove_bot_chat(db_conn, -1)
    db_conn.commit()

    from api.workspaces_routes import router, _setup

    class _DB:
        def __init__(self, c):
            self.conn = c; self.cursor = c.cursor()

        def get_workspace_by_chat(self, chat_id):
            from database.db_workspaces import get_workspace_by_chat
            return get_workspace_by_chat(self.conn, chat_id)

        def get_site_user(self, user_id):
            row = self.conn.execute(
                "SELECT user_id, username, first_name FROM users WHERE user_id=?", (user_id,)
            ).fetchone()
            return {'user_id': row[0], 'username': row[1], 'first_name': row[2]} if row else None

    def fake_require_auth(authorization):
        return {'user_id': int(authorization.replace('Bearer ', '')[5:])}

    _setup(_DB(db_conn), fake_require_auth)
    app = FastAPI(); app.include_router(router)
    c = TestClient(app)

    data = c.get(f'/api/workspaces/{ws}', headers={'Authorization': 'Bearer fake-42'}).json()
    titles = [ch['title'] for ch in data['chats']]
    assert titles == ['Active', 'Removed'], f"активный должен быть первым, {titles}"
    removed = next(ch for ch in data['chats'] if ch['title'] == 'Removed')
    active = next(ch for ch in data['chats'] if ch['title'] == 'Active')
    assert removed['removed_at'] is not None
    assert active['removed_at'] is None

