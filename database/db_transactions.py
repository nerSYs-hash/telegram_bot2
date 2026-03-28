#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Транзакции и Центробанк. Вынесено из Database."""

from database.db_settings import get_setting, set_setting


def add_transaction(db, from_user_id, to_user_id, amount, transaction_type, description=None):
    """Record transaction (with decimal support)"""
    amount = round(float(amount), 2)

    db.cursor.execute('''
        INSERT INTO transactions 
        (from_user_id, to_user_id, amount, transaction_type, description)
        VALUES (?, ?, ?, ?, ?)
    ''', (from_user_id, to_user_id, amount, transaction_type, description))
    db.conn.commit()
    return db.cursor.lastrowid


def get_bank_balance(db):
    """Get central bank balance"""
    try:
        val = get_setting(db, 'bank_balance', '10000000')
        return float(val)
    except (ValueError, TypeError):
        return 10000000.0


def update_bank_balance(db, amount, operation='subtract'):
    """Update bank balance"""
    current = get_bank_balance(db)
    amount = float(amount)

    if operation == 'add':
        new_balance = current + amount
    elif operation == 'subtract':
        if current < amount:
            return False
        new_balance = current - amount
    else:
        new_balance = amount

    new_balance = round(new_balance, 2)
    set_setting(db, 'bank_balance', str(new_balance))
    return True
