#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пользователи — CRUD и топы. Вынесено из Database."""

import hashlib


def add_user(db, user_id, username=None, first_name=None, last_name=None,
             is_admin=False, is_owner=False):
    """Add or update user"""
    referral_code = f"ref_{hashlib.md5(str(user_id).encode()).hexdigest()[:8]}"

    existing_user = get_user(db, user_id)

    if existing_user:
        db.cursor.execute('''
            UPDATE users 
            SET username = ?, first_name = ?, last_name = ?, 
                last_active = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (username, first_name, last_name, user_id))
    else:
        db.cursor.execute('''
            INSERT INTO users 
            (user_id, username, first_name, last_name, is_admin, is_owner, 
             referral_code, last_active, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0)
        ''', (user_id, username, first_name, last_name, is_admin, is_owner, referral_code))

    db.conn.commit()


def get_user(db, user_id):
    """Get user by ID"""
    db.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return db.cursor.fetchone()


def update_user_balance(db, user_id, amount, operation='add'):
    """Update user balance (with decimal support, rounded to 2 places)"""
    user = get_user(db, user_id)
    if not user:
        return False

    current_balance = float(user['balance'])
    amount = float(amount)

    if operation == 'add':
        new_balance = current_balance + amount
    elif operation == 'subtract':
        new_balance = current_balance - amount
        if new_balance < 0:
            return False
    else:
        new_balance = amount

    new_balance = round(new_balance, 2)

    db.cursor.execute('''
        UPDATE users SET balance = ?, last_active = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (new_balance, user_id))
    db.conn.commit()
    return True


def get_top_users_by_balance(db, limit=5, exclude_admins=True):
    """Get top users by balance"""
    query = 'SELECT * FROM users WHERE is_left = 0'
    if exclude_admins:
        query += ' AND is_admin = 0 AND is_owner = 0'
    query += ' ORDER BY balance DESC LIMIT ?'

    db.cursor.execute(query, (limit,))
    return db.cursor.fetchall()


def get_top_daily_earners(db, date, limit=5):
    """Get top users by earnings for a specific date (Daily Top)"""
    db.cursor.execute('''
        SELECT u.username, u.first_name, us.pulses_mined 
        FROM user_stats us
        JOIN users u ON us.user_id = u.user_id
        WHERE us.date = ? AND us.pulses_mined > 0
          AND (u.is_admin = 0 AND u.is_owner = 0)
          AND u.is_left = 0
        ORDER BY us.pulses_mined DESC
        LIMIT ?
    ''', (date, limit))
    return db.cursor.fetchall()


def get_top_activists(db, date, limit=5):
    """Get top users by message count for a specific date"""
    db.cursor.execute('''
        SELECT u.username, u.first_name, us.total_messages
        FROM user_stats us
        JOIN users u ON us.user_id = u.user_id
        WHERE us.date = ? AND us.total_messages > 0
          AND (u.is_admin = 0 AND u.is_owner = 0)
          AND u.is_left = 0
        ORDER BY us.total_messages DESC
        LIMIT ?
    ''', (date, limit))
    return db.cursor.fetchall()
