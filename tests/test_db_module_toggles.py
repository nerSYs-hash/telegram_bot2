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

def test_migration_is_idempotent():
    conn = sqlite3.connect(":memory:")
    up(conn)
    up(conn)  # should not raise
