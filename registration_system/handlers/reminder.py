"""
Handler для отправки напоминаний пользователям, не закончившим заполнение анкеты
Реализует п.1.4.2.2 ТЗ - Напоминание через 5 минут
"""
import logging
import json
import asyncio
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatType

from database import get_users_with_incomplete_questionnaire, update_user, get_user
from utils.keyboards import create_continue_keyboard, create_skip_keyboard
from constants import Messages, RegistrationStates

logger = logging.getLogger(__name__)
router = Router()


async def check_incomplete_questionnaires(bot):
    """Проверка пользователей с незаконченными анкетами"""
    while True:
        try:
            # Находим пользователей, которые начали заполнение, но не закончили
            # и не получали напоминание более 5 минут
            users = await get_users_with_incomplete_questionnaire(minutes=5)
            
            for user in users:
                user_id = user['tg_id']
                q_name = user.get('q_name')
                first_name = user.get('first_name')
                state_data = json.loads(user['questionnaire_state']) if user.get('questionnaire_state') else None
                
                if not state_data:
                    continue
                
                # Получаем имя для обращения
                user_name = q_name if q_name else first_name
                if not user_name:
                    user_name = "Пользователь"
                
                try:
                    # Отправляем напоминание
                    await bot.send_message(
                        user_id,
                        f"{user_name}, ты не закончил заполнение анкеты, возможно, тебя отвлекли.",
                        reply_markup=create_continue_keyboard()
                    )
                    
                    # Обновляем время последней активности
                    await update_user(
                        user_id,
                        last_activity=datetime.now().isoformat()
                    )
                    
                    logger.info(f"Reminder sent to user {user_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send reminder to {user_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error in reminder checker: {e}")
        
        # Ждем 1 минуту перед следующей проверкой
        await asyncio.sleep(60)


async def save_questionnaire_state(user_id: int, state: dict):
    """Сохранение состояния анкеты в БД"""
    await update_user(
        user_id,
        questionnaire_state=json.dumps(state) if state else None,
        last_activity=datetime.now().isoformat()
    )


async def clear_questionnaire_state(user_id: int):
    """Очистка состояния анкеты после завершения"""
    await update_user(
        user_id,
        questionnaire_state=None,
        last_activity=datetime.now().isoformat()
    )


@router.callback_query(F.data == "continue_questionnaire", F.message.chat.type == ChatType.PRIVATE)
async def continue_questionnaire(callback: CallbackQuery, state: FSMContext):
    """Продолжение заполнения анкеты после напоминания"""
    logger.info(f"Continue questionnaire from user {callback.from_user.id}")
    
    await callback.answer()
    
    # Получаем сохраненное состояние из БД
    user = await get_user(callback.from_user.id)
    if not user or not user.get('questionnaire_state'):
        await callback.message.edit_text(
            "❌ Не удалось восстановить анкету. Начните заново с /start"
        )
        return
    
    try:
        state_data = json.loads(user['questionnaire_state'])
        saved_state = state_data.get('state')
        saved_data = state_data.get('data', {})
    except json.JSONDecodeError:
        await callback.message.edit_text(
            "❌ Ошибка при восстановлении анкеты. Начните заново с /start"
        )
        await clear_questionnaire_state(callback.from_user.id)
        return
    
    if not saved_state:
        await callback.message.edit_text(
            "❌ Не удалось восстановить состояние анкеты. Начните заново с /start"
        )
        await clear_questionnaire_state(callback.from_user.id)
        return
    
    # Восстанавливаем данные
    for key, value in saved_data.items():
        await state.update_data(**{key: value})
    
    # Устанавливаем состояние
    await state.set_state(saved_state)
    
    # Удаляем сообщение с напоминанием
    await callback.message.delete()
    
    # Отправляем сообщение о продолжении
    await callback.message.answer(
        "Продолжаем заполнение анкеты с того места, где ты остановился."
    )
    
    # Отправляем следующий вопрос в зависимости от состояния
    if saved_state == RegistrationStates.WAITING_NAME.state:
        await callback.message.answer(Messages.Q_NAME)
    elif saved_state == RegistrationStates.WAITING_AGE.state:
        await callback.message.answer(Messages.Q_AGE)
    elif saved_state == RegistrationStates.WAITING_BIRTH_DATE.state:
        await callback.message.answer(Messages.Q_BIRTH_DATE)
    elif saved_state == RegistrationStates.WAITING_CITY.state:
        await callback.message.answer(Messages.Q_CITY)
    elif saved_state == RegistrationStates.WAITING_THERAPY.state:
        await callback.message.answer(Messages.Q_THERAPY)
    elif saved_state == RegistrationStates.WAITING_REF_CODE.state:
        await callback.message.answer(
            Messages.Q_REF_CODE,
            reply_markup=create_skip_keyboard()
        )
    else:
        # Если состояние не распознано, начинаем заново
        await callback.message.answer(
            "❌ Не удалось определить место остановки. Начните заполнение заново с /start"
        )
        await state.clear()
        await clear_questionnaire_state(callback.from_user.id)