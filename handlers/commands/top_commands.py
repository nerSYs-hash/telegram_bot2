#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль топов — триггерные команды (богач / активист).

Вынесено из message_handler.py.
Все функции — модульного уровня (без класса).
db передаётся явно.

Использование:
    from handlers.messages.top_commands import show_top_rich, show_top_activists
"""

import os
import logging
from utils.helpers import format_number, get_today_date_msk, get_moscow_time


async def show_top_rich(message, context, db):
    """
    Show top 5 richest users with balance + mined today.
    
    Исключены: is_admin=1, is_owner=1.
    НЕ показывает «Добыто всего» — только Баланс и Добыто сегодня.
    """
    try:
        today = get_today_date_msk()

        db.cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, u.balance,
                   COALESCE(us_today.pulses_mined, 0) as pulses_today
            FROM users u
            LEFT JOIN user_stats us_today 
                ON u.user_id = us_today.user_id AND us_today.date = ?
            WHERE u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
            ORDER BY u.balance DESC
            LIMIT 5
        ''', (today,))

        top_users = db.cursor.fetchall()

        if not top_users:
            await context.bot.send_message(
                chat_id=message.chat.id,
                text="Пока нет данных о богачах."
            )
            return

        response = "🏆 ТОП-5 БОГАЧЕЙ ЧАТА\n"
        response += f"({get_moscow_time().strftime('%d.%m.%Y %H:%M')} МСК)\n\n"

        emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']

        for idx, user in enumerate(top_users):
            username = user['username'] or user['first_name'] or 'Unknown'
            balance = format_number(user['balance'])
            pulses_today = format_number(user['pulses_today'])

            response += f"{emojis[idx]} @{username}\n"
            response += f"   💰 Баланс: {balance} 💎\n"
            response += f"   ⛏ Добыто сегодня: {pulses_today} 💎\n\n"

        await context.bot.send_message(
            chat_id=message.chat.id,
            text=response
        )

    except Exception as e:
        logging.error(f"Error showing top rich: {e}")


# ══════════════════════════════════════════════════════════════════
# ФОРМУЛА ИНДЕКСА АКТИВНОСТИ — ЕДИНАЯ (из exchange_rate.py)
# ══════════════════════════════════════════════════════════════════

from utils.exchange_rate import ACTIVITY_INDEX_SQL, CHARS_NORM


async def show_top_activists(message, context, db):
    """
    Show top 5 most active users by composite Activity Index (АктП).
    
    Исключены: is_admin=1, is_owner=1.
    """
    try:
        today = get_today_date_msk()

        # ── Единая формула АктП из exchange_rate.py (без деления на участников) ──
        db.cursor.execute(f'''
            SELECT 
                u.username, 
                u.first_name,
                ({ACTIVITY_INDEX_SQL}) as activity_index
            FROM user_stats us
            JOIN users u ON us.user_id = u.user_id
            WHERE us.date = ?
              AND u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
            GROUP BY us.user_id
            HAVING SUM(us.total_messages) > 0 OR SUM(us.reactions_given) > 0
                   OR SUM(us.reactions_received) > 0 OR SUM(us.replies_sent) > 0
            ORDER BY activity_index DESC
            LIMIT 5
        ''', (today,))

        top_users = db.cursor.fetchall()

        if not top_users:
            await context.bot.send_message(
                chat_id=message.chat.id,
                text="Сегодня ещё никто не проявлял активность."
            )
            return

        response = "🏆 ТОП-5 АКТИВИСТОВ СЕГОДНЯ\n"
        response += f"({get_moscow_time().strftime('%d.%m.%Y %H:%M')} МСК)\n\n"

        emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
        from config.emojis import ICON_FIRE
        max_score = float(top_users[0]['activity_index']) if top_users else 1

        for idx, user in enumerate(top_users):
            username = user['username'] or user['first_name'] or 'Unknown'
            score = float(user['activity_index'])
            pct = round(score / max_score * 100) if max_score > 0 else 0
            filled = round(pct / 10)
            bar = '▰' * filled + '░' * (10 - filled)
            fire = ICON_FIRE if idx == 0 else ''
            response += f"{emojis[idx]} @{username} {bar} {pct}%{fire}\n"

        await context.bot.send_message(
            chat_id=message.chat.id,
            text=response,
            parse_mode='HTML'
        )

    except Exception as e:
        logging.error(f"Error showing top activists: {e}")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль Статистики и Топов — вынесен из CommandHandler.
Все функции принимают db, admin_id, target_chat_id как аргументы.
"""

from telegram import Update
from telegram.ext import ContextTypes
from utils.helpers import format_number, get_moscow_time, get_today_date_msk


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Handle /top command — ежедневный топ-5 по добытым пульсам"""
    today = get_today_date_msk()

    # Top 5 users by pulses mined TODAY with total pulses mined
    db.cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, u.balance, 
               COALESCE(us_today.pulses_mined, 0) as pulses_today,
               COALESCE(SUM(us_all.pulses_mined), 0) as pulses_total
        FROM users u
        LEFT JOIN user_stats us_today ON u.user_id = us_today.user_id AND us_today.date = ?
        LEFT JOIN user_stats us_all ON u.user_id = us_all.user_id
        WHERE u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
        GROUP BY u.user_id
        ORDER BY pulses_today DESC, pulses_total DESC, u.balance DESC
        LIMIT 5
    ''', (today,))

    top_users = db.cursor.fetchall()

    message = "🏆 ТОП-5 БОГАЧЕЙ ЗА СЕГОДНЯ\n"
    message += f"(по добытым пульсам: {get_moscow_time().strftime('%d.%m.%Y')})\n\n"

    if top_users and any(user['pulses_today'] > 0 for user in top_users):
        emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']

        for idx, user in enumerate(top_users):
            if user['pulses_today'] > 0:  # Показываем только тех, кто майнил сегодня
                username = user['username'] or user['first_name'] or 'Unknown'
                pulses_today = format_number(user['pulses_today'])
                pulses_total = format_number(user['pulses_total'])
                balance = format_number(user['balance'])

                message += f"{emojis[idx]} @{username}\n"
                message += f"   💎 Добыто сегодня: {pulses_today}\n"
                message += f"   💎 Добыто всего: {pulses_total}\n"
                message += f"   💰 Общий баланс: {balance}\n\n"
    else:
        message += "Сегодня еще никто не добывал пульсы.\n"

    await update.message.reply_text(message)


async def top5_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db, admin_id, target_chat_id):
    """Handle /top5 command (owner only) — админская публикация топа в чат"""
    if update.effective_user.id != admin_id:
        return

    try:
        # Get top 5 users
        top_users = db.get_top_users_by_balance(limit=5, exclude_admins=True)

        if not top_users:
            await update.message.reply_text("Нет данных для топ-5")
            return

        message = "🏆 ТОП-5 БОГАЧЕЙ ЧАТА\n"
        message += f"(период: {get_moscow_time().strftime('%d.%m.%Y %H:%M')} МСК)\n\n"
        message += "    Всего добыто\n"

        emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']

        for idx, user in enumerate(top_users):
            username = user['username'] or user['first_name'] or 'Unknown'
            balance = format_number(user['balance'])
            message += f"{emojis[idx]} @{username} — {balance} 💎\n"

        # Calculate total mined
        db.cursor.execute('''
            SELECT SUM(amount) as total FROM transactions
            WHERE transaction_type = 'message_reward'
        ''')
        result = db.cursor.fetchone()
        total_mined = result['total'] if result and result['total'] else 0

        message += f"\n💰 Всего добыто чатом за всё время: {format_number(total_mined)} 💎"

        # Send to target chat
        await context.bot.send_message(
            chat_id=target_chat_id,
            text=message
        )

        await update.message.reply_text("✅ Топ-5 опубликован в чат!")

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
