#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Настройки и фичи — вынесено из Database."""


def get_setting(db, key, default=None):
    """Get setting value"""
    db.cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = db.cursor.fetchone()
    return result['value'] if result else default


def set_setting(db, key, value):
    """Set setting value"""
    db.cursor.execute('''
        INSERT OR REPLACE INTO settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (key, str(value)))
    db.conn.commit()


def initialize_settings(db, initial_bank_balance=10000000, initial_difficulty_k=5.0):
    """Initialize default settings"""
    settings = [
        ('bank_balance', str(initial_bank_balance)),
        ('difficulty_k', str(initial_difficulty_k)),
        ('reactor_balance', '0'),
        ('reactor_goal', '10000'),
        ('reactor_level', '0')
    ]

    for key, value in settings:
        db.cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value)
            VALUES (?, ?)
        ''', (key, value))

    db.conn.commit()


def is_feature_enabled(db, feature_name):
    """Check if a feature is enabled"""
    key = f'feature_{feature_name}'
    value = get_setting(db, key, '1')  # Default: enabled
    return value == '1'


def toggle_feature(db, feature_name):
    """Toggle feature on/off"""
    key = f'feature_{feature_name}'
    current = get_setting(db, key, '1')
    new_value = '0' if current == '1' else '1'
    set_setting(db, key, new_value)
    return new_value == '1'
