"""Handler для событий чата - вход/выход и синхронизация пользователей"""
import logging
import asyncio
from datetime import datetime
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated, Message
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER

from database import update_user, get_user, create_user, deactivate_invite_link
from utils.journal import log_join, log_exit
from config import CHAT_ID
from constants import UserStatus, UserRole, Messages
from handlers.exit_survey import send_exit_survey

logger = logging.getLogger(__name__)
router = Router()

# Синхронизация при любом сообщении в чате
@router.message(F.chat.id == CHAT_ID)
async def sync_chat_user(message: Message):
    """Синхронизация пользователя при любом сообщении в чате"""
    user_id = message.from_user.id
    logger.info(f"📨 Синхронизация: пользователь {user_id} написал в чат")
    
    user = await get_user(user_id)
    
    if not user:
        # Создаем нового пользователя
        await create_user(
            tg_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            role=UserRole.USER
        )
        await update_user(user_id, status=UserStatus.IN_CHAT)
        logger.info(f"✅ Создан новый пользователь {user_id} из сообщения в чате")
    else:
        old_status = user.get('status')
        if old_status != UserStatus.IN_CHAT:
            await update_user(user_id, status=UserStatus.IN_CHAT)
            logger.info(f"🔄 Статус пользователя {user_id} обновлен: {old_status} -> IN_CHAT")
        else:
            logger.info(f"⏸️ Статус пользователя {user_id} уже IN_CHAT")

@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def user_joined(event: ChatMemberUpdated):
    """Пользователь вступил в чат"""
    if event.chat.id != CHAT_ID:
        logger.info(f"⏭️ Событие вступления в другом чате: {event.chat.id} != {CHAT_ID}")
        return
    
    user_id = event.from_user.id
    logger.info(f"🔥🔥🔥 ВСТУПЛЕНИЕ: пользователь {user_id} вошел в чат")
    
    # Проверяем, есть ли пользователь в БД
    user = await get_user(user_id)
    
    invite_was_active = False
    
    if not user:
        # Создаем нового пользователя
        await create_user(
            tg_id=user_id,
            username=event.from_user.username,
            first_name=event.from_user.first_name,
            last_name=event.from_user.last_name
        )
        logger.info(f"✅ Создан новый пользователь {user_id} при вступлении")
    else:
        logger.info(f"📊 Найден пользователь {user_id} в БД")
        
        # Если у пользователя была активная ссылка - деактивируем её
        if user.get('invite_link'):
            await deactivate_invite_link(user['invite_link'])
            logger.info(f"🔗 Деактивирована ссылка для пользователя {user_id}")
            invite_was_active = True
        
        # Если есть ID сообщения со ссылкой - удаляем его
        if user.get('invite_message_id'):
            try:
                await event.bot.delete_message(
                    user_id,
                    user['invite_message_id']
                )
                logger.info(f"🗑️ Удалено сообщение со ссылкой для пользователя {user_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка удаления сообщения для {user_id}: {e}")
    
    # Обновляем статус в БД и очищаем ссылку
    old_status = user.get('status') if user else 'None'
    await update_user(
        user_id, 
        status=UserStatus.IN_CHAT, 
        invite_link=None,
        invite_message_id=None
    )
    logger.info(f"🔄 Статус пользователя {user_id} обновлен: {old_status} -> IN_CHAT")
    
    # Если пользователь вступил по ссылке, отправляем приглашение друзей через 1 минуту
    if invite_was_active or user:
        logger.info(f"⏰ Планируем отправку приглашения для {user_id} через 60 сек")
        try:
            asyncio.create_task(send_delayed_invite(event.bot, user_id))
        except Exception as e:
            logger.error(f"❌ Ошибка планирования приглашения: {e}")
    
    # Логируем в журнал
    await log_join(event.bot, user_id, event.chat.title or "Pulse 4ever")

async def send_delayed_invite(bot, user_id: int, delay: int = 60):
    """Отправка приглашения друзей с задержкой"""
    try:
        logger.info(f"⏳ Задержка {delay} сек для пользователя {user_id}")
        await asyncio.sleep(delay)
        
        # Получаем актуальные данные пользователя
        user_data = await get_user(user_id)
        if not user_data:
            logger.warning(f"⚠️ Пользователь {user_id} не найден при отправке приглашения")
            return
        
        # Проверяем, что пользователь все еще в чате
        current_status = user_data.get('status')
        if current_status != UserStatus.IN_CHAT:
            logger.info(f"⏭️ Пользователь {user_id} больше не в чате (статус: {current_status}), пропускаем приглашение")
            return
        
        # Получаем имя пользователя для приглашения
        user_name = user_data.get('q_name', user_data.get('first_name', 'Друг'))
        
        # Отправляем приглашение
        await bot.send_message(
            user_id,
            Messages.INVITE_FRIENDS.format(name=user_name)
        )
        logger.info(f"✅ Отправлено приглашение друзей пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки приглашения пользователю {user_id}: {e}")

@router.chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def user_left(event: ChatMemberUpdated):
    """Пользователь вышел из чата"""
    if event.chat.id != CHAT_ID:
        logger.info(f"⏭️ Событие выхода в другом чате: {event.chat.id} != {CHAT_ID}")
        return
    
    user_id = event.from_user.id
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    
    logger.info(f"🔥🔥🔥 ВЫХОД: пользователь {user_id} покинул чат")
    logger.info(f"📊 Статус: {old_status} -> {new_status}")
    
    # Получаем пользователя из БД для логирования
    user = await get_user(user_id)
    if user:
        old_db_status = user.get('status')
        logger.info(f"📊 Статус в БД до обновления: {old_db_status}")
        
        # Получаем имя для опроса
        user_name = user.get('q_name', user.get('first_name', 'Пользователь'))
    else:
        logger.info(f"📊 Пользователь {user_id} не найден в БД")
        user_name = event.from_user.first_name
    
    # Обновляем статус в БД
    await update_user(
        user_id, 
        status=UserStatus.NOT_IN_CHAT, 
        last_exit_at=datetime.now().isoformat()
    )
    logger.info(f"✅ Статус пользователя {user_id} обновлен на NOT_IN_CHAT")
    
    # Определяем кикнули или сам вышел
    kicked_by = None
    if new_status == "kicked" and event.from_user.id != user_id:
        kicked_by = event.from_user.id
        logger.info(f"👢 Пользователь {user_id} был кикнут администратором {kicked_by}")
    
    # Если пользователь вышел сам (не кикнули), отправляем опрос
    if not kicked_by and user:
        logger.info(f"📝 Планируем отправку опроса для {user_id}")
        try:
            asyncio.create_task(send_exit_survey(event.bot, user_id, user_name))
        except Exception as e:
            logger.error(f"❌ Ошибка планирования опроса: {e}")
    
    # Логируем в журнал
    await log_exit(event.bot, user_id, event.chat.title or "Pulse 4ever", kicked_by)