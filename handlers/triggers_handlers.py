#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система триггеров — автомодерация по ключевым словам.

Путь: handlers/triggers_handlers.py

Функционал:
  - CRUD триггеров через инлайн-меню владельца
  - Обработка сообщений: проверка на совпадение ключевых слов
  - Действия: ответ в чат, удаление, мут, предупреждение, кик, бан
  - Вероятность срабатывания (1-100%)
  - Накопительные триггеры: N нарушений → финальное действие
"""

import json
import logging
import random
import re
import time
from typing import Optional, List

from telegram import (
    Update, ChatPermissions,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes
from config.emojis import ICON_HIGH_VOLTAGE

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════

# Условия совпадения
CONDITIONS = {
    'exact':       'Точное совпадение',
    'contains':    'Содержит',
    'starts_with': 'Начинается с',
    'ends_with':   'Заканчивается на',
    'whole_word':  'Целое слово',
}

# Действия при срабатывании
ACTIONS = {
    'reply':   '💬 Ответ в чат',
    'delete':  '🗑 Удалить сообщение',
    'warn':    '⚠️ Предупреждение',
    'mute_5m': '🔇 Мут 5 мин',
    'mute_1h': '🔇 Мут 1 час',
    'mute_1d': '🔇 Мут 1 день',
    'kick':    '👢 Кик',
    'ban':     '🚫 Бан',
}

# Для накопительного финального действия
CUMULATIVE_ACTIONS = {
    'mute_1h': '🔇 Мут 1 час',
    'mute_1d': '🔇 Мут 1 день',
    'kick':    '👢 Кик',
    'ban':     '🚫 Бан',
}

MUTE_DURATIONS = {
    'mute_5m': 300,
    'mute_1h': 3600,
    'mute_1d': 86400,
}


# ═══════════════════════════════════════════════════════════════
#  ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ
# ═══════════════════════════════════════════════════════════════

def ensure_trigger_tables(db) -> None:
    """Создаёт таблицы triggers и trigger_violations."""
    try:
        db.cursor.execute('''
            CREATE TABLE IF NOT EXISTS triggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                keywords TEXT NOT NULL,
                condition TEXT NOT NULL DEFAULT 'contains',
                action TEXT NOT NULL DEFAULT 'delete',
                action_value TEXT,
                probability INTEGER NOT NULL DEFAULT 100,
                cumulative_enabled INTEGER DEFAULT 0,
                cumulative_threshold INTEGER DEFAULT 3,
                cumulative_action TEXT DEFAULT 'kick',
                is_enabled INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trigger_violations (
                user_id INTEGER NOT NULL,
                trigger_id INTEGER NOT NULL,
                count INTEGER DEFAULT 0,
                last_violation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, trigger_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (trigger_id) REFERENCES triggers(id) ON DELETE CASCADE
            )
        ''')
        db.conn.commit()
    except Exception as e:
        logger.error(f"ensure_trigger_tables error: {e}")


# ═══════════════════════════════════════════════════════════════
#  ХЕЛПЕРЫ БД
# ═══════════════════════════════════════════════════════════════

def _get_all_triggers(db) -> list:
    db.cursor.execute('SELECT * FROM triggers ORDER BY id')
    return db.cursor.fetchall()


def _get_enabled_triggers(db) -> list:
    db.cursor.execute('SELECT * FROM triggers WHERE is_enabled = 1 ORDER BY id')
    return db.cursor.fetchall()


def _get_trigger(db, trigger_id: int):
    db.cursor.execute('SELECT * FROM triggers WHERE id = ?', (trigger_id,))
    return db.cursor.fetchone()


def _delete_trigger(db, trigger_id: int) -> None:
    db.cursor.execute('DELETE FROM triggers WHERE id = ?', (trigger_id,))
    db.cursor.execute('DELETE FROM trigger_violations WHERE trigger_id = ?', (trigger_id,))
    db.conn.commit()


def _toggle_trigger(db, trigger_id: int) -> bool:
    t = _get_trigger(db, trigger_id)
    if not t:
        return False
    new_state = 0 if t['is_enabled'] else 1
    db.cursor.execute('UPDATE triggers SET is_enabled = ? WHERE id = ?', (new_state, trigger_id))
    db.conn.commit()
    return bool(new_state)


def _increment_violation(db, user_id: int, trigger_id: int) -> int:
    """Увеличивает счётчик нарушений, возвращает новое значение."""
    db.cursor.execute(
        'SELECT count FROM trigger_violations WHERE user_id = ? AND trigger_id = ?',
        (user_id, trigger_id)
    )
    row = db.cursor.fetchone()
    if row:
        new_count = row['count'] + 1
        db.cursor.execute(
            'UPDATE trigger_violations SET count = ?, last_violation_at = CURRENT_TIMESTAMP '
            'WHERE user_id = ? AND trigger_id = ?',
            (new_count, user_id, trigger_id)
        )
    else:
        new_count = 1
        db.cursor.execute(
            'INSERT INTO trigger_violations (user_id, trigger_id, count) VALUES (?, ?, 1)',
            (user_id, trigger_id)
        )
    db.conn.commit()
    return new_count


def _reset_violations(db, user_id: int, trigger_id: int) -> None:
    db.cursor.execute(
        'DELETE FROM trigger_violations WHERE user_id = ? AND trigger_id = ?',
        (user_id, trigger_id)
    )
    db.conn.commit()


def _user_link(user) -> str:
    name = user.first_name or "Пользователь"
    return f'<a href="tg://user?id={user.id}">{name}</a>'


# ═══════════════════════════════════════════════════════════════
#  ДВИЖОК ОБРАБОТКИ СООБЩЕНИЙ
# ═══════════════════════════════════════════════════════════════

async def process_triggers(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    target_chat_id: int,
    main_admin_id: int,
) -> bool:
    """
    Проверяет сообщение на совпадение с триггерами.
    Вызывается из message_handler.handle_message.
    Возвращает True если сообщение было обработано (удалено/наказан).
    """
    message = update.effective_message
    if not message or not message.text:
        return False

    user = message.from_user
    if not user:
        return False

    # Не применяем триггеры к админам/владельцу
    user_data = db.get_user(user.id)
    if user_data and (user_data['is_admin'] or user_data['is_owner']):
        return False
    if user.id == main_admin_id:
        return False

    triggers = _get_enabled_triggers(db)
    if not triggers:
        return False

    msg_text = message.text.lower().strip()
    handled = False

    for trigger in triggers:
        # Проверка вероятности
        prob = trigger['probability'] or 100
        if prob < 100 and random.randint(1, 100) > prob:
            continue

        # Проверка совпадения
        keywords = [kw.strip().lower() for kw in trigger['keywords'].split(',') if kw.strip()]
        condition = trigger['condition'] or 'contains'
        matched = False

        for kw in keywords:
            if condition == 'exact':
                matched = (msg_text == kw)
            elif condition == 'contains':
                matched = (kw in msg_text)
            elif condition == 'starts_with':
                matched = msg_text.startswith(kw)
            elif condition == 'ends_with':
                matched = msg_text.endswith(kw)
            elif condition == 'whole_word':
                matched = bool(re.search(rf'\b{re.escape(kw)}\b', msg_text))
            if matched:
                break

        if not matched:
            continue

        # ── Совпадение! Выполняем действие ──
        action = trigger['action'] or 'delete'
        action_value = trigger['action_value'] or ''
        trigger_name = trigger['name']

        logger.info(f"TRIGGER '{trigger_name}' matched for user {user.id}: action={action}")

        # Журнал
        try:
            from handlers.journal_handlers import log_trigger
            action_label = ACTIONS.get(action, action)
            await log_trigger(context.bot, db, user.id, trigger_name, action_label)
        except Exception:
            pass

        try:
            if action == 'reply':
                reply_text = action_value or f"⚠️ Триггер: {trigger_name}"
                await message.reply_text(reply_text, parse_mode='HTML')

            elif action == 'delete':
                try:
                    await message.delete()
                except Exception:
                    pass
                handled = True

            elif action == 'warn':
                warn_text = action_value or f"⚠️ {_user_link(user)}, предупреждение!"
                await message.reply_text(warn_text, parse_mode='HTML')

            elif action in MUTE_DURATIONS:
                duration = MUTE_DURATIONS[action]
                until_ts = int(time.time()) + duration
                await context.bot.restrict_chat_member(
                    chat_id=target_chat_id,
                    user_id=user.id,
                    permissions=ChatPermissions(
                        can_send_messages=False,
                        can_send_audios=False,
                        can_send_documents=False,
                        can_send_photos=False,
                        can_send_videos=False,
                        can_send_video_notes=False,
                        can_send_voice_notes=False,
                        can_send_polls=False,
                        can_send_other_messages=False,
                        can_add_web_page_previews=False,
                    ),
                    until_date=until_ts,
                )
                try:
                    await message.delete()
                except Exception:
                    pass
                handled = True

            elif action == 'kick':
                await context.bot.ban_chat_member(chat_id=target_chat_id, user_id=user.id)
                await context.bot.unban_chat_member(chat_id=target_chat_id, user_id=user.id)
                handled = True

            elif action == 'ban':
                await context.bot.ban_chat_member(chat_id=target_chat_id, user_id=user.id)
                handled = True

        except Exception as e:
            logger.error(f"Trigger '{trigger_name}' action '{action}' failed: {e}")

        # ── Накопительная система ──
        if trigger['cumulative_enabled']:
            count = _increment_violation(db, user.id, trigger['id'])
            threshold = trigger['cumulative_threshold'] or 3

            if count >= threshold:
                cum_action = trigger['cumulative_action'] or 'kick'
                logger.warning(
                    f"CUMULATIVE trigger '{trigger_name}': user {user.id} "
                    f"reached {count}/{threshold} → {cum_action}"
                )
                try:
                    if cum_action in MUTE_DURATIONS:
                        until_ts = int(time.time()) + MUTE_DURATIONS[cum_action]
                        await context.bot.restrict_chat_member(
                            chat_id=target_chat_id,
                            user_id=user.id,
                            permissions=ChatPermissions(can_send_messages=False),
                            until_date=until_ts,
                        )
                    elif cum_action == 'kick':
                        await context.bot.ban_chat_member(chat_id=target_chat_id, user_id=user.id)
                        await context.bot.unban_chat_member(chat_id=target_chat_id, user_id=user.id)
                    elif cum_action == 'ban':
                        await context.bot.ban_chat_member(chat_id=target_chat_id, user_id=user.id)

                    handled = True
                except Exception as e:
                    logger.error(f"Cumulative action failed: {e}")

                _reset_violations(db, user.id, trigger['id'])

        if handled:
            break  # Сообщение удалено — дальше не проверяем

    return handled


# ═══════════════════════════════════════════════════════════════
#  МЕНЮ ТРИГГЕРОВ (для владельца)
# ═══════════════════════════════════════════════════════════════

async def show_triggers_menu(query, db, admin_id: int) -> None:
    """Главное меню триггеров."""
    ensure_trigger_tables(db)
    triggers = _get_all_triggers(db)

    total = len(triggers)
    enabled = sum(1 for t in triggers if t['is_enabled'])

    text = (
        f"{ICON_HIGH_VOLTAGE} <b>ТРИГГЕРЫ</b>\n"
        f"{'━' * 24}\n\n"
        f"📊 Всего: <b>{total}</b> | Активных: <b>{enabled}</b>\n\n"
    )

    if triggers:
        for t in triggers:
            icon = "🟢" if t['is_enabled'] else "🔴"
            cum = " 📈" if t['cumulative_enabled'] else ""
            text += f"  {icon} <b>{t['name']}</b> — {CONDITIONS.get(t['condition'], '?')}{cum}\n"
    else:
        text += "  <i>Триггеров пока нет</i>\n"

    keyboard = [
        [InlineKeyboardButton("✨ Создать триггер", callback_data="trigger_create")],
        [InlineKeyboardButton("📋 Управление", callback_data="trigger_list")],
        [InlineKeyboardButton("🔙 Назад", callback_data="panel_main")],
    ]
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"show_triggers_menu error: {e}")


# ═══════════════════════════════════════════════════════════════
#  СПИСОК ТРИГГЕРОВ (для управления)
# ═══════════════════════════════════════════════════════════════

async def show_trigger_list(query, db, admin_id: int) -> None:
    """Список триггеров с кнопками управления."""
    ensure_trigger_tables(db)
    triggers = _get_all_triggers(db)

    if not triggers:
        text = f"{ICON_HIGH_VOLTAGE} <b>Триггеры</b>\n\n<i>Список пуст.</i>"
        keyboard = [
            [InlineKeyboardButton("✨ Создать", callback_data="trigger_create")],
            [InlineKeyboardButton("🔙 Назад", callback_data="owner_triggers")],
        ]
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = f"{ICON_HIGH_VOLTAGE} <b>УПРАВЛЕНИЕ ТРИГГЕРАМИ</b>\n{'━' * 24}\n\n"

    keyboard = []
    for t in triggers:
        icon = "🟢" if t['is_enabled'] else "🔴"
        keyboard.append([
            InlineKeyboardButton(f"{icon} {t['name']}", callback_data=f"trigger_view_{t['id']}"),
        ])

    keyboard.append([InlineKeyboardButton("✨ Создать", callback_data="trigger_create")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="owner_triggers")])

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


# ═══════════════════════════════════════════════════════════════
#  ПРОСМОТР/РЕДАКТИРОВАНИЕ ТРИГГЕРА
# ═══════════════════════════════════════════════════════════════

async def show_trigger_detail(query, db, trigger_id: int) -> None:
    """Детальный просмотр триггера с кнопками действий."""
    t = _get_trigger(db, trigger_id)
    if not t:
        await query.answer("❌ Триггер не найден.", show_alert=True)
        return

    status = "🟢 Включён" if t['is_enabled'] else "🔴 Выключен"
    action_label = ACTIONS.get(t['action'], t['action'])
    cond_label = CONDITIONS.get(t['condition'], t['condition'])

    text = (
        f"{ICON_HIGH_VOLTAGE} <b>{t['name']}</b>\n"
        f"{'━' * 24}\n\n"
        f"📝 Ключевые слова: <code>{t['keywords']}</code>\n"
        f"🔍 Условие: {cond_label}\n"
        f" {ICON_HIGH_VOLTAGE} Действие: {action_label}\n"
    )

    if t['action_value']:
        text += f"💬 Текст: <i>{t['action_value'][:100]}</i>\n"

    text += (
        f"🎲 Вероятность: {t['probability']}%\n"
        f"📡 Статус: {status}\n"
    )

    if t['cumulative_enabled']:
        cum_label = CUMULATIVE_ACTIONS.get(t['cumulative_action'], t['cumulative_action'])
        text += (
            f"\n📈 <b>Накопительный:</b>\n"
            f"  Порог: {t['cumulative_threshold']} нарушений\n"
            f"  Действие: {cum_label}\n"
        )

    toggle_label = "🔴 Выключить" if t['is_enabled'] else "🟢 Включить"

    keyboard = [
        [InlineKeyboardButton(toggle_label, callback_data=f"trigger_toggle_{trigger_id}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"trigger_delete_{trigger_id}")],
        [InlineKeyboardButton("🔙 К списку", callback_data="trigger_list")],
    ]

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_trigger_toggle(query, db, trigger_id: int) -> None:
    new_state = _toggle_trigger(db, trigger_id)
    label = "включён 🟢" if new_state else "выключен 🔴"
    await query.answer(f"Триггер {label}", show_alert=True)
    await show_trigger_detail(query, db, trigger_id)


async def handle_trigger_delete_confirm(query, db, trigger_id: int) -> None:
    t = _get_trigger(db, trigger_id)
    if not t:
        await query.answer("❌ Не найден.", show_alert=True)
        return

    text = f"🗑 Удалить триггер <b>{t['name']}</b>?\n\nЭто действие нельзя отменить."
    keyboard = [
        [InlineKeyboardButton("⚠️ ДА, удалить", callback_data=f"trigger_delete_yes_{trigger_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"trigger_view_{trigger_id}")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_trigger_delete_execute(query, db, trigger_id: int) -> None:
    _delete_trigger(db, trigger_id)
    await query.answer("✅ Триггер удалён.", show_alert=True)
    await show_trigger_list(query, db, 0)


# ═══════════════════════════════════════════════════════════════
#  СОЗДАНИЕ ТРИГГЕРА (пошаговый FSM)
# ═══════════════════════════════════════════════════════════════

async def trigger_create_start(query, context, db) -> None:
    """Шаг 1: Ввод названия."""
    context.user_data['trigger_draft'] = {}
    context.user_data['owner_awaiting'] = 'trigger_name'

    text = (
        f"{ICON_HIGH_VOLTAGE} <b>Создание триггера</b> — Шаг 1/5\n\n"
        "Введите <b>название</b> триггера:\n"
        "<i>(Для вашего удобства, например: «Спам-ссылки»)</i>"
    )
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_triggers")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def trigger_create_set_condition(query, context) -> None:
    """Шаг 3: Выбор условия."""
    text = (
        "✨ <b>Создание триггера</b> — Шаг 3/5\n\n"
        "Выберите <b>условие</b> совпадения:"
    )
    keyboard = []
    for key, label in CONDITIONS.items():
        keyboard.append([InlineKeyboardButton(label, callback_data=f"trigger_cond_{key}")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="owner_triggers")])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def trigger_create_set_action(query, context) -> None:
    """Шаг 4: Выбор действия."""
    text = (
        "✨ <b>Создание триггера</b> — Шаг 4/5\n\n"
        "Выберите <b>действие</b>:"
    )
    keyboard = []
    for key, label in ACTIONS.items():
        keyboard.append([InlineKeyboardButton(label, callback_data=f"trigger_act_{key}")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="owner_triggers")])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def trigger_create_set_cumulative(query, context) -> None:
    """Шаг 5: Накопительный режим."""
    text = (
        "✨ <b>Создание триггера</b> — Шаг 5/5\n\n"
        "Включить <b>накопительный</b> режим?\n\n"
        "<i>Если да — после N нарушений сработает\n"
        "финальное наказание (мут/кик/бан)</i>"
    )
    keyboard = [
        [InlineKeyboardButton("📈 Да, включить", callback_data="trigger_cum_yes")],
        [InlineKeyboardButton("➡️ Нет, пропустить", callback_data="trigger_cum_no")],
        [InlineKeyboardButton("❌ Отмена", callback_data="owner_triggers")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def trigger_create_cum_threshold(query, context) -> None:
    """Подшаг: порог нарушений."""
    text = (
        "📈 <b>Накопительный режим</b>\n\n"
        "Выберите порог (сколько нарушений до наказания):"
    )
    keyboard = [
        [
            InlineKeyboardButton("3", callback_data="trigger_cum_th_3"),
            InlineKeyboardButton("5", callback_data="trigger_cum_th_5"),
            InlineKeyboardButton("10", callback_data="trigger_cum_th_10"),
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="owner_triggers")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def trigger_create_cum_action(query, context) -> None:
    """Подшаг: финальное действие."""
    text = (
        "📈 <b>Финальное наказание</b>\n\n"
        "Что делать при достижении порога?"
    )
    keyboard = []
    for key, label in CUMULATIVE_ACTIONS.items():
        keyboard.append([InlineKeyboardButton(label, callback_data=f"trigger_cum_act_{key}")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="owner_triggers")])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def trigger_create_save(query, context, db) -> None:
    """Сохранение триггера в БД."""
    draft = context.user_data.get('trigger_draft', {})
    if not draft.get('name') or not draft.get('keywords'):
        await query.answer("❌ Данные триггера неполные.", show_alert=True)
        return

    ensure_trigger_tables(db)

    try:
        db.cursor.execute('''
            INSERT INTO triggers 
            (name, keywords, condition, action, action_value, probability,
             cumulative_enabled, cumulative_threshold, cumulative_action, 
             is_enabled, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        ''', (
            draft['name'],
            draft['keywords'],
            draft.get('condition', 'contains'),
            draft.get('action', 'delete'),
            draft.get('action_value', ''),
            100,
            1 if draft.get('cumulative') else 0,
            draft.get('cum_threshold', 3),
            draft.get('cum_action', 'kick'),
            query.from_user.id,
        ))
        db.conn.commit()
        trigger_id = db.cursor.lastrowid

        context.user_data.pop('trigger_draft', None)
        context.user_data.pop('owner_awaiting', None)

        await query.answer("✅ Триггер создан!", show_alert=True)
        await show_trigger_detail(query, db, trigger_id)

    except Exception as e:
        logger.error(f"trigger_create_save error: {e}")
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
#  FSM: ОБРАБОТКА ТЕКСТОВОГО ВВОДА
# ═══════════════════════════════════════════════════════════════

async def handle_trigger_text_input(update, context, db) -> bool:
    """
    Обрабатывает текстовый ввод при создании триггера.
    Возвращает True если обработано.
    """
    awaiting = context.user_data.get('owner_awaiting', '')
    if not awaiting.startswith('trigger_'):
        return False

    message = update.effective_message
    text = message.text.strip() if message.text else ''
    draft = context.user_data.get('trigger_draft', {})

    # ── Шаг 1: Название ──
    if awaiting == 'trigger_name':
        if len(text) < 2 or len(text) > 50:
            await message.reply_text("❌ Название: 2–50 символов.")
            return True

        draft['name'] = text
        context.user_data['trigger_draft'] = draft
        context.user_data['owner_awaiting'] = 'trigger_keywords'

        await message.reply_text(
            f"{ICON_HIGH_VOLTAGE} <b>Создание триггера</b> — Шаг 2/5\n\n"
            "Введите <b>ключевые слова</b> через запятую:\n"
            "<i>(Пример: спам, реклама, подписывайся)</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="owner_triggers")]
            ])
        )
        return True

    # ── Шаг 2: Ключевые слова ──
    if awaiting == 'trigger_keywords':
        if len(text) < 1:
            await message.reply_text("❌ Введите хотя бы одно ключевое слово.")
            return True

        draft['keywords'] = text
        context.user_data['trigger_draft'] = draft
        context.user_data.pop('owner_awaiting', None)

        # Переходим к выбору условия (инлайн-кнопки)
        cond_text = (
            f"{ICON_HIGH_VOLTAGE} <b>Создание триггера</b> — Шаг 3/5\n\n"
            "Выберите <b>условие</b> совпадения:"
        )
        keyboard = []
        for key, label in CONDITIONS.items():
            keyboard.append([InlineKeyboardButton(label, callback_data=f"trigger_cond_{key}")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="owner_triggers")])

        await message.reply_text(
            cond_text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return True

    # ── Текст ответа (после action=reply/warn) ──
    if awaiting == 'trigger_action_value':
        draft['action_value'] = text
        context.user_data['trigger_draft'] = draft
        context.user_data.pop('owner_awaiting', None)

        # Переходим к накопительному режиму
        cum_text = (
            "✨ <b>Создание триггера</b> — Шаг 5/5\n\n"
            "Включить <b>накопительный</b> режим?\n\n"
            "<i>После N нарушений — финальное наказание</i>"
        )
        keyboard = [
            [InlineKeyboardButton("📈 Да", callback_data="trigger_cum_yes")],
            [InlineKeyboardButton("➡️ Нет", callback_data="trigger_cum_no")],
        ]
        await message.reply_text(
            cum_text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return True

    return False


# ═══════════════════════════════════════════════════════════════
#  ДИСПЕТЧЕР CALLBACK-ОВ
# ═══════════════════════════════════════════════════════════════

async def handle_trigger_callback(query, data: str, context, db, admin_id: int) -> None:
    """
    Единый обработчик всех callback_data начинающихся с 'trigger_'.
    Вызывается из callback_handler.py.
    """
    user = query.from_user

    # Проверяем доступ (owner или admin)
    user_data = db.get_user(user.id)
    is_staff = user.id == admin_id or (user_data and (user_data['is_admin'] or user_data['is_owner']))
    if not is_staff:
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    draft = context.user_data.get('trigger_draft', {})

    # ── Меню ──
    if data == "trigger_create":
        await trigger_create_start(query, context, db)

    elif data == "trigger_list":
        await show_trigger_list(query, db, admin_id)

    # ── Просмотр ──
    elif data.startswith("trigger_view_"):
        tid = int(data.replace("trigger_view_", ""))
        await show_trigger_detail(query, db, tid)

    # ── Вкл/выкл ──
    elif data.startswith("trigger_toggle_"):
        tid = int(data.replace("trigger_toggle_", ""))
        await handle_trigger_toggle(query, db, tid)

    # ── Удаление ──
    elif data.startswith("trigger_delete_yes_"):
        tid = int(data.replace("trigger_delete_yes_", ""))
        await handle_trigger_delete_execute(query, db, tid)

    elif data.startswith("trigger_delete_"):
        tid = int(data.replace("trigger_delete_", ""))
        await handle_trigger_delete_confirm(query, db, tid)

    # ── Создание: выбор условия ──
    elif data.startswith("trigger_cond_"):
        cond = data.replace("trigger_cond_", "")
        draft['condition'] = cond
        context.user_data['trigger_draft'] = draft
        await trigger_create_set_action(query, context)

    # ── Создание: выбор действия ──
    elif data.startswith("trigger_act_"):
        act = data.replace("trigger_act_", "")
        draft['action'] = act
        context.user_data['trigger_draft'] = draft

        # Для reply и warn — запрашиваем текст
        if act in ('reply', 'warn'):
            context.user_data['owner_awaiting'] = 'trigger_action_value'
            text = (
                "💬 <b>Текст ответа / предупреждения</b>\n\n"
                "Введите текст, который бот отправит при срабатывании:"
            )
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_triggers")]]
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            # Переходим к накопительному
            await trigger_create_set_cumulative(query, context)

    # ── Создание: накопительный ──
    elif data == "trigger_cum_yes":
        draft['cumulative'] = True
        context.user_data['trigger_draft'] = draft
        await trigger_create_cum_threshold(query, context)

    elif data == "trigger_cum_no":
        draft['cumulative'] = False
        context.user_data['trigger_draft'] = draft
        await trigger_create_save(query, context, db)

    elif data.startswith("trigger_cum_th_"):
        th = int(data.replace("trigger_cum_th_", ""))
        draft['cum_threshold'] = th
        context.user_data['trigger_draft'] = draft
        await trigger_create_cum_action(query, context)

    elif data.startswith("trigger_cum_act_"):
        act = data.replace("trigger_cum_act_", "")
        draft['cum_action'] = act
        context.user_data['trigger_draft'] = draft
        await trigger_create_save(query, context, db)

    else:
        await query.answer("❓ Неизвестное действие.", show_alert=True)
