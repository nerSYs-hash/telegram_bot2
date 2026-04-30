#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
owner_titles_panel.py — Панель Владельца для системы Титулов (V1.16.0).

Содержит:
- Главный экран `owner_titles_menu`
- CRUD пакетов (раздел Пакеты)
- Настройка цены переименования (`title_rename_price_pulses`)
- Настройка TTL заявок (`title_request_ttl_hours`)
- Лента и обработка заявок на оплату (`approve` / `reject` с причиной)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from handlers.titles_handlers import (
    apply_title_purchase, validate_title_text,
    _get_db, _get_target_chat_id, _get_main_admin_id,
    _format_number, _fmt_duration, _get_rename_price, _get_request_ttl_hours,
    CB_REQ_APPROVE_PRE, CB_REQ_REJECT_PRE,
    UD_REJECT_REQ_ID,
    STATE_AWAIT_REJECT_RSN,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
#  КОЛБЭКИ
# ════════════════════════════════════════════════════════════════════════════════

CB_OWNER_MENU         = 'owner_titles_menu'
CB_PKG_LIST           = 'owner_titles_packages'
CB_PKG_CARD_PRE       = 'owner_titles_pkg_'           # owner_titles_pkg_<id>
CB_PKG_TOGGLE_PRE     = 'owner_titles_pkg_toggle_'    # owner_titles_pkg_toggle_<id>
CB_PKG_EDIT_PRE       = 'owner_titles_pkg_edit_'      # owner_titles_pkg_edit_<id>_<field>
CB_PKG_ADD            = 'owner_titles_pkg_add'
CB_RENAME_PRICE       = 'owner_titles_rename_price'
CB_TTL                = 'owner_titles_ttl'
CB_REQUESTS           = 'owner_titles_requests'

# FSM states
ST_PKG_ADD_LABEL    = 'OT_PKG_ADD_LABEL'
ST_PKG_ADD_DAYS     = 'OT_PKG_ADD_DAYS'
ST_PKG_ADD_PULSES   = 'OT_PKG_ADD_PULSES'
ST_PKG_ADD_RUB      = 'OT_PKG_ADD_RUB'
ST_PKG_EDIT_VALUE   = 'OT_PKG_EDIT_VALUE'
ST_RENAME_PRICE_VAL = 'OT_RENAME_PRICE_VAL'
ST_TTL_VAL          = 'OT_TTL_VAL'

# user_data ключи
UD_NEW_PKG       = '_ot_new_pkg'      # dict-черновик при добавлении
UD_EDIT_PKG_ID   = '_ot_edit_pkg_id'
UD_EDIT_FIELD    = '_ot_edit_field'   # 'label' / 'duration_days' / 'price_pulses' / 'price_rub'


# ════════════════════════════════════════════════════════════════════════════════
#  ПРАВА
# ════════════════════════════════════════════════════════════════════════════════

def _is_owner(context, user_id: int) -> bool:
    main_admin_id = _get_main_admin_id(context)
    return user_id == main_admin_id


# ════════════════════════════════════════════════════════════════════════════════
#  ГЛАВНЫЙ ЭКРАН
# ════════════════════════════════════════════════════════════════════════════════

def _build_owner_menu(db) -> tuple[str, InlineKeyboardMarkup]:
    pkgs = db.list_title_packages(only_enabled=False)
    enabled = sum(1 for p in pkgs if p['is_enabled'])
    pending = db.count_title_requests_pending()
    rename_price = _get_rename_price(db)
    ttl = _get_request_ttl_hours(db)

    text = (
        "🛍 <b>НАСТРОЙКА ТИТУЛОВ</b>\n\n"
        f"📦 Пакетов всего: {len(pkgs)} (активно: {enabled})\n"
        f"💸 Цена переименования: {rename_price}💎\n"
        f"⏱ TTL заявок (рубли): {ttl} ч\n"
        f"📨 Pending заявок: {pending}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('📦 Пакеты', callback_data=CB_PKG_LIST)],
        [InlineKeyboardButton('✏️ Цена переименования', callback_data=CB_RENAME_PRICE)],
        [InlineKeyboardButton('⏱ TTL заявок', callback_data=CB_TTL)],
        [InlineKeyboardButton(f'📨 Заявки на оплату ({pending})',
                              callback_data=CB_REQUESTS)],
        [InlineKeyboardButton('🔙 Назад', callback_data='owner_dashboard')],
    ])
    return text, kb


async def cb_owner_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return
    await query.answer()
    db = _get_db(context)
    text, kb = _build_owner_menu(db)
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)
    except Exception:
        await query.message.reply_text(text, parse_mode='HTML', reply_markup=kb)


# ════════════════════════════════════════════════════════════════════════════════
#  РАЗДЕЛ ПАКЕТЫ
# ════════════════════════════════════════════════════════════════════════════════

def _format_pkg_row(p: dict) -> str:
    icon = '🟢' if p['is_enabled'] else '⚪'
    rub = (f' · {_format_number(p["price_rub"])}₽' if p['price_rub'] else ' · —₽')
    return (f"{icon} {p['label']} ({_fmt_duration(p['duration_days'])}) · "
            f"{_format_number(p['price_pulses'])}💎{rub}")


def _build_pkg_list(db) -> tuple[str, InlineKeyboardMarkup]:
    pkgs = db.list_title_packages(only_enabled=False)
    text = '📦 <b>ПАКЕТЫ ТИТУЛОВ</b>\n\n'
    if pkgs:
        text += '\n'.join(_format_pkg_row(p) for p in pkgs)
    else:
        text += '— ни одного пакета —'
    rows = [[InlineKeyboardButton(p['label'],
                                  callback_data=CB_PKG_CARD_PRE + str(p['id']))]
            for p in pkgs]
    rows.append([InlineKeyboardButton('➕ Добавить пакет', callback_data=CB_PKG_ADD)])
    rows.append([InlineKeyboardButton('🔙 Назад', callback_data=CB_OWNER_MENU)])
    return text, InlineKeyboardMarkup(rows)


async def cb_pkg_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return
    await query.answer()
    db = _get_db(context)
    text, kb = _build_pkg_list(db)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)


def _build_pkg_card(pkg: dict) -> tuple[str, InlineKeyboardMarkup]:
    rub = f"{_format_number(pkg['price_rub'])} ₽" if pkg['price_rub'] else 'не продаётся'
    text = (
        f"📦 <b>«{pkg['label']}»</b>\n"
        f"Срок: {_fmt_duration(pkg['duration_days'])}\n"
        f"💎 Пульсы: {_format_number(pkg['price_pulses'])}\n"
        f"💳 Рубли: {rub}\n"
        f"Состояние: {'🟢 включён' if pkg['is_enabled'] else '⚪ выключен'}"
    )
    pid = pkg['id']
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('✏️ Срок', callback_data=f'{CB_PKG_EDIT_PRE}{pid}_duration_days'),
         InlineKeyboardButton('💎 Пульсы', callback_data=f'{CB_PKG_EDIT_PRE}{pid}_price_pulses')],
        [InlineKeyboardButton('💳 Рубли', callback_data=f'{CB_PKG_EDIT_PRE}{pid}_price_rub'),
         InlineKeyboardButton('📝 Название', callback_data=f'{CB_PKG_EDIT_PRE}{pid}_label')],
        [InlineKeyboardButton('🔴 Выключить' if pkg['is_enabled'] else '🟢 Включить',
                              callback_data=f'{CB_PKG_TOGGLE_PRE}{pid}')],
        [InlineKeyboardButton('🔙 К списку', callback_data=CB_PKG_LIST)],
    ])
    return text, kb


async def cb_pkg_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return
    try:
        pid = int(query.data[len(CB_PKG_CARD_PRE):])
    except ValueError:
        await query.answer('❌', show_alert=True); return
    db = _get_db(context)
    pkg = db.get_title_package(pid)
    if not pkg:
        await query.answer('❌ Пакет не найден', show_alert=True); return
    await query.answer()
    text, kb = _build_pkg_card(pkg)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)


async def cb_pkg_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return
    try:
        pid = int(query.data[len(CB_PKG_TOGGLE_PRE):])
    except ValueError:
        await query.answer('❌', show_alert=True); return
    db = _get_db(context)
    new_val = db.toggle_title_package(pid)
    if new_val is None:
        await query.answer('❌ Пакет не найден', show_alert=True); return
    await query.answer('🟢 Включён' if new_val else '⚪ Выключен')
    pkg = db.get_title_package(pid)
    text, kb = _build_pkg_card(pkg)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)


# ── FSM добавления пакета ──────────────────────────────────────────────────────

async def cb_pkg_add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return ConversationHandler.END
    await query.answer()
    context.user_data[UD_NEW_PKG] = {}
    await query.edit_message_text(
        '➕ <b>Новый пакет — 1/4</b>\n\n'
        'Введи название (например: «1 месяц», «Навсегда»).',
        parse_mode='HTML',
    )
    return ST_PKG_ADD_LABEL


async def fsm_pkg_label(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(context, update.effective_user.id):
        return ConversationHandler.END
    label = (update.message.text or '').strip()
    if not (1 <= len(label) <= 30):
        await update.message.reply_text('❌ Длина 1–30 символов. Попробуй ещё или /cancel.')
        return ST_PKG_ADD_LABEL
    context.user_data[UD_NEW_PKG]['label'] = label
    await update.message.reply_text(
        '<b>2/4</b> — введи срок в днях (целое число > 0).\n'
        'Напиши <code>0</code> или <code>-</code> для пакета «Навсегда».',
        parse_mode='HTML',
    )
    return ST_PKG_ADD_DAYS


async def fsm_pkg_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(context, update.effective_user.id):
        return ConversationHandler.END
    raw = (update.message.text or '').strip()
    if raw in ('0', '-', 'навсегда', 'permanent'):
        days = None
    else:
        try:
            days = int(raw)
            if days <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                '❌ Введи положительное число дней или 0/- для бессрочного. /cancel — отмена.'
            )
            return ST_PKG_ADD_DAYS
    context.user_data[UD_NEW_PKG]['duration_days'] = days
    await update.message.reply_text(
        '<b>3/4</b> — цена в Пульсах (целое > 0).',
        parse_mode='HTML',
    )
    return ST_PKG_ADD_PULSES


async def fsm_pkg_pulses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(context, update.effective_user.id):
        return ConversationHandler.END
    try:
        v = int((update.message.text or '').strip())
        if v <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text('❌ Целое > 0. Попробуй ещё или /cancel.')
        return ST_PKG_ADD_PULSES
    context.user_data[UD_NEW_PKG]['price_pulses'] = v
    await update.message.reply_text(
        '<b>4/4</b> — цена в Рублях (целое ≥ 0).\n'
        '<code>0</code> = пакет не продаётся за рубли.',
        parse_mode='HTML',
    )
    return ST_PKG_ADD_RUB


async def fsm_pkg_rub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(context, update.effective_user.id):
        return ConversationHandler.END
    try:
        v = int((update.message.text or '').strip())
        if v < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text('❌ Целое ≥ 0. Попробуй ещё или /cancel.')
        return ST_PKG_ADD_RUB
    rub = v if v > 0 else None
    db = _get_db(context)
    draft = context.user_data.get(UD_NEW_PKG, {})
    pid = db.create_title_package(
        label=draft.get('label', '?'),
        duration_days=draft.get('duration_days'),
        price_pulses=draft.get('price_pulses', 0),
        price_rub=rub,
    )
    context.user_data.pop(UD_NEW_PKG, None)
    await update.message.reply_text(
        f"✅ Пакет #{pid} создан.",
    )
    text, kb = _build_pkg_list(db)
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    return ConversationHandler.END


# ── FSM редактирования отдельного поля пакета ──────────────────────────────────

async def cb_pkg_edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return ConversationHandler.END
    rest = query.data[len(CB_PKG_EDIT_PRE):]   # "<id>_<field>"
    try:
        pid_str, field = rest.split('_', 1)
        pid = int(pid_str)
    except ValueError:
        await query.answer('❌', show_alert=True); return ConversationHandler.END
    if field not in ('label', 'duration_days', 'price_pulses', 'price_rub'):
        await query.answer('❌', show_alert=True); return ConversationHandler.END

    context.user_data[UD_EDIT_PKG_ID] = pid
    context.user_data[UD_EDIT_FIELD] = field
    await query.answer()

    prompts = {
        'label': 'Новое название (1–30 символов).',
        'duration_days': 'Новый срок в днях (целое > 0). 0/- = бессрочно.',
        'price_pulses': 'Новая цена в Пульсах (целое > 0).',
        'price_rub': 'Новая цена в Рублях (целое ≥ 0). 0 = не продаётся за рубли.',
    }
    await query.edit_message_text(
        f"✏️ Изменение поля <b>{field}</b>.\n\n{prompts[field]}\n\n/cancel — отмена.",
        parse_mode='HTML',
    )
    return ST_PKG_EDIT_VALUE


async def fsm_pkg_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(context, update.effective_user.id):
        return ConversationHandler.END
    pid = context.user_data.get(UD_EDIT_PKG_ID)
    field = context.user_data.get(UD_EDIT_FIELD)
    if pid is None or field is None:
        return ConversationHandler.END

    raw = (update.message.text or '').strip()
    db = _get_db(context)

    if field == 'label':
        if not (1 <= len(raw) <= 30):
            await update.message.reply_text('❌ Длина 1–30. /cancel — отмена.')
            return ST_PKG_EDIT_VALUE
        db.update_title_package(pid, label=raw)
    elif field == 'duration_days':
        if raw in ('0', '-', 'навсегда', 'permanent'):
            db.update_title_package(pid, duration_days=None)
        else:
            try:
                v = int(raw)
                if v <= 0: raise ValueError
            except ValueError:
                await update.message.reply_text('❌ Целое > 0 или 0/- для бессрочного.')
                return ST_PKG_EDIT_VALUE
            db.update_title_package(pid, duration_days=v)
    elif field == 'price_pulses':
        try:
            v = int(raw)
            if v <= 0: raise ValueError
        except ValueError:
            await update.message.reply_text('❌ Целое > 0.')
            return ST_PKG_EDIT_VALUE
        db.update_title_package(pid, price_pulses=v)
    elif field == 'price_rub':
        try:
            v = int(raw)
            if v < 0: raise ValueError
        except ValueError:
            await update.message.reply_text('❌ Целое ≥ 0.')
            return ST_PKG_EDIT_VALUE
        db.update_title_package(pid, price_rub=(v if v > 0 else None))

    context.user_data.pop(UD_EDIT_PKG_ID, None)
    context.user_data.pop(UD_EDIT_FIELD, None)
    await update.message.reply_text('✅ Сохранено.')
    pkg = db.get_title_package(pid)
    if pkg:
        text, kb = _build_pkg_card(pkg)
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════════════════════════
#  ЦЕНА ПЕРЕИМЕНОВАНИЯ
# ════════════════════════════════════════════════════════════════════════════════

async def cb_rename_price_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return ConversationHandler.END
    await query.answer()
    db = _get_db(context)
    cur = _get_rename_price(db)
    await query.edit_message_text(
        f"💸 <b>Цена переименования титула</b>\n\nТекущее: {cur}💎\n\n"
        f"Введи новое значение (целое ≥ 0). 0 = бесплатно.\n/cancel — отмена.",
        parse_mode='HTML',
    )
    return ST_RENAME_PRICE_VAL


async def fsm_rename_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(context, update.effective_user.id):
        return ConversationHandler.END
    try:
        v = int((update.message.text or '').strip())
        if v < 0: raise ValueError
    except ValueError:
        await update.message.reply_text('❌ Целое ≥ 0.')
        return ST_RENAME_PRICE_VAL
    db = _get_db(context)
    db.set_setting('title_rename_price_pulses', str(v))
    await update.message.reply_text(f'✅ Цена переименования: {v}💎')
    text, kb = _build_owner_menu(db)
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════════════════════════
#  TTL ЗАЯВОК
# ════════════════════════════════════════════════════════════════════════════════

async def cb_ttl_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return ConversationHandler.END
    await query.answer()
    db = _get_db(context)
    cur = _get_request_ttl_hours(db)
    await query.edit_message_text(
        f"⏱ <b>TTL pending-заявок (часы)</b>\n\nТекущее: {cur} ч\n\n"
        f"Введи новое значение (целое > 0).\n"
        f"Через столько часов неподтверждённая заявка авто-помечается expired.\n/cancel — отмена.",
        parse_mode='HTML',
    )
    return ST_TTL_VAL


async def fsm_ttl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(context, update.effective_user.id):
        return ConversationHandler.END
    try:
        v = int((update.message.text or '').strip())
        if v <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text('❌ Целое > 0.')
        return ST_TTL_VAL
    db = _get_db(context)
    db.set_setting('title_request_ttl_hours', str(v))
    await update.message.reply_text(f'✅ TTL заявок: {v} ч')
    text, kb = _build_owner_menu(db)
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════════════════════════
#  ЛЕНТА ЗАЯВОК
# ════════════════════════════════════════════════════════════════════════════════

def _format_request_row(r: dict) -> str:
    icons = {'pending': '🟡', 'approved': '✅', 'rejected': '❌',
             'rejected_user_left': '⚠️', 'expired': '⌛'}
    icon = icons.get(r['status'], '·')
    when = (r.get('decided_at') or r.get('created_at') or '')[:16].replace('T', ' ')
    return (f"{icon} #{r['id']} · @{r['user_id']} · «{r['title_text']}» · "
            f"{_format_number(r['price_rub'])}₽ · {when}")


async def cb_requests_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return
    await query.answer()
    db = _get_db(context)
    rows = db.list_title_requests(limit=20)

    text = '📨 <b>ЗАЯВКИ НА ОПЛАТУ</b>\n\n'
    if not rows:
        text += '— заявок пока нет —'
    else:
        text += '\n'.join(_format_request_row(r) for r in rows)

    kb_rows = []
    for r in rows:
        if r['status'] == 'pending':
            kb_rows.append([
                InlineKeyboardButton(f'✅ #{r["id"]}',
                                     callback_data=CB_REQ_APPROVE_PRE + str(r['id'])),
                InlineKeyboardButton(f'❌ #{r["id"]}',
                                     callback_data=CB_REQ_REJECT_PRE + str(r['id'])),
            ])
    kb_rows.append([InlineKeyboardButton('🔙 Назад', callback_data=CB_OWNER_MENU)])
    await query.edit_message_text(text, parse_mode='HTML',
                                  reply_markup=InlineKeyboardMarkup(kb_rows))


# ════════════════════════════════════════════════════════════════════════════════
#  ПОДТВЕРЖДЕНИЕ ЗАЯВКИ
# ════════════════════════════════════════════════════════════════════════════════

async def cb_request_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return
    try:
        rid = int(query.data[len(CB_REQ_APPROVE_PRE):])
    except ValueError:
        await query.answer('❌', show_alert=True); return

    db = _get_db(context)
    req = db.get_title_request(rid)
    if not req:
        await query.answer('❌ Заявка не найдена', show_alert=True); return
    if req['status'] != 'pending':
        await query.answer(f'ℹ️ Статус: {req["status"]}', show_alert=True); return

    # Атомарный переход в approved
    ok = db.transition_title_request(
        rid, 'approved', decided_by=query.from_user.id, only_from='pending'
    )
    if not ok:
        await query.answer('⚠️ Заявка уже обработана', show_alert=True); return

    # Применяем титул
    target_chat_id = _get_target_chat_id(context)
    result = await apply_title_purchase(
        db, context, target_chat_id, req['user_id'],
        req['title_text'], req['duration_days']
    )

    if result['status'] != 'ok':
        # Откат статуса в rejected_user_left
        db.transition_title_request(
            rid, 'rejected_user_left', decided_by=query.from_user.id,
            reject_reason='apply failed', only_from='approved'
        )
        await query.answer(
            f'⚠️ Не удалось применить (юзер вне чата?). Заявка помечена.',
            show_alert=True
        )
        try:
            await query.edit_message_text(
                f"📨 ЗАЯВКА #{rid} — ⚠️ ПРИМЕНЕНИЕ ОТМЕНЕНО\n\n"
                f"🏷 «{req['title_text']}» · {_format_number(req['price_rub'])} ₽\n"
                f"Причина: юзер вне чата или Telegram отказал.\n"
                f"💡 Деньги решайте в личке.",
                parse_mode='HTML',
            )
        except Exception:
            pass
        return

    # Успех — редактируем карточку у Владельца
    if result['expires_at'] is None:
        until = 'бессрочно'
    else:
        until = datetime.fromtimestamp(result['expires_at']).strftime('%d.%m.%Y')
    word = 'продлён до' if result['extended'] else 'установлен до'

    try:
        await query.edit_message_text(
            f"📨 ЗАЯВКА #{rid} — ✅ ПОДТВЕРЖДЕНО\n\n"
            f"👤 user_id={req['user_id']} · {_format_number(req['price_rub'])} ₽\n"
            f"🏷 Применён «{result['text']}» {word} {until}\n"
            f"👍 Витя · {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode='HTML',
        )
    except Exception:
        pass

    # DM юзеру
    try:
        await context.bot.send_message(
            chat_id=req['user_id'],
            text=(f"✅ Заявка #{rid} подтверждена!\n"
                  f"Титул «{result['text']}» {word} {until}."),
            parse_mode='HTML',
        )
    except Exception as e:
        logger.warning('DM юзеру об одобрении не доставлено: %s', e)


# ════════════════════════════════════════════════════════════════════════════════
#  ОТКАЗ ЗАЯВКИ — FSM ПРИЧИНЫ
# ════════════════════════════════════════════════════════════════════════════════

async def cb_request_reject_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_owner(context, query.from_user.id):
        await query.answer('⛔', show_alert=True); return ConversationHandler.END
    try:
        rid = int(query.data[len(CB_REQ_REJECT_PRE):])
    except ValueError:
        await query.answer('❌', show_alert=True); return ConversationHandler.END

    db = _get_db(context)
    req = db.get_title_request(rid)
    if not req:
        await query.answer('❌ Заявка не найдена', show_alert=True); return ConversationHandler.END
    if req['status'] != 'pending':
        await query.answer(f'ℹ️ Статус: {req["status"]}', show_alert=True); return ConversationHandler.END

    await query.answer()
    context.user_data[UD_REJECT_REQ_ID] = rid
    await query.edit_message_text(
        f"❌ Отклонить заявку #{rid}?\n\n"
        f"🏷 «{req['title_text']}» · {_format_number(req['price_rub'])} ₽\n\n"
        f"Введи причину (видна юзеру) или /skip без причины.\n"
        f"/cancel — оставить pending.",
        parse_mode='HTML',
    )
    return STATE_AWAIT_REJECT_RSN


async def fsm_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rid = context.user_data.get(UD_REJECT_REQ_ID)
    if rid is None:
        return ConversationHandler.END
    if not _is_owner(context, update.effective_user.id):
        return ConversationHandler.END

    raw = (update.message.text or '').strip()
    reason = '' if raw.lower() in ('/skip', 'skip', '-') else raw[:200]

    db = _get_db(context)
    ok = db.transition_title_request(
        rid, 'rejected', decided_by=update.effective_user.id,
        reject_reason=(reason or 'без причины'),
        only_from='pending'
    )
    context.user_data.pop(UD_REJECT_REQ_ID, None)

    if not ok:
        await update.message.reply_text('⚠️ Заявка уже обработана.')
        return ConversationHandler.END

    req = db.get_title_request(rid)
    await update.message.reply_text(f'❌ Заявка #{rid} отклонена.')

    # DM юзеру
    if req:
        msg = (f"❌ Заявка #{rid} отклонена.\n"
               f"🏷 «{req['title_text']}» · {_format_number(req['price_rub'])} ₽")
        if reason:
            msg += f"\n💬 Причина: {reason}"
        try:
            await context.bot.send_message(req['user_id'], msg, parse_mode='HTML')
        except Exception:
            pass

    return ConversationHandler.END


async def fsm_reject_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Алиас на /skip — ничего не вводим, отклоняем без причины."""
    update.message.text = '/skip'
    return await fsm_reject_reason(update, context)


# ════════════════════════════════════════════════════════════════════════════════
#  УНИВЕРСАЛЬНЫЙ /cancel ДЛЯ FSM ПАНЕЛИ
# ════════════════════════════════════════════════════════════════════════════════

async def fsm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for k in (UD_NEW_PKG, UD_EDIT_PKG_ID, UD_EDIT_FIELD, UD_REJECT_REQ_ID):
        context.user_data.pop(k, None)
    if update.message:
        await update.message.reply_text('❌ Действие отменено.')
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════════════════════════
#  CONVERSATIONHANDLERS + РЕГИСТРАЦИЯ
# ════════════════════════════════════════════════════════════════════════════════

owner_titles_pkg_add_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(cb_pkg_add_entry, pattern=f'^{CB_PKG_ADD}$')],
    states={
        ST_PKG_ADD_LABEL:  [MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_pkg_label)],
        ST_PKG_ADD_DAYS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_pkg_days)],
        ST_PKG_ADD_PULSES: [MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_pkg_pulses)],
        ST_PKG_ADD_RUB:    [MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_pkg_rub)],
    },
    fallbacks=[CommandHandler('cancel', fsm_cancel)],
    per_message=False,
    name='owner_titles_pkg_add',
)

owner_titles_pkg_edit_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(cb_pkg_edit_entry,
                                       pattern=f'^{CB_PKG_EDIT_PRE}\\d+_(label|duration_days|price_pulses|price_rub)$')],
    states={
        ST_PKG_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_pkg_edit_value)],
    },
    fallbacks=[CommandHandler('cancel', fsm_cancel)],
    per_message=False,
    name='owner_titles_pkg_edit',
)

owner_titles_rename_price_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(cb_rename_price_entry, pattern=f'^{CB_RENAME_PRICE}$')],
    states={
        ST_RENAME_PRICE_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_rename_price)],
    },
    fallbacks=[CommandHandler('cancel', fsm_cancel)],
    per_message=False,
    name='owner_titles_rename_price',
)

owner_titles_ttl_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(cb_ttl_entry, pattern=f'^{CB_TTL}$')],
    states={
        ST_TTL_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_ttl)],
    },
    fallbacks=[CommandHandler('cancel', fsm_cancel)],
    per_message=False,
    name='owner_titles_ttl',
)

owner_titles_reject_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(cb_request_reject_entry,
                                       pattern=f'^{CB_REQ_REJECT_PRE}\\d+$')],
    states={
        STATE_AWAIT_REJECT_RSN: [
            CommandHandler('skip', fsm_reject_skip),
            MessageHandler(filters.TEXT & ~filters.COMMAND, fsm_reject_reason),
        ],
    },
    fallbacks=[CommandHandler('cancel', fsm_cancel)],
    per_message=False,
    name='owner_titles_reject',
)


def register_owner_titles(application) -> None:
    """Зарегистрировать панель Владельца + обработку заявок."""
    # Группа 1 — не конкурируем с catch-all (группа 0) в callback_router.py.
    application.add_handler(CallbackQueryHandler(cb_owner_menu,    pattern=f'^{CB_OWNER_MENU}$'), 1)
    application.add_handler(CallbackQueryHandler(cb_pkg_list,      pattern=f'^{CB_PKG_LIST}$'), 1)
    application.add_handler(CallbackQueryHandler(cb_pkg_card,      pattern=f'^{CB_PKG_CARD_PRE}\\d+$'), 1)
    application.add_handler(CallbackQueryHandler(cb_pkg_toggle,    pattern=f'^{CB_PKG_TOGGLE_PRE}\\d+$'), 1)
    application.add_handler(CallbackQueryHandler(cb_requests_list, pattern=f'^{CB_REQUESTS}$'), 1)
    application.add_handler(CallbackQueryHandler(cb_request_approve,
                                                 pattern=f'^{CB_REQ_APPROVE_PRE}\\d+$'), 1)

    # FSM-конверсейшны — тоже группа 1
    application.add_handler(owner_titles_pkg_add_conv, 1)
    application.add_handler(owner_titles_pkg_edit_conv, 1)
    application.add_handler(owner_titles_rename_price_conv, 1)
    application.add_handler(owner_titles_ttl_conv, 1)
    application.add_handler(owner_titles_reject_conv, 1)
