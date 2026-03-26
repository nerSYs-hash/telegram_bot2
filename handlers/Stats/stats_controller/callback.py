#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание: Основной коллбэк-диспетчер статистики.
Обрабатывает запросы stats_<period>_<type>: формирует текстовый отчёт
по чату или генерирует Excel-файл по пользователям.
Функции: handle_stats_callback.
"""

import os
import logging
from datetime import timedelta
from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import (
    format_number, get_moscow_time, get_today_date_msk,
    calculate_days_in_chat, round_decimal,
    export_users_stats_to_excel,
)

_d = Decimal


async def handle_stats_callback(query, data, user, context, db, admin_id, target_chat_id):
    """Handle statistics callbacks."""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return

    parts      = data.split('_')
    period     = parts[1]
    stats_type = parts[2] if len(parts) > 2 else 'chat'

    now = get_moscow_time()
    if period == 'yesterday':
        start_date  = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date    = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_name = "За вчера"
    elif period == 'day':
        start_date  = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date    = now
        period_name = "За сегодня"
    elif period == 'week':
        start_date  = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
        end_date    = now
        period_name = "За неделю"
    elif period == 'month':
        start_date  = now - timedelta(days=30)
        end_date    = now
        period_name = "За месяц"
    elif period == 'year':
        start_date  = now - timedelta(days=365)
        end_date    = now
        period_name = "За год"
    else:
        await query.answer("Неизвестный период", show_alert=True)
        return

    # ── По пользователям ─────────────────────────────────────────────────────
    if stats_type == 'users':
        await query.edit_message_text("📊 Генерирую детальный отчёт по всем пользователям чата...")
        logging.info(f"👥 Collecting data for ALL users, period: {period}")

        db.cursor.execute('''
            SELECT
                u.user_id, u.username, u.first_name, u.joined_at, u.last_active,
                COALESCE(SUM(us.total_messages), 0)     as total_messages,
                COALESCE(SUM(us.total_chars), 0)        as total_chars,
                COALESCE(SUM(us.total_words), 0)        as total_words,
                COALESCE(SUM(us.reactions_given), 0)    as reactions_given,
                COALESCE(SUM(us.reactions_received), 0) as reactions_received,
                COALESCE(SUM(us.replies_sent), 0)       as replies_sent,
                COALESCE(SUM(us.replies_received), 0)   as replies_received,
                COALESCE(SUM(us.mentions_received), 0)  as mentions_received,
                COALESCE(SUM(us.media_sent), 0)         as media_sent,
                COALESCE(SUM(us.other_threads_posts), 0) as other_threads_posts,
                COALESCE(SUM(us.pulses_mined), 0)       as pulses_mined,
                COUNT(DISTINCT CASE WHEN us.total_messages > 0 THEN us.date END) as active_days
            FROM users u
            LEFT JOIN user_stats us ON u.user_id = us.user_id AND us.date >= ? AND us.date <= ?
            WHERE u.is_admin = 0 AND u.is_owner = 0
            GROUP BY u.user_id ORDER BY pulses_mined DESC, total_messages DESC
        ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

        period_days = max(1, (end_date - start_date).days + 1)
        users_data = []
        for row in db.cursor.fetchall():
            u_dict = dict(row)
            u_dict['period_days'] = period_days
            u_dict['days_in_chat'] = calculate_days_in_chat(u_dict['joined_at']) if u_dict.get('joined_at') else 0
            users_data.append(u_dict)

        logging.info(f"✅ Collected data for {len(users_data)} users")

        if not users_data:
            await query.edit_message_text(
                "📭 Нет данных о пользователях за выбранный период",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_stats")]])
            )
            return

        timestamp = get_moscow_time().strftime('%Y%m%d_%H%M%S')
        filename  = f'users_stats_{period}_{timestamp}.xlsx'
        filepath  = os.path.join('logs', filename)
        os.makedirs('logs', exist_ok=True)

        try:
            member_count_excel = await context.bot.get_chat_member_count(target_chat_id)
        except Exception:
            db.cursor.execute('SELECT COUNT(*) as total FROM users')
            member_count_excel = db.cursor.fetchone()['total']

        result = export_users_stats_to_excel(
            users_data, filepath, period_name,
            member_count=member_count_excel,
            bot_count=int(os.getenv('BOT_COUNT', 1))
        )

        if result is None:
            await query.edit_message_text(
                "❌ Ошибка при создании файла. Проверьте логи.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_stats")]])
            )
            return

        if os.path.exists(filepath):
            with open(filepath, 'rb') as file:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file,
                    filename=filename,
                    caption=(
                        f"👤 Детальная статистика по {len(users_data)} пользователям чата ({period_name})\n\n"
                        f"📊 21 параметр для каждого пользователя:\n"
                        f"• Сообщения, символы, слова\n"
                        f"• Реакции, ответы, упоминания\n"
                        f"• Медиа, публикации в ветках\n"
                        f"• Дни в чате, активность, заработок"
                    ),
                    reply_to_message_id=query.message.message_id
                )
            try:
                os.remove(filepath)
            except Exception:
                pass
            await query.edit_message_text(
                f"✅ Отчёт по {len(users_data)} пользователям отправлен!\n\n"
                f"📊 Всего колонок: 20\n👥 Пользователей: {len(users_data)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]])
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка: файл не создан",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_stats")]])
            )
        return

    # ── Текстовая статистика (chat / combined) ────────────────────────────────
    type_names = {
        'chat':     '📊 Общая по чату',
        'users':    '👤 По пользователям',
        'combined': '📈 Чат + пользователи',
    }
    stats_message = f"{type_names.get(stats_type, '📊 СТАТИСТИКА ЧАТА')}\n{period_name}\n\n"


    # ── 1. Сообщений (Железобетонно из chat_stats) ──
    db.cursor.execute('''
        SELECT COALESCE(SUM(total_messages), 0) as count
        FROM chat_stats
        WHERE date >= ? AND date <= ?
    ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    total_messages = int(db.cursor.fetchone()['count'])

    stats_message += f"💬 Всего сообщений: {total_messages}\n"

    # ── 2. Активных пользователей (Железобетонно из user_stats) ──
    db.cursor.execute('''
        SELECT COUNT(DISTINCT user_id) as count
        FROM user_stats
        WHERE date >= ? AND date <= ? AND total_messages > 0
    ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    active_users = int(db.cursor.fetchone()['count'])

    stats_message += f"👥 Активных пользователей: {active_users}\n"

    if total_messages == 0:
        if period == 'day':
            db.cursor.execute('SELECT SUM(total_messages) as count FROM user_stats WHERE date = ?', (get_today_date_msk(),))
        elif period == 'yesterday':
            db.cursor.execute('SELECT SUM(total_messages) as count FROM user_stats WHERE date = ?', ((get_moscow_time() - timedelta(days=1)).date(),))
        else:
            db.cursor.execute('SELECT SUM(total_messages) as count FROM user_stats WHERE date >= ?', (start_date.date(),))
        r = db.cursor.fetchone()
        total_messages = int(_d(r['count'])) if r and r['count'] else 0

    stats_message += f"💬 Всего сообщений: {total_messages}\n"

    # Активных пользователей
    db.cursor.execute('SELECT COUNT(DISTINCT user_id) as count FROM messages WHERE timestamp >= ?', (start_date,))
    active_users = db.cursor.fetchone()['count']
    if active_users == 0:
        if period == 'day':
            db.cursor.execute('SELECT COUNT(DISTINCT user_id) as count FROM user_stats WHERE date = ? AND total_messages > 0', (get_today_date_msk(),))
        else:
            db.cursor.execute('SELECT COUNT(DISTINCT user_id) as count FROM user_stats WHERE date >= ? AND total_messages > 0', (start_date.date(),))
        r = db.cursor.fetchone()
        active_users = int(_d(r['count'])) if r and r['count'] else 0

    stats_message += f"👥 Активных пользователей: {active_users}\n"

    # Средний срок в чате
    db.cursor.execute('SELECT joined_at FROM users WHERE is_admin = 0 AND is_owner = 0 AND joined_at IS NOT NULL')
    all_users = db.cursor.fetchall()
    if all_users:
        total_days = sum(calculate_days_in_chat(u['joined_at']) for u in all_users)
        avg_days   = _d(total_days) / _d(len(all_users))                 # Decimal
        stats_message += f"⏱ Средний срок в чате: {int(avg_days)} дней\n"

    # Пульсов добыто
    db.cursor.execute('''
        SELECT SUM(amount) as total FROM transactions
        WHERE to_user_id IS NOT NULL AND transaction_type = 'message_reward' AND timestamp >= ?
    ''', (start_date,))
    r = db.cursor.fetchone()
    total_pulses = _d(r['total']) if r['total'] else Decimal('0')       # Decimal
    stats_message += f"💎 Добыто Пульсов: {format_number(total_pulses)}\n"

    # Вовлечённость
    try:
        member_count = await context.bot.get_chat_member_count(target_chat_id)
    except Exception:
        db.cursor.execute('SELECT COUNT(*) as total FROM users')
        member_count = db.cursor.fetchone()['total']

    er = round_decimal(_d(active_users) / _d(member_count) * Decimal('100'), 1) if member_count > 0 else Decimal('0')
    stats_message += f"📊 Коэффициент вовлеченности: {float(er):.1f}%\n"

    # Динамика пользователей
    stats_message += "\n📊 ДИНАМИКА ПОЛЬЗОВАТЕЛЕЙ:\n"
    db.cursor.execute('''
        SELECT COUNT(*) as joined FROM users
        WHERE DATE(joined_at) >= ? AND DATE(joined_at) <= ? AND is_admin = 0 AND is_owner = 0
    ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    joined_count = db.cursor.fetchone()['joined']

    db.cursor.execute('''
        SELECT COUNT(*) as left_users FROM transactions
        WHERE transaction_type = 'return_on_leave' AND DATE(timestamp) >= ? AND DATE(timestamp) <= ?
    ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    left_count  = db.cursor.fetchone()['left_users']
    net_change  = joined_count - left_count

    stats_message += f"🆕 Вступило за период: {joined_count}\n"
    stats_message += f"👋 Вышло за период: {left_count}\n"
    if net_change > 0:   stats_message += f"📈 Чистый прирост: +{net_change}\n"
    elif net_change < 0: stats_message += f"📉 Чистая убыль: {net_change}\n"
    else:                stats_message += "➡️ Без изменений: 0\n"

    if period in ['week', 'month']:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        db.cursor.execute('SELECT COUNT(*) as joined FROM users WHERE joined_at >= ? AND joined_at <= ? AND is_admin = 0 AND is_owner = 0', (today_start, now))
        j_today = db.cursor.fetchone()['joined']
        db.cursor.execute("SELECT COUNT(*) as l FROM transactions WHERE transaction_type = 'return_on_leave' AND timestamp >= ? AND timestamp <= ?", (today_start, now))
        l_today = db.cursor.fetchone()['l']
        stats_message += f"\n📅 За сегодня:\n   🆕 Вступило: {j_today}\n   👋 Вышло: {l_today}\n"

        if period == 'month':
            week_start = now - timedelta(days=7)
            db.cursor.execute('SELECT COUNT(*) as joined FROM users WHERE joined_at >= ? AND joined_at <= ? AND is_admin = 0 AND is_owner = 0', (week_start, now))
            j_week = db.cursor.fetchone()['joined']
            db.cursor.execute("SELECT COUNT(*) as l FROM transactions WHERE transaction_type = 'return_on_leave' AND timestamp >= ? AND timestamp <= ?", (week_start, now))
            l_week = db.cursor.fetchone()['l']
            stats_message += f"\n📅 За последние 7 дней:\n   🆕 Вступило: {j_week}\n   👋 Вышло: {l_week}\n"

    stats_message += "\n"

    # Детальные параметры
    stats_message += "\n📈 ДЕТАЛЬНЫЕ ПАРАМЕТРЫ:\n"
    date_from = start_date.strftime('%Y-%m-%d')
    date_to   = end_date.strftime('%Y-%m-%d')

    params_queries = [
        ('ОКС(Ч) (общее кол-во символов)',    'SELECT COALESCE(SUM(total_chars), 0) as v FROM chat_stats WHERE date >= ? AND date <= ?',       False),
        ('СДС(Ч) (средняя длина сообщения)',  'SELECT COALESCE(AVG(avg_message_length), 0) as v FROM chat_stats WHERE date >= ? AND date <= ?', True),
        ('Медиа(Ч) (медиа контент)',           'SELECT COALESCE(SUM(total_media), 0) as v FROM chat_stats WHERE date >= ? AND date <= ?',        False),
        ('КОР(Ч) (реакции оставленные)',       'SELECT COALESCE(SUM(reactions_given), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',    False),
        ('КПР(Ч) (реакции полученные)',        'SELECT COALESCE(SUM(reactions_received), 0) as v FROM user_stats WHERE date >= ? AND date <= ?', False),
        ('КОтв(Ч) (ответы полученные)',        'SELECT COALESCE(SUM(replies_received), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',   False),
        ('КОтп(Ч) (ответы отправленные)',      'SELECT COALESCE(SUM(replies_sent), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',       False),
        ('КУП(Ч) (упоминания @)',              'SELECT COALESCE(SUM(mentions_received), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',  False),
        ('ПДВ(Ч) (публ. в других ветках)',     'SELECT COALESCE(SUM(other_threads_posts), 0) as v FROM user_stats WHERE date >= ? AND date <= ?', False),
    ]

    for label, sql, is_avg in params_queries:
        db.cursor.execute(sql, (date_from, date_to))
        raw_val = db.cursor.fetchone()['v']
        val_d   = round_decimal(_d(raw_val), 1 if is_avg else 0)  # Decimal
        if is_avg:
            stats_message += f"• {label}: {float(val_d):.1f}\n"
        else:
            stats_message += f"• {label}: {format_number(val_d)}\n"

    stats_message += "\n"

    keyboard = [
        [InlineKeyboardButton("📊 Скачать отчёт",       callback_data=f"stats_export_{period}_{stats_type}")],
        [InlineKeyboardButton("🔙 Назад к периодам",    callback_data=f"stats_type_{stats_type}")],
        [InlineKeyboardButton("🔙 Назад к статистике",  callback_data="menu_stats")],
    ]
    await query.edit_message_text(stats_message, reply_markup=InlineKeyboardMarkup(keyboard))
