#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Пульт Владельца — инлайн-дашборд в ЛС.

Путь: handlers/owner_handlers.py

Разделы:
  👨‍💼 Персонал    — назначить / снять админа
  💰 Экономика   — эмиссия пульсов / глобальный вайп
  🛡 Модерация   — блэклист
  ⚙️ Система     — режим техобслуживания
  💾 Скачать БД  — бэкап (уже существует)
"""

import os
import time
import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ContextTypes
from utils.helpers import format_number

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  МИГРАЦИЯ: is_blacklisted
# ═══════════════════════════════════════════════════════════════

def ensure_owner_columns(db) -> None:
    """Добавляет колонку is_blacklisted в users если её нет."""
    try:
        db.cursor.execute("PRAGMA table_info(users)")
        cols = {row[1] for row in db.cursor.fetchall()}
        if 'is_blacklisted' not in cols:
            db.cursor.execute('ALTER TABLE users ADD COLUMN is_blacklisted INTEGER DEFAULT 0')
            db.conn.commit()
            logger.info("Migration: added is_blacklisted column to users")
    except Exception as e:
        logger.error(f"ensure_owner_columns error: {e}")


# ═══════════════════════════════════════════════════════════════
#  ХЕЛПЕРЫ
# ═══════════════════════════════════════════════════════════════

def _is_owner(db, user_id: int, admin_id: int) -> bool:
    if user_id == admin_id:
        return True
    user_data = db.get_user(user_id)
    return bool(user_data and user_data['is_owner'])


async def _edit_panel(context, chat_id: int, msg_id: int, text: str, markup) -> None:
    """Редактирует панельное сообщение (единое окно)."""
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=text, parse_mode='HTML', reply_markup=markup
        )
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f'_edit_panel error: {e}')


def _get_stats(db) -> dict:
    """Статистика для дашборда."""
    try:
        db.cursor.execute('SELECT COUNT(*) as cnt FROM users')
        total = db.cursor.fetchone()['cnt']

        db.cursor.execute('SELECT COUNT(*) as cnt FROM users WHERE is_admin = 1 OR is_owner = 1')
        admins = db.cursor.fetchone()['cnt']

        db.cursor.execute('SELECT COUNT(*) as cnt FROM users WHERE is_blacklisted = 1')
        blacklisted = db.cursor.fetchone()['cnt']
    except Exception:
        total, admins, blacklisted = 0, 0, 0

    maintenance = db.get_setting('maintenance_mode', '0') == '1'

    return {
        'total': total,
        'admins': admins,
        'blacklisted': blacklisted,
        'maintenance': maintenance,
    }


# ═══════════════════════════════════════════════════════════════
#  ГЛАВНЫЙ ДАШБОРД
# ═══════════════════════════════════════════════════════════════

async def show_owner_dashboard(query_or_update, context, db, admin_id: int) -> None:
    """
    Показывает главное меню «Пульт Владельца».
    Принимает как CallbackQuery, так и Update (для /owner_panel).
    """
    # Определяем, откуда пришёл вызов
    if hasattr(query_or_update, 'edit_message_text'):
        # CallbackQuery
        query = query_or_update
        user_id = query.from_user.id
        edit = True
    else:
        # Update (команда)
        query = None
        user_id = query_or_update.effective_user.id
        edit = False

    if not _is_owner(db, user_id, admin_id):
        if query:
            await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    ensure_owner_columns(db)
    stats = _get_stats(db)

    maint_icon = "🔴" if stats['maintenance'] else "🟢"
    maint_text = "ВКЛ" if stats['maintenance'] else "ВЫКЛ"

    text = (
        f"🎛 <b>ПУЛЬТ ВЛАДЕЛЬЦА</b>\n\n"
        f"👥 Людей в базе: <b>{stats['total']}</b>\n"
        f"👨‍💼 Админов: <b>{stats['admins']}</b>\n"
        f"🚫 В блэклисте: <b>{stats['blacklisted']}</b>\n"
        f"{maint_icon} Техобслуживание: <b>{maint_text}</b>"
    )

    keyboard = [
        [InlineKeyboardButton("👨‍💼 Персонал", callback_data="owner_staff")],
        [InlineKeyboardButton("💰 Экономика", callback_data="owner_economy")],
        [InlineKeyboardButton("🛡 Модерация", callback_data="owner_moderation")],
        [InlineKeyboardButton("⚡ Триггеры", callback_data="owner_triggers")],
        [InlineKeyboardButton("📢 Журнал событий", callback_data="owner_journal"),
         InlineKeyboardButton("📊 Не в чате", callback_data="owner_stats_not_in_chat")],
        [InlineKeyboardButton("📊 Опросы при выходе", callback_data="owner_survey_results")],
        [InlineKeyboardButton("⚙️ Система", callback_data="owner_system")],
        [InlineKeyboardButton("🆘 Восстановление веток", callback_data="owner_recovery_menu")],
        [InlineKeyboardButton("💾 Скачать БД", callback_data="owner_backup")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if edit and query:
        try:
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            if 'not modified' not in str(e).lower():
                logger.error(f"show_owner_dashboard error: {e}")
    else:
        msg_obj = query_or_update.effective_message or query_or_update.message
        sent = await msg_obj.reply_text(text, parse_mode='HTML', reply_markup=markup)
        context.user_data['owner_panel_msg_id'] = sent.message_id
        context.user_data['owner_panel_chat_id'] = sent.chat_id


# ═══════════════════════════════════════════════════════════════
#   ЭКОНОМИКА
# ═══════════════════════════════════════════════════════════════

async def show_economy_menu(query, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    bank = db.get_bank_balance()

    # Сумма балансов всех пользователей
    try:
        db.cursor.execute('SELECT COALESCE(SUM(balance), 0) AS total, COALESCE(SUM(frozen_balance), 0) AS frozen FROM users')
        row = db.cursor.fetchone()
        users_total = float(row['total']) if row else 0
        frozen_total = float(row['frozen']) if row else 0
    except Exception:
        users_total = 0
        frozen_total = 0

    # Общая масса = банк + на руках + заморожено
    total_supply = bank + users_total + frozen_total
    # Дефицит/профицит
    target = 10_000_000
    delta = total_supply - target
    if abs(delta) < 0.01:
        status_line = "✅ Контур замкнут"
    else:
        sign = "+" if delta > 0 else ""
        status_line = f"⚠️ Δ {sign}{format_number(delta)}"

    # Процент банка
    bank_pct = (bank / target * 100) if target > 0 else 0

    from utils.helpers import get_moscow_time
    now = get_moscow_time()
    time_str = now.strftime('%H:%M:%S')

    text = (
        f"💰 <b>ЭКОНОМИКА</b>\n"
        f"🕐 <i>{time_str} МСК</i>\n\n"
        f"🏦 Центробанк: <b>{format_number(bank)}</b> 💎 ({bank_pct:.1f}%)\n"
        f"👥 На руках: <b>{format_number(users_total)}</b> 💎\n"
        f"🧊 Заморожено: <b>{format_number(frozen_total)}</b> 💎\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 Всего: <b>{format_number(total_supply)}</b> / {format_number(target)} 💎\n"
        f"{status_line}"
    )
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="owner_economy")],
        [InlineKeyboardButton("💸 Выдать Пульсы", callback_data="owner_emit")],
        [InlineKeyboardButton("💀 Глобальный Вайп", callback_data="owner_wipe")],
        [InlineKeyboardButton("🔙 Назад", callback_data="panel_main")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def emit_start(query, context, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    context.user_data['owner_awaiting'] = 'emit'
    text = (
        "💸 <b>Выдать Пульсы</b>\n\n"
        "Отправьте в формате:\n"
        "<code>user_id сумма</code>\n\n"
        "Пример: <code>123456789 5000</code>"
    )
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_economy")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def wipe_confirm_step1(query, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    text = (
        "💀 <b>ГЛОБАЛЬНЫЙ ВАЙП БАЛАНСОВ</b>\n\n"
        "⚠️ Это обнулит <b>ВСЕ</b> балансы и замороженные средства "
        "у <b>ВСЕХ</b> пользователей!\n\n"
        "Вы уверены?"
    )
    keyboard = [
        [InlineKeyboardButton("⚠️ ДА, ОБНУЛИТЬ ВСЁ", callback_data="owner_wipe_confirm")],
        [InlineKeyboardButton("❌ Отмена", callback_data="owner_economy")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def wipe_execute(query, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    try:
        db.cursor.execute('UPDATE users SET balance = 0, frozen_balance = 0')
        db.cursor.execute("UPDATE settings SET value = '10000000' WHERE key = 'bank_balance'")
        db.conn.commit()

        affected = db.cursor.rowcount
        logger.warning(f"GLOBAL WIPE by {query.from_user.id}: {affected} users zeroed")

        text = (
            f"💀 <b>ВАЙП ВЫПОЛНЕН</b>\n\n"
            f"Обнулено пользователей: <b>{affected}</b>\n"
            f"Все балансы и замороженные средства = 0.\n"
            f"🏦 Банк восстановлен: 10 000 000 💎"
        )
    except Exception as e:
        logger.error(f"wipe_execute error: {e}")
        text = f"❌ Ошибка при вайпе: {e}"

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="owner_economy")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


# ═══════════════════════════════════════════════════════════════
#  ⚙️ СИСТЕМА
# ═══════════════════════════════════════════════════════════════

async def show_system_menu(query, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    maintenance = db.get_setting('maintenance_mode', '0') == '1'
    icon = "🔴 ВКЛ" if maintenance else "🟢 ВЫКЛ"
    btn_label = "🟢 Выключить техобслуживание" if maintenance else "🔴 Включить техобслуживание"

    text = (
        f"⚙️ <b>СИСТЕМА</b>\n\n"
        f"🔧 Режим техобслуживания: <b>{icon}</b>\n\n"
        f"<i>Когда включён — бот не обрабатывает\n"
        f"сообщения обычных пользователей.</i>"
    )

    keyboard = [
        [InlineKeyboardButton(btn_label, callback_data="owner_maintenance_toggle")],
        [InlineKeyboardButton("🔙 Назад", callback_data="panel_main")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def toggle_maintenance(query, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    current = db.get_setting('maintenance_mode', '0')
    new_val = '0' if current == '1' else '1'
    db.set_setting('maintenance_mode', new_val)

    status = "ВКЛЮЧЁН 🔴" if new_val == '1' else "ВЫКЛЮЧЕН 🟢"
    await query.answer(f"Техобслуживание {status}", show_alert=True)
    logger.info(f"Maintenance mode set to {new_val} by {query.from_user.id}")

    await show_system_menu(query, db, admin_id)


# ═══════════════════════════════════════════════════════════════
#  FSM: ОБРАБОТКА ТЕКСТОВОГО ВВОДА
# ═══════════════════════════════════════════════════════════════

MUTE_DURATIONS = {
    '5m':  (300,   '5 мин.'),
    '1h':  (3600,  '1 час'),
    '1d':  (86400, '1 день'),
}


# ── 👨‍💼 ПЕРСОНАЛ ──

async def show_staff_menu(query, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    db.cursor.execute(
        'SELECT user_id, username, first_name FROM users WHERE is_admin = 1 OR is_owner = 1'
    )
    admins = db.cursor.fetchall()

    lines = []
    for a in admins:
        name = a['username'] or a['first_name'] or f"ID:{a['user_id']}"
        role = "👑" if a['user_id'] == admin_id else "⭐"
        lines.append(f"  {role} @{name} (<code>{a['user_id']}</code>)")
    admin_block = "\n".join(lines) if lines else "  — пусто —"

    text = (
        f"👨‍💼 <b>ПЕРСОНАЛ</b>\n"
        f"{'━' * 24}\n\n"
        f"<b>Текущие админы:</b>\n"
        f"{admin_block}"
    )

    keyboard = [
        [InlineKeyboardButton("➕ Назначить админа", callback_data="owner_staff_add")],
        [InlineKeyboardButton("➖ Разжаловать", callback_data="owner_staff_remove")],
        [InlineKeyboardButton("🔙 Назад", callback_data="owner_dashboard")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def staff_add_start(query, context, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return
    context.user_data['owner_awaiting'] = 'staff_add'
    text = "➕ <b>Назначить админа</b>\n\nОтправьте <b>user_id</b> пользователя:"
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_staff")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def staff_remove_start(query, context, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return
    context.user_data['owner_awaiting'] = 'staff_remove'
    text = "➖ <b>Разжаловать админа</b>\n\nОтправьте <b>user_id</b> пользователя:"
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_staff")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


# ── 🛡 МОДЕРАЦИЯ (блэклист + мут по ID) ──

async def show_moderation_menu(query, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    ensure_owner_columns(db)

    db.cursor.execute('SELECT user_id, username, first_name FROM users WHERE is_blacklisted = 1')
    bl_users = db.cursor.fetchall()

    if bl_users:
        lines = [f"  🚫 @{u['username'] or u['first_name'] or u['user_id']} (<code>{u['user_id']}</code>)"
                 for u in bl_users]
        bl_block = "\n".join(lines)
    else:
        bl_block = "  — пусто —"

    text = (
        f"🛡 <b>МОДЕРАЦИЯ</b>\n{'━' * 24}\n\n"
        f"<b>Блэклист:</b>\n{bl_block}\n\n"
        f"<b>Быстрый мут (по ID):</b>\n"
        f"<i>Выберите время и введите user_id</i>"
    )

    keyboard = [
        [
            InlineKeyboardButton("🔇 5 мин", callback_data="owner_mute_5m"),
            InlineKeyboardButton("🔇 1 час", callback_data="owner_mute_1h"),
            InlineKeyboardButton("🔇 1 день", callback_data="owner_mute_1d"),
        ],
        [InlineKeyboardButton("🔊 Размутить (по ID)", callback_data="owner_unmute_start")],
        [InlineKeyboardButton("➕ Добавить в ЧС", callback_data="owner_bl_add")],
        [InlineKeyboardButton("➖ Убрать из ЧС", callback_data="owner_bl_remove")],
        [InlineKeyboardButton("🔙 Назад", callback_data="owner_dashboard")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def bl_add_start(query, context, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return
    context.user_data['owner_awaiting'] = 'bl_add'
    text = "➕ <b>Добавить в блэклист</b>\n\nОтправьте <b>user_id</b> пользователя:"
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_moderation")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def bl_remove_start(query, context, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return
    context.user_data['owner_awaiting'] = 'bl_remove'
    text = "➖ <b>Убрать из блэклиста</b>\n\nОтправьте <b>user_id</b> пользователя:"
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_moderation")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def mute_start(query, context, db, admin_id: int, duration_key: str) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return
    if duration_key not in MUTE_DURATIONS:
        await query.answer("❌ Неизвестная длительность.", show_alert=True)
        return
    _, human = MUTE_DURATIONS[duration_key]
    context.user_data['owner_awaiting'] = f'mute_{duration_key}'
    text = f"🔇 <b>Мут на {human}</b>\n\nОтправьте <b>user_id</b> пользователя:"
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_moderation")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def unmute_start(query, context, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return
    context.user_data['owner_awaiting'] = 'unmute'
    text = "🔊 <b>Снять мут</b>\n\nОтправьте <b>user_id</b> пользователя:"
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_moderation")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


# ═══════════════════════════════════════════════════════════════

async def handle_owner_text_input(
    update, context, db, admin_id: int, target_chat_id: int = None
) -> bool:
    """
    Обработчик текстового ввода для FSM пульта владельца.
    Все ответы редактируют одно панельное сообщение (режим 1 окна).
    Вызывается из message_handler → handle_private_message.
    Возвращает True если сообщение обработано, False если нет.
    """
    awaiting = context.user_data.get('owner_awaiting')
    if not awaiting:
        return False

    message = update.effective_message
    user = update.effective_user

    if not _is_owner(db, user.id, admin_id):
        context.user_data.pop('owner_awaiting', None)
        return False

    text = message.text.strip() if message.text else ''

    # Хелпер: удаляем входящее сообщение и редактируем панель
    panel_msg_id = context.user_data.get('owner_panel_msg_id')
    panel_chat_id = context.user_data.get('owner_panel_chat_id')

    async def reply(resp_text: str, markup=None) -> None:
        try:
            await message.delete()
        except Exception:
            pass
        if panel_msg_id and panel_chat_id:
            await _edit_panel(context, panel_chat_id, panel_msg_id, resp_text, markup)
        else:
            await message.reply_text(resp_text, parse_mode='HTML', reply_markup=markup)

    # ── Назначить админа ──
    if awaiting == 'staff_add':
        context.user_data.pop('owner_awaiting', None)
        try:
            target_id = int(text)
        except (ValueError, TypeError):
            await reply("❌ Введите числовой user_id.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Повторить", callback_data="owner_staff_add")]]))
            return True
        target = db.get_user(target_id)
        if not target:
            await reply(f"❌ Пользователь <code>{target_id}</code> не найден.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_staff")]]))
            return True
        if target['is_admin'] or target['is_owner']:
            await reply("ℹ️ Уже является админом.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_staff")]]))
            return True
        db.cursor.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (target_id,))
        db.conn.commit()
        name = target['username'] or target['first_name'] or target_id
        await reply(
            f"✅ @{name} (<code>{target_id}</code>) назначен админом.",
            InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💼 К персоналу", callback_data="owner_staff")]]))
        logger.info(f"STAFF ADD: {target_id} by {user.id}")
        return True

    # ── Разжаловать ──
    if awaiting == 'staff_remove':
        context.user_data.pop('owner_awaiting', None)
        try:
            target_id = int(text)
        except (ValueError, TypeError):
            await reply("❌ Введите числовой user_id.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Повторить", callback_data="owner_staff_remove")]]))
            return True
        if target_id == admin_id:
            await reply("⛔ Нельзя разжаловать владельца.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_staff")]]))
            return True
        target = db.get_user(target_id)
        if not target:
            await reply(f"❌ Пользователь <code>{target_id}</code> не найден.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_staff")]]))
            return True
        if not target['is_admin']:
            await reply("ℹ️ Не является админом.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_staff")]]))
            return True
        db.cursor.execute('UPDATE users SET is_admin = 0 WHERE user_id = ?', (target_id,))
        db.conn.commit()
        name = target['username'] or target['first_name'] or target_id
        await reply(
            f"✅ @{name} (<code>{target_id}</code>) разжалован.",
            InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💼 К персоналу", callback_data="owner_staff")]]))
        logger.info(f"STAFF REMOVE: {target_id} by {user.id}")
        return True

    # ── Эмиссия пульсов ──
    if awaiting == 'emit':
        context.user_data.pop('owner_awaiting', None)
        parts = text.split()
        if len(parts) != 2:
            await reply("❌ Формат: <code>user_id сумма</code>",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Повторить", callback_data="owner_emit")]]))
            return True
        try:
            target_id = int(parts[0])
            amount = round(float(parts[1].replace(',', '.')), 2)
        except (ValueError, TypeError):
            await reply("❌ Некорректные данные. Нужно: <code>user_id сумма</code>",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Повторить", callback_data="owner_emit")]]))
            return True
        if amount <= 0:
            await reply("❌ Сумма должна быть > 0.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Повторить", callback_data="owner_emit")]]))
            return True
        target = db.get_user(target_id)
        if not target:
            await reply(f"❌ Пользователь <code>{target_id}</code> не найден.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_economy")]]))
            return True
        bank_balance = db.get_bank_balance()
        if bank_balance < amount:
            await reply(
                f"❌ Недостаточно средств в Банке!\n"
                f"🏦 В банке: {format_number(bank_balance)} 💎\n"
                f"💸 Нужно: {format_number(amount)} 💎",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_economy")]]))
            return True
        db.update_bank_balance(amount, 'subtract')
        db.update_user_balance(target_id, amount, operation='add')
        db.add_transaction(None, target_id, amount, 'admin_give', 'Эмиссия от владельца')
        name = target['username'] or target['first_name'] or target_id
        new_balance = float(target['balance']) + amount
        new_bank = db.get_bank_balance()
        await reply(
            f"✅ <b>Эмиссия выполнена</b>\n\n"
            f"👤 @{name} (<code>{target_id}</code>)\n"
            f"💎 +{format_number(amount)} Пульсов\n"
            f"💰 Новый баланс: ~{format_number(new_balance)} 💎\n"
            f"🏦 Банк: {format_number(new_bank)} 💎",
            InlineKeyboardMarkup([[InlineKeyboardButton("💰 К экономике", callback_data="owner_economy")]]))
        logger.info(f"EMIT: {amount} to {target_id} by {user.id}")
        return True

    # ── Добавить в блэклист ──
    if awaiting == 'bl_add':
        context.user_data.pop('owner_awaiting', None)
        try:
            target_id = int(text)
        except (ValueError, TypeError):
            await reply("❌ Введите числовой user_id.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Повторить", callback_data="owner_bl_add")]]))
            return True
        if target_id == admin_id:
            await reply("⛔ Нельзя добавить владельца в блэклист.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
            return True
        ensure_owner_columns(db)
        target = db.get_user(target_id)
        if not target:
            await reply(f"❌ Пользователь <code>{target_id}</code> не найден.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
            return True
        db.cursor.execute('UPDATE users SET is_blacklisted = 1 WHERE user_id = ?', (target_id,))
        db.conn.commit()
        name = target['username'] or target['first_name'] or target_id
        await reply(
            f"🚫 @{name} (<code>{target_id}</code>) добавлен в блэклист.",
            InlineKeyboardMarkup([[InlineKeyboardButton("🛡 К модерации", callback_data="owner_moderation")]]))
        logger.info(f"BLACKLIST ADD: {target_id} by {user.id}")
        try:
            from handlers.journal_handlers import log_blacklist
            await log_blacklist(context.bot, db, target_id, user.id, True)
        except Exception:
            pass
        return True

    # ── Убрать из блэклиста ──
    if awaiting == 'bl_remove':
        context.user_data.pop('owner_awaiting', None)
        try:
            target_id = int(text)
        except (ValueError, TypeError):
            await reply("❌ Введите числовой user_id.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Повторить", callback_data="owner_bl_remove")]]))
            return True
        ensure_owner_columns(db)
        target = db.get_user(target_id)
        if not target:
            await reply(f"❌ Пользователь <code>{target_id}</code> не найден.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
            return True
        db.cursor.execute('UPDATE users SET is_blacklisted = 0 WHERE user_id = ?', (target_id,))
        db.conn.commit()
        name = target['username'] or target['first_name'] or target_id
        await reply(
            f"✅ @{name} (<code>{target_id}</code>) убран из блэклиста.",
            InlineKeyboardMarkup([[InlineKeyboardButton("🛡 К модерации", callback_data="owner_moderation")]]))
        logger.info(f"BLACKLIST REMOVE: {target_id} by {user.id}")
        try:
            from handlers.journal_handlers import log_blacklist
            await log_blacklist(context.bot, db, target_id, user.id, False)
        except Exception:
            pass
        return True

    # ── Мут по ID из ЛС ──
    if awaiting.startswith('mute_'):
        context.user_data.pop('owner_awaiting', None)
        duration_key = awaiting.replace('mute_', '')
        if duration_key not in MUTE_DURATIONS:
            await reply("❌ Неизвестная длительность.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
            return True
        try:
            target_id = int(text)
        except (ValueError, TypeError):
            await reply("❌ Введите числовой user_id.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
            return True
        seconds, human = MUTE_DURATIONS[duration_key]
        until_ts = int(time.time()) + seconds
        if not target_chat_id:
            await reply("❌ Не удалось определить чат.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
            return True
        try:
            await context.bot.restrict_chat_member(
                chat_id=target_chat_id, user_id=target_id,
                permissions=ChatPermissions(
                    can_send_messages=False, can_send_audios=False, can_send_documents=False,
                    can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
                    can_send_voice_notes=False, can_send_polls=False,
                    can_send_other_messages=False, can_add_web_page_previews=False,
                ),
                until_date=until_ts,
            )
            target = db.get_user(target_id)
            name = (target['username'] or target['first_name'] or target_id) if target else target_id
            await reply(
                f"🔇 <code>{name}</code> замучен на <b>{human}</b>",
                InlineKeyboardMarkup([[InlineKeyboardButton("🛡 К модерации", callback_data="owner_moderation")]]))
            logger.info(f"OWNER MUTE: {target_id} for {human} ({seconds}s) by {user.id}")
        except Exception as e:
            logger.error(f"Owner mute error: {e}")
            await reply(f"❌ Не удалось замутить: {e}",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
        return True

    # ── Размут по ID из ЛС ──
    if awaiting == 'unmute':
        context.user_data.pop('owner_awaiting', None)
        try:
            target_id = int(text)
        except (ValueError, TypeError):
            await reply("❌ Введите числовой user_id.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
            return True
        if not target_chat_id:
            await reply("❌ Не удалось определить чат.",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
            return True
        try:
            await context.bot.restrict_chat_member(
                chat_id=target_chat_id, user_id=target_id,
                permissions=ChatPermissions(
                    can_send_messages=True, can_send_audios=True, can_send_documents=True,
                    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                    can_send_voice_notes=True, can_send_polls=True,
                    can_send_other_messages=True, can_add_web_page_previews=True,
                ),
            )
            target = db.get_user(target_id)
            name = (target['username'] or target['first_name'] or target_id) if target else target_id
            await reply(
                f"🔊 <code>{name}</code> размучен",
                InlineKeyboardMarkup([[InlineKeyboardButton("🛡 К модерации", callback_data="owner_moderation")]]))
            logger.info(f"OWNER UNMUTE: {target_id} by {user.id}")
        except Exception as e:
            logger.error(f"Owner unmute error: {e}")
            await reply(f"❌ Не удалось размутить: {e}",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
        return True

    # Неизвестный awaiting — сбрасываем
    context.user_data.pop('owner_awaiting', None)
    return False


# ═══════════════════════════════════════════════════════════════
#  💾 БЭКАП (существующий функционал)
# ═══════════════════════════════════════════════════════════════

async def show_statistics_not_in_chat(query, admin_id: int) -> None:
    """Статистика 4.5 — пользователи Не в чате (БЗА / НПС)."""
    if query.from_user.id != admin_id:
        await query.answer("⛔", show_alert=True)
        return

    import sqlite3

    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'registration_system', 'pulse_bot.db'
    )

    bza_lines = []
    nps_lines = []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            "SELECT tg_id, first_name, last_name, username FROM users "
            "WHERE questionnaire_state IS NOT NULL"
        )
        for row in cur.fetchall():
            fn = (row['first_name'] or '').strip()
            ln = (row['last_name'] or '').strip()
            name = f"{fn} {ln}".strip() or row['username'] or f"ID:{row['tg_id']}"
            bza_lines.append(f"{name}, #user{row['tg_id']}, БЗА")

        cur.execute(
            "SELECT tg_id, first_name, last_name, username FROM users "
            "WHERE invite_link IS NOT NULL AND status = 'not_in_chat'"
        )
        for row in cur.fetchall():
            fn = (row['first_name'] or '').strip()
            ln = (row['last_name'] or '').strip()
            name = f"{fn} {ln}".strip() or row['username'] or f"ID:{row['tg_id']}"
            nps_lines.append(f"{name}, #user{row['tg_id']}, НПС")

        conn.close()
    except Exception as e:
        logger.error(f"show_statistics_not_in_chat DB error: {e}")
        await query.edit_message_text(
            f"❌ Ошибка чтения базы регистрации:\n<code>{e}</code>\n\n"
            f"Путь: <code>{db_path}</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="panel_main")]
            ])
        )
        return

    all_lines = bza_lines + nps_lines
    body = "\n".join(all_lines) if all_lines else "<i>Нет пользователей вне чата</i>"

    text = (
        f"📊 <b>НЕ В ЧАТЕ</b>\n"
        f"{'━' * 24}\n\n"
        f"🔴 БЗА (бросил анкету): <b>{len(bza_lines)}</b>\n"
        f"🟡 НПС (не перешёл по ссылке): <b>{len(nps_lines)}</b>\n\n"
        f"{body}"
    )

    if len(text) > 4000:
        text = text[:3980] + "\n\n<i>...список обрезан</i>"

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="panel_main")]]
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"show_statistics_not_in_chat error: {e}")


async def send_database_backup(query, user, db, admin_id: int, context) -> None:
    """Отправляет файл базы данных владельцу."""
    if user.id != admin_id:
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    db_path = db.db_path
    if not os.path.exists(db_path):
        await query.answer("❌ Файл БД не найден.", show_alert=True)
        return

    try:
        await query.answer("📦 Отправляю бэкап...")
        with open(db_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=user.id,
                document=f,
                filename=f"backup_{os.path.basename(db_path)}",
                caption="💾 Бэкап базы данных",
            )
    except Exception as e:
        logger.error(f"Backup error: {e}")
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
#  🆘 ВОССТАНОВЛЕНИЕ ВЕТОК
# ═══════════════════════════════════════════════════════════════

# Константы форума
_RECOVERY_CHAT_ID = -1003153855971
_BBS_THREAD_ID = 8
_NEWS_THREAD_ID = 26


async def show_recovery_menu(query, db, admin_id: int) -> None:
    """Главное меню восстановления веток."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    text = (
        "🆘 <b>ВОССТАНОВЛЕНИЕ ВЕТОК</b>\n\n"
        "Выберите ветку для восстановления из базы данных:"
    )
    keyboard = [
        [InlineKeyboardButton("♻️ Восстановить BBS", callback_data="owner_restore_bbs")],
        [InlineKeyboardButton("📰 Восстановить НьюзON", callback_data="owner_restore_news")],
        [InlineKeyboardButton("🔙 Назад", callback_data="panel_main")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def restore_bbs_confirm(query, db, admin_id: int) -> None:
    """Запрос подтверждения восстановления BBS."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    try:
        db.cursor.execute(
            "SELECT COUNT(*) as cnt FROM bbs_profiles WHERE published_at IS NOT NULL"
        )
        row = db.cursor.fetchone()
        count = row['cnt'] if row else 0
    except Exception:
        count = "?"

    text = (
        f"♻️ <b>Восстановление BBS</b>\n\n"
        f"Будет перепубликовано анкет: <b>{count}</b>\n"
        f"Ветка: <b>thread_id {_BBS_THREAD_ID}</b>\n\n"
        f"⚠️ Старые message_ids будут перезаписаны в БД.\n"
        f"Продолжить?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Да, восстановить", callback_data="owner_restore_bbs_confirm")],
        [InlineKeyboardButton("❌ Отмена", callback_data="owner_recovery_menu")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def restore_bbs_execute(query, context, db, admin_id: int) -> None:
    """Выполняет восстановление всех анкет BBS."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    from handlers.BBS.publishing_bbs import republish_profile

    await query.edit_message_text("⏳ Начинаю восстановление анкет...", parse_mode='HTML')

    try:
        db.cursor.execute(
            "SELECT user_id FROM bbs_profiles WHERE published_at IS NOT NULL"
        )
        rows = db.cursor.fetchall()
    except Exception as e:
        logger.error(f"restore_bbs_execute DB error: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="owner_recovery_menu")]]
        await query.edit_message_text(
            f"❌ Ошибка при чтении БД: {e}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    success, errors = 0, 0
    for row in rows:
        try:
            await republish_profile(
                context.bot, db, row['user_id'],
                _RECOVERY_CHAT_ID, _BBS_THREAD_ID,
            )
            success += 1
        except Exception as e:
            logger.error(f"restore_bbs: failed user_id={row['user_id']}: {e}")
            errors += 1
        await asyncio.sleep(2)

    keyboard = [[InlineKeyboardButton("🔙 В меню восстановления", callback_data="owner_recovery_menu")]]
    await query.edit_message_text(
        f"✅ <b>Восстановление BBS завершено!</b>\n\n"
        f"Успешно: <b>{success}</b>\n"
        f"Ошибок: <b>{errors}</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def restore_news_confirm(query, db, admin_id: int) -> None:
    """Запрос подтверждения восстановления НьюзON."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    try:
        db.cursor.execute(
            "SELECT COUNT(*) as cnt FROM scheduled_posts WHERE status = 'published'"
        )
        row = db.cursor.fetchone()
        count = row['cnt'] if row else 0
    except Exception:
        count = "?"

    text = (
        f"📰 <b>Восстановление НьюзON</b>\n\n"
        f"Будет перепубликовано постов: <b>{count}</b>\n"
        f"Ветка: <b>thread_id {_NEWS_THREAD_ID}</b>\n\n"
        f"⚠️ Посты публикуются в хронологическом порядке.\n"
        f"Продолжить?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Да, восстановить", callback_data="owner_restore_news_confirm")],
        [InlineKeyboardButton("❌ Отмена", callback_data="owner_recovery_menu")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def restore_news_execute(query, context, db, admin_id: int) -> None:
    """Выполняет восстановление всех постов НьюзON."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    from handlers.messages.admin_logic import publish_press_release_to_target

    await query.edit_message_text("⏳ Начинаю восстановление новостей...", parse_mode='HTML')

    try:
        db.cursor.execute(
            "SELECT text, photo_file_id FROM scheduled_posts "
            "WHERE status = 'published' ORDER BY publish_at ASC"
        )
        rows = db.cursor.fetchall()
    except Exception as e:
        logger.error(f"restore_news_execute DB error: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="owner_recovery_menu")]]
        await query.edit_message_text(
            f"❌ Ошибка при чтении БД: {e}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    success, errors = 0, 0
    for row in rows:
        try:
            result = await publish_press_release_to_target(
                context.bot,
                row['text'],
                row['photo_file_id'],
                _RECOVERY_CHAT_ID,
                _NEWS_THREAD_ID,
            )
            if result:
                success += 1
            else:
                errors += 1
        except Exception as e:
            logger.error(f"restore_news: failed post: {e}")
            errors += 1
        await asyncio.sleep(2)

    keyboard = [[InlineKeyboardButton("🔙 В меню восстановления", callback_data="owner_recovery_menu")]]
    await query.edit_message_text(
        f"✅ <b>Восстановление НьюзON завершено!</b>\n\n"
        f"Успешно: <b>{success}</b>\n"
        f"Ошибок: <b>{errors}</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
