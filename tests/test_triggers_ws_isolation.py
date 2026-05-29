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


# ── Инкремент 2: изоляция срабатывания ──

def test_get_enabled_triggers_scoped_by_workspace():
    """_get_enabled_triggers возвращает только триггеры запрошенного ws."""
    from handlers.triggers_handlers import _get_enabled_triggers
    db = _make_db()
    ensure_trigger_tables(db)
    db.cursor.execute(
        "INSERT INTO triggers (name, keywords, is_enabled, workspace_id) VALUES ('w1','a',1,1)")
    db.cursor.execute(
        "INSERT INTO triggers (name, keywords, is_enabled, workspace_id) VALUES ('w2','b',1,2)")
    db.conn.commit()
    assert [t['name'] for t in _get_enabled_triggers(db, 1)] == ['w1']
    assert [t['name'] for t in _get_enabled_triggers(db, 2)] == ['w2']


def test_process_triggers_does_not_fire_foreign_ws_trigger():
    """Сквозная изоляция: триггер ws=1 НЕ срабатывает в чате ws=2."""
    import asyncio
    from unittest.mock import MagicMock
    from database.migrations.module_toggles import up as up_modules
    from database.db_module_toggles import set_module_state
    from bot_core import module_guard as _mg
    from bot_core import workspace_context as _wc
    from handlers.triggers_handlers import process_triggers, ensure_trigger_tables

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    up_modules(conn)
    conn.execute('''CREATE TABLE bot_chats (
        workspace_id INTEGER, chat_id INTEGER, role TEXT,
        PRIMARY KEY(workspace_id, chat_id))''')
    conn.execute("INSERT INTO bot_chats VALUES (2, -2000, 'main')")  # чат принадлежит ws=2
    conn.commit()
    _mg._CACHE.clear()
    _wc._chat_to_ws_cache.clear()

    db = _DB(conn)
    ensure_trigger_tables(db)
    # триггер принадлежит ЧУЖОМУ ws=1
    db.cursor.execute(
        "INSERT INTO triggers (name, keywords, condition, is_enabled, workspace_id) "
        "VALUES ('foreign','привет','contains',1,1)")
    db.conn.commit()
    # модуль триггеров включён для ws=2
    set_module_state(conn, 2, "triggers", True, reason=None, user_id=0)

    upd = MagicMock()
    msg = MagicMock()
    msg.text = "привет всем"
    msg.caption = None
    msg.from_user = MagicMock(id=42, is_bot=False, first_name="T", username="t")
    msg.message_thread_id = None
    upd.effective_message = msg
    upd.message = msg
    ctx = MagicMock()
    ctx.bot.id = 999

    result = asyncio.run(process_triggers(
        upd, ctx, db, target_chat_id=-2000, main_admin_id=999))
    # триггер ws=1 не виден в ws=2 → ничего не сработало
    assert result is False
