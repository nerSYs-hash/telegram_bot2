"""
Handler для панели владельца - п.4.2 ТЗ
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType
from datetime import datetime

from database import (
    get_user, add_admin, remove_admin, get_all_admins,
    is_blacklisted, get_user_by_username, set_setting, get_setting,
    get_blacklist_reason,
)
from constants import Messages, UserRole
from utils.keyboards import (
    create_owner_panel_keyboard,
    create_admin_management_keyboard,
)
from utils.journal import get_journal_channel_id
from config import OWNER_ID, CHAT_ID

import logging
import random
import string

logger = logging.getLogger(__name__)

router = Router()


class OwnerStates(StatesGroup):
    waiting_admin_id = State()
    waiting_check_input = State()
    waiting_channel_forward = State()
    waiting_journal_action = State()


# Хранилище сгенерированных кодов
_pending_codes = {}


def generate_channel_code(length: int = 8) -> str:
    """Генерация уникального кода для подключения канала"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


@router.message(Command("owner_panel"), F.chat.type == ChatType.PRIVATE)
async def owner_panel(message: Message):
    """Панель владельца"""
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Нет доступа.")
        return

    await message.answer(
        "👑 **Панель владельца**\n\n"
        "Выберите действие:",
        reply_markup=create_owner_panel_keyboard(),
        parse_mode="Markdown"
    )


# ==================== УПРАВЛЕНИЕ ЖУРНАЛОМ ====================

@router.callback_query(F.data == "owner_journal")
async def owner_journal_menu(callback: CallbackQuery, state: FSMContext):
    """Меню управления журналом"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    from utils.keyboards import create_journal_management_keyboard

    journal_channel_id = await get_journal_channel_id()

    if journal_channel_id:
        status = f"✅ Канал подключен (ID: `{journal_channel_id}`)"
    else:
        status = "❌ Канал не подключен"

    await callback.message.edit_text(
        f"📢 **Управление журналом**\n\n"
        f"{status}\n\n"
        f"Выберите действие:",
        reply_markup=create_journal_management_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "journal_connect")
async def journal_connect_start(callback: CallbackQuery, state: FSMContext):
    """Начало подключения канала журнала"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    code = generate_channel_code()
    _pending_codes[code] = {
        'owner_id': callback.from_user.id,
        'created_at': datetime.now()
    }

    text = (
        "🔐 **Подключение канала журнала**\n\n"
        "1️⃣ Добавьте бота в канал как администратора\n"
        "2️⃣ Перешлите этот код в канал:\n\n"
        f"📌 **Код:** `{code}`\n\n"
        "3️⃣ После пересылки кода, бот автоматически проверит его и подключит канал\n\n"
        "⏳ Код действителен в течение 10 минут"
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=None)
    await callback.answer()


@router.message(F.forward_from_chat, F.chat.type == ChatType.PRIVATE)
async def process_channel_forward(message: Message, state: FSMContext):
    """Обработка пересланного сообщения из канала"""
    if message.from_user.id != OWNER_ID:
        return

    if not message.text:
        await message.answer("❌ Пересланное сообщение не содержит текста с кодом.")
        return

    code = message.text.strip()

    if code not in _pending_codes:
        await message.answer("❌ Неверный или устаревший код.")
        return

    code_data = _pending_codes[code]
    if (datetime.now() - code_data['created_at']).seconds > 600:
        del _pending_codes[code]
        await message.answer("❌ Код устарел. Сгенерируйте новый код.")
        return

    channel = message.forward_from_chat
    channel_id = channel.id
    channel_title = channel.title

    try:
        bot_member = await message.bot.get_chat_member(channel_id, message.bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            await message.answer(
                "❌ Бот не является администратором канала.\n"
                "Добавьте бота в канал как администратора и повторите попытку."
            )
            return
    except Exception as e:
        logger.error(f"Error checking bot permissions: {e}")
        await message.answer("❌ Не удалось проверить права бота в канале.")
        return

    await set_setting("journal_channel_id", str(channel_id))
    del _pending_codes[code]

    try:
        await message.bot.send_message(
            channel_id,
            "✅ **Журнал событий успешно подключен!**\n\n"
            "Теперь все события будут логироваться в этот канал.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send test message: {e}")

    await message.answer(
        f"✅ **Журнал событий успешно подключен!**\n\n"
        f"📌 Канал: {channel_title}\n"
        f"🆔 ID: `{channel_id}`\n\n"
        f"Теперь все события будут логироваться в этот канал.",
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "journal_disconnect")
async def journal_disconnect(callback: CallbackQuery):
    """Отключение канала журнала"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await set_setting("journal_channel_id", "")
    await callback.message.edit_text(
        "✅ **Канал журнала отключен**\n\nСобытия больше не будут логироваться.",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "journal_test")
async def journal_test(callback: CallbackQuery):
    """Отправка тестового сообщения в журнал"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    from utils.journal import send_to_journal

    result = await send_to_journal(
        callback.bot,
        "🔔 **Тестовое сообщение**\n\n"
        "Если вы видите это сообщение, канал журнала настроен правильно.",
        "info"
    )

    if result:
        await callback.answer("✅ Тестовое сообщение отправлено!", show_alert=True)
    else:
        await callback.answer("❌ Ошибка отправки. Канал не настроен.", show_alert=True)


# ==================== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "owner_admins")
async def owner_admins_menu(callback: CallbackQuery):
    """Меню управления администраторами"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "👤 **Управление администраторами**\n\nВыберите действие:",
        reply_markup=create_admin_management_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "owner_check")
async def owner_check_start(callback: CallbackQuery, state: FSMContext):
    """Начало проверки пользователя"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "🔍 **Проверка пользователя**\n\n"
        "Введите ID пользователя в формате #userXXXXXXXXX или @username:",
        parse_mode="Markdown"
    )
    await state.set_state(OwnerStates.waiting_check_input)
    await callback.answer()


@router.message(OwnerStates.waiting_check_input, F.text, F.chat.type == ChatType.PRIVATE)
async def owner_check_process(message: Message, state: FSMContext):
    """Обработка проверки пользователя"""
    if message.from_user.id != OWNER_ID:
        return

    input_text = message.text.strip()
    user = None

    if input_text.startswith('@'):
        user = await get_user_by_username(input_text[1:])
    elif input_text.startswith('#user'):
        try:
            user = await get_user(int(input_text[5:]))
        except ValueError:
            await message.answer("❌ Неверный формат ID. Используйте #userXXXXXXXXX")
            return
    elif input_text.isdigit():
        user = await get_user(int(input_text))
    else:
        await message.answer("❌ Неверный формат. Используйте @username или #userXXXXXXXXX")
        return

    if not user:
        await message.answer("❌ Пользователь не найден в базе данных.")
        await state.clear()
        return

    blacklisted = await is_blacklisted(user['tg_id'])
    blacklist_status = "✅ В черном списке" if blacklisted else "❌ Не в черном списке"
    blacklist_reason = await get_blacklist_reason(user['tg_id']) if blacklisted else ""

    status = "✅ В чате" if user.get('status') == 'in_chat' else "❌ Не в чате"
    anketa = "✅ Заполнена" if user.get('q_name') else "❌ Не заполнена"
    nick = f"@{user['username']}" if user.get('username') else "не указан"

    text = (
        f"**Результат проверки:**\n\n"
        f"👤 Имя: {user.get('q_name', 'не заполнял')}\n"
        f"📱 Пользователь: {user.get('first_name', '')} {user.get('last_name', '')}\n"
        f"🏷 Ник: {nick}\n"
        f"🆔 ID: #user{user['tg_id']}\n"
        f"📊 Статус в чате: {status}\n"
        f"📋 Анкета: {anketa}\n"
        f"🚫 Черный список: {blacklist_status}\n"
    )
    if blacklist_reason:
        text += f"📝 Причина блокировки: {blacklist_reason}\n"

    await message.answer(text, parse_mode="Markdown")
    await state.clear()


@router.callback_query(F.data == "admin_add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления администратора"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "➕ **Добавление администратора**\n\nВведите Telegram ID пользователя:",
        parse_mode="Markdown"
    )
    await state.set_state(OwnerStates.waiting_admin_id)
    await callback.answer()


@router.message(OwnerStates.waiting_admin_id, F.text, F.chat.type == ChatType.PRIVATE)
async def admin_add_process(message: Message, state: FSMContext):
    """Обработка добавления администратора"""
    if message.from_user.id != OWNER_ID:
        return

    if not message.text.isdigit():
        await message.answer("❌ ID должен быть числом. Попробуйте снова:")
        return

    tg_id = int(message.text)

    if tg_id == OWNER_ID:
        await message.answer("❌ Владелец уже имеет все права.")
        return

    user = await get_user(tg_id)
    if not user:
        await message.answer("❌ Пользователь с таким ID не найден в базе.")
        await state.clear()
        return

    await add_admin(tg_id, OWNER_ID)
    await message.answer(
        f"✅ Пользователь {user.get('first_name', '')} (ID: {tg_id}) назначен администратором."
    )
    await state.clear()


@router.callback_query(F.data == "admin_remove")
async def admin_remove_start(callback: CallbackQuery, state: FSMContext):
    """Начало удаления администратора"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    admins = await get_all_admins()
    if not admins:
        await callback.message.edit_text("📭 Список администраторов пуст.")
        await callback.answer()
        return

    text = "👤 **Текущие администраторы:**\n\n"
    for admin in admins:
        if admin['tg_id'] != OWNER_ID:
            text += f"• {admin.get('first_name', '')} {admin.get('last_name', '')} (ID: `{admin['tg_id']}`)\n"
    text += "\nВведите ID администратора для удаления:"

    await callback.message.edit_text(text, parse_mode="Markdown")
    await state.set_state(OwnerStates.waiting_admin_id)
    await callback.answer()


@router.message(OwnerStates.waiting_admin_id, F.text, F.chat.type == ChatType.PRIVATE)
async def admin_remove_process(message: Message, state: FSMContext):
    """Обработка удаления администратора"""
    if message.from_user.id != OWNER_ID:
        return

    if not message.text.isdigit():
        await message.answer("❌ ID должен быть числом. Попробуйте снова:")
        return

    tg_id = int(message.text)

    if tg_id == OWNER_ID:
        await message.answer("❌ Невозможно удалить владельца.")
        return

    user = await get_user(tg_id)
    if not user:
        await message.answer("❌ Пользователь с таким ID не найден.")
        await state.clear()
        return

    await remove_admin(tg_id)
    await message.answer(
        f"✅ Пользователь {user.get('first_name', '')} (ID: {tg_id}) удален из администраторов."
    )
    await state.clear()


@router.callback_query(F.data == "admin_back")
async def back_to_owner_panel(callback: CallbackQuery):
    """Возврат в главное меню владельца"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "👑 **Панель владельца**\n\nВыберите действие:",
        reply_markup=create_owner_panel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()
