#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание: Callback-диспетчер BBS — обрабатывает все inline-кнопки с префиксами
bbs_*, menu_bbs. Маршрутизирует нажатия: навигация, создание анкеты,
редактирование полей, публикация, удаление.
Функции: handle_bbs_callback.
"""

import json
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from utils.helpers import get_moscow_time

from handlers.BBS.constants_bbs import BBS, PARAM_OPTIONS, EDITABLE_FIELDS
from handlers.BBS.helpers_bbs import (
    get_bbs_state, set_bbs_state, get_bbs_data, clear_bbs, build_profile_text,
)
from handlers.BBS.database_bbs import get_profile
from handlers.BBS.fsm_other import handle_other_callback
from handlers.BBS.fsm_steps_bbs import (
    start_photo_step, start_name_step, start_age_step,
    start_params_step, build_params_keyboard, start_role_step, build_role_keyboard,
    start_city_step, build_city_keyboard, start_goal_step, build_goal_keyboard,
    start_about_step, show_preview,
)
from handlers.BBS.publishing_bbs import publish_profile, delete_profile_messages, update_profile_in_place
from handlers.BBS.editing_bbs import (
    apply_edit_and_republish, get_edited_fields, _build_edit_menu_keyboard,
    _build_edit_params_keyboard, _build_edit_role_keyboard,
    _build_edit_city_keyboard, _build_edit_goal_keyboard,
)
from handlers.BBS.navigation_bbs import show_bbs_menu, show_dating_menu, handle_bbs_view_profile
from bot_core.workspace_context import pulse_only  # V1.17.0a20 multi-tenancy gating


@pulse_only
async def handle_bbs_callback(query, context, db, target_chat_id, bbs_thread_id):
    data = query.data
    user_id = query.from_user.id

    handled_other = await handle_other_callback(query, context, db, target_chat_id, bbs_thread_id)
    if handled_other:
        return True

    # ── Навигация ──
    if data == 'menu_bbs':
        clear_bbs(context)
        await show_bbs_menu(query, context, db)
        return True
    if data == 'bbs_dating':
        clear_bbs(context)
        await show_dating_menu(query, context, db, user_id)
        return True
    if data == 'bbs_view_profile':
        await handle_bbs_view_profile(query, context, db)
        return True
    # ── Отмена ──
    if data == 'bbs_cancel':
        clear_bbs(context)
        await query.edit_message_text(
            "❌ Создание анкеты отменено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="menu_bbs")]
            ]),
        )
        return True

    # ── Создание ──
    if data == 'bbs_create_start':
        # Проверка 24ч до начала создания
        existing = get_profile(db, user_id)
        if existing and existing.get('published_at'):
            try:
                from utils.helpers import get_moscow_time
                published = datetime.fromisoformat(existing['published_at'])
                elapsed = (get_moscow_time().replace(tzinfo=None) - published).total_seconds()
                if elapsed < 86400:
                    hours_left = int((86400 - elapsed) / 3600)
                    mins_left  = int(((86400 - elapsed) % 3600) / 60)
                    await query.edit_message_text(
                        f"⏳ <b>Создание недоступно</b>\n\n"
                        f"Повторная публикация возможна через "
                        f"<b>{hours_left}ч {mins_left}мин</b>.\n\n"
                        f"❗️Функционал в разработке следи за новостями.",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Редактировать", callback_data="bbs_edit_start")],[InlineKeyboardButton("🔙 Назад", callback_data="bbs_dating")],
                        ]),
                    )
                    return True
            except Exception:
                pass
        # Показываем правила перед созданием
        rules_text = (
            "⚠️ <b>Правила Pulse BBS</b>\n\n"
            "🔸 Доска предназначена для некоммерческих и личных объявлений.\n\n"
            "🔸 Знакомства (дружба, общение, отношения и т.д.).\n\n"
            "🔸 Встречи по интересам (компания в кино, настолки, хобби, спорт).\n\n"
            "🔸 Продажа/дар личных вещей (одежда, техника, книги). "
            "Коммерческая деятельность запрещена без согласования с администрацией.\n\n"
            "🔸 Объявления должны соответствовать законодательству РФ.\n\n"
            "🔸 Все интимные части тела должны быть скрыты. Никакой эротики и порно!\n\n"
            "🔸 Нарушающие правила объявления будут удалены с выдачей предупреждений."
        )
        await query.edit_message_text(
            rules_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Согласен", callback_data="bbs_rules_agree")],
                [InlineKeyboardButton("❌ Не согласен", callback_data="bbs_rules_decline")],
            ]),
        )
        return True

    if data == 'bbs_rules_agree':
        clear_bbs(context)
        await start_photo_step(query, context)
        return True

    if data == 'bbs_rules_decline':
        # 1. Удаляем сообщение с правилами, чтобы сработал эффект
        try:
            await query.message.delete()
        except Exception:
            pass

        # 2. Отправляем сообщение об отказе с эффектом на весь экран!
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text="❌ <b>Вы не согласились с правилами.</b>\n\nСоздание анкеты отменено. Возвращайтесь, когда передумаете! 😉",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В меню BBS", callback_data="menu_bbs")]
            ])
        )
        return True

    # ── Фото ──
    if data == 'bbs_photo_done':
        if not get_bbs_data(context).get('photos'):
            await query.answer("❌ Добавьте хотя бы 1 фото", show_alert=True)
            return True
        context.user_data.pop('bbs_bot_msg_id', None)
        if context.user_data.get('bbs_tweaking'):
            context.user_data.pop('bbs_tweaking', None)
            await show_preview(query, context)
        else:
            await start_name_step(query, context)
        return True
    if data == 'bbs_add_more_photo':
        await query.answer("📷 Отправьте следующее фото")
        return True
    if data == 'bbs_photo_skip':
        get_bbs_data(context)['photos'] = []
        context.user_data.pop('bbs_bot_msg_id', None)
        if context.user_data.get('bbs_tweaking'):
            context.user_data.pop('bbs_tweaking', None)
            await show_preview(query, context)
        else:
            await start_name_step(query, context)
        return True

    # ── Параметры ──
    if data.startswith('bbs_param_'):
        param_key = data.replace('bbs_param_', '')
        if param_key in PARAM_OPTIONS:
            context.user_data['bbs_param_editing'] = param_key
            await query.edit_message_text(
                f"✍️ Введите значение для <b>{PARAM_OPTIONS[param_key]}</b>:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="bbs_back_to_params")],[InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")],
                ]),
            )
        return True
    if data == 'bbs_params_done':
        if context.user_data.get('bbs_tweaking'):
            context.user_data.pop('bbs_tweaking', None)
            await show_preview(query, context)
        else:
            await start_role_step(query, context)
        return True
    if data == 'bbs_params_skip':
        get_bbs_data(context)['params'] = {}
        if context.user_data.get('bbs_tweaking'):
            context.user_data.pop('bbs_tweaking', None)
            await show_preview(query, context)
        else:
            await start_role_step(query, context)
        return True
    if data == 'bbs_back_to_params':
        context.user_data['bbs_param_editing'] = None
        await start_params_step(query, context)
        return True

    # ── Кнопки «Назад» между шагами ──
    if data == 'bbs_back_to_photo':
        set_bbs_state(context, BBS.AWAITING_PHOTO)
        photos = get_bbs_data(context).get('photos', [])
        count = len(photos)
        remaining = 3 - count
        if count > 0:
            text = f"📷 <b>Шаг 1/8 — Фото</b>\n\n📎 Загружено: {count}/3\n"
            text += f"Можете добавить ещё {remaining}." if remaining > 0 else "✅ Максимум."
            keyboard = []
            if remaining > 0:
                keyboard.append([InlineKeyboardButton("📷 Добавить фото", callback_data="bbs_add_more_photo")])
            keyboard.append([InlineKeyboardButton("➡️ Далее", callback_data="bbs_photo_done")])
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")])
        else:
            text = "📷 <b>Шаг 1/8 — Фото</b>\n\nОтправьте от 1 до 3 фотографий.\n📎 Загружено: 0/3"
            keyboard = [
                [InlineKeyboardButton("⏭ Пропустить", callback_data="bbs_photo_skip")],
                [InlineKeyboardButton("❌ Отмена", callback_data="bbs_cancel")],
            ]
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return True
    if data == 'bbs_back_to_name':
        await start_name_step(query, context)
        return True
    if data == 'bbs_back_to_age':
        await start_age_step(query, context)
        return True
    if data == 'bbs_back_to_role':
        await start_role_step(query, context)
        return True
    if data == 'bbs_back_to_city':
        await start_city_step(query, context)
        return True
    if data == 'bbs_back_to_goal':
        await start_goal_step(query, context)
        return True

    # ── Роли ──
    if data.startswith('bbs_role_') and data != 'bbs_role_done':
        role = data.replace('bbs_role_', '')
        bbs_data = get_bbs_data(context)
        # Одиночный выбор: просто заменяем предыдущую роль
        if bbs_data.get('roles') == [role]:
            bbs_data['roles'] = []   # повторный тап — снять выбор
        else:
            bbs_data['roles'] = [role]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(build_role_keyboard(bbs_data['roles'])))
        return True
    if data == 'bbs_role_done':
        if not get_bbs_data(context).get('roles'):
            await query.answer("❌ Выберите хотя бы одну роль", show_alert=True)
            return True
        if context.user_data.get('bbs_tweaking'):
            context.user_data.pop('bbs_tweaking', None)
            await show_preview(query, context)
        else:
            await start_city_step(query, context)
        return True

    # ── Города (создание) ──
    if data.startswith('bbs_city_') and data not in ('bbs_city_done', 'bbs_city_custom'):
        tag = data.replace('bbs_city_', '')
        bbs_data = get_bbs_data(context)
        cities = bbs_data.get('city', [])
        if tag in cities:
            cities.remove(tag)
        else:
            cities.append(tag)
        bbs_data['city'] = cities
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(build_city_keyboard(cities)))
        return True
    if data == 'bbs_city_custom':
        set_bbs_state(context, BBS.AWAITING_CITY_INPUT)
        await query.edit_message_text(
            "🏙 Введите название вашего города:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="bbs_city_back")]
            ]),
        )
        return True
    if data == 'bbs_city_back':
        set_bbs_state(context, BBS.AWAITING_CITY)
        cities = get_bbs_data(context).get('city', [])
        await query.edit_message_text(
            "🏙 <b>Шаг 6/8 — Город</b>\n\nВыберите город или введите свой.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(build_city_keyboard(cities)),
        )
        return True
    if data == 'bbs_city_done':
        if not get_bbs_data(context).get('city'):
            await query.answer("❌ Выберите хотя бы один город", show_alert=True)
            return True
        if context.user_data.get('bbs_tweaking'):
            context.user_data.pop('bbs_tweaking', None)
            await show_preview(query, context)
        else:
            await start_goal_step(query, context)
        return True

    # ── Цели (создание) ──
    if data.startswith('bbs_goal_') and data != 'bbs_goal_done':
        goal = data.replace('bbs_goal_', '')
        bbs_data = get_bbs_data(context)
        goals = bbs_data.get('goals', [])
        if goal in goals:
            goals.remove(goal)
        else:
            goals.append(goal)
        bbs_data['goals'] = goals
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(build_goal_keyboard(goals)))
        return True
    if data == 'bbs_goal_done':
        if not get_bbs_data(context).get('goals'):
            await query.answer("❌ Выберите хотя бы одну цель", show_alert=True)
            return True
        if context.user_data.get('bbs_tweaking'):
            context.user_data.pop('bbs_tweaking', None)
            await show_preview(query, context)
        else:
            await start_about_step(query, context)
        return True

    # ── О себе: пропуск (отключён — поле обязательное) ──
    if data == 'bbs_about_skip':
        await query.answer("❌ Поле «О себе» обязательно для заполнения.", show_alert=True)
        return True

    # ── Доработка анкеты (из превью) ──
    if data == 'bbs_tweak':
        bbs_data = get_bbs_data(context)
        fields = [
            ('📷 Фото',       'photo'),
            ('✍️ Имя',        'name'),
            ('🎂 Возраст',    'age'),
            ('📏 Параметры',  'params'),
            ('🎭 Роль',       'role'),
            ('🏙 Город',      'city'),
            ('🎯 Цель',       'goal'),
            ('💬 О себе',     'about'),
        ]
        keyboard = []
        for label, key in fields:
            keyboard.append([InlineKeyboardButton(label, callback_data=f"bbs_tweak_{key}")])
        keyboard.append([InlineKeyboardButton("🔙 К превью", callback_data="bbs_back_to_preview")])
        await query.edit_message_text(
            "✏️ <b>Доработать анкету</b>\n\nВыберите что хотите изменить:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return True

    if data == 'bbs_back_to_preview':
        await show_preview(query, context)
        return True

    if data.startswith('bbs_tweak_'):
        field = data.replace('bbs_tweak_', '')
        context.user_data['bbs_tweaking'] = True
        if field == 'photo':
            await start_photo_step(query, context)
        elif field == 'name':
            await start_name_step(query, context)
        elif field == 'age':
            await start_age_step(query, context)
        elif field == 'params':
            await start_params_step(query, context)
        elif field == 'role':
            await start_role_step(query, context)
        elif field == 'city':
            await start_city_step(query, context)
        elif field == 'goal':
            await start_goal_step(query, context)
        elif field == 'about':
            await start_about_step(query, context)
        return True

    # ── Публикация ──
    if data == 'bbs_publish':
        await publish_profile(query, context, db, target_chat_id, bbs_thread_id)
        return True

    # ── Удаление ──
    if data == 'bbs_delete_confirm':
        profile = get_profile(db, user_id)
        if not profile:
            await query.answer("У вас нет анкеты.", show_alert=True)
            return True

        # Показываем краткую сводку анкеты которую удаляем
        try:
            from handlers.BBS.helpers_bbs import build_profile_text
            preview = build_profile_text(profile)
        except Exception:
            preview = f"{profile.get('name', '?')}, {profile.get('age', '?')}"

        await query.edit_message_text(
            f"🗑 <b>Удалить анкету?</b>\n\n"
            f"{preview}\n\n"
            f"⚠️ Это действие нельзя отменить.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Да, удалить", callback_data="bbs_delete_yes")],[InlineKeyboardButton("🔙 Назад",       callback_data="bbs_dating")],
            ]),
        )
        return True
    if data == 'bbs_delete_yes':
        profile = get_profile(db, user_id)
        if profile:
            await delete_profile_messages(context.bot, db, profile, target_chat_id, profile.get('thread_id'), deleted_by='user')
            await query.edit_message_text(
                "✅ Анкета удалена.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="menu_bbs")]
                ]),
            )
        else:
            await query.answer("У вас нет анкеты.", show_alert=True)
        return True

    # ═══════════════════════════════════════════════════════════
    # РЕДАКТИРОВАНИЕ (каждое поле — 1 раз за 24ч)
    # ═══════════════════════════════════════════════════════════

    if data == 'bbs_edit_start':
        if not db.is_feature_enabled('bbs_edit'):
            await query.answer("✏️ Редактирование анкет временно отключено.", show_alert=True)
            return True

        set_bbs_state(context, BBS.EDIT_CHOOSE_FIELD)
        context.user_data.pop('bbs_param_editing', None)
        context.user_data.pop('bbs_edit_param_editing', None)

        profile = get_profile(db, user_id)
        if not profile or not profile.get('published_at'):
            await query.answer("Редактирование недоступно.", show_alert=True)
            return True

        context.user_data['bbs_editing_profile_id'] = profile['id']
        context.user_data['bbs_edit_chat_id'] = target_chat_id
        context.user_data['bbs_edit_thread_id'] = bbs_thread_id

        edited = get_edited_fields(profile)
        keyboard_rows = _build_edit_menu_keyboard(edited)
        remaining = len(EDITABLE_FIELDS) - len(edited)

        await query.edit_message_text(
            f"✏️ <b>Редактирование анкеты</b>\n\n"
            f"Каждое поле — <b>1 раз за 24ч</b>.\n"
            f"Доступно изменений: <b>{remaining}</b> из {len(EDITABLE_FIELDS)}.\n"
            f"🔒 — изменено, снова доступно через 24ч.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
        )
        return True

    if data == 'bbs_noop':
        await query.answer("✅ Это поле уже было отредактировано.", show_alert=True)
        return True

    # ── Выбор поля для редактирования ──
    if data.startswith('bbs_edit_field_'):
        field = data.replace('bbs_edit_field_', '')
        profile = get_profile(db, user_id)
        if not profile:
            await query.answer("Анкета не найдена.", show_alert=True)
            return True
        edited = get_edited_fields(profile)
        if field in edited:
            await query.answer("Это поле уже было отредактировано.", show_alert=True)
            return True

        context.user_data['bbs_editing_profile_id'] = profile['id']
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")]
        ])

        if field == 'photo':
            set_bbs_state(context, BBS.EDIT_PHOTO)
            context.user_data['bbs_edit_photos'] = []
            cur_photos = json.loads(profile.get('photos') or '[]')
            await query.edit_message_text(
                f"📷 <b>Фото</b>\n\nТекущее: <b>{len(cur_photos)} фото</b>\n\nОтправьте новые фото (1–3), затем нажмите «Готово».",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Готово", callback_data="bbs_edit_photo_done")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")],
                ]),
            )
        elif field == 'name':
            set_bbs_state(context, BBS.EDIT_NAME)
            cur = profile.get('name') or '—'
            await query.edit_message_text(
                f"✍️ <b>Имя</b>\n\nТекущее: <b>{cur}</b>\n\nВведите новое имя (кириллица, 2–30 символов):",
                parse_mode='HTML',
                reply_markup=back_kb,
            )
        elif field == 'age':
            set_bbs_state(context, BBS.EDIT_AGE)
            cur = str(profile.get('age') or '—')
            await query.edit_message_text(
                f"🎂 <b>Возраст</b>\n\nТекущее: <b>{cur}</b>\n\nВведите новый возраст или дату рождения (ДД.ММ.ГГГГ):",
                parse_mode='HTML',
                reply_markup=back_kb,
            )
        elif field == 'params':
            set_bbs_state(context, BBS.EDIT_PARAMS)
            params = json.loads(profile.get('params') or '{}')
            context.user_data['bbs_edit_params'] = params
            context.user_data['bbs_edit_param_editing'] = None
            cur_parts = [f"{k}: {v}" for k, v in params.items() if v]
            cur = ', '.join(cur_parts) if cur_parts else '—'
            await query.edit_message_text(
                f"📏 <b>Параметры</b>\n\nТекущие: <code>{cur}</code>\n\nНажмите на параметр для изменения.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(_build_edit_params_keyboard(params)),
            )
        elif field == 'role':
            set_bbs_state(context, BBS.EDIT_ROLE)
            roles = json.loads(profile.get('roles') or '[]')
            context.user_data['bbs_edit_roles'] = roles
            cur = ', '.join(roles) if roles else '—'
            await query.edit_message_text(
                f"🎭 <b>Роль</b>\n\nТекущая: <b>{cur}</b>\n\nВыберите новую роль (сохранится сразу):",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(_build_edit_role_keyboard(roles)),
            )
        elif field == 'city':
            set_bbs_state(context, BBS.EDIT_CITY)
            cities = json.loads(profile.get('city') or '[]')
            context.user_data['bbs_edit_cities'] = cities
            cur = ', '.join(cities) if cities else '—'
            await query.edit_message_text(
                f"🏙 <b>Город</b>\n\nТекущие: <code>{cur}</code>\n\nВыберите город или введите свой:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(_build_edit_city_keyboard(cities)),
            )
        elif field == 'goal':
            set_bbs_state(context, BBS.EDIT_GOAL)
            goals = json.loads(profile.get('goals') or '[]')
            context.user_data['bbs_edit_goals'] = goals
            cur = ', '.join(goals) if goals else '—'
            await query.edit_message_text(
                f"🎯 <b>Цель</b>\n\nТекущие: <code>{cur}</code>\n\nВыберите новые цели:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(_build_edit_goal_keyboard(goals)),
            )
        elif field == 'about':
            set_bbs_state(context, BBS.EDIT_ABOUT)
            cur = profile.get('about') or '—'
            await query.edit_message_text(
                f"💬 <b>О себе</b>\n\nТекущее:\n<i>{cur}</i>\n\nВведите новый текст (до 400 символов):",
                parse_mode='HTML',
                reply_markup=back_kb,
            )
        return True

    # ── Edit: фото готово ──
    if data == 'bbs_edit_photo_done':
        photos = context.user_data.get('bbs_edit_photos', [])
        if not photos:
            await query.answer("❌ Добавьте хотя бы 1 фото", show_alert=True)
            return True
        await apply_edit_and_republish(
            query, context, db, target_chat_id, bbs_thread_id,
            field_name='photo', db_column='photos', value=json.dumps(photos),
        )
        return True

    # ── Edit: параметры ──
    if data.startswith('bbs_eparam_') and data not in ('bbs_eparam_done', 'bbs_eparam_back'):
        param_key = data.replace('bbs_eparam_', '')
        if param_key in PARAM_OPTIONS:
            context.user_data['bbs_edit_param_editing'] = param_key
            await query.edit_message_text(
                f"✍️ Введите значение для <b>{PARAM_OPTIONS[param_key]}</b>:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="bbs_eparam_back")]
                ]),
            )
        return True
    if data == 'bbs_eparam_back':
        context.user_data['bbs_edit_param_editing'] = None
        params = context.user_data.get('bbs_edit_params', {})
        await query.edit_message_text(
            "📏 <b>Редактирование параметров</b>\n\nНажмите на параметр для изменения.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(_build_edit_params_keyboard(params)),
        )
        return True
    if data == 'bbs_eparam_done':
        params = context.user_data.get('bbs_edit_params', {})
        await apply_edit_and_republish(
            query, context, db, target_chat_id, bbs_thread_id,
            field_name='params', db_column='params', value=json.dumps(params),
        )
        return True

    # ── Edit: роли (ИЗМЕНЕНО НА ОДИНОЧНЫЙ ВЫБОР С МОМЕНТАЛЬНЫМ СОХРАНЕНИЕМ) ──
    if data.startswith('bbs_erole_'):
        # Если случайно кто-то нажмет на старую кнопку "done", просим выбрать роль
        if data == 'bbs_erole_done':
            await query.answer("Выберите роль из списка выше.", show_alert=True)
            return True

        role = data.replace('bbs_erole_', '')
        roles = [role]  # Одиночный выбор
        context.user_data['bbs_edit_roles'] = roles

        # Сразу сохраняем и обновляем анкету
        await apply_edit_and_republish(
            query, context, db, target_chat_id, bbs_thread_id,
            field_name='role', db_column='roles', value=json.dumps(roles),
        )
        return True

    # ── Edit: город ──
    if data.startswith('bbs_ecity_') and data not in ('bbs_ecity_done', 'bbs_ecity_custom', 'bbs_ecity_back_list'):
        tag = data.replace('bbs_ecity_', '')
        cities = context.user_data.get('bbs_edit_cities', [])
        if tag in cities:
            cities.remove(tag)
        else:
            cities.append(tag)
        context.user_data['bbs_edit_cities'] = cities
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(_build_edit_city_keyboard(cities))
        )
        return True
    if data == 'bbs_ecity_custom':
        set_bbs_state(context, BBS.EDIT_CITY_INPUT)
        await query.edit_message_text(
            "🏙 Введите название города:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="bbs_ecity_back_list")]
            ]),
        )
        return True
    if data == 'bbs_ecity_back_list':
        set_bbs_state(context, BBS.EDIT_CITY)
        cities = context.user_data.get('bbs_edit_cities', [])
        await query.edit_message_text(
            "🏙 Выберите город:", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(_build_edit_city_keyboard(cities)),
        )
        return True
    if data == 'bbs_ecity_done':
        cities = context.user_data.get('bbs_edit_cities', [])
        if not cities:
            await query.answer("❌ Выберите хотя бы один город", show_alert=True)
            return True
        await apply_edit_and_republish(
            query, context, db, target_chat_id, bbs_thread_id,
            field_name='city', db_column='city', value=json.dumps(cities),
        )
        return True

    # ── Edit: цели ──
    if data.startswith('bbs_egoal_') and data != 'bbs_egoal_done':
        goal = data.replace('bbs_egoal_', '')
        goals = context.user_data.get('bbs_edit_goals', [])
        if goal in goals:
            goals.remove(goal)
        else:
            goals.append(goal)
        context.user_data['bbs_edit_goals'] = goals
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(_build_edit_goal_keyboard(goals))
        )
        return True
    if data == 'bbs_egoal_done':
        goals = context.user_data.get('bbs_edit_goals', [])
        if not goals:
            await query.answer("❌ Выберите хотя бы одну цель", show_alert=True)
            return True
        await apply_edit_and_republish(
            query, context, db, target_chat_id, bbs_thread_id,
            field_name='goal', db_column='goals', value=json.dumps(goals),
        )
        return True

    # ── Публикация изменений на месте ──
    if data == 'bbs_publish_now':
        profile = get_profile(db, user_id)
        if not profile:
            await query.answer("Анкета не найдена.", show_alert=True)
            return True
        try:
            await update_profile_in_place(context.bot, db, user_id, target_chat_id)
            await query.edit_message_text(
                "✅ <b>Анкета обновлена в чате!</b>\n\nИзменения применены на месте.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Ещё редактировать", callback_data="bbs_edit_start")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_bbs")],
                ]),
            )
        except Exception as e:
            logging.error(f"BBS bbs_publish_now error: {e}")
            await query.answer("❌ Ошибка публикации. Попробуйте ещё раз.", show_alert=True)
        return True

    return False
