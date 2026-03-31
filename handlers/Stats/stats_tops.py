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

def _mark_user_left(db, user_id):
    """Пометить ушедшего: is_left=1 + заморозить баланс + вернуть пульсы в банк."""
    from datetime import datetime, timedelta
    db.cursor.execute('UPDATE users SET is_left = 1 WHERE user_id = ?', (user_id,))
    db.conn.commit()
    # Заморозить баланс если есть
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
    from utils.exchange_rate import ACTIVITY_INDEX_SQL
    now = get_moscow_time()
    date_30 = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    target_chat_id = int(os.getenv('TARGET_CHAT_ID'))

    admin_ids = set()
    if context:
        try:
            admins_list = await context.bot.get_chat_administrators(target_chat_id)
            admin_ids = {a.user.id for a in admins_list}
        except Exception:
            pass

    db.cursor.execute(f'''
        SELECT u.user_id, u.username, u.first_name,
            ({ACTIVITY_INDEX_SQL}) as activity_index
        FROM user_stats us JOIN users u ON us.user_id = u.user_id
        WHERE us.date >= ? AND u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
        GROUP BY us.user_id HAVING SUM(us.total_messages)>0 OR SUM(us.reactions_given)>0 OR SUM(us.reactions_received)>0 OR SUM(us.replies_sent)>0
        ORDER BY activity_index DESC LIMIT 20
    ''', (date_30,))

    all_users = db.cursor.fetchall()
    top_users = await _filter_active_users(context, target_chat_id, all_users, admin_ids, db, limit=5)

    message = "🏆 ТОП-5 АКТИВИСТОВ ЧАТА\n\n"
    if top_users:
        from config.emojis import ICON_FIRE
        emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
        max_score = float(top_users[0]['activity_index']) if top_users else 1
        for idx, u_data in enumerate(top_users):
            username = u_data['username'] or u_data['first_name'] or 'Unknown'
            score = float(u_data['activity_index'])
            pct = round(score / max_score * 100) if max_score > 0 else 0
            filled = round(pct / 10)
            bar = '▰' * filled + '░' * (10 - filled)
            fire = ICON_FIRE if idx == 0 else ''
            message += f"{emojis[idx]} @{username} {bar} {pct}%{fire}\n"
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
