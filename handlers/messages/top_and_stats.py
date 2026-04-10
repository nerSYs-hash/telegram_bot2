#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль топов и статистики — триггерные и командные обработчики.
"""

import os
import logging
from decimal import Decimal

from telegram import Update
from telegram.ext import ContextTypes
from utils.helpers import format_number, get_today_date_msk, get_moscow_time

# ══════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════════

async def _get_excluded_ids(context, chat_id):
    """Get set of user IDs to exclude from tops: Telegram admins + bot deputies."""
    excluded = set()
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        excluded = {admin.user.id for admin in admins}
    except Exception as e:
        logging.warning(f"Could not fetch admins from API: {e}")
    try:
        from database.db_friend import get_all_deputies
        deputies = await get_all_deputies()
        for d in deputies:
            deputy_id = d.get('tg_id') or d.get('user_id')
            if deputy_id:
                excluded.add(deputy_id)
    except Exception as e:
        logging.warning(f"Could not fetch deputies for top filter: {e}")
    return excluded

def _mark_user_left(db, user_id):
    """Пометить ушедшего: is_left=1 + заморозить баланс + вернуть пульсы в банк."""
    from datetime import datetime, timedelta
    db.cursor.execute('UPDATE users SET is_left = 1 WHERE user_id = ?', (user_id,))
    db.conn.commit()
    user_data = db.get_user(user_id)
    if not user_data:
        return
    try:
        balance = float(user_data['balance'] or 0)
    except (KeyError, IndexError):
        balance = 0
    if balance > 0:
        now = datetime.now()
        freeze_until = now + timedelta(days=30)
        db.cursor.execute(
            'UPDATE users SET frozen_balance = ?, freeze_until = ? WHERE user_id = ?',
            (balance, freeze_until, user_id)
        )
        db.update_user_balance(user_id, 0, 'set')
        db.update_bank_balance(balance, 'add')
        db.conn.commit()
        logging.info(f"💰 TOP filter: user {user_id} balance {balance} → frozen 30d, returned to bank")

async def _filter_active_users(context, chat_id, users_list, admin_ids, db, limit=5):
    """Живая проверка: фильтрует ушедших пользователей и автоматически чинит БД."""
    active_users = []
    if not context:
        return [u for u in users_list if u['user_id'] not in admin_ids][:limit]

    for u in users_list:
        if u['user_id'] in admin_ids:
            continue

        try:
            member = await context.bot.get_chat_member(chat_id, u['user_id'])
            if member.status in ('left', 'kicked'):
                logging.info(f"🚫 TOP filter: user {u['user_id']} status={member.status} → is_left=1")
                _mark_user_left(db, u['user_id'])
                continue
        except Exception as e:
            logging.warning(f"⚠️ TOP filter: user {u['user_id']} API error ({e}) → is_left=1")
            _mark_user_left(db, u['user_id'])
            continue

        active_users.append(u)
        if len(active_users) == limit:
            break

    return active_users


# ══════════════════════════════════════════════════════════════════
# ТРИГГЕРНЫЕ КОМАНДЫ (богач / активист)
# ══════════════════════════════════════════════════════════════════

async def show_top_rich(message, context, db):
    try:
        today = get_today_date_msk()
        admin_ids = await _get_excluded_ids(context,message.chat.id)

        # Берем 20 человек с запасом
        db.cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, u.balance,
                   COALESCE(us_today.pulses_mined, 0) as pulses_today
            FROM users u
            LEFT JOIN user_stats us_today 
                ON u.user_id = us_today.user_id AND us_today.date = ?
            WHERE u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
            ORDER BY u.balance DESC
            LIMIT 20
        ''', (today,))

        all_users = db.cursor.fetchall()
        # Фильтруем через живую проверку
        top_users = await _filter_active_users(context, message.chat.id, all_users, admin_ids, db, limit=5)

        if not top_users:
            sent = await context.bot.send_message(chat_id=message.chat.id, text="Пока нет данных о богачах.")
            return sent

        response = "🏆 ТОП-5 БОГАЧЕЙ ЧАТА\n\n"
        emojis =['🥇', '🥈', '🥉', '4️⃣', '5️⃣']

        for idx, user in enumerate(top_users):
            username = user['username'] or user['first_name'] or 'Unknown'
            balance = format_number(user['balance'])
            pulses_today = format_number(user['pulses_today'])
            response += f"{emojis[idx]} @{username}\n   💰 Баланс: {balance} 💎\n   ⛏ Добыто сегодня: {pulses_today} 💎\n\n"

        sent = await context.bot.send_message(chat_id=message.chat.id, text=response)
        return sent
    except Exception as e:
        logging.error(f"Error showing top rich: {e}")
        return None


async def show_top_activists(message, context, db):
    try:
        # Берём кешированные % из БД (обновляются каждый час)
        excluded_ids = await _get_excluded_ids(context, message.chat.id)
        top_users = [u for u in db.get_top5_percent()
                     if u['user_id'] not in excluded_ids][:5]

        if not top_users:
            sent = await context.bot.send_message(chat_id=message.chat.id, text="Пока нет данных об активности.")
            return sent

        response = "🏆 ТОП-5 АКТИВИСТОВ ЧАТА\n\n"
        from config.emojis import ICON_TOP_ACT
        emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
        for idx, user in enumerate(top_users):
            username = user['username'] or user['first_name'] or 'Unknown'
            pct = float(user['percent'])
            filled = min(round(pct / 10), 10)
            bar = '▰' * filled + '░' * (10 - filled)
            fire = ICON_TOP_ACT if idx == 0 else ''
            response += f"{emojis[idx]} @{username} {bar} {pct:.1f}%{fire}\n"

        sent = await context.bot.send_message(chat_id=message.chat.id, text=response, parse_mode='HTML')
        return sent
    except Exception as e:
        logging.error(f"Error showing top activists: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# SLASH-КОМАНДЫ (/top, /top5)
# ══════════════════════════════════════════════════════════════════

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    today = get_today_date_msk()
    admin_ids = await _get_excluded_ids(context,update.message.chat.id)

    db.cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, u.balance, 
               COALESCE(us_today.pulses_mined, 0) as pulses_today,
               COALESCE(SUM(us_all.pulses_mined), 0) as pulses_total
        FROM users u
        LEFT JOIN user_stats us_today ON u.user_id = us_today.user_id AND us_today.date = ?
        LEFT JOIN user_stats us_all ON u.user_id = us_all.user_id
        WHERE (u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0)
        GROUP BY u.user_id
        ORDER BY pulses_today DESC, pulses_total DESC, u.balance DESC
        LIMIT 20
    ''', (today,))

    all_users = db.cursor.fetchall()
    top_users = await _filter_active_users(context, update.message.chat.id, all_users, admin_ids, db, limit=5)

    message = "🏆 ТОП-5 БОГАЧЕЙ ЗА СЕГОДНЯ\n\n"

    if top_users and any(user['pulses_today'] > 0 for user in top_users):
        emojis =['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
        for idx, user in enumerate(top_users):
            if user['pulses_today'] > 0:
                username = user['username'] or user['first_name'] or 'Unknown'
                pulses_today = format_number(user['pulses_today'])
                pulses_total = format_number(user['pulses_total'])
                balance = format_number(user['balance'])
                message += f"{emojis[idx]} @{username}\n   💎 Добыто сегодня: {pulses_today}\n   💎 Добыто всего: {pulses_total}\n   💰 Общий баланс: {balance}\n\n"
    else:
        message += "Сегодня еще никто не добывал пульсы.\n"

    await update.message.reply_text(message)


async def top5_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db, admin_id, target_chat_id):
    if update.effective_user.id != admin_id:
        return

    try:
        admin_ids = await _get_excluded_ids(context,target_chat_id)
        all_users = db.get_top_users_by_balance(limit=20, exclude_admins=True)
        top_users = await _filter_active_users(context, target_chat_id, all_users, admin_ids, db, limit=5)

        if not top_users:
            await update.message.reply_text("Нет данных для топ-5")
            return

        message = "🏆 ТОП-5 БОГАЧЕЙ ЧАТА\n\n"
        emojis =['🥇', '🥈', '🥉', '4️⃣', '5️⃣']

        for idx, user in enumerate(top_users):
            username = user['username'] or user['first_name'] or 'Unknown'
            balance = format_number(user['balance'])
            message += f"{emojis[idx]} @{username} — {balance} 💎\n"

        db.cursor.execute("SELECT SUM(amount) as total FROM transactions WHERE transaction_type = 'message_reward'")
        result = db.cursor.fetchone()
        total_mined = result['total'] if result and result['total'] else 0

        message += f"\n💰 Всего добыто чатом за всё время: {format_number(total_mined)} 💎"
        await context.bot.send_message(chat_id=target_chat_id, text=message)
        await update.message.reply_text("✅ Топ-5 опубликован в чат!")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")