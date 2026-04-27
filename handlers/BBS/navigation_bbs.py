#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание: Навигационные меню BBS — главное меню и меню знакомств.
Функции: show_bbs_menu, show_dating_menu, handle_bbs_view_profile.
"""

import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

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
        if profile.get('published_at') and not profile.get('deleted_at'):
            keyboard.insert(0, [InlineKeyboardButton("👁 Моя анкета", callback_data="bbs_view_profile")])
            # ── VIP-услуги (доступны только для опубликованной анкеты) ──
            try:
                ib = db.get_vip_settings(code='INSTANT_BUMP')
                rate = float(db.get_setting('pulse_rate', '1.42') or '1.42')
                if rate <= 0:
                    rate = 1.42
                ib_pulses = round(float(ib['price_rub']) / rate, 0) if ib else 35.0
                instant_label = f"🚀 Поднять анкету сейчас ({ib_pulses:.0f} 💎)"
            except Exception:
                instant_label = "🚀 Поднять анкету сейчас"
            keyboard.append([InlineKeyboardButton("💎 Улучшить анкету (VIP)", callback_data="bbs_vip_storefront")])
            keyboard.append([InlineKeyboardButton(instant_label, callback_data="bbs_vip_instant_bump")])
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


async def handle_bbs_view_profile(query, context, db):
    """Показывает пользователю его опубликованную анкету: фото + полный текст."""
    user_id = query.from_user.id
    profile = get_profile(db, user_id)

    if not profile or not profile.get('published_at'):
        await query.answer("У вас нет опубликованной анкеты.", show_alert=True)
        return

    from handlers.BBS.helpers_bbs import build_profile_text
    profile_text = build_profile_text(profile)
    caption = f"👁 <b>ВАША АНКЕТА</b>\n\n{profile_text}"

    chat_id = query.message.chat.id
    photos = json.loads(profile.get('photos', '[]')) if isinstance(profile.get('photos'), str) else (profile.get('photos') or [])

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="bbs_dating")],
    ])

    try:
        if len(photos) == 1:
            await context.bot.send_photo(
                chat_id=chat_id, photo=photos[0],
                caption=caption, parse_mode='HTML',
            )
        elif len(photos) > 1:
            media = [InputMediaPhoto(media=photos[0], caption=caption, parse_mode='HTML')]
            media += [InputMediaPhoto(media=fid) for fid in photos[1:]]
            await context.bot.send_media_group(chat_id=chat_id, media=media)
        else:
            await context.bot.send_message(
                chat_id=chat_id, text=caption + "\n\n⚠️ Фото не загружены.",
                parse_mode='HTML',
            )
    except Exception as e:
        import logging
        logging.error(f"BBS view profile photos error: {e}")

    await context.bot.send_message(
        chat_id=chat_id,
        text="👆 Ваша анкета выглядит так в чате.",
        reply_markup=keyboard,
    )
    await query.answer()
