#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль Донатов — вынесен из CommandHandler.
Все функции принимают db как аргумент вместо self.db.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import format_number
from handlers.commands.economy_commands import safe_name


async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Handle /donate command — универсальная система донатов

    Форматы:
      /donate                              — интерактивное меню
      /donate @username <сумма> [коммент]   — донат пользователю
      /donate bank <сумма>                  — донат в Центробанк
      /donate reactor <сумма>               — донат в Реакторе
    """
    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await update.message.reply_text("Сначала используй /start")
        return

    if not db.is_feature_enabled('donate'):
        await update.message.reply_text("⛔ Функция донатов временно отключена.")
        return

    # Без аргументов — показать меню
    if not context.args:
        balance = user_data['balance']
        message = (
            f"🎁 СИСТЕМА ДОНАТОВ\n\n"
            f"💰 Ваш баланс: {format_number(balance)} 💎\n\n"
            f"Выберите действие или команды:\n"
            f"  /donate @user сумма — пользователю\n"
            f"  /donate bank сумма — в Центробанк\n"
            f"  /donate reactor сумма — в Реактор"
        )
        keyboard = [
            [InlineKeyboardButton("🎁 Пользователю", callback_data="donate_to_user_start")],
            [InlineKeyboardButton("🏦 В Центробанк", callback_data="donate_to_bank_start")],
            [InlineKeyboardButton("🔋 В Реактор", callback_data="donate_to_reactor_start")],
            [InlineKeyboardButton("📜 Мои донаты", callback_data="donate_history")],
            [InlineKeyboardButton("🔙 Меню", callback_data="back_to_menu")]
        ]
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ── /donate bank <сумма> ──
    if context.args[0].lower() == 'bank':
        await _donate_bank(update, context, db, user, user_data)
        return

    # ── /donate reactor <сумма> ──
    if context.args[0].lower() == 'reactor':
        await _donate_reactor(update, context, db, user, user_data)
        return

    # ── /donate @username <сумма> [комментарий] ──
    await _donate_user(update, context, db, user, user_data)


# ──────────────────────────────────────────────
#  Вспомогательные функции (вызываются из donate_command)
# ──────────────────────────────────────────────

async def _donate_bank(update, context, db, user, user_data):
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /donate bank <сумма>\nПример: /donate bank 500")
        return
    try:
        amount = round(float(context.args[1]), 2)
        if amount <= 0:
            await update.message.reply_text("Сумма должна быть положительной.")
            return
        if user_data['balance'] < amount:
            await update.message.reply_text(f"Недостаточно средств.\nВаш баланс: {format_number(user_data['balance'])} 💎")
            return

        db.update_user_balance(user.id, amount, 'subtract')
        db.update_bank_balance(amount, 'add')
        db.add_transaction(user.id, None, amount, 'donate_to_bank', 'Донат в Центробанк')

        sender_name = safe_name(user_data)
        await update.message.reply_text(
            f"🏦 Донат в Центробанк!\n\n"
            f"👤 От: @{sender_name}\n"
            f"💎 Сумма: {format_number(amount)} Пульсов\n"
            f"🏦 Банк: {format_number(db.get_bank_balance())} 💎\n"
            f"💰 Ваш баланс: {format_number(float(user_data['balance']) - amount)} 💎"
        )
    except ValueError:
        await update.message.reply_text("Неверный формат суммы.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")


async def _donate_reactor(update, context, db, user, user_data):
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /donate reactor <сумма>\nПример: /donate reactor 200")
        return
    try:
        amount = round(float(context.args[1]), 2)
        if amount <= 0:
            await update.message.reply_text("Сумма должна быть положительной.")
            return
        if user_data['balance'] < amount:
            await update.message.reply_text(f"Недостаточно средств.\nВаш баланс: {format_number(user_data['balance'])} 💎")
            return

        db.update_user_balance(user.id, amount, 'subtract')
        db.update_bank_balance(amount, 'add')
        db.cursor.execute('INSERT INTO reactor (user_id, amount) VALUES (?, ?)', (user.id, amount))
        current_reactor = float(db.get_setting('reactor_balance', 0))
        db.set_setting('reactor_balance', current_reactor + amount)
        db.add_transaction(user.id, None, amount, 'reactor_donation', 'Донат в Реактор')
        db.conn.commit()

        reactor_balance = float(db.get_setting('reactor_balance', 0))
        reactor_goal = float(db.get_setting('reactor_goal', 10000))
        progress = (reactor_balance / reactor_goal) * 100 if reactor_goal > 0 else 0

        await update.message.reply_text(
            f"🔋 Спасибо за вклад в Реактор!\n\n"
            f"💎 Пожертвовано: {format_number(amount)} Пульсов\n"
            f"🔋 Реактор: {format_number(reactor_balance)} / {format_number(reactor_goal)}\n"
            f"📊 Прогресс: {progress:.1f}%"
        )
    except ValueError:
        await update.message.reply_text("Неверный формат суммы.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")


async def _donate_user(update, context, db, user, user_data):
    try:
        target_username = context.args[0].lstrip('@')
        if len(context.args) < 2:
            await update.message.reply_text(
                "Использование: /donate @username <сумма> [комментарий]\n"
                "Пример: /donate @john 100 Спасибо!"
            )
            return

        amount = round(float(context.args[1]), 2)
        comment = ' '.join(context.args[2:]) if len(context.args) > 2 else None

        if amount <= 0:
            await update.message.reply_text("Сумма должна быть положительной.")
            return
        if user_data['balance'] < amount:
            await update.message.reply_text(f"Недостаточно средств.\nВаш баланс: {format_number(user_data['balance'])} 💎")
            return

        db.cursor.execute('SELECT * FROM users WHERE username = ?', (target_username,))
        target_user = db.cursor.fetchone()
        if not target_user:
            await update.message.reply_text(f"Пользователь @{target_username} не найден.")
            return
        if target_user['user_id'] == user.id:
            await update.message.reply_text("Нельзя отправить донат самому себе!")
            return

        db.update_user_balance(user.id, amount, 'subtract')
        db.update_user_balance(target_user['user_id'], amount, 'add')

        target_name = safe_name(target_user)
        sender_name = safe_name(user_data)
        desc = f'Донат для @{target_name}'
        if comment:
            desc += f': {comment[:100]}'
        db.add_transaction(user.id, target_user['user_id'], amount, 'donate_to_user', desc)

        result_msg = (
            f"🎁 Донат отправлен!\n\n"
            f"👤 От: @{sender_name}\n"
            f"👤 Кому: @{target_name}\n"
            f"💎 Сумма: {format_number(amount)} Пульсов"
        )
        if comment:
            result_msg += f"\n💬 {comment[:100]}"
        result_msg += f"\n\n💰 Ваш баланс: {format_number(float(user_data['balance']) - amount)} 💎"
        await update.message.reply_text(result_msg)

        try:
            notify = f"🎁 Вам пришёл донат!\n\n👤 От: @{sender_name}\n💎 Сумма: {format_number(amount)} Пульсов"
            if comment:
                notify += f"\n💬 {comment[:100]}"
            await context.bot.send_message(chat_id=target_user['user_id'], text=notify)
        except:
            pass

    except ValueError:
        await update.message.reply_text("Неверный формат суммы.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
