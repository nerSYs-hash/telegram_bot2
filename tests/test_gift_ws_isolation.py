"""V1.17.0T (M5): изоляция «подарка месяца» per-workspace."""
import sqlite3
from datetime import datetime

from handlers.gift_handlers import GiftHandler


class _DB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _conn(ws_id, chat_id):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE bot_chats (
        workspace_id INTEGER, chat_id INTEGER, role TEXT,
        PRIMARY KEY(workspace_id, chat_id))''')
    conn.execute("INSERT INTO bot_chats VALUES (?, ?, 'main')", (ws_id, chat_id))
    conn.execute('''CREATE TABLE monthly_gifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT, prize_amount INTEGER,
        status TEXT, workspace_id INTEGER DEFAULT 1)''')
    conn.commit()
    from bot_core import workspace_context as _wc
    _wc._chat_to_ws_cache.clear()
    return conn


def test_handler_resolves_ws():
    h = GiftHandler(_DB(_conn(2, -2000)), -2000, 999)
    assert h.ws_id == 2


def test_current_gift_scoped_by_ws():
    db = _DB(_conn(2, -2000))
    h = GiftHandler(db, -2000, 999)
    m = datetime.now().strftime('%Y-%m')
    db.cursor.execute(
        "INSERT INTO monthly_gifts (month,prize_amount,status,workspace_id) VALUES (?,100,'active',1)", (m,))
    db.conn.commit()
    gift, _ = h._get_current_gift()
    assert gift is None  # подарок ws=1 не виден в ws=2

    db.cursor.execute(
        "INSERT INTO monthly_gifts (month,prize_amount,status,workspace_id) VALUES (?,100,'active',2)", (m,))
    db.conn.commit()
    gift, _ = h._get_current_gift()
    assert gift is not None and gift['workspace_id'] == 2
