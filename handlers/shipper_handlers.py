#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Owner/Admin управление модулем Шиппер."""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.shipper_logic import schedule_next_shipper_run, TARGET_MODES

logger = logging.getLogger(__name__)

SHIPPER_CATEGORIES = [
    ("hot18", "🔥 Горячие / 18+"),
    ("funny", "😂 Смешные / Подколы"),
    ("romantic", "💘 Милые / Романтика"),
]

TARGET_MODE_LABELS = {
    "inactive_long": "🕸 Давно не писали",
    "active_48": "⏱ Активные 48ч",
    "active_72": "🕒 Активные 72ч",
    "all_random": "🎲 Полный рандом",
}


def _is_shipper_manager(db, user_id: int) -> bool:
    try:
        user = db.get_user(user_id)
        return bool(user and user["is_owner"] and user["is_admin"])
    except Exception:
        return False


def _shipper_status_text(db):
    try:
        enabled = db.get_setting("shipper_enabled", "0") == "1"
        min_h = db.get_setting("shipper_min_hours", "2")
        max_h = db.get_setting("shipper_max_hours", "5")
        mode = db.get_setting("shipper_target_mode", "active_48")
        phrases_count = len(db.get_shipper_phrases())
        status = "🟢 ВКЛ" if enabled else "🔴 ВЫКЛ"
        mode_label = TARGET_MODE_LABELS.get(mode, TARGET_MODES.get(mode, mode))
        return (
            f"💘 <b>РУЛЕТКА ПАР (ШИППЕР)</b>\n\n"
            f"Статус: <b>{status}</b>\n"
            f"Тайминг: <b>{min_h}..{max_h} ч</b>\n"
            f"Кого тегать: <b>{mode_label}</b>\n"
            f"Фраз в базе: <b>{phrases_count}</b>"
        )
    except Exception as e:
        logger.error(f"_shipper_status_text error: {e}")
        return "💘 <b>РУЛЕТКА ПАР (ШИППЕР)</b>\n\n❌ Ошибка чтения настроек."


async def show_shipper_menu(query, context, db, target_chat_id):
    try:
        if not _is_shipper_manager(db, query.from_user.id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        text = _shipper_status_text(db)
        keyboard = [
            [InlineKeyboardButton("🔁 Вкл/Выкл рулетку", callback_data="owner_shipper_toggle")],
            [InlineKeyboardButton("⏱ Настроить тайминг", callback_data="owner_shipper_timing")],
            [InlineKeyboardButton("🎯 Кого тегать", callback_data="owner_shipper_target_menu")],
            [InlineKeyboardButton("➕ Добавить фразу", callback_data="owner_shipper_add_phrase")],
            [InlineKeyboardButton("📋 Список фраз", callback_data="owner_shipper_list_1")],
            [InlineKeyboardButton("▶️ Запустить сейчас", callback_data="owner_shipper_run_now")],
            [InlineKeyboardButton("🔙 Назад", callback_data="owner_dashboard")],
        ]
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"show_shipper_menu error: {e}")
        try:
            await query.answer(f"Ошибка: {e}", show_alert=True)
        except Exception:
            pass


async def toggle_shipper_enabled(query, context, db, target_chat_id):
    try:
        if not _is_shipper_manager(db, query.from_user.id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        current = db.get_setting("shipper_enabled", "0")
        new_value = "0" if current == "1" else "1"
        db.set_setting("shipper_enabled", new_value)

        if new_value == "1":
            await schedule_next_shipper_run(context, db, target_chat_id)

        await show_shipper_menu(query, context, db, target_chat_id)
    except Exception as e:
        logger.error(f"toggle_shipper_enabled error: {e}")
        try:
            await query.answer(f"Ошибка: {e}", show_alert=True)
        except Exception:
            pass


async def start_shipper_timing_input(query, context, db):
    try:
        if not _is_shipper_manager(db, query.from_user.id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        context.user_data["owner_awaiting"] = "shipper_timing"
        await query.edit_message_text(
            "⏱ <b>НАСТРОЙКА ТАЙМИНГА</b>\n\n"
            "Введите: <code>мин_часы макс_часы</code>\n"
            "Пример: <code>2 6</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="owner_shipper_menu")]]),
        )
    except Exception as e:
        logger.error(f"start_shipper_timing_input error: {e}")


async def start_shipper_add_phrase(query, context, db):
    try:
        if not _is_shipper_manager(db, query.from_user.id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        context.user_data.pop("shipper_new_phrase_category", None)
        keyboard = [[InlineKeyboardButton(label, callback_data=f"owner_shipper_cat_{key}")] for key, label in SHIPPER_CATEGORIES]
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="owner_shipper_menu")])

        await query.edit_message_text(
            "➕ <b>ДОБАВЛЕНИЕ ФРАЗЫ</b>\n\n"
            "1) Выберите категорию\n"
            "2) Затем отправьте текст с <code>{user1}</code> и <code>{user2}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as e:
        logger.error(f"start_shipper_add_phrase error: {e}")


async def show_shipper_target_menu(query, db):
    try:
        if not _is_shipper_manager(db, query.from_user.id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        current = db.get_setting("shipper_target_mode", "active_48")
        keyboard = []
        for key, label in TARGET_MODE_LABELS.items():
            prefix = "✅ " if key == current else ""
            keyboard.append([InlineKeyboardButton(f"{prefix}{label}", callback_data=f"owner_shipper_target_{key}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="owner_shipper_menu")])

        await query.edit_message_text(
            "🎯 <b>КОГО ТЕГАТЬ В РУЛЕТКЕ</b>\n\nВыберите режим отбора пользователей:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as e:
        logger.error(f"show_shipper_target_menu error: {e}")


async def set_shipper_target_mode(query, data, context, db, target_chat_id):
    try:
        if not _is_shipper_manager(db, query.from_user.id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        mode = data.replace("owner_shipper_target_", "")
        if mode not in TARGET_MODE_LABELS:
            await query.answer("Неизвестный режим", show_alert=True)
            return

        db.set_setting("shipper_target_mode", mode)
        if db.get_setting("shipper_enabled", "0") == "1":
            await schedule_next_shipper_run(context, db, target_chat_id)
        await show_shipper_menu(query, context, db, target_chat_id)
    except Exception as e:
        logger.error(f"set_shipper_target_mode error: {e}")


async def select_shipper_category(query, data, context, db):
    try:
        if not _is_shipper_manager(db, query.from_user.id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        category = data.replace("owner_shipper_cat_", "")
        keys = {x[0] for x in SHIPPER_CATEGORIES}
        if category not in keys:
            await query.answer("Неверная категория", show_alert=True)
            return

        context.user_data["shipper_new_phrase_category"] = category
        context.user_data["owner_awaiting"] = "shipper_add_phrase_text"

        await query.edit_message_text(
            f"✅ Категория: <b>{category}</b>\n\n"
            "Теперь отправьте текст фразы.\n"
            "Обязательно используйте метки <code>{user1}</code> и <code>{user2}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="owner_shipper_menu")]]),
        )
    except Exception as e:
        logger.error(f"select_shipper_category error: {e}")


async def show_shipper_phrases(query, db, page=1):
    try:
        if not _is_shipper_manager(db, query.from_user.id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        category = query.data.replace("owner_shipper_listcat_", "") if str(query.data).startswith("owner_shipper_listcat_") else None
        phrases = db.get_shipper_phrases_by_category(category) if category else db.get_shipper_phrases()
        if not phrases:
            await query.edit_message_text(
                "📋 Фраз пока нет.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="owner_shipper_menu")]]),
            )
            return

        page_size = 10
        total = len(phrases)
        pages = (total + page_size - 1) // page_size
        page = max(1, min(page, pages))
        start = (page - 1) * page_size
        chunk = phrases[start:start + page_size]

        lines = ["📋 <b>ФРАЗЫ ШИППЕРА</b>\n"]
        keyboard = []
        for row in chunk:
            snippet = (row["text"][:70] + "...") if len(row["text"]) > 70 else row["text"]
            lines.append(f"<b>#{row['id']}</b> [{row['category']}] {snippet}")
            keyboard.append([InlineKeyboardButton(f"🗑 Удалить #{row['id']}", callback_data=f"owner_shipper_phrase_delete_{row['id']}")])

        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton("⬅️", callback_data=f"owner_shipper_list_{page-1}"))
        nav.append(InlineKeyboardButton(f"{page}/{pages}", callback_data="owner_shipper_noop"))
        if page < pages:
            nav.append(InlineKeyboardButton("➡️", callback_data=f"owner_shipper_list_{page+1}"))
        keyboard.append(nav)
        keyboard.append([
            InlineKeyboardButton("🔥 18+", callback_data="owner_shipper_listcat_hot18"),
            InlineKeyboardButton("😂 Подколы", callback_data="owner_shipper_listcat_funny"),
            InlineKeyboardButton("💘 Романтика", callback_data="owner_shipper_listcat_romantic"),
        ])
        keyboard.append([InlineKeyboardButton("📋 Все", callback_data="owner_shipper_list_1")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="owner_shipper_menu")])

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as e:
        logger.error(f"show_shipper_phrases error: {e}")
        try:
            await query.answer(f"Ошибка: {e}", show_alert=True)
        except Exception:
            pass


async def delete_shipper_phrase(query, data, db):
    try:
        if not _is_shipper_manager(db, query.from_user.id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        phrase_id = int(data.replace("owner_shipper_phrase_delete_", ""))
        ok = db.delete_shipper_phrase(phrase_id)
        if ok:
            await query.answer("Фраза удалена")
        else:
            await query.answer("Не удалось удалить", show_alert=True)
        await show_shipper_phrases(query, db, page=1)
    except Exception as e:
        logger.error(f"delete_shipper_phrase error: {e}")
        try:
            await query.answer(f"Ошибка: {e}", show_alert=True)
        except Exception:
            pass


async def run_shipper_now(query, context, db, target_chat_id):
    try:
        if not _is_shipper_manager(db, query.from_user.id):
            await query.answer("⛔ Нет доступа", show_alert=True)
            return

        from handlers.shipper_logic import run_shipper_roulette
        await run_shipper_roulette(context, db, target_chat_id)
        await query.answer("✅ Рулетка выполнена")
    except Exception as e:
        logger.error(f"run_shipper_now error: {e}")
        try:
            await query.answer(f"Ошибка: {e}", show_alert=True)
        except Exception:
            pass


async def handle_shipper_text_input(update, context, db, admin_id, target_chat_id=None):
    try:
        awaiting = context.user_data.get("owner_awaiting")
        if awaiting not in ("shipper_timing", "shipper_add_phrase_text"):
            return False

        user = update.effective_user
        if not _is_shipper_manager(db, user.id):
            context.user_data.pop("owner_awaiting", None)
            return False

        message = update.effective_message
        text = (message.text or "").strip()

        if awaiting == "shipper_timing":
            context.user_data.pop("owner_awaiting", None)
            parts = text.replace(",", " ").split()
            if len(parts) != 2:
                await message.reply_text("❌ Формат: мин макс. Пример: 2 6")
                return True
            try:
                min_h = int(parts[0])
                max_h = int(parts[1])
            except Exception:
                await message.reply_text("❌ Часы должны быть числами. Пример: 2 6")
                return True

            if min_h < 1 or max_h < 1 or min_h > max_h:
                await message.reply_text("❌ Некорректный диапазон. Нужно: min >= 1 и max >= min")
                return True

            db.set_setting("shipper_min_hours", str(min_h))
            db.set_setting("shipper_max_hours", str(max_h))

            if db.get_setting("shipper_enabled", "0") == "1":
                await schedule_next_shipper_run(context, db, target_chat_id)

            await message.reply_text(f"✅ Тайминг сохранен: {min_h}..{max_h} ч")
            return True

        if awaiting == "shipper_add_phrase_text":
            context.user_data.pop("owner_awaiting", None)
            category = context.user_data.get("shipper_new_phrase_category")
            context.user_data.pop("shipper_new_phrase_category", None)

            if not category:
                await message.reply_text("❌ Категория не выбрана. Начните заново.")
                return True
            if "{user1}" not in text or "{user2}" not in text:
                await message.reply_text("❌ Фраза должна содержать оба шаблона: {user1} и {user2}")
                return True

            phrase_id = db.add_shipper_phrase(category, text)
            if phrase_id:
                await message.reply_text(f"✅ Фраза добавлена (ID: {phrase_id})")
            else:
                await message.reply_text("❌ Не удалось добавить фразу")
            return True

        return False
    except Exception as e:
        logger.error(f"handle_shipper_text_input error: {e}")
        return False
