import html
import asyncio
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
import logging
from database.db_friend import (
    approve_application, reject_application, update_user,
    get_user, get_application, create_invite_link
)
from config import CHAT_ID, ADMIN_CHAT_ID, DOSSIER_THREAD_ID, APPLICATIONS_THREAD_ID
from utils.face_detector import has_human_face

logger = logging.getLogger(__name__)

# Текст кнопок для ReplyKeyboard в треде заявок
BTN_NEW_APPS = "📋 Новые заявки"
BTN_ADMINS = "👥 Админы"
BTN_BLACKLIST = "🚫 Черный список"
BTN_CHECK_USER = "🔍 Проверка ника"
BTN_TRIGGERS = "⚡ Триггеры"
BTN_JOURNAL = "📓 Журнал"
BTN_STATS = "📊 Статистика"
BTN_NOT_IN_CHAT = "📊 Не в чате"
BTN_ECONOMY = "💰 Экономика"
BTN_SYSTEM = "⚙️ Система"
BTN_BACKUP = "💾 Скачать БД"


def get_applications_keyboard(is_owner: bool = False) -> ReplyKeyboardMarkup:
    """Возвращает ReplyKeyboard для треда заявок в зависимости от роли"""
    if is_owner:
        buttons = [
            [KeyboardButton(BTN_NEW_APPS)],
            [KeyboardButton(BTN_ADMINS), KeyboardButton(BTN_BLACKLIST)],
            [KeyboardButton(BTN_CHECK_USER)],
            [KeyboardButton(BTN_TRIGGERS), KeyboardButton(BTN_JOURNAL)],
            [KeyboardButton(BTN_STATS), KeyboardButton(BTN_NOT_IN_CHAT)],
            [KeyboardButton(BTN_ECONOMY), KeyboardButton(BTN_SYSTEM)],
            [KeyboardButton(BTN_BACKUP)],
        ]
    else:
        buttons = [
            [KeyboardButton(BTN_NEW_APPS)],
        ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, selective=True)


async def _send_dossier(bot, user_id: int, dossier_text: str, keyboard):
    """Отправляет досье с фото (если найдено лицо) в тред администраторов."""
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=3)
        face_photo = None

        for photo_size_list in (photos.photos or []):
            try:
                file = await bot.get_file(photo_size_list[-1].file_id)
                byte_array = await file.download_as_bytearray()
                if await has_human_face(byte_array):
                    face_photo = photo_size_list[-1].file_id
                    break
            except Exception as e:
                logger.warning(f"_send_dossier: ошибка обработки фото: {e}")
                continue

        if face_photo:
            await bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                message_thread_id=DOSSIER_THREAD_ID,
                photo=face_photo,
                caption=dossier_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        else:
            no_face_text = dossier_text + "\n\n<i>(⚠️ ИИ не обнаружил человеческого лица на открытых аватарках)</i>"
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                message_thread_id=DOSSIER_THREAD_ID,
                text=no_face_text,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
    except Exception as e:
        logger.error(f"_send_dossier: ошибка отправки досье для {user_id}: {e}")


async def _send_invite_link(bot, user_id: int, user_name: str):
    """Генерирует одноразовую ссылку и отправляет пуш пользователю. Возвращает message_id."""

    try:
        link_obj = await bot.create_chat_invite_link(
            chat_id=CHAT_ID,
            name=f"Approve: {user_name}"[:32],
            member_limit=1
        )
        invite_link = link_obj.invite_link
    except Exception as e:
        logger.error(f"Не удалось создать ссылку для {user_id}: {e}")
        return None

    # Сохраняем ссылку в БД
    await create_invite_link(user_id, invite_link)

    # Отправляем пуш (ссылка скрыта в кнопке, защита от пересылки)
    try:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚪 Войти в чат Pulse 4ever", url=invite_link)]
        ])
        msg = await bot.send_message(
            chat_id=user_id,
            text=(
                f"{user_name}, ты на пороге входа в чат Pulse 4ever! 🎉\n\n"
                f"Нажми кнопку ниже, чтобы присоединиться.\n\n"
                f"⚠️ Ссылка одноразовая и только для тебя — никому не передавай!"
            ),
            reply_markup=keyboard,
            protect_content=True
        )
        # Сохраняем message_id чтобы удалить его после вступления
        await update_user(user_id, invite_message_id=msg.message_id)
        logger.info(f"✅ Invite link sent to {user_id}, message_id={msg.message_id}")
        return msg.message_id
    except Exception as e:
        logger.error(f"Ошибка отправки ссылки пользователю {user_id}: {e}")
        return None


async def _send_invite_friends_after_delay(bot, user_id: int, user_name: str, delay: int = 60):
    """Через delay секунд отправляет сообщение с приглашением друзей."""
    await asyncio.sleep(delay)
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"{user_name},\n"
                f"Приглашай своих знакомых и друзей в чат Pulse 💗💗💗\n\n"
                f"Отправь нашего бота @Pulse_4ever_bot своему «статусному» другу!"
            )
        )
        logger.info(f"✅ Invite friends message sent to {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения друзьям для {user_id}: {e}")


def _msk_now() -> str:
    msk = pytz.timezone('Europe/Moscow')
    return datetime.now(msk).strftime("%d %B %Y г. %H:%M:%S МСК")

def _fmt_date(dt_str: str) -> str:
    """Форматирует строку даты из БД в читаемый МСК формат"""
    if not dt_str:
        return "—"
    try:
        msk = pytz.timezone('Europe/Moscow')
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        return dt.astimezone(msk).strftime("%d %B %Y г. %H:%M:%S МСК")
    except Exception:
        return dt_str

async def admin_moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Данные кнопки: adm_action_USERID_APPID
    parts = query.data.split("_")
    if len(parts) < 4:
        return

    # Обработка случая "Отмена" при вводе причины
    # Формат: adm_rej_cancel_USERID_APPID -> len(parts) == 5
    is_cancel = False
    if len(parts) == 5 and parts[2] == "cancel":
        is_cancel = True
        action = parts[1]
        target_user_id = int(parts[3])
        app_id = int(parts[4])
    else:
        action = parts[1]  # app, rej или skip
        target_user_id = int(parts[2])
        app_id = int(parts[3])

    if is_cancel:
        # Сбрасываем все флаги ожидания
        context.user_data.pop('awaiting_reject_reason', None)
        context.user_data.pop('rej_app_id', None)
        context.user_data.pop('rej_user_id', None)
        context.user_data.pop('rej_reg_data', None)
        context.user_data.pop('rej_applied_at', None)
        
        # Показываем карточку заявки заново
        app_data = await get_application(app_id)
        reg_data = await get_user(target_user_id)
        if app_data and reg_data:
            await _show_app_card(query, context, app_data, reg_data)
        else:
            await query.edit_message_text("❌ Ошибка: Данные заявки не найдены.")
        return

    main_db = context.bot_data.get('db')

    # Получаем данные заявки и пользователя
    app_data = await get_application(app_id)

    # Защита от двойного нажатия — если заявка уже обработана
    if app_data and app_data.get('status') in ('approved', 'rejected', 'deleted'):
        await query.answer("⚠️ Эта заявка уже обработана.", show_alert=True)
        return

    reg_data = await get_user(target_user_id)
    if not reg_data:
        # Пользователь не найден в БД — создаём запись и подтягиваем из Telegram
        from database.db_friend import create_user
        try:
            chat_member = await context.bot.get_chat_member(target_user_id, target_user_id)
            tg_user = chat_member.user
        except Exception:
            tg_user = None
        
        if tg_user:
            await create_user(target_user_id, tg_user.username or '', tg_user.first_name or '', tg_user.last_name or '')
            reg_data = await get_user(target_user_id)
        
        if not reg_data:
            reg_data = {}
            logger.warning(f"⚠️ Пользователь {target_user_id} не найден в БД регистрации")
    applied_at = _fmt_date(app_data.get('created_at')) if app_data else "—"

    if action == "app":
        joined_at = _msk_now()

        # 1. Одобряем в базе регистрации
        await approve_application(app_id, query.from_user.id)
        await update_user(target_user_id, status='approved')

        # 2. Регистрируем в основной базе (майнинг и т.д.)
        referrer_id = reg_data.get('referred_by') if reg_data else None
        if main_db:
            main_db.add_user(
                target_user_id,
                username=reg_data.get('username', ''),
                first_name=reg_data.get('first_name', ''),
                last_name=reg_data.get('last_name', ''),
            )
            if referrer_id:
                try:
                    main_db.cursor.execute(
                        'UPDATE users SET referrer_id = ? WHERE user_id = ?',
                        (referrer_id, target_user_id)
                    )
                    main_db.conn.commit()
                    logger.info(f"✅ Реферал {referrer_id} привязан к {target_user_id}")
                except Exception as e:
                    logger.error(f"⚠️ Не удалось привязать реферала: {e}")

        # 3. Уведомляем пользователя + отправляем одноразовую ссылку
        user_name = reg_data.get('q_name') or reg_data.get('first_name') or 'Друг'
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 Поздравляем! Твоя заявка одобрена."
            )
        except Exception as e:
            logger.error(f"Не смог написать юзеру {target_user_id}: {e}")

        # Отправляем одноразовую ссылку
        await _send_invite_link(context.bot, target_user_id, user_name)

        # Через 1 минуту — сообщение "Приглашай друзей"
        asyncio.create_task(
            _send_invite_friends_after_delay(context.bot, target_user_id, user_name, delay=60)
        )

        # 4. Карточка 3.3.3 в чате администраторов
        admin_name = f"@{query.from_user.username}" if query.from_user.username else str(query.from_user.id)
        is_returning = bool(reg_data.get('last_exit_at'))
        block_b = "#Возвращение" if is_returning else "#Новый"
        username_str = f"@{reg_data.get('username')}" if reg_data.get('username') else "нет"
        full_name = html.escape(
            f"{reg_data.get('first_name') or ''} {reg_data.get('last_name') or ''}".strip()
            or reg_data.get('q_name') or '—'
        )
        user_link = f'<a href="tg://user?id={target_user_id}">{full_name}</a>'
        group_link = f'<a href="https://t.me/c/{str(CHAT_ID).replace("-100", "")}/1">Pulse 4ever</a>'

        card_text = (
            f"#Одобрено\n"
            f"{block_b}\n"
            f"Заявка одобрена {admin_name}\n\n"
            f"Группа: {group_link}\n"
            f"Пользователь: {user_link}\n"
            f"Никнейм: {username_str}\n"
            f"ID: <code>{target_user_id}</code> <b>#user{target_user_id}</b>\n\n"
            f"<b>Анкета:</b>\n"
            f"Имя: {html.escape(reg_data.get('q_name') or '—')}\n"
            f"Возраст: {reg_data.get('q_age') or '—'}\n"
            f"Город: {html.escape(reg_data.get('q_city') or '—')}\n"
            f"Терапия: {html.escape(reg_data.get('q_therapy') or '—')}\n\n"
            f"📅 Дата заявки: {applied_at}\n"
            f"✅ Дата вступления: {joined_at}"
        )
        card_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✉️ Написать в ЛС", url=f"tg://user?id={target_user_id}")]
        ])
        await query.edit_message_text(card_text, reply_markup=card_kb, parse_mode="HTML",
                                      disable_web_page_preview=True)

        # 5. Удаляем карточку заявки из треда APPLICATIONS_THREAD_ID
        app_msg_id = app_data.get('message_id') if app_data else None
        logger.info(f"Удаляем заявку #{app_id}: message_id={app_msg_id}, chat={ADMIN_CHAT_ID}")
        if app_msg_id:
            try:
                await context.bot.delete_message(chat_id=ADMIN_CHAT_ID, message_id=app_msg_id)
                logger.info(f"✅ Сообщение заявки {app_msg_id} удалено из треда")
            except Exception as e:
                logger.error(f"❌ Не удалось удалить сообщение заявки {app_msg_id}: {e}")
        else:
            logger.warning(f"⚠️ message_id не сохранён для заявки #{app_id} — удаление пропущено")

        # 6. ДОСЬЕ С ФОТО — отправляем в тред ADMIN_CHAT_ID/DOSSIER_THREAD_ID
        asyncio.create_task(
            _send_dossier(context.bot, target_user_id, card_text, card_kb)
        )

    elif action == "rej":
        # Продлеваем блокировку на 5 минут для ввода причины
        from database.db_friend import lock_application
        await lock_application(app_id, query.from_user.id, duration_minutes=5)

        # Сохраняем данные и ждём причину от администратора
        context.user_data['rej_app_id'] = app_id
        context.user_data['rej_user_id'] = target_user_id
        context.user_data['rej_reg_data'] = dict(reg_data)
        context.user_data['rej_applied_at'] = applied_at
        context.user_data['awaiting_reject_reason'] = True

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data=f"adm_rej_cancel_{target_user_id}_{app_id}")]
        ])
        await query.edit_message_text(
            f"✍️ <b>Заявка #{app_id}</b>\n\n"
            f"Напишите причину отказа следующим сообщением в этот чат.\n\n"
            f"<i>Пример: Анкета содержит неполные данные — не указана терапия.</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    elif action == "skip":
        # Ставим статус 'skipped' — заявка возвращается в очередь отдельным статусом
        from database.db_friend import set_application_skipped
        await set_application_skipped(app_id)
        context.user_data.pop('current_app_id', None)

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Следующая заявка", callback_data="new_app")]
        ])
        await query.edit_message_text(
            f"⏳ <b>Заявка #{app_id} — ОТЛОЖЕНА</b>\n\n"
            f"👤 <code>{target_user_id}</code> #user{target_user_id} пока не уведомлен.\n"
            f"Заявка возвращена в очередь.",
            parse_mode="HTML",
            reply_markup=kb
        )

    elif action == "del":
        # Удаляем заявку — статус DELETED, не возвращается в очередь, пользователь НЕ уведомлён
        from database.db_friend import delete_application
        await delete_application(app_id, query.from_user.id)
        context.user_data.pop('current_app_id', None)

        admin_name = f"@{query.from_user.username}" if query.from_user.username else str(query.from_user.id)

        # Удаляем карточку из треда заявок
        app_msg_id = app_data.get('message_id') if app_data else None
        if app_msg_id:
            try:
                await context.bot.delete_message(chat_id=ADMIN_CHAT_ID, message_id=app_msg_id)
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение заявки {app_msg_id}: {e}")

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Следующая заявка", callback_data="new_app")]
        ])
        await query.edit_message_text(
            f"🗑 <b>Заявка #{app_id} — УДАЛЕНА</b>\n\n"
            f"👤 <code>{target_user_id}</code> #user{target_user_id}\n"
            f"👨‍💼 Удалил: {admin_name}\n\n"
            f"<i>Пользователь не уведомлён.</i>",
            parse_mode="HTML",
            reply_markup=kb
        )
        logger.info(f"Application #{app_id} deleted by {query.from_user.id}")
        
async def handle_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста с причиной отказа от администратора"""
    from database.db_friend import reject_application, update_user
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    if not context.user_data.get('awaiting_reject_reason'):
        return  # не ждём причины — игнорируем

    # Удаляем сообщение админа с причиной из чата
    try:
        await update.message.delete()
    except Exception:
        pass

    reason = update.message.text.strip()
    app_id = context.user_data.pop('rej_app_id', None)
    target_user_id = context.user_data.pop('rej_user_id', None)
    reg_data = context.user_data.pop('rej_reg_data', {})
    applied_at = context.user_data.pop('rej_applied_at', '—')
    context.user_data.pop('awaiting_reject_reason', None)

    if not app_id or not target_user_id:
        return

    # Сохраняем отказ в БД
    from database.db_friend import get_application
    app_data = await get_application(app_id)
    
    await reject_application(app_id, update.effective_user.id, reason)
    await update_user(target_user_id, status='rejected')

    user_name = reg_data.get('q_name') or reg_data.get('first_name') or 'Пользователь'
    admin_name = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)

    # 3.4.1 Пуш пользователю с причиной + кнопка [Подать заявку]
    try:
        keyboard_user = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Подать заявку снова", callback_data="reapply")]
        ])
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"{user_name}, к сожалению, анкета содержит недостоверные или неполные данные: "
                f"{reason}\n\n"
                f"Просьба подать заявку снова."
            ),
            reply_markup=keyboard_user
        )
    except Exception as e:
        logger.error(f"Не смог написать юзеру {target_user_id}: {e}")

    # 3.4.2 Карточка отказа в тред заявок
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        message_thread_id=APPLICATIONS_THREAD_ID,
        text=
        f"❌ <b>#Отказ — Заявка #{app_id}</b>\n\n"
        f"👤 {html.escape(reg_data.get('q_name') or '—')} | "
        f"<code>{target_user_id}</code>\n"
        f"Никнейм: @{reg_data.get('username') or 'нет'}\n\n"
        f"📋 <b>Анкета:</b>\n"
        f"Имя: {html.escape(reg_data.get('q_name') or '—')}\n"
        f"🎂 Возраст: {reg_data.get('q_age') or '—'}\n"
        f"🏙 Город: {html.escape(reg_data.get('q_city') or '—')}\n"
        f"💊 Терапия: {html.escape(reg_data.get('q_therapy') or '—')}\n\n"
        f"📅 Дата заявки: {applied_at}\n\n"
        f"🚫 <b>Причина отказа:</b> {html.escape(reason)}\n\n"
        f"👨‍💼 Обработал: {admin_name}",
        parse_mode="HTML"
    )


    # 3.4.3 УДАЛЯЕМ старую карточку заявки из треда заявок
    app_msg_id = app_data.get('message_id') if app_data else None
    if not app_msg_id:
        # Пытаемся взять из текущей сессии если не сохранили в БД
        app_msg_id = context.user_data.get('current_app_msg_id')

    if app_msg_id:
        try:
            await context.bot.delete_message(chat_id=ADMIN_CHAT_ID, message_id=app_msg_id)
            logger.info(f"✅ Сообщение заявки {app_msg_id} удалено после ОТКАЗА")
        except Exception as e:
            logger.error(f"❌ Не удалось удалить сообщение заявки {app_msg_id} при отказе: {e}")

    logger.info(f"Application #{app_id} rejected by {update.effective_user.id}, reason: {reason}")


async def send_admin_panel(bot, chat_id: int, is_owner: bool = False, thread_id: int = None):
    """Отправляет панель администратора/владельца в чат (с учётом ветки)"""
    if is_owner:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Новые заявки", callback_data="new_app")],
            [InlineKeyboardButton("👥 Админы", callback_data="panel_admins"),
             InlineKeyboardButton("🚫 Черный список", callback_data="panel_blacklist")],
            [InlineKeyboardButton("🔍 Проверка ника", callback_data="panel_check_user")],
            [InlineKeyboardButton("⚡ Триггеры", callback_data="owner_triggers"),
             InlineKeyboardButton("📓 Журнал", callback_data="owner_journal")],
            [InlineKeyboardButton("📊 Статистика", callback_data="menu_stats"),
             InlineKeyboardButton("📊 Не в чате", callback_data="owner_stats_not_in_chat")],
            [InlineKeyboardButton("💰 Экономика", callback_data="owner_economy"),
             InlineKeyboardButton("⚙️ Система", callback_data="owner_system")],
            [InlineKeyboardButton("💾 Скачать БД", callback_data="owner_backup")],
        ])
        text = "👑 <b>Панель владельца</b>\n\nВыберите раздел:"
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Новые заявки", callback_data="new_app")],
        ])
        text = "👨‍💼 <b>Панель администратора</b>\n\nНажмите кнопку, чтобы получить следующую заявку."

    kw = {'chat_id': chat_id, 'text': text, 'reply_markup': keyboard, 'parse_mode': 'HTML'}
    if thread_id:
        kw['message_thread_id'] = thread_id
    await bot.send_message(**kw)


def _owner_inline_panel() -> InlineKeyboardMarkup:
    """InlineKeyboard полной панели владельца для треда заявок"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Новые заявки", callback_data="new_app")],
        [InlineKeyboardButton("👥 Админы", callback_data="panel_admins"),
         InlineKeyboardButton("🚫 Черный список", callback_data="panel_blacklist")],
        [InlineKeyboardButton("🔍 Проверка ника", callback_data="panel_check_user")],
        [InlineKeyboardButton("⚡ Триггеры", callback_data="owner_triggers"),
         InlineKeyboardButton("📓 Журнал", callback_data="owner_journal")],
        [InlineKeyboardButton("📊 Статистика", callback_data="menu_stats"),
         InlineKeyboardButton("📊 Не в чате", callback_data="owner_stats_not_in_chat")],
        [InlineKeyboardButton("💰 Экономика", callback_data="owner_economy"),
         InlineKeyboardButton("⚙️ Система", callback_data="owner_system")],
        [InlineKeyboardButton("💾 Скачать БД", callback_data="owner_backup")],
    ])


def _admin_inline_panel() -> InlineKeyboardMarkup:
    """InlineKeyboard панели админа для треда заявок"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Новые заявки", callback_data="new_app")],
    ])


async def send_applications_button(bot):
    """Отправляет InlineKeyboard панель в тред заявок при старте бота"""
    keyboard = _owner_inline_panel()
    try:
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            message_thread_id=APPLICATIONS_THREAD_ID,
            text="👑 <b>Панель заявок</b>\n\nИспользуйте кнопки для управления.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        logger.info(f"✅ InlineKeyboard панели отправлена в тред {APPLICATIONS_THREAD_ID}")
    except Exception as e:
        logger.warning(f"Не удалось отправить панель в тред заявок: {e}")


async def handle_owner_panel_button(update: Update, context: ContextTypes.DEFAULT_TYPE, btn_text: str):
    """Обработчик текстовых кнопок панели владельца в треде заявок"""
    user_id = update.effective_user.id

    if not await _is_owner_or_deputy(user_id):
        return

    # Удаляем сообщение с текстом кнопки
    try:
        await update.message.delete()
    except Exception:
        pass

    # Маппинг текстовых кнопок → callback_data для panel_callback
    btn_map = {
        BTN_ADMINS: "panel_admins",
        BTN_BLACKLIST: "panel_blacklist",
        BTN_CHECK_USER: "panel_check_user",
        BTN_TRIGGERS: "owner_triggers",
        BTN_JOURNAL: "owner_journal",
        BTN_STATS: "menu_stats",
        BTN_NOT_IN_CHAT: "owner_stats_not_in_chat",
        BTN_ECONOMY: "owner_economy",
        BTN_SYSTEM: "owner_system",
        BTN_BACKUP: "owner_backup",
    }

    callback_data = btn_map.get(btn_text)
    if not callback_data:
        return

    # Отправляем inline-панель владельца с подсветкой нужного раздела
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Новые заявки", callback_data="new_app")],
        [InlineKeyboardButton("👥 Админы", callback_data="panel_admins"),
         InlineKeyboardButton("🚫 Черный список", callback_data="panel_blacklist")],
        [InlineKeyboardButton("🔍 Проверка ника", callback_data="panel_check_user")],
        [InlineKeyboardButton("⚡ Триггеры", callback_data="owner_triggers"),
         InlineKeyboardButton("📓 Журнал", callback_data="owner_journal")],
        [InlineKeyboardButton("📊 Статистика", callback_data="menu_stats"),
         InlineKeyboardButton("📊 Не в чате", callback_data="owner_stats_not_in_chat")],
        [InlineKeyboardButton("💰 Экономика", callback_data="owner_economy"),
         InlineKeyboardButton("⚙️ Система", callback_data="owner_system")],
        [InlineKeyboardButton("💾 Скачать БД", callback_data="owner_backup")],
    ])
    sent = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        message_thread_id=update.message.message_thread_id,
        text=f"👑 <b>Панель владельца</b>\n\nВыберите раздел:",
        reply_markup=kb,
        parse_mode="HTML"
    )


async def handle_new_apps_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовой кнопки '📋 Новые заявки' — показывает первую заявку inline"""
    from database.db_friend import get_new_applications, lock_application, is_admin as is_reg_admin

    user_id = update.effective_user.id
    # Удаляем сообщение с текстом кнопки
    try:
        await update.message.delete()
    except Exception:
        pass

    apps = await get_new_applications(exclude_locked=True)
    if not apps:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Новые заявки", callback_data="new_app")]
        ])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            message_thread_id=update.message.message_thread_id,
            text="✅ <b>Все заявки обработаны.</b>\n\nНажмите кнопку когда появятся новые.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    app = apps[0]
    app_id = app['id']
    target_user_id = app['user_id']

    locked = await lock_application(app_id, user_id, duration_minutes=2)
    if not locked:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ Заявку уже взял другой администратор.",
            parse_mode="HTML"
        )
        return

    context.user_data['current_app_id'] = app_id

    reg_data = await get_user(target_user_id)
    if not reg_data:
        return

    last_rejection = reg_data.get('last_rejection_reason')
    block_d = ""
    if app.get('status') == 'skipped':
        block_d = "\n⏳ <b>Заявка была отложена ранее.</b>\n"
    elif last_rejection:
        block_d = (
            f"\n🚨 <b>Внимание! Пользователь уже подавал заявку.</b>\n"
            f"Причина отказа: {last_rejection}\n"
        )

    applied_at = _fmt_date(app.get('created_at'))
    username_str = f"@{reg_data.get('username')}" if reg_data.get('username') else "нет"

    text = (
        f"📋 <b>ЗАЯВКА #{app_id}</b>"
        f"{block_d}\n"
        f"👤 Имя: {html.escape(reg_data.get('q_name') or '—')} | <code>{target_user_id}</code> | <b>#user{target_user_id}</b>\n"
        f"🎂 Возраст: {reg_data.get('q_age') or '—'}\n"
        f"🏙 Город: {html.escape(reg_data.get('q_city') or '—')}\n"
        f"💊 Терапия: {html.escape(reg_data.get('q_therapy') or '—')}\n"
        f"🤝 Реферал: {html.escape(str(reg_data.get('referred_by') or 'Нет'))}\n"
        f"🆔 Никнейм: {username_str}\n\n"
        f"📅 <b>Блок Е:</b>\n"
        f"Дата заявки: {applied_at}\n\n"
        f"⏳ <i>Заявка заблокирована на 2 минуты для вас</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_app_{target_user_id}_{app_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_rej_{target_user_id}_{app_id}"),
            InlineKeyboardButton("⏳ Отложить", callback_data=f"adm_skip_{target_user_id}_{app_id}"),
        ],
        [
            InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_{target_user_id}_{app_id}"),
            InlineKeyboardButton("✉️ Написать в ЛС", url=f"tg://user?id={target_user_id}"),
        ],
        [InlineKeyboardButton("📋 Следующая заявка", callback_data="new_app")],
    ])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        message_thread_id=update.message.message_thread_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def new_application_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Новые заявки'"""
    from database.db_friend import get_new_applications, lock_application, unlock_application
    from config import ADMIN_CHAT_ID

    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id

    # Разблокируем предыдущую заявку этого админа (если есть)
    prev_app_id = context.user_data.get('current_app_id')
    if prev_app_id:
        await unlock_application(prev_app_id)
        context.user_data.pop('current_app_id', None)
        logger.info(f"Admin {admin_id} released app {prev_app_id}")

    # Берём следующую свободную заявку (исключая ту что только что смотрели)
    apps = await get_new_applications(exclude_locked=True)
    if prev_app_id:
        apps = [a for a in apps if a['id'] != prev_app_id]
    if not apps:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Новые заявки", callback_data="new_app")]
        ])
        try:
            await query.edit_message_text(
                "✅ <b>Все заявки обработаны.</b>\n\nНажмите кнопку когда появятся новые.",
                parse_mode="HTML",
                reply_markup=kb
            )
        except Exception:
            pass
        return

    app = apps[0]
    app_id = app['id']
    user_id = app['user_id']

    # Блокируем на 2 минуты за этим админом
    locked = await lock_application(app_id, admin_id, duration_minutes=2)
    if not locked:
        await query.answer("Заявку только что взял другой администратор. Попробуйте ещё раз.", show_alert=True)
        return

    context.user_data['current_app_id'] = app_id

    # Получаем данные пользователя из регистрационной базы
    reg_data = await get_user(user_id)
    if not reg_data:
        await query.answer("Ошибка: данные пользователя не найдены.", show_alert=True)
        return

    # Отрисовка карточки
    await _show_app_card(query, context, app, reg_data)


async def _show_app_card(query, context, app, reg_data):
    """Вспомогательная функция для отрисовки карточки заявки admin-у"""
    from config import ADMIN_CHAT_ID, APPLICATIONS_THREAD_ID
    
    app_id = app['id']
    user_id = app['user_id']
    
    # Блок Д — статус заявки
    last_rejection = reg_data.get('last_rejection_reason')
    block_d = ""
    if app.get('status') == 'skipped':
        block_d = "\n⏳ <b>Заявка была отложена ранее.</b>\n"
    elif last_rejection:
        block_d = (
            f"\n🚨 <b>Внимание! Пользователь уже подавал заявку.</b>\n"
            f"Причина отказа: {last_rejection}\n"
        )

    # Блок Е — даты
    applied_at = _fmt_date(app.get('created_at'))

    # Имя и никнейм
    username_str = f"@{reg_data.get('username')}" if reg_data.get('username') else "нет"

    text = (
        f"📋 <b>ЗАЯВКА #{app_id}</b>"
        f"{block_d}\n"
        f"👤 Имя: {html.escape(reg_data.get('q_name') or '—')} | <code>{user_id}</code> | <b>#user{user_id}</b>\n"
        f"🎂 Возраст: {reg_data.get('q_age') or '—'}\n"
        f"🏙 Город: {html.escape(reg_data.get('q_city') or '—')}\n"
        f"💊 Терапия: {html.escape(reg_data.get('q_therapy') or '—')}\n"
        f"🤝 Реферал: {html.escape(str(reg_data.get('referred_by') or 'Нет'))}\n"
        f"🆔 Никнейм: {username_str}\n\n"
        f"📅 <b>Блок Е:</b>\n"
        f"Дата заявки: {applied_at}\n\n"
        f"⏳ <i>Заявка заблокирована на 2 минуты для вас</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_app_{user_id}_{app_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_rej_{user_id}_{app_id}"),
            InlineKeyboardButton("⏳ Отложить", callback_data=f"adm_skip_{user_id}_{app_id}"),
        ],
        [
            InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_{user_id}_{app_id}"),
            InlineKeyboardButton("✉️ Написать в ЛС", url=f"tg://user?id={user_id}"),
        ],
        [InlineKeyboardButton("📋 Следующая заявка", callback_data="new_app")],
    ])

    # Редактируем текущее сообщение вместо отправки нового
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        # Если не удалось отредактировать — отправляем новое
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                message_thread_id=APPLICATIONS_THREAD_ID,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )


async def _is_owner_or_deputy(user_id: int) -> bool:
    """Проверка: владелец или зам владельца."""
    from config import OWNER_ID
    if user_id == OWNER_ID:
        return True
    from database.db_friend import is_deputy
    return await is_deputy(user_id)


async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок панели владельца: Админы, ЧС, Проверка ника"""
    from database.db_friend import (
        is_admin, add_admin, remove_admin, get_all_admins,
        is_blacklisted, add_to_blacklist, remove_from_blacklist, get_blacklist_with_users
    )
    from config import OWNER_ID

    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # Только владелец или зам
    if not await _is_owner_or_deputy(user_id):
        await query.answer("⛔ Только для владельца.", show_alert=True)
        return

    back_btn = [[InlineKeyboardButton("🔙 Назад", callback_data="panel_main")]]

    # ─── ГЛАВНАЯ ───
    if data == "panel_main":
        await send_admin_panel(context.bot, query.message.chat.id, is_owner=True)
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    # ─── АДМИНЫ (4.2.1) ───
    elif data == "panel_admins":
        from database.db_friend import get_all_deputies
        admins = await get_all_admins()
        deputies = await get_all_deputies()
        deputy_ids = {d['tg_id'] for d in deputies}

        lines = []
        for a in admins:
            name = a.get('username') or a.get('first_name') or str(a['tg_id'])
            if a['tg_id'] == OWNER_ID:
                role = "👑 Владелец"
            elif a['tg_id'] in deputy_ids:
                role = "🥈 Зам"
            else:
                role = "⭐ Админ"
            lines.append(f"  {role} — @{name} (<code>{a['tg_id']}</code>)")
        admin_block = "\n".join(lines) if lines else "— пусто —"
        text = f"👥 <b>Персонал</b>\n\n{admin_block}"
        buttons = [
            [InlineKeyboardButton("➕ Добавить админа", callback_data="panel_admin_add"),
             InlineKeyboardButton("➖ Удалить админа", callback_data="panel_admin_remove")],
        ]
        # Кнопки зама — только для главного владельца
        if user_id == OWNER_ID:
            buttons.append(
                [InlineKeyboardButton("👑 Назначить зама", callback_data="panel_deputy_add"),
                 InlineKeyboardButton("👑 Снять зама", callback_data="panel_deputy_remove")]
            )
        buttons.extend(back_btn)
        kb = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

    elif data == "panel_admin_add":
        context.user_data['panel_awaiting'] = 'admin_add'
        await query.edit_message_text(
            "➕ <b>Добавить администратора</b>\n\nОтправьте <b>Telegram ID</b> пользователя:",
            reply_markup=InlineKeyboardMarkup(back_btn), parse_mode="HTML"
        )

    elif data == "panel_admin_remove":
        context.user_data['panel_awaiting'] = 'admin_remove'
        await query.edit_message_text(
            "➖ <b>Удалить администратора</b>\n\nОтправьте <b>Telegram ID</b> пользователя:",
            reply_markup=InlineKeyboardMarkup(back_btn), parse_mode="HTML"
        )

    # ─── ЗАМ ВЛАДЕЛЬЦА (только главный владелец) ───
    elif data == "panel_deputy_add":
        if user_id != OWNER_ID:
            await query.answer("⛔ Только владелец может назначать замов.", show_alert=True)
            return
        context.user_data['panel_awaiting'] = 'deputy_add'
        await query.edit_message_text(
            "👑 <b>Назначить Зама Владельца</b>\n\n"
            "Зам получает полный доступ к Панели Владельца.\n\n"
            "Отправьте <b>Telegram ID</b> участника:",
            reply_markup=InlineKeyboardMarkup(back_btn), parse_mode="HTML"
        )

    elif data == "panel_deputy_remove":
        if user_id != OWNER_ID:
            await query.answer("⛔ Только владелец может снимать замов.", show_alert=True)
            return
        from database.db_friend import get_all_deputies
        deputies = await get_all_deputies()
        if deputies:
            dep_lines = [f"  🥈 @{d.get('username') or d.get('first_name') or d['tg_id']} (<code>{d['tg_id']}</code>)"
                         for d in deputies]
            dep_block = "\n".join(dep_lines)
        else:
            dep_block = "  — замов нет —"
        context.user_data['panel_awaiting'] = 'deputy_remove'
        await query.edit_message_text(
            f"👑 <b>Снять Зама Владельца</b>\n\n"
            f"<b>Текущие замы:</b>\n{dep_block}\n\n"
            f"Отправьте <b>Telegram ID</b> зама для снятия:",
            reply_markup=InlineKeyboardMarkup(back_btn), parse_mode="HTML"
        )

    # ─── ЧЕРНЫЙ СПИСОК (4.2.2) ───
    elif data == "panel_blacklist":
        bl_users = await get_blacklist_with_users()
        if bl_users:
            lines = [f"• <code>{u['tg_id']}</code> — {html.escape(u.get('reason') or '—')}" for u in bl_users]
            text = "🚫 <b>Черный список</b>\n\n" + "\n".join(lines)
        else:
            text = "🚫 <b>Черный список</b>\n\n— пусто —"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить", callback_data="panel_bl_add"),
             InlineKeyboardButton("➖ Удалить", callback_data="panel_bl_remove")],
            *back_btn
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

    elif data == "panel_bl_add":
        context.user_data['panel_awaiting'] = 'bl_add'
        await query.edit_message_text(
            "➕ <b>Добавить в ЧС</b>\n\nОтправьте <b>Telegram ID</b> пользователя:",
            reply_markup=InlineKeyboardMarkup(back_btn), parse_mode="HTML"
        )

    elif data == "panel_bl_remove":
        context.user_data['panel_awaiting'] = 'bl_remove'
        await query.edit_message_text(
            "➖ <b>Убрать из ЧС</b>\n\nОтправьте <b>Telegram ID</b> пользователя:",
            reply_markup=InlineKeyboardMarkup(back_btn), parse_mode="HTML"
        )

    # ─── ПРОВЕРКА НИКА ───
    elif data == "panel_check_user":
        context.user_data['panel_awaiting'] = 'check_user'
        await query.edit_message_text(
            "🔍 <b>Проверка пользователя</b>\n\nОтправьте <b>Telegram ID</b> или <b>@username</b>:",
            reply_markup=InlineKeyboardMarkup(back_btn), parse_mode="HTML"
        )


async def handle_panel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстового ввода для панели владельца"""
    from database.db_friend import (
        is_admin, add_admin, remove_admin,
        is_blacklisted, add_to_blacklist, remove_from_blacklist,
        get_user, get_user_by_username
    )
    from config import OWNER_ID

    awaiting = context.user_data.get('panel_awaiting')
    if not awaiting:
        return False  # не наш ввод

    if not await _is_owner_or_deputy(update.effective_user.id):
        return False

    text = update.message.text.strip()
    context.user_data.pop('panel_awaiting', None)

    # ─── ДОБАВИТЬ АДМИНА ───
    if awaiting == 'admin_add':
        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text("❌ Введите числовой Telegram ID.")
            return True
        if target_id == OWNER_ID:
            await update.message.reply_text("⛔ Невозможно изменить роль владельца.")
            return True
        await add_admin(target_id, added_by=OWNER_ID)
        await update.message.reply_text(f"✅ Пользователь <code>{target_id}</code> назначен администратором.",
                                        parse_mode="HTML")

    # ─── УДАЛИТЬ АДМИНА ───
    elif awaiting == 'admin_remove':
        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text("❌ Введите числовой Telegram ID.")
            return True
        if target_id == OWNER_ID:
            await update.message.reply_text("⛔ Невозможно удалить владельца из списка администраторов.")
            return True
        await remove_admin(target_id)
        await update.message.reply_text(f"✅ Пользователь <code>{target_id}</code> удалён из администраторов.",
                                        parse_mode="HTML")

    # ─── НАЗНАЧИТЬ ЗАМА ───
    elif awaiting == 'deputy_add':
        from database.db_friend import add_deputy, is_deputy
        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text("❌ Введите числовой Telegram ID.")
            return True
        if target_id == OWNER_ID:
            await update.message.reply_text("⛔ Владельцу нельзя назначить роль зама.")
            return True
        if await is_deputy(target_id):
            await update.message.reply_text("ℹ️ Уже является замом владельца.")
            return True
        target_user = await get_user(target_id)
        if not target_user:
            await update.message.reply_text(f"❌ Пользователь <code>{target_id}</code> не найден в базе.",
                                            parse_mode="HTML")
            return True
        await add_deputy(target_id, added_by=OWNER_ID)
        # Синхронная БД: is_owner=1 чтобы зам видел клавиатуру "Панель Владельца"
        try:
            from database.db_manager import Database
            import os, sqlite3
            sync_db = Database(os.getenv('DB_PATH', 'database/bot_database.db'))
            try:
                sync_db.cursor.execute('ALTER TABLE users ADD COLUMN is_owner INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass
            sync_db.cursor.execute('UPDATE users SET is_owner = 1 WHERE user_id = ?', (target_id,))
            sync_db.conn.commit()
            sync_db.conn.close()
        except Exception as e:
            logger.warning(f"Could not sync deputy to main DB: {e}")
        name = target_user.get('username') or target_user.get('first_name') or target_id
        await update.message.reply_text(
            f"✅ @{name} (<code>{target_id}</code>) назначен <b>Замом Владельца</b>.\n"
            f"Теперь видит полную Панель Владельца.",
            parse_mode="HTML")

    # ─── СНЯТЬ ЗАМА ───
    elif awaiting == 'deputy_remove':
        from database.db_friend import remove_deputy, is_deputy
        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text("❌ Введите числовой Telegram ID.")
            return True
        if not await is_deputy(target_id):
            await update.message.reply_text("ℹ️ Этот пользователь не является замом.")
            return True
        target_user = await get_user(target_id)
        await remove_deputy(target_id)
        # Синхронная БД: вернуть is_owner=0
        try:
            from database.db_manager import Database
            import os
            sync_db = Database(os.getenv('DB_PATH', 'database/bot_database.db'))
            sync_db.cursor.execute('UPDATE users SET is_owner = 0 WHERE user_id = ?', (target_id,))
            sync_db.conn.commit()
            sync_db.conn.close()
        except Exception as e:
            logger.warning(f"Could not sync deputy removal to main DB: {e}")
        name = (target_user.get('username') or target_user.get('first_name') or target_id) if target_user else target_id
        await update.message.reply_text(
            f"✅ @{name} (<code>{target_id}</code>) снят с поста зама → обычный админ.",
            parse_mode="HTML")

    # ─── ДОБАВИТЬ В ЧС: сначала ждём ID, потом причину ───
    elif awaiting == 'bl_add':
        try:
            target_id = int(text)
            context.user_data['bl_add_id'] = target_id
            context.user_data['panel_awaiting'] = 'bl_add_reason'
            await update.message.reply_text(
                f"📝 Теперь отправьте <b>причину</b> блокировки для <code>{target_id}</code>:",
                parse_mode="HTML"
            )
        except ValueError:
            await update.message.reply_text("❌ Введите числовой Telegram ID.")
        return True

    elif awaiting == 'bl_add_reason':
        target_id = context.user_data.pop('bl_add_id', None)
        if not target_id:
            return True
        await add_to_blacklist(target_id, reason=text, admin_id=OWNER_ID)
        await update.message.reply_text(
            f"🚫 Пользователь <code>{target_id}</code> добавлен в ЧС.\nПричина: {html.escape(text)}",
            parse_mode="HTML"
        )

    # ─── УДАЛИТЬ ИЗ ЧС ───
    elif awaiting == 'bl_remove':
        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text("❌ Введите числовой Telegram ID.")
            return True
        await remove_from_blacklist(target_id)
        await update.message.reply_text(f"✅ Пользователь <code>{target_id}</code> удалён из ЧС.",
                                        parse_mode="HTML")

    # ─── ПРОВЕРКА ПОЛЬЗОВАТЕЛЯ (4.2.3) ───
    elif awaiting == 'check_user':
        from config import CHAT_ID

        # Определяем способ ввода и получаем данные
        search_by_id = False
        user_data = None

        if text.startswith('#user'):
            # Формат #user123456789
            raw = text[5:].strip()
            try:
                tg_id = int(raw)
                user_data = await get_user(tg_id)
                search_by_id = True
            except ValueError:
                await update.message.reply_text("❌ Неверный формат. Используйте #user123456789 или @username.")
                return True
        elif text.startswith('@'):
            user_data = await get_user_by_username(text.lstrip('@'))
            search_by_id = False
        else:
            # Просто число
            try:
                tg_id = int(text)
                user_data = await get_user(tg_id)
                search_by_id = True
            except ValueError:
                await update.message.reply_text("❌ Введите #userID, числовой ID или @username.")
                return True

        # Если не нашли в базе — пробуем через Telegram API (только если есть username)
        tg_member = None
        resolved_id = user_data['tg_id'] if user_data else None

        if user_data:
            # Проверяем членство в чате
            try:
                tg_member = await context.bot.get_chat_member(CHAT_ID, user_data['tg_id'])
            except Exception:
                tg_member = None

        in_chat = tg_member and tg_member.status not in ('left', 'kicked', 'banned')

        # Актуальное имя и ник из Telegram (если в чате)
        actual_first = user_data.get('first_name') or '' if user_data else ''
        actual_last = user_data.get('last_name') or '' if user_data else ''
        actual_username = user_data.get('username') if user_data else None
        if tg_member and hasattr(tg_member, 'user'):
            actual_first = tg_member.user.first_name or actual_first
            actual_last = tg_member.user.last_name or actual_last
            actual_username = tg_member.user.username or actual_username

        full_name = html.escape(f"{actual_first} {actual_last}".strip() or '—')
        user_link = f'<a href="tg://user?id={resolved_id}">{full_name}</a>' if resolved_id else full_name
        nik_str = f"@{actual_username}" if actual_username else "не указан"
        uid_str = f"#user{resolved_id}" if resolved_id else "неизвестен"
        q_name = user_data.get('q_name') if user_data else None
        anketa_name = html.escape(q_name) if q_name else "не заполнял"
        anketa_status = "✅ Заполнена" if (user_data and user_data.get('q_name')) else "❌ Не заполнена"
        chat_status = "✅ В чате" if in_chat else "❌ Не в чате"

        if not user_data and not tg_member:
            await update.message.reply_text(
                f"🔍 Пользователь <b>{html.escape(text)}</b> не найден ни в базе, ни в чате.",
                parse_mode="HTML"
            )
            return True

        await update.message.reply_text(
            f"🔍 <b>Проверка пользователя</b>\n\n"
            f"Имя: {anketa_name}\n"
            f"Пользователь: {user_link}\n"
            f"Ник: {nik_str}\n"
            f"ID: <code>{uid_str}</code>\n"
            f"Статус в чате: {chat_status}\n"
            f"Анкета: {anketa_status}",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    return True


async def continue_reg_callback(update, context):
    query = update.callback_query
    await query.answer()
    
    # Мы просто предлагаем юзеру нажать /register снова, 
    # а в коде /register мы сделаем проверку на сохраненные данные
    await query.message.reply_text("Давай продолжим! Нажми /register, и мы начнем с того места, где ты остановился.")

async def format_unified_app(user_id, app_id, event_tag, admin_user=None, rejection_reason=None, context=None):
    from database.db_friend import get_user, get_application
    from config import CHAT_ID
    
    user_reg = await get_user(user_id)
    # Пытаемся достать данные из основной базы через context.bot_data
    main_db = context.bot_data.get('db')
    user_main = main_db.get_user(user_id) if main_db else None

    # Блок Б: Новый или Возвращение
    # Если у юзера в базе есть дата выхода или он уже был в основной базе - #Возвращение
    is_returning = False
    if user_reg and user_reg.get('last_exit_at'): is_returning = True
    status_tag = "#Возвращение" if is_returning else "#Новый"

    # Блок В: Ссылки и ID
    # Ссылка на группу
    group_link = f'<a href="https://t.me/c/{str(CHAT_ID)[4:]}/1">Чат Pulse</a>' # Упрощенно
    # Ссылка на пользователя
    user_name = html.escape(f"{user_reg.get('first_name') or ''} {user_reg.get('last_name') or ''}".strip() or "Пользователь")
    user_link = f'<a href="tg://user?id={user_id}">{user_name}</a>'
    
    # Сборка текста
    text = f"{event_tag}\n" # Блок А
    text += f"{status_tag}\n\n" # Блок Б
    
    text += f"Группа: {group_link}\n"
    text += f"Пользователь: {user_link}\n"
    text += f"Никнейм: @{user_reg.get('username') or 'null'}\n"
    text += f"ID-пользователя: <code>#user{user_id}</code>\n"
    
    if admin_user:
        text += f"Администратор: @{admin_user.username or admin_user.id}\n"
    
    text += "\nБлок Г (Анкета):\n"
    text += f"Имя: {user_reg.get('q_name', '—')}\n"
    text += f"Возраст: {user_reg.get('q_age', '—')}\n"
    text += f"Город: {user_reg.get('q_city', '—')}\n"
    text += f"Терапия: {user_reg.get('q_therapy', '—')}\n"

    if rejection_reason:
        text += f"\nБлок Д (Отказ):\nПричина: {rejection_reason}"

    return text    