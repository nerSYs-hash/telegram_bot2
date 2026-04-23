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
        yesterday = (now - timedelta(days=1))
        start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date   = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)
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

    date_from = start_date.strftime('%Y-%m-%d')
    date_to   = end_date.strftime('%Y-%m-%d')

    # ── Хелпер: дельта (%) относительно предыдущего периода ──
    def _delta_str(cur, prev):
        """Возвращает строку дельты: 🔺 +12.3% или 🔻 -5.1%"""
        if prev is None or prev == 0:
            return ""
        pct = (cur - prev) / prev * 100
        if pct > 0:
            return f" 🔺 +{pct:.1f}%"
        elif pct < 0:
            return f" 🔻 {pct:.1f}%"
        return ""

    # ── Предыдущий период для сравнения ──
    if period == 'yesterday':
        prev_start = (start_date - timedelta(days=1)).strftime('%Y-%m-%d')
        prev_end   = (end_date - timedelta(days=1)).strftime('%Y-%m-%d')
    elif period == 'day':
        prev_start = (start_date - timedelta(days=1)).strftime('%Y-%m-%d')
        prev_end   = date_from
    elif period == 'week':
        prev_start = (start_date - timedelta(days=7)).strftime('%Y-%m-%d')
        prev_end   = (start_date - timedelta(days=1)).strftime('%Y-%m-%d')
    elif period == 'month':
        prev_start = (start_date - timedelta(days=30)).strftime('%Y-%m-%d')
        prev_end   = (start_date - timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        prev_start = prev_end = None

    def _prev_val(sql, args):
        """Получить значение за предыдущий период."""
        if prev_start is None:
            return None
        db.cursor.execute(sql, args)
        r = db.cursor.fetchone()
        return int(r['count']) if r and r['count'] else 0

    # ── 1. Сообщений ──
    db.cursor.execute('''
        SELECT COALESCE(SUM(total_messages), 0) as count
        FROM user_stats
        WHERE date >= ? AND date <= ?
    ''', (date_from, date_to))
    total_messages = int(db.cursor.fetchone()['count'])

    prev_msgs = _prev_val('''
        SELECT COALESCE(SUM(total_messages), 0) as count
        FROM user_stats
        WHERE date >= ? AND date <= ?
    ''', (prev_start, prev_end))

    formatted_total = "{:,}".format(int(total_messages)).replace(',', ' ')
    stats_message += f"💬 Сообщений: {formatted_total}{_delta_str(total_messages, prev_msgs)}\n"

    # ── 2. Активных пользователей ──
    db.cursor.execute('''
        SELECT COUNT(DISTINCT user_id) as count
        FROM user_stats
        WHERE date >= ? AND date <= ? AND total_messages > 0
    ''', (date_from, date_to))
    active_users = int(db.cursor.fetchone()['count'])

    prev_active = _prev_val('''
        SELECT COUNT(DISTINCT user_id) as count
        FROM user_stats
        WHERE date >= ? AND date <= ? AND total_messages > 0
    ''', (prev_start, prev_end))

    stats_message += f"👥 Активных: {active_users}{_delta_str(active_users, prev_active)}\n"

    # Средний срок в чате
    db.cursor.execute('SELECT joined_at FROM users WHERE is_admin = 0 AND is_owner = 0 AND is_left = 0 AND joined_at IS NOT NULL')
    all_users = db.cursor.fetchall()
    if all_users:
        total_days = sum(calculate_days_in_chat(u['joined_at']) for u in all_users)
        avg_days   = _d(total_days) / _d(len(all_users))
        stats_message += f"⏱ Средний срок в чате: {int(avg_days)} дней\n"

    # Пульсов заработано — все виды наград
    # 1. Считаем чистую добычу (Майнинг) из user_stats
    db.cursor.execute('''
        SELECT COALESCE(SUM(pulses_mined), 0) as total 
        FROM user_stats 
        WHERE date >= ? AND date <= ?
    ''', (date_from, date_to))
    net_mined = Decimal(str(db.cursor.fetchone()['total']))
    
    
    # 1. Сначала берем "грязный" майнинг из статистики
    db.cursor.execute('''
        SELECT COALESCE(SUM(pulses_mined), 0) as total 
        FROM user_stats 
        WHERE date >= ? AND date <= ?
    ''', (date_from, date_to))
    raw_mined = Decimal(str(db.cursor.fetchone()['total']))

    # 2. Берем ШТРАФЫ и ОБЩИЙ заработок из транзакций
    db.cursor.execute('''
        SELECT
            COALESCE(SUM(CASE WHEN transaction_type = 'penalty_deduct' THEN amount ELSE 0 END), 0) AS penalized,
            COALESCE(SUM(CASE WHEN transaction_type IN (
                'message_reward','combo_reward','sprint_reward',
                'referral_reward','lottery_win','bingo_win',
                'monthly_gift','reaction_given_reward','reaction_received_reward',
                'lootbox_win','bbs_popularity','admin_give','compensation_reward'
            ) THEN amount ELSE 0 END), 0) AS total_earned
        FROM transactions
        WHERE to_user_id IS NOT NULL
          AND timestamp >= ? AND timestamp <= ?
    ''', (start_date, end_date))
    
    r = db.cursor.fetchone()
    _penalty = _d(r['penalized'])
    _earned  = _d(r['total_earned'])

    # 3. Применяем твою математику (Чистая прибыль = Грязная - Штрафы)
    # Здесь мы используем raw_mined, который взяли из user_stats
    net_mined  = max(raw_mined - _penalty, Decimal('0'))
    net_earned = max(_earned - _penalty, Decimal('0'))

    # Формируем сообщение
    stats_message += (
        f"💎 Добыто Пульсов: {format_number(net_mined)}"
        f" | Всего заработано: {format_number(net_earned)}\n"
    )

    # Вовлечённость
    try:
        member_count = await context.bot.get_chat_member_count(target_chat_id)
    except Exception:
        db.cursor.execute('SELECT COUNT(*) as total FROM users WHERE is_left = 0')
        member_count = db.cursor.fetchone()['total']

    er = round_decimal(_d(active_users) / _d(member_count) * Decimal('100'), 1) if member_count > 0 else Decimal('0')
    stats_message += f"📊 Вовлечённость: {float(er):.1f}%\n"

    # ── ДИНАМИКА ПОЛЬЗОВАТЕЛЕЙ ──
    stats_message += "\n📊 ДИНАМИКА ПОЛЬЗОВАТЕЛЕЙ:\n"
    db.cursor.execute('''
        SELECT COUNT(*) as joined FROM users
        WHERE DATE(joined_at) >= ? AND DATE(joined_at) <= ? AND is_admin = 0 AND is_owner = 0
    ''', (date_from, date_to))
    joined_count = db.cursor.fetchone()['joined']

    db.cursor.execute('''
        SELECT COUNT(*) as left_users FROM transactions
        WHERE transaction_type = 'return_on_leave' AND DATE(timestamp) >= ? AND DATE(timestamp) <= ?
    ''', (date_from, date_to))
    left_count  = db.cursor.fetchone()['left_users']
    net_change  = joined_count - left_count

    stats_message += f"🆕 Вступило: {joined_count}\n"
    stats_message += f"👋 Вышло: {left_count}\n"
    if net_change > 0:   stats_message += f"🔺 Прирост: +{net_change}\n"
    elif net_change < 0: stats_message += f"🔻 Убыль: {net_change}\n"
    else:                stats_message += "➡️ Без изменений\n"

    if period in ['week', 'month']:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        db.cursor.execute('SELECT COUNT(*) as joined FROM users WHERE joined_at >= ? AND joined_at <= ? AND is_admin = 0 AND is_owner = 0', (today_start, now))
        j_today = db.cursor.fetchone()['joined']
        db.cursor.execute("SELECT COUNT(*) as l FROM transactions WHERE transaction_type = 'return_on_leave' AND timestamp >= ? AND timestamp <= ?", (today_start, now))
        l_today = db.cursor.fetchone()['l']
        stats_message += f"\n📅 За сегодня: 🆕 {j_today}  👋 {l_today}\n"

        if period == 'month':
            week_start = now - timedelta(days=7)
            db.cursor.execute('SELECT COUNT(*) as joined FROM users WHERE joined_at >= ? AND joined_at <= ? AND is_admin = 0 AND is_owner = 0', (week_start, now))
            j_week = db.cursor.fetchone()['joined']
            db.cursor.execute("SELECT COUNT(*) as l FROM transactions WHERE transaction_type = 'return_on_leave' AND timestamp >= ? AND timestamp <= ?", (week_start, now))
            l_week = db.cursor.fetchone()['l']
            stats_message += f"📅 За 7 дней: 🆕 {j_week}  👋 {l_week}\n"

    stats_message += "\n"

   # ── ДЕТАЛЬНЫЕ ПАРАМЕТРЫ (Полностью переведены на user_stats для точности) ──
    stats_message += "📈 ДЕТАЛЬНЫЕ ПАРАМЕТРЫ:\n"

    params_queries = [
        ('ОКС — символов',         'SELECT COALESCE(SUM(total_chars), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',       False),
        ('СДС — ср. длина сообщ.', 'SELECT CAST(SUM(total_chars) AS REAL) / NULLIF(SUM(total_messages), 0) as v FROM user_stats WHERE date >= ? AND date <= ?', True),
        ('Медиа',                   'SELECT COALESCE(SUM(media_sent), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',        False),
        ('Реакции ↗',               'SELECT COALESCE(SUM(reactions_given), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',    False),
        ('Реакции ↙',               'SELECT COALESCE(SUM(reactions_received), 0) as v FROM user_stats WHERE date >= ? AND date <= ?', False),
        ('Ответов всего',           'SELECT COALESCE(SUM(replies_sent), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',       False),
        ('Отвечали (уник.)',        'SELECT COUNT(DISTINCT user_id) as v FROM user_stats WHERE date >= ? AND date <= ? AND total_messages > 0',     False),
        ('Получили ответ (уник.)',  'SELECT COUNT(DISTINCT user_id) as v FROM user_stats WHERE date >= ? AND date <= ? AND replies_received > 0', False),
        ('Упоминания @',            'SELECT COALESCE(SUM(mentions_received), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',  False),
        ('Др. ветки',               'SELECT COALESCE(SUM(other_threads_posts), 0) as v FROM user_stats WHERE date >= ? AND date <= ?', False),
    ]

    for label, sql, is_avg in params_queries:
        db.cursor.execute(sql, (date_from, date_to))
        row = db.cursor.fetchone()
        raw_val = row['v'] if row['v'] is not None else 0
        
        val_d = round_decimal(_d(raw_val), 1 if is_avg else 0)
        
        if is_avg:
            # Для среднего значения (СДС) оставляем один знак после запятой
            stats_message += f"• {label}: {float(val_d):.1f}\n"
        else:
            # Для всех остальных (ОКС, Медиа, Реакции) убираем .00
            # Мы НЕ используем здесь format_number, а форматируем вручную с пробелом-разделителем
            val_int = int(val_d)
            formatted_val = "{:,}".format(val_int).replace(',', ' ')
            stats_message += f"• {label}: {formatted_val}\n"

    keyboard = [
        [InlineKeyboardButton("📊 Скачать отчёт",       callback_data=f"stats_export_{period}_{stats_type}")],
        [InlineKeyboardButton("🔙 Назад к периодам",    callback_data=f"stats_type_{stats_type}")],
        [InlineKeyboardButton("🔙 Назад к статистике",  callback_data="menu_stats")],
    ]
    await query.edit_message_text(stats_message, reply_markup=InlineKeyboardMarkup(keyboard))
