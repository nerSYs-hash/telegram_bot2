#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль Курса Валют — автоматический плавающий курс.
"""

from telegram import Update
from telegram.ext import ContextTypes
from utils.exchange_rate import rate_cache, scheduled_rate_update, MAX_RATE
from utils.helpers import get_today_date_msk, format_number


async def course_command(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         db, target_chat_id):
    """Handle /kurs — показать текущий плавающий курс"""
    user = update.effective_user
    user_data = db.get_user(user.id)

    # Если кеш не инициализирован — делаем полный расчёт
    if not rate_cache.initialized:
        try:
            total_members = await context.bot.get_chat_member_count(target_chat_id)
            total_members = max(1, total_members - 1)
            db.set_setting('total_chat_members', str(total_members))
        except Exception:
            total_members = int(db.get_setting('total_chat_members', '1'))

        today = get_today_date_msk()
        rate_cache.full_recalculate(db, total_members, today)

    # Показываем курс из кеша
    rate_data = rate_cache.get_rate_data()
    balance = user_data['balance'] if user_data else None

    # Расширенное — ТОЛЬКО владелец + ТОЛЬКО в ЛС бота
    import os
    main_admin_id = int(os.getenv('MAIN_ADMIN_ID', 0))
    is_owner = (user.id == main_admin_id)

    is_private = update.message.chat.type == 'private'

    if is_owner and is_private:
        message = format_admin_rate_message(rate_data, balance)
    else:
        username = user.username or user.first_name or None
        message = format_user_rate_message(rate_data, balance, username, is_private)

    await update.message.reply_text(message)


async def recalc_rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db, admin_id, target_chat_id):
    """/recalc — перезапуск курса (только для владельца)."""
    if update.effective_user.id != admin_id:
        return

    import logging

    try:
        db.set_setting('exchange_rate_manual', '0')
        rate_cache.unset_manual()

        try:
            total_members = await context.bot.get_chat_member_count(target_chat_id)
            total_members = max(1, total_members - 1)
            db.set_setting('total_chat_members', str(total_members))
        except Exception:
            total_members = int(db.get_setting('total_chat_members', '1'))

        old_rate = db.get_exchange_rate()
        today = get_today_date_msk()
        new_rate = scheduled_rate_update(db, total_members, today)

        rate_data = rate_cache.get_rate_data()

        msg = (
            f"✅ Курс перезапущен!\n\n"
            f"Было: {format_number(old_rate)} ₽\n"
            f"Стало: {format_number(new_rate)} ₽\n\n"
            f"👥 Участников: {rate_data.get('total_members', '?')}\n"
            f"📊 Ср. активных (30д): {rate_data.get('avg_active', '?')}\n"
            f"📈 AI (30д): {format_number(rate_data.get('ai_30d', 0))}\n\n"
            f"Курс обновляется автоматически:\n"
            f"⚡ В реальном времени при каждом действии\n"
            f"🔄 Полный пересчёт каждые 30 мин"
        )

        logging.info(f"💱 Rate restarted: {old_rate} → {new_rate}")
        await update.message.reply_text(msg)

    except Exception as e:
        logging.error(f"Error in recalc_rate: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


def format_admin_rate_message(rate_data, balance=None):
    """Полная статистика для владельца в ЛС"""
    rate = rate_data.get('rate', 0)

    msg = "💱 КУРС ПУЛЬСА\n\n"
    msg += f"📊 1 💎 Пульс = {rate:.6f} ₽\n\n"
    msg += f"📋 Показатели:\n"
    msg += f"   💎 Индекс активности (30д): {rate_data.get('ai_30d', 0):.2f}\n"
    msg += f"   👥 Людей в чате: {rate_data.get('total_members', 0)}\n"
    msg += f"   👥 Активных (ср. 30д): {rate_data.get('avg_active', 0):.1f}\n"
    msg += f"   📅 Дней с данными: {rate_data.get('days_with_data', 0)}/30\n"

    if rate >= MAX_RATE:
        msg += f"   ⚠️ Достигнут потолок: {MAX_RATE} ₽\n"

    if balance is not None and rate > 0:
        rub_value = balance * rate
        msg += f"\n💰 Ваш баланс:\n"
        msg += f"   💎 {format_number(balance)} Пульсов\n"
        msg += f"   💵 ≈ {rub_value:.4f} ₽"

    return msg


def format_user_rate_message(rate_data, balance=None, username=None, is_private=False):
    """Краткая версия для всех (чат + ЛС пользователей)"""
    rate = rate_data.get('rate', 0)

    msg = "💱 КУРС ПУЛЬСА\n\n"
    msg += f"📊 1 💎 Пульс = {rate:.6f} ₽\n"

    if balance is not None and rate > 0:
        if is_private or not username:
            msg += f"\n💰 Ваш баланс: {format_number(balance)} 💎"
        else:
            msg += f"\n💰 Баланс @{username}: {format_number(balance)} 💎"

    return msg
