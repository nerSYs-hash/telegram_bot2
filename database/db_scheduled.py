#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Отложенные публикации. Вынесено из Database."""


def add_scheduled_post(db, author_id, text, photo_file_id, target_chat_id, thread_id, publish_at):
    """Add a scheduled post"""
    db.cursor.execute('''
        INSERT INTO scheduled_posts (author_id, text, photo_file_id, target_chat_id, thread_id, publish_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (author_id, text, photo_file_id, target_chat_id, thread_id, publish_at))
    db.conn.commit()
    return db.cursor.lastrowid


def get_scheduled_post(db, post_id):
    """Get a single scheduled post by ID"""
    db.cursor.execute('''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
        WHERE sp.id = ?
    ''', (post_id,))
    return db.cursor.fetchone()


def update_scheduled_post(db, post_id, **kwargs):
    """
    Update fields of a scheduled post.
    
    Supported kwargs: text, photo_file_id, thread_id, publish_at
    Only updates fields that are explicitly passed.
    """
    allowed_fields = {'text', 'photo_file_id', 'thread_id', 'publish_at'}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not updates:
        return False
    
    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [post_id, 'pending']
    
    db.cursor.execute(f'''
        UPDATE scheduled_posts
        SET {set_clause}
        WHERE id = ? AND status = ?
    ''', values)
    db.conn.commit()
    return db.cursor.rowcount > 0


def get_pending_scheduled_posts(db, before_time):
    """Get all pending scheduled posts that should be published"""
    db.cursor.execute('''
        SELECT * FROM scheduled_posts
        WHERE status = 'pending' AND publish_at <= ?
        ORDER BY publish_at ASC
    ''', (before_time,))
    return db.cursor.fetchall()


def mark_scheduled_post_published(db, post_id):
    """Mark a scheduled post as published"""
    db.cursor.execute('''
        UPDATE scheduled_posts 
        SET status = 'published', published_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (post_id,))
    db.conn.commit()


def get_scheduled_posts_list(db, status='pending'):
    """Get list of scheduled posts"""
    db.cursor.execute('''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
        WHERE sp.status = ?
        ORDER BY sp.publish_at ASC
    ''', (status,))
    return db.cursor.fetchall()


def delete_scheduled_post(db, post_id):
    """Delete a scheduled post"""
    db.cursor.execute('DELETE FROM scheduled_posts WHERE id = ? AND status = ?', (post_id, 'pending'))
    db.conn.commit()
    return db.cursor.rowcount > 0
