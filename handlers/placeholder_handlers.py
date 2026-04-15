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
import json
import re
from datetime import datetime, timedelta, date
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
    # Старый формат (совместимость)
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
    # Новый формат %act_X% и %rpl_X%
    'act_tgun':  '%act_X% — инициатор: имя в Telegram',
    'act_nn':    '%act_X% — инициатор: @nickname',
    'act_blns':  '%act_X% — инициатор: баланс пульсов',
    'act_msg':   '%act_X% — инициатор: сообщений всего',
    'act_msg_t': '%act_X% — инициатор: сообщений сегодня',
    'act_msg_w': '%act_X% — инициатор: сообщений за неделю',
    'act_msg_m': '%act_X% — инициатор: сообщений за месяц',
    'act_msg_y': '%act_X% — инициатор: сообщений за год',
    'act_d':     '%act_X% — инициатор: дней в чате',
    'act_w':     '%act_X% — инициатор: предупреждения',
    'act_plc':   '%act_X% — инициатор: место в рейтинге',
    'act_jt':    '%act_X% — инициатор: дата вступления',
    'act_rnk':   '%act_X% — инициатор: ранг',
    'act_rfrl_c':'%act_X% — инициатор: количество рефералов',
    'act_form':  '%act_X% — инициатор: полная анкета',
    'act_un':    '%act_X% — инициатор: имя из анкеты',
    'act_city':  '%act_X% — инициатор: город',
    'act_yo':    '%act_X% — инициатор: возраст',
    'act_sr':    '%act_X% — инициатор: роль',
    # rpl_ — те же суффиксы, но для цитируемого пользователя
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

# ═══════════════════════════════════════════════════════════════
#  ТАБЛИЦА НАСТРОЕК АНКЕТЫ ПОЛЬЗОВАТЕЛЯ
# ═══════════════════════════════════════════════════════════════

def ensure_form_settings_table(db) -> None:
    try:
        db.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_form_settings (
                user_id   INTEGER PRIMARY KEY,
                show_un   INTEGER DEFAULT 1,
                show_city INTEGER DEFAULT 1,
                show_yo   INTEGER DEFAULT 1,
                show_sr   INTEGER DEFAULT 1
            )
        ''')
        db.conn.commit()
    except Exception as e:
        logger.error(f"ensure_form_settings_table: {e}")


def _get_form_prefs(db, user_id: int) -> dict:
    """Возвращает настройки анкеты пользователя (по умолчанию всё вкл)."""
    try:
        ensure_form_settings_table(db)
        db.cursor.execute('SELECT * FROM user_form_settings WHERE user_id = ?', (user_id,))
        row = db.cursor.fetchone()
        if row:
            return {'show_un': bool(row['show_un']), 'show_city': bool(row['show_city']),
                    'show_yo': bool(row['show_yo']), 'show_sr': bool(row['show_sr'])}
    except Exception:
        pass
    return {'show_un': True, 'show_city': True, 'show_yo': True, 'show_sr': True}


def _set_form_pref(db, user_id: int, field: str, value: bool) -> None:
    try:
        ensure_form_settings_table(db)
        db.cursor.execute(
            f'INSERT INTO user_form_settings (user_id, {field}) VALUES (?, ?) '
            f'ON CONFLICT(user_id) DO UPDATE SET {field} = excluded.{field}',
            (user_id, int(value))
        )
        db.conn.commit()
    except Exception as e:
        logger.error(f"_set_form_pref: {e}")


# ═══════════════════════════════════════════════════════════════
#  РАЗРЕШЕНИЕ ДАННЫХ ПОЛЬЗОВАТЕЛЯ
# ═══════════════════════════════════════════════════════════════

def _resolve_user_stats(db, user_id: int) -> dict:
    """Собирает все данные о пользователе для плейсхолдеров %act_X% / %rpl_X%."""
    result: dict = {}
    if not db or not user_id:
        return result

    today_str = date.today().isoformat()
    week_ago  = (date.today() - timedelta(days=7)).isoformat()
    month_ago = (date.today() - timedelta(days=30)).isoformat()
    year_ago  = (date.today() - timedelta(days=365)).isoformat()

    def _stat(field, date_from=None):
        try:
            if date_from:
                db.cursor.execute(
                    f'SELECT COALESCE(SUM({field}),0) FROM user_stats WHERE user_id=? AND date>=?',
                    (user_id, date_from))
            else:
                db.cursor.execute(
                    f'SELECT COALESCE(SUM({field}),0) FROM user_stats WHERE user_id=?',
                    (user_id,))
            r = db.cursor.fetchone()
            return str(int(r[0])) if r else '0'
        except Exception:
            return '0'

    # ── Базовые данные из users ──
    try:
        row = db.get_user(user_id)
        if row:
            result['blns']  = str(int(float(row.get('balance', 0) or 0)))
            result['tgun']  = row.get('first_name', '') or ''
            nn = row.get('username', '')
            result['nn']    = f'@{nn}' if nn else result['tgun']
            joined = str(row.get('joined_at', '') or '')
            if joined:
                try:
                    jdt = datetime.fromisoformat(joined.split('.')[0])
                    result['d']  = str((datetime.now() - jdt).days)
                    result['jt'] = jdt.strftime('%d.%m.%Y')
                except Exception:
                    result['d']  = '?'
                    result['jt'] = '?'
    except Exception as e:
        logger.debug(f"_resolve_user_stats users: {e}")

    # ── Статистика сообщений ──
    result['msg']     = _stat('total_messages')
    result['msg_t']   = _stat('total_messages', today_str)
    result['msg_w']   = _stat('total_messages', week_ago)
    result['msg_m']   = _stat('total_messages', month_ago)
    result['msg_y']   = _stat('total_messages', year_ago)
    result['media_t'] = _stat('media_sent')
    result['media_w'] = _stat('media_sent', week_ago)
    result['media_m'] = _stat('media_sent', month_ago)
    result['media_y'] = _stat('media_sent', year_ago)
    result['w']       = _stat('warnings')

    # ── Место в рейтинге ──
    try:
        db.cursor.execute(
            'SELECT COUNT(*)+1 FROM users WHERE balance > '
            '(SELECT balance FROM users WHERE user_id=?) AND is_left=0 AND is_admin=0 AND is_owner=0',
            (user_id,))
        r = db.cursor.fetchone()
        result['plc'] = f'#{r[0]}' if r else '?'
    except Exception:
        result['plc'] = '?'

    # ── Количество рефералов ──
    try:
        db.cursor.execute('SELECT COUNT(*) FROM users WHERE referrer_id=?', (user_id,))
        r = db.cursor.fetchone()
        result['rfrl_c'] = str(r[0]) if r else '0'
    except Exception:
        result['rfrl_c'] = '0'

    # ── Данные из BBS-анкеты ──
    try:
        from handlers.BBS.database_bbs import get_profile
        profile = get_profile(db, user_id)
        if profile:
            result['un']  = profile.get('name', '') or ''
            result['yo']  = str(profile.get('age', '') or '')
            city_raw = profile.get('city', '')
            if isinstance(city_raw, str):
                try:
                    city_list = json.loads(city_raw)
                    result['city'] = ', '.join(city_list) if isinstance(city_list, list) else str(city_list)
                except Exception:
                    result['city'] = city_raw
            else:
                result['city'] = str(city_raw)
            roles_raw = profile.get('roles', '[]')
            if isinstance(roles_raw, str):
                try:
                    roles = json.loads(roles_raw)
                    result['sr'] = ', '.join(roles) if isinstance(roles, list) else str(roles)
                except Exception:
                    result['sr'] = roles_raw
            else:
                result['sr'] = str(roles_raw)
    except Exception as e:
        logger.debug(f"_resolve_user_stats bbs: {e}")

    return result


def _build_form(db, user_id: int, stats: dict) -> str:
    """Строит анкету пользователя для %act_form% / %rpl_form%."""
    prefs = _get_form_prefs(db, user_id)
    lines = []

    # Конфигурируемые (пользователь может скрыть)
    if prefs.get('show_un') and stats.get('un'):
        lines.append(f"📛 {stats['un']}")
    if prefs.get('show_city') and stats.get('city'):
        lines.append(f"📍 {stats['city']}")
    if prefs.get('show_yo') and stats.get('yo'):
        lines.append(f"🎂 {stats['yo']} лет")
    if prefs.get('show_sr') and stats.get('sr'):
        lines.append(f"🎭 {stats['sr']}")

    # Разделитель если есть конфигурируемые данные
    if lines:
        lines.append('—' * 12)

    # Всегда показываются
    if stats.get('d'):    lines.append(f"📅 В чате: {stats['d']} дн.")
    if stats.get('rnk'):  lines.append(f"🏅 Ранг: {stats['rnk']}")
    if stats.get('blns'): lines.append(f"💎 Баланс: {stats['blns']}")
    if stats.get('msg'):  lines.append(f"💬 Сообщений: {stats['msg']}")
    if stats.get('plc'):  lines.append(f"🏆 Место: {stats['plc']}")
    if stats.get('lvl'):  lines.append(f"⭐ Уровень: {stats['lvl']}")

    return '\n'.join(lines) if lines else '—'


# ═══════════════════════════════════════════════════════════════
#  МЕНЮ НАСТРОЕК АНКЕТЫ (для пользователя в ЛС бота)
# ═══════════════════════════════════════════════════════════════

FORM_FIELD_LABELS = {
    'show_un':   ('📛', 'Имя из анкеты'),
    'show_city': ('📍', 'Город'),
    'show_yo':   ('🎂', 'Возраст'),
    'show_sr':   ('🎭', 'Роль'),
}


async def show_form_settings(update_or_query, db, user_id: int, edit: bool = False) -> None:
    """Показывает меню настройки видимости полей анкеты в %_form%."""
    ensure_form_settings_table(db)
    prefs = _get_form_prefs(db, user_id)

    text = (
        "⚙️ <b>Настройка анкеты</b>\n\n"
        "Эти поля будут видны другим пользователям когда бот показывает твой профиль.\n\n"
        "<i>Всегда видны:</i> дней в чате, баланс, место в рейтинге, сообщения.\n\n"
        "Выбери что показывать:"
    )
    kb = []
    for field, (icon, label) in FORM_FIELD_LABELS.items():
        is_on = prefs.get(field, True)
        status = "🟢 Показывать" if is_on else "🔴 Скрыть"
        kb.append([IKB(f"{icon} {label}  —  {status}", callback_data=f"form_toggle_{field}")])
    kb.append([IKB("✅ Готово", callback_data="form_done")])

    markup = IKM(kb)
    try:
        if edit:
            await update_or_query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        else:
            await update_or_query.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        logger.error(f"show_form_settings: {e}")


async def handle_form_settings_callback(query, data: str, db, user_id: int) -> None:
    """Обрабатывает нажатия кнопок настройки анкеты."""
    if data == 'form_done':
        try:
            await query.edit_message_text(
                "✅ <b>Настройки анкеты сохранены!</b>\n\n"
                "Теперь когда бот выводит твой профиль, он будет учитывать эти настройки.",
                parse_mode='HTML',
            )
        except Exception:
            pass
        return

    if data.startswith('form_toggle_'):
        field = data[len('form_toggle_'):]
        if field not in FORM_FIELD_LABELS:
            return
        prefs = _get_form_prefs(db, user_id)
        new_val = not prefs.get(field, True)
        _set_form_pref(db, user_id, field, new_val)
        await show_form_settings(query, db, user_id, edit=True)


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

    # ── Новый формат: %act_X% и %rpl_X% ──
    if db and ('%act_' in text or '%rpl_' in text):
        act_id = user.id   if user   else None
        rpl_id = quoted.id if quoted else act_id

        act_stats = _resolve_user_stats(db, act_id) if act_id else {}
        rpl_stats = _resolve_user_stats(db, rpl_id) if rpl_id else {}

        # act_form / rpl_form — собираем отдельно
        if '%act_form%' in text:
            act_stats['form'] = _build_form(db, act_id, act_stats) if act_id else '—'
        if '%rpl_form%' in text:
            rpl_stats['form'] = _build_form(db, rpl_id, rpl_stats) if rpl_id else '—'

        for suffix, val in act_stats.items():
            text = text.replace(f'%act_{suffix}%', str(val))
        for suffix, val in rpl_stats.items():
            text = text.replace(f'%rpl_{suffix}%', str(val))

        # Убираем незаполненные %act_X% / %rpl_X% если данных нет
        text = re.sub(r'%(?:act|rpl)_[a-z_]+%', '', text)

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
