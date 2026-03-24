from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
# Импортируем функцию получения юзера из файла друга
from database import get_user

class CheckRegistrationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        
        # 1. Проверяем, существует ли пользователь в базе друга
        user = await get_user(user_id)
        
        # 2. Если юзера нет или он не заполнил имя (q_name)
        # И если это не команда /start (чтобы он мог зарегистрироваться)
        if not user or not user.get('q_name'):
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
            
            await event.answer("⚠️ Для использования бота необходимо пройти регистрацию.\nВведите /start")
            return # Блокируем выполнение остальных функций

        # Если всё ок, передаем управление дальше (в твои функции)
        return await handler(event, data)