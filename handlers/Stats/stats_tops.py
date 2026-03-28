#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import logging
from decimal import Decimal
from datetime import timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import format_number, get_moscow_time, get_today_date_msk, round_decimal, to_decimal
from handlers.donate_handlers import safe_name

def _d(val): return to_decimal(val)

async def _filter_active_users(context, chat_id, users_list, admin_ids, db, limit=5):
    """Живая проверка через Telegram API: в топе только те, кто реально в чате."""
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
                db.cursor.execute('UPDATE users SET is_left = 1 WHERE user_id = ?', (u['user_id'],))
                db.conn.commit()
                continue
        except Exception as e:
            logging.warning(f"⚠️ TOP filter: user {u['user_id']} API error ({e}) → is_left=1")
            db.cursor.execute('UPDATE users SET is_left = 1 WHERE user_id = ?', (u['user_id'],))
            db.conn.commit()
            continue
        active_users.append(u)
        if len(active_users) == limit:
            break
    return active_users

async def show_top(query, db, target_chat_id, context=None):
    today = get_today_date_msk()
    admin_ids = set()
    if context:
        try:
            admins = await context.bot.get_chat_administrators(target_chat_id)
            admin_ids = {a.user.id for a in admins}
        except: pass
    db.cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, u.balance,
               COALESCE(us_today.pulses_mined, 0) as pulses_today,
               COALESCE(SUM(us_all.pulses_mined), 0) as pulses_total
        FROM users u
        LEFT JOIN user_stats us_today ON u.user_id = us_today.user_id AND us_today.date = ?
        LEFT JOIN user_stats us_all   ON u.user_id = us_all.user_id
        WHERE u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
        GROUP BY u.user_id ORDER BY pulses_today DESC, pulses_total DESC, u.balance DESC LIMIT 20
    ''', (today,))
    all_users = db.cursor.fetchall()
    top_users = await _filter_active_users(context, target_chat_id, all_users, admin_ids, db, limit=5)
    message = f"🏆 ТОП-5 БОГАЧЕЙ ЗА СЕГОДНЯ\n({get_moscow_time().strftime('%d.%m.%Y')})\n\n"
    if top_users and any(_d(u['pulses_today']) > 0 for u in top_users):
        emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
        for idx, user in enumerate(top_users):
            username = safe_name(user)
            message += f"{emojis[idx]} @{username}\n   💎 Добыто: {format_number(user['pulses_today'])}\n   💰 Баланс: {format_number(user['balance'])}\n\n"
    else:
        message += "Сегодня еще никто не добывал пульсы.\n"
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]))

async def show_top5_menu(query, user):
    keyboard = [
        [InlineKeyboardButton("🏆 Активисты", callback_data="top5_activists")],
        [InlineKeyboardButton("💰 Богачи", callback_data="top5_rich")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    await query.edit_message_text("🏆 ТОП-5\nВыберите категорию:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_top5_activists(query, user, db, context=None):
    CHARS_NORM = Decimal('100')
    now = get_moscow_time()
    date_30 = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    bot_count = int(os.getenv('BOT_COUNT', 1))
    target_chat_id = int(os.getenv('TARGET_CHAT_ID'))

    try:
        member_count = await context.bot.get_chat_member_count(target_chat_id)
    except Exception:
        db.cursor.execute('SELECT COUNT(*) as cnt FROM users')
        member_count = db.cursor.fetchone()['cnt']

    divisor = Decimal(max(member_count - bot_count - 1, 1))
    admin_ids = set()
    if context:
        try:
            admins_list = await context.bot.get_chat_administrators(target_chat_id)
            admin_ids = {a.user.id for a in admins_list}
        except Exception:
            pass

    db.cursor.execute('''
        SELECT u.user_id, u.username, u.first_name,
            (0.05*(SUM(us.total_chars)*1.0/?)+0.05*(CASE WHEN SUM(us.total_messages)>0 THEN (SUM(us.total_chars)*1.0/SUM(us.total_messages))/? ELSE 0 END)+0.05*SUM(us.total_words)+0.08*SUM(us.reactions_given)+0.10*SUM(us.reactions_received)+0.18*SUM(us.replies_received)+0.15*SUM(us.replies_sent)+0.15*SUM(us.mentions_received)+0.07*SUM(us.media_sent)+0.12*SUM(us.other_threads_posts))/? as activity_index
        FROM user_stats us JOIN users u ON us.user_id = u.user_id
        WHERE us.date >= ? AND u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
        GROUP BY us.user_id HAVING SUM(us.total_messages)>0 OR SUM(us.reactions_given)>0 OR SUM(us.reactions_received)>0 OR SUM(us.replies_sent)>0
        ORDER BY activity_index DESC LIMIT 20
    ''', (float(CHARS_NORM), float(CHARS_NORM), float(divisor), date_30))

    all_users = db.cursor.fetchall()
    top_users = await _filter_active_users(context, target_chat_id, all_users, admin_ids, db, limit=5)

    message = "⚡ ТОП-5 АКТИВИСТОВ ЧАТА\n\n"
    if top_users:
        emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
        for idx, u_data in enumerate(top_users):
            username = u_data['username'] or u_data['first_name'] or 'Unknown'
            score = float(round_decimal(_d(u_data['activity_index']), 2))
            message += f"{emojis[idx]} @{username} — {score}\n"
    else:
        message += "За последние 30 дней нет данных об активности."

    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к ТОП-5", callback_data="menu_top5")],[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]]))

async def show_top5_rich(query, user, db, context=None):
    today = get_today_date_msk()
    target_chat_id = int(os.getenv('TARGET_CHAT_ID'))
    
    admin_ids = set()
    if context:
        try:
            admins_list = await context.bot.get_chat_administrators(target_chat_id)
            admin_ids = {a.user.id for a in admins_list}
        except Exception:
            pass
    
    db.cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, u.balance, COALESCE(us_today.pulses_mined, 0) as pulses_today
        FROM users u LEFT JOIN user_stats us_today ON u.user_id = us_today.user_id AND us_today.date = ?
        WHERE u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
        ORDER BY u.balance DESC LIMIT 20
    ''', (today,))
    
    all_users = db.cursor.fetchall()
    top_users = await _filter_active_users(context, target_chat_id, all_users, admin_ids, db, limit=5)

    message = f"💰 ТОП-5 БОГАЧЕЙ ЧАТА\n({get_moscow_time().strftime('%d.%m.%Y %H:%M')} МСК)\n\n"
    if top_users:
        emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
        for idx, u_data in enumerate(top_users):
            username = u_data['username'] or u_data['first_name'] or 'Unknown'
            message += f"{emojis[idx]} @{username}\n   💰 Баланс: {format_number(u_data['balance'])} 💎\n   ⛏ Добыто сегодня: {format_number(u_data['pulses_today'])} 💎\n\n"
    else:
        message += "Пока нет данных."

    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад к ТОП-5", callback_data="menu_top5")],[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]]))
