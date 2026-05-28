"""
Handler для регистрации пользователей
Реализует п.1 ТЗ - Регистрация с блокировкой несовершеннолетних
"""
import logging
import json
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatType

from constants import Messages, RegistrationStates, CallbackData, UserStatus
from utils.keyboards import (
    create_age_confirm_keyboard,
    create_rules_keyboard,
    create_submit_application_keyboard,
    create_skip_keyboard,
    create_app_review_keyboard,
    create_admin_reply_keyboard,
    create_owner_reply_keyboard,
    create_main_menu_keyboard
)
from database import get_user, create_user, update_user, create_application, get_all_admins, get_new_applications
from utils.formatters import format_application_text
from config import OWNER_ID, CHAT_ID


def _user_workspace_id(user_id: int) -> int | None:
    """Этап B B4 (V1.17.0O5): резолвит workspace_id для юзера через членство.

    None → caller использует legacy ws=1 fallback (для PositivЭ работает).
    Для multi-ws: юзер-член ws=N → его регистрация и проверка членства
    идут в этот ws.
    """
    try:
        import sqlite3, os
        from bot_core.ws_resolver import resolve_user_primary_workspace
        db_path = os.getenv('DB_PATH', 'database/bot_database.db')
        conn = sqlite3.connect(db_path)
        try:
            return resolve_user_primary_workspace(conn, user_id)
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"_user_workspace_id fallback: {e}")
    return None


def _user_main_chat(user_id: int, fallback: int) -> int:
    """Main_chat workspace юзера. Fallback на CHAT_ID если ws не найден.

    V1.17.0O5: для регистрации/инвайтов — определяем чат куда юзер должен
    войти после одобрения заявки.
    """
    try:
        import sqlite3, os
        from bot_core.ws_resolver import resolve_user_primary_workspace, resolve_role_chat
        db_path = os.getenv('DB_PATH', 'database/bot_database.db')
        conn = sqlite3.connect(db_path)
        try:
            ws_id = resolve_user_primary_workspace(conn, user_id)
            if ws_id is not None:
                main_chat = resolve_role_chat(conn, ws_id, 'main')
                if main_chat:
                    return main_chat
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"_user_main_chat fallback: {e}")
    return fallback
from handlers.reminder import save_questionnaire_state, clear_questionnaire_state

logger = logging.getLogger(__name__)
router = Router()


def calculate_age_from_birth_date(birth_date_str: str) -> int:
    """Расчет возраста по дате рождения"""
    try:
        birth_date = datetime.strptime(birth_date_str, "%d.%m.%Y").date()
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age
    except Exception as e:
        logger.error(f"Error calculating age: {e}")
        return 0


def calculate_unlock_date(birth_date_str: str) -> str:
    """Расчет даты, когда пользователю исполнится 18 лет"""
    birth_date = datetime.strptime(birth_date_str, "%d.%m.%Y").date()
    unlock_date = birth_date + relativedelta(years=18)
    return unlock_date.strftime("%d.%m.%Y")


async def submit_application(message_or_callback, state: FSMContext, data: dict, is_callback: bool = False):
    """Общая функция для отправки заявки"""
    
    # Проверяем, что все необходимые данные есть
    required_fields = ['name', 'age', 'city', 'therapy']
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        logger.error(f"Missing fields: {missing_fields}")
        error_text = "❌ Произошла ошибка. Пожалуйста, начните регистрацию заново с команды /start"
        
        if is_callback:
            await message_or_callback.edit_text(error_text)
        else:
            await message_or_callback.answer(error_text)
            
        await state.clear()
        return

    # Определяем user_id и bot для отправки
    if is_callback:
        user_id = message_or_callback.chat.id
        bot = message_or_callback.bot
        full_name = message_or_callback.chat.full_name
        username = message_or_callback.chat.username
    else:
        user_id = message_or_callback.from_user.id
        bot = message_or_callback.bot
        full_name = message_or_callback.from_user.full_name
        username = message_or_callback.from_user.username

    # Сохраняем данные в БД
    update_data = {
        'q_name': data.get('name'),
        'q_age': data.get('age'),
        'q_city': data.get('city'),
        'q_therapy': data.get('therapy'),
        'invite_link': data.get('ref_code')
    }
    
    # Добавляем birth_date только если он есть
    if data.get('birth_date'):
        update_data['birth_date'] = data.get('birth_date')
    
    await update_user(user_id, **update_data)

    # Создаем заявку (Этап B B4: per-ws)
    app_id = await create_application(user_id, workspace_id=_user_workspace_id(user_id))

    # ============================================
    # РАССЫЛАЕМ УВЕДОМЛЕНИЯ - ИСПРАВЛЕНО: владелец получает 1 уведомление
    # ============================================
    
    # Формируем короткое уведомление (без полной анкеты)
    notification_text = (
        f"📢 **Новая заявка** #{app_id}\n\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 ID: {user_id}\n\n"
        f"Нажмите кнопку 'Новые заявки' в панели для просмотра."
    )
    
    # Отправляем владельцу
    try:
        await bot.send_message(
            OWNER_ID,
            notification_text,
            reply_markup=create_app_review_keyboard(app_id),
            parse_mode="Markdown"
        )
        logger.info(f"Push notification sent to owner for application {app_id}")
    except Exception as e:
        logger.error(f"Failed to send push notification to owner: {e}")
    
    # Отправляем всем администраторам, КРОМЕ ВЛАДЕЛЬЦА
    admins = await get_all_admins()
    for admin in admins:
        # Пропускаем владельца, чтобы не дублировать
        if admin['tg_id'] == OWNER_ID:
            continue
            
        try:
            await bot.send_message(
                admin['tg_id'],
                notification_text,
                reply_markup=create_app_review_keyboard(app_id),
                parse_mode="Markdown"
            )
            logger.info(f"Push notification sent to admin {admin['tg_id']}")
        except Exception as e:
            logger.error(f"Failed to send push notification to admin {admin['tg_id']}: {e}")

    # Сообщение пользователю
    success_text = "✅ Спасибо! Ваша заявка принята и находится на рассмотрении у администраторов. Мы сообщим вам о результате."
    
    if is_callback:
        await message_or_callback.edit_text(success_text)
    else:
        await message_or_callback.answer(success_text)
    
    # Очищаем состояние анкеты
    if is_callback:
        await clear_questionnaire_state(message_or_callback.chat.id)
    else:
        await clear_questionnaire_state(message_or_callback.from_user.id)
    
    await state.clear()


@router.message(Command("start"))
async def cmd_start(message: Message):
    user = await get_user(message.from_user.id)
    if user and user.get('q_name'):
        # Если уже зарегистрирован — показывай СВОЁ старое меню
        await message.answer("С возвращением! Вот твое меню...")
    else:
        # Если новый — запускай логику регистрации друга
        await message.answer("Привет! Давай заполним анкету. Как тебя зовут?")
        # Тут вызывай функции друга для создания юзера (create_user)
    
    # Очищаем предыдущее состояние
    await state.clear()
    
    # Очищаем сохраненное состояние в БД
    await clear_questionnaire_state(user_id)

    user = await get_user(user_id)

    # Проверяем, заблокирован ли пользователь
    if user and user.get('blocked_until'):
        try:
            blocked_until = datetime.strptime(user['blocked_until'], "%d.%m.%Y").date()
            today = date.today()
            
            if today < blocked_until:
                # Все еще заблокирован
                days_left = (blocked_until - today).days
                await message.answer(
                    f"⛔ Ваш доступ ограничен до {user['blocked_until']}.\n"
                    f"Осталось дней: {days_left}\n\n"
                    f"Мы уведомим вас, когда вам исполнится 18 лет."
                )
                return
            else:
                # Срок блокировки истек - разблокируем
                logger.info(f"User {user_id} automatically unblocked")
                await update_user(
                    user_id,
                    blocked_until=None,
                    status=UserStatus.NOT_IN_CHAT
                )
                # Продолжаем регистрацию
        except Exception as e:
            logger.error(f"Error checking blocked status: {e}")

    # Проверяем через API, действительно ли пользователь в чате (B4: per-ws main)
    is_actually_in_chat = False
    _check_chat = _user_main_chat(user_id, CHAT_ID)
    if _check_chat:
        try:
            chat_member = await message.bot.get_chat_member(_check_chat, user_id)
            is_actually_in_chat = chat_member.status in ['member', 'administrator', 'creator']
            logger.info(f"User {user_id} actual chat status: {chat_member.status} -> in_chat: {is_actually_in_chat} (ws-chat={_check_chat})")
        except Exception as e:
            logger.error(f"Error checking chat member for user {user_id}: {e}")

    # Если пользователь в БД как in_chat, но реально не в чате - исправляем статус
    if user and user.get('status') == UserStatus.IN_CHAT and not is_actually_in_chat:
        logger.info(f"User {user_id} has wrong status in DB (IN_CHAT but not in chat), fixing...")
        await update_user(user_id, status=UserStatus.NOT_IN_CHAT)
        user['status'] = UserStatus.NOT_IN_CHAT

    # Определяем финальный статус для логики приглашения
    is_in_chat = user and user.get('status') == UserStatus.IN_CHAT and is_actually_in_chat

    # Если пользователь действительно в чате - только приглашение друзей
    if is_in_chat:
        await message.answer(
            Messages.INVITE_FRIENDS.format(name=message.from_user.first_name)
        )
        return

    # Проверяем, есть ли уже активная заявка у пользователя
    active_applications = await get_new_applications(exclude_locked=True)
    has_active_application = any(app['user_id'] == user_id for app in active_applications)
    
    if has_active_application:
        # Получаем имя из анкеты или используем имя из Telegram
        user_name = user.get('q_name') if user and user.get('q_name') else message.from_user.first_name
        
        # Сообщение о том, что заявка уже на рассмотрении
        await message.answer(
            f"{user_name}, ты уже подал заявку на вступление и она уже на рассмотрении. Немного терпения, наши администраторы обязательно обработают ее, а пока ты можешь отправить нашего бота @Pulse_4ever_Bot своим друзьям или знакомым со \"статусом\"."
        )
        return

    # Если пользователя нет в БД - создаем
    if not user:
        await create_user(
            tg_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

    # Если пользователь не в чате, не заблокирован и нет активной заявки - запускаем регистрацию
    await message.answer(
        Messages.WELCOME.format(name=message.from_user.first_name),
        reply_markup=create_age_confirm_keyboard()
    )
    await state.set_state(RegistrationStates.WAITING_AGE_CONFIRM)


@router.callback_query(F.data == CallbackData.AGE_CONFIRM, F.message.chat.type == ChatType.PRIVATE)
async def process_age_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение возраста - показываем правила"""
    logger.info(f"Age confirm from user {callback.from_user.id}")
    
    await callback.answer()
    
    # Сохраняем состояние
    current_state = await state.get_state()
    if current_state:
        await save_questionnaire_state(
            callback.from_user.id, 
            {"state": current_state, "data": await state.get_data()}
        )
    
    await callback.message.delete()
    await callback.message.answer(
        Messages.RULES,
        reply_markup=create_rules_keyboard()
    )
    await state.set_state(RegistrationStates.WAITING_RULES_ACCEPT)


@router.callback_query(F.data == CallbackData.RULES_ACCEPT, F.message.chat.type == ChatType.PRIVATE)
async def process_rules_accept(callback: CallbackQuery, state: FSMContext):
    """Принятие правил - после правил показываем кнопку подачи заявки"""
    logger.info(f"Rules accept from user {callback.from_user.id}")
    
    await callback.answer()
    
    # Сохраняем состояние
    current_state = await state.get_state()
    if current_state:
        await save_questionnaire_state(
            callback.from_user.id,
            {"state": current_state, "data": await state.get_data()}
        )
    
    await callback.message.delete()
    await callback.message.answer(
        "✅ Правила приняты! Теперь вы можете подать заявку.",
        reply_markup=create_submit_application_keyboard()
    )
    await state.set_state(RegistrationStates.WAITING_APPLY)


@router.callback_query(F.data == CallbackData.SUBMIT_APP, F.message.chat.type == ChatType.PRIVATE)
async def process_submit_application(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Подать заявку' - начало анкеты"""
    logger.info(f"Submit application from user {callback.from_user.id}")
    
    # Дополнительная проверка на наличие активной заявки
    user_id = callback.from_user.id
    active_applications = await get_new_applications(exclude_locked=True)
    has_active_application = any(app['user_id'] == user_id for app in active_applications)
    
    if has_active_application:
        user = await get_user(user_id)
        user_name = user.get('q_name') if user and user.get('q_name') else callback.from_user.first_name
        
        await callback.answer()
        await callback.message.delete()
        await callback.message.answer(
            f"{user_name}, ты уже подал заявку на вступление и она уже на рассмотрении. Немного терпения, наши администраторы обязательно обработают ее, а пока ты можешь отправить нашего бота @Pulse_4ever_Bot своим друзьям или знакомым со \"статусом\"."
        )
        return
    
    await callback.answer()
    
    # Сохраняем состояние
    await save_questionnaire_state(
        callback.from_user.id,
        {"state": RegistrationStates.WAITING_NAME, "data": {}}
    )
    
    await callback.message.delete()
    await callback.message.answer(Messages.Q_NAME)
    await state.set_state(RegistrationStates.WAITING_NAME)


@router.message(F.chat.type == ChatType.PRIVATE, StateFilter(RegistrationStates.WAITING_NAME))
async def process_name(message: Message, state: FSMContext):
    """Обработка имени"""
    logger.info(f"Name input from user {message.from_user.id}: {message.text}")

    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Пожалуйста, введите корректное имя (минимум 2 символа).")
        return

    await state.update_data(name=message.text.strip())
    
    # Сохраняем состояние
    current_state = await state.get_state()
    await save_questionnaire_state(
        message.from_user.id,
        {"state": current_state, "data": await state.get_data()}
    )
    
    await message.answer(Messages.Q_AGE)
    await state.set_state(RegistrationStates.WAITING_AGE)


@router.message(F.chat.type == ChatType.PRIVATE, StateFilter(RegistrationStates.WAITING_AGE))
async def process_age(message: Message, state: FSMContext):
    """Обработка возраста"""
    logger.info(f"Age input from user {message.from_user.id}: {message.text}")

    if not message.text or not message.text.isdigit():
        await message.answer("Пожалуйста, введите число (ваш возраст).")
        return

    age = int(message.text)
    if age < 1 or age > 120:
        await message.answer("Пожалуйста, введите корректный возраст (от 1 до 120).")
        return

    await state.update_data(age=age)
    
    # Сохраняем состояние
    current_state = await state.get_state()
    await save_questionnaire_state(
        message.from_user.id,
        {"state": current_state, "data": await state.get_data()}
    )

    if age < 18:
        await message.answer(Messages.Q_BIRTH_DATE)
        await state.set_state(RegistrationStates.WAITING_BIRTH_DATE)
    else:
        await message.answer(Messages.Q_CITY)
        await state.set_state(RegistrationStates.WAITING_CITY)


@router.message(F.chat.type == ChatType.PRIVATE, StateFilter(RegistrationStates.WAITING_BIRTH_DATE))
async def process_birth_date(message: Message, state: FSMContext):
    """Обработка даты рождения для несовершеннолетних - БЛОКИРОВКА"""
    logger.info(f"Birth date input from user {message.from_user.id}: {message.text}")

    date_text = message.text.strip()
    if len(date_text) == 10 and date_text[2] == '.' and date_text[5] == '.':
        day, month, year = date_text.split('.')
        if day.isdigit() and month.isdigit() and year.isdigit():
            try:
                birth_date = datetime.strptime(date_text, "%d.%m.%Y").date()
                today = date.today()
                
                if birth_date > today:
                    await message.answer("❌ Дата рождения не может быть в будущем. Пожалуйста, введите корректную дату.")
                    return
                
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                
                if age >= 18:
                    logger.info(f"User {message.from_user.id} claimed age <18 but birth date shows age {age}")
                    await message.answer("✅ Согласно введенной дате, вам уже есть 18 лет. Продолжаем регистрацию.")
                    await state.update_data(age=age, birth_date=date_text)
                    
                    # Сохраняем состояние
                    current_state = await state.get_state()
                    await save_questionnaire_state(
                        message.from_user.id,
                        {"state": current_state, "data": await state.get_data()}
                    )
                    
                    await message.answer(Messages.Q_CITY)
                    await state.set_state(RegistrationStates.WAITING_CITY)
                    return
                
                unlock_date = birth_date + relativedelta(years=18)
                days_until_unlock = (unlock_date - today).days
                unlock_date_str = unlock_date.strftime("%d.%m.%Y")
                
                await state.update_data(birth_date=date_text)
                
                await update_user(
                    message.from_user.id,
                    birth_date=date_text,
                    blocked_until=unlock_date_str,
                    status=UserStatus.BLOCKED
                )
                
                await message.answer(
                    f"⛔ Доступ в чат разрешен только лицам старше 18 лет.\n\n"
                    f"📅 Ваша дата рождения: {date_text}\n"
                    f"🔓 Доступ будет разблокирован: {unlock_date_str}\n"
                    f"📆 Осталось дней: {days_until_unlock}\n\n"
                    f"Мы уведомим вас, когда вам исполнится 18 лет."
                )
                
                await state.clear()
                await clear_questionnaire_state(message.from_user.id)
                return
                
            except ValueError as e:
                logger.error(f"Date parsing error: {e}")
                await message.answer("❌ Пожалуйста, введите корректную дату в формате ДД.ММ.ГГГГ")
                return

    await message.answer("❌ Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например, 15.05.2010)")


@router.message(F.chat.type == ChatType.PRIVATE, StateFilter(RegistrationStates.WAITING_CITY))
async def process_city(message: Message, state: FSMContext):
    """Обработка города"""
    logger.info(f"City input from user {message.from_user.id}: {message.text}")

    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Пожалуйста, введите название города (минимум 2 символа).")
        return

    await state.update_data(city=message.text.strip())
    
    # Сохраняем состояние
    current_state = await state.get_state()
    await save_questionnaire_state(
        message.from_user.id,
        {"state": current_state, "data": await state.get_data()}
    )
    
    await message.answer(Messages.Q_THERAPY)
    await state.set_state(RegistrationStates.WAITING_THERAPY)


@router.message(F.chat.type == ChatType.PRIVATE, StateFilter(RegistrationStates.WAITING_THERAPY))
async def process_therapy(message: Message, state: FSMContext):
    """Обработка терапии"""
    logger.info(f"Therapy input from user {message.from_user.id}: {message.text}")

    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Пожалуйста, укажите принимаемую терапию (минимум 2 символа).")
        return

    await state.update_data(therapy=message.text.strip())
    
    # Сохраняем состояние
    current_state = await state.get_state()
    await save_questionnaire_state(
        message.from_user.id,
        {"state": current_state, "data": await state.get_data()}
    )

    await message.answer(
        Messages.Q_REF_CODE,
        reply_markup=create_skip_keyboard()
    )
    await state.set_state(RegistrationStates.WAITING_REF_CODE)


@router.message(F.chat.type == ChatType.PRIVATE, StateFilter(RegistrationStates.WAITING_REF_CODE))
async def process_ref_code(message: Message, state: FSMContext):
    """Обработка реферального кода - сразу отправляем заявку"""
    logger.info(f"Ref code input from user {message.from_user.id}: {message.text}")
    
    # Сохраняем реферальный код
    await state.update_data(ref_code=message.text.strip())
    
    # Получаем все данные
    data = await state.get_data()
    
    # Отправляем заявку
    await submit_application(message, state, data, is_callback=False)


@router.callback_query(F.data == "skip_ref_code", F.message.chat.type == ChatType.PRIVATE)
async def skip_ref_code(callback: CallbackQuery, state: FSMContext):
    """Пропуск реферального кода - сразу отправляем заявку"""
    logger.info(f"Skip ref code from user {callback.from_user.id}")
    
    await callback.answer()
    await callback.message.delete()
    
    await state.update_data(ref_code=None)
    data = await state.get_data()
    await submit_application(callback.message, state, data, is_callback=True)


@router.message(Command("skip"), F.chat.type == ChatType.PRIVATE)
async def cmd_skip(message: Message, state: FSMContext):
    """Обработка команды /skip"""
    current_state = await state.get_state()

    if current_state == RegistrationStates.WAITING_REF_CODE:
        await state.update_data(ref_code=None)
        data = await state.get_data()
        await submit_application(message, state, data, is_callback=False)
    else:
        await message.answer("Эта команда сейчас не нужна.")


@router.callback_query(F.data == "main_menu_fill_application", F.message.chat.type == ChatType.PRIVATE)
async def main_menu_fill_application(callback: CallbackQuery, state: FSMContext):
    """Начать заполнение новой анкеты (при уже существующей)"""
    logger.info(f"Main menu: fill new application from user {callback.from_user.id}")
    await callback.answer()
    
    await update_user(
        callback.from_user.id,
        q_name=None,
        q_age=None,
        q_city=None,
        q_therapy=None,
        birth_date=None
    )
    
    await callback.message.edit_text(
        "📝 Заполнение новой анкеты.\n\n"
        f"{Messages.Q_NAME}"
    )
    await state.set_state(RegistrationStates.WAITING_NAME)


@router.callback_query(F.data == "main_menu_edit_profile", F.message.chat.type == ChatType.PRIVATE)
async def main_menu_edit_profile(callback: CallbackQuery):
    """Редактировать существующую анкету"""
    logger.info(f"Main menu: edit profile from user {callback.from_user.id}")
    await callback.answer()
    
    user = await get_user(callback.from_user.id)
    
    text = "📋 **Ваша текущая анкета:**\n\n"
    text += f"Имя: {user.get('q_name', '—')}\n"
    text += f"Возраст: {user.get('q_age', '—')}\n"
    text += f"Город: {user.get('q_city', '—')}\n"
    text += f"Терапия: {user.get('q_therapy', '—')}\n"
    
    if user.get('birth_date'):
        text += f"Дата рождения: {user['birth_date']}\n"
    
    text += "\n🚧 Функция редактирования находится в разработке."
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "main_menu_check_status", F.message.chat.type == ChatType.PRIVATE)
async def main_menu_check_status(callback: CallbackQuery):
    """Проверить статус заявки"""
    logger.info(f"Main menu: check status from user {callback.from_user.id}")
    await callback.answer()
    
    user_id = callback.from_user.id
    
    from database import is_blacklisted, get_blacklist_reason
    
    applications = await get_new_applications(exclude_locked=True)
    active_app = next((app for app in applications if app['user_id'] == user_id), None)
    
    if active_app:
        await callback.message.edit_text(
            "📋 Ваша заявка находится на рассмотрении.\n\n"
            "Ожидайте решения администраторов. Мы сообщим вам о результате."
        )
    else:
        if await is_blacklisted(user_id):
            reason = await get_blacklist_reason(user_id)
            await callback.message.edit_text(
                f"⛔ Вы находитесь в черном списке.\n\n"
                f"Причина: {reason}"
            )
        else:
            is_in_chat = False
            # B4: per-ws main chat
            _check_chat = _user_main_chat(user_id, CHAT_ID)
            if _check_chat:
                try:
                    chat_member = await callback.bot.get_chat_member(_check_chat, user_id)
                    is_in_chat = chat_member.status in ['member', 'administrator', 'creator']
                except Exception:
                    pass
            
            if is_in_chat:
                await callback.message.edit_text(
                    "✅ Вы уже в чате PositivЭ!\n\n"
                    "Приглашайте друзей и общайтесь!"
                )
            else:
                await callback.message.edit_text(
                    "❌ У вас нет активных заявок.\n\n"
                    "Нажмите /start, чтобы начать регистрацию."
                )


@router.message(F.chat.type != ChatType.PRIVATE)
async def ignore_group_messages(message: Message):
    """Игнорируем все сообщения в групповых чатах"""
    logger.info(f"Ignoring group message from user {message.from_user.id} in chat {message.chat.id}")


@router.callback_query(F.message.chat.type == ChatType.PRIVATE)
async def catch_all_callback(callback: CallbackQuery):
    """Отлов необработанных callback-запросов"""
    callback_data = callback.data
    
    if callback_data and (
        callback_data.startswith('app_') or 
        callback_data.startswith('admin_') or 
        callback_data.startswith('owner_') or
        callback_data.startswith('main_menu_') or
        callback_data == "continue_questionnaire"
    ):
        logger.info(f"Пропускаем callback: {callback_data}")
        return
    
    logger.warning(f"Unhandled callback query: {callback_data} from user {callback.from_user.id}")
    try:
        await callback.answer("Эта кнопка пока не работает.", show_alert=True)
    except Exception as e:
        logger.error(f"Error answering callback: {e}")


@router.message(F.chat.type == ChatType.PRIVATE)
async def catch_all_messages(message: Message, state: FSMContext):
    """Отлов необработанных сообщений в ЛС"""
    from database import is_admin
    from config import OWNER_ID
    
    current_state = await state.get_state()
    logger.warning(f"Unhandled message from user {message.from_user.id} in state {current_state}: {message.text}")

    user_id = message.from_user.id
    is_admin_user = await is_admin(user_id)
    is_owner = (user_id == OWNER_ID)
    
    if current_state:
        await message.answer(
            "Пожалуйста, продолжайте заполнение анкеты или используйте кнопки."
        )
    else:
        if is_owner:
            await message.answer(
                "👑 **Панель владельца**\n\n"
                "Кнопки управления всегда доступны внизу экрана:",
                reply_markup=create_owner_reply_keyboard(),
                parse_mode="Markdown"
            )
        elif is_admin_user:
            await message.answer(
                "👨‍💼 **Панель администратора**\n\n"
                "Кнопки управления всегда доступны внизу экрана:",
                reply_markup=create_admin_reply_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "👋 Используйте команду /start для начала регистрации в чат PULSE 4ever."
            )