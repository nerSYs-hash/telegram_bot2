#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Методы БД для курса Пульса и истории ТОП-5 активистов.
"""

import logging
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════
# ТАБЛИЦЫ (вызывается из db_manager.create_tables)
# ═══════════════════════════════════════════════════

def create_exchange_tables(db):
    """Создать таблицы exchange_rate_history и top_activists_history."""
    db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchange_rate_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rate REAL NOT NULL,
            ai_value REAL DEFAULT 0,
            total_members INTEGER DEFAULT 0,
            avg_active REAL DEFAULT 0,
            denominator REAL DEFAULT 0,
            is_manual BOOLEAN DEFAULT 0,
            changed_by INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS top_activists_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            rank INTEGER NOT NULL,
            activity_index REAL DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Индекс для быстрого поиска по дате и пользователю
    db.cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_top_activists_date
        ON top_activists_history (date, time_slot)
    ''')

    db.cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_top_activists_user
        ON top_activists_history (user_id, date)
    ''')

    db.conn.commit()


# ═══════════════════════════════════════════════════
# EXCHANGE RATE
# ═══════════════════════════════════════════════════

def set_exchange_rate(db, rate, changed_by=None, is_manual=False,
                      ai_value=0, total_members=0, avg_active=0, denominator=0):
    """Сохранить курс в историю и в settings."""
    try:
        db.cursor.execute('''
            INSERT INTO exchange_rate_history
                (rate, ai_value, total_members, avg_active, denominator, is_manual, changed_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (rate, ai_value, total_members, avg_active, denominator,
              1 if is_manual else 0, changed_by))

        db.cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value)
            VALUES ('exchange_rate', ?)
        ''', (str(rate),))

        db.cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value)
            VALUES ('exchange_rate_manual', ?)
        ''', ('1' if is_manual else '0',))

        db.conn.commit()
    except Exception as e:
        logger.error(f"Error setting exchange rate: {e}")


def get_exchange_rate(db):
    """Получить текущий курс."""
    db.cursor.execute("SELECT value FROM settings WHERE key = 'exchange_rate'")
    row = db.cursor.fetchone()
    return float(row['value']) if row else 1.0


def is_rate_manual(db):
    """Проверить, установлен ли курс вручную."""
    db.cursor.execute("SELECT value FROM settings WHERE key = 'exchange_rate_manual'")
    row = db.cursor.fetchone()
    return row and row['value'] == '1'


def get_rate_history(db, limit=48):
    """Получить историю курса (по умолчанию за 24 часа при 30-мин интервале)."""
    db.cursor.execute('''
        SELECT rate, ai_value, total_members, avg_active, denominator,
               is_manual, changed_by, timestamp
        FROM exchange_rate_history
        ORDER BY id DESC
        LIMIT ?
    ''', (limit,))
    return db.cursor.fetchall()


def get_rate_history_30d(db):
    """Получить историю курса за 30 дней (для владельца)."""
    db.cursor.execute('''
        SELECT rate, ai_value, total_members, avg_active, denominator,
               is_manual, timestamp
        FROM exchange_rate_history
        WHERE timestamp >= datetime('now', '-30 days')
        ORDER BY timestamp ASC
    ''')
    return db.cursor.fetchall()


# ═══════════════════════════════════════════════════
# TOP-5 ACTIVISTS HISTORY
# ═══════════════════════════════════════════════════

def save_top_snapshot(db, date, time_slot, user_id, rank, activity_index):
    """Сохранить одну запись ТОП-5 снапшота."""
    try:
        db.cursor.execute('''
            INSERT INTO top_activists_history
                (date, time_slot, user_id, rank, activity_index)
            VALUES (?, ?, ?, ?, ?)
        ''', (date, time_slot, user_id, rank, activity_index))
        db.conn.commit()
    except Exception as e:
        logger.error(f"Error saving top snapshot: {e}")


def get_latest_top_snapshot(db):
    """Получить последний снапшот ТОП-5."""
    db.cursor.execute('''
        SELECT tah.*, u.username, u.first_name
        FROM top_activists_history tah
        JOIN users u ON tah.user_id = u.user_id
        WHERE u.is_left = 0
          AND (tah.date, tah.time_slot) = (
            SELECT date, time_slot
            FROM top_activists_history
            ORDER BY id DESC
            LIMIT 1
        )
        ORDER BY tah.rank ASC
    ''')
    return db.cursor.fetchall()


def get_previous_top_snapshot(db):
    """Получить предыдущий снапшот ТОП-5 (для сравнения стрелок ↑↓)."""
    # Сначала находим последний
    db.cursor.execute('''
        SELECT DISTINCT date, time_slot
        FROM top_activists_history
        ORDER BY date DESC, time_slot DESC
        LIMIT 2
    ''')
    rows = db.cursor.fetchall()
    if len(rows) < 2:
        return []

    prev = rows[1]
    db.cursor.execute('''
        SELECT tah.*, u.username, u.first_name
        FROM top_activists_history tah
        JOIN users u ON tah.user_id = u.user_id
        WHERE tah.date = ? AND tah.time_slot = ?
          AND u.is_left = 0
        ORDER BY tah.rank ASC
    ''', (prev['date'], prev['time_slot']))
    return db.cursor.fetchall()


def get_user_top_appearances(db, user_id, days=30):
    """
    Сколько раз пользователь был в ТОП-5 за N дней.

    Returns:
        dict: {'total_snapshots': int, 'appearances': int, 'percentage': float,
               'best_rank': int, 'avg_rank': float}
    """
    db.cursor.execute('''
        SELECT COUNT(DISTINCT date || time_slot) as total
        FROM top_activists_history
        WHERE date >= date('now', ?)
    ''', (f'-{days} days',))
    total_snapshots = db.cursor.fetchone()['total'] or 0

    db.cursor.execute('''
        SELECT COUNT(*) as appearances,
               MIN(rank) as best_rank,
               AVG(rank) as avg_rank
        FROM top_activists_history
        WHERE user_id = ? AND date >= date('now', ?)
    ''', (user_id, f'-{days} days'))
    row = db.cursor.fetchone()

    appearances = row['appearances'] or 0
    percentage = (appearances / total_snapshots * 100) if total_snapshots > 0 else 0

    return {
        'total_snapshots': total_snapshots,
        'appearances': appearances,
        'percentage': round(percentage, 1),
        'best_rank': row['best_rank'] or 0,
        'avg_rank': round(row['avg_rank'] or 0, 1),
    }


def get_all_top_appearances(db, days=30):
    """
    Статистика появлений ВСЕХ пользователей в ТОП-5 за N дней.
    Для отображения владельцу.
    """
    db.cursor.execute('''
        SELECT COUNT(DISTINCT date || time_slot) as total
        FROM top_activists_history
        WHERE date >= date('now', ?)
    ''', (f'-{days} days',))
    total_snapshots = db.cursor.fetchone()['total'] or 0

    db.cursor.execute('''
        SELECT tah.user_id, u.username, u.first_name,
               COUNT(*) as appearances,
               MIN(tah.rank) as best_rank,
               ROUND(AVG(tah.rank), 1) as avg_rank
        FROM top_activists_history tah
        JOIN users u ON tah.user_id = u.user_id
        WHERE tah.date >= date('now', ?)
          AND u.is_left = 0
        GROUP BY tah.user_id
        ORDER BY appearances DESC, best_rank ASC
    ''', (f'-{days} days',))

    rows = db.cursor.fetchall()
    result = []
    for row in rows:
        pct = (row['appearances'] / total_snapshots * 100) if total_snapshots > 0 else 0
        result.append({
            'user_id': row['user_id'],
            'username': row['username'] or row['first_name'] or f"ID:{row['user_id']}",
            'appearances': row['appearances'],
            'total_snapshots': total_snapshots,
            'percentage': round(pct, 1),
            'best_rank': row['best_rank'],
            'avg_rank': row['avg_rank'],
        })

    return result
