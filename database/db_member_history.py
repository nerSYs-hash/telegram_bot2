#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""История членства per-workspace — фундамент виджета Статистики №6
(Новые / Вернувшиеся). Данные копятся ВПЕРЁД (как почасовые): вход/выход
участника пишется в `member_history`, классификация считается по истории.

V1.17.0U (29.05). Per-ws изолировано (workspace_id).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Iterable

logger = logging.getLogger(__name__)


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


def _table_columns(cursor, table: str) -> set[str]:
    cursor.execute(f'PRAGMA table_info({table})')
    return {row[1] for row in cursor.fetchall()}


def parse_ts(value: Any) -> int | None:
    """Привести timestamp/joined_at к unix-секундам (локальное naive время)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    for fmt, size in (
        ('%Y-%m-%d %H:%M:%S', 19),
        ('%Y-%m-%dT%H:%M:%S', 19),
        ('%Y-%m-%d %H:%M', 16),
        ('%Y-%m-%d', 10),
    ):
        try:
            return int(datetime.strptime(text[:size], fmt).timestamp())
        except ValueError:
            continue
    try:
        return int(datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp())
    except ValueError:
        return None


def _event_key(workspace_id: int, user_id: int, event: str, ts: int) -> tuple:
    return (int(workspace_id), int(user_id), event, int(ts))


def existing_member_history_keys(db) -> set[tuple]:
    """Ключи уже записанных событий (для идемпотентного backfill)."""
    rows = db.cursor.execute(
        'SELECT workspace_id, user_id, event, ts FROM member_history'
    ).fetchall()
    keys = set()
    for r in rows:
        if hasattr(r, 'keys'):
            keys.add(_event_key(r['workspace_id'], r['user_id'], r['event'], r['ts']))
        else:
            keys.add(_event_key(r[0], r[1], r[2], r[3]))
    return keys


def _first_activity_ts_after(db, workspace_id: int, user_id: int, after_ts: int) -> int | None:
    """Первая активность в user_stats после выхода — эвристика «вернулся в чат»."""
    after_date = datetime.fromtimestamp(after_ts).strftime('%Y-%m-%d')
    row = db.cursor.execute(
        'SELECT MIN(date) AS d FROM user_stats '
        'WHERE workspace_id=? AND user_id=? AND date > ? AND total_messages > 0',
        (workspace_id, user_id, after_date),
    ).fetchone()
    if not row:
        return None
    d = row['d'] if hasattr(row, 'keys') else row[0]
    if not d:
        return None
    return parse_ts(f'{d} 12:00:00')


def collect_backfill_events(db, default_workspace_id: int = 1) -> list[dict]:
    """Собрать join/left из legacy-источников (без записи в БД).

    Источники:
      • user_joins — каждая строка = вход;
      • users.joined_at — первый вход, если нет user_joins;
      • transactions.return_on_leave — выход;
      • user_stats после выхода — оценка повторного входа, если нет 2-й строки в user_joins.
    """
    cols_uj = _table_columns(db.cursor, 'user_joins')
    cols_tx = _table_columns(db.cursor, 'transactions')
    has_ws_uj = 'workspace_id' in cols_uj
    has_ws_tx = 'workspace_id' in cols_tx

    joins_by_user: dict[tuple[int, int], list[int]] = {}
    leaves_by_user: dict[tuple[int, int], list[int]] = {}
    events: list[dict] = []

    def _remember_join(ws: int, uid: int, ts: int) -> None:
        if ts is None:
            return
        key = (ws, uid)
        joins_by_user.setdefault(key, [])
        if ts not in joins_by_user[key]:
            joins_by_user[key].append(ts)

    # Уже записанные live-события — только для логики «вернувшийся», не дублируем в events.
    for r in db.cursor.execute(
        'SELECT workspace_id, user_id, ts FROM member_history WHERE event=?',
        ('joined',),
    ).fetchall():
        ws = int(r['workspace_id'] if hasattr(r, 'keys') else r[0])
        uid = int(r['user_id'] if hasattr(r, 'keys') else r[1])
        ts = int(r['ts'] if hasattr(r, 'keys') else r[2])
        _remember_join(ws, uid, ts)

    def _add_join(ws: int, uid: int, ts: int, source: str) -> None:
        if ts is None:
            return
        _remember_join(ws, uid, ts)
        events.append({
            'workspace_id': ws, 'user_id': uid, 'event': 'joined',
            'ts': ts, 'source': source,
        })

    def _add_left(ws: int, uid: int, ts: int, source: str) -> None:
        if ts is None:
            return
        key = (ws, uid)
        leaves_by_user.setdefault(key, [])
        if ts not in leaves_by_user[key]:
            leaves_by_user[key].append(ts)
        events.append({
            'workspace_id': ws, 'user_id': uid, 'event': 'left',
            'ts': ts, 'source': source,
        })

    if db.cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_joins'"
    ).fetchone():
        ws_expr = 'workspace_id' if has_ws_uj else str(default_workspace_id)
        rows = db.cursor.execute(
            f'SELECT {ws_expr} AS ws, user_id, joined_at FROM user_joins '
            'WHERE user_id IS NOT NULL ORDER BY joined_at'
        ).fetchall()
        users_with_uj: set[tuple[int, int]] = set()
        for r in rows:
            ws = int(r['ws'] if hasattr(r, 'keys') else r[0])
            uid = int(r['user_id'] if hasattr(r, 'keys') else r[1])
            ts = parse_ts(r['joined_at'] if hasattr(r, 'keys') else r[2])
            _add_join(ws, uid, ts, 'user_joins')
            users_with_uj.add((ws, uid))

    rows = db.cursor.execute(
        'SELECT user_id, joined_at FROM users '
        'WHERE joined_at IS NOT NULL AND is_admin=0 AND is_owner=0'
    ).fetchall()
    for r in rows:
        uid = int(r['user_id'] if hasattr(r, 'keys') else r[0])
        ts = parse_ts(r['joined_at'] if hasattr(r, 'keys') else r[1])
        ws = default_workspace_id
        if (ws, uid) not in joins_by_user:
            _add_join(ws, uid, ts, 'users.joined_at')

    if db.cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='transactions'"
    ).fetchone():
        ws_expr = 'workspace_id' if has_ws_tx else str(default_workspace_id)
        rows = db.cursor.execute(
            f"SELECT {ws_expr} AS ws, from_user_id, timestamp FROM transactions "
            "WHERE transaction_type='return_on_leave' AND from_user_id IS NOT NULL "
            'ORDER BY timestamp'
        ).fetchall()
        for r in rows:
            ws = int(r['ws'] if hasattr(r, 'keys') else r[0])
            uid = int(r['from_user_id'] if hasattr(r, 'keys') else r[1])
            ts = parse_ts(r['timestamp'] if hasattr(r, 'keys') else r[2])
            _add_left(ws, uid, ts, 'return_on_leave')

    for (ws, uid), leave_list in leaves_by_user.items():
        joins = sorted(joins_by_user.get((ws, uid), []))
        for leave_ts in sorted(leave_list):
            has_join_after = any(j > leave_ts for j in joins)
            if has_join_after:
                continue
            inferred = _first_activity_ts_after(db, ws, uid, leave_ts)
            if inferred and inferred > leave_ts:
                _add_join(ws, uid, inferred, 'inferred_after_leave')
                joins.append(inferred)

    # Стабильный порядок: пользователь → время → joined перед left при равенстве
    events.sort(key=lambda e: (e['workspace_id'], e['user_id'], e['ts'],
                               0 if e['event'] == 'joined' else 1))
    return events


def apply_backfill_events(db, events: Iterable[dict], dry_run: bool = False) -> dict:
    """Дописать события в member_history (идемпотентно)."""
    create_member_history(db)
    existing = existing_member_history_keys(db)
    to_insert = []
    skipped = 0
    for ev in events:
        key = _event_key(ev['workspace_id'], ev['user_id'], ev['event'], ev['ts'])
        if key in existing:
            skipped += 1
            continue
        to_insert.append(ev)
        existing.add(key)

    if dry_run:
        joined = sum(1 for e in to_insert if e['event'] == 'joined')
        left = sum(1 for e in to_insert if e['event'] == 'left')
        return {
            'dry_run': True, 'would_insert': len(to_insert), 'skipped': skipped,
            'joined': joined, 'left': left,
        }

    for ev in to_insert:
        db.cursor.execute(
            'INSERT INTO member_history (workspace_id, user_id, event, ts) VALUES (?,?,?,?)',
            (ev['workspace_id'], ev['user_id'], ev['event'], ev['ts']),
        )
    if to_insert:
        db.conn.commit()

    joined = sum(1 for e in to_insert if e['event'] == 'joined')
    left = sum(1 for e in to_insert if e['event'] == 'left')
    return {
        'dry_run': False, 'inserted': len(to_insert), 'skipped': skipped,
        'joined': joined, 'left': left,
    }
