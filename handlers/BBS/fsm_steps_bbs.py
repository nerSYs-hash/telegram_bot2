#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FSM-шаги создания анкеты BBS (шаги 1–8).
Единое сообщение бота — обновляется на каждом шаге.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from handlers.BBS.constants_bbs import (
    BBS, PARAM_OPTIONS, ROLE_OPTIONS, GOAL_OPTIONS, NAME_REGEX,
)
from handlers.BBS.helpers_bbs import (
    get_bbs_data, set_bbs_state, parse_age, city_to_hashtag, build_profile_text,
)


# ═══════════════════════════════════════════════════════════════
# ХЕЛПЕР: ОДНО СООБЩЕНИЕ БОТА
# ═══════════════════════════════════════════════════════════════

async def _step_msg(src, context, text, keyboard_rows):
    """Обновляет ОДНО сообщение бота. Удаляет текст пользователя.

    src: CallbackQuery или Message.
    - CallbackQuery → edit_message_text (кнопка нажата)
    - Message → удалить msg пользователя, edit бот-сообщение
    """
    markup = InlineKeyboardMarkup(keyboard_rows)

    if hasattr(src, 'edit_message_text'):
        # CallbackQuery — редактируем сообщение с кнопкой
        await src.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        context.user_data['bbs_bot_msg_id'] = src.message.message_id
        return

    # Message (пользователь набрал текст) — удаляем его, редактируем бот-сообщение
    chat_id = src.chat.id
    try:
        await src.delete()
    except Exception:
        pass

    msg_id = context.user_data.get('bbs_bot_msg_id')
    if msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=text, parse_mode='HTML', reply_markup=markup,
            )
            return
        except Exception:
            pass

    # Fallback — отправить новое
    msg = await context.bot.send_message(
        chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=markup,
    )
    context.user_data['bbs_bot_msg_id'] = msg.message_id


# ═══════════════════════════════════════════════════════════════
# ШАГ 1: ФОТО (1–3)
# ═══════════════════════════════════════════════════════════════

async def start_photo_step(query_or_message, context):
    set_bbs_state(context, BBS.AWAITING_PHOTO)
    data = get_bbs_data(context)
    data['photos'] = []

    text = (
        "📷 <b>Шаг 1/8 — Фото</b>\n\n"
        "Отправьте от 1 до 3 фотографий.\n"
        "Или нажмите «Пропустить».\n"
        "📎 Загружено: 0/3"
    )
    keyboard = [
        [InlineKeyboardButton("⏭ Пропустить", callback_data="bbs_photo_skip")],
        [InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")],
    ]
    await _step_msg(query_or_message, context, text, keyboard)


async def handle_photo_input(message, context):
    data = get_bbs_data(context)

    if not message.photo:
        # Не фото — удаляем и показываем ошибку в том же сообщении
        try:
            await message.delete()
        except Exception:
            pass
        return

    photos = data.get('photos', [])
    if len(photos) >= 3:
        try:
            await message.delete()
        except Exception:
            pass
        return

    photos.append(message.photo[-1].file_id)
    data['photos'] = photos

    try:
        await message.delete()
    except Exception:
        pass

    count = len(photos)
    remaining = 3 - count

    keyboard = []
    if remaining > 0:
        keyboard.append([InlineKeyboardButton("📷 Добавить фото", callback_data="bbs_add_more_photo")])
    keyboard.append([InlineKeyboardButton("➡️ Перейти далее", callback_data="bbs_photo_done")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")])

    text = f"📷 <b>Шаг 1/8 — Фото</b>\n\n📎 Загружено: {count}/3\n"
    text += f"Можете добавить ещё {remaining}." if remaining > 0 else "✅ Максимум загружен."

    msg_id = context.user_data.get('bbs_bot_msg_id')
    if msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=message.chat.id, message_id=msg_id,
                text=text, parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return
        except Exception:
            pass

    msg = await context.bot.send_message(
        chat_id=message.chat.id, text=text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    context.user_data['bbs_bot_msg_id'] = msg.message_id


# ═══════════════════════════════════════════════════════════════
# ШАГ 2: ИМЯ
# ═══════════════════════════════════════════════════════════════

async def start_name_step(src, context):
    set_bbs_state(context, BBS.AWAITING_NAME)
    text = (
        "✍️ <b>Шаг 2/8 — Имя</b>\n\n"
        "Введите ваше имя (только кириллица, 2–30 символов)."
    )
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_photo")],
        [InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")],
    ]
    await _step_msg(src, context, text, keyboard)


async def handle_name_input(message, context):
    text = (message.text or '').strip()
    if not NAME_REGEX.match(text):
        await _step_msg(message, context,
            "❌ Имя должно содержать только кириллицу (2–30 символов).\n\nПопробуйте ещё раз:",
            [[InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_photo")],
             [InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")]])
        set_bbs_state(context, BBS.AWAITING_NAME)
        return
    get_bbs_data(context)['name'] = text.title()
    if context.user_data.get('bbs_tweaking'):
        context.user_data.pop('bbs_tweaking', None)
        await show_preview(message, context)
    else:
        await start_age_step(message, context)


# ═══════════════════════════════════════════════════════════════
# ШАГ 3: ВОЗРАСТ
# ═══════════════════════════════════════════════════════════════

async def start_age_step(src, context):
    set_bbs_state(context, BBS.AWAITING_AGE)
    text = (
        "🎂 <b>Шаг 3/8 — Возраст</b>\n\n"
        "Введите возраст числом (например: <code>25</code>)\n"
        "или дату рождения (<code>15.03.1998</code>).\n\n"
        "Допустимый диапазон: 18–99 лет."
    )
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_name")],
        [InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")],
    ]
    await _step_msg(src, context, text, keyboard)


async def handle_age_input(message, context):
    text = (message.text or '').strip()
    age = parse_age(text)
    if age is None:
        await _step_msg(message, context,
            "❌ Введите число (18–99) или дату ДД.ММ.ГГГГ.\n\nПопробуйте ещё раз:",
            [[InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_name")],
             [InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")]])
        set_bbs_state(context, BBS.AWAITING_AGE)
        return
    get_bbs_data(context)['age'] = age
    if context.user_data.get('bbs_tweaking'):
        context.user_data.pop('bbs_tweaking', None)
        await show_preview(message, context)
    else:
        await start_params_step(message, context)


# ═══════════════════════════════════════════════════════════════
# ШАГ 4: ПАРАМЕТРЫ
# ═══════════════════════════════════════════════════════════════

def build_params_keyboard(params: dict) -> list:
    keyboard = []
    for key, label in PARAM_OPTIONS.items():
        value = params.get(key)
        check = f" ✅ {value}" if value else ""
        keyboard.append([InlineKeyboardButton(f"{label}{check}", callback_data=f"bbs_param_{key}")])

    has_data = any(params.get(k) for k in PARAM_OPTIONS)
    if has_data:
        keyboard.append([InlineKeyboardButton("➡️ Далее", callback_data="bbs_params_done")])
    else:
        keyboard.append([InlineKeyboardButton("⏭ Пропустить", callback_data="bbs_params_skip")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_age")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")])
    return keyboard


async def start_params_step(src, context):
    set_bbs_state(context, BBS.AWAITING_PARAMS)
    data = get_bbs_data(context)
    if 'params' not in data:
        data['params'] = {}
    context.user_data['bbs_param_editing'] = None

    keyboard = build_params_keyboard(data['params'])
    text = (
        "📏 <b>Шаг 4/8 — Параметры</b>\n\n"
        "Нажмите на параметр, затем введите значение.\n"
        "Или нажмите <b>«Пропустить»</b>."
    )
    await _step_msg(src, context, text, keyboard)


async def handle_param_value_input(message, context):
    param_key = context.user_data.get('bbs_param_editing')
    if not param_key:
        return

    text = (message.text or '').strip()
    if not text or len(text) > 20:
        await _step_msg(message, context,
            "❌ Введите корректное значение (до 20 символов).",
            [[InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_params")],
             [InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")]])
        return

    data = get_bbs_data(context)
    data['params'][param_key] = text
    context.user_data['bbs_param_editing'] = None

    keyboard = build_params_keyboard(data['params'])
    await _step_msg(message, context,
        f"✅ {PARAM_OPTIONS[param_key]}: <b>{text}</b>\n\n"
        "Выберите ещё параметр или нажмите <b>«Далее»</b>.",
        keyboard)


# ═══════════════════════════════════════════════════════════════
# ШАГ 5: РОЛЬ
# ═══════════════════════════════════════════════════════════════

def build_role_keyboard(selected: list) -> list:
    keyboard = []
    for role in ROLE_OPTIONS:
        check = "✅ " if role in selected else ""
        keyboard.append([InlineKeyboardButton(f"{check}{role}", callback_data=f"bbs_role_{role}")])
    if selected:
        keyboard.append([InlineKeyboardButton("➡️ Далее", callback_data="bbs_role_done")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_params")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")])
    return keyboard


async def start_role_step(src, context):
    set_bbs_state(context, BBS.AWAITING_ROLE)
    data = get_bbs_data(context)
    if 'roles' not in data:
        data['roles'] = []

    keyboard = build_role_keyboard(data['roles'])
    text = "🎭 <b>Шаг 5/8 — Роль</b>\n\nВыберите одну роль."
    await _step_msg(src, context, text, keyboard)


# ═══════════════════════════════════════════════════════════════
# ШАГ 6: ГОРОД
# ═══════════════════════════════════════════════════════════════

def build_city_keyboard(selected: list) -> list:
    presets = [('Санкт-Петербург', '#Спб'), ('Москва', '#Мск')]
    keyboard = []
    for label, tag in presets:
        check = "✅ " if tag in selected else ""
        keyboard.append([InlineKeyboardButton(f"{check}{label}", callback_data=f"bbs_city_{tag}")])
    keyboard.append([InlineKeyboardButton("🏙 Другой город", callback_data="bbs_city_custom")])
    keyboard.append([InlineKeyboardButton("➡️ Далее", callback_data="bbs_city_done")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_role")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")])
    return keyboard


async def start_city_step(src, context):
    set_bbs_state(context, BBS.AWAITING_CITY)
    data = get_bbs_data(context)
    if 'city' not in data:
        data['city'] = []

    keyboard = build_city_keyboard(data['city'])
    text = "🏙 <b>Шаг 6/8 — Город</b>\n\nВыберите город или введите свой."
    await _step_msg(src, context, text, keyboard)


async def handle_city_custom_input(message, context):
    text = (message.text or '').strip()
    if not text or len(text) > 50:
        await _step_msg(message, context,
            "❌ Введите название города (до 50 символов).",
            [[InlineKeyboardButton("🔙 Назад", callback_data="bbs_city_back")],
             [InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")]])
        return

    tag = city_to_hashtag(text)
    data = get_bbs_data(context)
    if tag not in data['city']:
        data['city'].append(tag)

    set_bbs_state(context, BBS.AWAITING_CITY)
    keyboard = build_city_keyboard(data['city'])
    await _step_msg(message, context,
        f"✅ Добавлен: <b>{tag}</b>\n\nВыберите ещё или нажмите <b>«Далее»</b>.",
        keyboard)


# ═══════════════════════════════════════════════════════════════
# ШАГ 7: ЦЕЛЬ
# ═══════════════════════════════════════════════════════════════

def build_goal_keyboard(selected: list) -> list:
    keyboard = []
    for goal in GOAL_OPTIONS:
        check = "✅ " if goal in selected else ""
        keyboard.append([InlineKeyboardButton(f"{check}{goal}", callback_data=f"bbs_goal_{goal}")])
    keyboard.append([InlineKeyboardButton("➡️ Далее", callback_data="bbs_goal_done")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_city")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")])
    return keyboard


async def start_goal_step(src, context):
    set_bbs_state(context, BBS.AWAITING_GOAL)
    data = get_bbs_data(context)
    if 'goals' not in data:
        data['goals'] = []

    keyboard = build_goal_keyboard(data['goals'])
    text = "🎯 <b>Шаг 7/8 — Цель</b>\n\nВыберите одну или несколько целей."
    await _step_msg(src, context, text, keyboard)


# ═══════════════════════════════════════════════════════════════
# ШАГ 8: О СЕБЕ
# ═══════════════════════════════════════════════════════════════

async def start_about_step(src, context):
    set_bbs_state(context, BBS.AWAITING_ABOUT)
    text = (
        "💬 <b>Шаг 8/8 — О себе</b>\n\n"
        "Напишите немного о себе (до 400 символов).\n"
        "Или нажмите <b>«Пропустить»</b>."
    )
    keyboard = [
        [InlineKeyboardButton("⏭ Пропустить", callback_data="bbs_about_skip")],
        [InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_goal")],
        [InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")],
    ]
    await _step_msg(src, context, text, keyboard)


async def handle_about_input(message, context):
    text = (message.text or '').strip()
    if len(text) > 400:
        await _step_msg(message, context,
            f"❌ Слишком длинный текст ({len(text)}/400). Сократите.",
            [[InlineKeyboardButton("⏭ Пропустить", callback_data="bbs_about_skip")],
             [InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")]])
        set_bbs_state(context, BBS.AWAITING_ABOUT)
        return

    get_bbs_data(context)['about'] = text if text else None
    context.user_data.pop('bbs_tweaking', None)
    return True


# ═══════════════════════════════════════════════════════════════
# ПРЕДПРОСМОТР
# ═══════════════════════════════════════════════════════════════

async def show_preview(message_or_query, context):
    """Превью: фото + текст + кнопки на отдельном сообщении."""
    data = get_bbs_data(context)
    photos = data.get('photos', [])
    profile_text = build_profile_text(data)
    preview_caption = f"👀 <b>ПРЕДПРОСМОТР</b>\n\n{profile_text}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Опубликовать", callback_data="bbs_publish")],
        [InlineKeyboardButton("✏️ Доработать",   callback_data="bbs_tweak")],
        [InlineKeyboardButton("❌ Отмена",        callback_data="bbs_cancel")],
    ])

    # Удаляем предыдущее бот-сообщение (шаговое)
    if hasattr(message_or_query, 'message'):
        chat_id = message_or_query.message.chat.id
    else:
        chat_id = message_or_query.chat.id

    old_msg_id = context.user_data.pop('bbs_bot_msg_id', None)
    if old_msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
        except Exception:
            pass

    # Удаляем сообщение-источник (если это текстовый ввод)
    if not hasattr(message_or_query, 'message'):
        try:
            await message_or_query.delete()
        except Exception:
            pass

    try:
        if len(photos) == 1:
            if len(preview_caption) <= 1024:
                await context.bot.send_photo(
                    chat_id=chat_id, photo=photos[0],
                    caption=preview_caption, parse_mode='HTML',
                )
            else:
                await context.bot.send_photo(chat_id=chat_id, photo=photos[0])
                await context.bot.send_message(
                    chat_id=chat_id, text=preview_caption, parse_mode='HTML',
                )
        elif len(photos) > 1:
            if len(preview_caption) <= 1024:
                media = [InputMediaPhoto(media=photos[0], caption=preview_caption, parse_mode='HTML')]
            else:
                media = [InputMediaPhoto(media=photos[0])]
            media += [InputMediaPhoto(media=fid) for fid in photos[1:]]
            await context.bot.send_media_group(chat_id=chat_id, media=media)
            if len(preview_caption) > 1024:
                await context.bot.send_message(
                    chat_id=chat_id, text=preview_caption, parse_mode='HTML',
                )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=preview_caption + "\n\n⚠️ Фото не загружены.",
                parse_mode='HTML',
            )
    except Exception as e:
        logging.error(f"BBS preview photos error: {e}")
        await context.bot.send_message(
            chat_id=chat_id, text=preview_caption, parse_mode='HTML',
        )

    # Кнопки — на отдельном сообщении (чтобы edit работал)
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text="👆 Всё верно? Нажмите кнопку ниже.",
        reply_markup=keyboard,
    )
    context.user_data['bbs_bot_msg_id'] = msg.message_id
