#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система триггеров v2 — полная реализация ТЗ блок 7.

Путь: handlers/triggers_handlers.py

Функционал:
  - Создание триггера (7.2): имя → ключевые слова → вероятность → удаление сообщ. бота
  - Меню настроек (7.3): условие, где, инициатор, цель, действия
  - Конфигурация действий (7.4): текст, медиа, мут, предупреждение, эмодзи и т.д.
  - Навигация (7.1): назад, сброс, пропустить, завершить
  - Список и управление (7.6): вкл/выкл, удалить, редактировать
  - Редактирование (7.5): изменение параметров существующего триггера
  - Движок (process_triggers): проверка сообщений + выполнение действий
"""

import json
import logging
import random
import re
import time
from datetime import datetime
from typing import Optional

from telegram import (
    Update, ChatPermissions,
    InlineKeyboardButton as IKB,
    InlineKeyboardMarkup as IKM,
)
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════

CONDITIONS = {
    'exact':       'Точное совпадение',
    'contains':    'Содержит',
    'starts_with': 'Начинается с',
    'ends_with':   'Заканчивается на',
    'whole_word':  'Целое слово',
}

INITIATORS = {
    'all':          '👥 Все',
    'users':        '👤 Только пользователи',
    'owner':        '👑 Владелец',
    'admins_owner': '🛡 Админы и владелец',
}

TARGETS = {
    'initiator': '🎯 На инициатора',
    'all':       '👥 На всех в чате',
    'specific':  '📌 На указанного пользователя',
    'random':    '🎲 На случайного пользователя',
    'admins':    '🛡 На администраторов',
    'nobody':    '💡 Ни на кого (информационное)',
}

ACTIONS_AVAILABLE = {
    'msg_chat':  '💬 Сообщение в чат',
    'msg_dm':    '✉️ Сообщение в ЛС',
    'rotation':  '🔁 Ротация',
    'pin':       '📌 Закрепление сообщения',
    'delete':    '🗑 Удалить сообщение',
    'warn':      '⚠️ Предупреждение',
    'mute':      '🔇 Мут',
    'emoji':     '😀 Отметить эмодзи',
}

MUTE_OPTIONS = {
    '5m':  ('🔇 5 мин',   300),
    '15m': ('🔇 15 мин',  900),
    '30m': ('🔇 30 мин',  1800),
    '60m': ('🔇 60 мин',  3600),
    '24h': ('🔇 24 часа', 86400),
}

DELETE_OPTIONS = {
    'trigger_word': '💬 Слово-триггер',
    'user_message': '📝 Сообщение пользователя',
}

# Эскалация предупреждений (7.4.6.1)
WARN_ESCALATION = [
    (3,  300),    # 3 → мут 5 мин
    (5,  900),    # 5 → мут 15 мин
    (10, 3600),   # 10 → мут 60 мин
    (15, 10800),  # 15 → мут 3 часа
]

# Шаги создания (для навигации «назад»)
CREATION_STEPS = ['name', 'keywords', 'probability', 'bot_delete', 'menu']

BOT_DEL_OPTIONS = {
    'no':              '❌ Нет',
    'period':          '⏱ Период',
    'previous':        '🔄 Предыдущее',
    'previous_period': '🔄⏱ Предыдущ. + период',
}


# ═══════════════════════════════════════════════════════════════
#  FSM — СОСТОЯНИЯ И ХЕЛПЕРЫ
# ═══════════════════════════════════════════════════════════════

class TS:
    """Trigger FSM States."""
    # Создание (sequential)
    NAME               = 'tg_name'
    KEYWORDS           = 'tg_keywords'
    PROBABILITY        = 'tg_probability'
    BOT_DEL_PERIOD     = 'tg_bot_del_period'
    # Конфигурация действий
    ACT_CHAT_TEXT      = 'tg_act_chat_text'
    ACT_CHAT_MEDIA     = 'tg_act_chat_media'
    ACT_DM_TEXT        = 'tg_act_dm_text'
    ACT_DM_MEDIA       = 'tg_act_dm_media'
    ACT_ROT_TEXT       = 'tg_act_rot_text'
    ACT_ROT_MEDIA      = 'tg_act_rot_media'
    ACT_EMOJI          = 'tg_act_emoji'
    ACT_WARN_PERIOD    = 'tg_act_warn_period'
    ACT_DELAYED_TIME   = 'tg_act_delayed_time'
    # Кнопки-ссылки
    ACT_BTN_TEXT       = 'tg_act_btn_text'
    ACT_BTN_URL        = 'tg_act_btn_url'
    # Лимиты
    ACT_FIRE_LIMIT     = 'tg_act_fire_limit'
    # Редактирование
    EDIT_NAME          = 'tg_edit_name'
    EDIT_KW_ADD        = 'tg_edit_kw_add'
    EDIT_KW_DEL        = 'tg_edit_kw_del'
    EDIT_PROBABILITY   = 'tg_edit_prob'
    EDIT_BOT_DEL_PERIOD = 'tg_edit_bot_del_period'
    EDIT_ACT_CHAT_TEXT = 'tg_edit_act_chat_text'
    EDIT_ACT_DM_TEXT   = 'tg_edit_act_dm_text'
    EDIT_ACT_EMOJI     = 'tg_edit_act_emoji'
    EDIT_ACT_WARN_PERIOD = 'tg_edit_act_warn_period'


def _get_state(ctx) -> Optional[str]:
    return ctx.user_data.get('trigger_state')

def _set_state(ctx, state: Optional[str]):
    if state is None:
        ctx.user_data.pop('trigger_state', None)
    else:
        ctx.user_data['trigger_state'] = state

def _get_data(ctx) -> dict:
    if 'trigger_data' not in ctx.user_data:
        ctx.user_data['trigger_data'] = _default_data()
    return ctx.user_data['trigger_data']

def _set_data(ctx, data: dict):
    ctx.user_data['trigger_data'] = data

def _clear_fsm(ctx):
    ctx.user_data.pop('trigger_state', None)
    ctx.user_data.pop('trigger_data', None)
    ctx.user_data.pop('trigger_bot_msg', None)
    ctx.user_data.pop('trigger_step', None)
    ctx.user_data.pop('trigger_edit_id', None)
    ctx.user_data.pop('owner_awaiting', None)
    ctx.user_data.pop('trigger_configuring_action', None)
    ctx.user_data.pop('trigger_rotation_slot', None)
    ctx.user_data.pop('trigger_btn_action', None)
    ctx.user_data.pop('trigger_btn_text_tmp', None)

def _default_data() -> dict:
    return {
        'name': None,
        'keywords': None,
        'probability': 100,
        'condition': 'contains',
        'where_fires': 'all',
        'initiator': 'all',
        'target': 'nobody',
        'target_user': None,
        'actions': [],
        'action_configs': {},
        'bot_msg_delete': 'no',
        'bot_msg_delete_after': None,
        'warn_period': None,
        'delayed_enabled': False,
        'delayed_configs': {},
        'fire_limit': None,
        'auto_pin': 0,
    }


def _nav_buttons(step: str, show_skip: bool = False) -> list:
    """Кнопки навигации для текущего шага."""
    row = []
    idx = CREATION_STEPS.index(step) if step in CREATION_STEPS else -1
    if idx > 0:
        row.append(IKB("◀ Назад", callback_data="trigger_back"))
    elif idx == 0:
        row.append(IKB("◀ Назад в меню", callback_data="trigger_back_to_menu"))
    row.append(IKB("❌ Сброс", callback_data="trigger_reset"))
    if show_skip:
        row.append(IKB("⏩ Пропустить", callback_data="trigger_skip"))
    return row


# ═══════════════════════════════════════════════════════════════
#  UI ХЕЛПЕР — единое сообщение бота
# ═══════════════════════════════════════════════════════════════

async def _send_step(src, ctx, text: str, keyboard: list, chat_id: int = None):
    """
    Отправить или отредактировать сообщение бота для текущего шага.
    src: CallbackQuery или Message (от пользователя).
    """
    markup = IKM(keyboard) if keyboard else None

    # CallbackQuery — просто edit
    if hasattr(src, 'edit_message_text'):
        try:
            await src.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
            return
        except Exception as e:
            if 'not modified' in str(e).lower():
                return
            chat_id = chat_id or src.message.chat.id

    # Message от пользователя — удалить его, обновить bot msg
    if hasattr(src, 'delete'):
        try:
            await src.delete()
        except Exception:
            pass
        chat_id = chat_id or src.chat.id

    # Пробуем edit существующего bot message
    bot_msg_id = ctx.user_data.get('trigger_bot_msg')
    if bot_msg_id and chat_id:
        try:
            bot = ctx.bot if hasattr(ctx, 'bot') else ctx.application.bot
            await bot.edit_message_text(
                chat_id=chat_id, message_id=bot_msg_id,
                text=text, parse_mode='HTML', reply_markup=markup
            )
            return
        except Exception:
            pass

    # Fallback — новое сообщение
    if chat_id:
        bot = ctx.bot if hasattr(ctx, 'bot') else ctx.application.bot
        msg = await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=markup)
        ctx.user_data['trigger_bot_msg'] = msg.message_id


# ═══════════════════════════════════════════════════════════════
#  БД — ТАБЛИЦЫ И МИГРАЦИЯ
# ═══════════════════════════════════════════════════════════════

def ensure_trigger_tables(db) -> None:
    """Создаёт таблицы и мигрирует схему."""
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
                PRIMARY KEY (user_id, trigger_id)
            )
        ''')
        db.conn.commit()
        _migrate_trigger_columns(db)
    except Exception as e:
        logger.error(f"ensure_trigger_tables error: {e}")


def _migrate_trigger_columns(db):
    """Добавляет новые колонки v2 к существующей таблице."""
    new_cols = [
        ("where_fires",          "TEXT DEFAULT 'all'"),
        ("initiator",            "TEXT DEFAULT 'all'"),
        ("target",               "TEXT DEFAULT 'nobody'"),
        ("target_user",          "TEXT"),
        ("actions",              "TEXT DEFAULT '[]'"),
        ("action_configs",       "TEXT DEFAULT '{}'"),
        ("bot_msg_delete",       "TEXT DEFAULT 'no'"),
        ("bot_msg_delete_after", "INTEGER"),
        ("warn_period",          "INTEGER"),
        ("delayed_configs",      "TEXT DEFAULT '{}'"),
        ("last_bot_msg_id",      "INTEGER"),
        ("last_bot_msg_chat",    "INTEGER"),
        ("fire_limit",           "INTEGER DEFAULT NULL"),
        ("fire_count",           "INTEGER DEFAULT 0"),
        ("auto_pin",             "INTEGER DEFAULT 0"),
    ]
    for col_name, col_def in new_cols:
        try:
            db.cursor.execute(f"ALTER TABLE triggers ADD COLUMN {col_name} {col_def}")
            db.conn.commit()
        except Exception:
            pass  # Колонка уже существует

    # Миграция: old action → new actions JSON
    try:
        db.cursor.execute("SELECT id, action, actions FROM triggers")
        for row in db.cursor.fetchall():
            actions_json = row['actions'] if row['actions'] else '[]'
            try:
                acts = json.loads(actions_json)
            except (json.JSONDecodeError, TypeError):
                acts = []
            if not acts and row['action']:
                old = row['action']
                new_acts = {'reply': ['msg_chat'], 'delete': ['delete'], 'warn': ['warn'],
                            'mute_5m': ['mute'], 'mute_1h': ['mute'], 'mute_1d': ['mute'],
                            'kick': ['delete'], 'ban': ['delete']}.get(old, [old])
                db.cursor.execute(
                    "UPDATE triggers SET actions = ? WHERE id = ?",
                    (json.dumps(new_acts), row['id'])
                )
        db.conn.commit()
    except Exception as e:
        logger.debug(f"Migration action→actions: {e}")


# ═══════════════════════════════════════════════════════════════
#  БД — CRUD
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

def _delete_trigger(db, trigger_id: int):
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

def _actions_to_legacy(actions: list) -> str:
    if 'delete' in actions: return 'delete'
    if 'mute' in actions: return 'mute_1h'
    if 'msg_chat' in actions: return 'reply'
    if 'warn' in actions: return 'warn'
    return 'delete'

def _save_trigger(db, data: dict, created_by: int) -> int:
    data = _normalize_rotation_action(dict(data))
    ensure_trigger_tables(db)
    db.cursor.execute('''
        INSERT INTO triggers
        (name, keywords, condition, probability,
         where_fires, initiator, target, target_user,
         actions, action_configs,
         bot_msg_delete, bot_msg_delete_after,
         warn_period, delayed_configs,
         action, action_value, is_enabled, created_by,
         fire_limit, fire_count, auto_pin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 0, ?)
    ''', (
        data['name'], data['keywords'],
        data.get('condition', 'contains'), data.get('probability', 100),
        data.get('where_fires', 'all'), data.get('initiator', 'all'),
        data.get('target', 'nobody'), data.get('target_user'),
        json.dumps(data.get('actions', [])),
        json.dumps(data.get('action_configs', {})),
        data.get('bot_msg_delete', 'no'), data.get('bot_msg_delete_after'),
        data.get('warn_period'),
        json.dumps(data.get('delayed_configs', {})),
        _actions_to_legacy(data.get('actions', [])),
        data.get('action_configs', {}).get('msg_chat', {}).get('text', ''),
        created_by,
        data.get('fire_limit'),
        data.get('auto_pin', 0),
    ))
    db.conn.commit()
    return db.cursor.lastrowid

def _update_trigger(db, trigger_id: int, data: dict):
    data = _normalize_rotation_action(dict(data))
    db.cursor.execute('''
        UPDATE triggers SET
            name=?, keywords=?, condition=?, probability=?,
            where_fires=?, initiator=?, target=?, target_user=?,
            actions=?, action_configs=?,
            bot_msg_delete=?, bot_msg_delete_after=?,
            warn_period=?, delayed_configs=?,
            action=?, action_value=?,
            fire_limit=?, auto_pin=?
        WHERE id=?
    ''', (
        data['name'], data['keywords'],
        data.get('condition', 'contains'), data.get('probability', 100),
        data.get('where_fires', 'all'), data.get('initiator', 'all'),
        data.get('target', 'nobody'), data.get('target_user'),
        json.dumps(data.get('actions', [])),
        json.dumps(data.get('action_configs', {})),
        data.get('bot_msg_delete', 'no'), data.get('bot_msg_delete_after'),
        data.get('warn_period'),
        json.dumps(data.get('delayed_configs', {})),
        _actions_to_legacy(data.get('actions', [])),
        data.get('action_configs', {}).get('msg_chat', {}).get('text', ''),
        data.get('fire_limit'),
        data.get('auto_pin', 0),
        trigger_id,
    ))
    db.conn.commit()

def _trigger_to_data(t) -> dict:
    """Конвертирует sqlite3.Row в trigger_data dict."""
    def _json(val, default):
        if not val: return default
        try: return json.loads(val)
        except (json.JSONDecodeError, TypeError): return default

    def _safe_int(val, default=None):
        if val is None: return default
        try: return int(val)
        except (TypeError, ValueError): return default

    data = {
        'name': t['name'],
        'keywords': t['keywords'],
        'probability': t['probability'] if t['probability'] is not None else 100,
        'condition': t['condition'] or 'contains',
        'where_fires': t['where_fires'] or 'all',
        'initiator': t['initiator'] or 'all',
        'target': t['target'] or 'nobody',
        'target_user': t['target_user'],
        'actions': _json(t['actions'], []),
        'action_configs': _json(t['action_configs'], {}),
        'bot_msg_delete': t['bot_msg_delete'] or 'no',
        'bot_msg_delete_after': t['bot_msg_delete_after'],
        'warn_period': t['warn_period'],
        'delayed_enabled': bool(_json(t['delayed_configs'], {})),
        'delayed_configs': _json(t['delayed_configs'], {}),
        'fire_limit': _safe_int(t['fire_limit'] if 'fire_limit' in t.keys() else None),
        'auto_pin': _safe_int(t['auto_pin'] if 'auto_pin' in t.keys() else 0, default=0),
    }
    return _normalize_rotation_action(data)

def _increment_violation(db, user_id: int, trigger_id: int) -> int:
    db.cursor.execute(
        'SELECT count FROM trigger_violations WHERE user_id=? AND trigger_id=?',
        (user_id, trigger_id)
    )
    row = db.cursor.fetchone()
    if row:
        new_count = row['count'] + 1
        db.cursor.execute(
            'UPDATE trigger_violations SET count=?, last_violation_at=CURRENT_TIMESTAMP '
            'WHERE user_id=? AND trigger_id=?', (new_count, user_id, trigger_id)
        )
    else:
        new_count = 1
        db.cursor.execute(
            'INSERT INTO trigger_violations (user_id, trigger_id, count) VALUES (?,?,1)',
            (user_id, trigger_id)
        )
    db.conn.commit()
    return new_count

def _get_violations_in_period(db, user_id: int, trigger_id: int, period_sec) -> int:
    """Количество нарушений за период. Если период истёк — сброс."""
    if not period_sec:
        return _increment_violation(db, user_id, trigger_id)
    db.cursor.execute(
        "SELECT count, last_violation_at FROM trigger_violations WHERE user_id=? AND trigger_id=?",
        (user_id, trigger_id)
    )
    row = db.cursor.fetchone()
    if row and row['last_violation_at']:
        try:
            last_dt = datetime.fromisoformat(str(row['last_violation_at']))
            if (datetime.now() - last_dt).total_seconds() > period_sec:
                db.cursor.execute(
                    "UPDATE trigger_violations SET count=1, last_violation_at=CURRENT_TIMESTAMP "
                    "WHERE user_id=? AND trigger_id=?", (user_id, trigger_id)
                )
                db.conn.commit()
                return 1
        except Exception:
            pass
    return _increment_violation(db, user_id, trigger_id)

def _reset_violations(db, user_id: int, trigger_id: int):
    db.cursor.execute('DELETE FROM trigger_violations WHERE user_id=? AND trigger_id=?',
                      (user_id, trigger_id))
    db.conn.commit()

def _user_link(user) -> str:
    name = user.first_name or "Пользователь"
    return f'<a href="tg://user?id={user.id}">{name}</a>'


# ═══════════════════════════════════════════════════════════════
#  ФОРМАТИРОВАНИЕ ДЛИТЕЛЬНОСТИ
# ═══════════════════════════════════════════════════════════════

def _format_duration(seconds) -> str:
    if not seconds: return '—'
    seconds = int(seconds)
    if seconds < 3600: return f"{seconds // 60} мин"
    if seconds < 86400: return f"{seconds // 3600} ч"
    return f"{seconds // 86400} дн"

def _parse_duration_input(text: str) -> Optional[int]:
    """Парсит '30 мин', '2 часа', '1 день', '30' (→ минуты)."""
    text = text.lower().strip()
    try:
        return int(text) * 60
    except ValueError:
        pass
    m = re.match(r'(\d+)\s*(мин|м|min|час|ч|h|день|дн|д|day|d)', text)
    if m:
        val = int(m.group(1))
        u = m.group(2)
        if u in ('мин', 'м', 'min'): return val * 60
        if u in ('час', 'ч', 'h'): return val * 3600
        if u in ('день', 'дн', 'д', 'day', 'd'): return val * 86400
    return None


# ═══════════════════════════════════════════════════════════════
#  ГЛАВНОЕ МЕНЮ ТРИГГЕРОВ
# ═══════════════════════════════════════════════════════════════

async def show_triggers_menu(query, db, admin_id: int) -> None:
    ensure_trigger_tables(db)
    triggers = _get_all_triggers(db)
    total = len(triggers)
    enabled = sum(1 for t in triggers if t['is_enabled'])

    text = (
        f"⚡ <b>ТРИГГЕРЫ</b>\n\n"
        f"📊 Всего: <b>{total}</b> | Активных: <b>{enabled}</b>\n"
    )
    keyboard = [
        [IKB("🔔 Создать", callback_data="trigger_create")],
        [IKB("⚡ Быстротриг (скоро)", callback_data="trigger_quicktrig")],
        [IKB("📰 Список", callback_data="trigger_list")],
        [IKB("🔙 Назад", callback_data="panel_main")],
    ]
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=IKM(keyboard))
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"show_triggers_menu: {e}")


# ═══════════════════════════════════════════════════════════════
#  СОЗДАНИЕ — ШАГИ 1-4 (7.2)
# ═══════════════════════════════════════════════════════════════

async def _step_name(src, ctx, db=None):
    _set_state(ctx, TS.NAME)
    ctx.user_data['trigger_step'] = 'name'
    data = _get_data(ctx)
    cur = f"\nТекущее: <b>{data['name']}</b>" if data.get('name') else ""
    text = (
        f"⚡ <b>Создание триггера</b> — Шаг 1/4\n\n"
        f"Введите <b>название</b> триггера:\n"
        f"<i>(Для отображения в списке, например: «Спам-ссылки»)</i>{cur}"
    )
    await _send_step(src, ctx, text, [_nav_buttons('name')])

async def _step_keywords(src, ctx):
    _set_state(ctx, TS.KEYWORDS)
    ctx.user_data['trigger_step'] = 'keywords'
    data = _get_data(ctx)
    cur = f"\nТекущие: <code>{data['keywords']}</code>" if data.get('keywords') else ""
    text = (
        f"⚡ <b>Создание триггера</b> — Шаг 2/4\n\n"
        f"Введите <b>ключевые слова</b> через запятую:\n"
        f"<i>(Пример: спам, реклама, подписывайся)</i>{cur}"
    )
    await _send_step(src, ctx, text, [_nav_buttons('keywords')])

async def _step_probability(src, ctx):
    _set_state(ctx, TS.PROBABILITY)
    ctx.user_data['trigger_step'] = 'probability'
    data = _get_data(ctx)
    text = (
        f"⚡ <b>Создание триггера</b> — Шаг 3/4\n\n"
        f"Введите <b>вероятность срабатывания</b> (0–100%):\n"
        f"<i>Текущее: {data.get('probability', 100)}%</i>"
    )
    await _send_step(src, ctx, text, [_nav_buttons('probability', show_skip=True)])

async def _step_bot_delete(src, ctx):
    _set_state(ctx, None)
    ctx.user_data['trigger_step'] = 'bot_delete'
    data = _get_data(ctx)
    cur = BOT_DEL_OPTIONS.get(data.get('bot_msg_delete', 'no'), '❌ Нет')
    text = (
        f"⚡ <b>Создание триггера</b> — Шаг 4/4\n\n"
        f"<b>Удаление сообщения бота</b> после срабатывания:\n"
        f"<i>Текущее: {cur}</i>\n\n"
        f"• <b>Нет</b> — сообщение остаётся\n"
        f"• <b>Период</b> — удалить через время\n"
        f"• <b>Предыдущее</b> — удалить предыдущее сообщ. бота сразу\n"
        f"• <b>Предыдущ.+период</b> — удалить предыдущее через время"
    )
    keyboard = [
        [IKB("❌ Нет", callback_data="trigger_botdel_no"),
         IKB("⏱ Период", callback_data="trigger_botdel_period")],
        [IKB("🔄 Предыдущее", callback_data="trigger_botdel_prev"),
         IKB("🔄⏱ Предыдущ.+период", callback_data="trigger_botdel_prevperiod")],
        _nav_buttons('bot_delete', show_skip=True),
    ]
    await _send_step(src, ctx, text, keyboard)


# ═══════════════════════════════════════════════════════════════
#  МЕНЮ НАСТРОЕК (7.3) — хаб
# ═══════════════════════════════════════════════════════════════

async def _show_settings_menu(src, ctx):
    _set_state(ctx, None)
    ctx.user_data['trigger_step'] = 'menu'
    data = _get_data(ctx)

    cond = CONDITIONS.get(data.get('condition', 'contains'), '?')
    where = 'Во всём чате' if data.get('where_fires', 'all') == 'all' else 'Выбранные ветки'
    init = INITIATORS.get(data.get('initiator', 'all'), '?')
    tgt = TARGETS.get(data.get('target', 'nobody'), '?')
    acts = data.get('actions', [])
    visible_acts = _visible_actions(acts)
    acts_str = ', '.join(ACTIONS_AVAILABLE.get(a, a) for a in visible_acts) if visible_acts else '<i>не выбрано</i>'

    fire_limit = data.get('fire_limit')
    fire_lbl = f"{fire_limit}" if fire_limit is not None else "∞"
    auto_pin = data.get('auto_pin', 0)
    pin_lbl = "✅ Да" if auto_pin else "❌ Нет"

    text = (
        f"⚡ <b>Настройки «{data.get('name', '?')}»</b>\n\n"
        f"🔍 Условие: <b>{cond}</b>\n"
        f"📍 Где: <b>{where}</b>\n"
        f"👤 Инициатор: <b>{init}</b>\n"
        f"🎯 Цель: <b>{tgt}</b>\n"
        f"⚡ Действия: {acts_str}\n"
        f"🔢 Лимит срабатываний: <b>{fire_lbl}</b>\n"
        f"📌 Автозакреп ответа: <b>{pin_lbl}</b>\n\n"
        f"<i>Настройте параметры или 💾 Завершить</i>"
    )
    keyboard = [
        [IKB(f"🔍 Условие: {cond}", callback_data="trigger_set_cond")],
        [IKB(f"📍 Где: {where}", callback_data="trigger_set_where")],
        [IKB(f"👤 Инициатор", callback_data="trigger_set_init")],
        [IKB(f"🎯 Цель", callback_data="trigger_set_target")],
        [IKB(f"⚡ Действия ({len(visible_acts)})", callback_data="trigger_set_actions")],
        [IKB(f"🔢 Лимит: {fire_lbl}", callback_data="trigger_set_firelimit"),
         IKB(f"📌 Автозакреп: {pin_lbl}", callback_data="trigger_set_autopin")],
        [IKB("💾 Завершить", callback_data="trigger_finish")],
        [IKB("❌ Сброс", callback_data="trigger_reset")],
    ]
    await _send_step(src, ctx, text, keyboard)


# ═══════════════════════════════════════════════════════════════
#  ПОДМЕНЮ НАСТРОЕК (7.3.1 — 7.3.5)
# ═══════════════════════════════════════════════════════════════

async def _show_condition_menu(src, ctx):
    data = _get_data(ctx)
    cur = data.get('condition', 'contains')
    text = "🔍 <b>Выберите условие совпадения:</b>"
    kb = [[IKB(f"{v}{' ✅' if k == cur else ''}", callback_data=f"trigger_cond_{k}")]
          for k, v in CONDITIONS.items()]
    kb.append([IKB("◀ Назад к меню", callback_data="trigger_menu")])
    await _send_step(src, ctx, text, kb)

async def _show_where_menu(src, ctx, db=None):
    data = _get_data(ctx)
    cur = data.get('where_fires', 'all')
    text = "📍 <b>Где срабатывает триггер:</b>\n\n<i>По умолчанию — во всём чате</i>"
    kb = [
        [IKB(f"🌐 Во всём чате{' ✅' if cur == 'all' else ''}", callback_data="trigger_where_all")],
        [IKB(f"📂 Выбор веток{' ✅' if cur != 'all' else ''}", callback_data="trigger_where_topics")],
        [IKB("◀ Назад к меню", callback_data="trigger_menu")],
    ]
    await _send_step(src, ctx, text, kb)


async def _show_topics_select(src, ctx, db, page=0):
    """Показать список веток чата для множественного выбора (с пагинацией)."""
    from config import CHAT_ID
    TOPICS_PER_PAGE = 15
    data = _get_data(ctx)

    # Текущий выбор
    cur = data.get('where_fires', 'all')
    selected_ids = []
    if cur != 'all':
        try:
            selected_ids = json.loads(cur) if isinstance(cur, str) else cur
            if not isinstance(selected_ids, list):
                selected_ids = []
        except (json.JSONDecodeError, TypeError):
            selected_ids = []

    # Получаем ветки из БД
    topics = db.get_all_topics(CHAT_ID) if CHAT_ID else []

    if not topics:
        text = "📂 <b>Выбор веток</b>\n\n<i>Ветки не найдены. Бот запоминает ветки автоматически при получении сообщений.</i>"
        kb = [[IKB("◀ Назад", callback_data="trigger_set_where")]]
        await _send_step(src, ctx, text, kb)
        return

    total = len(topics)
    total_pages = (total + TOPICS_PER_PAGE - 1) // TOPICS_PER_PAGE
    page = max(0, min(page, total_pages - 1))

    start = page * TOPICS_PER_PAGE
    end = min(start + TOPICS_PER_PAGE, total)
    page_topics = topics[start:end]

    sel_count = len(selected_ids)
    page_info = f" (стр. {page + 1}/{total_pages})" if total_pages > 1 else ""
    sel_info = f"\nВыбрано: {sel_count}" if sel_count else ""
    text = (
        f"📂 <b>Выбор веток</b>{page_info}\n\n"
        f"<i>Нажмите на ветку чтобы вкл/выкл.\n"
        f"Затем «✅ Готово».</i>{sel_info}"
    )
    kb = []
    for t in page_topics:
        tid = t['thread_id']
        raw_name = t['thread_name'] or ''
        if tid is None:
            # Главный чат (thread_id IS NULL)
            name = "💬 Главный чат"
        elif raw_name and not raw_name.startswith('Ветка #') and not raw_name.startswith('Ветка '):
            # Реальное название ветки из БД
            name = f"📂 {raw_name}"
        else:
            # Ветка без красивого имени — показываем ID
            name = f"📂 Ветка #{tid}"
        mark = " ✅" if tid in selected_ids else ""
        # callback_data: thread_id или 0 для главного чата
        cb_id = tid if tid is not None else 0
        # Обрезаем длинные названия
        display = name[:30] + "…" if len(name) > 30 else name
        kb.append([IKB(f"{display}{mark}", callback_data=f"trigger_wt_{cb_id}")])

    # Навигация по страницам
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(IKB("◀ Пред.", callback_data=f"trigger_wtp_{page - 1}"))
        if page < total_pages - 1:
            nav.append(IKB("След. ▶", callback_data=f"trigger_wtp_{page + 1}"))
        kb.append(nav)

    # Сохраняем текущую страницу для восстановления после toggle
    ctx.user_data['trigger_topics_page'] = page

    kb.append([IKB("✅ Готово", callback_data="trigger_wt_done")])
    kb.append([IKB("◀ Назад", callback_data="trigger_set_where")])
    await _send_step(src, ctx, text, kb)

async def _show_initiator_menu(src, ctx):
    data = _get_data(ctx)
    cur = data.get('initiator', 'all')
    text = "👤 <b>На кого реагирует триггер:</b>\n\n<i>По умолчанию — на всех</i>"
    kb = [[IKB(f"{v}{' ✅' if k == cur else ''}", callback_data=f"trigger_init_{k}")]
          for k, v in INITIATORS.items()]
    kb.append([IKB("◀ Назад к меню", callback_data="trigger_menu")])
    await _send_step(src, ctx, text, kb)

async def _show_target_menu(src, ctx):
    data = _get_data(ctx)
    cur = data.get('target', 'nobody')
    text = "🎯 <b>На кого распространяется действие:</b>\n\n<i>По умолчанию — ни на кого</i>"
    kb = [[IKB(f"{v}{' ✅' if k == cur else ''}", callback_data=f"trigger_tgt_{k}")]
          for k, v in TARGETS.items()]
    kb.append([IKB("◀ Назад к меню", callback_data="trigger_menu")])
    await _send_step(src, ctx, text, kb)

async def _show_actions_menu(src, ctx):
    data = _get_data(ctx)
    selected = data.get('actions', [])
    text = (
        "⚡ <b>Выберите действия</b> (множественный выбор):\n\n"
        "<i>Нажмите чтобы вкл/выкл. «⚙» — настройка. «✅ Готово» — вернуться.</i>"
    )
    kb = []
    for key, label in ACTIONS_AVAILABLE.items():
        if key == 'rotation':
            continue
        mark = " ✅" if key in selected else ""
        row = [IKB(f"{label}{mark}", callback_data=f"trigger_act_{key}")]
        if key in selected and key in ('msg_chat', 'msg_dm', 'mute', 'warn', 'emoji', 'delete', 'pin'):
            row.append(IKB("⚙", callback_data=f"trigger_acfg_{key}"))
        kb.append(row)
    kb.append([IKB("✅ Готово", callback_data="trigger_actdone")])
    kb.append([IKB("◀ Назад к меню", callback_data="trigger_menu")])
    await _send_step(src, ctx, text, kb)


def _get_rotation_items(data: dict) -> list:
    cfgs = data.get('action_configs', {})
    rot = cfgs.get('rotation', {})
    items = rot.get('items', []) if isinstance(rot, dict) else []
    if not isinstance(items, list):
        items = []
    return items[:5]


def _set_rotation_items(data: dict, items: list):
    cfgs = data.get('action_configs', {})
    rot = cfgs.get('rotation', {}) if isinstance(cfgs.get('rotation', {}), dict) else {}
    rot['items'] = items[:5]
    if not isinstance(rot.get('next_idx', 0), int):
        rot['next_idx'] = 0
    cfgs['rotation'] = rot
    data['action_configs'] = cfgs


def _ensure_rotation_slot(data: dict, slot: int) -> dict:
    items = _get_rotation_items(data)
    while len(items) < slot:
        items.append({})
    _set_rotation_items(data, items)
    return items[slot - 1]


def _visible_actions(actions: list) -> list:
    """Действия для UI без скрытой служебной ротации."""
    return [action for action in actions if action != 'rotation']


def _rotation_items_for_trigger(tdata: dict) -> list:
    cfgs = tdata.get('action_configs', {}) if isinstance(tdata, dict) else {}
    rot = cfgs.get('rotation', {}) if isinstance(cfgs.get('rotation', {}), dict) else {}
    items = rot.get('items', []) if isinstance(rot, dict) else []
    if not isinstance(items, list):
        return []
    return [item for item in items[:5] if isinstance(item, dict) and (item.get('text') or item.get('media_id'))]


def _normalize_rotation_action(data: dict) -> dict:
    """Ротация живет внутри msg_chat, а не отдельным действием."""
    actions = list(data.get('actions', []))
    rotation_items = _get_rotation_items(data)
    has_rotation = any(item.get('text') or item.get('media_id') for item in rotation_items)

    if 'rotation' in actions:
        actions = [action for action in actions if action != 'rotation']

    if has_rotation and 'msg_chat' not in actions:
        actions.append('msg_chat')

    data['actions'] = actions
    return data


async def _execute_rotation_action(context, db, trigger, cfgs, message):
    rot_cfg = cfgs.get('rotation', {}) if isinstance(cfgs.get('rotation', {}), dict) else {}
    items = rot_cfg.get('items', []) if isinstance(rot_cfg.get('items', []), list) else []
    items = [i for i in items[:5] if isinstance(i, dict) and (i.get('text') or i.get('media_id'))]
    if not items:
        return None

    next_idx = rot_cfg.get('next_idx', 0)
    if not isinstance(next_idx, int):
        next_idx = 0
    idx = next_idx % len(items)
    item_cfg = items[idx]

    bot_msg = await _send_action_message(
        bot=context.bot,
        chat_id=message.chat.id,
        thread_id=getattr(message, 'message_thread_id', None),
        text=(item_cfg.get('text') or '').strip(),
        act_cfg=item_cfg,
        parse_mode='HTML',
    )

    rot_cfg['next_idx'] = (idx + 1) % len(items)
    cfgs['rotation'] = rot_cfg
    try:
        db.cursor.execute(
            "UPDATE triggers SET action_configs=? WHERE id=?",
            (json.dumps(cfgs), trigger['id'])
        )
        db.conn.commit()
    except Exception as e:
        logger.warning(f"Rotation next_idx save failed: {e}")

    return bot_msg


async def _show_rotation_slot_menu(src, ctx, slot: int):
    data = _get_data(ctx)
    items = _get_rotation_items(data)
    cfg = items[slot - 1] if len(items) >= slot else {}
    txt = (cfg.get('text') or '<i>не задан</i>')[:150]
    has_media = '✅' if cfg.get('media_id') else '❌'
    mode = '🖼+📝 Одним сообщением' if cfg.get('media_pos', 'above') == 'above' else '📝 Потом 🖼 отдельным'
    text = (
        f"🔁 <b>Ротация — слот {slot}/5</b>\n\n"
        f"📝 Текст: {txt}\n"
        f"🖼 Медиа: {has_media}\n"
        f"📐 Режим: {mode}"
    )
    kb = [
        [IKB("📝 Задать текст", callback_data=f"trigger_acfg_rot_text_{slot}")],
        [IKB("🖼 Прикрепить медиа", callback_data=f"trigger_acfg_rot_media_{slot}")],
        [IKB("🖼+📝 Одним сообщением", callback_data=f"trigger_acfg_rot_above_{slot}")],
        [IKB("📝 Потом 🖼 отдельным", callback_data=f"trigger_acfg_rot_below_{slot}")],
        [IKB("🗑 Очистить слот", callback_data=f"trigger_acfg_rot_clear_{slot}")],
        [IKB("◀ К ротации", callback_data="trigger_acfg_rotation")],
    ]
    await _send_step(src, ctx, text, kb)


# ═══════════════════════════════════════════════════════════════
#  КНОПКИ-ССЫЛКИ ДЛЯ СООБЩЕНИЙ ТРИГГЕРА
# ═══════════════════════════════════════════════════════════════

async def _show_buttons_menu(src, ctx, action_key: str):
    """Показывает список URL-кнопок для действия msg_chat или msg_dm."""
    data = _get_data(ctx)
    cfgs = data.get('action_configs', {})
    cfg = cfgs.get(action_key, {})
    buttons = cfg.get('buttons', [])

    ctx.user_data['trigger_btn_action'] = action_key

    action_name = "в чат" if action_key == 'msg_chat' else "в ЛС"
    text = (
        f"🔘 <b>Кнопки-ссылки ({action_name})</b>\n\n"
        f"Добавьте кнопки с URL (до 5 шт).\n"
        f"Каждая кнопка — отдельная строка.\n\n"
    )
    if buttons:
        for i, btn in enumerate(buttons, 1):
            text += f"{i}. <b>{btn.get('text', '?')}</b> — <code>{btn.get('url', '?')}</code>\n"
    else:
        text += "<i>Кнопок пока нет.</i>"

    kb = []
    for i, btn in enumerate(buttons):
        kb.append([IKB(f"🗑 Удалить «{btn.get('text', '?')[:20]}»",
                       callback_data=f"trigger_acfg_btn_del_{i}")])
    if len(buttons) < 5:
        kb.append([IKB("➕ Добавить кнопку", callback_data="trigger_acfg_btn_add")])
    back_cb = "trigger_acfg_msg_chat" if action_key == 'msg_chat' else "trigger_acfg_msg_dm"
    kb.append([IKB("◀ Назад", callback_data=back_cb)])
    await _send_step(src, ctx, text, kb)


# ═══════════════════════════════════════════════════════════════
#  КОНФИГУРАЦИЯ ДЕЙСТВИЙ (7.4)
# ═══════════════════════════════════════════════════════════════

async def _configure_action(src, ctx, action: str):
    ctx.user_data['trigger_configuring_action'] = action
    data = _get_data(ctx)
    cfg = data.get('action_configs', {}).get(action, {})

    if action == 'msg_chat':
        cur_text = cfg.get('text', '<i>не задан</i>')
        has_media = '✅' if cfg.get('media_id') else '❌'
        pos = '🖼 Медиа + текст (одно сообщение)' if cfg.get('media_pos', 'above') == 'above' else '📝 Текст, затем 🖼 медиа'
        rot_items = _get_rotation_items(data)
        rot_ready = sum(1 for item in rot_items if item.get('text') or item.get('media_id'))
        rot_status = f"🔁 Ротация: {'✅' if rot_ready else '❌'} ({rot_ready}/5)"
        link_prev = cfg.get('link_preview', True)
        link_prev_icon = '✅' if link_prev else '❌'
        with_reply = cfg.get('reply_to_user', False)
        reply_icon = '✅' if with_reply else '❌'
        buttons = cfg.get('buttons', [])
        btn_count = len(buttons)
        text = (
            f"💬 <b>Сообщение в чат</b>\n\n"
            f"📝 Текст: {cur_text[:200]}\n"
            f"🖼 Медиа: {has_media}\n"
            f"📐 Режим: {pos}\n"
            f"{rot_status}\n"
            f"🔗 Превью ссылок: {link_prev_icon}\n"
            f"↩️ Реплай на сообщение: {reply_icon}\n"
            f"🔘 Кнопки-ссылки: <b>{btn_count}</b> шт."
        )
        kb = [
            [IKB("📝 Задать текст", callback_data="trigger_acfg_chat_text")],
            [IKB("🖼 Прикрепить медиа", callback_data="trigger_acfg_chat_media")],
            [IKB("🖼+📝 Одним сообщением", callback_data="trigger_acfg_media_above")],
            [IKB("📝 Потом 🖼 отдельным", callback_data="trigger_acfg_media_below")],
            [IKB(f"🔁 Ротация ({rot_ready}/5)", callback_data="trigger_acfg_rotation")],
            [IKB(f"{link_prev_icon} Превью ссылок", callback_data="trigger_acfg_link_preview_toggle"),
             IKB(f"{reply_icon} Реплай", callback_data="trigger_acfg_reply_toggle")],
            [IKB(f"🔘 Кнопки-ссылки ({btn_count})", callback_data="trigger_acfg_chat_buttons")],
            [IKB("◀ К действиям", callback_data="trigger_set_actions")],
        ]

    elif action == 'msg_dm':
        cur_text = cfg.get('text', '<i>не задан</i>')
        has_media = '✅' if cfg.get('media_id') else '❌'
        link_prev = cfg.get('link_preview', True)
        link_prev_icon = '✅' if link_prev else '❌'
        dm_buttons = cfg.get('buttons', [])
        dm_btn_count = len(dm_buttons)
        text = (
            f"✉️ <b>Сообщение в ЛС</b>\n\n"
            f"📝 Текст: {cur_text[:200]}\n"
            f"🖼 Медиа: {has_media}\n"
            f"🔗 Превью ссылок: {link_prev_icon}\n"
            f"🔘 Кнопки-ссылки: <b>{dm_btn_count}</b> шт."
        )
        kb = [
            [IKB("📝 Задать текст", callback_data="trigger_acfg_dm_text")],
            [IKB("🖼 Прикрепить медиа", callback_data="trigger_acfg_dm_media")],
            [IKB(f"{link_prev_icon} Превью ссылок", callback_data="trigger_acfg_link_preview_toggle")],
            [IKB(f"🔘 Кнопки-ссылки ({dm_btn_count})", callback_data="trigger_acfg_dm_buttons")],
            [IKB("◀ К действиям", callback_data="trigger_set_actions")],
        ]

    elif action == 'rotation':
        items = _get_rotation_items(data)
        ready = sum(1 for i in items if i.get('text') or i.get('media_id'))
        idx = cfg.get('next_idx', 0) if isinstance(cfg, dict) else 0
        text = (
            "🔁 <b>Ротация сообщений</b>\n\n"
            f"Слотов заполнено: <b>{ready}/5</b>\n"
            f"Следующий слот: <b>{(idx % max(1, len(items))) + 1 if items else 1}</b>\n\n"
            "<i>Настройте до 5 слотов (текст и/или медиа).</i>"
        )
        kb = []
        for n in range(1, 6):
            slot_cfg = items[n - 1] if len(items) >= n else {}
            mark = "✅" if slot_cfg.get('text') or slot_cfg.get('media_id') else "▫"
            kb.append([IKB(f"{mark} Слот {n}", callback_data=f"trigger_acfg_rot_slot_{n}")])
        kb.append([IKB("◀ К сообщению в чат", callback_data="trigger_acfg_msg_chat")])

    elif action == 'pin':
        notify = cfg.get('notify', False)
        text = f"📌 <b>Закрепление</b>\n\nУведомление: {'✅ Да' if notify else '❌ Нет'}"
        kb = [
            [IKB("✅ С уведомлением", callback_data="trigger_acfg_pin_yes"),
             IKB("❌ Без", callback_data="trigger_acfg_pin_no")],
            [IKB("◀ К действиям", callback_data="trigger_set_actions")],
        ]

    elif action == 'delete':
        what = cfg.get('what', [])
        text = "🗑 <b>Удалить сообщение</b>\n\nЧто удаляем? (множественный выбор):"
        kb = [[IKB(f"{v}{' ✅' if k in what else ''}", callback_data=f"trigger_acfg_del_{k}")]
              for k, v in DELETE_OPTIONS.items()]
        kb.append([IKB("✅ Готово", callback_data="trigger_acfg_del_done")])
        kb.append([IKB("◀ К действиям", callback_data="trigger_set_actions")])

    elif action == 'mute':
        cur = cfg.get('duration', '')
        text = "🔇 <b>Мут</b>\n\nВыберите длительность:"
        kb = [[IKB(f"{lbl}{' ✅' if k == cur else ''}", callback_data=f"trigger_acfg_mute_{k}")]
              for k, (lbl, _) in MUTE_OPTIONS.items()]
        kb.append([IKB("◀ К действиям", callback_data="trigger_set_actions")])

    elif action == 'warn':
        period = data.get('warn_period')
        p_str = _format_duration(period) if period else 'не задан'
        text = (
            f"⚠️ <b>Предупреждение</b>\n\n"
            f"Эскалация:\n"
            f"  3 → мут 5 мин\n  5 → мут 15 мин\n  10 → мут 60 мин\n  15 → мут 3 ч\n\n"
            f"📅 Период накопления: <b>{p_str}</b>"
        )
        kb = [
            [IKB("📅 Задать период", callback_data="trigger_acfg_warn_period")],
            [IKB("◀ К действиям", callback_data="trigger_set_actions")],
        ]

    elif action == 'emoji':
        cur = cfg.get('emoji', '<i>не выбран</i>')
        text = f"😀 <b>Эмодзи-реакция</b>\n\nТекущий: {cur}\n\nОтправьте нужный эмодзи:"
        _set_state(ctx, TS.ACT_EMOJI)
        kb = [[IKB("◀ К действиям", callback_data="trigger_set_actions")]]

    else:
        await _show_actions_menu(src, ctx)
        return

    await _send_step(src, ctx, text, kb)


# ═══════════════════════════════════════════════════════════════
#  СОХРАНЕНИЕ
# ═══════════════════════════════════════════════════════════════

async def _finish_and_save(src, ctx, db):
    data = _normalize_rotation_action(_get_data(ctx))
    _set_data(ctx, data)
    edit_id = ctx.user_data.get('trigger_edit_id')

    if not data.get('name'):
        if hasattr(src, 'answer'):
            await src.answer("❌ Не задано название.", show_alert=True)
        return
    if not data.get('keywords'):
        if hasattr(src, 'answer'):
            await src.answer("❌ Не заданы ключевые слова.", show_alert=True)
        return

    try:
        if edit_id:
            _update_trigger(db, edit_id, data)
            tid = edit_id
            msg = "✅ Триггер обновлён!"
        else:
            uid = src.from_user.id if hasattr(src, 'from_user') else 0
            tid = _save_trigger(db, data, uid)
            msg = "✅ Триггер создан!"

        _clear_fsm(ctx)
        if hasattr(src, 'answer'):
            await src.answer(msg, show_alert=True)
        await _show_trigger_detail(src, db, tid)
    except Exception as e:
        logger.error(f"Trigger save error: {e}")
        if hasattr(src, 'answer'):
            await src.answer(f"❌ Ошибка: {e}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
#  СПИСОК ТРИГГЕРОВ (7.6)
# ═══════════════════════════════════════════════════════════════

async def show_trigger_list(query, db, admin_id: int, ctx=None) -> None:
    ensure_trigger_tables(db)
    triggers = _get_all_triggers(db)

    if not triggers:
        text = "⚡ <b>Триггеры</b>\n\n<i>Список пуст.</i>"
        kb = [
            [IKB("🔔 Создать", callback_data="trigger_create")],
            [IKB("🔙 Назад", callback_data="owner_triggers")],
        ]
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=IKM(kb))
        return

    text = (
        "⚡ <b>СПИСОК ТРИГГЕРОВ</b>\n"
        "<i>Здесь можно редактировать, включать/выключать и удалять — просто нажмите на триггер.</i>\n\n"
    )
    expanded_id = ctx.user_data.get('trigger_list_expanded_id') if ctx else None
    kb = []
    for t in triggers:
        status = "✅" if t['is_enabled'] else "❌"
        tid = t['id']
        kb.append([IKB(t['name'], callback_data=f"trigger_expand_{tid}")])
        if expanded_id == tid:
            kb.append([
                IKB("✏️", callback_data=f"trigger_edit_{tid}"),
                IKB(status, callback_data=f"trigger_toggle_{tid}"),
                IKB("🚫", callback_data=f"trigger_del_{tid}"),
            ])
    kb.append([IKB("🔔 Создать", callback_data="trigger_create")])
    kb.append([IKB("🔙 Назад", callback_data="owner_triggers")])
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=IKM(kb))


# ═══════════════════════════════════════════════════════════════
#  ДЕТАЛИ ТРИГГЕРА
# ═══════════════════════════════════════════════════════════════

async def _show_trigger_detail(src, db, trigger_id: int):
    t = _get_trigger(db, trigger_id)
    if not t:
        if hasattr(src, 'answer'):
            await src.answer("❌ Триггер не найден.", show_alert=True)
        return

    data = _trigger_to_data(t)
    status = "✅ Включён" if t['is_enabled'] else "❌ Выключен"
    cond = CONDITIONS.get(data['condition'], data['condition'])
    init = INITIATORS.get(data['initiator'], data['initiator'])
    tgt = TARGETS.get(data['target'], data['target'])
    where = 'Во всём чате' if data['where_fires'] == 'all' else 'Выбранные ветки'
    acts = data.get('actions', [])
    visible_acts = _visible_actions(acts)
    acts_str = ', '.join(ACTIONS_AVAILABLE.get(a, a) for a in visible_acts) if visible_acts else '—'
    bot_del = BOT_DEL_OPTIONS.get(data.get('bot_msg_delete', 'no'), 'Нет')
    if data.get('bot_msg_delete') == 'period' and data.get('bot_msg_delete_after'):
        bot_del += f" ({_format_duration(data['bot_msg_delete_after'])})"

    text = (
        f"⚡ <b>{t['name']}</b>\n\n"
        f"📝 Слова: <code>{t['keywords']}</code>\n"
        f"🎲 Вероятность: {data['probability']}%\n"
        f"🔍 Условие: {cond}\n"
        f"📍 Где: {where}\n"
        f"👤 Инициатор: {init}\n"
        f"🎯 Цель: {tgt}\n"
        f"⚡ Действия: {acts_str}\n"
        f"🤖 Удаление сообщ. бота: {bot_del}\n"
        f"📡 Статус: {status}\n"
    )
    cfgs = data.get('action_configs', {})
    if 'msg_chat' in acts and cfgs.get('msg_chat', {}).get('text'):
        text += f"\n💬 Текст: <i>{cfgs['msg_chat']['text'][:100]}</i>"
    if 'mute' in acts and cfgs.get('mute', {}).get('duration'):
        d = cfgs['mute']['duration']
        text += f"\n🔇 Мут: {MUTE_OPTIONS.get(d, (d,))[0]}"
    if 'emoji' in acts and cfgs.get('emoji', {}).get('emoji'):
        text += f"\n😀 Эмодзи: {cfgs['emoji']['emoji']}"
    if data.get('warn_period'):
        text += f"\n⚠️ Период: {_format_duration(data['warn_period'])}"

    toggle_lbl = "❌ Выключить" if t['is_enabled'] else "✅ Включить"
    kb = [
        [IKB(toggle_lbl, callback_data=f"trigger_toggle_{trigger_id}"),
         IKB("✏️ Редактировать", callback_data=f"trigger_edit_{trigger_id}")],
        [IKB("🚫 Удалить", callback_data=f"trigger_del_{trigger_id}")],
        [IKB("◀ К списку", callback_data="trigger_list")],
    ]
    try:
        if hasattr(src, 'edit_message_text'):
            await src.edit_message_text(text, parse_mode='HTML', reply_markup=IKM(kb))
        else:
            await src.reply_text(text, parse_mode='HTML', reply_markup=IKM(kb))
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"trigger_detail: {e}")


# ═══════════════════════════════════════════════════════════════
#  РЕДАКТИРОВАНИЕ (7.5)
# ═══════════════════════════════════════════════════════════════

async def _start_edit(query, ctx, db, trigger_id: int):
    t = _get_trigger(db, trigger_id)
    if not t:
        await query.answer("❌ Не найден.", show_alert=True)
        return
    _set_data(ctx, _trigger_to_data(t))
    ctx.user_data['trigger_edit_id'] = trigger_id
    await _show_edit_menu(query, ctx, db, trigger_id)

async def _show_edit_menu(src, ctx, db, trigger_id: int):
    data = _get_data(ctx)
    cond = CONDITIONS.get(data.get('condition', 'contains'), '?')
    where = 'Во всём чате' if data.get('where_fires', 'all') == 'all' else 'Ветки'
    init = INITIATORS.get(data.get('initiator', 'all'), '?')
    tgt = TARGETS.get(data.get('target', 'nobody'), '?')
    acts = data.get('actions', [])
    bot_del = BOT_DEL_OPTIONS.get(data.get('bot_msg_delete', 'no'), 'Нет')
    fire_limit = data.get('fire_limit')
    fire_lbl = str(fire_limit) if fire_limit is not None else "∞"
    auto_pin = data.get('auto_pin', 0)
    pin_lbl = "✅" if auto_pin else "❌"

    text = (
        f"✏️ <b>Редактирование «{data.get('name', '?')}»</b>\n\n"
        f"<i>Нажмите на параметр для изменения</i>"
    )
    kb = [
        [IKB(f"📛 Имя: {data.get('name', '?')}", callback_data="trigger_edt_name")],
        [IKB(f"📝 Слова: {(data.get('keywords') or '?')[:30]}", callback_data="trigger_edt_kw")],
        [IKB(f"🎲 Вероятность: {data.get('probability', 100)}%", callback_data="trigger_edt_prob")],
        [IKB(f"🤖 Удаление: {bot_del}", callback_data="trigger_edt_botdel")],
        [IKB(f"🔍 Условие: {cond}", callback_data="trigger_set_cond")],
        [IKB(f"📍 Где: {where}", callback_data="trigger_set_where")],
        [IKB(f"👤 Инициатор: {init}", callback_data="trigger_set_init")],
        [IKB(f"🎯 Цель: {tgt}", callback_data="trigger_set_target")],
        [IKB(f"⚡ Действия ({len(acts)})", callback_data="trigger_set_actions")],
        [IKB(f"🔢 Лимит: {fire_lbl}", callback_data="trigger_set_firelimit"),
         IKB(f"📌 Автозакреп: {pin_lbl}", callback_data="trigger_set_autopin")],
        [IKB("💾 Сохранить", callback_data="trigger_finish")],
        [IKB("❌ Отмена", callback_data=f"trigger_view_{trigger_id}")],
    ]
    _set_state(ctx, None)
    ctx.user_data['trigger_step'] = 'menu'
    await _send_step(src, ctx, text, kb)


# ═══════════════════════════════════════════════════════════════
#  ДВИЖОК — ОБРАБОТКА СООБЩЕНИЙ
# ═══════════════════════════════════════════════════════════════

async def process_triggers(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    target_chat_id: int,
    main_admin_id: int,
) -> bool:
    """Проверяет сообщение на совпадение с триггерами. True если обработано."""
    message = update.effective_message
    if not message or not message.text:
        return False
    user = message.from_user
    if not user:
        return False

    # Игнорируем собственные сообщения бота
    try:
        if user.id == context.bot.id:
            return False
    except Exception:
        pass

    ensure_trigger_tables(db)
    triggers = _get_enabled_triggers(db)
    if not triggers:
        return False

    msg_text = message.text.lower().strip()
    thread_id = getattr(message, 'message_thread_id', None)
    handled = False

    for trigger in triggers:
        tdata = _trigger_to_data(trigger)

        # Фильтр: Где (7.3.2)
        where = tdata.get('where_fires', 'all')
        if where != 'all':
            try:
                allowed = json.loads(where) if isinstance(where, str) else where
                if isinstance(allowed, list) and thread_id not in allowed:
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

        # Фильтр: Инициатор (7.3.3)
        initiator = tdata.get('initiator', 'all')
        if initiator != 'all':
            udata = db.get_user(user.id)
            is_admin = udata and (udata['is_admin'] or udata['is_owner'])
            is_owner = user.id == main_admin_id or (udata and udata['is_owner'])
            if initiator == 'users' and (is_admin or is_owner):
                continue
            elif initiator == 'owner' and not is_owner:
                continue
            elif initiator == 'admins_owner' and not (is_admin or is_owner):
                continue

        # Вероятность
        raw_prob = tdata.get('probability', 100)
        if raw_prob is None:
            prob = 100
        else:
            try:
                prob = int(raw_prob)
            except (TypeError, ValueError):
                prob = 100
        prob = max(0, min(100, prob))
        if prob < 100 and random.randint(1, 100) > prob:
            continue

        # Проверка совпадения
        keywords = [kw.strip().lower() for kw in tdata['keywords'].split(',') if kw.strip()]
        cond = tdata.get('condition', 'contains')
        matched = False
        for kw in keywords:
            if cond == 'exact':     matched = (msg_text == kw)
            elif cond == 'contains':  matched = (kw in msg_text)
            elif cond == 'starts_with': matched = msg_text.startswith(kw)
            elif cond == 'ends_with':   matched = msg_text.endswith(kw)
            elif cond == 'whole_word':  matched = bool(re.search(rf'\b{re.escape(kw)}\b', msg_text))
            if matched:
                break

        if not matched:
            continue

        # Проверка лимита срабатываний
        fire_limit = tdata.get('fire_limit')
        if fire_limit is not None:
            try:
                fire_count = int(trigger['fire_count'] if 'fire_count' in trigger.keys() else 0) or 0
            except (TypeError, ValueError):
                fire_count = 0
            if fire_count >= fire_limit:
                logger.info(f"TRIGGER '{trigger['name']}' fire_limit={fire_limit} reached, skip")
                continue

        # ═══ СОВПАДЕНИЕ ═══
        logger.info(f"TRIGGER '{trigger['name']}' matched user {user.id}")

        actions = tdata.get('actions', [])
        cfgs = tdata.get('action_configs', {})
        target_type = tdata.get('target', 'nobody')
        has_rotation = bool(_rotation_items_for_trigger(tdata))
        sent_public_bot_message = False
        last_bot_msg_for_pin = None

        # Журнал
        try:
            from handlers.journal_handlers import log_trigger
            await log_trigger(
                context.bot, db, user.id, trigger['name'],
                ', '.join(actions) if actions else 'info',
                chat=message.chat, tg_user=user, triggered_at=message.date,
                trigger_message=message,
            )
        except Exception as _je:
            logger.error(f"log_trigger error: {_je}")

        for act in actions:
            try:
                act_cfg = cfgs.get(act, {})

                if act == 'msg_chat':
                    if has_rotation:
                        bot_msg = await _execute_rotation_action(context, db, trigger, cfgs, message)
                    else:
                        reply_text = (act_cfg.get('text') or trigger['name']).strip()
                        reply_id = message.message_id if act_cfg.get('reply_to_user', False) else None
                        bot_msg = await _send_action_message(
                            bot=context.bot,
                            chat_id=message.chat.id,
                            thread_id=getattr(message, 'message_thread_id', None),
                            text=reply_text,
                            act_cfg=act_cfg,
                            parse_mode='HTML',
                            reply_to_message_id=reply_id,
                        )
                    if bot_msg:
                        sent_public_bot_message = True
                        last_bot_msg_for_pin = bot_msg
                        await _handle_bot_msg_deletion(context, db, trigger, bot_msg)

                elif act == 'msg_dm':
                    dm_text = (act_cfg.get('text') or trigger['name']).strip()
                    uid = _resolve_target(user, target_type, tdata)
                    if uid:
                        try:
                            await _send_action_message(
                                bot=context.bot,
                                chat_id=uid,
                                thread_id=None,
                                text=dm_text,
                                act_cfg=act_cfg,
                                parse_mode='HTML',
                            )
                        except Exception as e:
                            logger.warning(f"DM failed: {e}")

                elif act == 'pin':
                    try:
                        await message.pin(disable_notification=not act_cfg.get('notify', False))
                    except Exception as e:
                        logger.warning(f"Pin failed: {e}")

                elif act == 'delete':
                    try:
                        await message.delete()
                        handled = True
                    except Exception:
                        pass

                elif act == 'mute':
                    dur_key = act_cfg.get('duration', '60m')
                    _, dur_sec = MUTE_OPTIONS.get(dur_key, ('', 3600))
                    uid = _resolve_target(user, target_type, tdata)
                    if uid:
                        try:
                            await context.bot.restrict_chat_member(
                                chat_id=target_chat_id, user_id=uid,
                                permissions=ChatPermissions(
                                    can_send_messages=False, can_send_audios=False,
                                    can_send_documents=False, can_send_photos=False,
                                    can_send_videos=False, can_send_video_notes=False,
                                    can_send_voice_notes=False, can_send_polls=False,
                                    can_send_other_messages=False,
                                    can_add_web_page_previews=False),
                                until_date=int(time.time()) + dur_sec)
                        except Exception as e:
                            logger.error(f"Mute failed: {e}")

                elif act == 'warn':
                    uid = _resolve_target(user, target_type, tdata)
                    if not uid:
                        continue
                    wp = tdata.get('warn_period')
                    count = _get_violations_in_period(db, user.id, trigger['id'], wp)
                    # При включенной ротации не дублируем чат дополнительными сообщениями warn.
                    if not has_rotation:
                        bot_msg = await message.reply_text(
                            f"⚠️ {_user_link(user)}, предупреждение ({count})!",
                            parse_mode='HTML')
                        sent_public_bot_message = True
                        await _handle_bot_msg_deletion(context, db, trigger, bot_msg)
                    # Эскалация
                    for threshold, mute_sec in WARN_ESCALATION:
                        if count == threshold:
                            try:
                                await context.bot.restrict_chat_member(
                                    chat_id=target_chat_id, user_id=uid,
                                    permissions=ChatPermissions(can_send_messages=False),
                                    until_date=int(time.time()) + mute_sec)
                                if not has_rotation:
                                    await message.reply_text(
                                        f"🔇 {_user_link(user)} — мут {_format_duration(mute_sec)} "
                                        f"({count} предупр.)", parse_mode='HTML')
                                    sent_public_bot_message = True
                            except Exception as e:
                                logger.error(f"Warn mute failed: {e}")
                            break

                elif act == 'emoji':
                    emoji_char = act_cfg.get('emoji', '👀')
                    try:
                        await message.set_reaction(emoji_char)
                    except Exception as e:
                        logger.warning(f"Emoji reaction failed: {e}")

            except Exception as e:
                logger.error(f"Trigger '{trigger['name']}' action '{act}': {e}")

        # Инкремент счётчика срабатываний
        try:
            db.cursor.execute(
                "UPDATE triggers SET fire_count = COALESCE(fire_count, 0) + 1 WHERE id = ?",
                (trigger['id'],)
            )
            db.conn.commit()
        except Exception as _fe:
            logger.warning(f"fire_count increment failed: {_fe}")

        # Автозакреп ответного сообщения
        auto_pin = tdata.get('auto_pin', 0)
        if auto_pin and last_bot_msg_for_pin:
            try:
                await context.bot.pin_chat_message(
                    chat_id=last_bot_msg_for_pin.chat.id,
                    message_id=last_bot_msg_for_pin.message_id,
                    disable_notification=True,
                )
            except Exception as _pe:
                logger.warning(f"auto_pin failed: {_pe}")

        if handled:
            break

    return handled


def _resolve_target(user, target_type: str, tdata: dict) -> Optional[int]:
    if target_type == 'initiator': return user.id
    if target_type == 'specific':
        try: return int(tdata.get('target_user', ''))
        except (ValueError, TypeError): pass
    if target_type == 'nobody': return None
    return user.id  # fallback


def _build_url_markup(act_cfg: dict):
    """Строит InlineKeyboardMarkup из списка кнопок-ссылок в act_cfg."""
    buttons = act_cfg.get('buttons', [])
    if not buttons:
        return None
    rows = []
    for btn in buttons:
        url = btn.get('url', '').strip()
        label = btn.get('text', '').strip()
        if url and label:
            try:
                rows.append([IKB(label, url=url)])
            except Exception:
                pass
    return IKM(rows) if rows else None


async def _send_action_message(bot, chat_id: int, thread_id: Optional[int], text: str,
                               act_cfg: dict, parse_mode: str = 'HTML',
                               reply_to_message_id: Optional[int] = None):
    """Отправка сообщения действия с опциональным медиа и URL-кнопками."""
    media_id = act_cfg.get('media_id')
    media_type = act_cfg.get('media_type')
    media_pos = act_cfg.get('media_pos', 'above')
    link_preview = act_cfg.get('link_preview', True)
    text = (text or '').strip()
    reply_markup = _build_url_markup(act_cfg)

    if not media_id or not media_type:
        if not text:
            return None
        kwargs = {
            'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode,
            'disable_web_page_preview': not link_preview,
        }
        if thread_id is not None:
            kwargs['message_thread_id'] = thread_id
        if reply_to_message_id is not None:
            kwargs['reply_to_message_id'] = reply_to_message_id
        if reply_markup:
            kwargs['reply_markup'] = reply_markup
        return await bot.send_message(**kwargs)

    if media_pos == 'above':
        return await _send_action_media(
            bot=bot,
            chat_id=chat_id,
            thread_id=thread_id,
            media_id=media_id,
            media_type=media_type,
            caption=text or None,
            parse_mode=parse_mode,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup,
        )

    sent_text = None
    if text:
        kwargs = {
            'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode,
            'disable_web_page_preview': not link_preview,
        }
        if thread_id is not None:
            kwargs['message_thread_id'] = thread_id
        if reply_to_message_id is not None:
            kwargs['reply_to_message_id'] = reply_to_message_id
        if reply_markup:
            kwargs['reply_markup'] = reply_markup
        sent_text = await bot.send_message(**kwargs)

    sent_media = await _send_action_media(
        bot=bot,
        chat_id=chat_id,
        thread_id=thread_id,
        media_id=media_id,
        media_type=media_type,
        reply_to_message_id=sent_text.message_id if sent_text else reply_to_message_id,
        reply_markup=reply_markup if not sent_text else None,
    )

    return sent_text or sent_media


async def _send_action_media(bot, chat_id: int, thread_id: Optional[int],
                             media_id: str, media_type: str,
                             caption: Optional[str] = None,
                             parse_mode: str = 'HTML',
                             reply_to_message_id: Optional[int] = None,
                             reply_markup=None):
    """Отправка одного медиа-сообщения в чат/ветку или ЛС."""
    kwargs = {'chat_id': chat_id}
    if thread_id is not None:
        kwargs['message_thread_id'] = thread_id
    if reply_to_message_id is not None:
        kwargs['reply_to_message_id'] = reply_to_message_id
    if reply_markup is not None:
        kwargs['reply_markup'] = reply_markup

    if media_type == 'photo':
        if caption:
            kwargs['caption'] = caption
            kwargs['parse_mode'] = parse_mode
        return await bot.send_photo(photo=media_id, **kwargs)
    if media_type == 'video':
        if caption:
            kwargs['caption'] = caption
            kwargs['parse_mode'] = parse_mode
        return await bot.send_video(video=media_id, **kwargs)
    if media_type == 'animation':
        if caption:
            kwargs['caption'] = caption
            kwargs['parse_mode'] = parse_mode
        return await bot.send_animation(animation=media_id, **kwargs)

    logger.warning(f"Unsupported media_type in trigger action: {media_type}")
    return None


async def _handle_bot_msg_deletion(context, db, trigger, bot_msg):
    """Удаление сообщения бота (7.2.4)."""
    try:
        bot_del = trigger['bot_msg_delete'] or 'no'
    except (KeyError, TypeError):
        return

    if bot_del == 'previous':
        try:
            old_id = trigger['last_bot_msg_id']
            old_chat = trigger['last_bot_msg_chat']
            if old_id and old_chat:
                try:
                    await context.bot.delete_message(chat_id=old_chat, message_id=old_id)
                except Exception:
                    pass
        except (KeyError, TypeError):
            pass
        try:
            db.cursor.execute(
                "UPDATE triggers SET last_bot_msg_id=?, last_bot_msg_chat=? WHERE id=?",
                (bot_msg.message_id, bot_msg.chat.id, trigger['id']))
            db.conn.commit()
        except Exception:
            pass

    elif bot_del == 'previous_period':
        # Удалить предыдущее сообщение бота через период (не сразу)
        try:
            old_id = trigger['last_bot_msg_id']
            old_chat = trigger['last_bot_msg_chat']
            delay = trigger['bot_msg_delete_after'] or 60
            if old_id and old_chat:
                try:
                    context.job_queue.run_once(
                        _delete_bot_msg_job, when=delay,
                        data={'chat_id': old_chat, 'message_id': old_id},
                        name=f"trig_prevdel_{old_id}")
                except Exception as e:
                    logger.warning(f"Schedule previous bot msg deletion: {e}")
        except (KeyError, TypeError):
            pass
        try:
            db.cursor.execute(
                "UPDATE triggers SET last_bot_msg_id=?, last_bot_msg_chat=? WHERE id=?",
                (bot_msg.message_id, bot_msg.chat.id, trigger['id']))
            db.conn.commit()
        except Exception:
            pass

    elif bot_del == 'period':
        try:
            delay = trigger['bot_msg_delete_after'] or 60
        except (KeyError, TypeError):
            delay = 60
        try:
            context.job_queue.run_once(
                _delete_bot_msg_job, when=delay,
                data={'chat_id': bot_msg.chat.id, 'message_id': bot_msg.message_id},
                name=f"trig_del_{bot_msg.message_id}")
        except Exception as e:
            logger.warning(f"Schedule bot msg deletion: {e}")


async def _delete_bot_msg_job(context):
    try:
        d = context.job.data
        await context.bot.delete_message(chat_id=d['chat_id'], message_id=d['message_id'])
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
#  FSM — ТЕКСТОВЫЙ ВВОД
# ═══════════════════════════════════════════════════════════════

async def handle_trigger_text_input(update: Update, context, db) -> bool:
    """Обрабатывает текстовый ввод при создании/редактировании триггера."""
    state = _get_state(context)
    if not state:
        # Legacy: owner_awaiting с trigger_ prefix
        oa = context.user_data.get('owner_awaiting', '')
        if oa.startswith('trigger_'):
            state = {'trigger_name': TS.NAME, 'trigger_keywords': TS.KEYWORDS,
                     'trigger_action_value': TS.ACT_CHAT_TEXT}.get(oa)
            if state:
                _set_state(context, state)
            else:
                return False
        else:
            return False

    message = update.effective_message
    text = (message.text or '').strip() if message else ''
    data = _get_data(context)
    chat_id = message.chat.id if message else None

    # ── Шаг 1: Название ──
    if state == TS.NAME:
        if len(text) < 2 or len(text) > 50:
            await _send_step(message, context, "❌ Название: 2–50 символов.",
                             [_nav_buttons('name')], chat_id)
            return True
        data['name'] = text
        _set_data(context, data)
        await _step_keywords(message, context)
        return True

    # ── Шаг 2: Ключевые слова ──
    if state == TS.KEYWORDS:
        if not text:
            await _send_step(message, context, "❌ Введите ключевое слово.",
                             [_nav_buttons('keywords')], chat_id)
            return True
        data['keywords'] = text
        _set_data(context, data)
        await _step_probability(message, context)
        return True

    # ── Шаг 3: Вероятность ──
    if state == TS.PROBABILITY:
        try:
            val = int(text)
            if not (0 <= val <= 100): raise ValueError
        except ValueError:
            await _send_step(message, context, "❌ Число от 0 до 100.",
                             [_nav_buttons('probability', show_skip=True)], chat_id)
            return True
        data['probability'] = val
        _set_data(context, data)
        await _step_bot_delete(message, context)
        return True

    # ── Период удаления бот-сообщения ──
    if state in (TS.BOT_DEL_PERIOD, TS.EDIT_BOT_DEL_PERIOD):
        seconds = _parse_duration_input(text)
        if not seconds or seconds < 30:
            await _send_step(message, context,
                "❌ Мин. 30 сек. Примеры: <code>5 мин</code>, <code>2 часа</code>",
                [[IKB("◀ Назад", callback_data="trigger_back")]], chat_id)
            return True
        # Если уже установлен previous_period — сохраняем его, иначе ставим period
        if data.get('bot_msg_delete') != 'previous_period':
            data['bot_msg_delete'] = 'period'
        data['bot_msg_delete_after'] = seconds
        _set_data(context, data)
        _set_state(context, None)
        edit_id = context.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(message, context, db, edit_id)
        else:
            await _show_settings_menu(message, context)
        return True

    # ── Текст в чат (7.4.1.1) ──
    if state in (TS.ACT_CHAT_TEXT, TS.EDIT_ACT_CHAT_TEXT):
        cfgs = data.get('action_configs', {})
        cfg = cfgs.get('msg_chat', {})
        cfg['text'] = text
        cfgs['msg_chat'] = cfg
        data['action_configs'] = cfgs
        _set_data(context, data)
        _set_state(context, TS.ACT_CHAT_MEDIA)
        await _send_step(message, context,
            "🖼 <b>Прикрепление медиа</b>\n\nОтправьте фото/видео/gif или «Пропустить»", [
            [IKB("⏩ Пропустить", callback_data="trigger_acfg_media_skip")],
            [IKB("◀ К действиям", callback_data="trigger_set_actions")],
        ], chat_id)
        return True

    # ── Текст в ЛС (7.4.2.1) ──
    if state in (TS.ACT_DM_TEXT, TS.EDIT_ACT_DM_TEXT):
        cfgs = data.get('action_configs', {})
        cfg = cfgs.get('msg_dm', {})
        cfg['text'] = text
        cfgs['msg_dm'] = cfg
        data['action_configs'] = cfgs
        _set_data(context, data)
        _set_state(context, TS.ACT_DM_MEDIA)
        await _send_step(message, context,
            "🖼 <b>Медиа для ЛС</b>\n\nОтправьте фото/видео/gif или «Пропустить»", [
            [IKB("⏩ Пропустить", callback_data="trigger_acfg_media_skip")],
        ], chat_id)
        return True

    # ── Текст в слот ротации ──
    if state == TS.ACT_ROT_TEXT:
        slot = context.user_data.get('trigger_rotation_slot', 1)
        try:
            slot = int(slot)
        except (TypeError, ValueError):
            slot = 1
        slot = max(1, min(5, slot))

        _ensure_rotation_slot(data, slot)
        items = _get_rotation_items(data)
        items[slot - 1]['text'] = text
        _set_rotation_items(data, items)
        _set_data(context, data)
        _set_state(context, TS.ACT_ROT_MEDIA)

        await _send_step(
            message,
            context,
            f"🖼 <b>Слот {slot}: медиа</b>\n\nОтправьте фото/видео/gif или «Пропустить».",
            [
                [IKB("⏩ Пропустить", callback_data=f"trigger_acfg_rot_media_skip_{slot}")],
                [IKB("◀ К слоту", callback_data=f"trigger_acfg_rot_slot_{slot}")],
            ],
            chat_id,
        )
        return True

    # ── Эмодзи (7.4.7) ──
    if state in (TS.ACT_EMOJI, TS.EDIT_ACT_EMOJI):
        if text:
            cfgs = data.get('action_configs', {})
            cfgs['emoji'] = {'emoji': text}
            data['action_configs'] = cfgs
            _set_data(context, data)
        _set_state(context, None)
        await _show_actions_menu(message, context)
        return True

    # ── Период предупреждений (7.4.6.2) ──
    if state in (TS.ACT_WARN_PERIOD, TS.EDIT_ACT_WARN_PERIOD):
        seconds = _parse_duration_input(text)
        if not seconds:
            await _send_step(message, context,
                "❌ Примеры: <code>30 мин</code>, <code>24 часа</code>",
                [[IKB("◀ К действиям", callback_data="trigger_set_actions")]], chat_id)
            return True
        data['warn_period'] = seconds
        _set_data(context, data)
        _set_state(context, None)
        await _show_actions_menu(message, context)
        return True

    # ── Редактирование: Название ──
    if state == TS.EDIT_NAME:
        if len(text) < 2 or len(text) > 50:
            await _send_step(message, context, "❌ 2–50 символов.",
                             [[IKB("⏩ Пропустить", callback_data="trigger_edt_menu")]], chat_id)
            return True
        data['name'] = text
        _set_data(context, data)
        _set_state(context, None)
        edit_id = context.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(message, context, db, edit_id)
        else:
            await _show_settings_menu(message, context)
        return True

    # ── Редактирование: Добавить слова ──
    if state == TS.EDIT_KW_ADD:
        if text:
            old = data.get('keywords', '')
            data['keywords'] = f"{old}, {text}" if old else text
            _set_data(context, data)
        _set_state(context, None)
        edit_id = context.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(message, context, db, edit_id)
        return True

    # ── Редактирование: Удалить слова ──
    if state == TS.EDIT_KW_DEL:
        if text:
            to_del = {w.strip().lower() for w in text.split(',') if w.strip()}
            existing = [w.strip() for w in (data.get('keywords', '') or '').split(',') if w.strip()]
            remaining = [w for w in existing if w.lower() not in to_del]
            data['keywords'] = ', '.join(remaining) if remaining else data.get('keywords', '')
            _set_data(context, data)
        _set_state(context, None)
        edit_id = context.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(message, context, db, edit_id)
        return True

    # ── Редактирование: Вероятность ──
    if state == TS.EDIT_PROBABILITY:
        try:
            val = int(text)
            if not (0 <= val <= 100): raise ValueError
        except ValueError:
            await _send_step(message, context, "❌ 0–100.",
                             [[IKB("⏩ Пропустить", callback_data="trigger_edt_menu")]], chat_id)
            return True
        data['probability'] = val
        _set_data(context, data)
        _set_state(context, None)
        edit_id = context.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(message, context, db, edit_id)
        return True

    # ── Кнопка: текст ──
    if state == TS.ACT_BTN_TEXT:
        if not text or len(text) > 64:
            await _send_step(message, context, "❌ Текст кнопки: 1–64 символа.",
                             [[IKB("❌ Отмена", callback_data="trigger_acfg_btn_cancel")]], chat_id)
            return True
        context.user_data['trigger_btn_text_tmp'] = text
        _set_state(context, TS.ACT_BTN_URL)
        await _send_step(message, context,
            f"🔗 <b>Введите URL для кнопки «{text}»</b>\n\n"
            "<i>Например: https://t.me/yourchat</i>",
            [[IKB("❌ Отмена", callback_data="trigger_acfg_btn_cancel")]], chat_id)
        return True

    # ── Кнопка: URL ──
    if state == TS.ACT_BTN_URL:
        url = text.strip()
        if not url.startswith(('http://', 'https://', 't.me/', 'tg://')):
            await _send_step(message, context,
                "❌ Некорректный URL. Должен начинаться с <code>https://</code> или <code>t.me/</code>",
                [[IKB("❌ Отмена", callback_data="trigger_acfg_btn_cancel")]], chat_id)
            return True
        btn_text = context.user_data.pop('trigger_btn_text_tmp', 'Кнопка')
        action_key = context.user_data.get('trigger_btn_action', 'msg_chat')
        cfgs = data.get('action_configs', {})
        cfg = cfgs.get(action_key, {})
        buttons = cfg.get('buttons', [])
        buttons.append({'text': btn_text, 'url': url})
        cfg['buttons'] = buttons
        cfgs[action_key] = cfg
        data['action_configs'] = cfgs
        _set_data(context, data)
        _set_state(context, None)
        await _show_buttons_menu(message, context, action_key)
        return True

    # ── Лимит срабатываний ──
    if state == TS.ACT_FIRE_LIMIT:
        if text.lower() in ('0', '∞', 'нет', 'inf', 'бесконечно'):
            data['fire_limit'] = None
        else:
            try:
                val = int(text)
                if val < 1: raise ValueError
                data['fire_limit'] = val
            except ValueError:
                await _send_step(message, context,
                    "❌ Введите число (≥1) или 0/∞ для бесконечного количества.",
                    [[IKB("❌ Отмена", callback_data="trigger_menu")]], chat_id)
                return True
        _set_data(context, data)
        _set_state(context, None)
        edit_id = context.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(message, context, db, edit_id)
        else:
            await _show_settings_menu(message, context)
        return True

    return False


async def handle_trigger_media_input(update: Update, context, db) -> bool:
    """Обработка медиа (фото/видео/gif) для триггеров."""
    state = _get_state(context)
    if state not in (TS.ACT_CHAT_MEDIA, TS.ACT_DM_MEDIA, TS.ACT_ROT_MEDIA):
        return False

    message = update.effective_message
    if not message:
        return False

    file_id = media_type = None
    if message.photo:
        file_id, media_type = message.photo[-1].file_id, 'photo'
    elif message.video:
        file_id, media_type = message.video.file_id, 'video'
    elif message.animation:
        file_id, media_type = message.animation.file_id, 'animation'
    if not file_id:
        return False

    data = _get_data(context)
    cfgs = data.get('action_configs', {})
    if state in (TS.ACT_CHAT_MEDIA, TS.ACT_DM_MEDIA):
        key = 'msg_chat' if state == TS.ACT_CHAT_MEDIA else 'msg_dm'
        cfg = cfgs.get(key, {})
        cfg['media_id'] = file_id
        cfg['media_type'] = media_type
        cfgs[key] = cfg
        data['action_configs'] = cfgs
        _set_data(context, data)
        _set_state(context, None)
    else:
        slot = context.user_data.get('trigger_rotation_slot', 1)
        try:
            slot = int(slot)
        except (TypeError, ValueError):
            slot = 1
        slot = max(1, min(5, slot))
        _ensure_rotation_slot(data, slot)
        items = _get_rotation_items(data)
        items[slot - 1]['media_id'] = file_id
        items[slot - 1]['media_type'] = media_type
        _set_rotation_items(data, items)
        _set_data(context, data)
        _set_state(context, None)

    try:
        await message.delete()
    except Exception:
        pass

    # Позиция медиа
    if state == TS.ACT_ROT_MEDIA:
        slot = context.user_data.get('trigger_rotation_slot', 1)
        kb = [
            [IKB("🖼+📝 Одним сообщением", callback_data=f"trigger_acfg_rot_above_{slot}")],
            [IKB("📝 Потом 🖼 отдельным", callback_data=f"trigger_acfg_rot_below_{slot}")],
            [IKB("◀ К слоту", callback_data=f"trigger_acfg_rot_slot_{slot}")],
        ]
        await _send_step(message, context, f"📐 <b>Слот {slot}: выберите формат отправки</b>", kb, message.chat.id)
    else:
        kb = [
            [IKB("🖼+📝 Одним сообщением", callback_data="trigger_acfg_media_above")],
            [IKB("📝 Потом 🖼 отдельным", callback_data="trigger_acfg_media_below")],
            [IKB("◀ К действиям", callback_data="trigger_set_actions")],
        ]
        await _send_step(message, context, "📐 <b>Выберите формат отправки:</b>", kb, message.chat.id)
    return True


# ═══════════════════════════════════════════════════════════════
#  ДИСПЕТЧЕР CALLBACK-ОВ
# ═══════════════════════════════════════════════════════════════

async def handle_trigger_callback(query, data_str: str, context, db, admin_id: int) -> None:
    """Единый обработчик всех trigger_ callback_data."""
    user = query.from_user
    user_data = db.get_user(user.id)
    is_staff = user.id == admin_id or (user_data and (user_data['is_admin'] or user_data['is_owner']))
    if not is_staff:
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    d = data_str
    ctx = context
    draft = _get_data(ctx)

    # ═══ МЕНЮ ═══
    if d == "trigger_create":
        _clear_fsm(ctx)
        ctx.user_data['trigger_data'] = _default_data()
        await _step_name(query, ctx, db)

    elif d == "trigger_quicktrig":
        await query.answer("⚡ Быстротриг — скоро!", show_alert=True)

    elif d == "trigger_list":
        _clear_fsm(ctx)
        ctx.user_data.pop('trigger_list_expanded_id', None)
        await show_trigger_list(query, db, admin_id, ctx)

    elif d.startswith("trigger_expand_"):
        tid = int(d[len("trigger_expand_"):])
        cur = ctx.user_data.get('trigger_list_expanded_id')
        ctx.user_data['trigger_list_expanded_id'] = None if cur == tid else tid
        await show_trigger_list(query, db, admin_id, ctx)

    elif d == "trigger_menu":
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)
        else:
            await _show_settings_menu(query, ctx)

    # ═══ НАВИГАЦИЯ (7.1) ═══
    elif d == "trigger_back":
        step = ctx.user_data.get('trigger_step', 'name')
        idx = CREATION_STEPS.index(step) if step in CREATION_STEPS else 0
        if idx > 0:
            prev = CREATION_STEPS[idx - 1]
            {'name': lambda: _step_name(query, ctx, db),
             'keywords': lambda: _step_keywords(query, ctx),
             'probability': lambda: _step_probability(query, ctx),
             'bot_delete': lambda: _step_bot_delete(query, ctx),
             'menu': lambda: _show_settings_menu(query, ctx),
             }.get(prev, lambda: _step_name(query, ctx, db))
            # Вызываем корутину
            prev_fn = {
                'name': _step_name, 'keywords': _step_keywords,
                'probability': _step_probability, 'bot_delete': _step_bot_delete,
                'menu': _show_settings_menu,
            }.get(prev)
            if prev_fn:
                if prev == 'name':
                    await prev_fn(query, ctx, db)
                elif prev == 'menu':
                    await prev_fn(query, ctx)
                else:
                    await prev_fn(query, ctx)
        else:
            await _step_name(query, ctx, db)

    elif d == "trigger_back_to_menu":
        _clear_fsm(ctx)
        await show_triggers_menu(query, db, admin_id)

    elif d == "trigger_reset":
        _clear_fsm(ctx)
        ctx.user_data['trigger_data'] = _default_data()
        await _step_name(query, ctx, db)

    elif d == "trigger_skip":
        step = ctx.user_data.get('trigger_step', 'name')
        if step == 'probability':
            await _step_bot_delete(query, ctx)
        elif step == 'bot_delete':
            await _show_settings_menu(query, ctx)
        else:
            await _show_settings_menu(query, ctx)

    elif d == "trigger_finish":
        await _finish_and_save(query, ctx, db)

    # ═══ BOT MSG DELETE (7.2.4) ═══
    elif d == "trigger_botdel_no":
        draft['bot_msg_delete'] = 'no'
        draft['bot_msg_delete_after'] = None
        _set_data(ctx, draft)
        await _show_settings_menu(query, ctx)

    elif d == "trigger_botdel_period":
        _set_state(ctx, TS.BOT_DEL_PERIOD)
        await _send_step(query, ctx,
            "⏱ <b>Период автоудаления</b>\n\nУкажите время:\n"
            "<i>Примеры: <code>5 мин</code>, <code>2 часа</code>, <code>1 день</code></i>",
            [[IKB("◀ Назад", callback_data="trigger_back")]])

    elif d == "trigger_botdel_prev":
        draft['bot_msg_delete'] = 'previous'
        draft['bot_msg_delete_after'] = None
        _set_data(ctx, draft)
        await _show_settings_menu(query, ctx)

    elif d == "trigger_botdel_prevperiod":
        _set_state(ctx, TS.BOT_DEL_PERIOD)
        draft['bot_msg_delete'] = 'previous_period'
        _set_data(ctx, draft)
        await _send_step(query, ctx,
            "🔄⏱ <b>Предыдущее + период</b>\n\n"
            "Через какое время удалить предыдущее сообщение бота?\n"
            "<i>Примеры: <code>5 мин</code>, <code>2 часа</code>, <code>1 день</code></i>",
            [[IKB("◀ Назад", callback_data="trigger_back")]])

    # ═══ ПОДМЕНЮ (7.3) ═══
    elif d == "trigger_set_cond":
        await _show_condition_menu(query, ctx)
    elif d == "trigger_set_where":
        await _show_where_menu(query, ctx, db)
    elif d == "trigger_set_init":
        await _show_initiator_menu(query, ctx)
    elif d == "trigger_set_target":
        await _show_target_menu(query, ctx)
    elif d == "trigger_set_actions":
        await _show_actions_menu(query, ctx)

    # ═══ УСЛОВИЕ (7.3.1) ═══
    elif d.startswith("trigger_cond_"):
        cond = d.replace("trigger_cond_", "")
        if cond in CONDITIONS:
            draft['condition'] = cond
            _set_data(ctx, draft)
            await query.answer(f"✅ {CONDITIONS[cond]}")
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)
        else:
            await _show_settings_menu(query, ctx)

    # ═══ ГДЕ (7.3.2) ═══
    elif d == "trigger_where_all":
        draft['where_fires'] = 'all'
        _set_data(ctx, draft)
        await query.answer("✅ Во всём чате")
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)
        else:
            await _show_settings_menu(query, ctx)

    elif d == "trigger_where_topics":
        await _show_topics_select(query, ctx, db, page=0)

    elif d.startswith("trigger_wtp_"):
        # Пагинация веток
        pg = int(d[len("trigger_wtp_"):])
        await _show_topics_select(query, ctx, db, page=pg)

    elif d == "trigger_wt_done":
        cur = draft.get('where_fires', 'all')
        # Если пустой список — ставим 'all'
        if cur != 'all':
            try:
                selected = json.loads(cur) if isinstance(cur, str) else cur
                if not selected:
                    draft['where_fires'] = 'all'
                    _set_data(ctx, draft)
            except (json.JSONDecodeError, TypeError):
                pass
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)
        else:
            await _show_settings_menu(query, ctx)

    elif d.startswith("trigger_wt_"):
        # Toggle ветки в выборе
        raw = d[len("trigger_wt_"):]
        if not raw.lstrip('-').isdigit():
            await query.answer("⚠️ Некорректный ID ветки")
            return
        tid = int(raw)
        if tid == 0:
            tid = None  # главный чат

        cur = draft.get('where_fires', 'all')
        selected = []
        if cur != 'all':
            try:
                selected = json.loads(cur) if isinstance(cur, str) else cur
                if not isinstance(selected, list):
                    selected = []
            except (json.JSONDecodeError, TypeError):
                selected = []

        if tid in selected:
            selected.remove(tid)
        else:
            selected.append(tid)

        draft['where_fires'] = json.dumps(selected) if selected else 'all'
        _set_data(ctx, draft)
        pg = ctx.user_data.get('trigger_topics_page', 0)
        await _show_topics_select(query, ctx, db, page=pg)

    # ═══ ИНИЦИАТОР (7.3.3) ═══
    elif d.startswith("trigger_init_"):
        key = d.replace("trigger_init_", "")
        if key in INITIATORS:
            draft['initiator'] = key
            _set_data(ctx, draft)
            await query.answer(f"✅ {INITIATORS[key]}")
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)
        else:
            await _show_settings_menu(query, ctx)

    # ═══ ЦЕЛЬ (7.3.4) ═══
    elif d.startswith("trigger_tgt_"):
        key = d.replace("trigger_tgt_", "")
        if key in TARGETS:
            draft['target'] = key
            _set_data(ctx, draft)
            await query.answer(f"✅ {TARGETS[key]}")
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)
        else:
            await _show_settings_menu(query, ctx)

    # ═══ ДЕЙСТВИЯ toggle (7.3.5) ═══
    elif d.startswith("trigger_act_"):
        key = d.replace("trigger_act_", "")
        if key in ACTIONS_AVAILABLE:
            acts = draft.get('actions', [])
            if key == 'rotation':
                if 'msg_chat' not in acts:
                    acts.append('msg_chat')
                draft['actions'] = acts
                _set_data(ctx, draft)
                await _configure_action(query, ctx, 'msg_chat')
                return
            if key in acts:
                acts.remove(key)
                draft.get('action_configs', {}).pop(key, None)
            else:
                acts.append(key)
            draft['actions'] = acts
            _set_data(ctx, draft)
        await _show_actions_menu(query, ctx)

    elif d == "trigger_actdone":
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)
        else:
            await _show_settings_menu(query, ctx)

    # ═══ КОНФИГ ДЕЙСТВИЙ (7.4) ═══
    elif d.startswith("trigger_acfg_"):
        sub = d[len("trigger_acfg_"):]

        if sub == "msg_chat":
            await _configure_action(query, ctx, 'msg_chat')

        elif sub == "rotation":
            acts = draft.get('actions', [])
            if 'msg_chat' not in acts:
                acts.append('msg_chat')
                draft['actions'] = acts
                _set_data(ctx, draft)
            await _configure_action(query, ctx, 'rotation')

        elif sub.startswith("rot_slot_"):
            try:
                slot = int(sub[len("rot_slot_"):])
            except ValueError:
                slot = 1
            slot = max(1, min(5, slot))
            ctx.user_data['trigger_rotation_slot'] = slot
            await _show_rotation_slot_menu(query, ctx, slot)

        elif sub.startswith("rot_text_"):
            try:
                slot = int(sub[len("rot_text_"):])
            except ValueError:
                slot = 1
            slot = max(1, min(5, slot))
            ctx.user_data['trigger_rotation_slot'] = slot
            _set_state(ctx, TS.ACT_ROT_TEXT)
            await _send_step(
                query,
                ctx,
                f"📝 <b>Слот {slot}: введите текст</b>",
                [[IKB("◀ К слоту", callback_data=f"trigger_acfg_rot_slot_{slot}")]],
            )

        elif sub.startswith("rot_media_"):
            if sub.startswith("rot_media_skip_"):
                try:
                    slot = int(sub[len("rot_media_skip_"):])
                except ValueError:
                    slot = 1
                slot = max(1, min(5, slot))
                _set_state(ctx, None)
                await _show_rotation_slot_menu(query, ctx, slot)
            else:
                try:
                    slot = int(sub[len("rot_media_"):])
                except ValueError:
                    slot = 1
                slot = max(1, min(5, slot))
                ctx.user_data['trigger_rotation_slot'] = slot
                _set_state(ctx, TS.ACT_ROT_MEDIA)
                await _send_step(
                    query,
                    ctx,
                    f"🖼 <b>Слот {slot}: отправьте медиа</b>",
                    [
                        [IKB("⏩ Пропустить", callback_data=f"trigger_acfg_rot_media_skip_{slot}")],
                        [IKB("◀ К слоту", callback_data=f"trigger_acfg_rot_slot_{slot}")],
                    ],
                )

        elif sub.startswith("rot_clear_"):
            try:
                slot = int(sub[len("rot_clear_"):])
            except ValueError:
                slot = 1
            slot = max(1, min(5, slot))
            items = _get_rotation_items(draft)
            while len(items) < slot:
                items.append({})
            items[slot - 1] = {}
            _set_rotation_items(draft, items)
            _set_data(ctx, draft)
            await _show_rotation_slot_menu(query, ctx, slot)

        elif sub.startswith("rot_above_"):
            try:
                slot = int(sub[len("rot_above_"):])
            except ValueError:
                slot = 1
            slot = max(1, min(5, slot))
            _ensure_rotation_slot(draft, slot)
            items = _get_rotation_items(draft)
            items[slot - 1]['media_pos'] = 'above'
            _set_rotation_items(draft, items)
            _set_data(ctx, draft)
            await _show_rotation_slot_menu(query, ctx, slot)

        elif sub.startswith("rot_below_"):
            try:
                slot = int(sub[len("rot_below_"):])
            except ValueError:
                slot = 1
            slot = max(1, min(5, slot))
            _ensure_rotation_slot(draft, slot)
            items = _get_rotation_items(draft)
            items[slot - 1]['media_pos'] = 'below'
            _set_rotation_items(draft, items)
            _set_data(ctx, draft)
            await _show_rotation_slot_menu(query, ctx, slot)

        elif sub == "chat_text":
            _set_state(ctx, TS.ACT_CHAT_TEXT)
            await _send_step(query, ctx, "💬 <b>Введите текст сообщения в чат:</b>",
                             [[IKB("◀ К действиям", callback_data="trigger_set_actions")]])

        elif sub == "chat_media":
            _set_state(ctx, TS.ACT_CHAT_MEDIA)
            await _send_step(query, ctx, "🖼 Отправьте фото / видео / gif:", [
                [IKB("⏩ Пропустить", callback_data="trigger_acfg_media_skip")],
                [IKB("◀ К действиям", callback_data="trigger_set_actions")]])

        elif sub == "dm_text":
            _set_state(ctx, TS.ACT_DM_TEXT)
            await _send_step(query, ctx, "✉️ <b>Введите текст сообщения в ЛС:</b>",
                             [[IKB("◀ К действиям", callback_data="trigger_set_actions")]])

        elif sub == "dm_media":
            _set_state(ctx, TS.ACT_DM_MEDIA)
            await _send_step(query, ctx, "🖼 Отправьте медиа для ЛС:", [
                [IKB("⏩ Пропустить", callback_data="trigger_acfg_media_skip")],
                [IKB("◀ К действиям", callback_data="trigger_set_actions")]])

        elif sub == "media_skip":
            _set_state(ctx, None)
            await _show_actions_menu(query, ctx)

        elif sub == "media_above":
            act = ctx.user_data.get('trigger_configuring_action', 'msg_chat')
            cfgs = draft.get('action_configs', {})
            cfgs.setdefault(act, {})['media_pos'] = 'above'
            draft['action_configs'] = cfgs
            _set_data(ctx, draft)
            _set_state(ctx, None)
            await _show_actions_menu(query, ctx)

        elif sub == "media_below":
            act = ctx.user_data.get('trigger_configuring_action', 'msg_chat')
            cfgs = draft.get('action_configs', {})
            cfgs.setdefault(act, {})['media_pos'] = 'below'
            draft['action_configs'] = cfgs
            _set_data(ctx, draft)
            _set_state(ctx, None)
            await _show_actions_menu(query, ctx)

        elif sub == "pin_yes":
            cfgs = draft.get('action_configs', {})
            cfgs['pin'] = {'notify': True}
            draft['action_configs'] = cfgs
            _set_data(ctx, draft)
            await query.answer("✅ С уведомлением")
            await _show_actions_menu(query, ctx)

        elif sub == "pin_no":
            cfgs = draft.get('action_configs', {})
            cfgs['pin'] = {'notify': False}
            draft['action_configs'] = cfgs
            _set_data(ctx, draft)
            await query.answer("✅ Без уведомления")
            await _show_actions_menu(query, ctx)

        elif sub == "link_preview_toggle":
            act = ctx.user_data.get('trigger_configuring_action', 'msg_chat')
            cfgs = draft.get('action_configs', {})
            cfg = cfgs.setdefault(act, {})
            cfg['link_preview'] = not cfg.get('link_preview', True)
            cfgs[act] = cfg
            draft['action_configs'] = cfgs
            _set_data(ctx, draft)
            state = '✅ включено' if cfg['link_preview'] else '❌ отключено'
            await query.answer(f"Превью ссылок: {state}")
            await _configure_action(query, ctx, act)

        elif sub == "reply_toggle":
            act = ctx.user_data.get('trigger_configuring_action', 'msg_chat')
            cfgs = draft.get('action_configs', {})
            cfg = cfgs.setdefault(act, {})
            cfg['reply_to_user'] = not cfg.get('reply_to_user', False)
            cfgs[act] = cfg
            draft['action_configs'] = cfgs
            _set_data(ctx, draft)
            state = '✅ включен' if cfg['reply_to_user'] else '❌ отключен'
            await query.answer(f"Реплай: {state}")
            await _configure_action(query, ctx, act)

        elif sub.startswith("del_"):
            dsub = sub[4:]
            if dsub == "done":
                await _show_actions_menu(query, ctx)
            elif dsub in DELETE_OPTIONS:
                cfgs = draft.get('action_configs', {})
                cfg = cfgs.get('delete', {})
                what = cfg.get('what', [])
                if dsub in what:
                    what.remove(dsub)
                else:
                    what.append(dsub)
                cfg['what'] = what
                cfgs['delete'] = cfg
                draft['action_configs'] = cfgs
                _set_data(ctx, draft)
                await _configure_action(query, ctx, 'delete')

        elif sub.startswith("mute_"):
            dur = sub[5:]
            if dur in MUTE_OPTIONS:
                cfgs = draft.get('action_configs', {})
                cfgs['mute'] = {'duration': dur}
                draft['action_configs'] = cfgs
                _set_data(ctx, draft)
                await query.answer(f"✅ {MUTE_OPTIONS[dur][0]}")
                await _show_actions_menu(query, ctx)

        elif sub == "warn_period":
            _set_state(ctx, TS.ACT_WARN_PERIOD)
            await _send_step(query, ctx,
                "📅 <b>Период накопления</b>\n\nУкажите:\n"
                "<i>Примеры: <code>30 мин</code>, <code>24 часа</code>, <code>7 дней</code></i>",
                [[IKB("◀ К действиям", callback_data="trigger_set_actions")]])

        elif sub in ACTIONS_AVAILABLE:
            await _configure_action(query, ctx, sub)
        else:
            await query.answer("❓", show_alert=False)

    # ═══ ПРОСМОТР ═══
    elif d.startswith("trigger_view_"):
        tid = int(d[len("trigger_view_"):])
        _clear_fsm(ctx)
        await _show_trigger_detail(query, db, tid)

    # ═══ ВКЛ/ВЫКЛ ═══
    elif d.startswith("trigger_toggle_"):
        tid = int(d[len("trigger_toggle_"):])
        new = _toggle_trigger(db, tid)
        await query.answer(f"Триггер {'✅ вкл' if new else '❌ выкл'}", show_alert=True)
        await show_trigger_list(query, db, admin_id, ctx)

    # ═══ УДАЛЕНИЕ ═══
    elif d.startswith("trigger_delyes_"):
        tid = int(d[len("trigger_delyes_"):])
        _delete_trigger(db, tid)
        if ctx.user_data.get('trigger_list_expanded_id') == tid:
            ctx.user_data.pop('trigger_list_expanded_id', None)
        await query.answer("✅ Удалён.", show_alert=True)
        await show_trigger_list(query, db, admin_id, ctx)

    elif d.startswith("trigger_del_"):
        tid = int(d[len("trigger_del_"):])
        t = _get_trigger(db, tid)
        if not t:
            await query.answer("❌ Не найден.", show_alert=True)
            return
        await query.edit_message_text(
            f"🚫 Удалить <b>{t['name']}</b>?\n\nДействие нельзя отменить.",
            parse_mode='HTML', reply_markup=IKM([
                [IKB("⚠️ ДА", callback_data=f"trigger_delyes_{tid}")],
                [IKB("❌ Отмена", callback_data=f"trigger_view_{tid}")],
            ]))

    # ═══ РЕДАКТИРОВАНИЕ (7.5) ═══
    elif d.startswith("trigger_edit_"):
        tid = int(d[len("trigger_edit_"):])
        await _start_edit(query, ctx, db, tid)

    elif d == "trigger_edt_name":
        _set_state(ctx, TS.EDIT_NAME)
        data = _get_data(ctx)
        await _send_step(query, ctx,
            f"📛 <b>Название</b>\n\nТекущее: <b>{data.get('name', '?')}</b>\n\nВведите новое:",
            [[IKB("⏩ Пропустить", callback_data="trigger_edt_menu")]])

    elif d == "trigger_edt_kw":
        data = _get_data(ctx)
        await _send_step(query, ctx,
            f"📝 <b>Ключевые слова</b>\n\nТекущие: <code>{data.get('keywords', '?')}</code>", [
            [IKB("🔄 Заново", callback_data="trigger_edt_kw_reset")],
            [IKB("➕ Добавить", callback_data="trigger_edt_kw_add")],
            [IKB("➖ Удалить", callback_data="trigger_edt_kw_del")],
            [IKB("⏩ Пропустить", callback_data="trigger_edt_menu")],
        ])

    elif d == "trigger_edt_kw_reset":
        _set_state(ctx, TS.KEYWORDS)
        await _send_step(query, ctx, "📝 <b>Введите новые ключевые слова через запятую:</b>",
                         [[IKB("❌ Отмена", callback_data="trigger_edt_menu")]])

    elif d == "trigger_edt_kw_add":
        _set_state(ctx, TS.EDIT_KW_ADD)
        await _send_step(query, ctx, "➕ <b>Введите слова для добавления через запятую:</b>",
                         [[IKB("❌ Отмена", callback_data="trigger_edt_menu")]])

    elif d == "trigger_edt_kw_del":
        _set_state(ctx, TS.EDIT_KW_DEL)
        data = _get_data(ctx)
        await _send_step(query, ctx,
            f"➖ <b>Введите слова для удаления:</b>\n\nТекущие: <code>{data.get('keywords', '?')}</code>",
            [[IKB("❌ Отмена", callback_data="trigger_edt_menu")]])

    elif d == "trigger_edt_prob":
        _set_state(ctx, TS.EDIT_PROBABILITY)
        data = _get_data(ctx)
        await _send_step(query, ctx,
            f"🎲 <b>Вероятность</b>\n\nТекущее: <b>{data.get('probability', 100)}%</b>\n\nВведите 0–100:",
            [[IKB("⏩ Пропустить", callback_data="trigger_edt_menu")]])

    elif d == "trigger_edt_botdel":
        data = _get_data(ctx)
        cur = BOT_DEL_OPTIONS.get(data.get('bot_msg_delete', 'no'), 'Нет')
        await _send_step(query, ctx, f"🤖 <b>Удаление бот-сообщения</b>\n\nТекущее: <b>{cur}</b>", [
            [IKB("❌ Нет", callback_data="trigger_edt_botdel_no"),
             IKB("⏱ Период", callback_data="trigger_edt_botdel_period")],
            [IKB("🔄 Предыдущее", callback_data="trigger_edt_botdel_prev"),
             IKB("🔄⏱ Предыдущ.+период", callback_data="trigger_edt_botdel_prevperiod")],
            [IKB("⏩ Пропустить", callback_data="trigger_edt_menu")],
        ])

    elif d == "trigger_edt_botdel_no":
        draft['bot_msg_delete'] = 'no'
        draft['bot_msg_delete_after'] = None
        _set_data(ctx, draft)
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)

    elif d == "trigger_edt_botdel_period":
        _set_state(ctx, TS.EDIT_BOT_DEL_PERIOD)
        await _send_step(query, ctx,
            "⏱ Укажите период:\n<i>Примеры: <code>5 мин</code>, <code>2 часа</code></i>",
            [[IKB("⏩ Пропустить", callback_data="trigger_edt_menu")]])

    elif d == "trigger_edt_botdel_prev":
        draft['bot_msg_delete'] = 'previous'
        draft['bot_msg_delete_after'] = None
        _set_data(ctx, draft)
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)

    elif d == "trigger_edt_botdel_prevperiod":
        draft['bot_msg_delete'] = 'previous_period'
        _set_data(ctx, draft)
        _set_state(ctx, TS.EDIT_BOT_DEL_PERIOD)
        await _send_step(query, ctx,
            "🔄⏱ <b>Предыдущее + период</b>\n\n"
            "Через какое время удалить предыдущее сообщение?\n"
            "<i>Примеры: <code>5 мин</code>, <code>2 часа</code></i>",
            [[IKB("⏩ Пропустить", callback_data="trigger_edt_menu")]])

    elif d == "trigger_edt_menu":
        _set_state(ctx, None)
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)
        else:
            await _show_settings_menu(query, ctx)

    # ═══ ЛИМИТ СРАБАТЫВАНИЙ ═══
    elif d == "trigger_set_firelimit":
        _set_state(ctx, TS.ACT_FIRE_LIMIT)
        cur = draft.get('fire_limit')
        cur_str = str(cur) if cur is not None else "∞"
        await _send_step(query, ctx,
            f"🔢 <b>Лимит срабатываний</b>\n\n"
            f"Текущее: <b>{cur_str}</b>\n\n"
            f"Введите число (≥1) или <code>0</code> для бесконечного.\n"
            f"<i>По умолчанию: ∞ (без ограничений)</i>",
            [[IKB("∞ Без ограничений", callback_data="trigger_firelimit_inf")],
             [IKB("◀ Назад", callback_data="trigger_menu")]])

    elif d == "trigger_firelimit_inf":
        draft['fire_limit'] = None
        _set_data(ctx, draft)
        _set_state(ctx, None)
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)
        else:
            await _show_settings_menu(query, ctx)

    # ═══ АВТОЗАКРЕП ═══
    elif d == "trigger_set_autopin":
        cur = draft.get('auto_pin', 0)
        draft['auto_pin'] = 0 if cur else 1
        _set_data(ctx, draft)
        state_str = "✅ включён" if draft['auto_pin'] else "❌ выключен"
        await query.answer(f"Автозакреп {state_str}")
        edit_id = ctx.user_data.get('trigger_edit_id')
        if edit_id:
            await _show_edit_menu(query, ctx, db, edit_id)
        else:
            await _show_settings_menu(query, ctx)

    # ═══ КНОПКИ-ССЫЛКИ ═══
    elif d == "trigger_acfg_chat_buttons":
        await _show_buttons_menu(query, ctx, 'msg_chat')

    elif d == "trigger_acfg_dm_buttons":
        await _show_buttons_menu(query, ctx, 'msg_dm')

    elif d == "trigger_acfg_btn_add":
        _set_state(ctx, TS.ACT_BTN_TEXT)
        await _send_step(query, ctx,
            "🔘 <b>Добавить кнопку-ссылку</b>\n\nВведите <b>текст</b> кнопки:",
            [[IKB("❌ Отмена", callback_data="trigger_acfg_btn_cancel")]])

    elif d == "trigger_acfg_btn_cancel":
        _set_state(ctx, None)
        action_key = ctx.user_data.get('trigger_btn_action', 'msg_chat')
        ctx.user_data.pop('trigger_btn_text_tmp', None)
        await _show_buttons_menu(query, ctx, action_key)

    elif d.startswith("trigger_acfg_btn_del_"):
        idx_str = d[len("trigger_acfg_btn_del_"):]
        try:
            idx = int(idx_str)
        except ValueError:
            await query.answer("❌ Ошибка", show_alert=True)
            return
        action_key = ctx.user_data.get('trigger_btn_action', 'msg_chat')
        cfgs = draft.get('action_configs', {})
        cfg = cfgs.get(action_key, {})
        buttons = cfg.get('buttons', [])
        if 0 <= idx < len(buttons):
            buttons.pop(idx)
            cfg['buttons'] = buttons
            cfgs[action_key] = cfg
            draft['action_configs'] = cfgs
            _set_data(ctx, draft)
            await query.answer("✅ Кнопка удалена")
        await _show_buttons_menu(query, ctx, action_key)

    elif d == "trigger_acfg_msg_chat":
        await _configure_action(query, ctx, 'msg_chat')

    elif d == "trigger_acfg_msg_dm":
        await _configure_action(query, ctx, 'msg_dm')

    else:
        await query.answer("❓", show_alert=True)
