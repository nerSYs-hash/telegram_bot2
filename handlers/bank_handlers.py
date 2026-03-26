#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Обработчики банка — вынесены из callback_handler.py

Все функции — модульного уровня (без класса).
db, admin_id передаются явно.

Использование в callback_handler.py:
    from handlers.bank_handlers import (
        show_bank, show_bank_menu,
        show_exchange_rate, start_bank_transfer,
        select_transfer_amount, execute_bank_transfer,
    )
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import format_number


async def show_bank_menu(query, user, db, admin_id):
    """Show simple bank menu (like ReplyKeyboard button)"""
    is_owner = user.id == admin_id

    kb = [
        [InlineKeyboardButton("💱 Курс Пульса", callback_data="show_exchange_rate")],
    ]
    if is_owner:
        kb.append([InlineKeyboardButton("💸 Перевод из банка", callback_data="bank_transfer_start")])

    await query.edit_message_text(
        "🏦 ЦЕНТРОБАНК\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def show_bank(query, user, db, admin_id):
    """Show bank panel"""
    # Check if user is owner for full access
    is_owner = user.id == admin_id
    
    if is_owner:
        # Full panel for owner
        bank_balance = db.get_bank_balance()

        message = f"🏦 ПАНЕЛЬ ЦЕНТРОБАНКА\n\n"
        message += f"💰 Баланс Банка: {format_number(bank_balance)} 💎"

        keyboard = [
            [InlineKeyboardButton("💱 Текущий курс", callback_data="show_exchange_rate")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="bank_refresh")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_bank")]
        ]
    else:
        # Limited panel for regular users
        rate = db.get_exchange_rate()
        user_data = db.get_user(user.id)
        balance = user_data['balance'] if user_data else 0
        
        message = f"🏦 ЦЕНТРОБАНК\n\n"
        message += f"💱 Текущий курс: 1 💎 = {rate} ₽\n\n"
        message += f"Ваш баланс:\n"
        message += f"💎 {format_number(balance)} Пульсов\n"
        message += f"💵 ≈ {balance * rate:.2f} ₽"
        
        keyboard = [
            [InlineKeyboardButton("💱 Текущий курс", callback_data="show_exchange_rate")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)


async def show_exchange_rate(query, user, db):
    """Show current exchange rate (for all users)"""
    rate = db.get_exchange_rate()
    
    user_data = db.get_user(user.id)
    balance = user_data['balance'] if user_data else 0
    rub_value = balance * rate
    
    message = f"💱 ТЕКУЩИЙ КУРС\n\n"
    message += f"1 💎 Пульс = {rate} ₽\n\n"
    
    if user_data:
        message += f"Ваш баланс:\n"
        message += f"💎 {format_number(balance)} Пульсов\n"
        message += f"💵 ≈ {rub_value:.2f} ₽"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu_bank")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup)

async def start_bank_transfer(query, user, context, db, admin_id):
    """Start bank transfer to user (owner only) - with inline buttons"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return
    
    bank_balance = db.get_bank_balance()
    
    # Get top users by balance (excluding admins)
    top_users = db.get_top_users_by_balance(limit=10, exclude_admins=True)
    
    if not top_users:
        await query.edit_message_text(
            "📭 Нет пользователей для перевода",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в ЦБ", callback_data="menu_bank")
                
            ]])
        )
        return
    
    message = f"💸 ПЕРЕВОД ИЗ БАНКА\n\n"
    message += f"💰 Баланс банка: {format_number(bank_balance)} 💎\n\n"
    message += "Выберите получателя:"
    
    keyboard = []
    for u in top_users[:10]:  # Top 10
        username = u['username'] or u['first_name'] or f"User{u['user_id']}"
        balance = format_number(u['balance'])
        keyboard.append([
            InlineKeyboardButton(
                f"👤 @{username} - {balance} 💎",
                callback_data=f"bt_user_{u['user_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def select_transfer_amount(query, user_id, user, context, db, admin_id):
    """Select amount for bank transfer"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return
    
    target_user = db.get_user(user_id)
    if not target_user:
        await query.answer("Пользователь не найден", show_alert=True)
        return
    
    username = target_user['username'] or target_user['first_name'] or f"User{user_id}"
    bank_balance = db.get_bank_balance()
    
    message = f"💸 ПЕРЕВОД ДЛЯ @{username}\n\n"
    message += f"💰 Баланс банка: {format_number(bank_balance)} 💎\n\n"
    message += "Выберите сумму:"
    
    keyboard = [
        [
            InlineKeyboardButton("50 💎", callback_data=f"bt_amount_{user_id}_50"),
            InlineKeyboardButton("100 💎", callback_data=f"bt_amount_{user_id}_100")
        ],
        [
            InlineKeyboardButton("500 💎", callback_data=f"bt_amount_{user_id}_500"),
            InlineKeyboardButton("1000 💎", callback_data=f"bt_amount_{user_id}_1000")
        ],
        [InlineKeyboardButton("✏️ Своя сумма", callback_data=f"bt_custom_{user_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="bank_transfer_start")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def execute_bank_transfer(query, user_id, amount, user, context, db, admin_id):
    """Execute bank transfer"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return
    
    try:
        amount = float(amount)
        
        # Check bank balance
        bank_balance = db.get_bank_balance()
        if amount > bank_balance:
            await query.answer(
                f"❌ Недостаточно средств!\nВ банке: {format_number(bank_balance)} 💎",
                show_alert=True
            )
            return
        
        target_user = db.get_user(user_id)
        if not target_user:
            await query.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        # Execute transfer
        db.update_bank_balance(amount, 'subtract')
        db.update_user_balance(user_id, amount, 'add')
        db.add_transaction(
            None,
            user_id,
            amount,
            'bank_transfer',
            f'Transfer from bank by owner'
        )
        
        username = target_user['username'] or target_user['first_name'] or f"User{user_id}"
        new_bank_balance = db.get_bank_balance()
        
        await query.edit_message_text(
            f"✅ ПЕРЕВОД ВЫПОЛНЕН!\n\n"
            f"👤 Получатель: @{username}\n"
            f"💎 Сумма: {format_number(amount)} Пульсов\n\n"
            f"💰 Остаток в банке: {format_number(new_bank_balance)} 💎",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
            ]])
        )
        
        # Notify recipient
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"💸 Вам зачислены Пульсы из банка!\n\n"
                     f"💎 Сумма: {format_number(amount)} Пульсов\n"
                     f"💰 Ваш баланс: {format_number(target_user['balance'] + amount)} 💎"
            )
        except:
            pass
            
    except Exception as e:
        await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

