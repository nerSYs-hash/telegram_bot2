"""Тесты изоляции статистики между workspace (M1 SaaS).

Проверяют, что:
1) WRITE-путь `db_stats.update_user_activity` пишет в правильный workspace
   и ON CONFLICT по composite PK (workspace_id, user_id, date) теперь
   действительно срабатывает (UPSERT, не падает в except).
2) Данные ws=1 невидимы при SELECT с WHERE workspace_id=2 и наоборот.
3) `db_exchange.update_user_activity_hourly` — то же по composite PK
   (workspace_id, user_id, date, hour).
"""
import sqlite3
import types
import pytest

from database.db_stats import update_user_activity
from database.db_exchange import update_user_activity_hourly


class _StubDB:
    """Минимальный обёртка для функций db_stats/db_exchange.

    Им нужно только .conn, .cursor; commit/rollback мы доверяем sqlite3.
    """
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cursor = conn.cursor()


@pytest.fixture
def db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    # Схема как после composite_pk_fix (см. database/bot_database.db).
    conn.execute('''
        CREATE TABLE user_stats (
            id INTEGER,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            total_chars INTEGER DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            total_words INTEGER DEFAULT 0,
            reactions_given INTEGER DEFAULT 0,
            reactions_received INTEGER DEFAULT 0,
            replies_received INTEGER DEFAULT 0,
            replies_sent INTEGER DEFAULT 0,
            mentions_received INTEGER DEFAULT 0,
            media_sent INTEGER DEFAULT 0,
            other_threads_posts INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            activity_score REAL DEFAULT 0,
            pulses_mined REAL DEFAULT 0.0,
            workspace_id INTEGER NOT NULL DEFAULT 1,
            edited_count INTEGER DEFAULT 0,
            links_sent INTEGER DEFAULT 0,
            PRIMARY KEY (workspace_id, user_id, date)
        )
    ''')
    conn.execute('''
        CREATE TABLE user_stats_hourly (
            id INTEGER,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            hour INTEGER NOT NULL,
            total_chars INTEGER DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            total_words INTEGER DEFAULT 0,
            reactions_given INTEGER DEFAULT 0,
            reactions_received INTEGER DEFAULT 0,
            replies_received INTEGER DEFAULT 0,
            replies_sent INTEGER DEFAULT 0,
            mentions_received INTEGER DEFAULT 0,
            media_sent INTEGER DEFAULT 0,
            other_threads_posts INTEGER DEFAULT 0,
            workspace_id INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (workspace_id, user_id, date, hour)
        )
    ''')
    # stat_events_log нужен для дедупа в update_user_activity (когда event_id передан)
    conn.execute('''
        CREATE TABLE stat_events_log (
            workspace_id INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, event_id)
        )
    ''')
    yield _StubDB(conn)
    conn.close()


def test_update_user_activity_isolates_workspaces(db):
    """ws=1 и ws=2 пишутся в отдельные строки, не мешая друг другу."""
    update_user_activity(db, 1, user_id=100, date='2026-05-27', total_messages=5)
    update_user_activity(db, 2, user_id=100, date='2026-05-27', total_messages=3)

    rows = db.conn.execute(
        "SELECT workspace_id, total_messages FROM user_stats "
        "WHERE user_id=100 AND date='2026-05-27' ORDER BY workspace_id"
    ).fetchall()
    assert [(r['workspace_id'], r['total_messages']) for r in rows] == [(1, 5), (2, 3)]


def test_update_user_activity_on_conflict_upserts_same_workspace(db):
    """Повторный вызов в тот же ws/юзер/день должен УВЕЛИЧИТЬ счётчик
    через ON CONFLICT(workspace_id, user_id, date), а НЕ упасть в except.
    """
    update_user_activity(db, 1, user_id=100, date='2026-05-27', total_messages=5)
    update_user_activity(db, 1, user_id=100, date='2026-05-27', total_messages=7)

    row = db.conn.execute(
        "SELECT total_messages FROM user_stats "
        "WHERE workspace_id=1 AND user_id=100 AND date='2026-05-27'"
    ).fetchone()
    assert row['total_messages'] == 12  # 5+7, прибавилось


def test_update_user_activity_select_ws1_does_not_see_ws2(db):
    """Чтение SUM по ws=1 не должно подмешивать данные ws=2."""
    update_user_activity(db, 1, user_id=100, date='2026-05-27', total_messages=5)
    update_user_activity(db, 2, user_id=100, date='2026-05-27', total_messages=999)

    r = db.conn.execute(
        "SELECT COALESCE(SUM(total_messages),0) as s FROM user_stats "
        "WHERE date='2026-05-27' AND workspace_id=1"
    ).fetchone()
    assert r['s'] == 5  # НЕ 5+999, фильтр работает


def test_hourly_isolates_workspaces_and_upserts(db):
    """То же для user_stats_hourly: composite PK + ws-фильтр."""
    update_user_activity_hourly(db, 1, user_id=100, date='2026-05-27', hour=10, total_messages=2)
    update_user_activity_hourly(db, 1, user_id=100, date='2026-05-27', hour=10, total_messages=3)
    update_user_activity_hourly(db, 2, user_id=100, date='2026-05-27', hour=10, total_messages=11)

    rows = db.conn.execute(
        "SELECT workspace_id, total_messages FROM user_stats_hourly "
        "WHERE user_id=100 AND date='2026-05-27' AND hour=10 ORDER BY workspace_id"
    ).fetchall()
    assert [(r['workspace_id'], r['total_messages']) for r in rows] == [(1, 5), (2, 11)]


def test_event_id_dedup_isolated_per_workspace(db):
    """event_id — дедуп per-ws: один и тот же event_id в разных ws работает."""
    update_user_activity(db, 1, user_id=100, date='2026-05-27',
                         event_id='msg_777_2026-05-27', total_messages=1)
    # Повтор в том же ws — дедуп, счётчик не растёт
    update_user_activity(db, 1, user_id=100, date='2026-05-27',
                         event_id='msg_777_2026-05-27', total_messages=1)
    # В другом ws тот же event_id — должен пройти
    update_user_activity(db, 2, user_id=100, date='2026-05-27',
                         event_id='msg_777_2026-05-27', total_messages=1)

    rows = db.conn.execute(
        "SELECT workspace_id, total_messages FROM user_stats "
        "WHERE user_id=100 AND date='2026-05-27' ORDER BY workspace_id"
    ).fetchall()
    assert [(r['workspace_id'], r['total_messages']) for r in rows] == [(1, 1), (2, 1)]
