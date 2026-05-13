#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Методы БД для курса Пульса и истории ТОП-5 активистов.

V1.17.0a15 (multi-tenancy):
  • exchange_rate_history — ГЛОБАЛЬНАЯ (Pulse-токен — единая «валюта» сети),
    нет workspace_id (см. GLOBAL_TABLES в migrations/multi_tenancy.py).
  • settings — ГЛОБАЛЬНАЯ key-value (exchange_rate, exchange_rate_manual).
  • top_activists_history / top_activists_percent / user_stats_hourly —
    тенантизированные, требуют workspace_id первым аргументом после `db`.
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

    # ═══ Почасовая статистика для % активности (4ч окно) ═══
    db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_stats_hourly (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE(user_id, date, hour)
        )
    ''')

    db.cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_stats_hourly_date_hour
        ON user_stats_hourly (date, hour)
    ''')

    # ═══ Кеш ТОП-5 % активности (обновляется каждый час) ═══
    db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS top_activists_percent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            percent REAL DEFAULT 0,
            activity_index REAL DEFAULT 0,
            rank INTEGER NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    db.cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_top_percent_updated
        ON top_activists_percent (updated_at)
    ''')

    db.conn.commit()


# ═══════════════════════════════════════════════════
# EXCHANGE RATE (ГЛОБАЛЬНЫЙ — без workspace_id)
# ═══════════════════════════════════════════════════

def set_exchange_rate(db, rate, changed_by=None, is_manual=False,
                      ai_value=0, total_members=0, avg_active=0, denominator=0):
    """Сохранить курс в историю и в settings. ГЛОБАЛЬНО."""
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
    """Получить текущий курс. ГЛОБАЛЬНО."""
    db.cursor.execute("SELECT value FROM settings WHERE key = 'exchange_rate'")
    row = db.cursor.fetchone()
    return float(row['value']) if row else 1.0


def is_rate_manual(db):
    """Проверить, установлен ли курс вручную. ГЛОБАЛЬНО."""
    db.cursor.execute("SELECT value FROM settings WHERE key = 'exchange_rate_manual'")
    row = db.cursor.fetchone()
    return row and row['value'] == '1'


def get_rate_history(db, limit=48):
    """Получить историю курса (по умолчанию за 24 часа при 30-мин интервале). ГЛОБАЛЬНО."""
    db.cursor.execute('''
        SELECT rate, ai_value, total_members, avg_active, denominator,
               is_manual, changed_by, timestamp
        FROM exchange_rate_history
        ORDER BY id DESC
        LIMIT ?
    ''', (limit,))
    return db.cursor.fetchall()


def get_rate_history_30d(db):
    """Получить историю курса за 30 дней (для владельца). ГЛОБАЛЬНО."""
    db.cursor.execute('''
        SELECT rate, ai_value, total_members, avg_active, denominator,
               is_manual, timestamp
        FROM exchange_rate_history
        WHERE timestamp >= datetime('now', '-30 days')
        ORDER BY timestamp ASC
    ''')
    return db.cursor.fetchall()


# ═══════════════════════════════════════════════════
# TOP-5 ACTIVISTS HISTORY (ТЕНАНТИЗИРОВАНО)
# ═══════════════════════════════════════════════════

def save_top_snapshot(db, workspace_id, date, time_slot, user_id, rank, activity_index):
    """Сохранить одну запись ТОП-5 снапшота."""
    try:
        db.cursor.execute('''
            INSERT INTO top_activists_history
                (workspace_id, date, time_slot, user_id, rank, activity_index)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (workspace_id, date, time_slot, user_id, rank, activity_index))
        db.conn.commit()
    except Exception as e:
        logger.error(f"Error saving top snapshot: {e}")


def get_latest_top_snapshot(db, workspace_id):
    """Получить последний снапшот ТОП-5 для workspace."""
    db.cursor.execute('''
        SELECT tah.*, u.username, u.first_name
        FROM top_activists_history tah
        JOIN users u ON tah.user_id = u.user_id
        WHERE tah.workspace_id = ?
          AND (tah.date, tah.time_slot) = (
              SELECT date, time_slot
              FROM top_activists_history
              WHERE workspace_id = ?
              ORDER BY id DESC
              LIMIT 1
          )
        ORDER BY tah.rank ASC
    ''', (workspace_id, workspace_id))
    return db.cursor.fetchall()


def get_previous_top_snapshot(db, workspace_id):
    """Получить предыдущий снапшот ТОП-5 (для сравнения стрелок ↑↓)."""
    # Сначала находим последний
    db.cursor.execute('''
        SELECT DISTINCT date, time_slot
        FROM top_activists_history
        WHERE workspace_id = ?
        ORDER BY date DESC, time_slot DESC
        LIMIT 2
    ''', (workspace_id,))
    rows = db.cursor.fetchall()
    if len(rows) < 2:
        return []

    prev = rows[1]
    db.cursor.execute('''
        SELECT tah.*, u.username, u.first_name
        FROM top_activists_history tah
        JOIN users u ON tah.user_id = u.user_id
        WHERE tah.workspace_id = ? AND tah.date = ? AND tah.time_slot = ?
        ORDER BY tah.rank ASC
    ''', (workspace_id, prev['date'], prev['time_slot']))
    return db.cursor.fetchall()


def get_user_top_appearances(db, workspace_id, user_id, days=30):
    """
    Сколько раз пользователь был в ТОП-5 за N дней в этом workspace.

    Returns:
        dict: {'total_snapshots': int, 'appearances': int, 'percentage': float,
               'best_rank': int, 'avg_rank': float}
    """
    db.cursor.execute('''
        SELECT COUNT(DISTINCT date || time_slot) as total
        FROM top_activists_history
        WHERE workspace_id = ? AND date >= date('now', ?)
    ''', (workspace_id, f'-{days} days'))
    total_snapshots = db.cursor.fetchone()['total'] or 0

    db.cursor.execute('''
        SELECT COUNT(*) as appearances,
               MIN(rank) as best_rank,
               AVG(rank) as avg_rank
        FROM top_activists_history
        WHERE workspace_id = ? AND user_id = ? AND date >= date('now', ?)
    ''', (workspace_id, user_id, f'-{days} days'))
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


def get_all_top_appearances(db, workspace_id, days=30):
    """
    Статистика появлений ВСЕХ пользователей в ТОП-5 за N дней в этом workspace.
    Для отображения владельцу.
    """
    db.cursor.execute('''
        SELECT COUNT(DISTINCT date || time_slot) as total
        FROM top_activists_history
        WHERE workspace_id = ? AND date >= date('now', ?)
    ''', (workspace_id, f'-{days} days'))
    total_snapshots = db.cursor.fetchone()['total'] or 0

    db.cursor.execute('''
        SELECT tah.user_id, u.username, u.first_name,
               COUNT(*) as appearances,
               MIN(tah.rank) as best_rank,
               ROUND(AVG(tah.rank), 1) as avg_rank
        FROM top_activists_history tah
        JOIN users u ON tah.user_id = u.user_id
        WHERE tah.workspace_id = ? AND tah.date >= date('now', ?)
        GROUP BY tah.user_id
        ORDER BY appearances DESC, best_rank ASC
    ''', (workspace_id, f'-{days} days'))

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


# ═══════════════════════════════════════════════════
# HOURLY STATS (ТЕНАНТИЗИРОВАНО)
# ═══════════════════════════════════════════════════

def update_user_activity_hourly(db, workspace_id, user_id, date, hour, **kwargs):
    """Атомарное обновление почасовой статистики (защита от race condition).

    workspace_id вторым аргументом, далее user_id/date/hour. UNIQUE-индекс
    остался на (user_id, date, hour) — если два workspace разделят user в
    один час, придётся переделать на (workspace_id, user_id, date, hour).
    TODO(multi-tenancy-pk): обновить UNIQUE до composite перед onboarding
    2-го workspace. См. multi_tenancy_pk_debt.md.
    """
    # Список разрешенных полей
    allowed = [
        'total_chars', 'total_messages', 'total_words', 'reactions_given',
        'reactions_received', 'replies_received', 'replies_sent',
        'mentions_received', 'media_sent', 'other_threads_posts'
    ]

    # Фильтруем входящие данные
    data = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not data:
        return

    # Подготовка SQL запроса
    columns = ['workspace_id', 'user_id', 'date', 'hour'] + list(data.keys())
    placeholders = ', '.join(['?'] * len(columns))

    # Инструкция для обновления: прибавляем новые значения к старым
    update_stmt = ", ".join([f"{col} = {col} + excluded.{col}" for col in data.keys()])

    sql = f'''
        INSERT INTO user_stats_hourly ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(user_id, date, hour) DO UPDATE SET
        {update_stmt}
    '''

    try:
        params = [workspace_id, user_id, date, hour] + list(data.values())
        db.cursor.execute(sql, params)
        db.conn.commit()
    except Exception as e:
        import logging
        logging.error(f"Hourly Stats Update Error: {e}")
        db.conn.rollback()


def save_top5_percent(db, workspace_id, entries, window_start, window_end):
    """
    Сохранить кеш ТОП-5 % активности для workspace.
    entries: list of dict {'user_id', 'percent', 'activity_index', 'rank'}
    """
    try:
        db.cursor.execute(
            'DELETE FROM top_activists_percent WHERE workspace_id = ?',
            (workspace_id,)
        )
        for e in entries:
            db.cursor.execute('''
                INSERT INTO top_activists_percent
                    (workspace_id, user_id, percent, activity_index, rank, window_start, window_end)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (workspace_id, e['user_id'], e['percent'], e['activity_index'], e['rank'],
                  window_start, window_end))
        db.conn.commit()
    except Exception as e:
        logger.error(f"Error saving top5 percent: {e}")


def get_top5_percent(db, workspace_id):
    """Получить кешированный ТОП-5 % активности для workspace (до 10 для фильтрации замов)."""
    db.cursor.execute('''
        SELECT tap.*, u.username, u.first_name
        FROM top_activists_percent tap
        JOIN users u ON tap.user_id = u.user_id
        WHERE tap.workspace_id = ?
        ORDER BY tap.rank ASC
        LIMIT 10
    ''', (workspace_id,))
    return db.cursor.fetchall()


def cleanup_old_hourly_stats(db, days_to_keep=2):
    """Удалить hourly-данные старше N дней (cross-workspace cleanup — глобально)."""
    try:
        db.cursor.execute('''
            DELETE FROM user_stats_hourly
            WHERE date < date('now', ?)
        ''', (f'-{days_to_keep} days',))
        db.conn.commit()
    except Exception as e:
        logger.error(f"Error cleaning hourly stats: {e}")
