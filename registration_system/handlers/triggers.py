"""
Система триггеров — п.7 ТЗ
Создание/редактирование/список + движок обработки сообщений.
"""
import json
import logging
import random
import re
import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, ChatPermissions,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ChatType

from database import (
    get_enabled_triggers, get_all_triggers, get_trigger,
    create_trigger_db, update_trigger, delete_trigger_db, toggle_trigger,
    inc_trigger_violation, reset_trigger_violations,
    get_chat_threads, save_chat_threads,
    is_admin, get_user,
)
from config import OWNER_ID, CHAT_ID
from constants import UserRole

logger = logging.getLogger(__name__)
router = Router()

MSK = timezone(timedelta(hours=3))

# ═══════════════════════════════════════════════════════════════
#  КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════

CONDITIONS = {
    'exact':       '🎯 Точное совпадение',
    'contains':    '🔍 Содержит',
    'starts_with': '▶️ Начинается с',
    'ends_with':   '◀️ Заканчивается на',
    'whole_word':  '📝 Целое слово',
}

INITIATORS = {
    'all':    '👥 Все',
    'users':  '👤 Только пользователи',
    'owner':  '👑 Владелец',
    'admins': '🛡️ Админы и владелец',
}

TARGETS = {
    'initiator': '↩️ На инициатора',
    'all':       '📢 На всех в чате',
    'specific':  '👤 На указанного пользователя',
    'random':    '🎲 На случайного пользователя',
    'admins':    '🛡️ На администраторов',
    'nobody':    '🔇 Ни на кого',
}

ACTIONS = {
    'chat_msg': '💬 Сообщение в чат',
    'dm':       '📩 Сообщение в ЛС',
    'pin':      '📌 Закрепление',
    'delete':   '🗑️ Удалить сообщение',
    'warn':     '⚠️ Предупреждение',
    'mute':     '🔇 Мут',
    'emoji':    '😊 Эмодзи-реакция',
}

MUTE_OPTIONS = {
    '5m':  (300,   '5 мин'),
    '15m': (900,   '15 мин'),
    '30m': (1800,  '30 мин'),
    '60m': (3600,  '60 мин'),
    '24h': (86400, '24 ч'),
}

# Пороги предупреждений → мут (количество → секунды мута)
WARN_THRESHOLDS = [(3, 300), (5, 900), (10, 3600), (15, 10800)]


# ═══════════════════════════════════════════════════════════════
#  FSM STATES
# ═══════════════════════════════════════════════════════════════

class TriggerCreate(StatesGroup):
    name           = State()   # 7.2.1
    keywords       = State()   # 7.2.2
    probability    = State()   # 7.2.3
    del_period     = State()   # 7.2.4 → period input
    # 7.4 action text inputs
    chat_text      = State()
    chat_media     = State()
    dm_text        = State()
    dm_media       = State()
    emoji_input    = State()
    warn_period    = State()   # 7.4.6.2
    delay_value    = State()   # 7.4.8


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def _empty_draft(mode: str = 'create', edit_id: int = None) -> dict:
    return {
        'mode': mode,
        'edit_id': edit_id,
        'name': '',
        'keywords': '',
        'probability': 100,
        'delete_bot_msg': 'no',
        'delete_bot_msg_period': None,
        'condition': 'contains',
        'where_fires': 'all',
        'threads': [],
        'initiator': 'all',
        'target': 'nobody',
        'actions': [],
        'action_details': {},
        'delay': {'enabled': False, 'actions': [], 'details': {}},
        '_step': 'name',
        '_action_queue': [],
        '_current_action': None,
    }


def _draft_to_save(draft: dict) -> dict:
    """Convert draft to kwargs for create_trigger_db / update_trigger."""
    actions_list = []
    for atype in draft.get('actions', []):
        details = dict(draft.get('action_details', {}).get(atype, {}))
        details['type'] = atype
        if draft.get('delay', {}).get('enabled') and atype in draft['delay'].get('actions', []):
            details['delay'] = draft['delay'].get('details', {}).get(atype)
        actions_list.append(details)
    return {
        'keywords':             draft.get('keywords', ''),
        'condition':            draft.get('condition', 'contains'),
        'probability':          draft.get('probability', 100),
        'delete_bot_msg':       draft.get('delete_bot_msg', 'no'),
        'delete_bot_msg_period': draft.get('delete_bot_msg_period'),
        'where_fires':          draft.get('where_fires', 'all'),
        'threads':              json.dumps(draft.get('threads', [])),
        'initiator':            draft.get('initiator', 'all'),
        'target':               draft.get('target', 'nobody'),
        'actions':              json.dumps(actions_list),
    }


async def _is_staff(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    return await is_admin(user_id)


def _nav_buttons(skip: bool = True) -> List[List[InlineKeyboardButton]]:
    row = [
        InlineKeyboardButton(text="◀ Назад",  callback_data="tg_back"),
        InlineKeyboardButton(text="❌ Сброс", callback_data="tg_reset"),
    ]
    if skip:
        row.append(InlineKeyboardButton(text="⏩ Пропустить", callback_data="tg_skip"))
    return [row]


def _config_text(draft: dict) -> str:
    acts = draft.get('actions', [])
    acts_str = ', '.join(ACTIONS.get(a, a) for a in acts) if acts else '<i>не выбраны</i>'
    threads = draft.get('threads', [])
    where_str = '📍 Весь чат' if draft.get('where_fires') == 'all' else f'🧵 Выбранные ветки ({len(threads)})'
    del_info = draft.get('delete_bot_msg', 'no')
    if del_info == 'period' and draft.get('delete_bot_msg_period'):
        del_info = f'через {draft["delete_bot_msg_period"]} мин'
    return (
        f"⚡ <b>Настройка триггера</b>\n{'━' * 24}\n\n"
        f"📛 Название: <b>{draft.get('name', '?')}</b>\n"
        f"🔑 Слова: <code>{draft.get('keywords', '—')}</code>\n"
        f"🎲 Вероятность: <b>{draft.get('probability', 100)}%</b>\n"
        f"🗑 Удаление ответа бота: <b>{del_info}</b>\n\n"
        f"🔍 Условие: {CONDITIONS.get(draft.get('condition', 'contains'), '?')}\n"
        f"📍 Где: {where_str}\n"
        f"👤 Инициатор: {INITIATORS.get(draft.get('initiator', 'all'), '?')}\n"
        f"🎯 Цель: {TARGETS.get(draft.get('target', 'nobody'), '?')}\n"
        f"⚡ Действия: {acts_str}\n"
    )


def _config_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="Условие",         callback_data="tg_cfg_condition"),
        InlineKeyboardButton(text="Где срабатывает", callback_data="tg_cfg_where"),
    )
    b.row(
        InlineKeyboardButton(text="Инициатор", callback_data="tg_cfg_initiator"),
        InlineKeyboardButton(text="Цель",       callback_data="tg_cfg_target"),
    )
    b.row(InlineKeyboardButton(text="⚡ Действия", callback_data="tg_cfg_actions"))
    b.row(
        InlineKeyboardButton(text="◀ Назад",      callback_data="tg_back"),
        InlineKeyboardButton(text="❌ Сброс",     callback_data="tg_reset"),
        InlineKeyboardButton(text="💾 Завершить", callback_data="tg_save"),
    )
    return b.as_markup()


async def _show_config_menu(target, draft: dict, state: FSMContext):
    """Show 7.3 config menu. target = Message or CallbackQuery."""
    await state.update_data(draft=draft, _step='config')
    text = _config_text(draft)
    kb = _config_kb()
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb, parse_mode='HTML')
    else:
        await target.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


# ═══════════════════════════════════════════════════════════════
#  ENTRY POINT — opens triggers menu
# ═══════════════════════════════════════════════════════════════

async def show_triggers_menu(target, state: FSMContext = None):
    """Called from admin.py when user presses 🔔 Триггеры button."""
    if state:
        await state.clear()
    all_trig = await get_all_triggers()
    total = len(all_trig)
    enabled = sum(1 for t in all_trig if t.get('enabled'))
    text = (
        f"🔔 <b>ТРИГГЕРЫ</b>\n{'━' * 24}\n\n"
        f"📊 Всего: <b>{total}</b> | Активных: <b>{enabled}</b>\n"
        f"<i>Выберите действие:</i>"
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🔔 Создать",    callback_data="tg_create"),
        InlineKeyboardButton(text="⚡ Быстротриг", callback_data="tg_quick"),
    )
    b.row(InlineKeyboardButton(text="📰 Список", callback_data="tg_list"))
    kb = b.as_markup()
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb, parse_mode='HTML')
    else:
        await target.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


# ═══════════════════════════════════════════════════════════════
#  7.6 LIST
# ═══════════════════════════════════════════════════════════════

async def _show_list(target, state: FSMContext = None):
    if state:
        await state.clear()
    triggers = await get_all_triggers()
    text = f"📰 <b>СПИСОК ТРИГГЕРОВ</b>\n{'━' * 24}\n"
    if not triggers:
        text += "\n<i>Триггеров пока нет.</i>"
    b = InlineKeyboardBuilder()
    for t in triggers:
        tid = t['id']
        name = t.get('name', '?')
        toggle_icon = '✅' if t.get('enabled') else '❌'
        b.row(
            InlineKeyboardButton(text=name,         callback_data=f"tg_view_{tid}"),
            InlineKeyboardButton(text='✏️',          callback_data=f"tg_edit_{tid}"),
            InlineKeyboardButton(text=toggle_icon,  callback_data=f"tg_toggle_{tid}"),
            InlineKeyboardButton(text='🚫',          callback_data=f"tg_del_{tid}"),
        )
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="tg_menu"))
    if isinstance(target, Message):
        await target.answer(text, reply_markup=b.as_markup(), parse_mode='HTML')
    else:
        await target.message.edit_text(text, reply_markup=b.as_markup(), parse_mode='HTML')


async def _show_trigger_detail(callback: CallbackQuery, trigger_id: int):
    t = await get_trigger(trigger_id)
    if not t:
        await callback.answer("❌ Триггер не найден", show_alert=True)
        return
    status = "🟢 Включён" if t.get('enabled') else "🔴 Выключен"
    cond = CONDITIONS.get(t.get('condition', 'contains'), '?')
    acts_raw = t.get('actions', '[]')
    try:
        acts_list = json.loads(acts_raw)
        acts_str = ', '.join(ACTIONS.get(a.get('type', ''), a.get('type', '')) for a in acts_list) or '—'
    except Exception:
        acts_str = t.get('action', '—')
    text = (
        f"⚡ <b>{t['name']}</b>\n{'━' * 24}\n\n"
        f"🔑 Слова: <code>{t.get('keywords') or t.get('pattern', '—')}</code>\n"
        f"🔍 Условие: {cond}\n"
        f"🎲 Вероятность: {t.get('probability', 100)}%\n"
        f"⚡ Действия: {acts_str}\n"
        f"📡 Статус: {status}\n"
    )
    toggle_label = "🔴 Выключить" if t.get('enabled') else "🟢 Включить"
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=toggle_label,  callback_data=f"tg_toggle_{trigger_id}"))
    b.row(
        InlineKeyboardButton(text="✏️ Изменить", callback_data=f"tg_edit_{trigger_id}"),
        InlineKeyboardButton(text="🚫 Удалить",  callback_data=f"tg_del_{trigger_id}"),
    )
    b.row(InlineKeyboardButton(text="🔙 К списку", callback_data="tg_list"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode='HTML')


# ═══════════════════════════════════════════════════════════════
#  7.2 CREATE — step by step
# ═══════════════════════════════════════════════════════════════

async def _start_create(callback: CallbackQuery, state: FSMContext):
    draft = _empty_draft('create')
    await state.update_data(draft=draft, _step='name')
    await state.set_state(TriggerCreate.name)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Сброс", callback_data="tg_reset"))
    await callback.message.edit_text(
        "🔔 <b>Создание триггера</b> — Шаг 1/4\n\n"
        "📛 Введите <b>название триггера</b> (для списка):",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


@router.message(TriggerCreate.name, F.chat.type == ChatType.PRIVATE)
async def handle_trigger_name(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    text = message.text.strip() if message.text else ''
    if len(text) < 2 or len(text) > 60:
        await message.answer("❌ Название: от 2 до 60 символов.")
        return
    draft['name'] = text
    await state.update_data(draft=draft, _step='keywords')
    await state.set_state(TriggerCreate.keywords)
    b = InlineKeyboardBuilder()
    b.row(*[InlineKeyboardButton(text=t, callback_data=c) for t, c in [
        ("◀ Назад", "tg_back"), ("❌ Сброс", "tg_reset")
    ]])
    await message.answer(
        "🔔 <b>Создание триггера</b> — Шаг 2/4\n\n"
        "🔑 Введите <b>слова-триггеры</b> через запятую:\n"
        "<i>Пример: спам, реклама, казино</i>",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


@router.message(TriggerCreate.keywords, F.chat.type == ChatType.PRIVATE)
async def handle_trigger_keywords(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    text = message.text.strip() if message.text else ''
    if not text:
        await message.answer("❌ Введите хотя бы одно слово.")
        return
    draft['keywords'] = text
    await state.update_data(draft=draft, _step='probability')
    await state.set_state(TriggerCreate.probability)
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="◀ Назад",      callback_data="tg_back"),
        InlineKeyboardButton(text="❌ Сброс",     callback_data="tg_reset"),
        InlineKeyboardButton(text="⏩ Пропустить", callback_data="tg_skip"),
    )
    await message.answer(
        "🔔 <b>Создание триггера</b> — Шаг 3/4\n\n"
        "🎲 <b>Вероятность срабатывания</b> (0–100%):\n"
        "<i>⏩ Пропустить = 100%</i>",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


@router.message(TriggerCreate.probability, F.chat.type == ChatType.PRIVATE)
async def handle_trigger_probability(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    text = message.text.strip() if message.text else ''
    try:
        prob = int(text)
        if not 0 <= prob <= 100:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 0 до 100.")
        return
    draft['probability'] = prob
    await state.update_data(draft=draft, _step='delete_bot_msg')
    await _ask_delete_bot_msg(message, state)


async def _ask_delete_bot_msg(target, state: FSMContext):
    """7.2.4 — ask delete_bot_msg setting."""
    await state.set_state(None)
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="Нет",        callback_data="tg_delmsg_no"),
        InlineKeyboardButton(text="Период",     callback_data="tg_delmsg_period"),
        InlineKeyboardButton(text="Предыдущее", callback_data="tg_delmsg_previous"),
    )
    b.row(
        InlineKeyboardButton(text="◀ Назад", callback_data="tg_back"),
        InlineKeyboardButton(text="❌ Сброс", callback_data="tg_reset"),
    )
    text = (
        "🔔 <b>Создание триггера</b> — Шаг 4/4\n\n"
        "🗑 <b>Удалять ответное сообщение бота?</b>\n\n"
        "• <b>Нет</b> — не удалять\n"
        "• <b>Период</b> — удалить через N минут\n"
        "• <b>Предыдущее</b> — удалить предыдущий ответ этого триггера"
    )
    if isinstance(target, Message):
        await target.answer(text, reply_markup=b.as_markup(), parse_mode='HTML')
    else:
        await target.message.edit_text(text, reply_markup=b.as_markup(), parse_mode='HTML')


@router.message(TriggerCreate.del_period, F.chat.type == ChatType.PRIVATE)
async def handle_del_period(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    text = message.text.strip() if message.text else ''
    try:
        mins = int(text)
        if mins <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число минут (больше 0).")
        return
    draft['delete_bot_msg_period'] = mins
    await state.update_data(draft=draft)
    await _show_config_menu(message, draft, state)


# ═══════════════════════════════════════════════════════════════
#  7.5 EDIT — loads existing trigger into draft
# ═══════════════════════════════════════════════════════════════

async def _start_edit(callback: CallbackQuery, state: FSMContext, trigger_id: int):
    t = await get_trigger(trigger_id)
    if not t:
        await callback.answer("❌ Триггер не найден", show_alert=True)
        return
    # Load existing data into draft
    try:
        acts_raw = json.loads(t.get('actions') or '[]')
        act_keys = [a.get('type') for a in acts_raw if a.get('type')]
        act_details = {a['type']: {k: v for k, v in a.items() if k != 'type'} for a in acts_raw}
    except Exception:
        act_keys, act_details = [], {}
    try:
        threads = json.loads(t.get('threads') or '[]')
    except Exception:
        threads = []
    draft = {
        'mode': 'edit',
        'edit_id': trigger_id,
        'name': t.get('name', ''),
        'keywords': t.get('keywords') or t.get('pattern', ''),
        'probability': t.get('probability', 100),
        'delete_bot_msg': t.get('delete_bot_msg', 'no'),
        'delete_bot_msg_period': t.get('delete_bot_msg_period'),
        'condition': t.get('condition', 'contains'),
        'where_fires': t.get('where_fires', 'all'),
        'threads': threads,
        'initiator': t.get('initiator', 'all'),
        'target': t.get('target', 'nobody'),
        'actions': act_keys,
        'action_details': act_details,
        'delay': {'enabled': False, 'actions': [], 'details': {}},
        '_step': 'config',
        '_action_queue': [],
        '_current_action': None,
    }
    await _show_config_menu(callback, draft, state)


# ═══════════════════════════════════════════════════════════════
#  7.3 CONFIG MENU CALLBACKS
# ═══════════════════════════════════════════════════════════════

async def _show_condition_menu(callback: CallbackQuery, draft: dict, state: FSMContext):
    cur = draft.get('condition', 'contains')
    b = InlineKeyboardBuilder()
    for key, label in CONDITIONS.items():
        mark = '✅ ' if key == cur else ''
        b.row(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"tg_cond_{key}"))
    b.row(InlineKeyboardButton(text="◀ Назад", callback_data="tg_back_cfg"))
    await state.update_data(draft=draft, _step='condition')
    await callback.message.edit_text(
        "🔍 <b>Условие срабатывания (7.3.1)</b>\n\nВыберите условие:",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


async def _show_where_menu(callback: CallbackQuery, draft: dict, state: FSMContext):
    cur = draft.get('where_fires', 'all')
    threads = await get_chat_threads()
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=f"{'✅ ' if cur == 'all' else ''}📍 Во всём чате",
            callback_data="tg_where_all"
        )
    )
    if threads:
        b.row(
            InlineKeyboardButton(
                text=f"{'✅ ' if cur == 'threads' else ''}🧵 Выбор веток",
                callback_data="tg_where_threads"
            )
        )
        if cur == 'threads':
            selected = draft.get('threads', [])
            for th in threads:
                mark = '✅ ' if th['thread_id'] in selected else '◻️ '
                b.row(InlineKeyboardButton(
                    text=f"{mark}{th['name']}",
                    callback_data=f"tg_thread_{th['thread_id']}"
                ))
    else:
        b.row(InlineKeyboardButton(text="ℹ️ Ветки не найдены", callback_data="tg_noop"))
    b.row(InlineKeyboardButton(text="◀ Назад", callback_data="tg_back_cfg"))
    await state.update_data(draft=draft, _step='where')
    await callback.message.edit_text(
        "📍 <b>Где срабатывает (7.3.2)</b>\n\nВыберите область:",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


async def _show_initiator_menu(callback: CallbackQuery, draft: dict, state: FSMContext):
    cur = draft.get('initiator', 'all')
    b = InlineKeyboardBuilder()
    for key, label in INITIATORS.items():
        mark = '✅ ' if key == cur else ''
        b.row(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"tg_init_{key}"))
    b.row(InlineKeyboardButton(text="◀ Назад", callback_data="tg_back_cfg"))
    await state.update_data(draft=draft, _step='initiator')
    await callback.message.edit_text(
        "👤 <b>Инициатор (7.3.3)</b>\n\nКто запускает триггер:",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


async def _show_target_menu(callback: CallbackQuery, draft: dict, state: FSMContext):
    cur = draft.get('target', 'nobody')
    b = InlineKeyboardBuilder()
    for key, label in TARGETS.items():
        mark = '✅ ' if key == cur else ''
        b.row(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"tg_target_{key}"))
    b.row(InlineKeyboardButton(text="◀ Назад", callback_data="tg_back_cfg"))
    await state.update_data(draft=draft, _step='target')
    await callback.message.edit_text(
        "🎯 <b>Цель (7.3.4)</b>\n\nНа кого направлено действие:",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


async def _show_actions_menu(callback: CallbackQuery, draft: dict, state: FSMContext):
    selected = draft.get('actions', [])
    b = InlineKeyboardBuilder()
    for key, label in ACTIONS.items():
        mark = '✅ ' if key in selected else '◻️ '
        b.row(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"tg_act_toggle_{key}"))
    if selected:
        b.row(InlineKeyboardButton(text="⚙️ Настроить выбранные", callback_data="tg_act_configure"))
    b.row(InlineKeyboardButton(text="◀ Назад", callback_data="tg_back_cfg"))
    await state.update_data(draft=draft, _step='actions')
    await callback.message.edit_text(
        "⚡ <b>Действия (7.3.5)</b>\n\nВыберите одно или несколько:",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


# ═══════════════════════════════════════════════════════════════
#  7.4 ACTION CONFIGURATION
# ═══════════════════════════════════════════════════════════════

async def _start_action_config(callback: CallbackQuery, state: FSMContext):
    """Begin configuring selected actions one by one."""
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    queue = [a for a in draft.get('actions', []) if a in ('chat_msg', 'dm', 'emoji', 'warn', 'mute', 'pin', 'delete')]
    draft['_action_queue'] = queue
    draft['_current_action'] = None
    await state.update_data(draft=draft)
    await _next_action_config(callback, state)


async def _next_action_config(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    queue = draft.get('_action_queue', [])
    if not queue:
        # All configured — show delay question (7.4.8)
        await _ask_delay(callback, state)
        return
    current = queue.pop(0)
    draft['_action_queue'] = queue
    draft['_current_action'] = current
    await state.update_data(draft=draft)
    await _configure_action(callback, draft, current, state)


async def _configure_action(callback: CallbackQuery, draft: dict, atype: str, state: FSMContext):
    details = draft.get('action_details', {}).get(atype, {})

    if atype == 'chat_msg':
        await state.set_state(TriggerCreate.chat_text)
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="⏩ Пропустить", callback_data="tg_act_skip"))
        cur_text = details.get('text', '')
        hint = f"\n<i>Текущий текст: {cur_text[:60]}...</i>" if cur_text else ''
        await callback.message.edit_text(
            f"💬 <b>Сообщение в чат (7.4.1.1)</b>{hint}\n\nВведите текст сообщения:",
            reply_markup=b.as_markup(), parse_mode='HTML'
        )

    elif atype == 'dm':
        await state.set_state(TriggerCreate.dm_text)
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="⏩ Пропустить", callback_data="tg_act_skip"))
        cur_text = details.get('text', '')
        hint = f"\n<i>Текущий текст: {cur_text[:60]}...</i>" if cur_text else ''
        await callback.message.edit_text(
            f"📩 <b>Сообщение в ЛС (7.4.2.1)</b>{hint}\n\nВведите текст сообщения:",
            reply_markup=b.as_markup(), parse_mode='HTML'
        )

    elif atype == 'pin':
        b = InlineKeyboardBuilder()
        notify = details.get('notify', False)
        b.row(
            InlineKeyboardButton(text=f"{'✅ ' if notify else ''}Да", callback_data="tg_pin_notify_yes"),
            InlineKeyboardButton(text=f"{'✅ ' if not notify else ''}Нет", callback_data="tg_pin_notify_no"),
        )
        b.row(InlineKeyboardButton(text="⏩ Пропустить", callback_data="tg_act_skip"))
        await callback.message.edit_text(
            "📌 <b>Закрепление (7.4.3)</b>\n\nВключить уведомление о закреплении?",
            reply_markup=b.as_markup(), parse_mode='HTML'
        )

    elif atype == 'delete':
        what = details.get('what', ['trigger_word'])
        b = InlineKeyboardBuilder()
        t_mark = '✅ ' if 'trigger_word' in what else '◻️ '
        m_mark = '✅ ' if 'user_message' in what else '◻️ '
        b.row(InlineKeyboardButton(text=f"{t_mark}Слово-триггер",      callback_data="tg_del_what_trigger"))
        b.row(InlineKeyboardButton(text=f"{m_mark}Сообщение пользователя", callback_data="tg_del_what_message"))
        b.row(InlineKeyboardButton(text="✅ Подтвердить", callback_data="tg_act_skip"))
        await callback.message.edit_text(
            "🗑️ <b>Удаление (7.4.4)</b>\n\nЧто удалять?",
            reply_markup=b.as_markup(), parse_mode='HTML'
        )

    elif atype == 'mute':
        b = InlineKeyboardBuilder()
        cur = details.get('duration', 300)
        for key, (secs, label) in MUTE_OPTIONS.items():
            mark = '✅ ' if cur == secs else ''
            b.row(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"tg_mute_{key}"))
        await callback.message.edit_text(
            "🔇 <b>Мут (7.4.5)</b>\n\nВыберите длительность:",
            reply_markup=b.as_markup(), parse_mode='HTML'
        )

    elif atype == 'warn':
        await state.set_state(TriggerCreate.warn_period)
        b = InlineKeyboardBuilder()
        b.row(
            InlineKeyboardButton(text="Мин",  callback_data="tg_warn_unit_min"),
            InlineKeyboardButton(text="Часы", callback_data="tg_warn_unit_hours"),
            InlineKeyboardButton(text="Дни",  callback_data="tg_warn_unit_days"),
        )
        b.row(InlineKeyboardButton(text="⏩ Пропустить (30 дней)", callback_data="tg_act_skip"))
        await callback.message.edit_text(
            "⚠️ <b>Предупреждение (7.4.6)</b>\n\n"
            "Накопительная система:\n"
            "• 3 предупреждения → мут 5 мин\n"
            "• 5 → мут 15 мин\n"
            "• 10 → мут 60 мин\n"
            "• 15 → мут 3 часа\n\n"
            "<b>Период накопления — в чём?</b>",
            reply_markup=b.as_markup(), parse_mode='HTML'
        )

    elif atype == 'emoji':
        await state.set_state(TriggerCreate.emoji_input)
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="⏩ Пропустить (👍)", callback_data="tg_act_skip"))
        await callback.message.edit_text(
            "😊 <b>Эмодзи-реакция (7.4.7)</b>\n\nОтправьте эмодзи:",
            reply_markup=b.as_markup(), parse_mode='HTML'
        )


async def _ask_delay(callback: CallbackQuery, state: FSMContext):
    """7.4.8 — ask if delayed execution is needed."""
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    acts = draft.get('actions', [])
    if not acts:
        await _show_config_menu(callback, draft, state)
        return
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="Нет",  callback_data="tg_delay_no"),
        InlineKeyboardButton(text="Да",   callback_data="tg_delay_yes"),
    )
    await callback.message.edit_text(
        "⏱ <b>Отложенное срабатывание (7.4.8)</b>\n\nВыполнить действия с задержкой?",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


async def _ask_delay_actions(callback: CallbackQuery, state: FSMContext):
    """Let user choose which actions get delayed."""
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    delay = draft.get('delay', {})
    selected_delay = delay.get('actions', [])
    acts = draft.get('actions', [])
    b = InlineKeyboardBuilder()
    for atype in acts:
        mark = '✅ ' if atype in selected_delay else '◻️ '
        b.row(InlineKeyboardButton(text=f"{mark}{ACTIONS.get(atype, atype)}", callback_data=f"tg_delay_act_{atype}"))
    b.row(InlineKeyboardButton(text="▶️ Далее", callback_data="tg_delay_set_period"))
    await callback.message.edit_text(
        "⏱ Выберите действия, которые должны выполняться с задержкой:",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


# ═══════════════════════════════════════════════════════════════
#  SAVE TRIGGER
# ═══════════════════════════════════════════════════════════════

async def _save_trigger(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    if not draft.get('name') or not draft.get('keywords'):
        await callback.answer("❌ Укажите название и ключевые слова!", show_alert=True)
        return
    save_data = _draft_to_save(draft)
    try:
        if draft.get('mode') == 'edit' and draft.get('edit_id'):
            await update_trigger(draft['edit_id'], name=draft['name'], **save_data)
            await callback.answer("✅ Триггер обновлён!", show_alert=True)
        else:
            await create_trigger_db(
                name=draft['name'],
                keywords=draft['keywords'],
                created_by=callback.from_user.id,
                **save_data
            )
            await callback.answer("✅ Триггер создан!", show_alert=True)
        await state.clear()
        await _show_list(callback)
    except Exception as e:
        logger.error(f"Save trigger error: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
#  MAIN CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("tg_"), F.message.chat.type == ChatType.PRIVATE)
async def trigger_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await _is_staff(user_id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    data = callback.data
    fsm_data = await state.get_data()
    draft = fsm_data.get('draft', _empty_draft())

    # ── Menu / navigation ──
    if data == "tg_menu":
        await show_triggers_menu(callback, state)

    elif data == "tg_list":
        await _show_list(callback, state)

    elif data == "tg_create":
        await _start_create(callback, state)

    elif data == "tg_quick":
        await callback.answer("⚡ Быстротриг будет реализован позже.", show_alert=True)

    elif data == "tg_reset":
        await state.clear()
        await _start_create(callback, state)

    elif data == "tg_back":
        step = fsm_data.get('_step', 'name')
        if step == 'name':
            await state.clear()
            await show_triggers_menu(callback)
        elif step == 'keywords':
            draft['_step'] = 'name'
            await state.update_data(draft=draft, _step='name')
            await state.set_state(TriggerCreate.name)
            b = InlineKeyboardBuilder()
            b.row(InlineKeyboardButton(text="❌ Сброс", callback_data="tg_reset"))
            await callback.message.edit_text(
                f"🔔 <b>Создание триггера</b> — Шаг 1/4\n\n"
                f"📛 Введите <b>название триггера</b>:\n<i>Текущее: {draft.get('name', '—')}</i>",
                reply_markup=b.as_markup(), parse_mode='HTML'
            )
        elif step == 'probability':
            draft['_step'] = 'keywords'
            await state.update_data(draft=draft, _step='keywords')
            await state.set_state(TriggerCreate.keywords)
            b = InlineKeyboardBuilder()
            b.row(InlineKeyboardButton(text="◀ Назад", callback_data="tg_back"),
                  InlineKeyboardButton(text="❌ Сброс", callback_data="tg_reset"))
            await callback.message.edit_text(
                f"🔔 Шаг 2/4\n🔑 Введите слова-триггеры через запятую:\n<i>Текущие: {draft.get('keywords', '—')}</i>",
                reply_markup=b.as_markup(), parse_mode='HTML'
            )
        elif step in ('delete_bot_msg', 'config'):
            draft['_step'] = 'probability'
            await state.update_data(draft=draft, _step='probability')
            await state.set_state(TriggerCreate.probability)
            b = InlineKeyboardBuilder()
            b.row(InlineKeyboardButton(text="◀ Назад", callback_data="tg_back"),
                  InlineKeyboardButton(text="❌ Сброс", callback_data="tg_reset"),
                  InlineKeyboardButton(text="⏩ Пропустить", callback_data="tg_skip"))
            await callback.message.edit_text(
                f"🔔 Шаг 3/4\n🎲 Вероятность (0-100%):\n<i>Текущая: {draft.get('probability', 100)}%</i>",
                reply_markup=b.as_markup(), parse_mode='HTML'
            )
        else:
            await _show_config_menu(callback, draft, state)

    elif data == "tg_back_cfg":
        await _show_config_menu(callback, draft, state)

    elif data == "tg_skip":
        step = fsm_data.get('_step', '')
        if step == 'probability':
            draft['probability'] = 100
            await state.update_data(draft=draft, _step='delete_bot_msg')
            await _ask_delete_bot_msg(callback, state)
        elif step in ('config', 'actions'):
            await _show_config_menu(callback, draft, state)
        else:
            # Skipping action config
            await state.set_state(None)
            await _next_action_config(callback, state)

    elif data == "tg_save":
        await _save_trigger(callback, state)

    # ── 7.2.4 delete bot msg ──
    elif data == "tg_delmsg_no":
        draft['delete_bot_msg'] = 'no'
        await state.update_data(draft=draft, _step='config')
        await _show_config_menu(callback, draft, state)

    elif data == "tg_delmsg_previous":
        draft['delete_bot_msg'] = 'previous'
        await state.update_data(draft=draft, _step='config')
        await _show_config_menu(callback, draft, state)

    elif data == "tg_delmsg_period":
        draft['delete_bot_msg'] = 'period'
        await state.update_data(draft=draft, _step='del_period')
        await state.set_state(TriggerCreate.del_period)
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="◀ Назад", callback_data="tg_back"))
        await callback.message.edit_text(
            "🗑 Укажите период автоудаления в <b>минутах</b>:",
            reply_markup=b.as_markup(), parse_mode='HTML'
        )

    # ── 7.3.1 Condition ──
    elif data == "tg_cfg_condition":
        await _show_condition_menu(callback, draft, state)

    elif data.startswith("tg_cond_"):
        draft['condition'] = data[len("tg_cond_"):]
        await state.update_data(draft=draft)
        await _show_config_menu(callback, draft, state)

    # ── 7.3.2 Where ──
    elif data == "tg_cfg_where":
        await _show_where_menu(callback, draft, state)

    elif data == "tg_where_all":
        draft['where_fires'] = 'all'
        draft['threads'] = []
        await state.update_data(draft=draft)
        await _show_config_menu(callback, draft, state)

    elif data == "tg_where_threads":
        draft['where_fires'] = 'threads'
        await state.update_data(draft=draft)
        await _show_where_menu(callback, draft, state)

    elif data.startswith("tg_thread_"):
        try:
            tid = int(data[len("tg_thread_"):])
            threads = draft.get('threads', [])
            if tid in threads:
                threads.remove(tid)
            else:
                threads.append(tid)
            draft['threads'] = threads
            await state.update_data(draft=draft)
            await _show_where_menu(callback, draft, state)
        except ValueError:
            pass

    # ── 7.3.3 Initiator ──
    elif data == "tg_cfg_initiator":
        await _show_initiator_menu(callback, draft, state)

    elif data.startswith("tg_init_"):
        draft['initiator'] = data[len("tg_init_"):]
        await state.update_data(draft=draft)
        await _show_config_menu(callback, draft, state)

    # ── 7.3.4 Target ──
    elif data == "tg_cfg_target":
        await _show_target_menu(callback, draft, state)

    elif data.startswith("tg_target_"):
        draft['target'] = data[len("tg_target_"):]
        await state.update_data(draft=draft)
        await _show_config_menu(callback, draft, state)

    # ── 7.3.5 Actions multi-select ──
    elif data == "tg_cfg_actions":
        await _show_actions_menu(callback, draft, state)

    elif data.startswith("tg_act_toggle_"):
        atype = data[len("tg_act_toggle_"):]
        acts = draft.get('actions', [])
        if atype in acts:
            acts.remove(atype)
        else:
            acts.append(atype)
        draft['actions'] = acts
        await state.update_data(draft=draft)
        await _show_actions_menu(callback, draft, state)

    elif data == "tg_act_configure":
        await _start_action_config(callback, state)

    elif data == "tg_act_skip":
        await state.set_state(None)
        await _next_action_config(callback, state)

    # ── 7.4.3 Pin ──
    elif data.startswith("tg_pin_notify_"):
        notify = data == "tg_pin_notify_yes"
        action_details = draft.get('action_details', {})
        action_details['pin'] = {'notify': notify}
        draft['action_details'] = action_details
        await state.update_data(draft=draft)
        await _next_action_config(callback, state)

    # ── 7.4.4 Delete what ──
    elif data.startswith("tg_del_what_"):
        what_key = 'trigger_word' if data == 'tg_del_what_trigger' else 'user_message'
        action_details = draft.get('action_details', {})
        del_details = action_details.get('delete', {'what': []})
        what_list = del_details.get('what', [])
        if what_key in what_list:
            what_list.remove(what_key)
        else:
            what_list.append(what_key)
        del_details['what'] = what_list
        action_details['delete'] = del_details
        draft['action_details'] = action_details
        await state.update_data(draft=draft)
        # Re-show delete config
        await _configure_action(callback, draft, 'delete', state)

    # ── 7.4.5 Mute ──
    elif data.startswith("tg_mute_"):
        key = data[len("tg_mute_"):]
        secs, _ = MUTE_OPTIONS.get(key, (300, ''))
        action_details = draft.get('action_details', {})
        action_details['mute'] = {'duration': secs}
        draft['action_details'] = action_details
        await state.update_data(draft=draft)
        await _next_action_config(callback, state)

    # ── 7.4.6.2 Warn period unit ──
    elif data.startswith("tg_warn_unit_"):
        unit = data[len("tg_warn_unit_"):]
        action_details = draft.get('action_details', {})
        action_details.setdefault('warn', {})['period_unit'] = unit
        draft['action_details'] = action_details
        await state.update_data(draft=draft)
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="⏩ Пропустить (30)", callback_data="tg_act_skip"))
        await callback.message.edit_text(
            f"⚠️ Период накопления ({unit}) — введите число:",
            reply_markup=b.as_markup(), parse_mode='HTML'
        )
        await state.set_state(TriggerCreate.warn_period)

    # ── 7.4.8 Delay ──
    elif data == "tg_delay_no":
        draft['delay'] = {'enabled': False, 'actions': [], 'details': {}}
        await state.update_data(draft=draft)
        await _show_config_menu(callback, draft, state)

    elif data == "tg_delay_yes":
        draft['delay'] = {'enabled': True, 'actions': [], 'details': {}}
        await state.update_data(draft=draft)
        await _ask_delay_actions(callback, state)

    elif data.startswith("tg_delay_act_"):
        atype = data[len("tg_delay_act_"):]
        delay = draft.get('delay', {})
        delay_acts = delay.get('actions', [])
        if atype in delay_acts:
            delay_acts.remove(atype)
        else:
            delay_acts.append(atype)
        delay['actions'] = delay_acts
        draft['delay'] = delay
        await state.update_data(draft=draft)
        await _ask_delay_actions(callback, state)

    elif data == "tg_delay_set_period":
        data2 = await state.get_data()
        draft2 = data2.get('draft', draft)
        delay = draft2.get('delay', {})
        queue = list(delay.get('actions', []))
        delay['_queue'] = queue
        draft2['delay'] = delay
        await state.update_data(draft=draft2)
        await _next_delay_period(callback, state)

    elif data.startswith("tg_delay_unit_"):
        # Store unit, then ask value
        unit = data[len("tg_delay_unit_"):]
        data2 = await state.get_data()
        draft2 = data2.get('draft', draft)
        delay = draft2.get('delay', {})
        delay['_cur_unit'] = unit
        draft2['delay'] = delay
        await state.update_data(draft=draft2)
        await state.set_state(TriggerCreate.delay_value)
        await callback.message.edit_text(f"⏱ Введите задержку ({unit}):")

    # ── List actions ──
    elif data.startswith("tg_view_"):
        try:
            tid = int(data[len("tg_view_"):])
            await _show_trigger_detail(callback, tid)
        except ValueError:
            pass

    elif data.startswith("tg_edit_"):
        try:
            tid = int(data[len("tg_edit_"):])
            await _start_edit(callback, state, tid)
        except ValueError:
            pass

    elif data.startswith("tg_toggle_"):
        try:
            tid = int(data[len("tg_toggle_"):])
            new_state = await toggle_trigger(tid)
            label = "включён 🟢" if new_state else "выключен 🔴"
            await callback.answer(f"Триггер {label}", show_alert=True)
            # Refresh view
            await _show_trigger_detail(callback, tid)
        except Exception as e:
            await callback.answer(f"❌ {e}", show_alert=True)

    elif data.startswith("tg_del_"):
        if data.startswith("tg_del_confirm_"):
            try:
                tid = int(data[len("tg_del_confirm_"):])
                await delete_trigger_db(tid)
                await callback.answer("✅ Удалён.", show_alert=True)
                await _show_list(callback, state)
            except Exception as e:
                await callback.answer(f"❌ {e}", show_alert=True)
        else:
            try:
                tid = int(data[len("tg_del_"):])
                t = await get_trigger(tid)
                if t:
                    b = InlineKeyboardBuilder()
                    b.row(
                        InlineKeyboardButton(text="⚠️ ДА, удалить", callback_data=f"tg_del_confirm_{tid}"),
                        InlineKeyboardButton(text="Отмена",          callback_data=f"tg_view_{tid}"),
                    )
                    await callback.message.edit_text(
                        f"🚫 Удалить триггер <b>{t['name']}</b>?\n\n<i>Это действие нельзя отменить.</i>",
                        reply_markup=b.as_markup(), parse_mode='HTML'
                    )
            except ValueError:
                pass

    elif data == "tg_noop":
        await callback.answer()

    else:
        await callback.answer()


# ═══════════════════════════════════════════════════════════════
#  ACTION CONFIG TEXT INPUT HANDLERS
# ═══════════════════════════════════════════════════════════════

@router.message(TriggerCreate.chat_text, F.chat.type == ChatType.PRIVATE)
async def handle_chat_text(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    action_details = draft.get('action_details', {})
    action_details.setdefault('chat_msg', {})['text'] = message.text or ''
    draft['action_details'] = action_details
    await state.update_data(draft=draft)
    await state.set_state(None)
    # Ask for media (7.4.1.2)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="⏩ Пропустить", callback_data="tg_act_skip"))
    await message.answer(
        "💬 <b>Медиа (7.4.1.2)</b>\n\nОтправьте фото/видео/gif или пропустите:",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )
    await state.set_state(TriggerCreate.chat_media)


@router.message(TriggerCreate.chat_media, F.chat.type == ChatType.PRIVATE)
async def handle_chat_media(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    action_details = draft.get('action_details', {})
    chat_msg = action_details.setdefault('chat_msg', {})
    if message.photo:
        chat_msg['media_file_id'] = message.photo[-1].file_id
        chat_msg['media_type'] = 'photo'
    elif message.video:
        chat_msg['media_file_id'] = message.video.file_id
        chat_msg['media_type'] = 'video'
    elif message.animation:
        chat_msg['media_file_id'] = message.animation.file_id
        chat_msg['media_type'] = 'gif'
    draft['action_details'] = action_details
    await state.update_data(draft=draft)
    await state.set_state(None)
    # Ask media position (7.4.1.3)
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="Над сообщением",  callback_data="tg_chat_pos_above"),
        InlineKeyboardButton(text="Под сообщением",  callback_data="tg_chat_pos_below"),
    )
    await message.answer("📐 Расположение медиа:", reply_markup=b.as_markup())


@router.message(TriggerCreate.dm_text, F.chat.type == ChatType.PRIVATE)
async def handle_dm_text(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    action_details = draft.get('action_details', {})
    action_details.setdefault('dm', {})['text'] = message.text or ''
    draft['action_details'] = action_details
    await state.update_data(draft=draft)
    await state.set_state(TriggerCreate.dm_media)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="⏩ Пропустить", callback_data="tg_act_skip"))
    await message.answer(
        "📩 <b>Медиа для ЛС (7.4.2.2)</b>\n\nОтправьте фото/видео/gif или пропустите:",
        reply_markup=b.as_markup(), parse_mode='HTML'
    )


@router.message(TriggerCreate.dm_media, F.chat.type == ChatType.PRIVATE)
async def handle_dm_media(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    action_details = draft.get('action_details', {})
    dm = action_details.setdefault('dm', {})
    if message.photo:
        dm['media_file_id'] = message.photo[-1].file_id
        dm['media_type'] = 'photo'
    elif message.video:
        dm['media_file_id'] = message.video.file_id
        dm['media_type'] = 'video'
    elif message.animation:
        dm['media_file_id'] = message.animation.file_id
        dm['media_type'] = 'gif'
    draft['action_details'] = action_details
    await state.update_data(draft=draft)
    await state.set_state(None)
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="Над сообщением", callback_data="tg_dm_pos_above"),
        InlineKeyboardButton(text="Под сообщением", callback_data="tg_dm_pos_below"),
    )
    await message.answer("📐 Расположение медиа:", reply_markup=b.as_markup())


@router.message(TriggerCreate.emoji_input, F.chat.type == ChatType.PRIVATE)
async def handle_emoji_input(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    action_details = draft.get('action_details', {})
    action_details.setdefault('emoji', {})['emoji'] = message.text or '👍'
    draft['action_details'] = action_details
    await state.update_data(draft=draft)
    await state.set_state(None)
    # Fake a callback-like next step — use a message-based next
    await message.answer("✅ Эмодзи сохранён.")
    # We need to proceed to next action but we have no callback. Use a workaround:
    # Send a message with a button to continue
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="▶️ Продолжить", callback_data="tg_act_skip"))
    await message.answer("Нажмите продолжить:", reply_markup=b.as_markup())


@router.message(TriggerCreate.warn_period, F.chat.type == ChatType.PRIVATE)
async def handle_warn_period(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    text = message.text.strip() if message.text else ''
    try:
        val = int(text)
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число.")
        return
    action_details = draft.get('action_details', {})
    warn = action_details.setdefault('warn', {})
    warn['period_value'] = val
    draft['action_details'] = action_details
    await state.update_data(draft=draft)
    await state.set_state(None)
    await message.answer("✅ Период сохранён.")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="▶️ Продолжить", callback_data="tg_act_skip"))
    await message.answer("Нажмите продолжить:", reply_markup=b.as_markup())


@router.message(TriggerCreate.delay_value, F.chat.type == ChatType.PRIVATE)
async def handle_delay_value(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    text = message.text.strip() if message.text else ''
    try:
        val = int(text)
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число.")
        return
    delay = draft.get('delay', {})
    queue = delay.get('_queue', [])
    unit = delay.get('_cur_unit', 'min')
    if queue:
        current_act = queue.pop(0)
        delay.setdefault('details', {})[current_act] = {'unit': unit, 'value': val}
        delay['_queue'] = queue
    draft['delay'] = delay
    await state.update_data(draft=draft)
    await state.set_state(None)
    # Continue delay config
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="▶️ Продолжить", callback_data="tg_delay_set_period"))
    await message.answer("✅ Задержка сохранена.", reply_markup=b.as_markup())


# ═══════════════════════════════════════════════════════════════
#  MEDIA POSITION CALLBACKS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.in_({"tg_chat_pos_above", "tg_chat_pos_below"}), F.message.chat.type == ChatType.PRIVATE)
async def handle_chat_pos(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    pos = 'above' if callback.data == 'tg_chat_pos_above' else 'below'
    draft.setdefault('action_details', {}).setdefault('chat_msg', {})['media_position'] = pos
    await state.update_data(draft=draft)
    await _next_action_config(callback, state)


@router.callback_query(F.data.in_({"tg_dm_pos_above", "tg_dm_pos_below"}), F.message.chat.type == ChatType.PRIVATE)
async def handle_dm_pos(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    pos = 'above' if callback.data == 'tg_dm_pos_above' else 'below'
    draft.setdefault('action_details', {}).setdefault('dm', {})['media_position'] = pos
    await state.update_data(draft=draft)
    await _next_action_config(callback, state)


# ═══════════════════════════════════════════════════════════════
#  DELAY PERIOD — next in queue
# ═══════════════════════════════════════════════════════════════

async def _next_delay_period(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    draft = data.get('draft', _empty_draft())
    delay = draft.get('delay', {})
    queue = delay.get('_queue', [])
    if not queue:
        # Done with delays
        draft['delay'] = delay
        await state.update_data(draft=draft)
        await _show_config_menu(callback, draft, state)
        return
    act = queue[0]
    delay['_queue'] = queue
    draft['delay'] = delay
    await state.update_data(draft=draft)
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="Мин",  callback_data="tg_delay_unit_min"),
        InlineKeyboardButton(text="Часы", callback_data="tg_delay_unit_hours"),
        InlineKeyboardButton(text="Дни",  callback_data="tg_delay_unit_days"),
    )
    await callback.message.edit_text(
        f"⏱ Задержка для «{ACTIONS.get(act, act)}» — в чём измерять?",
        reply_markup=b.as_markup()
    )


# Intercept tg_delay_set_period as callback
@router.callback_query(F.data == "tg_delay_set_period", F.message.chat.type == ChatType.PRIVATE)
async def cb_delay_set_period(callback: CallbackQuery, state: FSMContext):
    await _next_delay_period(callback, state)


# ═══════════════════════════════════════════════════════════════
#  ОБНОВЛЕНИЕ СПИСКА ВЕТОК (раз в месяц через планировщик)
# ═══════════════════════════════════════════════════════════════

async def sync_chat_threads_task(bot: Bot, chat_id: int):
    """Reads forum topics/threads from chat and saves them to DB."""
    try:
        # Get forum topics if the chat supports it
        threads = []
        try:
            result = await bot.get_forum_topics(chat_id)
            for topic in result.topics:
                threads.append({'thread_id': topic.message_thread_id, 'name': topic.name})
        except Exception:
            pass  # Not a forum or no permission
        if threads:
            await save_chat_threads(threads)
            logger.info(f"Synced {len(threads)} chat threads")
    except Exception as e:
        logger.error(f"sync_chat_threads_task error: {e}")


# ═══════════════════════════════════════════════════════════════
#  PROCESSING ENGINE (7.0 — обработка входящих сообщений)
# ═══════════════════════════════════════════════════════════════

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def process_triggers(message: Message):
    """Check incoming chat messages against all enabled triggers."""
    # ОБЩЕЕ ПРАВИЛО: бот игнорирует свои собственные сообщения
    if message.from_user and message.from_user.is_bot:
        return
    if not message.text and not message.caption:
        return
    if not CHAT_ID or message.chat.id != CHAT_ID:
        return

    msg_text = (message.text or message.caption or '').lower().strip()
    if not msg_text:
        return

    triggers = await get_enabled_triggers()
    if not triggers:
        return

    user = message.from_user
    user_db = await get_user(user.id) if user else None
    user_role = user_db.get('role', UserRole.USER) if user_db else UserRole.USER

    for trigger in triggers:
        try:
            # Check initiator filter
            initiator = trigger.get('initiator', 'all')
            if initiator == 'users' and user_role in (UserRole.ADMIN, UserRole.OWNER):
                continue
            if initiator == 'owner' and user_role != UserRole.OWNER:
                continue
            if initiator == 'admins' and user_role not in (UserRole.ADMIN, UserRole.OWNER):
                continue

            # Check where_fires filter
            where_fires = trigger.get('where_fires', 'all')
            if where_fires == 'threads':
                try:
                    allowed_threads = json.loads(trigger.get('threads') or '[]')
                except Exception:
                    allowed_threads = []
                if message.message_thread_id not in allowed_threads:
                    continue

            # Check probability
            prob = trigger.get('probability') or 100
            if prob < 100 and random.randint(1, 100) > prob:
                continue

            # Match keywords
            keywords_raw = trigger.get('keywords') or trigger.get('pattern') or ''
            keywords = [kw.strip().lower() for kw in keywords_raw.split(',') if kw.strip()]
            condition = trigger.get('condition', 'contains')
            matched = False
            for kw in keywords:
                if condition == 'exact':
                    matched = msg_text == kw
                elif condition == 'contains':
                    matched = kw in msg_text
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

            logger.info(f"TRIGGER '{trigger.get('name')}' matched for user {user.id if user else '?'}")

            # Execute actions
            try:
                actions_raw = json.loads(trigger.get('actions') or '[]')
            except Exception:
                # Legacy: use old action field
                actions_raw = [{'type': trigger.get('action', 'delete')}]

            for action in actions_raw:
                atype = action.get('type', '')
                delay_info = action.get('delay')
                if delay_info:
                    # Schedule delayed action
                    asyncio.create_task(_execute_trigger_action_delayed(
                        message, trigger, action, delay_info, user_db
                    ))
                else:
                    await _execute_trigger_action(message, trigger, action, user_db)

        except Exception as e:
            logger.error(f"Error processing trigger {trigger.get('id')}: {e}")


async def _execute_trigger_action_delayed(message: Message, trigger: dict, action: dict, delay_info: dict, user_db: dict):
    try:
        unit = delay_info.get('unit', 'min')
        value = delay_info.get('value', 1)
        multipliers = {'min': 60, 'hours': 3600, 'days': 86400}
        seconds = value * multipliers.get(unit, 60)
        await asyncio.sleep(seconds)
        await _execute_trigger_action(message, trigger, action, user_db)
    except Exception as e:
        logger.error(f"Delayed action error: {e}")


async def _execute_trigger_action(message: Message, trigger: dict, action: dict, user_db: dict):
    """Execute a single trigger action."""
    atype = action.get('type', '')
    bot = message.bot
    user = message.from_user

    try:
        if atype == 'chat_msg':
            text = action.get('text', f"⚡ {trigger.get('name', 'Триггер')}")
            media_id = action.get('media_file_id')
            media_type = action.get('media_type')
            media_pos = action.get('media_position', 'below')
            sent_msg = None
            if media_id and media_pos == 'above':
                await _send_media(message, media_id, media_type, caption=text)
            elif media_id and media_pos == 'below':
                await message.answer(text)
                await _send_media(message, media_id, media_type)
            else:
                sent_msg = await message.answer(text)
            # Handle delete_bot_msg
            if sent_msg:
                await _handle_delete_bot_msg(bot, trigger, sent_msg)

        elif atype == 'dm':
            if not user:
                return
            text = action.get('text', f"⚡ {trigger.get('name', 'Триггер')}")
            media_id = action.get('media_file_id')
            media_type = action.get('media_type')
            media_pos = action.get('media_position', 'below')
            try:
                if media_id and media_pos == 'above':
                    await _send_media_to_user(bot, user.id, media_id, media_type, caption=text)
                elif media_id and media_pos == 'below':
                    await bot.send_message(user.id, text)
                    await _send_media_to_user(bot, user.id, media_id, media_type)
                else:
                    await bot.send_message(user.id, text)
            except Exception as e:
                logger.error(f"DM action failed: {e}")

        elif atype == 'pin':
            notify = action.get('notify', False)
            try:
                await bot.pin_chat_message(
                    message.chat.id, message.message_id,
                    disable_notification=not notify
                )
            except Exception as e:
                logger.error(f"Pin action failed: {e}")

        elif atype == 'delete':
            what = action.get('what', ['trigger_word'])
            if 'trigger_word' in what or 'user_message' in what:
                try:
                    await message.delete()
                except Exception:
                    pass

        elif atype == 'mute':
            if not user:
                return
            duration = action.get('duration', 300)
            until_ts = int(time.time()) + duration
            try:
                await bot.restrict_chat_member(
                    chat_id=message.chat.id,
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
                    ),
                    until_date=until_ts,
                )
            except Exception as e:
                logger.error(f"Mute action failed: {e}")

        elif atype == 'warn':
            if not user:
                return
            warn = action.get('warn', action)
            period_unit = warn.get('period_unit', 'days')
            period_value = warn.get('period_value', 30)
            unit_secs = {'min': 60, 'hours': 3600, 'days': 86400}
            period_secs = period_value * unit_secs.get(period_unit, 86400)
            count = await inc_trigger_violation(user.id, trigger['id'], period_seconds=period_secs)
            # Apply mute based on threshold
            mute_secs = 0
            for threshold, secs in WARN_THRESHOLDS:
                if count >= threshold:
                    mute_secs = secs
            name = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'
            warn_text = f"⚠️ {name}, предупреждение! ({count} из {WARN_THRESHOLDS[-1][0]})"
            await message.answer(warn_text, parse_mode='HTML')
            if mute_secs:
                until_ts = int(time.time()) + mute_secs
                try:
                    await bot.restrict_chat_member(
                        chat_id=message.chat.id, user_id=user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                        until_date=until_ts,
                    )
                    await reset_trigger_violations(user.id, trigger['id'])
                except Exception as e:
                    logger.error(f"Warn mute failed: {e}")

        elif atype == 'emoji':
            emoji = action.get('emoji', '👍')
            try:
                await message.react([{"type": "emoji", "emoji": emoji}])
            except Exception:
                pass  # React not supported in all versions

    except Exception as e:
        logger.error(f"Action '{atype}' execution error: {e}")


async def _handle_delete_bot_msg(bot: Bot, trigger: dict, sent_msg: Message):
    """Handle delete_bot_msg setting for the bot's response."""
    mode = trigger.get('delete_bot_msg', 'no')
    if mode == 'no':
        return
    elif mode == 'previous':
        prev_id = trigger.get('last_bot_msg_id')
        if prev_id:
            try:
                await bot.delete_message(sent_msg.chat.id, prev_id)
            except Exception:
                pass
        await update_trigger(trigger['id'], last_bot_msg_id=sent_msg.message_id)
    elif mode == 'period':
        period_mins = trigger.get('delete_bot_msg_period') or 5
        asyncio.create_task(_delete_after(bot, sent_msg.chat.id, sent_msg.message_id, period_mins * 60))


async def _delete_after(bot: Bot, chat_id: int, message_id: int, delay_secs: int):
    try:
        await asyncio.sleep(delay_secs)
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def _send_media(message: Message, file_id: str, media_type: str, caption: str = None):
    try:
        if media_type == 'photo':
            await message.answer_photo(file_id, caption=caption)
        elif media_type == 'video':
            await message.answer_video(file_id, caption=caption)
        elif media_type == 'gif':
            await message.answer_animation(file_id, caption=caption)
    except Exception as e:
        logger.error(f"Send media error: {e}")


async def _send_media_to_user(bot: Bot, user_id: int, file_id: str, media_type: str, caption: str = None):
    try:
        if media_type == 'photo':
            await bot.send_photo(user_id, file_id, caption=caption)
        elif media_type == 'video':
            await bot.send_video(user_id, file_id, caption=caption)
        elif media_type == 'gif':
            await bot.send_animation(user_id, file_id, caption=caption)
    except Exception as e:
        logger.error(f"Send media to user error: {e}")
