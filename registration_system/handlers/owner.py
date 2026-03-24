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
    add_to_blacklist, remove_from_blacklist, is_blacklisted,
    get_user_by_username, set_setting, get_setting,
    get_blacklist_reason, get_blacklist_with_users  # Новая функция
)
from constants import Messages, UserRole
from utils.keyboards import (
    create_owner_panel_keyboard,
    create_admin_management_keyboard,
    create_blacklist_management_keyboard,
    create_blacklist_list_keyboard  # Новая клавиатура
)
from utils.journal import log_block, log_unblock, get_journal_channel_id
from config import OWNER_ID, CHAT_ID

import logging
import random
import string

logger = logging.getLogger(__name__)

router = Router()


class OwnerStates(StatesGroup):
    waiting_admin_id = State()
    waiting_blacklist_id = State()
    waiting_blacklist_reason = State()
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
    
    # Проверяем, подключен ли уже канал
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
    
    # Генерируем уникальный код
    code = generate_channel_code()
    
    # Сохраняем код в временное хранилище
    _pending_codes[code] = {
        'owner_id': callback.from_user.id,
        'created_at': datetime.now()
    }
    
    # Формируем инструкцию
    text = (
        "🔐 **Подключение канала журнала**\n\n"
        "1️⃣ Добавьте бота в канал как администратора\n"
        "2️⃣ Перешлите этот код в канал:\n\n"
        f"📌 **Код:** `{code}`\n\n"
        "3️⃣ После пересылки кода, бот автоматически проверит его и подключит канал\n\n"
        "⏳ Код действителен в течение 10 минут"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=None
    )
    await callback.answer()


@router.message(F.forward_from_chat, F.chat.type == ChatType.PRIVATE)
async def process_channel_forward(message: Message, state: FSMContext):
    """Обработка пересланного сообщения из канала"""
    if message.from_user.id != OWNER_ID:
        return
    
    # Получаем текст пересланного сообщения
    if not message.text:
        await message.answer("❌ Пересланное сообщение не содержит текста с кодом.")
        return
    
    code = message.text.strip()
    
    # Проверяем, есть ли такой код в хранилище
    if code not in _pending_codes:
        await message.answer("❌ Неверный или устаревший код.")
        return
    
    # Проверяем, не истек ли код (10 минут)
    code_data = _pending_codes[code]
    created_at = code_data['created_at']
    now = datetime.now()
    
    if (now - created_at).seconds > 600:  # 10 минут
        del _pending_codes[code]
        await message.answer("❌ Код устарел. Сгенерируйте новый код.")
        return
    
    # Получаем информацию о канале
    channel = message.forward_from_chat
    channel_id = channel.id
    channel_title = channel.title
    
    # Проверяем, является ли бот администратором канала
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
        await message.answer(
            "❌ Не удалось проверить права бота в канале.\n"
            "Убедитесь, что бот добавлен в канал как администратор."
        )
        return
    
    # Сохраняем ID канала в БД
    await set_setting("journal_channel_id", str(channel_id))
    
    # Удаляем использованный код
    del _pending_codes[code]
    
    # Отправляем тестовое сообщение
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
        "✅ **Канал журнала отключен**\n\n"
        "События больше не будут логироваться.",
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


# ==================== УПРАВЛЕНИЕ ЧЕРНЫМ СПИСКОМ ====================

@router.callback_query(F.data == "owner_blacklist")
async def owner_blacklist_menu(callback: CallbackQuery):
    """Меню управления черным списком"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    from database import get_blacklist_count
    
    # Получаем количество заблокированных пользователей
    count = await get_blacklist_count()
    
    await callback.message.edit_text(
        f"🚫 **Управление черным списком**\n\n"
        f"Всего заблокировано: {count}\n\n"
        f"Выберите действие:",
        reply_markup=create_blacklist_management_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "blacklist_list")
async def blacklist_list(callback: CallbackQuery):
    """Просмотр черного списка"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    from database import get_blacklist_with_users
    
    # Получаем список заблокированных пользователей с данными
    blacklist = await get_blacklist_with_users()
    
    if not blacklist:
        await callback.message.edit_text(
            "📭 **Черный список пуст**\n\n"
            "Нет заблокированных пользователей.",
            reply_markup=create_blacklist_management_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    # Формируем текст для первого сообщения (максимум 5 записей)
    page = 0
    await show_blacklist_page(callback.message, blacklist, page)
    await callback.answer()


async def show_blacklist_page(message: Message, blacklist: list, page: int):
    """Показать страницу черного списка"""
    from utils.keyboards import create_blacklist_pagination_keyboard
    
    items_per_page = 5
    total_pages = (len(blacklist) + items_per_page - 1) // items_per_page
    
    start = page * items_per_page
    end = start + items_per_page
    current_items = blacklist[start:end]
    
    text = f"🚫 **Черный список** (страница {page + 1} из {total_pages})\n\n"
    
    for item in current_items:
        user = item['user']
        ban_date = datetime.fromisoformat(item['created_at']).strftime('%d.%m.%Y')
        
        full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        if not full_name:
            full_name = "Без имени"
        
        username = f"@{user.get('username')}" if user.get('username') else "нет username"
        
        text += (
            f"👤 **{full_name}**\n"
            f"📱 {username}\n"
            f"🆔 `{user['tg_id']}`\n"
            f"📅 Заблокирован: {ban_date}\n"
            f"📝 Причина: {item['reason']}\n"
            f"👮 Админ: `{item['admin_id']}`\n\n"
        )
    
    await message.edit_text(
        text,
        reply_markup=create_blacklist_pagination_keyboard(page, total_pages),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("blacklist_page_"))
async def blacklist_page(callback: CallbackQuery):
    """Переключение страниц черного списка"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    page = int(callback.data.split("_")[2])
    
    from database import get_blacklist_with_users
    blacklist = await get_blacklist_with_users()
    
    await show_blacklist_page(callback.message, blacklist, page)
    await callback.answer()


@router.callback_query(F.data == "blacklist_add")
async def blacklist_add_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления в черный список"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🚫 **Добавление в черный список**\n\n"
        "Введите Telegram ID или @username пользователя:",
        parse_mode="Markdown"
    )
    await state.set_state(OwnerStates.waiting_blacklist_id)
    await callback.answer()


@router.message(OwnerStates.waiting_blacklist_id, F.text, F.chat.type == ChatType.PRIVATE)
async def blacklist_add_id_process(message: Message, state: FSMContext):
    """Обработка ввода ID для черного списка"""
    if message.from_user.id != OWNER_ID:
        return
    
    input_text = message.text.strip()
    
    # Определяем формат ввода
    if input_text.startswith('@'):
        username = input_text[1:]
        user = await get_user_by_username(username)
        if not user:
            await message.answer("❌ Пользователь с таким username не найден.")
            return
        tg_id = user['tg_id']
    elif input_text.isdigit():
        tg_id = int(input_text)
        user = await get_user(tg_id)
        if not user:
            await message.answer("❌ Пользователь с таким ID не найден.")
            return
    else:
        await message.answer("❌ Неверный формат. Используйте @username или числовой ID.")
        return
    
    if tg_id == OWNER_ID:
        await message.answer("❌ Нельзя заблокировать владельца.")
        return
    
    # Проверяем, не в черном ли уже списке
    if await is_blacklisted(tg_id):
        reason = await get_blacklist_reason(tg_id)
        await message.answer(
            f"⚠️ Пользователь уже в черном списке.\n"
            f"Причина: {reason}"
        )
        await state.clear()
        return
    
    await state.update_data(blacklist_tg_id=tg_id, blacklist_user=user)
    await message.answer("📝 Укажите причину блокировки:")
    await state.set_state(OwnerStates.waiting_blacklist_reason)


@router.message(OwnerStates.waiting_blacklist_reason, F.text, F.chat.type == ChatType.PRIVATE)
async def blacklist_add_reason_process(message: Message, state: FSMContext):
    """Обработка причины блокировки"""
    if message.from_user.id != OWNER_ID:
        return
    
    reason = message.text.strip()
    if len(reason) < 3:
        await message.answer("❌ Причина слишком короткая. Укажите минимум 3 символа.")
        return
    
    data = await state.get_data()
    tg_id = data['blacklist_tg_id']
    user = data['blacklist_user']
    
    # Добавляем в черный список
    await add_to_blacklist(tg_id, reason, OWNER_ID)
    
    # Логируем в журнал
    await log_block(message.bot, tg_id, OWNER_ID, reason)
    
    # Отправляем уведомление пользователю (если возможно)
    try:
        group_name = "Pulse 4ever"
        owner_mention = f"<a href='tg://user?id={OWNER_ID}'>владелец</a>"
        
        await message.bot.send_message(
            tg_id,
            Messages.BLACKLISTED.format(
                first_name=user.get('first_name', 'Пользователь'),
                group_name=group_name,
                reason=reason,
                owner_mention=owner_mention
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to notify user about blacklist: {e}")
    
    await message.answer(
        f"✅ Пользователь {user.get('first_name', '')} (ID: {tg_id}) добавлен в черный список.\n"
        f"Причина: {reason}"
    )
    await state.clear()


@router.callback_query(F.data == "blacklist_remove")
async def blacklist_remove_start(callback: CallbackQuery, state: FSMContext):
    """Начало удаления из черного списка"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🚫 **Удаление из черного списка**\n\n"
        "Введите Telegram ID пользователя:",
        parse_mode="Markdown"
    )
    await state.set_state(OwnerStates.waiting_blacklist_id)
    await callback.answer()


@router.message(OwnerStates.waiting_blacklist_id, F.text, F.chat.type == ChatType.PRIVATE)
async def blacklist_remove_process(message: Message, state: FSMContext):
    """Обработка удаления из черного списка"""
    if message.from_user.id != OWNER_ID:
        return
    
    if not message.text.isdigit():
        await message.answer("❌ Введите числовой ID.")
        return
    
    tg_id = int(message.text)
    user = await get_user(tg_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден.")
        await state.clear()
        return
    
    # Проверяем, в черном ли списке
    if not await is_blacklisted(tg_id):
        await message.answer("❌ Пользователь не находится в черном списке.")
        await state.clear()
        return
    
    # Получаем причину для логирования
    reason = await get_blacklist_reason(tg_id)
    
    # Удаляем из черного списка
    await remove_from_blacklist(tg_id)
    
    # Логируем в журнал
    await log_unblock(message.bot, tg_id, OWNER_ID)
    
    await message.answer(
        f"✅ Пользователь {user.get('first_name', '')} (ID: {tg_id}) удален из черного списка.\n"
        f"Предыдущая причина: {reason}"
    )
    await state.clear()


# ==================== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "owner_admins")
async def owner_admins_menu(callback: CallbackQuery):
    """Меню управления администраторами"""
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👤 **Управление администраторами**\n\n"
        "Выберите действие:",
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
    
    # Определяем формат ввода
    if input_text.startswith('@'):
        # Поиск по username
        username = input_text[1:]
        user = await get_user_by_username(username)
        search_type = "username"
    elif input_text.startswith('#user'):
        # Поиск по ID в формате #userXXXXX
        try:
            tg_id = int(input_text[5:])
            user = await get_user(tg_id)
            search_type = "id"
        except ValueError:
            await message.answer("❌ Неверный формат ID. Используйте #userXXXXXXXXX")
            return
    elif input_text.isdigit():
        # Поиск по числовому ID
        user = await get_user(int(input_text))
        search_type = "id"
    else:
        await message.answer("❌ Неверный формат. Используйте @username или #userXXXXXXXXX")
        return
    
    if not user:
        await message.answer("❌ Пользователь не найден в базе данных.")
        await state.clear()
        return
    
    # Проверяем, в черном ли списке
    blacklisted = await is_blacklisted(user['tg_id'])
    blacklist_status = "✅ В черном списке" if blacklisted else "❌ Не в черном списке"
    if blacklisted:
        blacklist_reason = await get_blacklist_reason(user['tg_id'])
    else:
        blacklist_reason = ""
    
    # Формируем ответ
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
        "➕ **Добавление администратора**\n\n"
        "Введите Telegram ID пользователя:",
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
    
    # Показываем список текущих админов
    admins = await get_all_admins()
    if not admins:
        await callback.message.edit_text("📭 Список администраторов пуст.")
        await callback.answer()
        return
    
    text = "👤 **Текущие администраторы:**\n\n"
    for admin in admins:
        if admin['tg_id'] != OWNER_ID:  # Не показываем владельца
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
        "👑 **Панель владельца**\n\n"
        "Выберите действие:",
        reply_markup=create_owner_panel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()