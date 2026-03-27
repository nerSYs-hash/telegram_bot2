#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Реферальные ссылки и отслеживание вступлений. Вынесено из Database."""

import secrets


def create_referral_link(db, user_id):
    """Create a new one-time referral link token for user"""
    token = f"ref1_{secrets.token_hex(8)}"

    db.cursor.execute('''
        INSERT INTO referral_links (user_id, token)
        VALUES (?, ?)
    ''', (user_id, token))
    db.conn.commit()
    return token


def get_active_referral_link(db, user_id):
    """Get the current active (unused) referral link for user"""
    db.cursor.execute('''
        SELECT token FROM referral_links
        WHERE user_id = ? AND is_used = 0
        ORDER BY created_at DESC LIMIT 1
    ''', (user_id,))
    result = db.cursor.fetchone()
    return result['token'] if result else None


def get_or_create_referral_link(db, user_id):
    """Get active link or create a new one"""
    token = get_active_referral_link(db, user_id)
    if not token:
        token = create_referral_link(db, user_id)
    return token


def get_referrer_by_token(db, token):
    """Get referrer user_id by token without marking it as used"""
    db.cursor.execute('''
        SELECT user_id FROM referral_links
        WHERE token = ? AND is_used = 0
    ''', (token,))
    result = db.cursor.fetchone()
    return result['user_id'] if result else None


def use_referral_link(db, token, used_by_user_id):
    """Mark referral link as used and return referrer_id"""
    db.cursor.execute('''
        SELECT user_id, is_used FROM referral_links
        WHERE token = ?
    ''', (token,))
    result = db.cursor.fetchone()

    if not result:
        return None

    if result['is_used']:
        return None  # Link already used

    referrer_id = result['user_id']

    # Don't allow self-referral
    if referrer_id == used_by_user_id:
        return None

    # Mark as used
    db.cursor.execute('''
        UPDATE referral_links 
        SET is_used = 1, used_by = ?, used_at = CURRENT_TIMESTAMP
        WHERE token = ?
    ''', (used_by_user_id, token))
    db.conn.commit()

    return referrer_id


def get_referral_link_stats(db, user_id):
    """Get stats for user's referral links"""
    db.cursor.execute('''
        SELECT 
            COUNT(*) as total_links,
            SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END) as used_links
        FROM referral_links
        WHERE user_id = ?
    ''', (user_id,))
    return db.cursor.fetchone()


def record_user_join(db, user_id, username, first_name, join_method,
                     referrer_id=None, referral_token=None):
    """Record how a user joined the chat"""
    db.cursor.execute('''
        INSERT INTO user_joins (user_id, username, first_name, join_method, referrer_id, referral_token)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, join_method, referrer_id, referral_token))
    db.conn.commit()


def get_user_joins(db, start_date=None, end_date=None):
    """Get user join records with optional date filter"""
    query = '''
        SELECT uj.*, 
               ref_user.username as referrer_username,
               ref_user.first_name as referrer_first_name
        FROM user_joins uj
        LEFT JOIN users ref_user ON uj.referrer_id = ref_user.user_id
    '''
    params = []

    if start_date and end_date:
        query += ' WHERE uj.joined_at >= ? AND uj.joined_at <= ?'
        params = [start_date, end_date]

    query += ' ORDER BY uj.joined_at DESC'

    db.cursor.execute(query, params)
    return db.cursor.fetchall()
