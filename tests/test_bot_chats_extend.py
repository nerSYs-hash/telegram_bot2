"""Тесты ALTER миграции bot_chats_extend."""
import os
import shutil
import sqlite3
import pytest

from database.migrations.bot_chats_extend import migrate_up, NEW_COLUMNS


@pytest.fixture
def db_copy(tmp_path):
    src = os.path.join(os.path.dirname(__file__), '..', 'database', 'bot_database.db')
    dst = tmp_path / 'test.db'
    shutil.copy2(src, dst)
    return str(dst)


def test_adds_all_new_columns(db_copy):
    migrate_up(db_copy)
    conn = sqlite3.connect(db_copy)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chats)").fetchall()]
    for new_col in NEW_COLUMNS:
        assert new_col in cols, f'{new_col} missing'
    conn.close()


def test_idempotent(db_copy):
    migrate_up(db_copy)
    migrate_up(db_copy)  # second call should not error
    conn = sqlite3.connect(db_copy)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chats)").fetchall()]
    assert len(cols) == len(set(cols))
    conn.close()
