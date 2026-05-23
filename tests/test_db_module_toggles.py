"""Тесты DB-слоя module_toggles (get/set/upsert тумблеров)."""

import sqlite3
from database.migrations.module_toggles import up

def test_migration_creates_three_tables():
    conn = sqlite3.connect(":memory:")
    up(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "module_toggles" in tables
    assert "module_toggle_history" in tables
    assert "module_toggle_cache_version" in tables
    indexes = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()}
    assert "idx_mth_ws_mod" in indexes

def test_migration_is_idempotent():
    conn = sqlite3.connect(":memory:")
    up(conn)
    up(conn)  # should not raise


import json
from pathlib import Path
from database.db_module_toggles import (
    is_module_enabled, set_module_state, get_modules,
    list_history, get_cache_version,
    VALID_MODULE_IDS,
)
from database.migrations.module_toggles import up as _up


def _fresh():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    _up(conn)
    return conn


def test_default_module_is_disabled():
    conn = _fresh()
    assert is_module_enabled(conn, 1, "triggers") is False


def test_set_module_state_enable_then_disable():
    conn = _fresh()
    set_module_state(conn, 1, "triggers", True,  reason=None,    user_id=42)
    assert is_module_enabled(conn, 1, "triggers") is True
    set_module_state(conn, 1, "triggers", False, reason="не нужен", user_id=42)
    assert is_module_enabled(conn, 1, "triggers") is False


def test_workspace_isolation():
    conn = _fresh()
    set_module_state(conn, 1, "triggers", True, reason=None, user_id=42)
    assert is_module_enabled(conn, 1, "triggers") is True
    assert is_module_enabled(conn, 2, "triggers") is False


def test_disable_requires_reason():
    conn = _fresh()
    try:
        set_module_state(conn, 1, "triggers", False, reason=None, user_id=42)
        assert False, "должен был кинуть ValueError"
    except ValueError:
        pass


def test_invalid_module_id_rejected():
    conn = _fresh()
    try:
        set_module_state(conn, 1, "unknown_xxx", True, reason=None, user_id=42)
        assert False
    except ValueError:
        pass


def test_history_records_action_and_reason():
    conn = _fresh()
    set_module_state(conn, 1, "triggers", True,  reason=None,  user_id=42)
    set_module_state(conn, 1, "triggers", False, reason="тест", user_id=42)
    h = list_history(conn, 1, "triggers", limit=10)
    assert [r["action"] for r in h] == ["disable", "enable"]  # DESC
    assert h[0]["reason"] == "тест"


def test_set_module_state_bumps_version():
    conn = _fresh()
    v0 = get_cache_version(conn, 1)
    set_module_state(conn, 1, "triggers", True, reason=None, user_id=42)
    assert get_cache_version(conn, 1) == v0 + 1


def test_valid_module_ids_loaded_from_json():
    catalog_path = Path(__file__).resolve().parent.parent / "shared" / "modules_catalog.json"
    cat = json.loads(catalog_path.read_text(encoding="utf-8"))
    expected = {m["id"] for m in cat["modules"]}
    assert VALID_MODULE_IDS == expected


def test_get_modules_returns_all_with_defaults():
    conn = _fresh()
    items = get_modules(conn, 1)
    ids = {i["id"] for i in items}
    assert "triggers" in ids
    assert all(i["is_enabled"] is False for i in items)
