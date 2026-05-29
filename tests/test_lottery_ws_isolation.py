"""V1.17.0T (M5): изоляция лотереи per-workspace.

LotteryHandler резолвит свой ws из target_chat_id; _active() и создание
скоупятся по ws. Лотерея одного ws не видна в другом.
"""
import sqlite3
import pytest

from handlers.lottery_handlers import LotteryHandler


class _DB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _conn_with_chat(ws_id, chat_id):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE bot_chats (
        workspace_id INTEGER, chat_id INTEGER, role TEXT,
        PRIMARY KEY(workspace_id, chat_id))''')
    conn.execute("INSERT INTO bot_chats VALUES (?, ?, 'main')", (ws_id, chat_id))
    conn.commit()
    from bot_core import workspace_context as _wc
    _wc._chat_to_ws_cache.clear()
    return conn


def _ins_active(db, ws_id):
    db.cursor.execute(
        "INSERT INTO lotteries (ticket_price,duration,end_time,status,total_pool,winners_mode,workspace_id) "
        "VALUES (100,3600,'2099-01-01 00:00:00','active',0,1,?)", (ws_id,))
    db.conn.commit()


def test_handler_resolves_ws_from_chat():
    db = _DB(_conn_with_chat(2, -2000))
    h = LotteryHandler(db, target_chat_id=-2000, main_admin_id=999)
    assert h.ws_id == 2


def test_active_lottery_scoped_by_workspace():
    db = _DB(_conn_with_chat(2, -2000))
    h = LotteryHandler(db, target_chat_id=-2000, main_admin_id=999)
    _ins_active(db, 1)          # чужая лотерея ws=1
    assert h._active() == []     # ws=2 её не видит
    _ins_active(db, 2)          # своя ws=2
    assert len(h._active()) == 1


def test_jackpot_key_per_workspace():
    db1 = _DB(_conn_with_chat(1, -1000))
    h1 = LotteryHandler(db1, target_chat_id=-1000, main_admin_id=999)
    db2 = _DB(_conn_with_chat(2, -2000))
    h2 = LotteryHandler(db2, target_chat_id=-2000, main_admin_id=999)
    assert h1._jackpot_key() == 'jackpot_pool'        # ws=1 — старый ключ
    assert h2._jackpot_key() == 'jackpot_pool_2'       # ws=2 — отдельный
