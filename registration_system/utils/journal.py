"""
Модуль для работы с журналом событий
Реализует п.5 ТЗ - логирование событий с кнопкой связи (Блок Ж)
"""
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from datetime import datetime
from typing import Optional

from database import (
    get_setting, 
    add_journal_message, 
    get_last_profile_message, 
    delete_journal_message,
    get_user
)
from constants import Hashtags
from utils.keyboards import create_dm_keyboard

logger = logging.getLogger(__name__)


async def get_journal_channel_id() -> Optional[int]:
    """Получение ID канала журнала из БД"""
    channel_id = await get_setting("journal_channel_id")
    if channel_id:
        return int(channel_id)
    return None


async def check_bot_is_admin(bot: Bot, channel_id: int) -> bool:
    """Проверка, является ли бот администратором канала"""
    try:
        bot_member = await bot.get_chat_member(channel_id, bot.id)
        return bot_member.status in ['administrator', 'creator']
    except Exception:
        return False


async def send_to_journal(
    bot: Bot, 
    text: str, 
    msg_type: str = "info", 
    user_id: Optional[int] = None,
    add_dm_button: bool = False
) -> Optional[int]:
    """
    Отправка сообщения в канал-журнал
    
    Args:
        bot: Экземпляр бота
        text: Текст сообщения
        msg_type: Тип сообщения (profile, join, exit и т.д.)
        user_id: ID пользователя (для кнопки ЛС)
        add_dm_button: Добавлять ли кнопку [Написать в ЛС]
    
    Returns:
        ID отправленного сообщения или None
    """
    # Получаем ID канала из БД
    journal_channel_id = await get_journal_channel_id()
    
    if not journal_channel_id:
        logger.warning("JOURNAL_CHANNEL_ID not set, skipping journal entry")
        return None
    
    # Определяем клавиатуру
    reply_markup = None
    if add_dm_button and user_id:
        reply_markup = create_dm_keyboard(user_id)
    
    try:
        # Добавляем хештег в зависимости от типа, если его нет
        if msg_type == "profile" and Hashtags.PROFILE not in text:
            text = f"{Hashtags.PROFILE}\n{text}"
        elif msg_type == "activity" and Hashtags.ACTIVITY not in text:
            text = f"{Hashtags.ACTIVITY}\n{text}"
        elif msg_type == "join" and Hashtags.JOIN not in text:
            text = f"{Hashtags.JOIN}\n{text}"
        elif msg_type == "exit" and Hashtags.EXIT not in text:
            text = f"{Hashtags.EXIT}\n{text}"
        elif msg_type == "kick" and Hashtags.KICK not in text:
            text = f"{Hashtags.KICK}\n{text}"
        elif msg_type == "approval" and Hashtags.APPROVED not in text:
            text = f"{Hashtags.APPROVED}\n{text}"
        elif msg_type == "rejection" and Hashtags.REJECT not in text:
            text = f"{Hashtags.REJECT}\n{text}"
        elif msg_type == "block" and Hashtags.BLOCKED not in text:
            text = f"{Hashtags.BLOCKED}\n{text}"
        elif msg_type == "unblock" and Hashtags.UNBLOCKED not in text:
            text = f"{Hashtags.UNBLOCKED}\n{text}"
        
        msg = await bot.send_message(
            journal_channel_id, 
            text, 
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        
        # Сохраняем ID сообщения в БД для последующего удаления
        await add_journal_message(msg.message_id, journal_channel_id, msg_type, user_id)
        
        logger.info(f"Sent {msg_type} message to journal (ID: {msg.message_id})")
        return msg.message_id
    except Exception as e:
        logger.error(f"Failed to send message to journal: {e}")
        return None


async def update_profile_message(
    bot: Bot,
    user_id: int,
    new_text: str,
    msg_type: str = "profile"
) -> Optional[int]:
    """
    Обновление сообщения о профиле: удаление старого и отправка нового
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        new_text: Новый текст сообщения
        msg_type: Тип сообщения
    
    Returns:
        ID нового сообщения или None
    """
    journal_channel_id = await get_journal_channel_id()
    if not journal_channel_id:
        return None
    
    # Получаем ID последнего сообщения о профиле
    last_msg_id = await get_last_profile_message(user_id, journal_channel_id)
    
    # Удаляем старое сообщение, если оно есть
    if last_msg_id:
        try:
            await bot.delete_message(journal_channel_id, last_msg_id)
            await delete_journal_message(last_msg_id)
            logger.info(f"Deleted old profile message {last_msg_id} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete old profile message: {e}")
    
    # Отправляем новое сообщение с кнопкой
    return await send_to_journal(
        bot, 
        new_text, 
        msg_type=msg_type, 
        user_id=user_id, 
        add_dm_button=True
    )


async def send_photo_to_journal(
    bot: Bot, 
    photo_id: str, 
    caption: str = "",
    user_id: Optional[int] = None,
    add_dm_button: bool = False
) -> Optional[int]:
    """Отправка фото в канал-журнал"""
    journal_channel_id = await get_journal_channel_id()
    
    if not journal_channel_id:
        logger.warning("JOURNAL_CHANNEL_ID not set, skipping photo journal entry")
        return None
    
    # Определяем клавиатуру
    reply_markup = None
    if add_dm_button and user_id:
        reply_markup = create_dm_keyboard(user_id)
    
    try:
        # Добавляем хештег фото, если его нет
        if Hashtags.PHOTO not in caption:
            caption = f"{Hashtags.PHOTO}\n{caption}"
        
        msg = await bot.send_photo(
            journal_channel_id, 
            photo_id, 
            caption=caption, 
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        
        await add_journal_message(msg.message_id, journal_channel_id, "photo", user_id)
        return msg.message_id
    except Exception as e:
        logger.error(f"Failed to send photo to journal: {e}")
        return None


# ==================== ФУНКЦИИ ЛОГИРОВАНИЯ СОБЫТИЙ ====================

async def log_join(bot: Bot, user_id: int, chat_name: str):
    """Логирование входа пользователя в чат"""
    user = await get_user(user_id)
    if not user:
        return
    
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if not full_name:
        full_name = "Пользователь"
    
    username = user.get('username', '')
    
    text = (
        f"<b>Вход в чат</b>\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
    )
    if username:
        text += f"📱 @{username}\n"
    text += f"💬 Чат: {chat_name}\n"
    text += f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    return await send_to_journal(bot, text, "join", user_id, add_dm_button=True)


async def log_exit(bot: Bot, user_id: int, chat_name: str, kicked_by: Optional[int] = None):
    """Логирование выхода пользователя из чата"""
    user = await get_user(user_id)
    if not user:
        return
    
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if not full_name:
        full_name = "Пользователь"
    
    username = user.get('username', '')
    
    action = "Исключен" if kicked_by else "Вышел"
    msg_type = "kick" if kicked_by else "exit"
    
    text = (
        f"<b>{action} из чата</b>\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
    )
    if username:
        text += f"📱 @{username}\n"
    text += f"💬 Чат: {chat_name}\n"
    if kicked_by:
        text += f"👮 Администратор: <code>{kicked_by}</code>\n"
    text += f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    return await send_to_journal(bot, text, msg_type, user_id, add_dm_button=True)


async def log_profile_change(bot: Bot, user_id: int, changes: list):
    """Логирование изменения профиля"""
    user = await get_user(user_id)
    if not user:
        return
    
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if not full_name:
        full_name = "Пользователь"
    
    text = (
        f"<b>Изменение профиля</b>\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        + "\n".join(changes)
    )
    
    # Используем update_profile_message для удаления старого сообщения
    return await update_profile_message(bot, user_id, text, "profile")


async def log_approval(bot: Bot, user_id: int, admin_id: int, chat_name: str):
    """Логирование одобрения заявки"""
    user = await get_user(user_id)
    if not user:
        return
    
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if not full_name:
        full_name = "Пользователь"
    
    username = user.get('username', '')
    
    text = (
        f"<b>Заявка одобрена</b>\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
    )
    if username:
        text += f"📱 @{username}\n"
    text += f"👨‍💼 Админ: <code>{admin_id}</code>\n"
    text += f"💬 Чат: {chat_name}\n"
    text += f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    return await send_to_journal(bot, text, "approval", user_id, add_dm_button=True)


async def log_rejection(bot: Bot, user_id: int, admin_id: int, reason: str, chat_name: str):
    """Логирование отклонения заявки"""
    user = await get_user(user_id)
    if not user:
        return
    
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if not full_name:
        full_name = "Пользователь"
    
    username = user.get('username', '')
    
    text = (
        f"<b>Заявка отклонена</b>\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
    )
    if username:
        text += f"📱 @{username}\n"
    text += f"👨‍💼 Админ: <code>{admin_id}</code>\n"
    text += f"📝 Причина: {reason}\n"
    text += f"💬 Чат: {chat_name}\n"
    text += f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    return await send_to_journal(bot, text, "rejection", user_id, add_dm_button=True)


async def log_photo_change(bot: Bot, user_id: int, photo_id: str = None):
    """Логирование смены фото"""
    user = await get_user(user_id)
    if not user:
        return
    
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if not full_name:
        full_name = "Пользователь"
    
    username = user.get('username', '')
    
    text = (
        f"<b>Изменение фото профиля</b>\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
    )
    if username:
        text += f"📱 @{username}\n"
    text += f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    if photo_id:
        return await send_photo_to_journal(bot, photo_id, text, user_id, add_dm_button=True)
    return await send_to_journal(bot, text, "photo", user_id, add_dm_button=True)


async def log_inactivity(bot: Bot, user_id: int):
    """Логирование неактивности (60+ дней)"""
    user = await get_user(user_id)
    if not user:
        return
    
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if not full_name:
        full_name = "Пользователь"
    
    username = user.get('username', '')
    
    text = (
        f"<b>Неактивность более 60 дней</b>\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
    )
    if username:
        text += f"📱 @{username}\n"
    text += f"⚠️ Пользователь не был онлайн более 60 дней\n"
    text += f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    return await send_to_journal(bot, text, "activity", user_id, add_dm_button=True)


async def log_block(bot: Bot, user_id: int, admin_id: int, reason: str):
    """Логирование блокировки пользователя"""
    user = await get_user(user_id)
    if not user:
        return
    
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if not full_name:
        full_name = "Пользователь"
    
    username = user.get('username', '')
    
    text = (
        f"<b>Блокировка пользователя</b>\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
    )
    if username:
        text += f"📱 @{username}\n"
    text += f"👨‍💼 Админ: <code>{admin_id}</code>\n"
    text += f"📝 Причина: {reason}\n"
    text += f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    return await send_to_journal(bot, text, "block", user_id, add_dm_button=True)


async def log_unblock(bot: Bot, user_id: int, admin_id: int):
    """Логирование разблокировки пользователя"""
    user = await get_user(user_id)
    if not user:
        return
    
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if not full_name:
        full_name = "Пользователь"
    
    username = user.get('username', '')
    
    text = (
        f"<b>Разблокировка пользователя</b>\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
    )
    if username:
        text += f"📱 @{username}\n"
    text += f"👨‍💼 Админ: <code>{admin_id}</code>\n"
    text += f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    return await send_to_journal(bot, text, "unblock", user_id, add_dm_button=True)


async def log_event(bot: Bot, event_type: str, user_id: int, **kwargs):
    """Общая функция для логирования событий"""
    user = await get_user(user_id)
    if not user:
        return
    
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if not full_name:
        full_name = "Пользователь"
    
    text = f"<b>Событие: {event_type}</b>\n"
    text += f"👤 Пользователь: {full_name}\n"
    text += f"🆔 ID: <code>{user_id}</code>\n"
    
    # Добавляем дополнительные параметры
    for key, value in kwargs.items():
        if value is not None:
            text += f"{key}: {value}\n"
    
    text += f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    # Определяем тип для хештега
    msg_type = event_type.lower()
    return await send_to_journal(bot, text, msg_type, user_id, add_dm_button=True)