#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Статистика активности и динамика пользователей. Вынесено из Database."""
import logging

def update_user_activity(db, user_id, date, **kwargs):
    """Обновление статистики пользователя (Защита от дублирования сообщений)"""
    if not kwargs:
        return

    # Список колонок, которые мы обновляем
    allowed_cols = [
        'total_chars', 'total_messages', 'total_words', 'reactions_given',
        'reactions_received', 'replies_received', 'replies_sent',
        'mentions_received', 'media_sent', 'other_threads_posts'
    ]
    
    # Очищаем входящие данные
    data = {k: v for k, v in kwargs.items() if k in allowed_cols and v is not None}
    
    columns = ['user_id', 'date'] + list(data.keys())
    placeholders = ', '.join(['?'] * len(columns))
    
    # Магия ON CONFLICT: если запись (user_id + date) уже есть, просто прибавляем значения
    update_stmt = ", ".join([f"{col} = {col} + excluded.{col}" for col in data.keys()])

    sql = f'''
        INSERT INTO user_stats ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(user_id, date) DO UPDATE SET
        {update_stmt}
    '''

    try:
        params = [user_id, date] + list(data.values())
        db.cursor.execute(sql, params)
        db.conn.commit()
    except Exception as e:
        logging.error(f"DB Stats Error: {e}")
        db.conn.rollback()


def get_active_core_count(db, date):
    """Get number of active users for date"""
    db.cursor.execute('''
        SELECT COUNT(DISTINCT user_id) as count
        FROM user_stats
        WHERE date = ? AND total_messages > 0
    ''', (date,))
    result = db.cursor.fetchone()
    return result['count'] if result else 0


def register_topic(db, chat_id, thread_id, thread_name=None):
    """Register or update a topic/thread. Never overwrites a real name with a generic one."""
    is_main = (thread_id is None)
    default_name = 'General' if is_main else f'Ветка #{thread_id}'
    name_to_insert = thread_name or default_name

    # Check if a real name already exists
    db.cursor.execute('''
        SELECT thread_name FROM topics 
        WHERE chat_id = ? AND thread_id IS ?
    ''', (chat_id, thread_id))
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
                WHERE chat_id = ? AND thread_id IS ?
            ''', (chat_id, thread_id))
        else:
            db.cursor.execute('''
                UPDATE topics SET
                    last_message_at = CURRENT_TIMESTAMP,
                    total_messages = total_messages + 1,
                    thread_name = ?
                WHERE chat_id = ? AND thread_id IS ?
            ''', (name_to_insert, chat_id, thread_id))
    else:
        # Удаляем возможные дубли с тем же thread_id (актуально для NULL, т.к. UNIQUE не защищает)
        db.cursor.execute(
            'DELETE FROM topics WHERE chat_id = ? AND thread_id IS ?',
            (chat_id, thread_id)
        )
        db.cursor.execute('''
            INSERT INTO topics (chat_id, thread_id, thread_name, is_main_thread,
                                last_message_at, total_messages)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
        ''', (chat_id, thread_id, name_to_insert, is_main))

    db.conn.commit()


def update_topic_name(db, chat_id, thread_id, thread_name):
    """Force-update topic name (from forum service messages). Always overwrites."""
    db.cursor.execute('''
        INSERT INTO topics (chat_id, thread_id, thread_name, is_main_thread,
                            last_message_at, total_messages)
        VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP, 0)
        ON CONFLICT(chat_id, thread_id) DO UPDATE SET
            thread_name = ?
    ''', (chat_id, thread_id, thread_name, thread_name))
    db.conn.commit()


def purge_unnamed_topics(db, chat_id):
    """Remove topics that only have generic names (Ветка #xxx)."""
    db.cursor.execute('''
        DELETE FROM topics 
        WHERE chat_id = ? 
          AND is_main_thread = 0
          AND (thread_name LIKE 'Ветка #%' OR thread_name LIKE 'Ветка %')
          AND thread_name NOT LIKE '%General%'
    ''', (chat_id,))
    deleted = db.cursor.rowcount
    db.conn.commit()
    return deleted


def get_all_topics(db, chat_id):
    """Get all unique topics/threads for a chat, deduplicated by thread_id."""
    db.cursor.execute('''
        SELECT
            chat_id,
            thread_id,
            MAX(thread_name)      AS thread_name,
            MAX(is_main_thread)   AS is_main_thread,
            MAX(last_message_at)  AS last_message_at,
            SUM(total_messages)   AS total_messages
        FROM topics
        WHERE chat_id = ?
        GROUP BY COALESCE(CAST(thread_id AS TEXT), '__main__')
        ORDER BY MAX(is_main_thread) DESC, SUM(total_messages) DESC
    ''', (chat_id,))
    return db.cursor.fetchall()


def get_joined_users_count(db, start_date, end_date):
    """Получить количество вступивших пользователей за период"""
    db.cursor.execute('''
        SELECT COUNT(*) as count 
        FROM users 
        WHERE joined_at >= ? AND joined_at <= ?
          AND is_admin = 0 AND is_owner = 0
    ''', (start_date, end_date))

    result = db.cursor.fetchone()
    return result['count'] if result else 0


def get_left_users_count(db, start_date, end_date):
    """Получить количество вышедших пользователей за период"""
    db.cursor.execute('''
        SELECT COUNT(*) as count 
        FROM transactions
        WHERE transaction_type = 'return_on_leave'
          AND timestamp >= ? AND timestamp <= ?
    ''', (start_date, end_date))

    result = db.cursor.fetchone()
    return result['count'] if result else 0


def get_user_dynamics_stats(db, start_date, end_date):
    """Получить расширенную статистику динамики пользователей"""
    joined = get_joined_users_count(db, start_date, end_date)
    left = get_left_users_count(db, start_date, end_date)

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
