"""Route-level cross-ws isolation для /api/economy/*.

После V1.17.0k1: роутер достаёт workspace_id из WS_ID_CTX (ставит
ws_context_middleware из X-Workspace-Id), а не из placeholder=1.
Тест доказывает, что владелец ws=2 видит данные ws=2 и НЕ видит ws=1.

Тестовая инфраструктура — как в test_ws_routes_inherit_ctx.py
(file-based импорт api.py, in-memory SQLite, monkeypatch permissions).
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


def _ensure_economy_tables(conn):
    """Создаём ровно те колонки, на которые опирается get_econ_settings."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS economy_settings (
            workspace_id INTEGER NOT NULL DEFAULT 1,
            key TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            label TEXT NOT NULL,
            description TEXT,
            value TEXT NOT NULL,
            value_type TEXT NOT NULL,
            unit TEXT DEFAULT '',
            min_value REAL,
            max_value REAL,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            is_hidden INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            topic_scope TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (workspace_id, key)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS economy_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL DEFAULT 1,
            setting_key TEXT NOT NULL,
            action TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            old_enabled INTEGER,
            new_enabled INTEGER,
            comment TEXT NOT NULL,
            changed_by INTEGER NOT NULL,
            changed_by_role TEXT NOT NULL,
            rollback_of INTEGER,
            changed_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS economy_section_toggles (
            workspace_id INTEGER NOT NULL DEFAULT 1,
            category TEXT NOT NULL,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            updated_by INTEGER,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (workspace_id, category)
        )
    """)
    conn.commit()


def _seed(conn, ws, key):
    conn.execute(
        "INSERT INTO economy_settings (workspace_id, key, category, label, value, value_type) "
        "VALUES (?, ?, 'mining', ?, '1.0', 'float')",
        (ws, key, f"label-{key}")
    )
    conn.commit()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVELOPER_ID", "555")
    monkeypatch.setenv("MAIN_ADMIN_ID", "0")
    monkeypatch.setenv("JWT_SECRET", "testsecret")

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    from database.migrations.multi_tenancy import up_create_workspaces_tables
    from database.db_workspaces import create_workspace, add_member
    up_create_workspaces_tables(conn)
    _ensure_economy_tables(conn)

    # ws=1 c owner=42; ws=2 c owner=99
    create_workspace(conn, "WS1", owner_user_id=42)
    create_workspace(conn, "WS2", owner_user_id=99)
    conn.commit()

    _seed(conn, 1, "test.ws1_only")
    _seed(conn, 2, "test.ws2_only")

    import permissions
    perm_db = str(tmp_path / "pulse_bot.db")
    monkeypatch.setattr(permissions, "_db_path", lambda: perm_db)
    permissions.init_permissions_db(perm_db)
    permissions.invalidate_cache()

    api_mod = _load_api_app()
    fake_db = _FakeDB(conn)
    api_mod.db = fake_db

    # _economy_setup был вызван при импорте api.py c РЕАЛЬНОЙ db —
    # переинъектируем fake_db в роутер, иначе get_econ_settings
    # читает прод-таблицу.
    from api.economy_routes import _setup as _economy_setup_fn
    from api.economy_ws import manager as _real_mgr
    _economy_setup_fn(fake_db, api_mod._require_auth,
                      api_mod._resolve_user_role, _real_mgr)
    return TestClient(api_mod.app, raise_server_exceptions=False), api_mod


def _tok(api_mod, uid):
    return api_mod._make_jwt({"user_id": uid, "username": "", "first_name": "",
                              "photo_url": "", "is_admin": False, "is_owner": False})


def test_economy_settings_ws1_owner_sees_only_ws1(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 42)}", "X-Workspace-Id": "1"}
    r = c.get("/api/economy/settings", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    keys = {item["key"] for item in body if isinstance(item, dict) and "key" in item}
    assert "test.ws1_only" in keys
    assert "test.ws2_only" not in keys


def test_economy_settings_ws2_owner_sees_only_ws2(client):
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 99)}", "X-Workspace-Id": "2"}
    r = c.get("/api/economy/settings", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    keys = {item["key"] for item in body if isinstance(item, dict) and "key" in item}
    assert "test.ws2_only" in keys
    assert "test.ws1_only" not in keys, "ws=2 не должен видеть данные ws=1"


def test_economy_settings_cross_tenant_blocked(client):
    """Owner ws=1 шлёт X-Workspace-Id: 2 — middleware отбивает 403."""
    c, api_mod = client
    h = {"Authorization": f"Bearer {_tok(api_mod, 42)}", "X-Workspace-Id": "2"}
    r = c.get("/api/economy/settings", headers=h)
    assert r.status_code == 403
