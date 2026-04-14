#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система плейсхолдеров — Панель Владельца → Система → Плейсхолдеры

Два типа плейсхолдеров:
  • Системные  — вычисляются автоматически из контекста (%user_name%, %date%, ...)
  • Кастомные  — Витя создаёт вручную (%правила%, %контакт%, ...)

Формат: %имя%
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import (
    InlineKeyboardButton as IKB,
    InlineKeyboardMarkup as IKM,
    Update,
)
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  СИСТЕМНЫЕ ПЛЕЙСХОЛДЕРЫ — справочник
# ═══════════════════════════════════════════════════════════════

SYSTEM_PLACEHOLDERS = {
    'user_name':       'Имя инициатора (кто написал слово-триггер)',
    'user_username':   '@username инициатора',
    'user_id':         'ID инициатора',
    'target_name':     'Имя цели (цитируемый пользователь или инициатор)',
    'target_username': '@username цели',
    'target_id':       'ID цели',
    'actor_name':      'Имя инициатора (синоним user_name)',
    'actor_username':  '@username инициатора (синоним user_username)',
    'chat_name':       'Название чата',
    'date':            'Текущая дата (дд.мм.гггг)',
    'time':            'Текущее время (чч:мм)',
    'warn_count':      'Количество предупреждений пользователя',
}


# ═══════════════════════════════════════════════════════════════
#  БД — ТАБЛИЦА И CRUD
# ═══════════════════════════════════════════════════════════════

def ensure_placeholder_table(db) -> None:
    try:
        db.cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_placeholders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                value       TEXT NOT NULL DEFAULT '',
                description TEXT DEFAULT '',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.conn.commit()
    except Exception as e:
        logger.error(f"ensure_placeholder_table: {e}")


def _get_all_custom(db) -> list:
    ensure_placeholder_table(db)
    db.cursor.execute('SELECT * FROM custom_placeholders ORDER BY name')
    return db.cursor.fetchall()


def _get_custom(db, ph_id: int):
    db.cursor.execute('SELECT * FROM custom_placeholders WHERE id = ?', (ph_id,))
    return db.cursor.fetchone()


def _get_custom_by_name(db, name: str):
    db.cursor.execute('SELECT * FROM custom_placeholders WHERE name = ?', (name.lower().strip(),))
    return db.cursor.fetchone()


def _create_custom(db, name: str, value: str, description: str = '') -> bool:
    name = name.lower().strip().replace('%', '').replace(' ', '_')
    if name in SYSTEM_PLACEHOLDERS:
        return False
    try:
        db.cursor.execute(
            'INSERT INTO custom_placeholders (name, value, description) VALUES (?, ?, ?)',
            (name, value, description)
        )
        db.conn.commit()
        return True
    except Exception as e:
        logger.error(f"_create_custom: {e}")
        return False


def _update_custom(db, ph_id: int, value: str, description: str = '') -> bool:
    try:
        db.cursor.execute(
            'UPDATE custom_placeholders SET value = ?, description = ? WHERE id = ?',
            (value, description, ph_id)
        )
        db.conn.commit()
        return True
    except Exception as e:
        logger.error(f"_update_custom: {e}")
        return False


def _delete_custom(db, ph_id: int) -> bool:
    try:
        db.cursor.execute('DELETE FROM custom_placeholders WHERE id = ?', (ph_id,))
        db.conn.commit()
        return True
    except Exception as e:
        logger.error(f"_delete_custom: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
#  ЦЕНТРАЛЬНАЯ ФУНКЦИЯ ЗАМЕНЫ
# ═══════════════════════════════════════════════════════════════

def apply_placeholders(text: str, db, context_data: dict = None) -> str:
    """
    Заменяет все %placeholder% в тексте.

    context_data может содержать:
        user        — объект telegram.User (инициатор)
        quoted_user — объект telegram.User (цитируемый, если есть)
        chat        — объект telegram.Chat
        warn_count  — int
    """
    if not text:
        return text

    ctx = context_data or {}

    # ── Системные ──
    user = ctx.get('user')
    quoted = ctx.get('quoted_user')
    chat = ctx.get('chat')
    now = datetime.now()

    def _name(u):
        return u.first_name if u else ''

    def _username(u):
        if not u:
            return ''
        return f'@{u.username}' if u.username else u.first_name

    def _uid(u):
        return str(u.id) if u else ''

    target = quoted or user

    system_values = {
        'user_name':       _name(user),
        'user_username':   _username(user),
        'user_id':         _uid(user),
        'target_name':     _name(target),
        'target_username': _username(target),
        'target_id':       _uid(target),
        'actor_name':      _name(user),
        'actor_username':  _username(user),
        'chat_name':       chat.title if chat else '',
        'date':            now.strftime('%d.%m.%Y'),
        'time':            now.strftime('%H:%M'),
        'warn_count':      str(ctx.get('warn_count', '')),
    }

    for key, val in system_values.items():
        text = text.replace(f'%{key}%', val)

    # ── Кастомные из БД ──
    try:
        customs = _get_all_custom(db)
        for row in customs:
            text = text.replace(f'%{row["name"]}%', row['value'])
    except Exception as e:
        logger.warning(f"apply_placeholders custom: {e}")

    return text


# ═══════════════════════════════════════════════════════════════
#  FSM СОСТОЯНИЯ
# ═══════════════════════════════════════════════════════════════

class PS:
    NAME  = 'ph_name'
    VALUE = 'ph_value'
    EDIT  = 'ph_edit_value'


# ═══════════════════════════════════════════════════════════════
#  UI — МЕНЮ ПЛЕЙСХОЛДЕРОВ
# ═══════════════════════════════════════════════════════════════

async def show_placeholder_menu(query, db, admin_id: int) -> None:
    ensure_placeholder_table(db)
    customs = _get_all_custom(db)

    text = "📝 <b>ПЛЕЙСХОЛДЕРЫ</b>\n\n"
    text += f"Кастомных: <b>{len(customs)}</b>\n\n"
    text += "<i>Используйте %имя% в текстах триггеров,\nFAQ и онбординге.</i>"

    kb = []
    for row in customs:
        val_preview = row['value'][:25] + '…' if len(row['value']) > 25 else row['value']
        kb.append([IKB(f"%{row['name']}%  →  {val_preview}", callback_data=f"ph_view_{row['id']}")])

    kb.append([IKB("➕ Создать плейсхолдер", callback_data="ph_create")])
    kb.append([IKB("📋 Системные плейсхолдеры", callback_data="ph_system_list")])
    kb.append([IKB("🔙 Назад", callback_data="owner_system")])

    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=IKM(kb))
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"show_placeholder_menu: {e}")


async def _show_system_list(query) -> None:
    text = "📋 <b>Системные плейсхолдеры</b>\n\n"
    text += "<i>Вычисляются автоматически, менять нельзя:</i>\n\n"
    for name, desc in SYSTEM_PLACEHOLDERS.items():
        text += f"<code>%{name}%</code> — {desc}\n"
    kb = [[IKB("◀ Назад", callback_data="ph_menu")]]
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=IKM(kb))
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"_show_system_list: {e}")


async def _show_ph_view(query, db, ph_id: int) -> None:
    row = _get_custom(db, ph_id)
    if not row:
        await query.answer("❌ Не найден", show_alert=True)
        return
    desc = row['description'] or '<i>нет описания</i>'
    text = (
        f"📝 <b>%{row['name']}%</b>\n\n"
        f"Значение:\n<code>{row['value']}</code>\n\n"
        f"Описание: {desc}"
    )
    kb = [
        [IKB("✏️ Изменить значение", callback_data=f"ph_edit_{ph_id}")],
        [IKB("🗑 Удалить", callback_data=f"ph_del_{ph_id}")],
        [IKB("◀ Назад", callback_data="ph_menu")],
    ]
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=IKM(kb))
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"_show_ph_view: {e}")


# ═══════════════════════════════════════════════════════════════
#  ДИСПЕТЧЕР CALLBACK'ОВ
# ═══════════════════════════════════════════════════════════════

async def handle_placeholder_callback(query, data: str, context, db, admin_id: int) -> None:
    ctx = context

    if data == "ph_menu":
        await show_placeholder_menu(query, db, admin_id)

    elif data == "ph_system_list":
        await _show_system_list(query)

    elif data == "ph_create":
        ctx.user_data['ph_state'] = PS.NAME
        await query.edit_message_text(
            "➕ <b>Создание плейсхолдера</b>\n\n"
            "Введите <b>имя</b> плейсхолдера:\n"
            "<i>(только латиница/кириллица/цифры/подчёркивание,\n"
            "например: <code>правила</code> или <code>admin_link</code>)</i>",
            parse_mode='HTML',
            reply_markup=IKM([[IKB("❌ Отмена", callback_data="ph_menu")]])
        )

    elif data.startswith("ph_view_"):
        ph_id = int(data[len("ph_view_"):])
        await _show_ph_view(query, db, ph_id)

    elif data.startswith("ph_edit_"):
        ph_id = int(data[len("ph_edit_"):])
        row = _get_custom(db, ph_id)
        if not row:
            await query.answer("❌ Не найден", show_alert=True)
            return
        ctx.user_data['ph_state'] = PS.EDIT
        ctx.user_data['ph_edit_id'] = ph_id
        await query.edit_message_text(
            f"✏️ <b>Редактирование %{row['name']}%</b>\n\n"
            f"Текущее значение:\n<code>{row['value']}</code>\n\n"
            "Введите новое значение:",
            parse_mode='HTML',
            reply_markup=IKM([[IKB("❌ Отмена", callback_data=f"ph_view_{ph_id}")]])
        )

    elif data.startswith("ph_del_"):
        ph_id = int(data[len("ph_del_"):])
        row = _get_custom(db, ph_id)
        if not row:
            await query.answer("❌ Не найден", show_alert=True)
            return
        await query.edit_message_text(
            f"🗑 Удалить <b>%{row['name']}%</b>?\n\n"
            f"Значение: <code>{row['value']}</code>",
            parse_mode='HTML',
            reply_markup=IKM([
                [IKB("⚠️ ДА, удалить", callback_data=f"ph_delyes_{ph_id}")],
                [IKB("❌ Отмена", callback_data=f"ph_view_{ph_id}")],
            ])
        )

    elif data.startswith("ph_delyes_"):
        ph_id = int(data[len("ph_delyes_"):])
        _delete_custom(db, ph_id)
        await query.answer("✅ Удалён", show_alert=True)
        await show_placeholder_menu(query, db, admin_id)

    else:
        await query.answer("❓", show_alert=True)


# ═══════════════════════════════════════════════════════════════
#  ОБРАБОТЧИК ТЕКСТОВОГО ВВОДА
# ═══════════════════════════════════════════════════════════════

async def handle_placeholder_text(update: Update, context, db, admin_id: int) -> bool:
    """Возвращает True если сообщение обработано."""
    state = context.user_data.get('ph_state')
    if not state:
        return False

    message = update.effective_message
    text = (message.text or '').strip()

    if not text:
        return False

    try:
        await message.delete()
    except Exception:
        pass

    chat_id = message.chat.id
    bot = context.bot

    # ── Создание: шаг 1 — имя ──
    if state == PS.NAME:
        name = text.lower().strip().replace('%', '').replace(' ', '_')
        # Валидация
        import re
        if not re.match(r'^[a-zа-яё0-9_]+$', name, re.IGNORECASE):
            msg = await bot.send_message(
                chat_id,
                "❌ Некорректное имя. Используйте буквы, цифры, подчёркивание.\n\nПовторите:",
                reply_markup=IKM([[IKB("❌ Отмена", callback_data="ph_menu")]])
            )
            return True

        if name in SYSTEM_PLACEHOLDERS:
            msg = await bot.send_message(
                chat_id,
                f"❌ <b>%{name}%</b> — системный плейсхолдер, нельзя переопределить.\n\nВведите другое имя:",
                parse_mode='HTML',
                reply_markup=IKM([[IKB("❌ Отмена", callback_data="ph_menu")]])
            )
            return True

        if _get_custom_by_name(db, name):
            msg = await bot.send_message(
                chat_id,
                f"❌ Плейсхолдер <code>%{name}%</code> уже существует.\n\nВведите другое имя:",
                parse_mode='HTML',
                reply_markup=IKM([[IKB("❌ Отмена", callback_data="ph_menu")]])
            )
            return True

        context.user_data['ph_state'] = PS.VALUE
        context.user_data['ph_new_name'] = name
        await bot.send_message(
            chat_id,
            f"✅ Имя: <code>%{name}%</code>\n\nТеперь введите <b>значение</b>:\n"
            f"<i>(то на что будет заменяться плейсхолдер)</i>",
            parse_mode='HTML',
            reply_markup=IKM([[IKB("❌ Отмена", callback_data="ph_menu")]])
        )
        return True

    # ── Создание: шаг 2 — значение ──
    if state == PS.VALUE:
        name = context.user_data.pop('ph_new_name', None)
        context.user_data.pop('ph_state', None)
        if not name:
            return False
        ok = _create_custom(db, name, text)
        if ok:
            await bot.send_message(
                chat_id,
                f"✅ Плейсхолдер <code>%{name}%</code> создан!\n\n"
                f"Значение: <code>{text}</code>\n\n"
                f"Теперь можно использовать <code>%{name}%</code> в текстах триггеров.",
                parse_mode='HTML',
                reply_markup=IKM([
                    [IKB("📝 К плейсхолдерам", callback_data="ph_menu")],
                    [IKB("🏠 Главное меню", callback_data="panel_main")],
                ])
            )
        else:
            await bot.send_message(chat_id, "❌ Ошибка создания.",
                                   reply_markup=IKM([[IKB("◀ Назад", callback_data="ph_menu")]]))
        return True

    # ── Редактирование значения ──
    if state == PS.EDIT:
        ph_id = context.user_data.pop('ph_edit_id', None)
        context.user_data.pop('ph_state', None)
        if not ph_id:
            return False
        row = _get_custom(db, ph_id)
        if not row:
            return False
        _update_custom(db, ph_id, text)
        await bot.send_message(
            chat_id,
            f"✅ <code>%{row['name']}%</code> обновлён!\n\nНовое значение: <code>{text}</code>",
            parse_mode='HTML',
            reply_markup=IKM([
                [IKB(f"👁 Просмотр %{row['name']}%", callback_data=f"ph_view_{ph_id}")],
                [IKB("📝 К плейсхолдерам", callback_data="ph_menu")],
            ])
        )
        return True

    return False
