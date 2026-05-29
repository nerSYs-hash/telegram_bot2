"""V1.17.0T (M5): банк per-workspace. Каждый ws стартует с 10М, банки независимы."""
import sqlite3

from database.db_transactions import (
    get_bank_balance, update_bank_balance, _bank_key, BANK_INITIAL_CAPITAL,
)


class _DB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)")
    conn.commit()
    return _DB(conn)


def test_ws1_uses_legacy_key():
    assert _bank_key(1) == 'bank_balance'
    assert _bank_key(2) == 'bank_balance_2'


def test_new_ws_bank_starts_at_10m():
    db = _db()
    assert get_bank_balance(db, 1) == BANK_INITIAL_CAPITAL
    assert get_bank_balance(db, 2) == BANK_INITIAL_CAPITAL  # новый ws — дефолт 10М


def test_bank_independent_per_ws():
    db = _db()
    update_bank_balance(db, 5000, 'subtract', ws_id=2)
    assert get_bank_balance(db, 2) == BANK_INITIAL_CAPITAL - 5000
    assert get_bank_balance(db, 1) == BANK_INITIAL_CAPITAL  # ws=1 не тронут

    update_bank_balance(db, 1000, 'add', ws_id=1)
    assert get_bank_balance(db, 1) == BANK_INITIAL_CAPITAL + 1000
    assert get_bank_balance(db, 2) == BANK_INITIAL_CAPITAL - 5000
