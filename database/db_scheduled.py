#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Отложенные публикации (старый API).

V1.17.0a17 (multi-tenancy): scheduled_posts тенантизирована — все функции
принимают workspace_id первым аргументом после db. Это legacy-интерфейс
(text+target+publish_at), новый full-featured API — в db_press_release.py.
"""


def add_scheduled_post(db, workspace_id, author_id, text, photo_file_id, target_chat_id, thread_id, publish_at):
    """Add a scheduled post in workspace."""
    db.cursor.execute('''
        INSERT INTO scheduled_posts (workspace_id, author_id, text, photo_file_id, target_chat_id, thread_id, publish_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled')
    ''', (workspace_id, author_id, text, photo_file_id, target_chat_id, thread_id, publish_at))
    db.conn.commit()
    return db.cursor.lastrowid


def get_scheduled_post(db, workspace_id, post_id):
    """Get a single scheduled post by ID in workspace."""
    db.cursor.execute('''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
        WHERE sp.id = ? AND sp.workspace_id = ?
    ''', (post_id, workspace_id))
    return db.cursor.fetchone()


def update_scheduled_post(db, workspace_id, post_id, **kwargs):
    """
    Update fields of a scheduled post in workspace.

    Supported kwargs: text, photo_file_id, thread_id, publish_at
    Only updates fields that are explicitly passed.
    """
    allowed_fields = {'text', 'photo_file_id', 'thread_id', 'publish_at'}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return False

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [post_id, workspace_id, 'pending']

    db.cursor.execute(f'''
        UPDATE scheduled_posts
        SET {set_clause}
        WHERE id = ? AND workspace_id = ? AND status = ?
    ''', values)
    db.conn.commit()
    return db.cursor.rowcount > 0


def get_pending_scheduled_posts(db, workspace_id, before_time):
    """Get pending scheduled posts in workspace that should be published."""
    db.cursor.execute('''
        SELECT * FROM scheduled_posts
        WHERE workspace_id = ? AND status = 'pending' AND publish_at <= ?
        ORDER BY publish_at ASC
    ''', (workspace_id, before_time))
    return db.cursor.fetchall()


def mark_scheduled_post_published(db, workspace_id, post_id):
    """Mark a scheduled post as published."""
    db.cursor.execute('''
        UPDATE scheduled_posts
        SET status = 'published', published_at = CURRENT_TIMESTAMP
        WHERE id = ? AND workspace_id = ?
    ''', (post_id, workspace_id))
    db.conn.commit()


def get_scheduled_posts_list(db, workspace_id, status='pending'):
    """Get list of scheduled posts in workspace."""
    db.cursor.execute('''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
        WHERE sp.workspace_id = ? AND sp.status = ?
        ORDER BY sp.publish_at ASC
    ''', (workspace_id, status))
    return db.cursor.fetchall()


def delete_scheduled_post(db, workspace_id, post_id):
    """Delete a scheduled post in workspace (only if pending)."""
    db.cursor.execute(
        'DELETE FROM scheduled_posts WHERE id = ? AND workspace_id = ? AND status = ?',
        (post_id, workspace_id, 'pending')
    )
    db.conn.commit()
    return db.cursor.rowcount > 0
