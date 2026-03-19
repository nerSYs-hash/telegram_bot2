#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль экономики — функции прямого управления кошельком.

Вынесено из command_handler.py.
Все функции — модульного уровня (без класса).
db, admin_id передаются явно.

Использование в command_handler.py:
    from handlers.commands.economy_commands import (
        safe_name, balance_command, pay_command, give_pulse_command, wipe_balances_command
    )
"""

from telegram import Update
from telegram.ext import ContextTypes
from utils.helpers import format_number


def safe_name(user_data):
    """Безопасное получение имени пользователя (никогда не None)"""
    if not user_data:
        return "Unknown"
    name = user_data.get('username') or user_data.get('first_name')
    if not name or str(name).strip() == '' or str(name) == 'None':
        return f"ID:{user_data.get('user_id', '?')}"
    return str(name)


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Handle /balance command"""
    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await update.message.reply_text("Сначала используй /start")
        return

    balance = user_data['balance']

    # Get user's title if any
    db.cursor.execute('''
        SELECT title_name, emoji, multiplier 
        FROM titles 
        WHERE user_id = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        ORDER BY granted_at DESC LIMIT 1
    ''', (user.id,))
    title = db.cursor.fetchone()

    message = f"💰 Ваш баланс: {format_number(balance)} 💎 Пульсов"

    if title:
        message += f"\n\n{title['emoji']} Титул: {title['title_name']}"
        message += f"\n⚡ Множитель: x{title['multiplier']}"

    await update.message.reply_text(message)


async def give_pulse_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db, admin_id):
    """Handle /give_pulse command (admin only)"""
    user = update.effective_user

    if user.id != admin_id:
        await update.message.reply_text("У вас нет прав для этой команды.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /give_pulse <user_id> <amount>\n"
            "Пример: /give_pulse 123456789 1000"
        )
        return

    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])

        if amount <= 0:
            await update.message.reply_text("Сумма должна быть положительной.")
            return

        # Check bank balance
        bank_balance = db.get_bank_balance()
        if bank_balance < amount:
            await update.message.reply_text(
                f"Недостаточно средств в Банке.\n"
                f"Доступно: {format_number(bank_balance)} Пульсов"
            )
            return

        # Check if user exists
        target_user = db.get_user(target_user_id)
        if not target_user:
            await update.message.reply_text("Пользователь не найден в базе данных.")
            return

        # Give pulse
        db.update_user_balance(target_user_id, amount, 'add')
        db.update_bank_balance(amount, 'subtract')
        db.add_transaction(
            None,  # From bank
            target_user_id,
            amount,
            'admin_give',
            'Выдача от администратора'
        )

        new_bank_balance = db.get_bank_balance()
        username = target_user['username'] or target_user['first_name']

        await update.message.reply_text(
            f"✅ Успешно выдано!\n\n"
            f"👤 Пользователю @{username}\n"
            f"💎 Выдано: {format_number(amount)} Пульсов\n"
            f"🏦 Остаток в Банке: {format_number(new_bank_balance)} Пульсов"
        )

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎁 Вам начислено {format_number(amount)} 💎 Пульсов!\n"
                     f"Новый баланс: {format_number(target_user['balance'] + amount)} 💎"
            )
        except:
            pass

    except ValueError:
        await update.message.reply_text("Неверный формат. Используйте числа.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")


async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Handle /pay command - transfer pulse to another user"""
    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await update.message.reply_text("Сначала используй /start")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /pay @username <amount>\n"
            "Пример: /pay @john 100"
        )
        return

    try:
        target_username = context.args[0].lstrip('@')
        amount = int(context.args[1])

        if amount <= 0:
            await update.message.reply_text("Сумма должна быть положительной.")
            return

        # Check sender balance
        if user_data['balance'] < amount:
            await update.message.reply_text(
                f"Недостаточно средств.\n"
                f"Ваш баланс: {format_number(user_data['balance'])} 💎"
            )
            return

        # Find target user
        db.cursor.execute(
            'SELECT * FROM users WHERE username = ?',
            (target_username,)
        )
        target_user = db.cursor.fetchone()

        if not target_user:
            await update.message.reply_text(
                f"Пользователь @{target_username} не найден."
            )
            return

        if target_user['user_id'] == user.id:
            await update.message.reply_text("Нельзя переводить самому себе!")
            return

        # Transfer
        db.update_user_balance(user.id, amount, 'subtract')
        db.update_user_balance(target_user['user_id'], amount, 'add')
        db.add_transaction(
            user.id,
            target_user['user_id'],
            amount,
            'transfer',
            'Прямой перевод'
        )

        await update.message.reply_text(
            f"✅ Перевод выполнен!\n\n"
            f"💸 @{target_username} получил {format_number(amount)} 💎 Пульсов\n"
            f"💰 Ваш баланс: {format_number(user_data['balance'] - amount)} 💎"
        )

        # Notify recipient
        try:
            await context.bot.send_message(
                chat_id=target_user['user_id'],
                text=f"💰 @{user.username or user.first_name} перевел вам "
                     f"{format_number(amount)} 💎 Пульсов!"
            )
        except:
            pass

    except ValueError:
        await update.message.reply_text("Неверный формат суммы.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")

async def wipe_balances_command(update, context, db, admin_id):
    """
    Глобальное обнуление экономики (Вайп). 
    Доступно только Владельцу. Требует подтверждения.
    """
    user = update.effective_user
    
    # 1. Жесткая проверка: только Владелец (admin_id из .env) может это сделать
    if user.id != admin_id:
        await update.message.reply_text("⛔️ Эта команда доступна только Владельцу бота.")
        return

    # 2. Проверяем предохранитель (аргумент CONFIRM)
    args = context.args
    if not args or args[0] != 'CONFIRM':
        await update.message.reply_text(
            "⚠️ <b>ВНИМАНИЕ! ГЛОБАЛЬНЫЙ СБРОС</b> ⚠️\n\n"
            "Это действие необратимо обнулит балансы и замороженные средства <b>ВСЕХ</b> пользователей в чате.\n\n"
            "Если вы точно хотите это сделать перед стартом, введите команду с подтверждением:\n"
            "👉 <code>/wipe_balances CONFIRM</code>",
            parse_mode='HTML'
        )
        return

    # 3. Выполняем обнуление
    try:
        # Сбрасываем основной баланс и замороженный баланс у всех юзеров
        db.cursor.execute("UPDATE users SET balance = 0, frozen_balance = 0")
        
        # Обнуляем баланс самого Центробанка (опционально)
        db.cursor.execute("UPDATE settings SET value = '0' WHERE key = 'bank_balance'")
        
        db.conn.commit()

        await update.message.reply_text(
            "✅ <b>ЭКОНОМИКА УСПЕШНО ОБНУЛЕНА!</b>\n\n"
            "Все тестовые балансы сброшены. У всех пользователей теперь 0 Пульсов. "
            "Бот готов к официальному старту! 🚀",
            parse_mode='HTML'
        )
        
    except Exception as e:
        import logging
        logging.error(f"Ошибка при вайпе балансов: {e}")
        await update.message.reply_text(f"❌ Ошибка базы данных при обнулении: {e}")