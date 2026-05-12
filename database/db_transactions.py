#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Транзакции и Центробанк. Вынесено из Database.

V1.17.0a16 (multi-tenancy):
  • transactions — тенантизирована, add_transaction принимает workspace_id.
  • bank_balance хранится в settings (key='bank_balance') — ГЛОБАЛЬНЫЙ для
    Pulse-токена. При multi-tenant модели биллинга бэнк станет per-workspace
    (TODO в подпроекте #6 биллинга).
"""

from database.db_settings import get_setting, set_setting


def add_transaction(db, workspace_id, from_user_id, to_user_id, amount, transaction_type, description=None):
    """Record transaction in workspace (with decimal support)."""
    amount = round(float(amount), 2)

    db.cursor.execute('''
        INSERT INTO transactions
        (workspace_id, from_user_id, to_user_id, amount, transaction_type, description)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (workspace_id, from_user_id, to_user_id, amount, transaction_type, description))
    db.conn.commit()
    return db.cursor.lastrowid


def get_bank_balance(db):
    """Get central bank balance. ГЛОБАЛЬНО (Pulse-токен)."""
    try:
        val = get_setting(db, 'bank_balance', '10000000')
        return float(val)
    except (ValueError, TypeError):
        return 10000000.0


def update_bank_balance(db, amount, operation='subtract'):
    """Update bank balance. ГЛОБАЛЬНО."""
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
