#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""История членства per-workspace — фундамент виджета Статистики №6
(Новые / Вернувшиеся). Данные копятся ВПЕРЁД (как почасовые): вход/выход
участника пишется в `member_history`, классификация считается по истории.

V1.17.0U (29.05). Per-ws изолировано (workspace_id).
"""
import time


def create_member_history(db):
    """Идемпотентно создаёт таблицу истории членства."""
    db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS member_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL DEFAULT 1,
            user_id INTEGER NOT NULL,
            event TEXT NOT NULL CHECK(event IN ('joined','left')),
            ts INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER))
        )
    ''')
    db.cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_mh_ws_user '
        'ON member_history(workspace_id, user_id, ts)')
    db.conn.commit()


def log_member_event(db, workspace_id, user_id, event, ts=None):
    """Записать событие членства. event: 'joined' | 'left'."""
    if event not in ('joined', 'left'):
        return
    db.cursor.execute(
        'INSERT INTO member_history (workspace_id, user_id, event, ts) VALUES (?,?,?,?)',
        (workspace_id, int(user_id), event, int(ts if ts is not None else time.time())))
    db.conn.commit()


def count_new_returning(db, workspace_id, start_ts, end_ts):
    """Классификация присоединившихся в окне [start_ts, end_ts):
      • Новые        — первый join этого юзера попадает в окно (раньше не было).
      • Вернувшиеся  — join в окне, но раньше окна уже был join (т.е. уходил и вернулся).
    Возвращает {'new': int, 'returning': int}.
    """
    rows = db.cursor.execute(
        'SELECT DISTINCT user_id FROM member_history '
        'WHERE workspace_id=? AND event=? AND ts>=? AND ts<?',
        (workspace_id, 'joined', start_ts, end_ts)).fetchall()
    new = returning = 0
    for r in rows:
        uid = r['user_id'] if not isinstance(r, (tuple, list)) else r[0]
        prior = db.cursor.execute(
            'SELECT 1 FROM member_history '
            'WHERE workspace_id=? AND user_id=? AND event=? AND ts<? LIMIT 1',
            (workspace_id, uid, 'joined', start_ts)).fetchone()
        if prior:
            returning += 1
        else:
            new += 1
    return {'new': new, 'returning': returning}
