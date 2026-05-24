"""V1.17.0j4: тесты GET /api/workspaces/{ws}/icon.jpg — auth + флаг + 404/200."""
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import create_workspace


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS", "1")
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    up_create_workspaces_tables(conn)
    # icon-колонки
    conn.execute("ALTER TABLE workspaces ADD COLUMN icon_file_id TEXT")
    conn.execute("ALTER TABLE workspaces ADD COLUMN icon_cached_at TIMESTAMP")
    conn.execute("ALTER TABLE workspaces ADD COLUMN icon_source TEXT DEFAULT 'tg'")
    conn.execute("ALTER TABLE workspaces ADD COLUMN icon_local_path TEXT")
    conn.execute('''CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY,
        workspace_id INTEGER, role TEXT, removed_at TIMESTAMP, added_at TEXT,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT)''')
    ws = create_workspace(conn, 'W', owner_user_id=42)
    conn.commit()

    from api.workspaces_routes import router, _setup

    class _DB:
        def __init__(self, c):
            self.conn = c
            self.cursor = c.cursor()

        def get_site_user(self, uid):
            return {'user_id': uid}

        def get_workspace_by_chat(self, chat_id):
            from database.db_workspaces import get_workspace_by_chat
            return get_workspace_by_chat(self.conn, chat_id)

    def fake_auth(authorization):
        if not authorization:
            raise HTTPException(status_code=401, detail="No auth")
        return {'user_id': int(authorization.replace('Bearer fake-', ''))}

    _setup(_DB(conn), fake_auth)
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app), conn, ws, tmp_path


def test_icon_404_when_no_cached_file(client):
    c, _, ws, _ = client
    r = c.get(f'/api/workspaces/{ws}/icon.jpg',
              headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 404


def test_icon_200_when_cached_file_exists(client):
    c, conn, ws, tmp = client
    p = Path(tmp) / f"{ws}.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0FAKEJPEG")
    conn.execute(
        "UPDATE workspaces SET icon_local_path=?, icon_cached_at=CURRENT_TIMESTAMP WHERE id=?",
        (str(p), ws)
    )
    conn.commit()
    r = c.get(f'/api/workspaces/{ws}/icon.jpg',
              headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('image/')
    # Cache-Control должен быть private (auth-protected)
    assert 'private' in r.headers.get('cache-control', '').lower()


def test_icon_401_no_auth(client):
    c, _, ws, _ = client
    assert c.get(f'/api/workspaces/{ws}/icon.jpg').status_code == 401


def test_icon_404_non_member(client):
    c, _, ws, _ = client
    r = c.get(f'/api/workspaces/{ws}/icon.jpg',
              headers={'Authorization': 'Bearer fake-999'})
    assert r.status_code == 404


def test_icon_404_when_flag_off(client, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS", "0")
    c, conn, ws, tmp = client
    p = Path(tmp) / f"{ws}.jpg"
    p.write_bytes(b"\xff\xd8FAKE")
    conn.execute("UPDATE workspaces SET icon_local_path=? WHERE id=?",
                 (str(p), ws))
    conn.commit()
    r = c.get(f'/api/workspaces/{ws}/icon.jpg',
              headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 404


def test_icon_404_when_path_in_db_but_file_missing(client):
    c, conn, ws, tmp = client
    conn.execute(
        "UPDATE workspaces SET icon_local_path=?, icon_cached_at=CURRENT_TIMESTAMP WHERE id=?",
        (str(Path(tmp) / "nonexistent.jpg"), ws)
    )
    conn.commit()
    r = c.get(f'/api/workspaces/{ws}/icon.jpg',
              headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 404
