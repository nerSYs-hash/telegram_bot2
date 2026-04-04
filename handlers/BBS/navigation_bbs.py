#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание: Навигационные меню BBS — главное меню и меню знакомств.
Функции: show_bbs_menu, show_dating_menu.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.BBS.constants_bbs import EDITABLE_FIELDS
from handlers.BBS.database_bbs import get_profile
from handlers.BBS.editing_bbs import get_edited_fields


async def show_bbs_menu(update_or_query, context, db):
    keyboard = [
        [InlineKeyboardButton("💘 Знакомства", callback_data="bbs_dating")],
    ]
    if db.is_feature_enabled('bbs_other'):
        keyboard.append([InlineKeyboardButton("📦 Другое", callback_data="bbs_other_stub")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    text = "📋 <b>Pulse BBS</b>\n\nВыберите раздел:"
    if hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def show_dating_menu(query, context, db, user_id):
    profile = get_profile(db, user_id)
    keyboard = [[InlineKeyboardButton("📝 Разместить анкету", callback_data="bbs_create_start")]]
    if profile:
        keyboard.append([InlineKeyboardButton("🗑 Удалить анкету", callback_data="bbs_delete_confirm")])
        if profile.get('published_at') and db.is_feature_enabled('bbs_edit'):
            edited = get_edited_fields(profile)
            if len(edited) < len(EDITABLE_FIELDS):
                keyboard.insert(1, [InlineKeyboardButton(
                    "✏️ Редактировать анкету", callback_data="bbs_edit_start"
                )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_bbs")])
    text = "💘 <b>Знакомства</b>\n\n"
    text += "У вас есть анкета (опубликована).\n" if profile else "У вас пока нет анкеты.\n"
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
