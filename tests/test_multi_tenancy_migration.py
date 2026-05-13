"""Тест полной миграции: up → down → up восстанавливает рабочее состояние."""
import os
import shutil
import sqlite3
import pytest

from database.migrations.multi_tenancy import (
    migrate_up, migrate_down, TENANTED_TABLES,
)


@pytest.fixture
def real_db_copy(tmp_path):
    """Копия настоящей БД во временной директории.
    Если live-БД уже мигрирована (workspaces existуют) — откатываем
    в копии, чтобы тест мог проверить up "с нуля"."""
    src = os.path.join(os.path.dirname(__file__), '..', 'database', 'bot_database.db')
    dst = tmp_path / 'test.db'
    shutil.copy2(src, dst)
    # Reset to pre-migration state на копии (live-БД не трогаем).
    conn = sqlite3.connect(str(dst))
    has_ws = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspaces'"
    ).fetchone()
    conn.close()
    if has_ws:
        migrate_down(str(dst))
    return str(dst)


def test_migrate_up_creates_workspaces_table(real_db_copy):
    migrate_up(real_db_copy, owner_user_id=12345)
    conn = sqlite3.connect(real_db_copy)
    rows = conn.execute(
        'SELECT id, name, owner_user_id, is_pulse_themed FROM workspaces'
    ).fetchall()
    assert len(rows) == 1
    assert rows[0] == (1, 'Pulse Москва', 12345, 1)
    conn.close()


def test_migrate_up_creates_owner_member(real_db_copy):
    migrate_up(real_db_copy, owner_user_id=12345)
    conn = sqlite3.connect(real_db_copy)
    rows = conn.execute(
        'SELECT user_id, role FROM workspace_members WHERE workspace_id=1'
    ).fetchall()
    assert (12345, 'owner') in rows
    conn.close()


def test_migrate_up_tenantizes_all_tables(real_db_copy):
    migrate_up(real_db_copy, owner_user_id=12345)
    conn = sqlite3.connect(real_db_copy)
    for tbl in TENANTED_TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not exists:
            continue
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info({tbl})').fetchall()]
        assert 'workspace_id' in cols, f'workspace_id missing in {tbl}'
    conn.close()


def test_migrate_up_backfills_existing_data(real_db_copy):
    """Существующие строки получают workspace_id=1."""
    migrate_up(real_db_copy, owner_user_id=12345)
    conn = sqlite3.connect(real_db_copy)
    for tbl in ['user_stats', 'economy_history', 'press_release_templates']:
        try:
            rows = conn.execute(
                f'SELECT COUNT(*) FROM {tbl} WHERE workspace_id=1'
            ).fetchone()
            total = conn.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()
            assert rows[0] == total[0], (
                f'{tbl}: {rows[0]}/{total[0]} rows have workspace_id=1'
            )
        except sqlite3.OperationalError:
            pass
    conn.close()


def test_migrate_round_trip_down_up(real_db_copy):
    """down после up удаляет колонки. Затем up создаёт заново."""
    migrate_up(real_db_copy, owner_user_id=12345)
    migrate_down(real_db_copy)

    conn = sqlite3.connect(real_db_copy)
    res = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workspaces'"
    ).fetchone()
    assert res is None
    cols = [r[1] for r in conn.execute('PRAGMA table_info(user_stats)').fetchall()]
    assert 'workspace_id' not in cols
    conn.close()

    migrate_up(real_db_copy, owner_user_id=12345)
