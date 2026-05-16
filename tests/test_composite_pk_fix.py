"""Тесты миграции composite_pk_fix — round-trip на копии live-БД."""
import os
import shutil
import sqlite3
import pytest

from database.migrations.composite_pk_fix import migrate_up, migrate_down, REBUILT_TABLES


@pytest.fixture
def db_with_v17_state(tmp_path):
    """Копия live-БД (уже мигрирована до multi-tenancy V1.17.0a22)."""
    src = os.path.join(os.path.dirname(__file__), '..', 'database', 'bot_database.db')
    dst = tmp_path / 'test.db'
    shutil.copy2(src, dst)
    return str(dst)


def test_migrate_up_recreates_economy_settings_pk(db_with_v17_state):
    migrate_up(db_with_v17_state)
    conn = sqlite3.connect(db_with_v17_state)
    pk_cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(economy_settings)"
    ).fetchall() if r[5] > 0]  # pk > 0
    assert set(pk_cols) == {'workspace_id', 'key'}
    conn.close()


def test_migrate_up_preserves_data(db_with_v17_state):
    conn = sqlite3.connect(db_with_v17_state)
    before = conn.execute("SELECT COUNT(*) FROM economy_settings").fetchone()[0]
    conn.close()
    migrate_up(db_with_v17_state)
    conn = sqlite3.connect(db_with_v17_state)
    after = conn.execute("SELECT COUNT(*) FROM economy_settings").fetchone()[0]
    assert after == before
    conn.close()


def test_migrate_up_allows_two_workspaces_same_key(db_with_v17_state):
    """После фикса можно иметь одинаковый key в разных workspace."""
    migrate_up(db_with_v17_state)
    conn = sqlite3.connect(db_with_v17_state)
    conn.execute(
        "INSERT INTO economy_settings "
        "(workspace_id, key, category, label, value, value_type) VALUES (?, ?, ?, ?, ?, ?)",
        (99, 'test_key', 'test', 'Test', '100', 'int')
    )
    conn.execute(
        "INSERT INTO economy_settings "
        "(workspace_id, key, category, label, value, value_type) VALUES (?, ?, ?, ?, ?, ?)",
        (100, 'test_key', 'test', 'Test', '200', 'int')
    )
    conn.commit()
    rows = conn.execute(
        "SELECT workspace_id, value FROM economy_settings WHERE key='test_key' ORDER BY workspace_id"
    ).fetchall()
    assert rows == [(99, '100'), (100, '200')]
    conn.close()


def test_migrate_down_reverts(db_with_v17_state):
    migrate_up(db_with_v17_state)
    migrate_down(db_with_v17_state)
    conn = sqlite3.connect(db_with_v17_state)
    pk_cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(economy_settings)"
    ).fetchall() if r[5] > 0]
    assert pk_cols == ['key']  # back to single PK
    conn.close()


def test_all_rebuilt_tables_have_composite_pk(db_with_v17_state):
    migrate_up(db_with_v17_state)
    conn = sqlite3.connect(db_with_v17_state)
    for tbl, expected_pk in REBUILT_TABLES.items():
        pk_cols = [r[1] for r in conn.execute(
            f"PRAGMA table_info({tbl})"
        ).fetchall() if r[5] > 0]
        assert set(pk_cols) == set(expected_pk), f'{tbl}: PK={pk_cols} expected={expected_pk}'
    conn.close()
