#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание: Меню статистики и выбор периода/формата экспорта.
Функции: show_stats_menu, show_stats_period_menu, handle_stats_export.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def show_stats_menu(query, user, admin_id, back_callback="back_to_menu"):
    """Show statistics menu (owner only)."""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return

    back_label = "🔙 Назад в меню" if back_callback == "back_to_menu" else "🔙 Назад в панель"
    keyboard = [
        [InlineKeyboardButton("📊 Общая по чату",        callback_data="stats_type_chat")],
        [InlineKeyboardButton("👤 По пользователям",     callback_data="stats_type_users")],
        [InlineKeyboardButton("📈 Чат + пользователи",   callback_data="stats_type_combined")],
        [InlineKeyboardButton(back_label,                callback_data=back_callback)],
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
