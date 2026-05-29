"""V1.17.0U: история членства — новые/вернувшиеся, per-ws изоляция."""
import sqlite3

from database.db_member_history import (
    create_member_history, log_member_event, count_new_returning,
)


class _DB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = _DB(conn)
    create_member_history(db)
    return db


def test_new_vs_returning_in_window():
    db = _db()
    W0, W1 = 1000, 2000  # окно [1000, 2000)
    # user 100: пришёл ДО окна, ушёл, вернулся В окне → вернувшийся
    log_member_event(db, 1, 100, 'joined', ts=500)
    log_member_event(db, 1, 100, 'left',   ts=700)
    log_member_event(db, 1, 100, 'joined', ts=1500)
    # user 200: первый join В окне → новый
    log_member_event(db, 1, 200, 'joined', ts=1600)
    # user 300: пришёл и ушёл ДО окна, в окне не возвращался → не считается
    log_member_event(db, 1, 300, 'joined', ts=400)
    log_member_event(db, 1, 300, 'left',   ts=600)

    res = count_new_returning(db, 1, W0, W1)
    assert res == {'new': 1, 'returning': 1}


def test_isolated_per_workspace():
    db = _db()
    log_member_event(db, 1, 100, 'joined', ts=1500)  # ws=1
    log_member_event(db, 2, 200, 'joined', ts=1500)  # ws=2
    assert count_new_returning(db, 1, 1000, 2000) == {'new': 1, 'returning': 0}
    assert count_new_returning(db, 2, 1000, 2000) == {'new': 1, 'returning': 0}


def test_invalid_event_ignored():
    db = _db()
    log_member_event(db, 1, 100, 'banned', ts=1500)  # не пишется
    assert count_new_returning(db, 1, 1000, 2000) == {'new': 0, 'returning': 0}
