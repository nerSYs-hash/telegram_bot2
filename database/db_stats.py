#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Статистика активности и динамика пользователей. Вынесено из Database.

V1.17.0a16 (multi-tenancy):
  • user_stats / chat_stats / stat_events_log / topics — тенантизированы,
    функции принимают workspace_id первым аргументом после db.
  • users — ГЛОБАЛЬНАЯ (joined_at — первый вход в сеть); per-workspace
    членство в workspace_members.joined_at. get_joined_users_count пока
    остаётся global-style (single-tenant safe); TODO при онбординге 2-го
    workspace переписать через JOIN workspace_members.
  • transactions — тенантизированы, get_left_users_count фильтрует ws_id.
"""
import logging


def register_stat_event(db, workspace_id, event_id: str) -> bool:
    """Регистрирует событие статистики для workspace. Возвращает True если новое.

    event_id уникален в скоупе workspace (одинаковый ключ в разных WS возможен).
    """
    try:
        db.cursor.execute(
            'INSERT OR IGNORE INTO stat_events_log (workspace_id, event_id) VALUES (?, ?)',
            (workspace_id, event_id)
        )
        db.conn.commit()
        return db.cursor.rowcount > 0
    except Exception as e:
        logging.error(f"register_stat_event error: {e}")
        return True  # при ошибке — разрешаем, чтобы не терять данные


def cleanup_stat_events_log(db, older_than_days: int = 3):
    """Удаляет записи старше N дней — cross-workspace очистка по дате."""
    try:
        cutoff = int(__import__('time').time()) - older_than_days * 86400
        db.cursor.execute('DELETE FROM stat_events_log WHERE ts < ?', (cutoff,))
        deleted = db.cursor.rowcount
        db.conn.commit()
        if deleted:
            logging.info(f"🧹 stat_events_log: удалено {deleted} старых записей")
    except Exception as e:
        logging.error(f"cleanup_stat_events_log error: {e}")


def update_user_activity(db, workspace_id, user_id, date, event_id: str = None, **kwargs):
    """Обновление статистики пользователя в workspace.

    event_id — уникальный ключ события (напр. 'react_123_456_2026-04-24').
    Если передан и уже есть в stat_events_log (для этого workspace) — вызов
    игнорируется (дедупликация).

    V1.17.0k8 (M1): ON CONFLICT target = composite PK
    (workspace_id, user_id, date). До 27.05 был хардкод (user_id, date),
    что после composite_pk_fix (13.05) валило INSERT в except.
    """
    if not kwargs:
        return

    if event_id is not None:
        if not register_stat_event(db, workspace_id, event_id):
            logging.debug(f"[DEDUP] пропущен дубль: {event_id}")
            return

    # Список колонок, которые мы обновляем
    allowed_cols = [
        'total_chars', 'total_messages', 'total_words', 'reactions_given',
        'reactions_received', 'replies_received', 'replies_sent',
        'mentions_received', 'media_sent', 'other_threads_posts',
        'edited_count', 'links_sent',
    ]

    # Очищаем входящие данные
    data = {k: v for k, v in kwargs.items() if k in allowed_cols and v is not None}

    columns = ['workspace_id', 'user_id', 'date'] + list(data.keys())
    placeholders = ', '.join(['?'] * len(columns))

    # ON CONFLICT по composite PK (workspace_id, user_id, date)
    update_stmt = ", ".join([f"{col} = {col} + excluded.{col}" for col in data.keys()])

    sql = f'''
        INSERT INTO user_stats ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(workspace_id, user_id, date) DO UPDATE SET
        {update_stmt}
    '''

    try:
        params = [workspace_id, user_id, date] + list(data.values())
        db.cursor.execute(sql, params)
        db.conn.commit()
    except Exception as e:
        logging.error(f"DB Stats Error: {e}")
        db.conn.rollback()


def get_active_core_count(db, workspace_id, date):
    """Get number of active users for date in workspace."""
    db.cursor.execute('''
        SELECT COUNT(DISTINCT user_id) as count
        FROM user_stats
        WHERE workspace_id = ? AND date = ? AND total_messages > 0
    ''', (workspace_id, date))
    result = db.cursor.fetchone()
    return result['count'] if result else 0


def register_topic(db, workspace_id, chat_id, thread_id, thread_name=None):
    """Register or update a topic/thread. Never overwrites a real name with a generic one."""
    is_main = (thread_id is None)
    default_name = 'General' if is_main else f'Ветка #{thread_id}'
    name_to_insert = thread_name or default_name

    # Check if a real name already exists
    db.cursor.execute('''
        SELECT thread_name FROM topics
        WHERE workspace_id = ? AND chat_id = ? AND thread_id IS ?
    ''', (workspace_id, chat_id, thread_id))
    existing = db.cursor.fetchone()

    if existing:
        existing_name = existing['thread_name'] or ''
        is_new_generic = (
            name_to_insert.startswith('Ветка #') or
            name_to_insert.startswith('Ветка ') or
            name_to_insert == default_name
        )
        is_existing_real = (
            existing_name and
            not existing_name.startswith('Ветка #') and
            not existing_name.startswith('Ветка ')
        )

        if is_new_generic and is_existing_real:
            # Keep existing real name, just bump counters
            db.cursor.execute('''
                UPDATE topics SET
                    last_message_at = CURRENT_TIMESTAMP,
                    total_messages = total_messages + 1
                WHERE workspace_id = ? AND chat_id = ? AND thread_id IS ?
            ''', (workspace_id, chat_id, thread_id))
        else:
            db.cursor.execute('''
                UPDATE topics SET
                    last_message_at = CURRENT_TIMESTAMP,
                    total_messages = total_messages + 1,
                    thread_name = ?
                WHERE workspace_id = ? AND chat_id = ? AND thread_id IS ?
            ''', (name_to_insert, workspace_id, chat_id, thread_id))
    else:
        # Удаляем возможные дубли с тем же thread_id (актуально для NULL)
        db.cursor.execute(
            'DELETE FROM topics WHERE workspace_id = ? AND chat_id = ? AND thread_id IS ?',
            (workspace_id, chat_id, thread_id)
        )
        db.cursor.execute('''
            INSERT INTO topics (workspace_id, chat_id, thread_id, thread_name, is_main_thread,
                                last_message_at, total_messages)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
        ''', (workspace_id, chat_id, thread_id, name_to_insert, is_main))

    db.conn.commit()


def update_topic_name(db, workspace_id, chat_id, thread_id, thread_name):
    """Force-update topic name (from forum service messages). Always overwrites."""
    db.cursor.execute('''
        INSERT INTO topics (workspace_id, chat_id, thread_id, thread_name, is_main_thread,
                            last_message_at, total_messages)
        VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP, 0)
        ON CONFLICT(chat_id, thread_id) DO UPDATE SET
            thread_name = ?
    ''', (workspace_id, chat_id, thread_id, thread_name, thread_name))
    db.conn.commit()


def purge_unnamed_topics(db, workspace_id, chat_id):
    """Remove topics that only have generic names (Ветка #xxx) in this workspace."""
    db.cursor.execute('''
        DELETE FROM topics
        WHERE workspace_id = ? AND chat_id = ?
          AND is_main_thread = 0
          AND (thread_name LIKE 'Ветка #%' OR thread_name LIKE 'Ветка %')
          AND thread_name NOT LIKE '%General%'
    ''', (workspace_id, chat_id))
    deleted = db.cursor.rowcount
    db.conn.commit()
    return deleted


def get_all_topics(db, workspace_id, chat_id):
    """Get all unique topics/threads for a chat in workspace, deduplicated by thread_id."""
    db.cursor.execute('''
        SELECT
            chat_id,
            thread_id,
            MAX(thread_name)      AS thread_name,
            MAX(is_main_thread)   AS is_main_thread,
            MAX(last_message_at)  AS last_message_at,
            SUM(total_messages)   AS total_messages
        FROM topics
        WHERE workspace_id = ? AND chat_id = ?
        GROUP BY COALESCE(CAST(thread_id AS TEXT), '__main__')
        ORDER BY MAX(is_main_thread) DESC, SUM(total_messages) DESC
    ''', (workspace_id, chat_id))
    return db.cursor.fetchall()


def get_joined_users_count(db, start_date, end_date):
    """Получить количество вступивших пользователей за период.

    NOTE: users — ГЛОБАЛЬНАЯ таблица. Сейчас для single-tenant Pulse это
    «вступившие в сеть» = «вступившие в Pulse». При onboarding 2-го
    workspace переписать через JOIN workspace_members (joined_at в нём).
    TODO(multi-tenancy): per-workspace joined через workspace_members.
    """
    db.cursor.execute('''
        SELECT COUNT(*) as count
        FROM users
        WHERE joined_at >= ? AND joined_at <= ?
          AND is_admin = 0 AND is_owner = 0
    ''', (start_date, end_date))

    result = db.cursor.fetchone()
    return result['count'] if result else 0


def get_left_users_count(db, workspace_id, start_date, end_date):
    """Получить количество вышедших пользователей в workspace за период."""
    db.cursor.execute('''
        SELECT COUNT(*) as count
        FROM transactions
        WHERE workspace_id = ?
          AND transaction_type = 'return_on_leave'
          AND timestamp >= ? AND timestamp <= ?
    ''', (workspace_id, start_date, end_date))

    result = db.cursor.fetchone()
    return result['count'] if result else 0


def get_user_dynamics_stats(db, workspace_id, start_date, end_date):
    """Получить расширенную статистику динамики пользователей в workspace."""
    joined = get_joined_users_count(db, start_date, end_date)
    left = get_left_users_count(db, workspace_id, start_date, end_date)

    db.cursor.execute('''
        SELECT COUNT(*) as count
        FROM users
        WHERE joined_at < ?
          AND is_admin = 0 AND is_owner = 0
    ''', (start_date,))

    initial_users = db.cursor.fetchone()['count']
    net_change = joined - left

    retention_rate = 0.0
    if initial_users > 0:
        retention_rate = ((initial_users - left) / initial_users) * 100

    return {
        'joined': joined,
        'left': left,
        'net_change': net_change,
        'initial_users': initial_users,
        'retention_rate': round(retention_rate, 1),
        'final_users': initial_users + joined - left
    }
