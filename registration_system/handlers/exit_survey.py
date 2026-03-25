"""
Handler для анкетирования ушедших пользователей
Реализует п.6 ТЗ - Опрос при выходе из чата
"""
import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType

from database import (
    get_user, update_user, create_invite_link, get_setting,
    should_send_survey, save_survey_result, get_referral_code
)
from utils.keyboards import (
    create_return_chat_keyboard,
    create_exit_push_keyboard,
    create_survey_keyboard,
    create_invite_friends_keyboard,
    create_dm_keyboard
)
from constants import Messages, UserStatus
from config import OWNER_ID, CHAT_ID

logger = logging.getLogger(__name__)
router = Router()


class SurveyStates(StatesGroup):
    """Состояния для опроса ушедших пользователей"""
    waiting_reason = State()
    waiting_expectations = State()
    waiting_threat_details = State()
    waiting_info_request = State()
    waiting_dislike_details = State()
    waiting_other_details = State()
    waiting_improvement = State()
    waiting_event = State()
    waiting_love_place = State()
    waiting_q4 = State()
    waiting_q5 = State()
    waiting_final = State()


# ==================== ОСНОВНАЯ ЛОГИКА ====================

async def send_exit_survey(bot, user_id: int, user_name: str):
    """Отправка опроса или сообщения 'снова ушел' при выходе из чата (п.6 ТЗ)"""
    try:
        if await should_send_survey(user_id):
            # Первый выход или прошло 30+ дней → пуш-уведомление (п.6.2)
            text = (
                f"Привет, {user_name},\n"
                f"Мы заметили, что ты вышел из чата Pulse 4ever. Нам очень жаль, что ты ушел 😔\n\n"
                f"Возможно ты поспешил? Не исключай дополнительную возможность знакомства, "
                f"ведь у нас есть доска BBS, где ты можешь публиковать сообщения о знакомстве, "
                f"знакомиться с людьми на офлайн встречах, участвовать в конкурсах, а главное - "
                f"ты всегда можешь получить консультацию равного консультанта по теме.\n\n"
                f"Если ты вышел по ошибке, нажми [Вернуться в чат]\n\n"
                f"Если же все же ты сделал это намеренно, пожалуйста, оставь обратную связь и "
                f"ответь на несколько вопросов. Это поможет нам стать лучше и займет не более 5 минут!"
            )
            await bot.send_message(
                user_id,
                text,
                reply_markup=create_exit_push_keyboard()
            )
            await update_user(user_id, last_survey_at=datetime.now().isoformat())
            logger.info(f"Exit survey push sent to {user_id}")
        else:
            # Повторный выход в течение 30 дней → сообщение "снова ушел" с одноразовой ссылкой
            await send_again_left_message(bot, user_id, user_name)

    except Exception as e:
        logger.error(f"Failed to send exit survey to {user_id}: {e}")


async def send_again_left_message(bot, user_id: int, user_name: str):
    """Отправка сообщения при повторном выходе в течение 30 дней (п.6 ТЗ)"""
    try:
        link = await generate_return_link(bot, user_id)
        if not link:
            logger.warning(f"Could not generate return link for {user_id} (again left)")
            return

        text = (
            f"{user_name}, привет!\n\n"
            f"Мы заметили, что ты снова ушел 🥺\n"
            f"Если это случайность, держи свою личную ссылку:\n"
            f"{link}"
        )
        msg = await bot.send_message(user_id, text)

        # Сохраняем message_id чтобы удалить сообщение при повторном вступлении
        await update_user(user_id, invite_message_id=msg.message_id)
        logger.info(f"'Again left' message sent to {user_id}")
    except Exception as e:
        logger.error(f"Failed to send 'again left' message to {user_id}: {e}")


async def generate_return_link(bot, user_id: int) -> str:
    """Генерация одноразовой ссылки для возврата в чат"""
    try:
        chat_id = await get_setting("main_chat_id")
        if not chat_id:
            chat_id = CHAT_ID
        
        if chat_id:
            invite_link_obj = await bot.create_chat_invite_link(
                chat_id=int(chat_id),
                member_limit=1,
                name=f"return_{user_id}_{datetime.now().timestamp()}"
            )
            
            await create_invite_link(user_id, invite_link_obj.invite_link)
            return invite_link_obj.invite_link
    except Exception as e:
        logger.error(f"Failed to generate return link for {user_id}: {e}")
    
    return None


# ==================== ОБРАБОТЧИКИ КНОПОК ====================

@router.callback_query(F.data == "return_to_chat")
async def return_to_chat(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки [Вернуться в чат] — генерирует одноразовую ссылку (п.6.1 ТЗ)"""
    logger.info(f"User {callback.from_user.id} wants to return to chat")

    await callback.answer()

    user_id = callback.from_user.id

    # Генерируем ссылку для возврата
    link = await generate_return_link(callback.bot, user_id)

    if link:
        # Сохраняем message_id чтобы удалить при вступлении
        await update_user(user_id, invite_message_id=callback.message.message_id)
        await callback.message.edit_text(
            f"Держи свою личную ссылку для возврата:\n{link}\n\n"
            f"Ссылка одноразовая и действительна только для тебя."
        )
    else:
        await callback.message.edit_text(
            "❌ Не удалось создать ссылку для возврата. Обратитесь к администратору."
        )

    await state.clear()


@router.callback_query(F.data == "continue_survey")
async def start_survey(callback: CallbackQuery, state: FSMContext):
    """Начало опроса"""
    logger.info(f"User {callback.from_user.id} started exit survey")
    
    await callback.answer()
    
    # Вопрос 1: Почему вышел?
    options = [
        "Скучно", "Одни и те же лица", "Мало народа", "Другие ожидания",
        "Много флуда", "Угрозы/Шантаж", "Меня игнорят", "Надоело",
        "Нашел любовь", "Нет нужной инфы", "Не зашло", "Токсичность",
        "Нет времени", "Много уведомлений", "Другое"
    ]
    
    await callback.message.edit_text(
        "1 Почему ты вышел из чата?",
        reply_markup=create_survey_keyboard(options, row_width=2)
    )
    await state.set_state(SurveyStates.waiting_reason)


@router.callback_query(F.data == "decline_survey")
async def decline_survey(callback: CallbackQuery, state: FSMContext):
    """Отказ от опроса"""
    logger.info(f"User {callback.from_user.id} declined survey")
    
    await callback.answer()
    await callback.message.edit_text(
        "Хорошо, если передумаешь - просто напиши /start"
    )
    await state.clear()


# ==================== ОБРАБОТКА ОТВЕТОВ ====================

@router.callback_query(SurveyStates.waiting_reason)
async def process_reason(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 1"""
    reason = callback.data.replace("survey_", "")
    
    await state.update_data(q1=reason)
    
    # Обработка специальных случаев
    if reason == "другие ожидания":
        await callback.message.edit_text(
            "Какие ожидания у тебя были от чата?"
        )
        await state.set_state(SurveyStates.waiting_expectations)
    
    elif reason == "угрозы/шантаж":
        await callback.message.edit_text(
            "Укажи при каких обстоятельствах это произошло? "
            "Эти люди из чата? Укажи, пожалуйста, их ник. "
            "Расскажи очень подробно, это поможет нам уберечь других пользователей."
        )
        await state.set_state(SurveyStates.waiting_threat_details)
    
    elif reason == "меня игнорят":
        await callback.message.edit_text(
            "Это очень прискорбно слышать. Давай попробуем еще раз. Как ты смотришь на это?",
            reply_markup=create_return_chat_keyboard()
        )
        await state.set_state(SurveyStates.waiting_final)
    
    elif reason == "надоело":
        await callback.message.edit_text(
            "А ты знал, что в телеграмме есть функция Архив. "
            "Не обязательно уходить из чата, можно временно смахнуть чат в архив.",
            reply_markup=create_return_chat_keyboard()
        )
        await state.set_state(SurveyStates.waiting_final)
    
    elif reason == "нашел любовь":
        options = ["В нашем чате", "В другом чате", "На сайте знакомств", "Познакомили друзья", "Другое"]
        await callback.message.edit_text(
            "Укажи, где ты встретил свою вторую половинку?",
            reply_markup=create_survey_keyboard(options)
        )
        await state.set_state(SurveyStates.waiting_love_place)
    
    elif reason == "нет нужной инфы":
        await callback.message.edit_text(
            "Укажи, какую информацию ты искал более подробно?"
        )
        await state.set_state(SurveyStates.waiting_info_request)
    
    elif reason == "не зашло":
        await callback.message.edit_text(
            "Расскажи более подробно, что именно тебе не понравилось в чате?"
        )
        await state.set_state(SurveyStates.waiting_dislike_details)
    
    elif reason == "много уведомлений":
        await callback.message.edit_text(
            "А ты знал, что уведомления можно отключить?\n\n"
            "Чтобы отключить уведомления от определённого чата в Telegram, нужно:\n"
            "1. Открыть приложение и перейти в нужный чат.\n"
            "2. Найти иконку с тремя точками или шестерёнку в верхнем углу экрана и нажать на неё.\n"
            "3. В открывшемся меню выбрать «Отключить уведомления».\n"
            "4. Можно выбрать временной интервал, на который нужно отключить уведомления, "
            "например, на 1 час, 8 часов или навсегда.",
            reply_markup=create_return_chat_keyboard()
        )
        await state.set_state(SurveyStates.waiting_final)
    
    elif reason == "другое":
        await callback.message.edit_text(
            "Расскажи нам подробности, нам очень интересно!"
        )
        await state.set_state(SurveyStates.waiting_other_details)
    
    else:
        # Обычный ответ - переходим к вопросу 2
        await ask_question2(callback.message, state)


async def ask_question2(message: Message, state: FSMContext):
    """Вопрос 2: Что можно улучшить?"""
    options = [
        "Работу админов", "Количество пользователей", "Конкурсы",
        "Темы/Ветки", "Не знаю", "Работу бота", "Другое"
    ]
    
    await message.edit_text(
        "2 Что можно улучшить в первую очередь?",
        reply_markup=create_survey_keyboard(options)
    )
    await state.set_state(SurveyStates.waiting_improvement)


@router.callback_query(SurveyStates.waiting_love_place)
async def process_love_place(callback: CallbackQuery, state: FSMContext):
    """Обработка места знакомства"""
    place = callback.data.replace("survey_", "")
    await state.update_data(q1_details=place)
    await ask_question2(callback.message, state)


@router.message(SurveyStates.waiting_expectations)
async def process_expectations(message: Message, state: FSMContext):
    """Обработка ожиданий"""
    await state.update_data(q1_details=message.text)
    await ask_question2(message, state)


@router.message(SurveyStates.waiting_threat_details)
async def process_threat_details(message: Message, state: FSMContext):
    """Обработка деталей угроз"""
    await state.update_data(q1_details=message.text)
    await ask_question2(message, state)


@router.message(SurveyStates.waiting_info_request)
async def process_info_request(message: Message, state: FSMContext):
    """Обработка запроса информации"""
    await state.update_data(q1_details=message.text)
    await ask_question2(message, state)


@router.message(SurveyStates.waiting_dislike_details)
async def process_dislike_details(message: Message, state: FSMContext):
    """Обработка причин недовольства"""
    await state.update_data(q1_details=message.text)
    await ask_question2(message, state)


@router.message(SurveyStates.waiting_other_details)
async def process_other_details(message: Message, state: FSMContext):
    """Обработка других причин"""
    await state.update_data(q1_details=message.text)
    await ask_question2(message, state)


@router.callback_query(SurveyStates.waiting_improvement)
async def process_improvement(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 2"""
    improvement = callback.data.replace("survey_", "")
    await state.update_data(q2=improvement)
    
    # Вопрос 3
    options = [
        "Нет", "Конфликт", "Нашел любовь",
        "Цифровой детокс", "Ушел в другой чат", "Другое"
    ]
    
    await callback.message.edit_text(
        "3 Было ли какое-то конкретное событие, после которого ты решил выйти?",
        reply_markup=create_survey_keyboard(options)
    )
    await state.set_state(SurveyStates.waiting_event)


@router.callback_query(SurveyStates.waiting_event)
async def process_event(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 3"""
    event = callback.data.replace("survey_", "")
    await state.update_data(q3=event)
    
    # Вопрос 4
    await callback.message.edit_text(
        "4 Какие были ожидания при вступлении в чат?"
    )
    await state.set_state(SurveyStates.waiting_q4)


@router.message(SurveyStates.waiting_q4)
async def process_q4(message: Message, state: FSMContext):
    """Обработка ответа на вопрос 4"""
    await state.update_data(q4=message.text)
    
    # Вопрос 5
    text = (
        "5 Ты уверен, что хочешь лишить себя:\n"
        "• Дополнительного инструмента для поиска парня или друзей?\n"
        "• Проведения офлайн досугов с чатланами?\n"
        "• Доступа к консультациям равного консультанта по теме?\n"
        "• Общения?"
    )
    
    await message.answer(
        text,
        reply_markup=create_return_chat_keyboard()
    )
    await state.set_state(SurveyStates.waiting_q5)


@router.callback_query(SurveyStates.waiting_q5, F.data == "return_to_chat")
async def return_from_survey(callback: CallbackQuery, state: FSMContext):
    """Возврат в чат из опроса"""
    await return_to_chat(callback, state)


@router.callback_query(SurveyStates.waiting_q5, F.data == "continue_survey")
async def continue_from_q5(callback: CallbackQuery, state: FSMContext):
    """Продолжение после вопроса 5 (завершение)"""
    await callback.answer()
    
    data = await state.get_data()
    
    # Сохраняем результаты опроса
    await save_survey_result(callback.from_user.id, data)
    
    await callback.message.edit_text(
        "Спасибо за обратную связь! Это поможет нам стать лучше."
    )
    await state.clear()


@router.callback_query(SurveyStates.waiting_q5, F.data == "decline_survey")
async def decline_from_q5(callback: CallbackQuery, state: FSMContext):
    """Отказ на вопросе 5"""
    await decline_survey(callback, state)