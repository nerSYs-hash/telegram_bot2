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
        [InlineKeyboardButton("💰 Экономика", callback_data="owner_economy")],
        [InlineKeyboardButton("⚡ Триггеры", callback_data="owner_triggers")],
        [InlineKeyboardButton("📢 Журнал событий", callback_data="owner_journal")],
        [InlineKeyboardButton("📊 Опросы при выходе", callback_data="owner_survey_results")],
        [InlineKeyboardButton("⚙️ Система", callback_data="owner_system")],
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
        msg = query_or_update.effective_message or query_or_update.message
        await msg.reply_text(text, parse_mode='HTML', reply_markup=markup)


# ═══════════════════════════════════════════════════════════════
#   ЭКОНОМИКА
# ═══════════════════════════════════════════════════════════════

async def show_economy_menu(query, db, admin_id: int) -> None:
    if not _is_owner(db, query.from_user.id, admin_id):
        await query.answer("⛔", show_alert=True)
        return

    bank = db.get_bank_balance()
    text = (
        f"💰 <b>ЭКОНОМИКА</b>\n\n"
        f"🏦 Центробанк: <b>{format_number(bank)}</b> 💎"
    )
    keyboard = [
        [InlineKeyboardButton("💸 Выдать Пульсы", callback_data="owner_emit")],
        [InlineKeyboardButton("💀 Глобальный Вайп", callback_data="owner_wipe")],
        [InlineKeyboardButton("🔙 Назад", callback_data="owner_dashboard")],
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
        db.conn.commit()

        affected = db.cursor.rowcount
        logger.warning(f"GLOBAL WIPE by {query.from_user.id}: {affected} users zeroed")

        # Журнал
        try:
            from handlers.journal_handlers import log_admin_action
            await log_admin_action(
                query.message.get_bot() if hasattr(query.message, 'get_bot') else None,
                db, query.from_user.id,
                f"💀 Глобальный вайп балансов ({affected} пользователей)"
            )
        except Exception:
            pass

        text = (
            f"💀 <b>ВАЙП ВЫПОЛНЕН</b>\n\n"
            f"Обнулено пользователей: <b>{affected}</b>\n"
            f"Все балансы и замороженные средства = 0."
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
        [InlineKeyboardButton("🔙 Назад", callback_data="owner_dashboard")],
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

async def handle_owner_text_input(
    update, context, db, admin_id: int, target_chat_id: int = None
) -> bool:
    """
    Обработчик текстового ввода для FSM пульта владельца.
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

    # ── Эмиссия пульсов ──
    if awaiting == 'emit':
        context.user_data.pop('owner_awaiting', None)
        parts = text.split()
        if len(parts) != 2:
            await message.reply_text(
                "❌ Формат: <code>user_id сумма</code>",
                parse_mode='HTML',
            )
            return True

        try:
            target_id = int(parts[0])
            amount = round(float(parts[1].replace(',', '.')), 2)
        except (ValueError, TypeError):
            await message.reply_text("❌ Некорректные данные. Нужно: <code>user_id сумма</code>", parse_mode='HTML')
            return True

        if amount <= 0:
            await message.reply_text("❌ Сумма должна быть > 0.")
            return True

        target = db.get_user(target_id)
        if not target:
            await message.reply_text(f"❌ Пользователь <code>{target_id}</code> не найден.", parse_mode='HTML')
            return True

        db.update_user_balance(target_id, amount, operation='add')
        db.add_transaction(None, target_id, amount, 'admin_give', f'Эмиссия от владельца')

        name = target['username'] or target['first_name'] or target_id
        new_balance = float(target['balance']) + amount

        await message.reply_text(
            f"✅ <b>Эмиссия</b>\n\n"
            f"👤 @{name} (<code>{target_id}</code>)\n"
            f"💎 +{format_number(amount)} Пульсов\n"
            f"💰 Новый баланс: ~{format_number(new_balance)} 💎",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 К экономике", callback_data="owner_economy")]
            ])
        )
        logger.info(f"EMIT: {amount} to {target_id} by {user.id}")

        # Журнал
        try:
            from handlers.journal_handlers import log_admin_action
            await log_admin_action(
                context.bot, db, user.id,
                f"💸 Эмиссия: {amount} 💎 → ID {target_id}"
            )
        except Exception:
            pass
        return True

    # Неизвестный awaiting — сбрасываем
    context.user_data.pop('owner_awaiting', None)
    return False


# ═══════════════════════════════════════════════════════════════
#  💾 БЭКАП (существующий функционал)
# ═══════════════════════════════════════════════════════════════

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
