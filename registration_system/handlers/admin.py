"""
Handler для работы администраторов с заявками
Реализует п.3 ТЗ - Работа с заявками
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType
from datetime import datetime

from database import (
    get_user, is_admin, get_new_applications, get_application,
    lock_application, approve_application, reject_application,
    update_user, create_invite_link, get_setting, get_all_admins,
    get_blacklist_count, get_blacklist_with_users
)
from constants import Messages, Buttons, UserStatus, UserRole
from utils.keyboards import (
    create_app_review_keyboard,
    create_admin_reply_keyboard,
    create_owner_panel_keyboard,
    create_submit_application_keyboard,
    create_application_navigation_keyboard,
    create_dm_keyboard,
    create_owner_reply_keyboard,
    create_blacklist_management_keyboard
)
from utils.journal import send_to_journal
from config import OWNER_ID, CHAT_ID

import logging
logger = logging.getLogger(__name__)

# Создаем router
router = Router()


class RejectionStates(StatesGroup):
    """Состояния для отклонения заявки"""
    waiting_reason = State()


@router.message(Command("admin_panel"), F.chat.type == ChatType.PRIVATE)
async def admin_panel(message: Message):
    """Панель администратора - только в ЛС"""
    user_id = message.from_user.id
    
    # Проверяем права
    if user_id != OWNER_ID and not await is_admin(user_id):
        await message.answer("❌ У вас нет доступа к административной панели.")
        return
    
    # Для владельца показываем расширенную панель
    if user_id == OWNER_ID:
        await message.answer(
            "👑 **Панель владельца**\n\n"
            "Кнопки управления всегда доступны внизу экрана:",
            reply_markup=create_owner_reply_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "👨‍💼 **Панель администратора**\n\n"
            "Кнопки управления всегда доступны внизу экрана:",
            reply_markup=create_admin_reply_keyboard(),
            parse_mode="Markdown"
        )


@router.message(Command("export_chat"), F.chat.type.in_({'group', 'supergroup'}))
async def export_chat_members(message: Message):
    """Экспорт участников чата через получение списка администраторов и недавних участников"""
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Только владелец может использовать эту команду.")
        return
    
    await message.answer(
        "⚠️ **Telegram Bot API не позволяет получить полный список участников чата.**\n\n"
        "Чтобы синхронизировать обычных пользователей, попросите их:\n"
        "1️⃣ Написать любое сообщение в этот чат\n"
        "2️⃣ Или написать боту в личку /start\n\n"
        "После этого они будут автоматически синхронизированы и при /start "
        "увидят приглашение друзей, а не регистрацию.",
        parse_mode="Markdown"
    )


# ==================== ОБРАБОТЧИКИ REPLY-КНОПОК ====================

@router.message(F.text == Buttons.NEW_APPLICATIONS, F.chat.type == ChatType.PRIVATE)
async def handle_new_applications_button(message: Message):
    """Обработка нажатия на кнопку 'Новые заявки'"""
    admin_id = message.from_user.id
    logger.info(f"Admin {admin_id} clicked NEW_APPLICATIONS button")
    
    # Проверяем права
    if admin_id != OWNER_ID and not await is_admin(admin_id):
        await message.answer("❌ У вас нет доступа.")
        return
    
    # Получаем новые заявки (исключая заблокированные)
    applications = await get_new_applications(exclude_locked=True)
    
    if not applications:
        await message.answer(
            "📭 **Новых заявок на данный момент нет.**",
            parse_mode="Markdown"
        )
        return
    
    # Сохраняем список заявок в данных пользователя для навигации
    app_ids = [app['id'] for app in applications]
    current_index = 0
    
    # Показываем первую заявку
    await show_application(message, applications[0], admin_id, app_ids, current_index)


@router.message(F.text == Buttons.ADMINS, F.chat.type == ChatType.PRIVATE)
async def handle_admins_button(message: Message):
    """Обработка нажатия на кнопку 'Админы'"""
    admin_id = message.from_user.id
    logger.info(f"Admin {admin_id} clicked ADMINS button")
    
    if admin_id != OWNER_ID and not await is_admin(admin_id):
        await message.answer("❌ У вас нет доступа.")
        return
    
    # Получаем список всех админов
    admins = await get_all_admins()
    
    if not admins:
        await message.answer("📭 Список администраторов пуст.")
        return
    
    text = "👤 **Список администраторов:**\n\n"
    for admin in admins:
        username = f"@{admin['username']}" if admin.get('username') else "нет username"
        text += f"• {admin.get('first_name', '')} {admin.get('last_name', '')}\n"
        text += f"  ID: `{admin['tg_id']}`\n"
        text += f"  Ник: {username}\n\n"
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == Buttons.BLACKLIST, F.chat.type == ChatType.PRIVATE)
async def handle_blacklist_button(message: Message):
    """Обработка нажатия на кнопку 'Черный список'"""
    admin_id = message.from_user.id
    logger.info(f"Admin {admin_id} clicked BLACKLIST button")
    
    # Проверяем права
    if admin_id != OWNER_ID and not await is_admin(admin_id):
        await message.answer("❌ У вас нет доступа.")
        return
    
    # Для владельца открываем панель управления черным списком
    if admin_id == OWNER_ID:
        count = await get_blacklist_count()
        
        await message.answer(
            f"🚫 **Управление черным списком**\n\n"
            f"Всего заблокировано: {count}\n\n"
            f"Выберите действие:",
            reply_markup=create_blacklist_management_keyboard(),
            parse_mode="Markdown"
        )
        return
    
    # Для обычных администраторов - только просмотр
    count = await get_blacklist_count()
    
    if count == 0:
        await message.answer(
            "📭 **Черный список пуст**\n\n"
            "Нет заблокированных пользователей.",
            parse_mode="Markdown"
        )
        return
    
    # Получаем список заблокированных (без пагинации для админов, только первые 10)
    blacklist = await get_blacklist_with_users()
    
    # Формируем текст
    text = f"🚫 **Черный список** (всего: {count})\n\n"
    
    # Показываем максимум 10 записей для админов
    for i, item in enumerate(blacklist[:10], 1):
        user = item['user']
        ban_date = datetime.fromisoformat(item['created_at']).strftime('%d.%m.%Y')
        
        full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        if not full_name:
            full_name = "Без имени"
        
        username = f"@{user.get('username')}" if user.get('username') else "нет username"
        
        text += (
            f"{i}. **{full_name}**\n"
            f"   📱 {username}\n"
            f"   🆔 `{item['tg_id']}`\n"
            f"   📅 {ban_date}\n"
            f"   📝 {item['reason']}\n\n"
        )
    
    if count > 10:
        text += f"_Показано 10 из {count} записей._"
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == Buttons.CHECK_USER, F.chat.type == ChatType.PRIVATE)
async def handle_check_user_button(message: Message):
    """Обработка нажатия на кнопку 'Проверка ника'"""
    admin_id = message.from_user.id
    logger.info(f"Admin {admin_id} clicked CHECK_USER button")
    
    if admin_id != OWNER_ID and not await is_admin(admin_id):
        await message.answer("❌ У вас нет доступа.")
        return
    
    await message.answer(
        "🔍 **Проверка пользователя**\n\n"
        "Введите ID пользователя в формате #userXXXXXXXXX или @username:",
        parse_mode="Markdown"
    )
    # TODO: реализовать FSM для проверки пользователя


@router.message(F.text == Buttons.TRIGGERS, F.chat.type == ChatType.PRIVATE)
async def handle_triggers_button(message: Message, state: FSMContext):
    """Обработка нажатия на кнопку 'Триггеры'"""
    admin_id = message.from_user.id
    logger.info(f"Admin {admin_id} clicked TRIGGERS button")

    if admin_id != OWNER_ID and not await is_admin(admin_id):
        await message.answer("❌ У вас нет доступа.")
        return

    from handlers.triggers import show_triggers_menu
    await show_triggers_menu(message, state)


@router.message(F.text == Buttons.JOURNAL, F.chat.type == ChatType.PRIVATE)
async def handle_journal_button(message: Message):
    """Обработка нажатия на кнопку 'Журнал' (п.5.1)"""
    from config import OWNER_ID as OID
    if message.from_user.id != OID:
        await message.answer("❌ Только для владельца.")
        return

    from utils.journal import get_journal_channel_id
    from utils.keyboards import create_journal_management_keyboard

    channel_id = await get_journal_channel_id()
    status = f"✅ Канал подключён (ID: `{channel_id}`)" if channel_id else "❌ Канал не подключён"

    await message.answer(
        f"📢 **Управление журналом**\n\n"
        f"{status}\n\n"
        f"Выберите действие:",
        reply_markup=create_journal_management_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == Buttons.STATISTICS, F.chat.type == ChatType.PRIVATE)
async def handle_statistics_button(message: Message):
    """
    Обработка кнопки 'Статистика' — п.4.5.
    Показывает список пользователей «Не в чате» с причинами БЗА / НПС.
    """
    from config import OWNER_ID as OID
    if message.from_user.id != OID:
        await message.answer("❌ Только для владельца.")
        return

    from database import get_users_with_incomplete_questionnaire, get_users_with_unused_link

    # БЗА — бросил заполнение (есть незаконченная анкета, любое время)
    bza_users = await get_users_with_incomplete_questionnaire(minutes=1)
    # НПС — не перешли по ссылке (ссылка выдана 1+ мин назад, ещё не вступили)
    nps_users = await get_users_with_unused_link(minutes=1)

    def _fmt_user(u: dict, reason: str) -> str:
        first = u.get('first_name', '')
        last = u.get('last_name', '')
        name = f"{first} {last}".strip() or "—"
        return f"{name}, #user{u['tg_id']}, {reason}"

    lines = ["📊 **Статистика — Не в чате**\n"]

    if bza_users or nps_users:
        seen = set()
        for u in bza_users:
            uid = u['tg_id']
            if uid not in seen:
                lines.append(_fmt_user(u, "БЗА"))
                seen.add(uid)
        for u in nps_users:
            uid = u['tg_id']
            if uid not in seen:
                lines.append(_fmt_user(u, "НПС"))
                seen.add(uid)
        lines.append(f"\n📌 БЗА — бросил заполнение")
        lines.append(f"📌 НПС — не перешли по ссылке")
    else:
        lines.append("✅ Нет пользователей вне чата с незавершённой регистрацией.")

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ==================== ОБРАБОТЧИКИ CALLBACK-КНОПОК ====================

@router.callback_query(F.data == "admin_apps")
async def show_new_applications(callback: CallbackQuery):
    """Показать новые заявки - работает для админов и владельца"""
    logger.info(f"🔥🔥🔥 admin_apps CALLBACK ПОЛУЧЕН в admin.py от пользователя {callback.from_user.id}")
    
    # Проверяем, что сообщение из личного чата
    if callback.message.chat.type != ChatType.PRIVATE:
        await callback.answer("Эта команда работает только в личных сообщениях", show_alert=True)
        return
    
    admin_id = callback.from_user.id
    logger.info(f"Admin {admin_id} requested new applications via callback")
    
    # Проверяем права
    if admin_id != OWNER_ID and not await is_admin(admin_id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Получаем новые заявки (исключая заблокированные)
    applications = await get_new_applications(exclude_locked=True)
    
    if not applications:
        await callback.message.edit_text(
            "📭 Новых заявок на данный момент нет.",
            reply_markup=None
        )
        await callback.answer()
        return
    
    # Сохраняем список заявок в данных пользователя для навигации
    app_ids = [app['id'] for app in applications]
    current_index = 0
    
    await callback.message.edit_text(
        f"📋 Найдено заявок: {len(app_ids)}\n"
        f"Показана заявка {current_index + 1} из {len(app_ids)}",
        reply_markup=None
    )
    
    # Показываем первую заявку
    await show_application(callback.message, applications[0], admin_id, app_ids, current_index)
    await callback.answer()


async def show_application(message: Message, app: dict, admin_id: int, app_ids: list, current_index: int):
    """Показать конкретную заявку (работает и с Message, и с CallbackQuery)"""
    
    # Блокируем заявку на 2 минуты
    locked = await lock_application(app['id'], admin_id, duration_minutes=2)
    
    if not locked:
        await message.answer(
            "⚠️ Эта заявка уже обрабатывается другим администратором.\n"
            "Попробуйте другую заявку."
        )
        # Показываем следующую заявку
        if current_index + 1 < len(app_ids):
            next_app = await get_application(app_ids[current_index + 1])
            if next_app:
                await show_application(message, next_app, admin_id, app_ids, current_index + 1)
        return
    
    # Получаем данные пользователя
    user = await get_user(app['user_id'])
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return
    
    user_dict = user
    
    # Формируем текст заявки согласно ТЗ (блоки A-Ж)
    is_returning = user_dict.get('last_exit_at') is not None
    status_tag = "#Возвращение" if is_returning else "#Новый"
    
    text = f"#Новая_заявка\n{status_tag}\n\n"
    
    # Блок В - базовая информация (отображаем только заполненные поля)
    # Имя пользователя - только если есть first_name или last_name
    user_name_parts = []
    if user_dict.get('first_name'):
        user_name_parts.append(user_dict['first_name'])
    if user_dict.get('last_name'):
        user_name_parts.append(user_dict['last_name'])
    
    if user_name_parts:
        text += f"👤 Пользователь: {' '.join(user_name_parts)}\n"
    
    if user_dict.get('username'):
        text += f"📱 @{user_dict['username']}\n"
    
    text += f"🆔 #user{user_dict['tg_id']}\n\n"
    text += f"📋 Анкета:\n"
    text += f"Имя: {user_dict.get('q_name', '—')}\n"
    text += f"Возраст: {user_dict.get('q_age', '—')}\n"
    text += f"Город: {user_dict.get('q_city', '—')}\n"
    text += f"Терапия: {user_dict.get('q_therapy', '—')}\n\n"
    
    if user_dict.get('birth_date'):
        text += f"📅 Дата рождения: {user_dict['birth_date']}\n"
    
    if user_dict.get('last_rejection_reason'):
        text += f"🚨 Внимание! Пользователь уже подавал заявку.\n"
        text += f"Причина отказа: {user_dict['last_rejection_reason']}\n\n"
    
    if app.get('created_at'):
        created = datetime.fromisoformat(app['created_at'])
        text += f"📅 Дата заявки: {created.strftime('%d.%m.%Y %H:%M')}\n"
    
    # Отправляем сообщение с инлайн-кнопками навигации
    await message.answer(
        text,
        reply_markup=create_application_navigation_keyboard(app['id'], app_ids, current_index)
    )


@router.callback_query(F.data.startswith("app_approve_"))
async def approve_app(callback: CallbackQuery):
    """Одобрение заявки - полная форма согласно ТЗ п.3.3.3"""
    logger.info(f"🔥🔥🔥 approve_app CALLBACK ПОЛУЧЕН в admin.py: {callback.data}")
    
    # Отвечаем на callback, чтобы убрать "часики"
    await callback.answer("⏳ Обрабатываю одобрение...")
    
    # Проверяем, что сообщение из личного чата
    if callback.message.chat.type != ChatType.PRIVATE:
        await callback.answer("Эта команда работает только в личных сообщениях", show_alert=True)
        return
    
    admin_id = callback.from_user.id
    app_id = int(callback.data.split("_")[2])
    admin_username = callback.from_user.username or str(admin_id)
    
    logger.info(f"Admin {admin_id} approving application {app_id}")
    
    if admin_id != OWNER_ID and not await is_admin(admin_id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    app = await get_application(app_id)
    if not app:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    user = await get_user(app['user_id'])
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    user_dict = user
    
    # Одобряем заявку
    await approve_application(app_id, admin_id)
    
    # Генерируем одноразовую ссылку
    invite_link = None
    invite_message_id = None
    try:
        chat_id = await get_setting("main_chat_id")
        if not chat_id:
            chat_id = CHAT_ID
        
        if chat_id:
            invite_link_obj = await callback.bot.create_chat_invite_link(
                chat_id=int(chat_id),
                creates_join_request=True,
                name=f"Invite_{user_dict['tg_id']}_{datetime.now().timestamp()}"
            )
            invite_link = invite_link_obj.invite_link
            
            await create_invite_link(user_dict['tg_id'], invite_link)
            
            # Отправляем пользователю АКТИВНУЮ ссылку для входа
            user_name = user_dict.get('q_name', user_dict.get('first_name', 'Пользователь'))
            msg = await callback.bot.send_message(
                user_dict['tg_id'],
                f"✨ {user_name}, ты на пороге входа в чат **Pulse 4ever**!\n\n"
                f"🔗 Твоя личная одноразовая ссылка:\n"
                f"{invite_link}\n\n"
                f"👉 Перейди по ссылке, чтобы вступить в чат.\n"
                f"Ссылка действует только один раз!",
                parse_mode="Markdown"
            )
            invite_message_id = msg.message_id
            
            # Сохраняем ссылку и ID сообщения
            await update_user(
                user_dict['tg_id'], 
                invite_link=invite_link,
                invite_message_id=invite_message_id
            )
            
        else:
            await callback.answer(
                "⚠️ ID чата не настроен. Используйте /set_chat",
                show_alert=True
            )
            return
        
    except Exception as e:
        logger.error(f"Error generating invite link: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
        return
    
    # ============================================
    # ФОРМИРУЕМ ПОЛНУЮ ФОРМУ ОДОБРЕНИЯ ПО ТЗ
    # ============================================
    
    # Определяем, новый пользователь или возвращается
    is_returning = user_dict.get('last_exit_at') is not None
    status_tag = "#Возвращение" if is_returning else "#Новый"
    
    # Форматируем дату заявки
    app_date = ""
    if app.get('created_at'):
        created = datetime.fromisoformat(app['created_at'])
        app_date = f"📅 {created.strftime('%d.%m.%Y %H:%M')}"
    
    # Блок А - хештег
    admin_text = f"#Одобрено\n"
    
    # Блок Б - статус пользователя
    admin_text += f"{status_tag}\n\n"
    
    # Заявка одобрена [@username администратора]
    admin_text += f"Заявка одобрена @{admin_username}\n\n"
    
    # Блок В - базовая информация (отображаем только заполненные поля)
    user_name_parts = []
    if user_dict.get('first_name'):
        user_name_parts.append(user_dict['first_name'])
    if user_dict.get('last_name'):
        user_name_parts.append(user_dict['last_name'])
    
    if user_name_parts:
        admin_text += f"👤 Пользователь: {' '.join(user_name_parts)}\n"
    
    if user_dict.get('username'):
        admin_text += f"📱 @{user_dict['username']}\n"
    
    admin_text += f"🆔 #user{user_dict['tg_id']}\n\n"
    
    # Блок Г - анкетные данные
    admin_text += f"📋 Анкета:\n"
    admin_text += f"Имя: {user_dict.get('q_name', '—')}\n"
    admin_text += f"Возраст: {user_dict.get('q_age', '—')}\n"
    admin_text += f"Город: {user_dict.get('q_city', '—')}\n"
    admin_text += f"Терапия: {user_dict.get('q_therapy', '—')}\n\n"
    
    # Блок Е - дата заявки
    if app_date:
        admin_text += f"{app_date}\n\n"
    
    # Логируем отправку
    logger.info(f"Форма одобрения для заявки #{app_id} отправлена админам")
    logger.info(f"Текст формы:\n{admin_text}")
    
    # ============================================
    # ОТПРАВКА УВЕДОМЛЕНИЙ
    # ============================================
    
    # Отправляем форму админу, который одобрил
    await callback.bot.send_message(
        admin_id,
        admin_text,
        reply_markup=create_dm_keyboard(user_dict['tg_id'])
    )
    logger.info(f"Отправлена форма одобрения админу {admin_id}")
    
    # Отправляем форму владельцу, если это не тот же админ
    if OWNER_ID != admin_id:
        await callback.bot.send_message(
            OWNER_ID,
            admin_text,
            reply_markup=create_dm_keyboard(user_dict['tg_id'])
        )
        logger.info(f"Отправлена форма одобрения владельцу {OWNER_ID}")
    
    # Логируем в журнал
    await send_to_journal(
        callback.bot,
        f"✅ Заявка одобрена\n👤 Пользователь: {user_dict['tg_id']}\n👨‍💼 Админ: {admin_id}",
        "approval"
    )
    
    # Удаляем сообщение с заявкой
    await callback.message.delete()


@router.callback_query(F.data.startswith("app_reject_"))
async def reject_app_start(callback: CallbackQuery, state: FSMContext):
    """Начало отклонения заявки"""
    logger.info(f"🔥🔥🔥 reject_app CALLBACK ПОЛУЧЕН в admin.py: {callback.data}")
    
    # Проверяем, что сообщение из личного чата
    if callback.message.chat.type != ChatType.PRIVATE:
        await callback.answer("Эта команда работает только в личных сообщениях", show_alert=True)
        return
    
    admin_id = callback.from_user.id
    app_id = int(callback.data.split("_")[2])
    
    logger.info(f"Admin {admin_id} rejecting application {app_id}")
    
    if admin_id != OWNER_ID and not await is_admin(admin_id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Сохраняем ID заявки и очищаем предыдущее состояние
    await state.clear()
    await state.update_data(app_id=app_id)
    await state.set_state(RejectionStates.waiting_reason)
    
    # Удаляем сообщение с заявкой
    await callback.message.delete()
    
    # Запрашиваем причину
    await callback.message.answer(
        "📝 Укажите причину отклонения заявки (минимум 5 символов):"
    )
    await callback.answer()


@router.message(RejectionStates.waiting_reason, F.text, F.chat.type == ChatType.PRIVATE)
async def reject_app_process(message: Message, state: FSMContext):
    """Обработка причины отклонения - полная форма согласно ТЗ"""
    admin_id = message.from_user.id
    reason = message.text.strip()
    admin_username = message.from_user.username or str(admin_id)
    
    if len(reason) < 5:
        await message.answer("❌ Причина слишком короткая. Укажите минимум 5 символов.")
        return
    
    data = await state.get_data()
    app_id = data.get('app_id')
    
    if not app_id:
        await message.answer("❌ Ошибка: ID заявки не найден")
        await state.clear()
        return
    
    app = await get_application(app_id)
    if not app:
        await message.answer("❌ Заявка не найдена")
        await state.clear()
        return
    
    user = await get_user(app['user_id'])
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    
    user_dict = user
    
    # Отклоняем заявку
    await reject_application(app_id, admin_id, reason)
    
    # Уведомляем пользователя
    try:
        await message.bot.send_message(
            user_dict['tg_id'],
            Messages.REJECTED.format(
                name=user_dict.get('q_name', user_dict.get('first_name', 'Пользователь')),
                reason=reason
            )
        )
        
        await message.bot.send_message(
            user_dict['tg_id'],
            "Вы можете подать заявку снова:",
            reply_markup=create_submit_application_keyboard()
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_dict['tg_id']}: {e}")
    
    # Формируем полную форму отказа согласно ТЗ
    is_returning = user_dict.get('last_exit_at') is not None
    status_tag = "#Возвращение" if is_returning else "#Новый"
    
    # Форматируем дату заявки
    app_date = ""
    if app.get('created_at'):
        created = datetime.fromisoformat(app['created_at'])
        app_date = f"📅 {created.strftime('%d.%m.%Y %H:%M')}\n"
    
    # Блок А - хештег
    text = f"#Отказ\n"
    
    # Блок Б - статус пользователя
    text += f"{status_tag}\n\n"
    
    # Заявка отклонена [@username администратора]
    text += f"Заявка отклонена @{admin_username}\n\n"
    
    # Блок В - базовая информация (отображаем только заполненные поля)
    user_name_parts = []
    if user_dict.get('first_name'):
        user_name_parts.append(user_dict['first_name'])
    if user_dict.get('last_name'):
        user_name_parts.append(user_dict['last_name'])
    
    if user_name_parts:
        text += f"👤 Пользователь: {' '.join(user_name_parts)}\n"
    
    if user_dict.get('username'):
        text += f"📱 @{user_dict['username']}\n"
    
    text += f"🆔 #user{user_dict['tg_id']}\n\n"
    
    # Блок Г - анкетные данные
    text += f"📋 Анкета:\n"
    text += f"Имя: {user_dict.get('q_name', '—')}\n"
    text += f"Возраст: {user_dict.get('q_age', '—')}\n"
    text += f"Город: {user_dict.get('q_city', '—')}\n"
    text += f"Терапия: {user_dict.get('q_therapy', '—')}\n\n"
    
    # Блок Е - дата заявки
    if app_date:
        text += app_date
    
    # Причина отклонения
    text += f"Причина отклонения: {reason}\n\n"
    
    # Отправляем форму ТОЛЬКО владельцу, если это не тот же админ
    if OWNER_ID != admin_id:
        try:
            await message.bot.send_message(
                OWNER_ID,
                text,
                reply_markup=create_dm_keyboard(user_dict['tg_id'])
            )
            logger.info(f"Sent rejection notification to owner {OWNER_ID}")
        except Exception as e:
            logger.error(f"Failed to notify owner {OWNER_ID}: {e}")
    
    # Логируем в журнал
    await send_to_journal(
        message.bot,
        f"❌ Заявка отклонена\n👤 Пользователь: {user_dict['tg_id']}\n👨‍💼 Админ: {admin_id}\n📝 Причина: {reason}",
        "rejection"
    )
    
    # Отправляем confirmation админу, который отклонил
    reply_keyboard = create_owner_reply_keyboard() if admin_id == OWNER_ID else create_admin_reply_keyboard()
    await message.answer(
        f"✅ Заявка #{app_id} отклонена\n\n"
        f"👤 Пользователь: {user_dict.get('first_name', 'Пользователь')}\n"
        f"📝 Причина: {reason}\n\n"
        f"Уведомление отправлено владельцу.",
        reply_markup=reply_keyboard
    )
    
    # Очищаем состояние
    await state.clear()


@router.callback_query(F.data.startswith("app_next_"))
async def next_application(callback: CallbackQuery):
    """Переход к следующей заявке"""
    logger.info(f"🔥🔥🔥 next_app CALLBACK ПОЛУЧЕН в admin.py: {callback.data}")
    
    # Проверяем, что сообщение из личного чата
    if callback.message.chat.type != ChatType.PRIVATE:
        await callback.answer("Эта команда работает только в личных сообщениях", show_alert=True)
        return
    
    data = callback.data.split("_")
    current_index = int(data[2])
    app_ids = list(map(int, data[3].split(',')))
    
    if current_index + 1 < len(app_ids):
        next_app = await get_application(app_ids[current_index + 1])
        if next_app:
            await show_application(callback.message, next_app, callback.from_user.id, app_ids, current_index + 1)
    else:
        await callback.answer("Это последняя заявка", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("app_prev_"))
async def prev_application(callback: CallbackQuery):
    """Переход к предыдущей заявке"""
    logger.info(f"🔥🔥🔥 prev_app CALLBACK ПОЛУЧЕН в admin.py: {callback.data}")
    
    # Проверяем, что сообщение из личного чата
    if callback.message.chat.type != ChatType.PRIVATE:
        await callback.answer("Эта команда работает только в личных сообщениях", show_alert=True)
        return
    
    data = callback.data.split("_")
    current_index = int(data[2])
    app_ids = list(map(int, data[3].split(',')))
    
    if current_index > 0:
        prev_app = await get_application(app_ids[current_index - 1])
        if prev_app:
            await show_application(callback.message, prev_app, callback.from_user.id, app_ids, current_index - 1)
    else:
        await callback.answer("Это первая заявка", show_alert=True)
    
    await callback.answer()


@router.message(Command("set_chat"), F.chat.type.in_({'group', 'supergroup'}))
async def set_main_chat(message: Message):
    """Установка ID основного чата - выполнять в группе"""
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Только владелец может использовать эту команду.")
        return
    
    from database import set_setting
    await set_setting("main_chat_id", str(message.chat.id))
    
    await message.answer(
        f"✅ Чат установлен!\n\n"
        f"ID: {message.chat.id}\n"
        f"Название: {message.chat.title}"
    )


@router.message(Command("sync_chat"), F.chat.type.in_({'group', 'supergroup'}))
async def sync_chat_members(message: Message):
    """Синхронизация статусов участников чата (для владельца)"""
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Только владелец может использовать эту команду.")
        return
    
    await message.answer("🔄 Начинаю синхронизацию участников чата...")
    
    try:
        # Получаем администраторов чата
        admins = await message.bot.get_chat_administrators(message.chat.id)
        
        updated_count = 0
        created_count = 0
        total_count = len(admins)
        
        for admin in admins:
            user_id = admin.user.id
            user = await get_user(user_id)
            
            if user:
                if user.get('status') != UserStatus.IN_CHAT:
                    await update_user(user_id, status=UserStatus.IN_CHAT)
                    updated_count += 1
                    logger.info(f"Updated status for user {user_id} to in_chat")
            else:
                # Если пользователя нет в БД, создаем запись
                from database import create_user
                role = UserRole.OWNER if admin.status == 'creator' else UserRole.ADMIN
                await create_user(
                    tg_id=user_id,
                    username=admin.user.username,
                    first_name=admin.user.first_name,
                    last_name=admin.user.last_name,
                    role=role
                )
                await update_user(user_id, status=UserStatus.IN_CHAT)
                created_count += 1
        
        await message.answer(
            f"✅ Синхронизация завершена!\n"
            f"📊 Обработано: {total_count}\n"
            f"🔄 Обновлено статусов: {updated_count}\n"
            f"➕ Создано новых: {created_count}\n\n"
            f"Примечание: Синхронизированы только администраторы чата."
        )
        
    except Exception as e:
        logger.error(f"Error syncing chat members: {e}")
        await message.answer(f"❌ Ошибка синхронизации: {e}")