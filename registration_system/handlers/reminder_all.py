"""
Единый handler для всех напоминаний бота
Содержит все фоновые задачи по отправке напоминаний:
- Напоминание о незаконченной анкете (5 минут) - п.1.4.2.2
- Напоминание о неиспользованной ссылке (5 минут) - п.3.3.2
- Напоминание о неиспользованной ссылке (10 дней) - п.8.3
- Проверка неактивных пользователей (60 дней) - п.2.1
- Очистка старых фотографий (14 дней) - п.5.3
"""
import logging
import asyncio
import json
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatType

from database import (
    get_user, update_user, get_users_with_incomplete_questionnaire,
    get_users_with_unused_link, get_inactive_users,
    get_old_journal_photos, delete_journal_message,
    get_setting, create_invite_link, deactivate_invite_link,
    get_active_invite_link
)
from handlers.reminder import save_questionnaire_state, clear_questionnaire_state
from utils.keyboards import (
    create_continue_keyboard,
    create_return_chat_keyboard,
    create_submit_application_keyboard,
    create_skip_keyboard
)
from utils.journal import send_to_journal, log_inactivity
from constants import Messages, RegistrationStates, UserStatus
from config import OWNER_ID, CHAT_ID

logger = logging.getLogger(__name__)
router = Router()


# ==================== ФОНДОВЫЕ ЗАДАЧИ ====================

class ReminderTasks:
    """Класс для управления всеми фоновыми задачами"""
    
    def __init__(self, bot):
        self.bot = bot
        self._running = False
        self.tasks = []
    
    async def start(self):
        """Запуск всех фоновых задач"""
        self._running = True
        self.tasks = [
            asyncio.create_task(self.check_incomplete_questionnaires(), name="incomplete_questionnaires"),
            asyncio.create_task(self.check_unused_links_5min(), name="unused_links_5min"),
            asyncio.create_task(self.check_unused_links_10days(), name="unused_links_10days"),
            asyncio.create_task(self.check_inactive_users(), name="inactive_users"),
            asyncio.create_task(self.cleanup_old_photos(), name="old_photos"),
        ]
        logger.info(f"✅ Запущено {len(self.tasks)} фоновых задач напоминаний")
    
    async def stop(self):
        """Остановка всех фоновых задач"""
        self._running = False
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("⏹️ Все фоновые задачи остановлены")
    
    # ========== ЗАДАЧА 1: Напоминание о незаконченной анкете (5 минут) ==========
    async def check_incomplete_questionnaires(self):
        """Проверка пользователей с незаконченными анкетами (п.1.4.2.2)"""
        while self._running:
            try:
                users = await get_users_with_incomplete_questionnaire(minutes=5)
                
                for user in users:
                    user_id = user['tg_id']
                    q_name = user.get('q_name')
                    first_name = user.get('first_name')
                    state_data = json.loads(user['questionnaire_state']) if user.get('questionnaire_state') else None
                    
                    if not state_data:
                        continue
                    
                    # Получаем имя для обращения
                    user_name = q_name if q_name else (first_name or "Пользователь")
                    
                    try:
                        await self.bot.send_message(
                            user_id,
                            f"{user_name}, ты не закончил заполнение анкеты, возможно, тебя отвлекли.",
                            reply_markup=create_continue_keyboard()
                        )
                        
                        await update_user(user_id, last_activity=datetime.now().isoformat())
                        logger.info(f"📝 Напоминание о анкете отправлено пользователю {user_id}")
                        
                    except Exception as e:
                        logger.error(f"Ошибка отправки напоминания {user_id}: {e}")
                
            except Exception as e:
                logger.error(f"Ошибка в задаче check_incomplete_questionnaires: {e}")
            
            await asyncio.sleep(60)  # Проверка каждую минуту
    
    # ========== ЗАДАЧА 2: Напоминание о неиспользованной ссылке (5 минут) ==========
    async def check_unused_links_5min(self):
        """Проверка пользователей, не перешедших по ссылке в течение 5 минут (п.3.3.2)"""
        while self._running:
            try:
                users = await get_users_with_unused_link(minutes=5)
                
                for user in users:
                    user_id = user['tg_id']
                    q_name = user.get('q_name')
                    first_name = user.get('first_name')
                    invite_link = user.get('invite_link')
                    invite_message_id = user.get('invite_message_id')
                    
                    user_name = q_name if q_name else (first_name or "Пользователь")
                    
                    try:
                        # Получаем название чата
                        chat_id = await get_setting("main_chat_id")
                        if not chat_id:
                            chat_id = CHAT_ID
                        
                        chat_name = "Pulse 4ever"
                        if chat_id:
                            try:
                                chat = await self.bot.get_chat(int(chat_id))
                                chat_name = chat.title
                            except:
                                pass
                        
                        # Удаляем предыдущее сообщение со ссылкой
                        if invite_message_id:
                            try:
                                await self.bot.delete_message(user_id, invite_message_id)
                                logger.info(f"Удалено старое сообщение со ссылкой для {user_id}")
                            except Exception as e:
                                logger.error(f"Ошибка удаления сообщения: {e}")
                        
                        # Отправляем напоминание
                        text = (
                            f"{user_name},\n"
                            f"Мы заметили, что так и не воспользовался ссылкой и не перешел в чат {chat_name}. Ждем тебя!"
                        )
                        
                        msg = await self.bot.send_message(
                            user_id,
                            text,
                            reply_markup=create_return_chat_keyboard()  # Кнопка [Вернуться в чат]
                        )
                        
                        await update_user(
                            user_id,
                            invite_message_id=msg.message_id,
                            last_activity=datetime.now().isoformat()
                        )
                        
                        logger.info(f"⏰ Напоминание о ссылке (5 мин) отправлено {user_id}")
                        
                    except Exception as e:
                        logger.error(f"Ошибка отправки напоминания {user_id}: {e}")
                
            except Exception as e:
                logger.error(f"Ошибка в задаче check_unused_links_5min: {e}")
            
            await asyncio.sleep(60)  # Проверка каждую минуту
    
    # ========== ЗАДАЧА 3: Напоминание о неиспользованной ссылке (10 дней) ==========
    async def check_unused_links_10days(self):
        """Проверка пользователей, не перешедших по ссылке в течение 10 дней (п.8.3)"""
        while self._running:
            try:
                users = await get_users_with_unused_link(days=10)
                
                for user in users:
                    user_id = user['tg_id']
                    q_name = user.get('q_name')
                    first_name = user.get('first_name')
                    invite_link = user.get('invite_link')
                    invite_message_id = user.get('invite_message_id')
                    
                    user_name = q_name if q_name else (first_name or "Пользователь")
                    
                    try:
                        # Получаем название чата
                        chat_id = await get_setting("main_chat_id")
                        if not chat_id:
                            chat_id = CHAT_ID
                        
                        chat_name = "Pulse 4ever"
                        if chat_id:
                            try:
                                chat = await self.bot.get_chat(int(chat_id))
                                chat_name = chat.title
                            except:
                                pass
                        
                        # Удаляем предыдущее сообщение со ссылкой
                        if invite_message_id:
                            try:
                                await self.bot.delete_message(user_id, invite_message_id)
                                logger.info(f"Удалено старое сообщение со ссылкой для {user_id}")
                            except Exception as e:
                                logger.error(f"Ошибка удаления сообщения: {e}")
                        
                        # Отправляем напоминание
                        text = (
                            f"{user_name}, с возвращением! 👋\n\n"
                            f"Мы заметили, что ты не воспользовался своей персональной ссылкой для входа в чат {chat_name}.\n"
                            f"Возможно, ты отвлёкся или потерял её — не проблема!"
                        )
                        
                        msg = await self.bot.send_message(
                            user_id,
                            text,
                            reply_markup=create_return_chat_keyboard()  # Кнопка [Вход в чат]
                        )
                        
                        await update_user(
                            user_id,
                            invite_message_id=msg.message_id,
                            last_activity=datetime.now().isoformat()
                        )
                        
                        logger.info(f"📅 Напоминание о ссылке (10 дней) отправлено {user_id}")
                        
                    except Exception as e:
                        logger.error(f"Ошибка отправки напоминания {user_id}: {e}")
                
            except Exception as e:
                logger.error(f"Ошибка в задаче check_unused_links_10days: {e}")
            
            await asyncio.sleep(86400)  # Проверка раз в день (24 часа)
    
    # ========== ЗАДАЧА 4: Проверка неактивных пользователей (60 дней) ==========
    async def check_inactive_users(self):
        """Проверка неактивных пользователей (60+ дней) - п.2.1"""
        while self._running:
            try:
                inactive_users = await get_inactive_users(days=60)
                
                for user in inactive_users:
                    try:
                        await log_inactivity(self.bot, user['tg_id'])
                        logger.info(f"⚠️ Зарегистрирована неактивность пользователя {user['tg_id']}")
                    except Exception as e:
                        logger.error(f"Ошибка логирования неактивности: {e}")
                
                logger.info(f"Проверка неактивных завершена. Найдено: {len(inactive_users)}")
                
            except Exception as e:
                logger.error(f"Ошибка в задаче check_inactive_users: {e}")
            
            await asyncio.sleep(86400)  # Проверка раз в день (24 часа)
    
    # ========== ЗАДАЧА 5: Очистка старых фотографий (14 дней) ==========
    async def cleanup_old_photos(self):
        """Очистка старых фотографий из журнала (14+ дней) - п.5.3"""
        while self._running:
            try:
                old_photos = await get_old_journal_photos(days=14)
                
                deleted_count = 0
                for photo in old_photos:
                    try:
                        await self.bot.delete_message(
                            chat_id=photo['chat_id'],
                            message_id=photo['message_id']
                        )
                        await delete_journal_message(photo['message_id'])
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка удаления фото: {e}")
                
                logger.info(f"Очистка фотографий завершена. Удалено: {deleted_count}")
                
            except Exception as e:
                logger.error(f"Ошибка в задаче cleanup_old_photos: {e}")
            
            await asyncio.sleep(86400)  # Проверка раз в день (24 часа)


# ==================== ОБРАБОТЧИКИ КНОПОК ====================

@router.callback_query(F.data == "continue_questionnaire")
async def continue_questionnaire(callback: CallbackQuery, state: FSMContext):
    """Продолжение заполнения анкеты после напоминания"""
    logger.info(f"Продолжение анкеты от пользователя {callback.from_user.id}")
    
    await callback.answer()
    
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
        await update_user(callback.from_user.id, questionnaire_state=None)
        return
    
    if not saved_state:
        await callback.message.edit_text(
            "❌ Не удалось восстановить состояние. Начните заново с /start"
        )
        return
    
    # Восстанавливаем данные
    for key, value in saved_data.items():
        await state.update_data(**{key: value})
    
    await state.set_state(saved_state)
    await callback.message.delete()
    await callback.message.answer("Продолжаем заполнение анкеты с того места, где ты остановился.")
    
    # Отправляем следующий вопрос
    from constants import Messages
    if saved_state == RegistrationStates.WAITING_NAME:
        await callback.message.answer(Messages.Q_NAME)
    elif saved_state == RegistrationStates.WAITING_AGE:
        await callback.message.answer(Messages.Q_AGE)
    elif saved_state == RegistrationStates.WAITING_BIRTH_DATE:
        await callback.message.answer(Messages.Q_BIRTH_DATE)
    elif saved_state == RegistrationStates.WAITING_CITY:
        await callback.message.answer(Messages.Q_CITY)
    elif saved_state == RegistrationStates.WAITING_THERAPY:
        await callback.message.answer(Messages.Q_THERAPY)
    elif saved_state == RegistrationStates.WAITING_REF_CODE:
        from utils.keyboards import create_skip_keyboard
        await callback.message.answer(
            Messages.Q_REF_CODE,
            reply_markup=create_skip_keyboard()
        )


@router.callback_query(F.data == "return_to_chat")
async def return_to_chat(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки [Вернуться в чат] / [Вход в чат]"""
    logger.info(f"Пользователь {callback.from_user.id} хочет вернуться в чат")
    
    await callback.answer()
    
    user_id = callback.from_user.id
    user = await get_user(user_id)
    
    if not user:
        await callback.message.edit_text(
            "❌ Пользователь не найден. Начните с /start"
        )
        return
    
    # Пытаемся получить активную ссылку
    invite_link = await get_active_invite_link(user_id)
    
    # Если нет активной ссылки, но есть сохраненная в пользователе
    if not invite_link and user.get('invite_link'):
        invite_link = user['invite_link']
    
    if invite_link:
        await callback.message.edit_text(
            f"🔗 Твоя личная ссылка для входа:\n{invite_link}\n\n"
            f"👉 Перейди по ссылке, чтобы вступить в чат.\n"
            f"Ссылка действует только один раз!"
        )
    else:
        # Генерируем новую ссылку
        try:
            chat_id = await get_setting("main_chat_id")
            if not chat_id:
                chat_id = CHAT_ID
            
            if chat_id:
                invite_link_obj = await callback.bot.create_chat_invite_link(
                    chat_id=int(chat_id),
                    member_limit=1,
                    name=f"return_{user_id}_{datetime.now().timestamp()}"
                )
                
                await create_invite_link(user_id, invite_link_obj.invite_link)
                await update_user(user_id, invite_link=invite_link_obj.invite_link)
                
                await callback.message.edit_text(
                    f"🔗 Твоя новая личная ссылка для входа:\n{invite_link_obj.invite_link}\n\n"
                    f"👉 Перейди по ссылке, чтобы вступить в чат.\n"
                    f"Ссылка действует только один раз!"
                )
            else:
                await callback.message.edit_text(
                    "❌ Чат не настроен. Обратитесь к администратору."
                )
        except Exception as e:
            logger.error(f"Ошибка создания ссылки: {e}")
            await callback.message.edit_text(
                "❌ Не удалось создать ссылку. Обратитесь к администратору."
            )
    
    await state.clear()