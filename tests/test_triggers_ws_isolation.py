"""V1.17.0T: изоляция триггеров per-workspace.

Инкремент 1 — схема: миграция добавляет workspace_id и бэкфиллит legacy → ws=1.
"""
import sqlite3
import pytest

from handlers.triggers_handlers import ensure_trigger_tables


class _DB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return _DB(conn)


def test_migration_adds_workspace_id_and_backfills_legacy():
    """Старая таблица triggers без workspace_id → после миграции колонка есть,
    существующая строка получает workspace_id=1."""
    db = _make_db()
    db.cursor.execute('''
        CREATE TABLE triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            keywords TEXT NOT NULL,
            condition TEXT NOT NULL DEFAULT 'contains',
            action TEXT NOT NULL DEFAULT 'delete',
            action_value TEXT,
            probability INTEGER NOT NULL DEFAULT 100,
            is_enabled INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.cursor.execute(
        "INSERT INTO triggers (name, keywords, action) VALUES ('legacy', 'привет', 'delete')")
    db.conn.commit()

    ensure_trigger_tables(db)

    cols = [r[1] for r in db.cursor.execute("PRAGMA table_info(triggers)").fetchall()]
    assert 'workspace_id' in cols

    row = db.cursor.execute(
        "SELECT workspace_id FROM triggers WHERE name='legacy'").fetchone()
    assert row['workspace_id'] == 1


def test_fresh_tables_have_workspace_id():
    """Чистое создание таблиц через ensure_trigger_tables — workspace_id присутствует."""
    db = _make_db()
    ensure_trigger_tables(db)
    cols = [r[1] for r in db.cursor.execute("PRAGMA table_info(triggers)").fetchall()]
    assert 'workspace_id' in cols
