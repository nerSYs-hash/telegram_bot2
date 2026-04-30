#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
titles_handlers.py — Кастомные титулы V1.16.0.

UI юзера (меню «Баланс → 🏷 Титулы», команда /titles), FSM покупки за Пульсы
и за Рубли, переименование, обработка кнопок Владельца на карточках заявок.

Применение титула — переиспользуем handlers/shop_mechanics.py.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from handlers.shop_mechanics import apply_title_to_user

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
#  КОНСТАНТЫ
# ════════════════════════════════════════════════════════════════════════════════

# Telegram-лимит на set_chat_administrator_custom_title
MAX_TITLE_LEN = 16
MIN_TITLE_LEN = 1

# Регекс разрешённых символов: латиница, кириллица, цифры, пробел и базовая пунктуация.
_ALLOWED_RE = re.compile(r'^[\w \-_.,!?]+$', re.UNICODE)

# Колбэки
CB_USER_MENU       = 'titles_menu'
CB_PKG_PREFIX      = 'titles_pkg_'           # titles_pkg_<pkg_id>
CB_BUY_PULSES_PRE  = 'titles_buy_pulses_'    # titles_buy_pulses_<pkg_id>
CB_BUY_RUB_PRE     = 'titles_buy_rub_'       # titles_buy_rub_<pkg_id>
CB_RENAME          = 'titles_rename'
CB_CANCEL_REQ_PRE  = 'titles_cancel_req_'    # titles_cancel_req_<request_id>
CB_REQ_APPROVE_PRE = 'titles_req_approve_'   # titles_req_approve_<request_id>
CB_REQ_REJECT_PRE  = 'titles_req_reject_'    # titles_req_reject_<request_id>

# FSM-состояния (используются в ConversationHandler в bot.py)
STATE_AWAIT_TEXT_PULSES = 'TITLE_AWAIT_TEXT_PULSES'
STATE_AWAIT_TEXT_RUB    = 'TITLE_AWAIT_TEXT_RUB'
STATE_AWAIT_RENAME      = 'TITLE_AWAIT_RENAME'
STATE_AWAIT_REJECT_RSN  = 'TITLE_AWAIT_REJECT_REASON'

# user_data ключи (для прокидки контекста между шагами FSM)
UD_PKG_ID         = '_titles_pkg_id'
UD_REJECT_REQ_ID  = '_titles_reject_req_id'


# ════════════════════════════════════════════════════════════════════════════════
#  ВАЛИДАЦИЯ ТЕКСТА ТИТУЛА
# ════════════════════════════════════════════════════════════════════════════════

def validate_title_text(text: str) -> tuple[bool, Optional[str]]:
    """
    Проверка/нормализация текста титула.
    Возвращает (ok, reason). Если ok=True, reason — нормализованный текст.
    Если ok=False, reason — человеческая причина отказа.
    """
    if text is None:
        return False, 'пустой текст'

    # Нормализация: убрать невидимое + схлопнуть пробелы
    cleaned = unicodedata.normalize('NFKC', text).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)

    if not cleaned:
        return False, 'пустой текст'

    if len(cleaned) < MIN_TITLE_LEN or len(cleaned) > MAX_TITLE_LEN:
        return False, f'длина {MIN_TITLE_LEN}–{MAX_TITLE_LEN} символов (у тебя {len(cleaned)})'

    if '\n' in cleaned or '\t' in cleaned:
        return False, 'без переносов строк'

    # Запрещённые символы
    for ch in cleaned:
        cat = unicodedata.category(ch)
        # Пиктограммы, эмодзи и symbol-other — выкидываем
        if cat.startswith('S') and ch not in {'-', '_', '.'}:
            return False, 'без эмодзи и спецсимволов'
        # Контрольные/форматные символы
        if cat in ('Cc', 'Cf', 'Cs', 'Co'):
            return False, 'без управляющих символов'

    if not _ALLOWED_RE.match(cleaned):
        return False, 'разрешены только буквы, цифры, пробел и - _ . , ! ?'

    # Чёрный список явно опасных символов (на всякий случай)
    if any(c in cleaned for c in '<>/\\@#'):
        return False, 'без < > / \\ @ #'

    return True, cleaned


# ════════════════════════════════════════════════════════════════════════════════
#  ПОИСК АКТИВНОГО ТИТУЛА ЮЗЕРА В marketplace_services
# ════════════════════════════════════════════════════════════════════════════════

def get_active_title_row(db, user_id: int) -> Optional[dict]:
    """
    Вернуть dict активной записи title из marketplace_services или None.
    expires_at интерпретируем как в shop_mechanics: если NULL — бессрочно;
    если число (timestamp) и > now — активно.
    """
    import time
    db.cursor.execute(
        "SELECT id, content, expires_at, start_time, status "
        "FROM marketplace_services "
        "WHERE user_id = ? AND service_type = 'title' AND status = 'active' "
        "ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    row = db.cursor.fetchone()
    if not row:
        return None
    rec = dict(row)
    exp = rec.get('expires_at')
    if exp is None or exp == '':
        rec['_is_permanent'] = True
        return rec
    try:
        if float(exp) < time.time():
            return None
        rec['_is_permanent'] = False
    except (TypeError, ValueError):
        # неинтерпретируемое — считаем бессрочным
        rec['_is_permanent'] = True
    return rec


def format_title_remaining(row: dict) -> str:
    """Текст «активно до DD.MM.YYYY (осталось N дн)» или «Бессрочно»."""
    if row.get('_is_permanent'):
        return 'Бессрочно'
    import time
    try:
        exp_ts = float(row['expires_at'])
    except Exception:
        return 'до неизвестной даты'
    exp_dt = datetime.fromtimestamp(exp_ts)
    days_left = max(0, int((exp_ts - time.time()) // 86400))
    return f"до {exp_dt.strftime('%d.%m.%Y')} (осталось {days_left} дн)"


# ════════════════════════════════════════════════════════════════════════════════
#  ВЫДАЧА / ПРОДЛЕНИЕ ТИТУЛА
# ════════════════════════════════════════════════════════════════════════════════

async def apply_title_purchase(db, context, target_chat_id: int, user_id: int,
                               title_text: str,
                               duration_days: Optional[int]) -> dict:
    """
    Применить покупку: новая запись или продление существующей.
    Возвращает {'status': 'ok'|'already_permanent'|'apply_failed',
                'text': str|None, 'expires_at': float|None, 'extended': bool}.
    Списание денег делает вызывающий код ДО этой функции.

    Логика продления:
      - existing бессрочный → ничего не меняем (already_permanent)
      - existing срочный, новый бессрочный → expires_at = NULL
      - existing срочный, новый срочный → expires_at = max(now, existing) + duration
      - existing нет → новая запись с expires_at = now + duration (или NULL)
    Текст при продлении сохраняется (а не подменяется).
    """
    import time
    now_ts = time.time()
    existing = get_active_title_row(db, user_id)

    # Уже бессрочный — кнопку «купить» юзеру лучше не показывать,
    # но если как-то долетел — отвечаем сразу.
    if existing and existing.get('_is_permanent'):
        return {'status': 'already_permanent', 'text': existing.get('content'),
                'expires_at': None, 'extended': False}

    if existing:
        # Продлеваем
        if duration_days is None:
            new_expires = None
        else:
            try:
                base = max(now_ts, float(existing['expires_at']))
            except Exception:
                base = now_ts
            new_expires = base + duration_days * 86400
        title_to_apply = existing['content']
        try:
            db.cursor.execute(
                'UPDATE marketplace_services SET expires_at = ? WHERE id = ?',
                (new_expires, existing['id'])
            )
            db.conn.commit()
        except Exception as e:
            logger.error('apply_title_purchase: update failed: %s', e)
            return {'status': 'apply_failed', 'text': None,
                    'expires_at': None, 'extended': False}
        extended = True
    else:
        # Новая покупка
        if duration_days is None:
            new_expires = None
        else:
            new_expires = now_ts + duration_days * 86400
        title_to_apply = title_text
        try:
            db.cursor.execute(
                "INSERT INTO marketplace_services "
                "(user_id, service_type, status, content, expires_at, start_time) "
                "VALUES (?, 'title', 'active', ?, ?, ?)",
                (user_id, title_text, new_expires, now_ts)
            )
            db.conn.commit()
        except Exception as e:
            logger.error('apply_title_purchase: insert failed: %s', e)
            return {'status': 'apply_failed', 'text': None,
                    'expires_at': None, 'extended': False}
        extended = False

    ok = await apply_title_to_user(context, target_chat_id, user_id, title_to_apply)
    if not ok:
        # Откатываем БД-запись если применение провалилось
        try:
            if extended:
                # Возврат старого expires_at
                db.cursor.execute(
                    'UPDATE marketplace_services SET expires_at = ? WHERE id = ?',
                    (existing['expires_at'], existing['id'])
                )
            else:
                db.cursor.execute(
                    "DELETE FROM marketplace_services WHERE user_id = ? "
                    "AND service_type = 'title' AND status = 'active' "
                    "AND content = ? AND start_time = ?",
                    (user_id, title_text, now_ts)
                )
            db.conn.commit()
        except Exception:
            pass
        return {'status': 'apply_failed', 'text': title_to_apply,
                'expires_at': None, 'extended': extended}

    return {'status': 'ok', 'text': title_to_apply,
            'expires_at': new_expires, 'extended': extended}


# ════════════════════════════════════════════════════════════════════════════════
#  ХЕЛПЕРЫ КОНТЕКСТА
# ════════════════════════════════════════════════════════════════════════════════

def _get_db(context):
    db = context.bot_data.get('db')
    if db is None:
        raise RuntimeError("bot_data['db'] не установлен")
    return db


def _get_target_chat_id(context) -> int:
    val = context.bot_data.get('target_chat_id')
    if val is not None:
        return int(val)
    return int(os.getenv('TARGET_CHAT_ID', '0'))


def _get_main_admin_id(context) -> int:
    val = context.bot_data.get('main_admin_id')
    if val is not None:
        return int(val)
    return int(os.getenv('MAIN_ADMIN_ID', '0'))


def _get_rename_price(db) -> int:
    try:
        from database.db_settings import get_setting
        raw = get_setting(db, 'title_rename_price_pulses', '50')
        return max(0, int(raw))
    except Exception:
        return 50


def _get_request_ttl_hours(db) -> int:
    try:
        from database.db_settings import get_setting
        raw = get_setting(db, 'title_request_ttl_hours', '48')
        return max(1, int(raw))
    except Exception:
        return 48


def _format_number(n) -> str:
    try:
        return f"{int(n):,}".replace(',', ' ')
    except Exception:
        return str(n)


def _fmt_duration(days) -> str:
    if days is None:
        return 'Бессрочно'
    if days % 365 == 0 and days >= 365:
        years = days // 365
        return f'{years} {"год" if years == 1 else "года" if 2 <= years <= 4 else "лет"}'
    if days % 30 == 0 and days >= 30:
        months = days // 30
        return f'{months} мес'
    return f'{days} дн'


# ════════════════════════════════════════════════════════════════════════════════
#  ОТРИСОВКА ГЛАВНОГО ЭКРАНА
# ════════════════════════════════════════════════════════════════════════════════

def _build_titles_menu_text(db, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Собрать текст и клавиатуру главного экрана `🏷 Титулы`."""
    active = get_active_title_row(db, user_id)
    rename_price = _get_rename_price(db)

    lines = ['🏷 <b>КАСТОМНЫЙ ТИТУЛ</b>', '']
    lines.append('Это твоя приписка к нику в чате — будет видна всем рядом с твоим именем.')
    lines.append('')

    buttons: list[list[InlineKeyboardButton]] = []

    if active:
        lines.append(f"Сейчас: «{active['content']}»")
        lines.append(f"Действует {format_title_remaining(active)}")
        lines.append('')

        if active.get('_is_permanent'):
            lines.append('💎 У тебя бессрочный титул — докупать не нужно.')
        else:
            buttons.append([InlineKeyboardButton(
                '💎 Купить / Продлить', callback_data=CB_PKG_PREFIX + 'list')])

        rename_label = (f'✏️ Изменить текст · {rename_price}💎'
                        if rename_price > 0 else '✏️ Изменить текст · бесплатно')
        buttons.append([InlineKeyboardButton(rename_label, callback_data=CB_RENAME)])
    else:
        lines.append('У тебя пока нет активного титула.')
        buttons.append([InlineKeyboardButton(
            '💎 Купить', callback_data=CB_PKG_PREFIX + 'list')])

    buttons.append([InlineKeyboardButton('🔙 Назад', callback_data='menu_balance')])

    return '\n'.join(lines), InlineKeyboardMarkup(buttons)


def _build_packages_keyboard(db) -> Optional[InlineKeyboardMarkup]:
    pkgs = db.list_title_packages(only_enabled=True)
    if not pkgs:
        return None
    rows = []
    row: list[InlineKeyboardButton] = []
    for i, p in enumerate(pkgs, 1):
        row.append(InlineKeyboardButton(
            f"{p['label']}", callback_data=CB_PKG_PREFIX + str(p['id'])))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton('🔙 Назад', callback_data=CB_USER_MENU)])
    return InlineKeyboardMarkup(rows)


def _build_currency_keyboard(pkg: dict) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        f"💎 {_format_number(pkg['price_pulses'])} Пульсов",
        callback_data=CB_BUY_PULSES_PRE + str(pkg['id']))]]
    rub = pkg.get('price_rub')
    if rub and int(rub) > 0:
        rows.append([InlineKeyboardButton(
            f"💳 {_format_number(rub)} ₽ — оплата у Вити",
            callback_data=CB_BUY_RUB_PRE + str(pkg['id']))])
    rows.append([InlineKeyboardButton('🔙 К пакетам', callback_data=CB_PKG_PREFIX + 'list')])
    return InlineKeyboardMarkup(rows)


# ════════════════════════════════════════════════════════════════════════════════
#  КОМАНДА И CALLBACK ВХОДА
# ════════════════════════════════════════════════════════════════════════════════

async def cmd_titles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /titles — показать главный экран."""
    db = _get_db(context)
    user_id = update.effective_user.id
    text, kb = _build_titles_menu_text(db, user_id)
    await update.effective_message.reply_text(text, parse_mode='HTML', reply_markup=kb)


async def cb_titles_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback titles_menu — открыть/обновить главный экран."""
    query = update.callback_query
    await query.answer()
    db = _get_db(context)
    text, kb = _build_titles_menu_text(db, query.from_user.id)
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)
    except Exception:
        # Сообщение не редактируется (например — было в группе) — пришлём новое
        await query.message.reply_text(text, parse_mode='HTML', reply_markup=kb)


async def cb_titles_pkg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback titles_pkg_list или titles_pkg_<id>."""
    query = update.callback_query
    await query.answer()
    db = _get_db(context)
    data = query.data[len(CB_PKG_PREFIX):]

    if data == 'list':
        kb = _build_packages_keyboard(db)
        if kb is None:
            await query.edit_message_text(
                '⏸ Покупка титулов сейчас недоступна — пакеты не настроены.',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton('🔙 Назад', callback_data=CB_USER_MENU)
                ]])
            )
            return
        await query.edit_message_text(
            '🏷 <b>Выбери срок подписки:</b>', parse_mode='HTML', reply_markup=kb
        )
        return

    # data — pkg_id
    try:
        pkg_id = int(data)
    except ValueError:
        await query.answer('❌ Неизвестный пакет', show_alert=True)
        return
    pkg = db.get_title_package(pkg_id)
    if not pkg or not pkg['is_enabled']:
        await query.answer('❌ Пакет недоступен', show_alert=True)
        return

    text = (
        f"📦 <b>{pkg['label']}</b>\n"
        f"Срок: {_fmt_duration(pkg['duration_days'])}\n\n"
        f"Выбери валюту:"
    )
    await query.edit_message_text(text, parse_mode='HTML',
                                  reply_markup=_build_currency_keyboard(pkg))


# ════════════════════════════════════════════════════════════════════════════════
#  ПОКУПКА ЗА ПУЛЬСЫ — вход в FSM
# ════════════════════════════════════════════════════════════════════════════════

async def cb_buy_pulses_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт покупки за Пульсы: проверяем баланс, спрашиваем текст."""
    query = update.callback_query
    db = _get_db(context)
    user_id = query.from_user.id

    pkg_id_raw = query.data[len(CB_BUY_PULSES_PRE):]
    try:
        pkg_id = int(pkg_id_raw)
    except ValueError:
        await query.answer('❌ Неизвестный пакет', show_alert=True)
        return ConversationHandler.END

    pkg = db.get_title_package(pkg_id)
    if not pkg or not pkg['is_enabled']:
        await query.answer('❌ Пакет недоступен', show_alert=True)
        return ConversationHandler.END

    # Проверка баланса
    user = db.get_user(user_id)
    balance = (user['balance'] if user else 0) or 0
    price = int(pkg['price_pulses'])
    if balance < price:
        await query.answer(
            f"❌ Нужно {_format_number(price)}💎, у тебя {_format_number(balance)}💎",
            show_alert=True
        )
        return ConversationHandler.END

    # Запрет покупки поверх бессрочного
    active = get_active_title_row(db, user_id)
    if active and active.get('_is_permanent'):
        await query.answer('⚠️ У тебя уже бессрочный титул', show_alert=True)
        return ConversationHandler.END

    await query.answer()
    context.user_data[UD_PKG_ID] = pkg_id

    if active:
        # Продление — текст уже есть, сразу выполняем
        return await _do_purchase_pulses(query, context, db, user_id, pkg, active['content'])

    # Новая покупка — спрашиваем текст
    await query.edit_message_text(
        f"📦 <b>{pkg['label']}</b> · 💎 {_format_number(price)}\n\n"
        f"✏️ Введи текст титула (от {MIN_TITLE_LEN} до {MAX_TITLE_LEN} символов).\n"
        f"Разрешены буквы, цифры, пробел и знаки <code>- _ . , ! ?</code>\n\n"
        f"Для отмены — /cancel.",
        parse_mode='HTML'
    )
    return STATE_AWAIT_TEXT_PULSES


async def fsm_text_pulses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили текст для покупки за Пульсы."""
    db = _get_db(context)
    user_id = update.effective_user.id
    pkg_id = context.user_data.get(UD_PKG_ID)
    if pkg_id is None:
        await update.message.reply_text('❌ Состояние потеряно. Запусти /titles снова.')
        return ConversationHandler.END

    pkg = db.get_title_package(pkg_id)
    if not pkg:
        await update.message.reply_text('❌ Пакет не найден.')
        return ConversationHandler.END

    raw = update.message.text or ''
    ok, payload = validate_title_text(raw)
    if not ok:
        await update.message.reply_text(
            f'❌ {payload}. Попробуй ещё раз или /cancel.'
        )
        return STATE_AWAIT_TEXT_PULSES

    return await _do_purchase_pulses(update.message, context, db, user_id, pkg, payload)


async def _do_purchase_pulses(target, context, db, user_id: int, pkg: dict,
                              title_text: str):
    """
    Собственно покупка/продление за Пульсы.
    `target` — query (для edit_message_text) или message (для reply_text).
    """
    price = int(pkg['price_pulses'])
    duration_days = pkg['duration_days']

    # Повторная проверка баланса (могли потратить пока вводили текст)
    user = db.get_user(user_id)
    balance = (user['balance'] if user else 0) or 0
    if balance < price:
        await _safe_send(target, f'❌ Недостаточно средств. Баланс: {_format_number(balance)}💎')
        context.user_data.pop(UD_PKG_ID, None)
        return ConversationHandler.END

    # Списание + транзакция
    try:
        db.update_user_balance(user_id, price, 'subtract')
        db.update_bank_balance(price, 'add')
        db.add_transaction(
            user_id, None, price, 'title_purchase',
            f"Титул: {pkg['label']}"
        )
    except Exception as e:
        logger.error('title pulses purchase: списание упало: %s', e)
        await _safe_send(target, '❌ Ошибка списания. Попробуй позже.')
        context.user_data.pop(UD_PKG_ID, None)
        return ConversationHandler.END

    target_chat_id = _get_target_chat_id(context)
    result = await apply_title_purchase(db, context, target_chat_id, user_id,
                                        title_text, duration_days)

    if result['status'] != 'ok':
        # Откат
        db.update_user_balance(user_id, price, 'add')
        db.update_bank_balance(price, 'subtract')
        db.add_transaction(
            None, user_id, price, 'title_refund',
            f"Возврат: не удалось применить титул «{title_text}»"
        )
        if result['status'] == 'already_permanent':
            await _safe_send(target, '⚠️ У тебя уже бессрочный титул, средства возвращены.')
        else:
            await _safe_send(target, '⚠️ Не удалось применить титул, средства возвращены. '
                                     'Сообщи Владельцу.')
        context.user_data.pop(UD_PKG_ID, None)
        return ConversationHandler.END

    # Успех
    if result['expires_at'] is None:
        until = 'бессрочно'
    else:
        until = datetime.fromtimestamp(result['expires_at']).strftime('%d.%m.%Y')
    word = 'продлён до' if result['extended'] else 'установлен до'
    await _safe_send(
        target,
        f"✅ Титул «{result['text']}» {word} {until}.\n"
        f"Списано: {_format_number(price)}💎",
    )
    context.user_data.pop(UD_PKG_ID, None)
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════════════════════════
#  ПОКУПКА ЗА РУБЛИ — вход в FSM
# ════════════════════════════════════════════════════════════════════════════════

async def cb_buy_rub_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт заявки за Рубли: спрашиваем текст."""
    query = update.callback_query
    db = _get_db(context)
    user_id = query.from_user.id

    pkg_id_raw = query.data[len(CB_BUY_RUB_PRE):]
    try:
        pkg_id = int(pkg_id_raw)
    except ValueError:
        await query.answer('❌ Неизвестный пакет', show_alert=True)
        return ConversationHandler.END

    pkg = db.get_title_package(pkg_id)
    if not pkg or not pkg['is_enabled']:
        await query.answer('❌ Пакет недоступен', show_alert=True)
        return ConversationHandler.END
    if not pkg.get('price_rub') or int(pkg['price_rub']) <= 0:
        await query.answer('❌ Этот пакет не продаётся за рубли', show_alert=True)
        return ConversationHandler.END

    active = get_active_title_row(db, user_id)
    if active and active.get('_is_permanent'):
        await query.answer('⚠️ У тебя уже бессрочный титул', show_alert=True)
        return ConversationHandler.END

    await query.answer()
    context.user_data[UD_PKG_ID] = pkg_id

    if active:
        # Продление — текст не нужен, заявка с уже существующим текстом
        return await _create_rub_request(query, context, db, user_id, pkg, active['content'])

    await query.edit_message_text(
        f"📦 <b>{pkg['label']}</b> · 💳 {_format_number(pkg['price_rub'])} ₽\n\n"
        f"✏️ Введи текст титула (от {MIN_TITLE_LEN} до {MAX_TITLE_LEN} символов).\n"
        f"Разрешены буквы, цифры, пробел и знаки <code>- _ . , ! ?</code>\n\n"
        f"После ввода придёт инструкция как написать Владельцу для оплаты.\n"
        f"Для отмены — /cancel.",
        parse_mode='HTML'
    )
    return STATE_AWAIT_TEXT_RUB


async def fsm_text_rub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _get_db(context)
    user_id = update.effective_user.id
    pkg_id = context.user_data.get(UD_PKG_ID)
    if pkg_id is None:
        await update.message.reply_text('❌ Состояние потеряно. Запусти /titles снова.')
        return ConversationHandler.END

    pkg = db.get_title_package(pkg_id)
    if not pkg:
        await update.message.reply_text('❌ Пакет не найден.')
        return ConversationHandler.END

    raw = update.message.text or ''
    ok, payload = validate_title_text(raw)
    if not ok:
        await update.message.reply_text(f'❌ {payload}. Попробуй ещё раз или /cancel.')
        return STATE_AWAIT_TEXT_RUB

    return await _create_rub_request(update.message, context, db, user_id, pkg, payload)


async def _create_rub_request(target, context, db, user_id: int, pkg: dict,
                              title_text: str):
    """Создать заявку и отправить карточку Владельцу в ЛС."""
    price_rub = int(pkg['price_rub'])
    duration_days = pkg['duration_days']

    request_id = db.create_title_request(
        user_id=user_id, package_id=pkg['id'],
        title_text=title_text, price_rub=price_rub,
        duration_days=duration_days
    )

    main_admin_id = _get_main_admin_id(context)
    ttl = _get_request_ttl_hours(db)

    # Карточка Владельцу
    user = db.get_user(user_id)
    uname = (user['username'] or user.get('first_name') or 'юзер') if user else 'юзер'
    owner_text = (
        f"📨 <b>НОВАЯ ЗАЯВКА #{request_id}</b>\n\n"
        f"👤 @{uname} (id={user_id})\n"
        f"📦 {pkg['label']} ({_fmt_duration(duration_days)})\n"
        f"🏷 Текст: «{title_text}»\n"
        f"💳 Сумма: {_format_number(price_rub)} ₽\n\n"
        f"⌛ Истечёт через {ttl} ч."
    )
    owner_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton('✅ Подтвердить',
                             callback_data=CB_REQ_APPROVE_PRE + str(request_id)),
        InlineKeyboardButton('❌ Отклонить',
                             callback_data=CB_REQ_REJECT_PRE + str(request_id)),
    ]])
    sent = None
    try:
        sent = await context.bot.send_message(
            chat_id=main_admin_id, text=owner_text,
            parse_mode='HTML', reply_markup=owner_kb
        )
    except Exception as e:
        logger.warning('Не удалось отправить карточку Владельцу: %s', e)

    if sent is not None:
        try:
            db.attach_title_request_message(request_id, sent.chat_id, sent.message_id)
        except Exception:
            pass

    # Юзеру
    deep_link = f"tg://user?id={main_admin_id}"
    user_text = (
        f"📨 <b>Заявка #{request_id} создана</b>\n\n"
        f"📦 {pkg['label']} · 🏷 «{title_text}»\n"
        f"💳 Сумма: {_format_number(price_rub)} ₽\n\n"
        f"Напиши Владельцу для оплаты — он подтвердит, и титул применится автоматически.\n"
        f"Заявка истечёт через {ttl} ч если не будет подтверждена."
    )
    user_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('📩 Написать Владельцу', url=deep_link)],
        [InlineKeyboardButton('❌ Отменить заявку',
                              callback_data=CB_CANCEL_REQ_PRE + str(request_id))],
    ])
    await _safe_send(target, user_text, reply_markup=user_kb)
    context.user_data.pop(UD_PKG_ID, None)
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════════════════════════
#  ОТМЕНА ЗАЯВКИ ЮЗЕРОМ
# ════════════════════════════════════════════════════════════════════════════════

async def cb_user_cancel_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    db = _get_db(context)
    try:
        request_id = int(query.data[len(CB_CANCEL_REQ_PRE):])
    except ValueError:
        await query.answer('❌', show_alert=True)
        return

    req = db.get_title_request(request_id)
    if not req:
        await query.answer('❌ Заявка не найдена', show_alert=True)
        return
    if req['user_id'] != query.from_user.id:
        await query.answer('⛔ Это не твоя заявка', show_alert=True)
        return
    if req['status'] != 'pending':
        await query.answer(f'ℹ️ Статус: {req["status"]}', show_alert=True)
        return

    ok = db.transition_title_request(
        request_id, 'rejected',
        decided_by=query.from_user.id,
        reject_reason='cancelled by user',
        only_from='pending'
    )
    if not ok:
        await query.answer('ℹ️ Заявка уже обработана', show_alert=True)
        return

    await query.edit_message_text(
        f'❌ Заявка #{request_id} отменена.',
    )

    # Подредактируем карточку у Владельца (если есть)
    if req.get('owner_chat_id') and req.get('owner_msg_id'):
        try:
            await context.bot.edit_message_text(
                chat_id=req['owner_chat_id'],
                message_id=req['owner_msg_id'],
                text=f"📨 Заявка #{request_id} — ❌ ОТМЕНЕНА ЮЗЕРОМ\n"
                     f"🏷 «{req['title_text']}» · {_format_number(req['price_rub'])} ₽",
                parse_mode='HTML',
            )
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════════
#  ПЕРЕИМЕНОВАНИЕ
# ════════════════════════════════════════════════════════════════════════════════

async def cb_rename_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    db = _get_db(context)
    user_id = query.from_user.id

    active = get_active_title_row(db, user_id)
    if not active:
        await query.answer('❌ У тебя нет активного титула', show_alert=True)
        return ConversationHandler.END

    price = _get_rename_price(db)
    user = db.get_user(user_id)
    balance = (user['balance'] if user else 0) or 0
    if price > 0 and balance < price:
        await query.answer(f'❌ Нужно {_format_number(price)}💎, у тебя {_format_number(balance)}💎',
                           show_alert=True)
        return ConversationHandler.END

    await query.answer()
    await query.edit_message_text(
        f"✏️ <b>Смена текста титула</b>\n\n"
        f"Текущий: «{active['content']}»\n"
        f"Стоимость смены: "
        f"{_format_number(price) + '💎' if price > 0 else 'бесплатно'}\n\n"
        f"Введи новый текст ({MIN_TITLE_LEN}–{MAX_TITLE_LEN} символов).\n"
        f"Для отмены — /cancel.",
        parse_mode='HTML',
    )
    return STATE_AWAIT_RENAME


async def fsm_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _get_db(context)
    user_id = update.effective_user.id

    active = get_active_title_row(db, user_id)
    if not active:
        await update.message.reply_text('❌ Активный титул больше не найден.')
        return ConversationHandler.END

    raw = update.message.text or ''
    ok, payload = validate_title_text(raw)
    if not ok:
        await update.message.reply_text(f'❌ {payload}. Попробуй ещё или /cancel.')
        return STATE_AWAIT_RENAME

    new_text = payload
    price = _get_rename_price(db)
    if price > 0:
        user = db.get_user(user_id)
        balance = (user['balance'] if user else 0) or 0
        if balance < price:
            await update.message.reply_text(
                f'❌ Недостаточно средств. Баланс: {_format_number(balance)}💎'
            )
            return ConversationHandler.END
        try:
            db.update_user_balance(user_id, price, 'subtract')
            db.update_bank_balance(price, 'add')
            db.add_transaction(
                user_id, None, price, 'title_rename',
                f'Смена текста титула: «{active["content"]}» → «{new_text}»'
            )
        except Exception as e:
            logger.error('rename: списание упало: %s', e)
            await update.message.reply_text('❌ Ошибка списания.')
            return ConversationHandler.END

    target_chat_id = _get_target_chat_id(context)
    try:
        await context.bot.set_chat_administrator_custom_title(
            chat_id=target_chat_id, user_id=user_id, custom_title=new_text
        )
    except Exception as e:
        logger.error('set_chat_administrator_custom_title: %s', e)
        if price > 0:
            db.update_user_balance(user_id, price, 'add')
            db.update_bank_balance(price, 'subtract')
            db.add_transaction(
                None, user_id, price, 'title_rename_refund',
                'Возврат за смену титула — Telegram отказал'
            )
        await update.message.reply_text(
            '⚠️ Telegram не дал сменить титул, средства возвращены. '
            'Возможно, ты вышел из чата или бот потерял права.'
        )
        return ConversationHandler.END

    try:
        db.cursor.execute(
            "UPDATE marketplace_services SET content = ? "
            "WHERE id = ?",
            (new_text, active['id'])
        )
        db.conn.commit()
    except Exception as e:
        logger.error('rename: update marketplace_services: %s', e)

    suffix = f"\nСписано: {_format_number(price)}💎" if price > 0 else ''
    await update.message.reply_text(
        f"✅ Титул сменён на «{new_text}».{suffix}"
    )
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════════════════════════
#  УНИВЕРСАЛЬНЫЙ /cancel ДЛЯ FSM
# ════════════════════════════════════════════════════════════════════════════════

async def fsm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop(UD_PKG_ID, None)
    context.user_data.pop(UD_REJECT_REQ_ID, None)
    if update.message:
        await update.message.reply_text('❌ Действие отменено.')
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНОЕ
# ════════════════════════════════════════════════════════════════════════════════

async def _safe_send(target, text: str, **kwargs):
    """target = telegram.Message или telegram.CallbackQuery."""
    try:
        # CallbackQuery
        if hasattr(target, 'edit_message_text'):
            try:
                await target.edit_message_text(text, parse_mode='HTML', **kwargs)
                return
            except Exception:
                pass
            await target.message.reply_text(text, parse_mode='HTML', **kwargs)
            return
        # Message
        await target.reply_text(text, parse_mode='HTML', **kwargs)
    except Exception as e:
        logger.warning('_safe_send: %s', e)


# ════════════════════════════════════════════════════════════════════════════════
#  CONVERSATIONHANDLER + РЕГИСТРАЦИЯ
# ════════════════════════════════════════════════════════════════════════════════

titles_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(cb_buy_pulses_entry, pattern=f'^{CB_BUY_PULSES_PRE}\\d+$'),
        CallbackQueryHandler(cb_buy_rub_entry,    pattern=f'^{CB_BUY_RUB_PRE}\\d+$'),
        CallbackQueryHandler(cb_rename_entry,     pattern=f'^{CB_RENAME}$'),
    ],
    states={
        STATE_AWAIT_TEXT_PULSES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_text_pulses),
        ],
        STATE_AWAIT_TEXT_RUB: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_text_rub),
        ],
        STATE_AWAIT_RENAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_rename),
        ],
    },
    fallbacks=[
        CommandHandler('cancel', fsm_cancel),
        # /titles, /start как «жёсткий рестарт» из любого состояния
        CommandHandler('titles', fsm_cancel),
        CommandHandler('start',  fsm_cancel),
    ],
    per_message=False,
    name='titles_conv',
    persistent=False,
)


def register_titles(application, db, target_chat_id: int, main_admin_id: int) -> None:
    """
    Зарегистрировать всю систему титулов в PTB Application.
    Вызывать из bot.py после `application.bot_data['db'] = self.db`.
    """
    application.bot_data['db'] = db
    application.bot_data['target_chat_id'] = target_chat_id
    application.bot_data['main_admin_id'] = main_admin_id

    # Команда
    application.add_handler(CommandHandler('titles', cmd_titles))

    # Главный экран и навигация — НЕ через ConversationHandler
    application.add_handler(CallbackQueryHandler(cb_titles_menu, pattern=f'^{CB_USER_MENU}$'))
    application.add_handler(CallbackQueryHandler(cb_titles_pkg,  pattern=f'^{CB_PKG_PREFIX}'))
    application.add_handler(CallbackQueryHandler(cb_user_cancel_request,
                                                 pattern=f'^{CB_CANCEL_REQ_PRE}\\d+$'))

    # FSM (покупки + переименование)
    application.add_handler(titles_conv)

