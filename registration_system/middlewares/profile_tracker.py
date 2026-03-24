"""
Middleware для отслеживания изменений профиля пользователя
Реализует п.2.3 ТЗ - отображение изменений со стрелками/null
"""
from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable, Optional
import logging

from database import get_user, update_user
from utils.journal import send_to_journal
from constants import Hashtags

logger = logging.getLogger(__name__)


class ProfileTrackerMiddleware(BaseMiddleware):
    """
    Middleware для отслеживания изменений в профиле пользователя
    Сравнивает текущие данные с сохраненными в БД и логирует изменения
    """
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Проверяем, что событие содержит пользователя
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        current_user = event.from_user
        
        # Получаем данные пользователя из БД
        db_user = await get_user(user_id)
        
        if db_user:
            # Проверяем изменения
            changes = []
            updates = {}
            
            # Проверяем username
            old_username = db_user.get('username')
            new_username = current_user.username
            
            if old_username != new_username:
                # Форматируем изменение со стрелкой
                old_val = f"@{old_username}" if old_username else "null"
                new_val = f"@{new_username}" if new_username else "null"
                changes.append(f"📱 Никнейм: {old_val} → {new_val}")
                
                updates['username'] = new_username
                updates['previous_username'] = old_username
                logger.info(f"User {user_id} username changed: {old_username} -> {new_username}")
            
            # Проверяем first_name
            old_first = db_user.get('first_name')
            new_first = current_user.first_name
            
            if old_first != new_first:
                old_val = old_first or "null"
                new_val = new_first or "null"
                changes.append(f"👤 Имя: {old_val} → {new_val}")
                
                updates['first_name'] = new_first
                updates['previous_first_name'] = old_first
                logger.info(f"User {user_id} first_name changed: {old_first} -> {new_first}")
            
            # Проверяем last_name
            old_last = db_user.get('last_name')
            new_last = current_user.last_name
            
            if old_last != new_last:
                old_val = old_last or "null"
                new_val = new_last or "null"
                changes.append(f"👤 Фамилия: {old_val} → {new_val}")
                
                updates['last_name'] = new_last
                updates['previous_last_name'] = old_last
                logger.info(f"User {user_id} last_name changed: {old_last} -> {new_last}")
            
            # Если есть изменения, обновляем БД и логируем
            if changes:
                # Обновляем данные в БД
                await update_user(user_id, **updates)
                
                # Формируем полное имя для отображения
                full_name = f"{new_first or ''} {new_last or ''}".strip()
                if not full_name:
                    full_name = "Пользователь"
                
                # Формируем текст для журнала
                text = (
                    f"{Hashtags.PROFILE}\n"
                    f"<b>Изменение профиля</b>\n"
                    f"👤 Пользователь: {full_name}\n"
                    f"🆔 ID: <code>{user_id}</code>\n\n"
                    + "\n".join(changes)
                )
                
                # Отправляем в журнал
                await send_to_journal(event.bot, text, msg_type="profile")
        
        # Продолжаем обработку
        return await handler(event, data)


def format_change(field: str, old: Optional[str], new: Optional[str]) -> str:
    """
    Форматирование изменения поля со стрелкой
    
    Args:
        field: Название поля
        old: Старое значение
        new: Новое значение
    
    Returns:
        Отформатированная строка
    """
    # Определяем эмодзи для поля
    emoji = "📱" if field == "Никнейм" else "👤"
    
    # Форматируем значения
    if field == "Никнейм":
        old_str = f"@{old}" if old else "null"
        new_str = f"@{new}" if new else "null"
    else:
        old_str = old or "null"
        new_str = new or "null"
    
    return f"{emoji} {field}: {old_str} → {new_str}"