"""V1.17.0j2: тест идемпотентной миграции workspaces.icon_* колонок."""
import sqlite3
from database.db_migrations import add_icon_columns_to_workspaces


class _DB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _cols(conn):
    return {r[1] for r in conn.execute("PRAGMA table_info(workspaces)").fetchall()}


def test_adds_4_columns_when_missing():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT)")
    add_icon_columns_to_workspaces(_DB(conn))
    cols = _cols(conn)
    for c in ("icon_file_id", "icon_cached_at", "icon_source", "icon_local_path"):
        assert c in cols, f"колонка {c} должна быть добавлена"


def test_icon_source_default_is_tg():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT)")
    add_icon_columns_to_workspaces(_DB(conn))
    conn.execute("INSERT INTO workspaces (id, name) VALUES (1, 'X')")
    row = conn.execute("SELECT icon_source FROM workspaces WHERE id=1").fetchone()
    assert row[0] == 'tg'


def test_idempotent_when_already_present():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT, "
        "icon_file_id TEXT, icon_cached_at TIMESTAMP, "
        "icon_source TEXT, icon_local_path TEXT)"
    )
    db = _DB(conn)
    add_icon_columns_to_workspaces(db)  # no-op
    add_icon_columns_to_workspaces(db)  # повторно тоже ok
    assert "icon_file_id" in _cols(conn)


def test_partial_columns_present_only_missing_added():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT, icon_file_id TEXT)"
    )
    add_icon_columns_to_workspaces(_DB(conn))
    cols = _cols(conn)
    # все 4 должны присутствовать; уже бывшие — без дублей
    assert {"icon_file_id", "icon_cached_at", "icon_source", "icon_local_path"} <= cols


def test_no_workspaces_table_is_safe():
    conn = sqlite3.connect(":memory:")
    # без таблицы — функция не падает, просто лог + return
    add_icon_columns_to_workspaces(_DB(conn))
