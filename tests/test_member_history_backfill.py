"""Backfill member_history из user_joins / return_on_leave."""
import sqlite3

from database.db_member_history import (
    apply_backfill_events,
    collect_backfill_events,
    count_new_returning,
    create_member_history,
    log_member_event,
)


class _DB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _make_db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    db = _DB(conn)
    db.cursor.executescript('''
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            joined_at TIMESTAMP,
            is_admin INTEGER DEFAULT 0,
            is_owner INTEGER DEFAULT 0
        );
        CREATE TABLE user_joins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL DEFAULT 1,
            user_id INTEGER NOT NULL,
            joined_at TIMESTAMP NOT NULL
        );
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL DEFAULT 1,
            from_user_id INTEGER,
            transaction_type TEXT,
            timestamp TIMESTAMP
        );
        CREATE TABLE user_stats (
            workspace_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            total_messages INTEGER DEFAULT 0,
            PRIMARY KEY (workspace_id, user_id, date)
        );
    ''')
    create_member_history(db)
    return db


def test_backfill_returning_after_leave_and_rejoin():
    db = _make_db()
    db.cursor.execute(
        "INSERT INTO users (user_id, joined_at) VALUES (100, '2024-01-01 10:00:00')"
    )
    db.cursor.execute(
        "INSERT INTO user_joins (workspace_id, user_id, joined_at) VALUES "
        "(1, 100, '2024-01-01 10:00:00'), (1, 100, '2024-06-01 12:00:00')"
    )
    db.cursor.execute(
        "INSERT INTO transactions (workspace_id, from_user_id, transaction_type, timestamp) "
        "VALUES (1, 100, 'return_on_leave', '2024-03-01 15:00:00')"
    )
    db.conn.commit()

    events = collect_backfill_events(db, default_workspace_id=1)
    res = apply_backfill_events(db, events)
    assert res['inserted'] > 0

    # Окно вокруг второго входа: 100 — вернувшийся (первый join до окна)
    w0 = int(__import__('datetime').datetime(2024, 5, 1).timestamp())
    w1 = int(__import__('datetime').datetime(2024, 7, 1).timestamp())
    assert count_new_returning(db, 1, w0, w1) == {'new': 0, 'returning': 1}


def test_backfill_idempotent():
    db = _make_db()
    db.cursor.execute(
        "INSERT INTO users (user_id, joined_at) VALUES (200, '2025-01-01 00:00:00')"
    )
    db.conn.commit()
    events = collect_backfill_events(db)
    r1 = apply_backfill_events(db, events)
    r2 = apply_backfill_events(db, events)
    assert r1['inserted'] >= 1
    assert r2['inserted'] == 0
    assert r2['skipped'] >= r1['inserted']


def test_backfill_infers_join_from_stats_after_leave():
    db = _make_db()
    db.cursor.execute(
        "INSERT INTO users (user_id, joined_at) VALUES (300, '2024-01-01 00:00:00')"
    )
    db.cursor.execute(
        "INSERT INTO transactions (workspace_id, from_user_id, transaction_type, timestamp) "
        "VALUES (1, 300, 'return_on_leave', '2024-02-01 12:00:00')"
    )
    db.cursor.execute(
        "INSERT INTO user_stats (workspace_id, user_id, date, total_messages) "
        "VALUES (1, 300, '2024-03-10', 5)"
    )
    db.conn.commit()

    events = collect_backfill_events(db)
    apply_backfill_events(db, events)

    w0 = int(__import__('datetime').datetime(2024, 3, 1).timestamp())
    w1 = int(__import__('datetime').datetime(2024, 4, 1).timestamp())
    assert count_new_returning(db, 1, w0, w1)['returning'] == 1


def test_live_events_not_duplicated():
    db = _make_db()
    ts = 1_700_000_000
    log_member_event(db, 1, 400, 'joined', ts=ts)
    db.cursor.execute(
        "INSERT INTO users (user_id, joined_at) VALUES (400, '2023-01-01')"
    )
    db.conn.commit()
    events = collect_backfill_events(db)
    r = apply_backfill_events(db, events)
    assert db.cursor.execute(
        'SELECT COUNT(*) FROM member_history WHERE user_id=400 AND event="joined"'
    ).fetchone()[0] == 1
    assert r['inserted'] == 0
