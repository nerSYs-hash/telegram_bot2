#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание: Диспетчер текстовых/медиа сообщений BBS FSM.
Обрабатывает ввод пользователя на каждом шаге создания и редактирования анкеты.
Функции: process_bbs_input.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.BBS.constants_bbs import BBS, PARAM_OPTIONS, NAME_REGEX
from handlers.BBS.helpers_bbs import (
    get_bbs_state, set_bbs_state, get_bbs_data, parse_age, city_to_hashtag,
)
from handlers.BBS.fsm_steps_bbs import (
    _step_msg, handle_photo_input, handle_name_input, handle_age_input,
    handle_param_value_input, handle_city_custom_input, handle_about_input,
    show_preview,
)
from handlers.BBS.editing_bbs import (
    apply_edit_and_republish, _build_edit_params_keyboard, _build_edit_city_keyboard,
)
from handlers.BBS.fsm_other import process_other_input
from bot_core.workspace_context import pulse_only  # V1.17.0a20 multi-tenancy gating


@pulse_only
async def process_bbs_input(message, context, db):
    """Обработка текстовых/фото сообщений в рамках BBS FSM."""
    if await process_other_input(message, context, db):
        return True

    state = get_bbs_state(context)
    if not state:
        return False

    # ── Создание ──
    if state == BBS.AWAITING_PHOTO:
        await handle_photo_input(message, context)
        return True
    if state == BBS.AWAITING_NAME:
        await handle_name_input(message, context)
        return True
    if state == BBS.AWAITING_AGE:
        await handle_age_input(message, context)
        return True
    if state == BBS.AWAITING_PARAMS:
        if context.user_data.get('bbs_param_editing'):
            await handle_param_value_input(message, context)
        return True
    if state == BBS.AWAITING_CITY_INPUT:
        await handle_city_custom_input(message, context)
        return True
    if state == BBS.AWAITING_ABOUT:
        done = await handle_about_input(message, context)
        if done:
            await show_preview(message, context)
        return True

    # ── Редактирование: фото ──
    if state == BBS.EDIT_PHOTO:
        if message.photo:
            photos = context.user_data.get('bbs_edit_photos', [])
            if len(photos) < 3:
                photos.append(message.photo[-1].file_id)
                context.user_data['bbs_edit_photos'] = photos
                try:
                    await message.delete()
                except Exception:
                    pass
                count = len(photos)
                remaining = 3 - count
                text = f"📷 Загружено: {count}/3."
                text += f" Можете добавить ещё {remaining}." if remaining > 0 else " ✅ Максимум."
                msg_id = context.user_data.get('bbs_bot_msg_id')
                try:
                    if msg_id:
                        await context.bot.edit_message_text(
                            chat_id=message.chat.id, message_id=msg_id, text=text,
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Готово", callback_data="bbs_edit_photo_done")],
                                [InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")],
                            ]),
                        )
                    else:
                        raise Exception("no msg_id")
                except Exception:
                    msg = await context.bot.send_message(
                        chat_id=message.chat.id, text=text,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Готово", callback_data="bbs_edit_photo_done")],[InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")],
                        ]),
                    )
                    context.user_data['bbs_bot_msg_id'] = msg.message_id
            else:
                try:
                    await message.delete()
                except Exception:
                    pass
        return True

    # ── Редактирование: имя ──
    if state == BBS.EDIT_NAME:
        text = (message.text or '').strip()
        if not NAME_REGEX.match(text):
            await _step_msg(message, context, "❌ Только кириллица, 2–30 символов.",
                [[InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")]])
            set_bbs_state(context, BBS.EDIT_NAME)
            return True
        try: await message.delete()
        except Exception: pass
        await apply_edit_and_republish(
            message, context, db, None, None,
            field_name='name', db_column='name', value=text.title(),
        )
        return True

    # ── Редактирование: возраст ──
    if state == BBS.EDIT_AGE:
        text = (message.text or '').strip()
        age = parse_age(text)
        if age is None:
            await _step_msg(message, context, "❌ Введите возраст (18–99) или дату ДД.ММ.ГГГГ.",
                [[InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")]])
            set_bbs_state(context, BBS.EDIT_AGE)
            return True
        try: await message.delete()
        except Exception: pass
        await apply_edit_and_republish(
            message, context, db, None, None,
            field_name='age', db_column='age', value=age,
        )
        return True

    # ── Редактирование: параметры (ввод значения) ──
    if state == BBS.EDIT_PARAMS:
        param_key = context.user_data.get('bbs_edit_param_editing')
        if param_key and param_key in PARAM_OPTIONS:
            text = (message.text or '').strip()
            if not text or len(text) > 20:
                await _step_msg(message, context, "❌ Введите корректное значение (до 20 символов).",
                    [[InlineKeyboardButton("🔙 Назад", callback_data="bbs_eparam_back")]])
                return True
            params = context.user_data.get('bbs_edit_params', {})
            params[param_key] = text
            context.user_data['bbs_edit_params'] = params
            context.user_data['bbs_edit_param_editing'] = None
            await _step_msg(message, context,
                f"✅ {PARAM_OPTIONS[param_key]}: <b>{text}</b>\n\n"
                "Выберите ещё параметр или нажмите <b>«Сохранить»</b>.",
                _build_edit_params_keyboard(params))
        return True

    # ── Редактирование: город (текстовый ввод) ──
    if state == BBS.EDIT_CITY_INPUT:
        text = (message.text or '').strip()
        if not text or len(text) > 50:
            await _step_msg(message, context, "❌ Введите название города (до 50 символов).",
                [[InlineKeyboardButton("🔙 Назад", callback_data="bbs_ecity_back_list")]])
            return True
        tag = city_to_hashtag(text)
        cities = context.user_data.get('bbs_edit_cities', [])
        if tag not in cities:
            cities.append(tag)
        context.user_data['bbs_edit_cities'] = cities
        set_bbs_state(context, BBS.EDIT_CITY)
        await _step_msg(message, context,
            f"✅ Добавлен: <b>{tag}</b>",
            _build_edit_city_keyboard(cities))
        return True

    # ── Редактирование: о себе ──
    if state == BBS.EDIT_ABOUT:
        text = (message.text or '').strip()
        if len(text) > 400:
            await _step_msg(message, context,
                f"❌ Максимум 400 символов ({len(text)}/400).",
                [[InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")]])
            set_bbs_state(context, BBS.EDIT_ABOUT)
            return True
        try: await message.delete()
        except Exception: pass
        await apply_edit_and_republish(
            message, context, db, None, None,
            field_name='about', db_column='about', value=text or None,
        )
        return True

    if state and state.startswith('bbs_'):
        return True

    return False
