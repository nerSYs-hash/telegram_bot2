"""Тесты миграции combo_claims/sprint_claims между workspace.

Покрывает 3 ключевых сценария:
1. чистый перенос без конфликтов
2. конфликт PK → побеждает более свежая claimed_at
3. dry-run = no-op, --apply = идемпотентна (повтор = no-op)

V1.17.0k2.
"""
import os
import sqlite3
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
from scripts.migrate_combo_sprint_workspaces import _plan, _apply


def _mk_schema(conn):
    conn.execute('''
        CREATE TABLE combo_claims (
            workspace_id INTEGER NOT NULL DEFAULT 1,
            user_id    INTEGER NOT NULL,
            combo_name TEXT    NOT NULL,
            reward     REAL    DEFAULT 0,
            claimed_at TEXT    NOT NULL,
            PRIMARY KEY (user_id, combo_name)
        )
    ''')
    conn.execute('''
        CREATE TABLE sprint_claims (
            workspace_id INTEGER NOT NULL DEFAULT 1,
            user_id     INTEGER NOT NULL,
            sprint_name TEXT    NOT NULL,
            window_key  TEXT    NOT NULL,
            reward      REAL    DEFAULT 0,
            claimed_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, sprint_name, window_key)
        )
    ''')
    # PK включает workspace_id, чтобы можно было держать строки с
    # одинаковым (user, combo) в разных ws (как на проде после миграции
    # multi-tenancy с composite-PK fix).
    # SQLite не даст 2 PK — пересоздадим без PK, оставим UNIQUE по
    # (workspace_id, user_id, combo_name) если нужно. Для тестов хватит
    # отсутствия PK.


def _mk_schema_no_pk(conn):
    conn.execute('''
        CREATE TABLE combo_claims (
            workspace_id INTEGER NOT NULL DEFAULT 1,
            user_id    INTEGER NOT NULL,
            combo_name TEXT    NOT NULL,
            reward     REAL    DEFAULT 0,
            claimed_at TEXT    NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE sprint_claims (
            workspace_id INTEGER NOT NULL DEFAULT 1,
            user_id     INTEGER NOT NULL,
            sprint_name TEXT    NOT NULL,
            window_key  TEXT    NOT NULL,
            reward      REAL    DEFAULT 0,
            claimed_at  TEXT    DEFAULT CURRENT_TIMESTAMP
        )
    ''')


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    _mk_schema_no_pk(c)
    yield c
    c.close()


def test_clean_migration_no_conflicts(conn):
    """Все строки src уезжают в into без конфликтов."""
    conn.executemany(
        "INSERT INTO combo_claims (workspace_id, user_id, combo_name, claimed_at) VALUES (?,?,?,?)",
        [(5, 100, 'reactor', '2026-05-20 12:00'),
         (6, 101, 'streak',  '2026-05-21 12:00')]
    )
    conn.executemany(
        "INSERT INTO sprint_claims (workspace_id, user_id, sprint_name, window_key, claimed_at) VALUES (?,?,?,?,?)",
        [(5, 100, 'hourly', '2026-05-20T14_1h', '2026-05-20 14:30')]
    )
    conn.commit()

    plan = _plan(conn, [5, 6], 1)
    # plan: (table, src, total, conflicts, fresh)
    by_key = {(r[0], r[1]): r for r in plan}
    assert by_key[('combo_claims',  5)][2:] == (1, 0, 1)
    assert by_key[('combo_claims',  6)][2:] == (1, 0, 1)
    assert by_key[('sprint_claims', 5)][2:] == (1, 0, 1)

    _apply(conn, [5, 6], 1)

    # Все строки теперь на ws=1
    assert conn.execute("SELECT COUNT(*) FROM combo_claims WHERE workspace_id=1").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM combo_claims WHERE workspace_id IN (5,6)").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM sprint_claims WHERE workspace_id=1").fetchone()[0] == 1


def test_pk_conflict_newer_wins(conn):
    """user=100 имеет 'reactor' и в ws=5, и в ws=1 → побеждает свежая дата."""
    conn.execute(
        "INSERT INTO combo_claims (workspace_id, user_id, combo_name, claimed_at, reward) "
        "VALUES (1, 100, 'reactor', '2026-05-19 10:00', 0.5)"
    )
    conn.execute(
        "INSERT INTO combo_claims (workspace_id, user_id, combo_name, claimed_at, reward) "
        "VALUES (5, 100, 'reactor', '2026-05-20 12:00', 0.7)"  # свежее
    )
    conn.commit()

    plan = _plan(conn, [5], 1)
    by_key = {(r[0], r[1]): r for r in plan}
    assert by_key[('combo_claims', 5)][2:] == (1, 1, 0)  # 1 строка, 1 конфликт, 0 fresh

    _apply(conn, [5], 1)

    rows = conn.execute(
        "SELECT workspace_id, claimed_at, reward FROM combo_claims "
        "WHERE user_id=100 AND combo_name='reactor'"
    ).fetchall()
    assert len(rows) == 1, "должна остаться одна строка"
    ws_id, claimed_at, reward = rows[0]
    assert ws_id == 1
    assert claimed_at == '2026-05-20 12:00', "должна победить свежая дата"
    assert reward == 0.7


def test_idempotent(conn):
    """Повторный --apply на уже-чистой БД = no-op."""
    conn.execute(
        "INSERT INTO combo_claims (workspace_id, user_id, combo_name, claimed_at) "
        "VALUES (5, 100, 'streak', '2026-05-20 12:00')"
    )
    conn.commit()
    _apply(conn, [5], 1)
    # Повтор: всё уже на ws=1, source пуст
    plan = _plan(conn, [5], 1)
    by_key = {(r[0], r[1]): r for r in plan}
    assert by_key[('combo_claims', 5)][2:] == (0, 0, 0)
    _apply(conn, [5], 1)  # не должен падать
    assert conn.execute("SELECT COUNT(*) FROM combo_claims").fetchone()[0] == 1


def test_dry_run_does_not_apply(tmp_path):
    """main(--from 5 --into 1) без --apply не трогает БД."""
    db = str(tmp_path / 't.db')
    c = sqlite3.connect(db)
    _mk_schema_no_pk(c)
    c.execute(
        "INSERT INTO combo_claims (workspace_id, user_id, combo_name, claimed_at) "
        "VALUES (5, 100, 'streak', '2026-05-20 12:00')"
    )
    c.commit(); c.close()

    from scripts.migrate_combo_sprint_workspaces import main
    rc = main(['--db', db, '--from', '5', '--into', '1'])
    assert rc == 0

    c = sqlite3.connect(db)
    ws_ids = [r[0] for r in c.execute("SELECT workspace_id FROM combo_claims")]
    assert ws_ids == [5], 'без --apply строка должна остаться на ws=5'


def test_combo_sprint_in_tenant_tables():
    """Регрессия: combo_claims/sprint_claims обязаны быть в TENANT_TABLES
    (иначе консолидация молча оставит сирот)."""
    from database.db_workspaces import TENANT_TABLES
    assert 'combo_claims' in TENANT_TABLES
    assert 'sprint_claims' in TENANT_TABLES
