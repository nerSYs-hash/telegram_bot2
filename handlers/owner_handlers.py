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
import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ContextTypes
from config import DEVELOPER_ID
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
    if DEVELOPER_ID and user_id == DEVELOPER_ID:
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
        [InlineKeyboardButton("🛍 Настройка Титулов", callback_data="owner_titles_menu")],
        [InlineKeyboardButton("🛡 Модерация", callback_data="owner_moderation")],
        [InlineKeyboardButton("💘 Рулетка пар (Шиппер)", callback_data="owner_shipper_menu")],
        [InlineKeyboardButton("⚡ Триггеры", callback_data="owner_triggers")],
        [InlineKeyboardButton("📢 Журнал событий", callback_data="owner_journal"),
         InlineKeyboardButton("📊 Не в чате", callback_data="owner_stats_not_in_chat")],
        [InlineKeyboardButton("📊 Опросы при выходе", callback_data="owner_survey_results")],
        [InlineKeyboardButton("🆘 Восстановление", callback_data="owner_recovery")],
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

    # Общая масса = банк + на руках
    total_supply = bank + users_total
    bank_pct = (bank / total_supply * 100) if total_supply > 0 else 0

    from utils.helpers import get_moscow_time
    now = get_moscow_time()
    time_str = now.strftime('%H:%M:%S')

    text = (
        f"💰 <b>ЭКОНОМИКА</b>\n"
        f"🕐 <i>{time_str} МСК</i>\n\n"
        f"🏦 Центробанк: <b>{format_number(bank)}</b> 💎 ({bank_pct:.1f}%)"
        f"{f' (вкл. 🧊 {format_number(frozen_total)})' if frozen_total > 0 else ''}\n"
        f"👥 На руках: <b>{format_number(users_total)}</b> 💎\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 В обороте: <b>{format_number(total_supply)}</b> 💎"
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
        affected = db.cursor.rowcount
        db.cursor.execute("UPDATE settings SET value = '10000000' WHERE key = 'bank_balance'")
        db.conn.commit()
        logger.warning(f"GLOBAL WIPE by {query.from_user.id}: {affected} users zeroed")

        # Журнал
        try:
            from handlers.journal_handlers import log_admin_action
            bot = query._bot if hasattr(query, '_bot') else None
            if bot:
                await log_admin_action(
                    bot, db, query.from_user.id,
                    f"💀 Глобальный вайп балансов: обнулено {affected} пользователей"
                )
        except Exception as e:
            logger.error(f"Journal log_admin_action (wipe) error: {e}")

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
        [InlineKeyboardButton("🔧 Управление функциями", callback_data="manage_features")],
        [InlineKeyboardButton("📝 Плейсхолдеры", callback_data="ph_menu")],
        [InlineKeyboardButton("💾 Скачать БД", callback_data="owner_backup")],
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
        'SELECT user_id, username, first_name, is_admin, is_owner FROM users WHERE is_admin = 1 OR is_owner = 1'
    )
    admins = db.cursor.fetchall()

    lines = []
    for a in admins:
        name = a['username'] or a['first_name'] or f"ID:{a['user_id']}"
        if a['user_id'] == admin_id:
            role = "👑 Владелец"
        elif a['is_owner']:
            role = "🥈 Зам"
        else:
            role = "⭐ Админ"
        lines.append(f"  {role} — @{name} (<code>{a['user_id']}</code>)")
    admin_block = "\n".join(lines) if lines else "  — пусто —"

    text = (
        f"👨‍💼 <b>ПЕРСОНАЛ</b>\n"
        f"{'━' * 24}\n\n"
        f"<b>Текущий состав:</b>\n"
        f"{admin_block}"
    )

    # Только главный владелец может назначать/снимать замов
    is_main = query.from_user.id == admin_id
    keyboard = [
        [InlineKeyboardButton("➕ Назначить админа", callback_data="owner_staff_add")],
        [InlineKeyboardButton("➖ Разжаловать", callback_data="owner_staff_remove")],
    ]
    if is_main:
        keyboard.append(
            [InlineKeyboardButton("👑 Назначить зама", callback_data="owner_staff_add_deputy"),
             InlineKeyboardButton("👑 Снять зама", callback_data="owner_staff_remove_deputy")]
        )
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="owner_dashboard")])
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

    if awaiting.startswith('shipper_'):
        try:
            from handlers.shipper_handlers import handle_shipper_text_input
            handled_shipper = await handle_shipper_text_input(
                update, context, db, admin_id, target_chat_id
            )
            if handled_shipper:
                return True
        except Exception as e:
            logger.error(f"shipper FSM delegate error: {e}")

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

        # Журнал
        try:
            from handlers.journal_handlers import log_admin_action
            await log_admin_action(
                context.bot, db, user.id,
                f"💸 Эмиссия: {format_number(amount)} 💎 → @{name} (<code>{target_id}</code>)"
            )
        except Exception as e:
            logger.error(f"Journal log_admin_action (emit) error: {e}")

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
        # Кикаем из чата (бан без возможности вернуться самостоятельно)
        if target_chat_id:
            try:
                await context.bot.ban_chat_member(chat_id=target_chat_id, user_id=target_id)
            except Exception as e:
                logger.error(f"BLACKLIST kick error: {e}")
        name = target['username'] or target['first_name'] or target_id
        await reply(
            f"🚫 @{name} (<code>{target_id}</code>) добавлен в блэклист и исключён из чата.",
            InlineKeyboardMarkup([[InlineKeyboardButton("🛡 К модерации", callback_data="owner_moderation")]]))
        logger.info(f"BLACKLIST ADD: {target_id} by {user.id}")
        try:
            from handlers.journal_handlers import log_blacklist
            await log_blacklist(context.bot, db, target_id, user.id, True, admin_user=user)
        except Exception as e:
            logger.error(f"Journal log_blacklist error: {e}")
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
        # Разбаниваем в Telegram чтобы мог вернуться
        if target_chat_id:
            try:
                await context.bot.unban_chat_member(chat_id=target_chat_id, user_id=target_id, only_if_banned=True)
            except Exception as e:
                logger.error(f"BLACKLIST unban error: {e}")
        name = target['username'] or target['first_name'] or target_id
        await reply(
            f"✅ @{name} (<code>{target_id}</code>) убран из блэклиста и разбанен.",
            InlineKeyboardMarkup([[InlineKeyboardButton("🛡 К модерации", callback_data="owner_moderation")]]))
        logger.info(f"BLACKLIST REMOVE: {target_id} by {user.id}")
        try:
            from handlers.journal_handlers import log_blacklist
            await log_blacklist(context.bot, db, target_id, user.id, False, admin_user=user)
        except Exception as e:
            logger.error(f"Journal log_blacklist error: {e}")
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


            # Журнал
            try:
                from handlers.journal_handlers import log_mute
                try:
                    real_chat = await context.bot.get_chat(target_chat_id)
                except Exception:
                    real_chat = None
                try:
                    target_tg = (await context.bot.get_chat_member(target_chat_id, target_id)).user
                except Exception:
                    target_tg = None
                await log_mute(
                    context.bot, db, target_id, user.id,
                    duration_human=human,
                    chat=real_chat,
                    admin_user=user,
                    target_user=target_tg,
                )
            except Exception as je:
                logger.error(f"Journal log_mute error: {je}")


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

            # Журнал
            try:
                from handlers.journal_handlers import log_unmute
                try:
                    real_chat = await context.bot.get_chat(target_chat_id)
                except Exception:
                    real_chat = None
                try:
                    target_tg = (await context.bot.get_chat_member(target_chat_id, target_id)).user
                except Exception:
                    target_tg = None
                await log_unmute(
                    context.bot, db, target_id, user.id,
                    chat=real_chat,
                    admin_user=user,
                    target_user=target_tg,
                )
            except Exception as je:
                logger.error(f"Journal log_unmute error: {je}")

        except Exception as e:
            logger.error(f"Owner unmute error: {e}")
            await reply(f"❌ Не удалось размутить: {e}",
                        InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_moderation")]]))
        return True

    # ── Компенсация BBS: ввод суммы ──
    if awaiting == 'compensate_bbs_amount':
        context.user_data.pop('owner_awaiting', None)
        try:
            amount = round(float(text.replace(',', '.')), 2)
        except (ValueError, TypeError):
            await message.reply_text("❌ Введите число. Пример: <code>500</code>", parse_mode='HTML')
            context.user_data['owner_awaiting'] = 'compensate_bbs_amount'
            return True

        if amount <= 0:
            await message.reply_text("❌ Сумма должна быть больше 0.")
            context.user_data['owner_awaiting'] = 'compensate_bbs_amount'
            return True

        affected = context.user_data.get('compensate_affected', [])
        total_cost = amount * len(affected)
        bank = db.get_bank_balance()

        if bank < total_cost:
            await message.reply_text(
                f"❌ <b>Недостаточно средств в Банке!</b>\n\n"
                f"🏦 В банке: {format_number(bank)} 💎\n"
                f"💸 Нужно: {format_number(total_cost)} 💎\n\n"
                f"Введите сумму поменьше или нажмите Отмена.",
                parse_mode='HTML',
            )
            context.user_data['owner_awaiting'] = 'compensate_bbs_amount'
            return True

        context.user_data['compensate_amount'] = amount

        await message.reply_text(
            f"⚖️ <b>СМЕТА КОМПЕНСАЦИИ</b>\n\n"
            f"👥 Пострадавших: <b>{len(affected)}</b>\n"
            f"💎 Выплата каждому: <b>{format_number(amount)} 💎</b>\n"
            f"🏦 Итого из Банка: <b>{format_number(total_cost)} 💎</b>\n\n"
            f"Запустить рассылку извинений?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Подтвердить рассылку", callback_data="confirm_compensate_bbs")],
                [InlineKeyboardButton("❌ Отмена", callback_data="owner_recovery_menu")],
            ]),
        )
        return True
    # ── VIP BBS: изменить цену ──
    if awaiting and awaiting.startswith('vip_price_edit_'):
        try:
            from handlers.bbs_vip_owner import handle_vip_price_input
            await handle_vip_price_input(message, context, db)
        except Exception as e:
            logger.error(f"vip_price_edit FSM error: {e}")
            context.user_data.pop('owner_awaiting', None)
            context.user_data.pop('vip_price_edit', None)
        return True

    # ── VIP BBS: создание скидки (тема) ──
    if awaiting == 'vip_disc_theme':
        try:
            from handlers.bbs_vip_owner import handle_disc_theme_input
            await handle_disc_theme_input(message, context, db)
        except Exception as e:
            logger.error(f"vip_disc_theme FSM error: {e}")
            context.user_data.pop('owner_awaiting', None)
        return True

    # ── VIP BBS: создание скидки (описание) ──
    if awaiting == 'vip_disc_desc':
        try:
            from handlers.bbs_vip_owner import handle_disc_desc_input
            await handle_disc_desc_input(message, context, db)
        except Exception as e:
            logger.error(f"vip_disc_desc FSM error: {e}")
            context.user_data.pop('owner_awaiting', None)
        return True

    # ── VIP BBS: создание скидки (процент) ──
    if awaiting == 'vip_disc_percent':
        try:
            from handlers.bbs_vip_owner import handle_disc_percent_input
            await handle_disc_percent_input(message, context, db)
        except Exception as e:
            logger.error(f"vip_disc_percent FSM error: {e}")
            context.user_data.pop('owner_awaiting', None)
        return True

    if awaiting and (awaiting.startswith('journal_connect_') or awaiting.startswith('journal_thread_')):
        return False

    # Неизвестный awaiting — сбрасываем
    context.user_data.pop('owner_awaiting', None)
    return False


# ═══════════════════════════════════════════════════════════════
#  💾 БЭКАП (существующий функционал)
# ═══════════════════════════════════════════════════════════════

async def show_statistics_not_in_chat(query, admin_id: int) -> None:
    """Статистика 4.5 — пользователи Не в чате (БЗА / НПС). Доступ: владелец и замы."""
    import html as _html

    # Сразу отвечаем на callback, чтобы у юзера не крутился loader
    try:
        await query.answer()
    except Exception:
        pass

    # Доступ: владелец ИЛИ зам владельца
    from handlers.admin_moderation import _is_owner_or_deputy
    if not await _is_owner_or_deputy(query.from_user.id):
        try:
            await query.answer("⛔ Нет доступа.", show_alert=True)
        except Exception:
            pass
        return

    import sqlite3

    # PTB-БД — источник правды (aiogram-БД больше не используется)
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'pulse_bot.db'
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
            # HTML-escape — иначе спецсимволы в имени ломают parse_mode='HTML'
            bza_lines.append(f"{_html.escape(name)}, #user{row['tg_id']}, БЗА")

        cur.execute(
            "SELECT tg_id, first_name, last_name, username FROM users "
            "WHERE invite_link IS NOT NULL AND status = 'not_in_chat'"
        )
        for row in cur.fetchall():
            fn = (row['first_name'] or '').strip()
            ln = (row['last_name'] or '').strip()
            name = f"{fn} {ln}".strip() or row['username'] or f"ID:{row['tg_id']}"
            nps_lines.append(f"{_html.escape(name)}, #user{row['tg_id']}, НПС")

        conn.close()
    except Exception as e:
        logger.error(f"show_statistics_not_in_chat DB error: {e}")
        try:
            await query.edit_message_text(
                f"❌ Ошибка чтения базы:\n<code>{_html.escape(str(e))}</code>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="panel_main")]
                ])
            )
        except Exception:
            await query.answer(f"❌ Ошибка БД: {e}"[:200], show_alert=True)
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
        if 'not modified' in str(e).lower():
            return
        logger.error(f"show_statistics_not_in_chat edit error: {e}")
        # Fallback: отправляем новое сообщение если edit не удался
        try:
            await query.message.reply_text(
                text, parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e2:
            logger.error(f"show_statistics_not_in_chat reply fallback failed: {e2}")
            await query.answer(f"❌ Ошибка отображения: {e}"[:200], show_alert=True)


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
    """Меню восстановления веток."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return
    try:
        db.cursor.execute(
            "SELECT COUNT(*) FROM bbs_other_posts "
            "WHERE deleted_by IS NULL OR deleted_by != ?",
            ('user',)
        )
        other_count = db.cursor.fetchone()[0]
    except Exception:
        other_count = 0
    text = (
        "🆘 <b>ВОССТАНОВЛЕНИЕ ВЕТОК</b>\n\n"
        "Выберите ветку для восстановления из базы данных:"
    )
    keyboard = [
        [InlineKeyboardButton("♻️ Восстановить BBS", callback_data="owner_restore_bbs")],
        [InlineKeyboardButton("⏮️ Восстановить последнюю анкету", callback_data="owner_restore_last_bbs")],
        [InlineKeyboardButton("📰 Восстановить НьюзON", callback_data="owner_restore_news")],
        [InlineKeyboardButton("🎁 Компенсация BBS", callback_data="owner_compensate_bbs")],
        [InlineKeyboardButton(f"📦 Восстановить «Другое» ({other_count} шт.)", callback_data="owner_recovery_other_confirm")],
        [InlineKeyboardButton("🔙 Назад", callback_data="panel_main")],
    ]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


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
        # Восстанавливаем только анкеты которые:
        # 1. Были опубликованы (published_at IS NOT NULL)
        # 2. Реально удалены (deleted_at IS NOT NULL) — не активные
        # 3. Удалены НЕ самим пользователем (deleted_by != 'user')
        # 4. Пользователь сейчас в чате (is_left = 0 в основной БД)
        db.cursor.execute('''
            SELECT bp.user_id
            FROM bbs_profiles bp
            JOIN users u ON u.user_id = bp.user_id
            WHERE bp.published_at IS NOT NULL
              AND bp.deleted_at IS NOT NULL
              AND (bp.deleted_by IS NULL OR bp.deleted_by NOT IN ('user'))
              AND (u.is_left = 0 OR u.is_left IS NULL)
        ''')
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


async def restore_last_bbs_execute(query, context, db, admin_id: int) -> None:
    """Восстанавливает только ПОСЛЕДНЮЮ удаленную анкету BBS."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    from handlers.BBS.publishing_bbs import republish_profile

    await query.edit_message_text("⏳ Восстанавливаю последнюю анкету...", parse_mode='HTML')

    try:
        # Получаем только ПОСЛЕДНЮЮ удаленную анкету
        db.cursor.execute('''
            SELECT bp.user_id
            FROM bbs_profiles bp
            JOIN users u ON u.user_id = bp.user_id
            WHERE bp.published_at IS NOT NULL
              AND bp.deleted_at IS NOT NULL
              AND (bp.deleted_by IS NULL OR bp.deleted_by NOT IN ('user'))
              AND (u.is_left = 0 OR u.is_left IS NULL)
            ORDER BY bp.deleted_at DESC
            LIMIT 1
        ''')
        row = db.cursor.fetchone()
    except Exception as e:
        logger.error(f"restore_last_bbs_execute DB error: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="owner_recovery_menu")]]
        await query.edit_message_text(
            f"❌ Ошибка при чтении БД: {e}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if not row:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="owner_recovery_menu")]]
        await query.edit_message_text(
            "ℹ️ Нет удаленных анкет для восстановления.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    try:
        await republish_profile(
            context.bot, db, row['user_id'],
            _RECOVERY_CHAT_ID, _BBS_THREAD_ID,
        )
        keyboard = [[InlineKeyboardButton("🔙 В меню восстановления", callback_data="owner_recovery_menu")]]
        await query.edit_message_text(
            f"✅ <b>Последняя анкета восстановлена!</b>\n\n"
            f"User ID: <b>{row['user_id']}</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as e:
        logger.error(f"restore_last_bbs_execute: failed user_id={row['user_id']}: {e}")
        keyboard = [[InlineKeyboardButton("🔙 В меню восстановления", callback_data="owner_recovery_menu")]]
        await query.edit_message_text(
            f"❌ Ошибка восстановления: {e}",
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


# ═══════════════════════════════════════════════════════════════
#  🎁 КОМПЕНСАЦИЯ BBS
# ═══════════════════════════════════════════════════════════════

async def compensate_bbs_start(query, context, db, admin_id: int) -> None:
    """ШАГ 1: получает список пострадавших и просит ввести сумму."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    try:
        db.cursor.execute(
            "SELECT user_id, username, name FROM bbs_profiles WHERE published_at IS NOT NULL"
        )
        rows = db.cursor.fetchall()
    except Exception as e:
        logger.error(f"compensate_bbs_start DB error: {e}")
        rows = []

    if not rows:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="owner_recovery_menu")]]
        await query.edit_message_text(
            "📭 Нет пользователей с анкетами BBS.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    affected = [{'user_id': r['user_id'], 'username': r['username'], 'name': r['name']} for r in rows]
    context.user_data['compensate_affected'] = affected
    context.user_data['owner_awaiting'] = 'compensate_bbs_amount'

    text = (
        f"🎁 <b>КОМПЕНСАЦИЯ BBS</b>\n\n"
        f"Найдено <b>{len(affected)}</b> пострадавших пользователей с анкетами.\n\n"
        f"Введите сумму Пульсов для компенсации <b>КАЖДОМУ</b> (число):"
    )
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_recovery_menu")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def compensate_bbs_confirm(query, context, db, admin_id: int) -> None:
    """ШАГ 3: подтверждение — запускает рассылку."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    affected = context.user_data.get('compensate_affected', [])
    amount = context.user_data.get('compensate_amount', 0)

    if not affected or not amount:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="owner_recovery_menu")]]
        await query.edit_message_text(
            "❌ Данные компенсации потеряны. Начните заново.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    await query.edit_message_text("⏳ Начинаю рассылку извинений и начисление Пульсов...", parse_mode='HTML')

    success, errors = 0, 0
    for u in affected:
        uid = u['user_id']
        try:
            db.update_user_balance(uid, amount, 'add')
            db.update_bank_balance(amount, 'subtract')
            db.add_transaction(None, uid, amount, 'compensation_reward', 'Компенсация за сбой в BBS')

            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "⚠️ <b>СИСТЕМНАЯ АНОМАЛИЯ УСТРАНЕНА</b>\n\n"
                    "Недавно в ветке знакомств (BBS) произошёл сбой. "
                    "Не переживайте, ваша анкета в безопасности и уже восстановлена!\n\n"
                    f"В качестве извинений Администрация начислила вам "
                    f"<b>+{format_number(amount)} 💎 Пульсов</b>.\n\n"
                    "Спасибо, что вы с нами! ❤️"
                ),
                parse_mode='HTML',
            )
            success += 1
        except Exception as e:
            logger.error(f"compensate_bbs user {uid}: {e}")
            errors += 1
        await asyncio.sleep(0.5)

    # Очистка
    context.user_data.pop('compensate_affected', None)
    context.user_data.pop('compensate_amount', None)

    keyboard = [[InlineKeyboardButton("🔙 В меню восстановления", callback_data="owner_recovery_menu")]]
    await query.edit_message_text(
        f"✅ <b>Компенсация выплачена!</b>\n\n"
        f"Получатели: <b>{success}</b>\n"
        f"Не удалось отправить: <b>{errors}</b>\n"
        f"Списано из банка: <b>{format_number(amount * success)} 💎</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def recovery_other_confirm(query, db, admin_id: int) -> None:
    """Показывает список объявлений «Другое», доступных к восстановлению."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    try:
        db.cursor.execute(
            'SELECT * FROM bbs_other_posts WHERE deleted_by IS NULL OR deleted_by != ? '
            'ORDER BY deleted_at DESC',
            ('user',)
        )
        posts = [dict(row) for row in db.cursor.fetchall()]
    except Exception as e:
        logger.error(f"recovery_other_confirm DB error: {e}")
        posts = []

    if not posts:
        keyboard = [[InlineKeyboardButton('🔙 Назад', callback_data='owner_recovery')]]
        await query.edit_message_text(
            'ℹ️ Нет объявлений раздела «Другое», которые можно восстановить.',
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    def _safe(value):
        if value is None:
            return '—'
        return html.escape(str(value))

    def _user_tag(post):
        username = post.get('username')
        if username:
            return f'@{html.escape(username)}'
        return f'<code>{html.escape(str(post.get("user_id") or "—"))}</code>'

    def _fmt_dt(value):
        if not value:
            return '—'
        try:
            return html.escape(value.split('.')[0].replace('T', ' '))
        except Exception:
            return html.escape(str(value))

    text = [
        '📦 <b>Восстановление раздела «Другое»</b>\n',
        f'Найдено объявлений для восстановления: <b>{len(posts)}</b>\n',
        'Ниже указаны данные объявления, дата удаления и @username автора:\n'
    ]

    max_items = 8
    keyboard = []
    for index, post in enumerate(posts[:max_items], start=1):
        text.append(
            f'\n<b>{index}. {_safe(post.get("title", "Без названия"))}</b>\n'
            f'Категория: {_safe(post.get("category"))}\n'
            f'Город: {_safe(post.get("city"))}\n'
            f'Автор: {_safe(post.get("author_name"))} ({_user_tag(post)})\n'
            f'Цена: {_safe(post.get("price"))}\n'
            f'Дата удаления: {_fmt_dt(post.get("deleted_at"))}\n'
            f'Описание: {_safe(post.get("description"))[:200]}\n'
        )
        keyboard.append([
            InlineKeyboardButton(
                f'Восстановить #{post.get("id")}',
                callback_data=f'owner_recovery_other_execute_{post.get("id")}'
            )
        ])

    if len(posts) > max_items:
        text.append(f'\n...еще <b>{len(posts) - max_items}</b> объявлений.')

    keyboard.append([InlineKeyboardButton('✅ Восстановить все', callback_data='owner_recovery_other_execute_all')])
    keyboard.append([InlineKeyboardButton('❌ Отмена', callback_data='owner_recovery')])
    await query.edit_message_text(
        '\n'.join(text),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def recovery_other_execute(query, db, admin_id: int, context, target_chat_id: int, bbs_thread_id: int, post_id: int | str = None) -> None:
    """Запускает перепубликацию объявлений «Другое» из БД."""
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    if post_id is None or post_id == 'all':
        await query.edit_message_text('⏳ Восстановление всех объявлений запущено...', parse_mode='HTML')
        from handlers.BBS.fsm_other import restore_all_other_posts
        ok, errors = await restore_all_other_posts(context.bot, db, target_chat_id, bbs_thread_id)
        await query.edit_message_text(
            f'✅ <b>Восстановление завершено</b>\n\nУспешно: {ok}\nОшибок: {errors}',
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Назад', callback_data='owner_recovery')]])
        )
        return

    await query.edit_message_text('⏳ Восстановление выбранного объявления запущено...', parse_mode='HTML')
    from handlers.BBS.fsm_other import republish_other_post
    try:
        db.cursor.execute(
            'SELECT * FROM bbs_other_posts WHERE id = ? AND (deleted_by IS NULL OR deleted_by != ?) ',
            (post_id, 'user')
        )
        post = db.cursor.fetchone()
    except Exception as e:
        post = None
        logger.error(f'recovery_other_execute DB error: {e}')

    if not post:
        await query.edit_message_text(
            '❌ Объявление не найдено или восстановление уже недоступно.',
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Назад', callback_data='owner_recovery')]])
        )
        return

    try:
        await republish_other_post(context.bot, db, dict(post), target_chat_id, bbs_thread_id)
        await query.edit_message_text(
            '✅ <b>Объявление восстановлено.</b>',
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Назад', callback_data='owner_recovery')]])
        )
    except Exception as exc:
        logger.error(f'recovery_other_execute failed id={post_id}: {exc}')
        await query.edit_message_text(
            f'❌ Ошибка восстановления объявления: {html.escape(str(exc))}',
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Назад', callback_data='owner_recovery')]])
        )
