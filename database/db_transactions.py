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


BANK_INITIAL_CAPITAL = 10_000_000  # стартовый капитал банка каждого workspace


def _bank_key(ws_id=1) -> str:
    """V1.17.0T (M5): банк per-ws. ws=1 — старый ключ (сохраняем баланс),
    остальные ws — отдельный ключ. Каждый ws стартует с 10М (дефолт)."""
    try:
        ws = int(ws_id)
    except (TypeError, ValueError):
        ws = 1
    return 'bank_balance' if ws == 1 else f'bank_balance_{ws}'


def get_bank_balance(db, ws_id=1):
    """Баланс банка workspace (виртуальные Пульсы). Новый ws → 10М по дефолту."""
    try:
        val = get_setting(db, _bank_key(ws_id), str(BANK_INITIAL_CAPITAL))
        return float(val)
    except (ValueError, TypeError):
        return float(BANK_INITIAL_CAPITAL)


def update_bank_balance(db, amount, operation='subtract', ws_id=1):
    """Изменить баланс банка workspace."""
    current = get_bank_balance(db, ws_id)
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
    set_setting(db, _bank_key(ws_id), str(new_balance))
    return True
