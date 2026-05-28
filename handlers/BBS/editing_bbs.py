#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Редактирование анкеты BBS.
Каждое поле — 1 раз за 24ч.
"""

import os
import json
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.BBS.constants_bbs import BBS, EDITABLE_FIELDS, PARAM_OPTIONS, ROLE_OPTIONS, GOAL_OPTIONS
from handlers.BBS.helpers_bbs import set_bbs_state
from handlers.BBS.database_bbs import get_profile
from handlers.BBS.publishing_bbs import safe_answer


def _get_chat_id(context, explicit=None):
    if explicit:
        return explicit
    v = context.user_data.get('bbs_edit_chat_id')
    if v:
        return v
    try:
        return int(os.getenv('TARGET_CHAT_ID', 0)) or None
    except Exception:
        return None


def _get_thread_id(context, explicit=None, kind='bbs'):
    """V1.17.0Q4: BBS thread per-ws через bot_chat_topics.kind.

    Приоритет:
    1. explicit (если передан конкретный thread_id) — для override.
    2. runtime context.user_data['bbs_edit_thread_id'] — сессионный.
    3. bot_chat_topics.kind=<kind> для активного ws (правильный путь).
       Для kind='bbs_other' — fallback на kind='bbs' (общий ББС-тред,
       как у Вити, см. memory bbs_family_thread_binding_2026_05_29).
    4. .env BBS_THREAD_ID — legacy fallback.
    """
    if explicit:
        return explicit
    v = context.user_data.get('bbs_edit_thread_id')
    if v:
        return v
    # 3. Per-ws через bot_chat_topics.
    try:
        from bot_core.ws_resolver import resolve_thread, _ws_ctx_from_context
        # ws_id из контекста (middleware ws_ctx)
        ws_ctx = _ws_ctx_from_context(context)
        ws_id = ws_ctx.workspace_id if ws_ctx is not None else None
        if ws_id is not None:
            # Открываем conn через DB_PATH
            import sqlite3
            db_path = os.getenv('DB_PATH', 'database/bot_database.db')
            conn = sqlite3.connect(db_path)
            try:
                tid = resolve_thread(conn, ws_id, kind)
                # bbs_other → fallback на bbs если своего нет
                if tid is None and kind == 'bbs_other':
                    tid = resolve_thread(conn, ws_id, 'bbs')
                if tid is not None:
                    return tid
            finally:
                conn.close()
    except Exception as e:
        logging.debug(f"BBS _get_thread_id ws-lookup fallback: {e}")
    # 4. Legacy fallback
    try:
        return int(os.getenv('BBS_THREAD_ID', 0)) or None
    except Exception:
        return None


def get_edited_fields(profile) -> list:
    raw = profile.get('edited_fields') or '{}'
    try:
        data = json.loads(raw)
    except Exception:
        return[]
    if isinstance(data, list):
        return []
    now = datetime.now()
    return[f for f, ts in data.items()
            if _within_24h(ts, now)]


def _within_24h(ts_str, now):
    try:
        return (now - datetime.fromisoformat(ts_str)).total_seconds() < 86400
    except Exception:
        return False


def mark_field_edited(db, profile_id, field_name):
    try:
        db.cursor.execute('SELECT edited_fields FROM bbs_profiles WHERE id = ?', (profile_id,))
        row = db.cursor.fetchone()
        raw = (row['edited_fields'] if row else None) or '{}'
        data = json.loads(raw)
        if isinstance(data, list):
            data = {}
    except Exception:
        data = {}

    data[field_name] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        db.cursor.execute(
            'UPDATE bbs_profiles SET edited_fields = ?, updated_at = ? WHERE id = ?',
            (json.dumps(data), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), profile_id),
        )
        db.conn.commit()
    except Exception as e:
        logging.error(f"BBS mark_field_edited: {e}")


def _build_edit_menu_keyboard(edited: list) -> list:
    rows =[]
    for fkey, (label, _col) in EDITABLE_FIELDS.items():
        if fkey in edited:
            rows.append([InlineKeyboardButton(f"🔒 {label}", callback_data="bbs_noop")])
        else:
            rows.append([InlineKeyboardButton(label, callback_data=f"bbs_edit_field_{fkey}")])
    rows.append([InlineKeyboardButton("📤 Опубликовать изменения", callback_data="bbs_publish_now")])
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_dating")])
    return rows


def _build_edit_params_keyboard(params: dict) -> list:
    keyboard =[]
    for key, label in PARAM_OPTIONS.items():
        val = params.get(key)
        check = f" ✅ {val}" if val else ""
        keyboard.append([InlineKeyboardButton(f"{label}{check}", callback_data=f"bbs_eparam_{key}")])
    keyboard.append([InlineKeyboardButton("✅ Сохранить", callback_data="bbs_eparam_done")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")])
    return keyboard


def _build_edit_role_keyboard(selected: list) -> list:
    keyboard =[]
    for role in ROLE_OPTIONS:
        check = "✅ " if role in selected else ""
        keyboard.append([InlineKeyboardButton(f"{check}{role}", callback_data=f"bbs_erole_{role}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")])
    return keyboard


def _build_edit_city_keyboard(selected: list) -> list:
    presets =[('Санкт-Петербург', '#Спб'), ('Москва', '#Мск')]
    keyboard =[]
    for label, tag in presets:
        check = "✅ " if tag in selected else ""
        keyboard.append([InlineKeyboardButton(f"{check}{label}", callback_data=f"bbs_ecity_{tag}")])
    keyboard.append([InlineKeyboardButton("🏙 Другой город", callback_data="bbs_ecity_custom")])
    keyboard.append([InlineKeyboardButton("✅ Сохранить", callback_data="bbs_ecity_done")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")])
    return keyboard


def _build_edit_goal_keyboard(selected: list) -> list:
    keyboard =[]
    for goal in GOAL_OPTIONS:
        check = "✅ " if goal in selected else ""
        keyboard.append([InlineKeyboardButton(f"{check}{goal}", callback_data=f"bbs_egoal_{goal}")])
    keyboard.append([InlineKeyboardButton("✅ Сохранить", callback_data="bbs_egoal_done")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")])
    return keyboard


async def apply_edit_and_republish(
    src, context, db,
    target_chat_id, bbs_thread_id,
    field_name, db_column, value
):
    user_id = src.from_user.id if hasattr(src, 'from_user') and src.from_user else src.chat.id
    profile_id = context.user_data.get('bbs_editing_profile_id')
    if not profile_id:
        logging.error("BBS EDIT: profile_id not set!")
        return

    chat_id = _get_chat_id(context, target_chat_id)
    thread_id = _get_thread_id(context, bbs_thread_id)
    logging.info(f"BBS EDIT START: field={field_name} user={user_id} chat={chat_id} thread={thread_id}")

    # --- ИСПРАВЛЕНИЕ: Конвертируем списки/словари в JSON перед записью в БД ---
    db_value = json.dumps(value) if isinstance(value, (list, dict)) else value

    # 1) UPDATE DB
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        db.cursor.execute(
            f'UPDATE bbs_profiles SET {db_column} = ?, updated_at = ? WHERE id = ?',
            (db_value, now, profile_id),
        )
        db.conn.commit()
        logging.info(f"BBS EDIT: DB OK — {db_column}")
    except Exception as e:
        logging.error(f"BBS EDIT DB ERROR: {e}")
        await _reply(src, f"❌ Ошибка БД: {e}", None)
        return

    # 2) MARK EDITED
    mark_field_edited(db, profile_id, field_name)

    # 3) SHOW EDIT MENU with publish button
    set_bbs_state(context, BBS.EDIT_CHOOSE_FIELD)
    profile = get_profile(db, user_id)
    label = EDITABLE_FIELDS.get(field_name, (field_name,))[0]

    if not profile:
        await _reply(src, "✅ Данные обновлены!", InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 В меню", callback_data="menu_bbs")]]))
        return

    edited = get_edited_fields(profile)
    kb = _build_edit_menu_keyboard(edited)
    left = len(EDITABLE_FIELDS) - len(edited)

    text = (
        f"✅ <b>«{label}»</b> сохранено.\n\n"
        f"✏️ Доступно: <b>{left}</b> из {len(EDITABLE_FIELDS)}.\n"
        f"🔒 = уже изменено за 24 часа.\n\n"
        f"Нажмите <b>«Опубликовать изменения»</b> чтобы применить в чате."
    )
    await _reply(src, text, InlineKeyboardMarkup(kb))


async def _reply(src, text, kb):
    if hasattr(src, 'edit_message_text'):
        await safe_answer(src, text, kb)
    else:
        await src.reply_text(text, parse_mode='HTML', reply_markup=kb)


async def apply_edit(query, context, db, target_chat_id, bbs_thread_id, field, value):
    await apply_edit_and_republish(
        query, context, db, target_chat_id, bbs_thread_id,
        field_name=field, db_column=field, value=value,
    )


# ═══════════════════════════════════════════════════════════════
# КЛАВИАТУРЫ ДЛЯ РЕДАКТИРОВАНИЯ (bbs_e* префиксы)
# ═══════════════════════════════════════════════════════════════

def _build_edit_params_keyboard(params: dict) -> list:
    keyboard = []
    for key, label in PARAM_OPTIONS.items():
        val = params.get(key)
        check = f" ✅ {val}" if val else ""
        keyboard.append([InlineKeyboardButton(f"{label}{check}", callback_data=f"bbs_eparam_{key}")])
    keyboard.append([InlineKeyboardButton("✅ Сохранить", callback_data="bbs_eparam_done")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")])
    return keyboard


def _build_edit_role_keyboard(selected: list) -> list:
    keyboard = []
    for role in ROLE_OPTIONS:
        check = "✅ " if role in selected else ""
        keyboard.append([InlineKeyboardButton(f"{check}{role}", callback_data=f"bbs_erole_{role}")])
    # УБРАНА кнопка "Сохранить", так как выбор роли теперь сохраняет ее сразу
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")])
    return keyboard


def _build_edit_city_keyboard(selected: list) -> list:
    presets = [('Санкт-Петербург', '#Спб'), ('Москва', '#Мск')]
    keyboard = []
    for label, tag in presets:
        check = "✅ " if tag in selected else ""
        keyboard.append([InlineKeyboardButton(f"{check}{label}", callback_data=f"bbs_ecity_{tag}")])
    keyboard.append([InlineKeyboardButton("🏙 Другой город", callback_data="bbs_ecity_custom")])
    keyboard.append([InlineKeyboardButton("✅ Сохранить", callback_data="bbs_ecity_done")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")])
    return keyboard


def _build_edit_goal_keyboard(selected: list) -> list:
    keyboard = []
    for goal in GOAL_OPTIONS:
        check = "✅ " if goal in selected else ""
        keyboard.append([InlineKeyboardButton(f"{check}{goal}", callback_data=f"bbs_egoal_{goal}")])
    keyboard.append([InlineKeyboardButton("✅ Сохранить", callback_data="bbs_egoal_done")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_edit_start")])
    return keyboard