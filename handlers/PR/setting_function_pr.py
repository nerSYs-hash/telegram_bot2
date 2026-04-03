#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Настройки бота и управление функциями.

Путь: handlers/PR/setting_function_pr.py

Все функции — модульного уровня (без класса).
db, admin_id передаются явно.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import format_number


# ═══════════════════════════════════════════════════════════════
# НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════════

async def show_settings(query, user, db, admin_id):
    """Show settings (owner only)"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return

    reactor_balance = int(float(db.get_setting('reactor_balance', 0)))
    reactor_goal = int(float(db.get_setting('reactor_goal', 10000)))

    message = f"⚙️ НАСТРОЙКИ БОТА\n\n"
    message += f"🔋 Реактор: {format_number(reactor_balance)} / {format_number(reactor_goal)}\n"
    message += f"📊 Прогресс: {(reactor_balance/reactor_goal)*100:.1f}%"

    keyboard = [
        [InlineKeyboardButton("🔧 Управление функциями", callback_data="manage_features")],
        [InlineKeyboardButton("📰 Пресс-релиз", callback_data="press_release_start")],
        [InlineKeyboardButton("🔮 Гороскоп", callback_data="horoscope_menu")],
        [InlineKeyboardButton("📋 Правила", url="https://t.me/c/3153855971/13")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup)


# ═══════════════════════════════════════════════════════════════
# УПРАВЛЕНИЕ ФУНКЦИЯМИ
# ═══════════════════════════════════════════════════════════════

async def show_features_management(query, user, db, admin_id):
    """Show features management menu (owner only)"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return

    features = [
        ('👤 Личный кабинет (Профиль)', 'profile'),
        ('📊 Статистика', 'statistics'),
        ('🏆 ТОП-5 и команды', 'top'),
        ('🏦 Центробанк', 'bank'),
        ('🎯 Активности', 'activities'),
        ('📋 Детализация', 'detalization'),
        ('🎰 Лотерея', 'lottery'),
        ('🎱 Бинго', 'bingo'),
        ('👥 Рефералы', 'referral'),
        ('🎁 Донаты', 'donate'),
        ('🎁 Подарок Месяца', 'monthly_gift'),
        ('🔮 Гороскоп', 'horoscope'),
        ('❣️ Pulse BBS', 'bbs'),
        ('📦 BBS: Другое', 'bbs_other'),
        ('✏️ Ред. анкет BBS', 'bbs_edit'),
        ('📝 Регистрация новых участников', 'registration'),
    ]

    message = "🔧 УПРАВЛЕНИЕ ФУНКЦИЯМИ\n\n"
    message += "Используйте переключатели справа:\n"

    keyboard = []

    for feature_name, feature_id in features:
        is_enabled = db.is_feature_enabled(feature_id)
        # Объединённый переключатель: показываем Вкл только если обе части активны
        if feature_id == 'top':
            is_enabled = is_enabled and db.is_feature_enabled('top_commands')

        if is_enabled:
            toggle_btn = InlineKeyboardButton("🟢 Вкл", callback_data=f"feature_off_{feature_id}")
        else:
            toggle_btn = InlineKeyboardButton("🔴 Выкл", callback_data=f"feature_on_{feature_id}")

        keyboard.append([
            InlineKeyboardButton(feature_name, callback_data="feature_info"),
            toggle_btn
        ])

    keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)


async def toggle_feature(query, data, user, db, admin_id):
    """Toggle feature on/off with separate buttons"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return

    parts = data.split('_', 2)
    action = parts[1]
    feature_id = parts[2]

    if action == 'on':
        db.set_setting(f'feature_{feature_id}', '1')
        if feature_id == 'top':
            db.set_setting('feature_top_commands', '1')
        await query.answer("✅ Функция включена!", show_alert=False)
    elif action == 'off':
        db.set_setting(f'feature_{feature_id}', '0')
        if feature_id == 'top':
            db.set_setting('feature_top_commands', '0')
        await query.answer("❌ Функция отключена!", show_alert=False)

    await show_features_management(query, user, db, admin_id)
