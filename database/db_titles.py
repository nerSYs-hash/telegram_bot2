#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db_titles.py — Кастомные титулы (V1.16.0).

Двухвалютная покупка титула через меню Баланс:
- title_packages — пакеты подписки (CRUD у Владельца)
- title_rub_requests — заявки на оплату рублями (Владелец подтверждает)

Применение титула переиспользует handlers/shop_mechanics.py:
apply_title_to_user / cleanup_expired_titles / get_user_title.
Хранение активного титула — в существующей таблице marketplace_services
(service_type='title').
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
#  СХЕМА БД
# ════════════════════════════════════════════════════════════════════════════════

def init_titles_tables(db) -> None:
    """Создать таблицы title_packages и title_rub_requests, идемпотентно."""
    db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS title_packages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            label           TEXT    NOT NULL,
            duration_days   INTEGER,
            price_pulses    INTEGER NOT NULL,
            price_rub       INTEGER,
            is_enabled      INTEGER NOT NULL DEFAULT 1,
            sort_order      INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    ''')
    db.cursor.execute('CREATE INDEX IF NOT EXISTS idx_title_packages_sort '
                      'ON title_packages(is_enabled, sort_order)')

    db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS title_rub_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            package_id      INTEGER NOT NULL,
            title_text      TEXT    NOT NULL,
            price_rub       INTEGER NOT NULL,
            duration_days   INTEGER,
            status          TEXT    NOT NULL DEFAULT 'pending',
            owner_msg_id    INTEGER,
            owner_chat_id   INTEGER,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            decided_at      TEXT,
            decided_by      INTEGER,
            reject_reason   TEXT,
            FOREIGN KEY (package_id) REFERENCES title_packages(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    db.cursor.execute('CREATE INDEX IF NOT EXISTS idx_title_req_status '
                      'ON title_rub_requests(status, created_at)')
    db.cursor.execute('CREATE INDEX IF NOT EXISTS idx_title_req_user '
                      'ON title_rub_requests(user_id, created_at)')
    db.conn.commit()


def seed_default_packages(db) -> None:
    """Залить дефолтные 5 пакетов и settings ключи (только если пусто)."""
    defaults = [
        # (label, duration_days, price_pulses, price_rub, sort_order)
        ('7 дней',     7,   5000,   100,  10),
        ('1 месяц',    30,  15000,  300,  20),
        ('3 месяца',   90,  40000,  750,  30),
        ('6 месяцев',  180, 70000,  1300, 40),
        ('1 год',      365, 120000, 2400, 50),
    ]
    db.cursor.execute('SELECT COUNT(*) AS c FROM title_packages')
    row = db.cursor.fetchone()
    if row and row['c'] == 0:
        for label, days, p_pul, p_rub, srt in defaults:
            db.cursor.execute(
                'INSERT INTO title_packages '
                '(label, duration_days, price_pulses, price_rub, sort_order) '
                'VALUES (?, ?, ?, ?, ?)',
                (label, days, p_pul, p_rub, srt)
            )
        logger.info('🏷 Засеяно %d дефолтных пакетов титулов', len(defaults))

    # settings (через сырой SQL — чтобы не зависеть от db.set_setting импорта)
    for key, value in (('title_rename_price_pulses', '50'),
                       ('title_request_ttl_hours', '48')):
        db.cursor.execute(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )
    db.conn.commit()


# ════════════════════════════════════════════════════════════════════════════════
#  CRUD ПАКЕТОВ
# ════════════════════════════════════════════════════════════════════════════════

def list_title_packages(db, only_enabled: bool = False) -> list[dict]:
    if only_enabled:
        db.cursor.execute(
            'SELECT * FROM title_packages WHERE is_enabled = 1 '
            'ORDER BY sort_order, id'
        )
    else:
        db.cursor.execute('SELECT * FROM title_packages ORDER BY sort_order, id')
    return [dict(r) for r in db.cursor.fetchall()]


def get_title_package(db, pkg_id: int) -> Optional[dict]:
    db.cursor.execute('SELECT * FROM title_packages WHERE id = ?', (pkg_id,))
    row = db.cursor.fetchone()
    return dict(row) if row else None


def create_title_package(db, label: str, duration_days: Optional[int],
                         price_pulses: int, price_rub: Optional[int]) -> int:
    db.cursor.execute('SELECT COALESCE(MAX(sort_order), 0) + 10 AS s '
                      'FROM title_packages')
    sort_order = db.cursor.fetchone()['s']
    db.cursor.execute(
        'INSERT INTO title_packages '
        '(label, duration_days, price_pulses, price_rub, sort_order) '
        'VALUES (?, ?, ?, ?, ?)',
        (label, duration_days, price_pulses, price_rub, sort_order)
    )
    db.conn.commit()
    return db.cursor.lastrowid


def update_title_package(db, pkg_id: int, **fields) -> None:
    """fields: label, duration_days, price_pulses, price_rub, is_enabled, sort_order."""
    allowed = {'label', 'duration_days', 'price_pulses', 'price_rub',
               'is_enabled', 'sort_order'}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f'{k} = ?')
            vals.append(v)
    if not sets:
        return
    sets.append("updated_at = datetime('now')")
    vals.append(pkg_id)
    db.cursor.execute(
        f"UPDATE title_packages SET {', '.join(sets)} WHERE id = ?", vals
    )
    db.conn.commit()


def toggle_title_package(db, pkg_id: int) -> Optional[bool]:
    """Переключить is_enabled. Возвращает новое значение или None если не найден."""
    pkg = get_title_package(db, pkg_id)
    if not pkg:
        return None
    new_val = 0 if pkg['is_enabled'] else 1
    update_title_package(db, pkg_id, is_enabled=new_val)
    return bool(new_val)


# ════════════════════════════════════════════════════════════════════════════════
#  CRUD ЗАЯВОК НА РУБЛЁВУЮ ОПЛАТУ
# ════════════════════════════════════════════════════════════════════════════════

def create_title_request(db, user_id: int, package_id: int, title_text: str,
                         price_rub: int, duration_days: Optional[int]) -> int:
    db.cursor.execute(
        'INSERT INTO title_rub_requests '
        '(user_id, package_id, title_text, price_rub, duration_days) '
        'VALUES (?, ?, ?, ?, ?)',
        (user_id, package_id, title_text, price_rub, duration_days)
    )
    db.conn.commit()
    return db.cursor.lastrowid


def attach_owner_message(db, request_id: int, owner_chat_id: int,
                         owner_msg_id: int) -> None:
    db.cursor.execute(
        'UPDATE title_rub_requests SET owner_chat_id = ?, owner_msg_id = ? '
        'WHERE id = ?',
        (owner_chat_id, owner_msg_id, request_id)
    )
    db.conn.commit()


def get_title_request(db, request_id: int) -> Optional[dict]:
    db.cursor.execute('SELECT * FROM title_rub_requests WHERE id = ?',
                      (request_id,))
    row = db.cursor.fetchone()
    return dict(row) if row else None


def list_title_requests(db, status: Optional[str] = None,
                        limit: int = 50, offset: int = 0) -> list[dict]:
    if status:
        db.cursor.execute(
            'SELECT * FROM title_rub_requests WHERE status = ? '
            'ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (status, limit, offset)
        )
    else:
        db.cursor.execute(
            'SELECT * FROM title_rub_requests '
            'ORDER BY (status = "pending") DESC, created_at DESC '
            'LIMIT ? OFFSET ?',
            (limit, offset)
        )
    return [dict(r) for r in db.cursor.fetchall()]


def count_title_requests_by_status(db, status: str) -> int:
    db.cursor.execute(
        'SELECT COUNT(*) AS c FROM title_rub_requests WHERE status = ?',
        (status,)
    )
    row = db.cursor.fetchone()
    return row['c'] if row else 0


def transition_title_request(db, request_id: int, new_status: str,
                             decided_by: Optional[int] = None,
                             reject_reason: Optional[str] = None,
                             only_from: str = 'pending') -> bool:
    """
    Атомарный переход статуса заявки.
    Возвращает True если переход выполнен, False — если статус не совпал
    с only_from (защита от двойных нажатий).
    Атомарность даёт сам UPDATE с условием WHERE status = ?.
    """
    db.cursor.execute(
        'UPDATE title_rub_requests '
        "SET status = ?, decided_at = datetime('now'), "
        '    decided_by = COALESCE(?, decided_by), '
        '    reject_reason = COALESCE(?, reject_reason) '
        'WHERE id = ? AND status = ?',
        (new_status, decided_by, reject_reason, request_id, only_from)
    )
    changed = db.cursor.rowcount
    db.conn.commit()
    return changed > 0


def expire_old_title_requests(db, ttl_hours: int) -> list[dict]:
    """
    Перевести pending-заявки старше ttl_hours в статус 'expired'.
    Возвращает список заявок которые были помечены — чтобы фон-задача
    могла отредактировать сообщения у Владельца.
    """
    db.cursor.execute(
        "SELECT * FROM title_rub_requests WHERE status = 'pending' "
        "AND created_at < datetime('now', ?)",
        (f'-{int(ttl_hours)} hours',)
    )
    rows = [dict(r) for r in db.cursor.fetchall()]
    if not rows:
        return []
    ids = [r['id'] for r in rows]
    placeholders = ','.join('?' * len(ids))
    db.cursor.execute(
        f"UPDATE title_rub_requests SET status = 'expired', "
        f"decided_at = datetime('now') "
        f"WHERE id IN ({placeholders}) AND status = 'pending'",
        ids
    )
    db.conn.commit()
    return rows
