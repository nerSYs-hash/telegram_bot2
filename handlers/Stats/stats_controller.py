#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import logging
import traceback
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import (
    format_number, get_moscow_time, get_today_date_msk, 
    export_stats_to_excel, export_users_stats_to_excel, export_stats_to_pdf
)

async def show_stats_menu(query, user, admin_id):
    """Главное меню статистики."""
    if user.id != admin_id:
        await query.answer("Нет доступа.", show_alert=True)
        return
    keyboard = [
        [InlineKeyboardButton("📊 Общая по чату", callback_data="stats_type_chat")],
        [InlineKeyboardButton("👤 По пользователям", callback_data="stats_type_users")],
        [InlineKeyboardButton("📈 Чат + пользователи", callback_data="stats_type_combined")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")],
    ]
    await query.edit_message_text("📊 СТАТИСТИКА\nВыберите тип:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_stats_period_menu(query, data, user, admin_id):
    """Меню выбора периода."""
    stats_type = data.split('_')[2]
    keyboard = [
        [InlineKeyboardButton("📅 Вчера", callback_data=f"stats_yesterday_{stats_type}")],
        [InlineKeyboardButton("📅 Сегодня", callback_data=f"stats_day_{stats_type}")],
        [InlineKeyboardButton("📅 Неделя", callback_data=f"stats_week_{stats_type}")],
        [InlineKeyboardButton("📅 Месяц", callback_data=f"stats_month_{stats_type}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu_stats")],
    ]
    await query.edit_message_text("📊 Выберите период:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_stats_export(query, data, user, context, admin_id):
    """Выбор формата файла."""
    period = data.split('_')[2]
    keyboard = [
        [InlineKeyboardButton("📗 Excel", callback_data=f"export_xlsx_{period}")],
        [InlineKeyboardButton("📕 PDF", callback_data=f"export_pdf_{period}")],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"stats_{period}")],
    ]
    await query.edit_message_text("📊 Выберите формат экспорта:", reply_markup=InlineKeyboardMarkup(keyboard))

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
            WHERE u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
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
    date_from = start_date.strftime('%Y-%m-%d')
    date_to   = end_date.strftime('%Y-%m-%d')

    # Точный диапазон дат для синхронизации с Excel
    if date_from == date_to:
        date_label = date_from
    else:
        date_label = f"{date_from} — {date_to}"

    stats_message = f"{type_names.get(stats_type, '📊 СТАТИСТИКА ЧАТА')}\n{period_name} ({date_label})\n\n"

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
        prev_end   = (start_date - timedelta(days=1)).strftime('%Y-%m-%d')  # только вчера, не сегодня
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

    # ── 1. Сообщений — из chat_stats (единый источник с Excel) ──
    db.cursor.execute('''
        SELECT COALESCE(SUM(total_messages), 0) as count
        FROM chat_stats
        WHERE date >= ? AND date <= ?
    ''', (date_from, date_to))
    total_messages = int(db.cursor.fetchone()['count'])

    prev_msgs = _prev_val('''
        SELECT COALESCE(SUM(total_messages), 0) as count
        FROM chat_stats
        WHERE date >= ? AND date <= ?
    ''', (prev_start, prev_end))

    stats_message += f"💬 Сообщений: {format_number(total_messages)}{_delta_str(total_messages, prev_msgs)}\n"

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

    # Пульсов заработано — все квесты и активности
    db.cursor.execute('''
        SELECT COALESCE(SUM(amount), 0) as total FROM transactions
        WHERE to_user_id IS NOT NULL
          AND transaction_type IN (
              'message_reward', 'combo_reward', 'sprint_reward',
              'referral_reward', 'lottery_win', 'bingo_win',
              'monthly_gift', 'reaction_given_reward', 'reaction_received_reward',
              'lootbox_win', 'bbs_popularity', 'admin_give', 'compensation_reward'
          )
          AND timestamp >= ? AND timestamp <= ?
    ''', (start_date, end_date))
    r = db.cursor.fetchone()
    total_pulses = _d(r['total']) if r['total'] else Decimal('0')
    stats_message += f"💎 Заработано Пульсов: {format_number(total_pulses)}\n"

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

    # ── ДЕТАЛЬНЫЕ ПАРАМЕТРЫ ──
    stats_message += "📈 ДЕТАЛЬНЫЕ ПАРАМЕТРЫ:\n"

    params_queries = [
        ('ОКС — символов',              'SELECT COALESCE(SUM(total_chars), 0) as v FROM chat_stats WHERE date >= ? AND date <= ?',       False),
        ('СДС — ср. длина сообщ.',      'SELECT COALESCE(AVG(avg_message_length), 0) as v FROM chat_stats WHERE date >= ? AND date <= ?', True),
        ('Медиа',                       'SELECT COALESCE(SUM(total_media), 0) as v FROM chat_stats WHERE date >= ? AND date <= ?',        False),
        ('Реакции оставлены пользователями', 'SELECT COALESCE(SUM(reactions_given), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',    False),
        ('Реакции получены пользователями', 'SELECT COALESCE(SUM(reactions_received), 0) as v FROM user_stats WHERE date >= ? AND date <= ?', False),
        ('Ответы отправлены',            'SELECT COALESCE(SUM(replies_sent), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',       False),
        ('Ответы получены',              'SELECT COALESCE(SUM(replies_received), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',   False),
        ('Упоминания @',                'SELECT COALESCE(SUM(mentions_received), 0) as v FROM user_stats WHERE date >= ? AND date <= ?',  False),
        ('Др. ветки',                   'SELECT COALESCE(SUM(other_threads_posts), 0) as v FROM user_stats WHERE date >= ? AND date <= ?', False),
    ]

    for label, sql, is_avg in params_queries:
        db.cursor.execute(sql, (date_from, date_to))
        raw_val = db.cursor.fetchone()['v']
        val_d   = round_decimal(_d(raw_val), 1 if is_avg else 0)
        if is_avg:
            stats_message += f"• {label}: {float(val_d):.1f}\n"
        else:
            stats_message += f"• {label}: {format_number(int(val_d))}\n"

    stats_message += "\n"

    keyboard = [
        [InlineKeyboardButton("📊 Скачать отчёт",       callback_data=f"stats_export_{period}_{stats_type}")],
        [InlineKeyboardButton("🔙 Назад к периодам",    callback_data=f"stats_type_{stats_type}")],
        [InlineKeyboardButton("🔙 Назад к статистике",  callback_data="menu_stats")],
    ]
    await query.edit_message_text(stats_message, reply_markup=InlineKeyboardMarkup(keyboard))

async def generate_export_file(query, data, user, context, db, admin_id, target_chat_id):
    """Генерация полного аналитического отчета (Все данные и индексы на месте)."""
    if user.id != admin_id:
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    parts = data.split('_')
    file_format = parts[1]
    period = parts[2]

    await query.edit_message_text("⏳ Генерирую расширенный аналитический отчёт...")

    try:
        now = get_moscow_time()
        if period == 'yesterday':
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date   = now.replace(hour=0, minute=0, second=0, microsecond=0)
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
            await query.edit_message_text("❌ Неизвестный период")
            return

        # 1. Знаменатель для индексов активности
        try:
            m_count = await context.bot.get_chat_member_count(target_chat_id)
        except Exception:
            db.cursor.execute('SELECT COUNT(*) as total FROM users')
            m_count = db.cursor.fetchone()['total']

        b_count = int(os.getenv('BOT_COUNT', 1))
        divisor = Decimal(max(m_count - b_count - 1, 1))   # ← Decimal

        # 2. Агрегированные данные из БД
        db.cursor.execute('''
            SELECT
                COALESCE(SUM(total_chars), 0)                as chars,
                COALESCE(SUM(total_messages), 0)             as msgs,
                COALESCE(SUM(total_words), 0)                as words,
                COALESCE(SUM(total_reactions), 0)            as reacts,
                COALESCE(SUM(total_media), 0)                as media,
                COALESCE(SUM(total_pulses_mined), 0)         as pulses,
                COALESCE(SUM(total_messages_with_admins), 0) as with_adm,
                COALESCE(SUM(total_messages_without_admins), 0) as no_adm,
                COALESCE(AVG(avg_message_length), 0)         as avg_len
            FROM chat_stats WHERE date >= ? AND date <= ?
        ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        raw = db.cursor.fetchone()

        db.cursor.execute('''
            SELECT
                COALESCE(SUM(reactions_given), 0)   as korp,
                COALESCE(SUM(reactions_received), 0) as kprp,
                COALESCE(SUM(replies_received), 0)  as kopyup,
                COALESCE(SUM(replies_sent), 0)      as kopyap,
                COALESCE(SUM(mentions_received), 0) as kupp,
                COALESCE(SUM(other_threads_posts), 0) as pivdvp
            FROM user_stats WHERE date >= ? AND date <= ?
        ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        det = db.cursor.fetchone()

        # 3. Структура отчёта
        stats_data = {
            'title': f'Аналитический отчет чата - {period_name}',
            'period': period_name, 'period_type': period,
            'start_date': start_date.strftime('%d.%m.%Y'),
            'end_date':   end_date.strftime('%d.%m.%Y'),
            'general': {}, 'top_messages': [], 'top_earners': [],
            'detailed_stats': {}, 'daily_stats': []
        }

        # 4. Наполнение GENERAL через Decimal
        g = stats_data['general']

        oksp_idx  = _calc_index(raw['chars'],    Decimal('0.05'), Decimal('100')) / divisor
        sdsp_idx  = _calc_index(raw['avg_len'],  Decimal('0.05'), Decimal('100')) / divisor
        cho_idx   = _calc_index(raw['words'],     Decimal('0.05'))                 / divisor
        media_idx = _calc_index(raw['media'],    Decimal('0.07'))                 / divisor
        korp_idx  = _calc_index(det['korp'],     Decimal('0.08'))                 / divisor
        kprp_idx  = _calc_index(det['kprp'],     Decimal('0.10'))                 / divisor
        kopyup_idx= _calc_index(det['kopyup'],   Decimal('0.18'))                 / divisor
        kopyap_idx= _calc_index(det['kopyap'],   Decimal('0.15'))                 / divisor
        kupp_idx  = _calc_index(det['kupp'],     Decimal('0.15'))                 / divisor
        pivdvp_idx= _calc_index(det['pivdvp'],   Decimal('0.12'))                 / divisor

        def _fmt_idx(idx_d: Decimal, raw_val) -> str:
            """Формат для general: 'индекс (значение)' — строка только для отображения."""
            return f"{float(round_decimal(idx_d, 3)):.3f} ({format_number(raw_val)})"

        g['ОКС(Ч) - Общее количество символов']        = _fmt_idx(oksp_idx,   raw['chars'])
        g['СДС(Ч) - Средняя длина сообщения']          = _fmt_idx(sdsp_idx,   raw['avg_len'])
        g['КС(Ч) - Количество слов (Всего сообщ.)']    = _fmt_idx(cho_idx,    raw['words'])
        g['Медиа(Ч) - Медиа контент']                  = _fmt_idx(media_idx,  raw['media'])
        g['КОР(Ч) - Реакции оставленные']              = _fmt_idx(korp_idx,   det['korp'])
        g['КПР(Ч) - Реакции полученные']               = _fmt_idx(kprp_idx,   det['kprp'])
        g['КОтв(Ч) - Ответы полученные']               = _fmt_idx(kopyup_idx, det['kopyup'])
        g['КОтп(Ч) - Ответы отправленные']             = _fmt_idx(kopyap_idx, det['kopyap'])
        g['КУП(Ч) - Упоминания @']                     = _fmt_idx(kupp_idx,   det['kupp'])
        g['ПДВ(Ч) - Публ. в других ветках']            = _fmt_idx(pivdvp_idx, det['pivdvp'])

        g['💬 Сообщений с администраторами']   = format_number(raw['with_adm'])
        g['💬 Сообщений без администраторов']  = format_number(raw['no_adm'])

        db.cursor.execute(
            'SELECT COUNT(DISTINCT user_id) as act FROM messages WHERE timestamp >= ? AND timestamp <= ?',
            (start_date, end_date)
        )
        stats_data['act_count'] = db.cursor.fetchone()['act']
        g['👥 Активных пользователей'] = stats_data['act_count']

        # Майнинг: chat_stats + транзакции новой системы (message_reward, combo/sprint - penalty)
        db.cursor.execute(
            "SELECT COALESCE(SUM(CASE WHEN transaction_type IN "
            "('message_reward','combo_reward','sprint_reward') THEN amount ELSE 0 END), 0) AS earned, "
            "COALESCE(SUM(CASE WHEN transaction_type = 'penalty_deduct' THEN amount ELSE 0 END), 0) AS penalized "
            "FROM transactions WHERE timestamp >= ? AND timestamp <= ?",
            (start_date, end_date)
        )
        _mining_row = db.cursor.fetchone()
        _mining_earned = float(_mining_row['earned'])
        _mining_penalty = float(_mining_row['penalized'])
        _mining_net = max(_mining_earned - _mining_penalty, 0)
        g['💎 Добыто Пульсов']         = _mining_net

        for t_type, t_label in [
            ('donate_to_user',   '🎁 Донатов пользователям'),
            ('donate_to_bank',   '🏦 Донатов в банк'),
            ('reactor_donation', '🔋 Донатов в реактор'),
        ]:
            db.cursor.execute(
                'SELECT COALESCE(SUM(amount),0) as tot, COUNT(*) as cnt FROM transactions '
                'WHERE transaction_type=? AND timestamp>=? AND timestamp<=?',
                (t_type, start_date, end_date)
            )
            r_don = db.cursor.fetchone()
            g[t_label] = f"{format_number(r_don['tot'])} 💎 ({r_don['cnt']} шт.)"

        db.cursor.execute(
            'SELECT COUNT(*) as j FROM users WHERE joined_at >= ? AND joined_at <= ? AND is_admin=0 AND is_owner=0',
            (start_date, end_date)
        )
        g['🆕 Вступило за период'] = db.cursor.fetchone()['j']

        db.cursor.execute(
            "SELECT COUNT(*) as l FROM transactions WHERE transaction_type='return_on_leave' "
            "AND timestamp >= ? AND timestamp <= ?",
            (start_date, end_date)
        )
        g['👋 Вышло за период'] = db.cursor.fetchone()['l']

        er = round_decimal(
            _d(stats_data['act_count']) / _d(m_count) * Decimal('100') if m_count > 0 else Decimal('0'),
            1
        )
        g['📊 Коэффициент вовлеченности (ER)'] = f"{float(er):.1f}%"

        # Итоговый индекс здоровья чата — Decimal сумма
        health_idx = (
            oksp_idx + sdsp_idx + cho_idx + media_idx +
            korp_idx + kprp_idx + kopyup_idx + kopyap_idx +
            kupp_idx + pivdvp_idx
        )
        g['🛡️ ИТОГОВЫЙ ИНДЕКС ЗДОРОВЬЯ ЧАТА'] = f"{float(round_decimal(health_idx, 3)):.3f}"

        # 5. ТОП 10 АКТИВИСТОВ (по индексу активности)
        from utils.exchange_rate import ACTIVITY_INDEX_SQL
        db.cursor.execute(f'''
            SELECT u.username, u.first_name,
                   ({ACTIVITY_INDEX_SQL}) as activity_index,
                   COALESCE(SUM(us.pulses_mined), 0) as earned
            FROM users u
            LEFT JOIN user_stats us ON u.user_id = us.user_id AND us.date >= ? AND us.date <= ?
            WHERE (u.is_admin=0 AND u.is_owner=0)
            GROUP BY u.user_id
            HAVING SUM(us.total_messages) > 0 OR SUM(us.reactions_given) > 0
                   OR SUM(us.reactions_received) > 0 OR SUM(us.replies_sent) > 0
            ORDER BY activity_index DESC LIMIT 10
        ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        for i, r_msg in enumerate(db.cursor.fetchall()):
            stats_data['top_messages'].append({
                'rank': i + 1,
                'username': f"@{r_msg['username'] or r_msg['first_name']}",
                'activity_score': float(_d(r_msg['activity_index'])),
                'earned_raw': float(_d(r_msg['earned'])),
            })

        # 5b. ТОП 10 ПО ЗАРАБОТКУ
        db.cursor.execute('''
            SELECT u.username, u.first_name,
                   COALESCE(SUM(us.pulses_mined), 0) as earned
            FROM users u
            LEFT JOIN user_stats us ON u.user_id = us.user_id AND us.date >= ? AND us.date <= ?
            WHERE (u.is_admin=0 AND u.is_owner=0)
            GROUP BY u.user_id HAVING earned > 0
            ORDER BY earned DESC LIMIT 10
        ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        for i, r_earn in enumerate(db.cursor.fetchall()):
            stats_data['top_earners'].append({
                'rank': i + 1,
                'username': f"@{r_earn['username'] or r_earn['first_name']}",
                'earned': float(_d(r_earn['earned'])),
            })

        # 6. ДЕТАЛИЗАЦИЯ с персональным индексом активности
        db.cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, u.joined_at,
                   COALESCE(SUM(us.total_messages), 0)    as msgs,
                   COALESCE(SUM(us.total_chars), 0)       as chars,
                   COALESCE(SUM(us.total_words), 0)       as words,
                   COALESCE(SUM(us.reactions_given), 0)   as reacts_g,
                   COALESCE(SUM(us.reactions_received), 0) as reacts_r,
                   COALESCE(SUM(us.replies_sent), 0)      as replies_s,
                   COALESCE(SUM(us.replies_received), 0)  as replies_r,
                   COALESCE(SUM(us.mentions_received), 0) as kupp_r,
                   COALESCE(SUM(us.media_sent), 0)        as media_s,
                   COALESCE(SUM(us.other_threads_posts), 0) as threads,
                   COALESCE(SUM(us.pulses_mined), 0)      as earned
            FROM users u LEFT JOIN user_stats us ON u.user_id = us.user_id AND us.date >= ? AND us.date <= ?
            WHERE (u.is_admin=0 AND u.is_owner=0)
            GROUP BY u.user_id HAVING msgs > 0 ORDER BY earned DESC
        ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

        CHARS_NORM = Decimal('100')
        for r_user in db.cursor.fetchall():
            _msgs  = _d(r_user['msgs'])
            _chars = _d(r_user['chars'])
            _avg_l = _chars / _msgs if _msgs > 0 else Decimal('0')

            # Индекс активности — Decimal арифметика (ЕДИНАЯ ФОРМУЛА)
            u_idx = (
                Decimal('0.05') * (_chars / CHARS_NORM) +
                Decimal('0.05') * (_avg_l / CHARS_NORM) +
                Decimal('0.05') * _msgs +
                Decimal('0.08') * _d(r_user['reacts_g']) +
                Decimal('0.10') * _d(r_user['reacts_r']) +
                Decimal('0.18') * _d(r_user['replies_r']) +
                Decimal('0.15') * _d(r_user['replies_s']) +
                Decimal('0.15') * _d(r_user['kupp_r']) +
                Decimal('0.07') * _d(r_user['media_s']) +
                Decimal('0.12') * _d(r_user['threads'])
            ) / divisor

            u_name = (
                f"@{r_user['username']}" if r_user['username']
                else (r_user['first_name'] or f"ID:{r_user['user_id']}")
            )
            stats_data['detailed_stats'][u_name] = {
                'user_id':           r_user['user_id'],
                'messages':          int(_msgs),
                'chars':             int(_chars),
                'words':             int(_d(r_user['words'])),
                'reactions':         int(_d(r_user['reacts_g'])),
                'reactions_received': int(_d(r_user['reacts_r'])),
                'replies':           int(_d(r_user['replies_s'])),
                'replies_received':  int(_d(r_user['replies_r'])),
                'mentions_received': int(_d(r_user['kupp_r'])),
                'media':             int(_d(r_user['media_s'])),
                'other_threads_posts': int(_d(r_user['threads'])),
                'days_in_chat':      calculate_days_in_chat(r_user['joined_at']),
                'earned':            float(round_decimal(_d(r_user['earned']), 2)),  # ← Decimal
                'activity_index':    float(round_decimal(u_idx, 3)),                 # ← Decimal
            }

        if period in ['week', 'month', 'year']:

            def collect_day_stats(day):
                """Собирает статистические данные за один день."""
                db.cursor.execute('''
                    SELECT
                        COALESCE(SUM(total_messages), 0)             as messages,
                        COALESCE(SUM(total_chars), 0)                as chars,
                        COALESCE(SUM(total_words), 0)                as words,
                        COALESCE(SUM(total_reactions), 0)            as reactions,
                        COALESCE(SUM(total_media), 0)                as media,
                        COALESCE(SUM(total_pulses_mined), 0)         as pulses,
                        COALESCE(SUM(total_messages_with_admins), 0) as msgs_with_admins,
                        COALESCE(SUM(total_messages_without_admins), 0) as msgs_without_admins,
                        COALESCE(AVG(avg_message_length), 0)         as avg_msg_length
                    FROM chat_stats WHERE date = ?
                ''', (day.strftime('%Y-%m-%d'),))
                day_data = db.cursor.fetchone()

                db.cursor.execute('''
                    SELECT COUNT(DISTINCT user_id) as active_users
                    FROM user_stats WHERE date = ? AND total_messages > 0
                ''', (day.strftime('%Y-%m-%d'),))
                row = db.cursor.fetchone()
                active_users = row['active_users'] if row else 0

                db.cursor.execute(
                    'SELECT COUNT(*) as joined FROM users WHERE DATE(joined_at) = ?',
                    (day.strftime('%Y-%m-%d'),)
                )
                row = db.cursor.fetchone()
                joined = row['joined'] if row else 0

                db.cursor.execute(
                    "SELECT COUNT(*) as left_users FROM transactions "
                    "WHERE transaction_type = 'return_on_leave' AND DATE(timestamp) = ?",
                    (day.strftime('%Y-%m-%d'),)
                )
                row = db.cursor.fetchone()
                left_users = row['left_users'] if row else 0

                db.cursor.execute(
                    "SELECT COUNT(*) as total_users FROM users WHERE joined_at <= ?",
                    (day.strftime('%Y-%m-%d 23:59:59'),)
                )
                row = db.cursor.fetchone()
                total_users = row['total_users'] if row else 0

                # Вовлечённость — Decimal
                engagement = float(
                    round_decimal(_d(active_users) / _d(total_users) * Decimal('100'), 2)
                    if total_users > 0 else Decimal('0')
                )

                db.cursor.execute('''
                    SELECT
                        COALESCE(SUM(reactions_given), 0)    as reactions_given,
                        COALESCE(SUM(reactions_received), 0) as reactions_received,
                        COALESCE(SUM(replies_sent), 0)       as replies_sent,
                        COALESCE(SUM(replies_received), 0)   as replies_received,
                        COALESCE(SUM(mentions_received), 0)  as mentions,
                        COALESCE(SUM(other_threads_posts), 0) as other_threads
                    FROM user_stats WHERE date = ?
                ''', (day.strftime('%Y-%m-%d'),))
                us = db.cursor.fetchone()

                return {
                    'messages':            int(_d(day_data['messages']      if day_data else 0)),
                    'chars':               int(_d(day_data['chars']         if day_data else 0)),
                    'words':               int(_d(day_data['words']         if day_data else 0)),
                    'reactions':           int(_d(day_data['reactions']     if day_data else 0)),
                    'media':               int(_d(day_data['media']         if day_data else 0)),
                    'pulses':              float(round_decimal(_d(day_data['pulses'] if day_data else 0), 2)),
                    'msgs_with_admins':    int(_d(day_data['msgs_with_admins']    if day_data else 0)),
                    'msgs_without_admins': int(_d(day_data['msgs_without_admins'] if day_data else 0)),
                    'avg_msg_length':      float(round_decimal(_d(day_data['avg_msg_length'] if day_data else 0), 2)),
                    'active_users':        int(active_users),
                    'total_users':         int(total_users),
                    'joined':              int(joined),
                    'left_users':          int(left_users),
                    'engagement':          engagement,
                    'reactions_given':     int(_d(us['reactions_given']    if us else 0)),
                    'reactions_received':  int(_d(us['reactions_received'] if us else 0)),
                    'replies_sent':        int(_d(us['replies_sent']       if us else 0)),
                    'replies_received':    int(_d(us['replies_received']   if us else 0)),
                    'mentions':            int(_d(us['mentions']            if us else 0)),
                    'other_threads':       int(_d(us['other_threads']      if us else 0)),
                }

            def collect_month_stats(first_day, last_day):
                """Собирает статистические данные за месяц."""
                db.cursor.execute('''
                    SELECT
                        COALESCE(SUM(total_messages), 0)             as messages,
                        COALESCE(SUM(total_chars), 0)                as chars,
                        COALESCE(SUM(total_words), 0)                as words,
                        COALESCE(SUM(total_reactions), 0)            as reactions,
                        COALESCE(SUM(total_media), 0)                as media,
                        COALESCE(SUM(total_pulses_mined), 0)         as pulses,
                        COALESCE(SUM(total_messages_with_admins), 0) as msgs_with_admins,
                        COALESCE(SUM(total_messages_without_admins), 0) as msgs_without_admins,
                        COALESCE(AVG(avg_message_length), 0)         as avg_msg_length
                    FROM chat_stats WHERE date >= ? AND date <= ?
                ''', (first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
                month_data = db.cursor.fetchone()

                db.cursor.execute('''
                    SELECT COUNT(DISTINCT user_id) as active_users
                    FROM user_stats WHERE date >= ? AND date <= ? AND total_messages > 0
                ''', (first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
                row = db.cursor.fetchone()
                active_users = row['active_users'] if row else 0

                db.cursor.execute(
                    'SELECT COUNT(*) as joined FROM users WHERE DATE(joined_at) >= ? AND DATE(joined_at) <= ?',
                    (first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d'))
                )
                row = db.cursor.fetchone()
                joined = row['joined'] if row else 0

                db.cursor.execute(
                    "SELECT COUNT(*) as left_users FROM transactions "
                    "WHERE transaction_type = 'return_on_leave' AND DATE(timestamp) >= ? AND DATE(timestamp) <= ?",
                    (first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d'))
                )
                row = db.cursor.fetchone()
                left_users = row['left_users'] if row else 0

                db.cursor.execute(
                    "SELECT COUNT(*) as total_users FROM users WHERE joined_at <= ?",
                    (last_day.strftime('%Y-%m-%d 23:59:59'),)
                )
                row = db.cursor.fetchone()
                total_users = row['total_users'] if row else 0

                engagement = float(
                    round_decimal(_d(active_users) / _d(total_users) * Decimal('100'), 2)
                    if total_users > 0 else Decimal('0')
                )

                db.cursor.execute('''
                    SELECT
                        COALESCE(SUM(reactions_given), 0)    as reactions_given,
                        COALESCE(SUM(reactions_received), 0) as reactions_received,
                        COALESCE(SUM(replies_sent), 0)       as replies_sent,
                        COALESCE(SUM(replies_received), 0)   as replies_received,
                        COALESCE(SUM(mentions_received), 0)  as mentions,
                        COALESCE(SUM(other_threads_posts), 0) as other_threads
                    FROM user_stats WHERE date >= ? AND date <= ?
                ''', (first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
                us = db.cursor.fetchone()

                return {
                    'messages':            int(_d(month_data['messages']      if month_data else 0)),
                    'chars':               int(_d(month_data['chars']         if month_data else 0)),
                    'words':               int(_d(month_data['words']         if month_data else 0)),
                    'reactions':           int(_d(month_data['reactions']     if month_data else 0)),
                    'media':               int(_d(month_data['media']         if month_data else 0)),
                    'pulses':              float(round_decimal(_d(month_data['pulses'] if month_data else 0), 2)),
                    'msgs_with_admins':    int(_d(month_data['msgs_with_admins']    if month_data else 0)),
                    'msgs_without_admins': int(_d(month_data['msgs_without_admins'] if month_data else 0)),
                    'avg_msg_length':      float(round_decimal(_d(month_data['avg_msg_length'] if month_data else 0), 2)),
                    'active_users':        int(active_users),
                    'total_users':         int(total_users),
                    'joined':              int(joined),
                    'left_users':          int(left_users),
                    'engagement':          engagement,
                    'reactions_given':     int(_d(us['reactions_given']    if us else 0)),
                    'reactions_received':  int(_d(us['reactions_received'] if us else 0)),
                    'replies_sent':        int(_d(us['replies_sent']       if us else 0)),
                    'replies_received':    int(_d(us['replies_received']   if us else 0)),
                    'mentions':            int(_d(us['mentions']            if us else 0)),
                    'other_threads':       int(_d(us['other_threads']      if us else 0)),
                }

            weekdays = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВСК']

            if period == 'week':
                current = start_date.date()
                while current <= end_date.date():
                    day_stats = collect_day_stats(current)
                    day_stats['date'] = f"{current.strftime('%d.%m.%y')} {weekdays[current.weekday()]}"
                    stats_data['daily_stats'].append(day_stats)
                    current += timedelta(days=1)

            elif period == 'month':
                current = start_date.date()
                while current <= end_date.date():
                    day_stats = collect_day_stats(current)
                    day_stats['date'] = f"{current.strftime('%d.%m.%y')} {weekdays[current.weekday()]}"
                    stats_data['daily_stats'].append(day_stats)
                    current += timedelta(days=1)

            elif period == 'year':
                cy, cm_ = start_date.year, start_date.month
                while (cy < end_date.year) or (cy == end_date.year and cm_ <= end_date.month):
                    first_day = date_type(cy, cm_, 1)
                    last_day  = date_type(cy, cm_, calendar.monthrange(cy, cm_)[1])
                    month_stats = collect_month_stats(first_day, last_day)
                    month_stats['date']  = f"{cm_:02d}"
                    month_stats['month'] = cm_
                    month_stats['year']  = cy
                    stats_data['daily_stats'].append(month_stats)
                    cm_ += 1
                    if cm_ > 12:
                        cm_ = 1
                        cy += 1
        
        try:
            db.cursor.execute('''
                SELECT
                    COALESCE(SUM(CASE WHEN transaction_type = 'message_reward' THEN amount ELSE 0 END), 0) AS base,
                    COALESCE(SUM(CASE WHEN transaction_type = 'combo_reward'   THEN amount ELSE 0 END), 0) AS combo,
                    COALESCE(SUM(CASE WHEN transaction_type = 'sprint_reward'  THEN amount ELSE 0 END), 0) AS sprint,
                    COALESCE(SUM(CASE WHEN transaction_type = 'penalty_deduct' THEN amount ELSE 0 END), 0) AS penalty
                FROM transactions
                WHERE timestamp >= ? AND timestamp <= ?
            ''', (start_date, end_date))
            mining_row = db.cursor.fetchone()
            stats_data['mining_stats'] = {
                'base':    float(mining_row['base'])    if mining_row else 0.0,
                'combo':   float(mining_row['combo'])   if mining_row else 0.0,
                'sprint':  float(mining_row['sprint'])  if mining_row else 0.0,
                'penalty': float(mining_row['penalty']) if mining_row else 0.0,
            }
        except Exception as e:
            logging.warning(f"Mining stats query failed: {e}")
            stats_data['mining_stats'] = {'base': 0, 'combo': 0, 'sprint': 0, 'penalty': 0} 
        
        # ── Детальная статистика майнинга (поимённо) ──────────────────────
        MINING_DESCRIPTIONS = {
            # Комбо
            'writer':       {'label': '✍️ Писатель',       'desc': 'Текст > 50 символов'},
            'illustrator':  {'label': '🖼 Иллюстратор',    'desc': 'Текст > 50 символов + Фото'},
            'reviewer':     {'label': '🎬 Обозреватель',    'desc': 'Видео + Текст > 100 слов'},
            'dj':           {'label': '🎧 Диджей',          'desc': 'Ссылка на плейлист'},
            'sharp_tongue': {'label': '🗡 Острый язык',     'desc': 'На сообщение ответили > 2 раз'},
            'viral_post':   {'label': '📢 Вирусный пост',   'desc': 'Сообщение собрало > 2 лайков'},
            'hit_post':     {'label': '💥 Хит-пост',        'desc': 'Сообщение собрало 4+ лайка'},
            'legend_post':  {'label': '👑 Легенда',          'desc': 'Сообщение собрало 6+ лайков'},
            # Спринты
            'chat_core':    {'label': '💬 Основа чата',      'desc': '10 сообщений за 24 часа'},
            'emotional':    {'label': '😍 Эмоциональный',    'desc': '10 эмодзи-сообщений за 24 часа'},
            'photographer': {'label': '📸 Фотограф',         'desc': '3+ фото за 24 часа'},
            'director':     {'label': '🎬 Режиссёр',         'desc': '2 видео за 24 часа (спец. ветки)'},
            'music_lover':  {'label': '🎧 Меломан',          'desc': '5 аудио за 24 часа (ветка Музыки)'},
            'face_seller':  {'label': '🫧 Лицом торгуешь',   'desc': '5 видео-кружков за 12 часов'},
            'center':       {'label': '🎯 Центр внимания',   'desc': '20 ответов тебе за 12 часов'},
            'radio':        {'label': '🎙 Радио',             'desc': '4 голосовых за 1 час'},
            'gif_room':     {'label': '🎞 Гифошная',          'desc': '10 гифок за 1 час'},
            'chatterbox':   {'label': '🗣 Болтун',            'desc': '20 ответов за 1 час'},
            'generous':     {'label': '💝 Щедрая душа',      'desc': '5 лайков за 1 час'},
            'favorite':     {'label': '⭐ Любимчик',          'desc': '10 полученных лайков за 1 час'},
            # Штрафы
            'copypaste':    {'label': '📋 Копипаст',          'desc': 'Дубликат сообщения за последний час'},
            'wrong_door':   {'label': '🚪 Не та дверь',      'desc': 'Контент не по теме ветки'},
            'toxic':        {'label': '☠️ Токсик',            'desc': 'Токсичное поведение'},
        }

        try:
            sd_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
            ed_str = end_date.strftime('%Y-%m-%d %H:%M:%S')

            # 1. Базовая добыча
            db.cursor.execute('''
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM transactions
                WHERE transaction_type = 'message_reward'
                  AND timestamp >= ? AND timestamp <= ?
            ''', (sd_str, ed_str))
            base_total = float(db.cursor.fetchone()['total'])

            # 2. Комбо (поимённо) — поддержка старой (date) и новой (claimed_at) схемы
            combos = []
            try:
                db.cursor.execute('''
                    SELECT combo_name, COALESCE(SUM(reward), 0) AS total
                    FROM combo_claims
                    WHERE claimed_at >= ? AND claimed_at <= ?
                    GROUP BY combo_name ORDER BY total DESC
                ''', (sd_str, ed_str))
                combos_raw = db.cursor.fetchall()
            except Exception:
                # Старая схема с колонкой date
                try:
                    sd_date = start_date.strftime('%Y-%m-%d')
                    ed_date = end_date.strftime('%Y-%m-%d')
                    db.cursor.execute('''
                        SELECT combo_name, COALESCE(SUM(reward), 0) AS total
                        FROM combo_claims
                        WHERE date >= ? AND date <= ?
                        GROUP BY combo_name ORDER BY total DESC
                    ''', (sd_date, ed_date))
                    combos_raw = db.cursor.fetchall()
                except Exception:
                    combos_raw = []
            for r in combos_raw:
                name = r['combo_name']
                info = MINING_DESCRIPTIONS.get(name, {'label': name, 'desc': ''})
                combos.append({'name': name, 'label': info['label'],
                               'description': info['desc'], 'sum': float(r['total'])})

            # 3. Спринты (поимённо)
            sprints = []
            try:
                db.cursor.execute('''
                    SELECT sprint_name, COALESCE(SUM(reward), 0) AS total
                    FROM sprint_claims
                    WHERE claimed_at >= ? AND claimed_at <= ?
                    GROUP BY sprint_name ORDER BY total DESC
                ''', (sd_str, ed_str))
                sprints_raw = db.cursor.fetchall()
            except Exception:
                sprints_raw = []
            for r in sprints_raw:
                name = r['sprint_name']
                info = MINING_DESCRIPTIONS.get(name, {'label': name, 'desc': ''})
                sprints.append({'name': name, 'label': info['label'],
                                'description': info['desc'], 'sum': float(r['total'])})

            # 4. Штрафы (поимённо)
            db.cursor.execute('''
                SELECT description, COALESCE(SUM(amount), 0) AS total
                FROM transactions
                WHERE transaction_type = 'penalty_deduct'
                  AND timestamp >= ? AND timestamp <= ?
                GROUP BY description ORDER BY total DESC
            ''', (sd_str, ed_str))
            penalties = []
            key_map = {'копипаст': 'copypaste', 'не в ту дверь (нарушение)': 'wrong_door',
                       'удаление (токсик)': 'toxic'}
            for r in db.cursor.fetchall():
                desc = r['description'] or ''
                raw_key = desc.replace('Штраф: ', '').strip().lower()
                mapped = key_map.get(raw_key, raw_key)
                info = MINING_DESCRIPTIONS.get(mapped, {'label': desc, 'desc': ''})
                penalties.append({'name': mapped, 'label': info['label'],
                                  'description': info['desc'], 'sum': float(r['total'])})

            stats_data['mining_detailed'] = {
                'base_total': base_total,
                'combos': combos,
                'sprints': sprints,
                'penalties': penalties,
            }
        except Exception as e:
            logging.warning(f"Mining detailed stats failed: {e}")
            stats_data['mining_detailed'] = None
        
        # Генерация файла
        timestamp = get_moscow_time().strftime('%Y%m%d_%H%M%S')
        os.makedirs('logs', exist_ok=True)

        try:
            joins_data = db.get_user_joins(
                start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
                end_date=end_date.strftime('%Y-%m-%d %H:%M:%S')
            )
            stats_data['user_joins'] = [dict(j) for j in joins_data] if joins_data else []
        except Exception as e:
            logging.error(f"Error collecting joins data: {e}")
            stats_data['user_joins'] = []

        if file_format == 'pdf':
            filename = f'stats_{period}_{timestamp}.pdf'
            filepath = os.path.join('logs', filename)
            logging.info(f"Generating PDF export to: {filepath}")
            result = export_stats_to_pdf(stats_data, filepath)
            if result is None:
                logging.error("export_stats_to_pdf returned None")
                await query.edit_message_text(
                    "❌ Ошибка при создании PDF. Проверьте логи.\n"
                    "Убедитесь что установлен пакет: pip install reportlab",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")
                    ]])
                )
                return
            caption = f"📕 Статистика чата ({period_name}) — PDF"
        else:
            filename = f'stats_{period}_{timestamp}.xlsx'
            filepath = os.path.join('logs', filename)
            logging.info(f"Generating Excel export to: {filepath}")
            result = export_stats_to_excel(stats_data, filepath)
            if result is None:
                logging.error("export_stats_to_excel returned None - file not created")
                await query.edit_message_text(
                    "❌ Ошибка при создании файла. Проверьте логи.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")
                    ]])
                )
                return
            # Добавляем лист "Курс" с графиком
            _add_rate_sheet_to_excel(filepath, db, start_date, end_date, period_name)
            caption = f"📊 Статистика чата ({period_name}) — Excel"

        if os.path.exists(filepath):
            with open(filepath, 'rb') as file:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file,
                    filename=filename,
                    caption=caption,
                    reply_to_message_id=query.message.message_id
                )
            os.remove(filepath)
            await query.edit_message_text(
                "✅ Отчёт успешно сгенерирован и отправлен!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")
                ]])
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка при создании файла",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")
                ]])
            )

    except Exception as e:
        logging.error(f"Error generating export: {e}")
        traceback.print_exc()
        await query.edit_message_text(
            f"❌ Произошла ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")
            ]])
        )


# ═══════════════════════════════════════════════════════════════
# ТОП, ЛИДЕРБОРДЫ, МЕНЮ СТАТИСТИКИ
# ═══════════════════════════════════════════════════════════════

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
    """Живая проверка: фильтрует ушедших и чинит БД."""
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
    today_str = str(today)

    admin_ids = set()
    if context:
        try:
            admins = await context.bot.get_chat_administrators(target_chat_id)
            admin_ids = {a.user.id for a in admins}
        except Exception:
            pass

    db.cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, u.balance,
               COALESCE(us_today.pulses_mined, 0) as pulses_today,
               COALESCE(SUM(us_all.pulses_mined), 0) as pulses_total
        FROM users u
        LEFT JOIN user_stats us_today ON u.user_id = us_today.user_id AND us_today.date = ?
        LEFT JOIN user_stats us_all   ON u.user_id = us_all.user_id
        WHERE u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
        GROUP BY u.user_id
        ORDER BY pulses_today DESC, pulses_total DESC, u.balance DESC
        LIMIT 20
    ''', (today,))
    
    all_users = db.cursor.fetchall()
    top_users = await _filter_active_users(context, target_chat_id, all_users, admin_ids, db, limit=5)

    message = "🏆 ТОП-5 БОГАЧЕЙ ЗА СЕГОДНЯ\n\n"

    if top_users and any(_d(u['pulses_today']) > 0 for u in top_users):
        emojis =['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
        for idx, user in enumerate(top_users):
            if _d(user['pulses_today']) > 0:
                username = safe_name(user)
                message += f"{emojis[idx]} @{username}\n   💎 Добыто сегодня: {format_number(user['pulses_today'])}\n   💰 Общий баланс: {format_number(user['balance'])}\n"
                
                db.cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE from_user_id = ? AND transaction_type IN ('donate_to_user','donate_to_bank','reactor_donation') AND DATE(timestamp) = ?", (user['user_id'], today_str))
                donated_today = _d(db.cursor.fetchone()['total'])
                db.cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE from_user_id = ? AND transaction_type IN ('donate_to_user','donate_to_bank','reactor_donation')", (user['user_id'],))
                donated_total = _d(db.cursor.fetchone()['total'])

                if donated_today > 0 or donated_total > 0:
                    message += f"   🎁 Задонатил: сегодня {format_number(donated_today)} / всего {format_number(donated_total)} 💎\n"
                message += "\n"
    else:
        message += "Сегодня еще никто не добывал пульсы.\n"

    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]]))


async def show_top5_menu(query, user):
    keyboard = [[InlineKeyboardButton("🏆 Активисты", callback_data="top5_activists")],[InlineKeyboardButton("💰 Богачи",    callback_data="top5_rich")],[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")],
    ]
    await query.edit_message_text("🏆 ТОП-5\n\nВыберите категорию:", reply_markup=InlineKeyboardMarkup(keyboard))


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

    from config.emojis import ICON_MONEY_BAG_GREEN
    message = "💰 ТОП-5 БОГАЧЕЙ ЧАТА\n\n"
    if top_users:
        emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
        for idx, u_data in enumerate(top_users):
            username = u_data['username'] or u_data['first_name'] or 'Unknown'
            bag = ICON_MONEY_BAG_GREEN if idx == 0 else '💰'
            message += f"{emojis[idx]} @{username}\n   {bag} Баланс: {format_number(u_data['balance'])} 💎\n\n"
    else:
        message += "Пока нет данных."

    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад к ТОП-5", callback_data="menu_top5")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
        ])
    )

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

    
    # ── 1. Сообщений (из chat_stats, фоллбэк на user_stats) ──
    db.cursor.execute('''
        SELECT COALESCE(SUM(total_messages), 0) as count
        FROM chat_stats
        WHERE date >= ? AND date <= ?
    ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    total_messages = int(db.cursor.fetchone()['count'])

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
        SELECT
            COALESCE(SUM(CASE WHEN transaction_type IN ('message_reward','combo_reward','sprint_reward') THEN amount ELSE 0 END), 0) AS earned,
            COALESCE(SUM(CASE WHEN transaction_type = 'message_reward' THEN amount ELSE 0 END), 0) AS base_earned,
            COALESCE(SUM(CASE WHEN transaction_type = 'combo_reward' THEN amount ELSE 0 END), 0) AS combo_earned,
            COALESCE(SUM(CASE WHEN transaction_type = 'sprint_reward' THEN amount ELSE 0 END), 0) AS sprint_earned,
            COALESCE(SUM(CASE WHEN transaction_type = 'penalty_deduct' THEN amount ELSE 0 END), 0) AS penalized
        FROM transactions WHERE timestamp >= ?
    ''', (start_date,))
    r = db.cursor.fetchone()
    _base   = _d(r['base_earned'])
    _combo  = _d(r['combo_earned'])
    _sprint = _d(r['sprint_earned'])
    _penalty = _d(r['penalized'])
    total_pulses = max(_d(r['earned']) - _penalty, Decimal('0'))
    detail_parts = [f"база: {format_number(_base)}"]
    if _combo > 0:
        detail_parts.append(f"комбо: +{format_number(_combo)}")
    if _sprint > 0:
        detail_parts.append(f"спринт: +{format_number(_sprint)}")
    if _penalty > 0:
        detail_parts.append(f"штрафы: -{format_number(_penalty)}")
    stats_message += f"💎 Добыто Пульсов: {format_number(total_pulses)} ({' | '.join(detail_parts)})\n"

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


async def handle_exit_interview(query, data, context, db):
    """Handle exit interview responses."""
    parts      = data.split('_')
    reason     = parts[1]
    user_id    = int(parts[2])

    reason_map = {
        'flood':    'Слишком много флуда',
        'boring':   'Стало скучно',
        'quality':  'Низкое качество',
        'toxic':    'Токсичная атмосфера',
        'admins':   'Действия админов',
        'personal': 'Личное',
    }
    reason_text = reason_map.get(reason, 'Неизвестная причина')

    db.cursor.execute('INSERT INTO exit_interviews (user_id, reason_category) VALUES (?, ?)', (user_id, reason_text))
    db.conn.commit()

    await query.edit_message_text(
        "Спасибо за ответ! Мы учтем это при улучшении чата.\n\n"
        "Если передумаешь - твои Пульсы заморожены на 30 дней. "
        "Просто вернись в чат, и они вернутся к тебе!"
    )

    if reason in ['toxic', 'admins']:
        try:
            user = db.get_user(user_id)
            username = user['username'] or user['first_name']
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"⚠️ ВАЖНОЕ УВЕДОМЛЕНИЕ\n\n"
                    f"Пользователь @{username} покинул чат.\n"
                    f"Причина: {reason_text}\n\n"
                    f"Рекомендуется проверить ситуацию."
                )
            )
        except Exception:
            pass


async def handle_stats_export(query, data, user, context, admin_id):
    """Handle statistics export."""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return

    period = data.split('_')[2]
    keyboard = [
        [InlineKeyboardButton("📗 Excel (.xlsx)", callback_data=f"export_xlsx_{period}")],
        [InlineKeyboardButton("📕 PDF (.pdf)",    callback_data=f"export_pdf_{period}")],
        [InlineKeyboardButton("📄 CSV (.csv)",    callback_data=f"export_csv_{period}")],
        [InlineKeyboardButton("🔙 Назад к статистике", callback_data=f"stats_{period}")],
    ]
    await query.edit_message_text(
        "📊 ЭКСПОРТ СТАТИСТИКИ\n\nВыберите формат для скачивания:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_stats_menu(query, user, admin_id):
    """Show statistics menu (owner only)."""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return

    keyboard = [
        [InlineKeyboardButton("📊 Общая по чату",        callback_data="stats_type_chat")],
        [InlineKeyboardButton("👤 По пользователям",     callback_data="stats_type_users")],
        [InlineKeyboardButton("📈 Чат + пользователи",   callback_data="stats_type_combined")],
        [InlineKeyboardButton("🔙 Назад в меню",         callback_data="back_to_menu")],
    ]
    await query.edit_message_text(
        "📊 СТАТИСТИКА\n\nВыберите тип статистики:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_stats_period_menu(query, data, user, admin_id):
    """Show period selection menu for selected stats type."""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return

    stats_type = data.split('_')[2]
    type_names = {
        'chat':     '📊 Общая по чату',
        'users':    '👤 По пользователям',
        'combined': '📈 Чат + пользователи',
    }
    keyboard = [
        [InlineKeyboardButton("📅 Вчера",  callback_data=f"stats_yesterday_{stats_type}")],
        [InlineKeyboardButton("📅 Сегодня", callback_data=f"stats_day_{stats_type}")],
        [InlineKeyboardButton("📅 Неделя", callback_data=f"stats_week_{stats_type}")],
        [InlineKeyboardButton("📅 Месяц",  callback_data=f"stats_month_{stats_type}")],
        [InlineKeyboardButton("📅 Год",    callback_data=f"stats_year_{stats_type}")],
        [InlineKeyboardButton("🔙 Назад к типам", callback_data="menu_stats")],
    ]
    await query.edit_message_text(
        f"📊 СТАТИСТИКА\n{type_names.get(stats_type, 'Статистика')}\n\nВыберите период:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
