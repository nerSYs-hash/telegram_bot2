import html
import asyncio
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
from database.db_friend import (
    approve_application, reject_application, update_user,
    get_user, get_application, create_invite_link
)
from config import CHAT_ID, ADMIN_CHAT_ID, DOSSIER_THREAD_ID
from utils.face_detector import has_human_face

logger = logging.getLogger(__name__)


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
    from handlers.messages.events_logic import get_chat_invite_link

    # Создаём одноразовую ссылку через Telegram API
    class _FakeContext:
        pass
    fake_ctx = _FakeContext()
    fake_ctx.bot = bot

    invite_link = await get_chat_invite_link(fake_ctx, CHAT_ID, CHAT_ID, user_name)
    if not invite_link:
        logger.error(f"Не удалось создать ссылку для {user_id}")
        return None

    # Сохраняем ссылку в БД
    await create_invite_link(user_id, invite_link)

    # Отправляем пуш
    try:
        msg = await bot.send_message(
            chat_id=user_id,
            text=(
                f"{user_name}, ты на пороге входа в чат Pulse 4ever!\n\n"
                f"Просто используй свою личную одноразовую ссылку:\n"
                f"{invite_link}\n\n"
                f"⚠️ Ссылка одноразовая и только для тебя — никому не передавай!"
            )
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

    action = parts[1]  # app, rej или skip
    target_user_id = int(parts[2])
    app_id = int(parts[3])

    main_db = context.bot_data.get('db')

    # Получаем данные заявки и пользователя
    app_data = await get_application(app_id)
    reg_data = await get_user(target_user_id)
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
                username=reg_data.get('username'),
                first_name=reg_data.get('first_name'),
                last_name=reg_data.get('last_name'),
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
            f"ID: <code>{target_user_id}</code>\n\n"
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

        # 5. ДОСЬЕ С ФОТО — отправляем в тред ADMIN_CHAT_ID/DOSSIER_THREAD_ID
        asyncio.create_task(
            _send_dossier(context.bot, target_user_id, card_text, card_kb)
        )

    elif action == "rej":
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

    elif action == "rej_cancel":
        # Отмена ввода причины
        context.user_data.pop('awaiting_reject_reason', None)
        context.user_data.pop('rej_app_id', None)
        context.user_data.pop('rej_user_id', None)
        context.user_data.pop('rej_reg_data', None)
        context.user_data.pop('rej_applied_at', None)
        await query.edit_message_text("↩️ Отклонение отменено. Заявка снова доступна.")

    elif action == "skip":
        await query.edit_message_text(
            f"⏳ <b>Заявка #{app_id} — ОТЛОЖЕНА</b>\n\n"
            f"👤 <code>{target_user_id}</code> пока не уведомлен.\n"
            f"Заявка вернётся в очередь автоматически.",
            parse_mode="HTML"
        )
        
async def handle_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста с причиной отказа от администратора"""
    from database.db_friend import reject_application, update_user
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    if not context.user_data.get('awaiting_reject_reason'):
        return  # не ждём причины — игнорируем

    reason = update.message.text.strip()
    app_id = context.user_data.pop('rej_app_id', None)
    target_user_id = context.user_data.pop('rej_user_id', None)
    reg_data = context.user_data.pop('rej_reg_data', {})
    applied_at = context.user_data.pop('rej_applied_at', '—')
    context.user_data.pop('awaiting_reject_reason', None)

    if not app_id or not target_user_id:
        return

    # Сохраняем отказ в БД
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

    # 3.4.2 Обновляем сообщение в чате администраторов
    await update.message.reply_text(
        f"❌ <b>#Отказ — Заявка #{app_id}</b>\n\n"
        f"👤 {html.escape(reg_data.get('q_name') or '—')} | "
        f"<code>{target_user_id}</code>\n"
        f"Никнейм: @{reg_data.get('username') or 'нет'}\n\n"
        f"📋 <b>Анкета:</b>\n"
        f"Имя: {html.escape(reg_data.get('q_name') or '—')}\n"
        f"Возраст: {reg_data.get('q_age') or '—'}\n"
        f"Город: {html.escape(reg_data.get('q_city') or '—')}\n"
        f"Терапия: {html.escape(reg_data.get('q_therapy') or '—')}\n\n"
        f"📅 Дата заявки: {applied_at}\n\n"
        f"🚫 <b>Причина отказа:</b> {html.escape(reason)}\n\n"
        f"👨‍💼 Обработал: {admin_name}",
        parse_mode="HTML"
    )
    logger.info(f"Application #{app_id} rejected by {update.effective_user.id}, reason: {reason}")


async def send_admin_panel(bot, chat_id: int, is_owner: bool = False):
    """Отправляет панель администратора/владельца в чат"""
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

    await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="HTML")


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

    # Берём следующую свободную заявку
    apps = await get_new_applications(exclude_locked=True)
    if not apps:
        await query.answer("Новых заявок нет.", show_alert=True)
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

    # Блок Д — предыдущий отказ
    last_rejection = reg_data.get('last_rejection_reason')
    block_d = ""
    if last_rejection:
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
        [InlineKeyboardButton("✉️ Написать в ЛС", url=f"tg://user?id={user_id}")],
        [InlineKeyboardButton("📋 Следующая заявка", callback_data="new_app")],
    ])

    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


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

    # Только владелец
    if user_id != OWNER_ID:
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
        admins = await get_all_admins()
        lines = [f"• <code>{a['tg_id']}</code>" for a in admins] if admins else ["— пусто —"]
        text = "👥 <b>Администраторы</b>\n\n" + "\n".join(lines)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить", callback_data="panel_admin_add"),
             InlineKeyboardButton("➖ Удалить", callback_data="panel_admin_remove")],
            *back_btn
        ])
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

    if update.effective_user.id != OWNER_ID:
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