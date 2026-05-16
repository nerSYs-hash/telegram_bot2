import html
import logging
import pytz
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from database.db_friend import get_user, create_user, update_user, create_application, save_application_message_id, get_all_admins, add_application_message
from config import OWNER_ID, ADMIN_CHAT_ID, APPLICATIONS_THREAD_ID

logger = logging.getLogger(__name__)

WELCOME, RULES, NAME, AGE, BIRTH_DATE, CITY, THERAPY, REF_CODE = range(8)

# Тексты кнопок reply-клавиатуры, которые не должны приниматься как ответы анкеты
_REPLY_KEYBOARD_TEXTS = {
    "👤 Профиль", "💰 Баланс", "📊 Курс",
    "👑 Панель Владельца", "📋 Новые заявки", "❓ FAQ",
    "📋 Меню", "🏆 ТОП-5", "🎯 Активности",
    "🏦 Центробанк", "❣️ Pulse BBS",
}


def _is_button_text(text: str) -> bool:
    """Проверяет, является ли текст нажатием reply-кнопки."""
    return text.strip() in _REPLY_KEYBOARD_TEXTS


def _build_form(data: dict, next_question: str, keyboard=None) -> str:
    """Строит текст анкеты с заполненными полями и следующим вопросом."""
    lines = ["📋 <b>Анкета регистрации</b>\n"]
    if data.get('reg_name'):
        lines.append(f"А. Имя: <b>{data['reg_name']}</b> ✅")
    if data.get('reg_age') is not None:
        lines.append(f"Б. Возраст: <b>{data['reg_age']}</b> ✅")
    if data.get('reg_city'):
        lines.append(f"В. Город: <b>{data['reg_city']}</b> ✅")
    if data.get('reg_therapy'):
        lines.append(f"Г. Терапия: <b>{data['reg_therapy']}</b> ✅")
    lines.append(f"\n✍️ {next_question}")
    return "\n".join(lines)


async def _edit_form(context, chat_id: int, msg_id: int, text: str, keyboard=None):
    """Редактирует окно анкеты."""
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        err = str(e)
        if "Message is not modified" in err:
            pass  # нормально при двойном нажатии
        else:
            logger.warning(f"_edit_form error: {err}")


async def _delete_user_msg(message):
    """Удаляет сообщение пользователя."""
    try:
        await message.delete()
    except Exception:
        pass


WELCOME_TEXT = (
    "Приветствуем, {name}!\n"
    "Ты на пороге входа в чат <b>PULSE 4ever 18+</b>\n\n"
    "<b>ЗДЕСЬ ТЫ:</b>\n"
    "🔥Найдёшь друзей МСМ, которые реально поймут\n"
    "🔥Закрутишь роман или просто приятное общение\n"
    "🔥Будешь в курсе всего самого интересного\n"
    "🔥Найдешь интересную информацию, касающуюся темы ВИЧ.\n\n"
    "Чат не является сообществом ЛГБТ*, не призывает и не пропагандирует "
    "никакие нетрадиционные ценности и соблюдает законодательство РФ.\n\n"
    "Если ты не являешься мужчиной практикующим секс с мужчиной и ты не достиг "
    "18-летия, незамедлительно прекрати работу с ботом!\n\n"
    "<i>*ЛГБТ - запрещено на территории РФ.</i>"
)

RULES_TEXT = (
    '<b>ПРАВИЛА ЧАТА "PULSE ❣️"</b>\n\n'
    "При заполнении анкеты, вы подтверждаете:\n"
    "✔️ Положительный статус;\n"
    "✔️ Совершенолетие (18+);\n"
    "✔️ Относитесь к МСМ-группе.\n\n"
    "Если это не про вас — немедленно покиньте чат.\n"
    "——————————\n\n"
    "<b>❌ Строгие запреты:</b>\n\n"
    "1. ВИЧ- — если знаете о нарушении, сообщите админам.\n"
    "2. Оскорбления, конфликты — никаких разборок и хамства.\n"
    "3. Запрещённые темы: расизм, экстремизм, наркотики, насилие, религия, политика.\n"
    "4. ЛГБТ*-атрибутика — даже намёки (флаги, символы и прочее).\n"
    "5. 18+ контент — порно, эротика (включая GIF/анимации).\n"
    "6. Спам, флуд, агрессия, попрошайничество.\n"
    "7. Реклама (в том числе затрагивание тем других чатов, ресурсов) и ссылки — только с разрешения админов.\n"
    "8. Личная информация о третьих лицах без их согласия, в том числе личная переписка и фотографии участников чата!\n"
    "9. Несовершеннолетние — возраст проверяется (при подозрениях или жалобах!)\n"
    "10. Caps Lock — злоупотребление = мут.\n"
    "——————————\n\n"
    "Незнание правил не освобождает от ответственности и ведут к бану.\n"
    "<i>*ЛГБТ - запрещено на территории РФ.</i>"
)


async def start_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db_friend import is_blacklisted, get_blacklist_reason
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Друг"

    # ── V1.17.0b6 Deep link `join_<ws_id>` — multi-tenancy onboarding ──
    # Для Pulse-сообщества (is_pulse_themed=1) → продолжаем обычную анкету.
    # Для не-Pulse → простой welcome без анкеты (модуль регистрации = #4).
    if context.args and context.args[0].startswith('join_'):
        try:
            target_ws_id = int(context.args[0][5:])
        except (ValueError, TypeError):
            await update.message.reply_text("❌ Некорректная ссылка.")
            return ConversationHandler.END

        main_db = context.bot_data.get('db')
        if main_db:
            from database.db_workspaces import get_workspace
            ws = get_workspace(main_db.conn, target_ws_id)
            if not ws:
                await update.message.reply_text("❌ Сообщество не найдено.")
                return ConversationHandler.END
            if not ws.is_pulse_themed:
                await update.message.reply_text(
                    f"👋 Добро пожаловать в «{ws.name}»!\n\n"
                    f"Скоро здесь будет регистрационная анкета этого сообщества. "
                    f"Пока — подожди приглашение от админов."
                )
                return ConversationHandler.END
        # is_pulse_themed=True → fall through к обычной Pulse-анкете

    # ── Deep link жалобы BBS: показываем меню выбора причины, минуя регистрацию ──
    if context.args and context.args[0].startswith('report_'):
        import html as _html
        try:
            reported_user_id = int(context.args[0].replace('report_', ''))
        except (ValueError, TypeError):
            await update.message.reply_text("❌ Некорректная ссылка для жалобы.")
            return ConversationHandler.END

        context.user_data['reporting_user_id'] = reported_user_id

        main_db = context.bot_data.get('db')
        reported_name = str(reported_user_id)
        if main_db:
            reported_user = main_db.get_user(reported_user_id)
            if reported_user:
                try:
                    reported_name = _html.escape(
                        reported_user['username'] or reported_user['first_name'] or str(reported_user_id)
                    )
                except (KeyError, IndexError):
                    pass

        header = f"🚨 <b>Жалоба на пользователя</b>\n\n👤 Нарушитель: @{reported_name}\n\n"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔞 Спам / Реклама",            callback_data="report_reason_spam")],
            [InlineKeyboardButton("🤡 Фейк / Мошенник",           callback_data="report_reason_fake")],
            [InlineKeyboardButton("🤬 Оскорбления / Токсичность", callback_data="report_reason_toxic")],
            [InlineKeyboardButton("🔞 Откровенный контент",       callback_data="report_reason_nsfw")],
            [InlineKeyboardButton("❌ Отмена",                    callback_data="report_cancel")],
        ])
        await update.message.reply_text(
            header + "Выберите причину жалобы:",
            parse_mode='HTML',
            reply_markup=kb,
        )
        return ConversationHandler.END

    # Удаляем команду /register или /start
    if update.message:
        await _delete_user_msg(update.message)

    # Проверка: регистрация включена?
    main_db = context.bot_data.get('db')
    if main_db and not main_db.is_feature_enabled('registration'):
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "🚫 <b>Регистрация временно закрыта.</b>\n\n"
                "Набор новых участников приостановлен администрацией чата.\n"
                "Следи за обновлениями!"
            ),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    # Проверка чёрного списка
    if await is_blacklisted(user_id):
        reason = await get_blacklist_reason(user_id)
        try:
            owner_chat = await context.bot.get_chat(OWNER_ID)
            owner_name = owner_chat.full_name or str(OWNER_ID)
        except Exception:
            owner_name = str(OWNER_ID)
        blacklist_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✉️ Написать администратору", url=f"tg://user?id={OWNER_ID}")]
        ])
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"{user_name}, мы сожалеем, но ты заблокирован администрацией "
                f"чата Pulse 4ever из-за: {reason}.\n\n"
                f"Если считаешь, что попал в ЧС по ошибке — нажми кнопку ниже."
            ),
            parse_mode="HTML",
            reply_markup=blacklist_kb
        )
        return ConversationHandler.END

    user = await get_user(user_id)

    # Проверка фактического членства в чате (железобетонная — через API)
    from config import CHAT_ID
    main_db = context.bot_data.get('db')
    from utils.membership import verify_chat_membership
    # H3: гейт по workspace юзера (ЛС регистрации → резолв по членству),
    # за флагом H_RUNTIME_WS. Флаг OFF / новый аппликант без членства →
    # CHAT_ID байт-в-байт. main_db=None → старое поведение.
    from bot_core.ws_resolver import resolve_gate_chat
    _gate_chat = (
        resolve_gate_chat(main_db.conn, context, CHAT_ID, user_id=user_id)
        if main_db else CHAT_ID
    )
    is_member = await verify_chat_membership(context.bot, _gate_chat, user_id, db=main_db)

    # Проверка блокировки по возрасту (< 18)
    if user and user.get('status') == 'blocked':
        blocked_until = user.get('blocked_until')
        if blocked_until:
            try:
                unlock_date = datetime.strptime(blocked_until, "%d.%m.%Y").date()
                if date.today() < unlock_date:
                    days_left = (unlock_date - date.today()).days
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"⛔️ <b>Доступ в чат разрешён только с 18 лет.</b>\n\n"
                            f"🔓 Доступ будет открыт: {blocked_until}\n"
                            f"⏳ Осталось дней: {days_left}\n\n"
                            f"Мы уведомим тебя, когда это произойдет."
                        ),
                        parse_mode="HTML"
                    )
                    return ConversationHandler.END
                else:
                    # Дата разблокировки прошла — сбрасываем статус
                    await update_user(user_id, status='not_in_chat', blocked_until=None)
            except ValueError:
                pass

    # Если пользователь РЕАЛЬНО в чате — перенаправляем в меню
    if is_member:
        # Закрываем все висящие заявки (если есть)
        try:
            from database.db_friend import close_user_applications
            await close_user_applications(user_id, status='approved')
        except Exception:
            pass

        if main_db:
            from handlers.commands.system_commands import get_main_reply_keyboard
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Ты уже участник чата! Нижнее меню восстановлено.",
                reply_markup=get_main_reply_keyboard(main_db, user_id, OWNER_ID)
            )
        else:
            logger.error("main_db is None in start_reg — bot_data['db'] not set!")
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Ты уже участник чата! Используй /menu для открытия меню."
            )
        return ConversationHandler.END

    # Если есть активная заявка на рассмотрении — сообщаем
    if user and user.get('status') in ('pending', 'in_work', 'locked'):
        from database.db_friend import get_user_pending_application
        pending_app = await get_user_pending_application(user_id)
        if pending_app:
            await context.bot.send_message(
                chat_id=user_id,
                text="⏳ Твоя анкета ещё на проверке у администраторов. Пожалуйста, подожди!"
            )
            return ConversationHandler.END

    # ═══ ВОЗВРАЩАЮЩИЙСЯ ЮЗЕР: уже есть q_name ИЛИ одобренная заявка ═══
    # Не прогоняем через анкету заново — генерируем ссылку для входа
    has_q_name = bool(user and user.get('q_name'))

    # Fallback: одобренная заявка в db_friend.applications (если q_name по какой-то причине пуст)
    has_approved_app = False
    if not has_q_name:
        try:
            from database.db_friend import db_pool
            from constants import ApplicationStatus
            async with db_pool.get_connection() as _db:
                async with _db.execute(
                    "SELECT 1 FROM applications WHERE user_id = ? AND status = ? LIMIT 1",
                    (user_id, ApplicationStatus.APPROVED)
                ) as _cur:
                    has_approved_app = bool(await _cur.fetchone())
        except Exception as e:
            logger.error(f"approved_app check failed in start_reg for {user_id}: {e}")

    if has_q_name or has_approved_app:
        # Проверяем не забанен ли в чате
        tg_status = None
        try:
            cm = await context.bot.get_chat_member(CHAT_ID, user_id)
            tg_status = cm.status
        except Exception:
            pass

        if tg_status == 'kicked':
            owner_link = f'<a href="tg://user?id={OWNER_ID}">владельца чата</a>'
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🚫 К сожалению, ты был заблокирован в чате Pulse 4ever.\n\n"
                    f"Самостоятельное возвращение невозможно. Если считаешь, что блокировка "
                    f"была ошибочной — напиши {owner_link}, чтобы уточнить возможность возвращения."
                ),
                parse_mode="HTML"
            )
            return ConversationHandler.END

        # Генерируем одноразовую invite-ссылку для возвращения
        try:
            from database.db_friend import create_invite_link as _save_invite
            display_name = (user.get('q_name') if user else None) or user_name
            invite_obj = await context.bot.create_chat_invite_link(
                CHAT_ID,
                member_limit=1,
                name=f"ret_{user_id}"[:32],
            )
            invite_url = invite_obj.invite_link
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"👋 С возвращением, {display_name}!\n\n"
                    f"Рады снова видеть тебя в Pulse 4ever 🤍\n\n"
                    f"🔗 Твоя персональная ссылка для входа в чат:\n{invite_url}\n\n"
                    f"⚠️ Ссылка одноразовая — действует только для тебя и "
                    f"сгорит сразу после использования."
                )
            )
            await _save_invite(user_id, invite_url)
            logger.info(f"Return invite sent (start_reg) to {user_id}")
        except Exception as e:
            logger.error(f"start_reg: error creating return invite for {user_id}: {e}")
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Не удалось создать ссылку для входа. Обратись к администратору."
            )
        return ConversationHandler.END

    # Если уже есть незавершённая анкета — восстанавливаем окно
    if user and user.get('questionnaire_state'):
        state = user['questionnaire_state']
        data = context.user_data
        questions = {
            "AGE": "Б. Сколько тебе полных лет?",
            "CITY": "В. В каком городе ты проживаешь?",
            "THERAPY": "Г. Какую терапию ты принимаешь?\n(Укажи точное наименование препаратов)",
            "REF_CODE": "Д. Реф. код (ник пользователя)\nЕсли тебя кто-то пригласил, введи его ник. Если нет — нажми кнопку.",
        }
        if user.get('q_name') and 'reg_name' not in data:
            data['reg_name'] = user['q_name']
        if user.get('q_age') and 'reg_age' not in data:
            data['reg_age'] = user['q_age']
        if user.get('q_city') and 'reg_city' not in data:
            data['reg_city'] = user['q_city']
        if user.get('q_therapy') and 'reg_therapy' not in data:
            data['reg_therapy'] = user['q_therapy']

        next_q = questions.get(state, "А. Как тебя зовут?")
        keyboard = None
        if state == "REF_CODE":
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_ref")]])

        sent = await context.bot.send_message(
            chat_id=user_id,
            text=_build_form(data, next_q),
            parse_mode="HTML",
            reply_markup=keyboard
        )
        context.user_data['reg_msg_id'] = sent.message_id
        state_map = {"AGE": AGE, "BIRTH_DATE": BIRTH_DATE, "CITY": CITY, "THERAPY": THERAPY, "REF_CODE": REF_CODE}
        return state_map.get(state, NAME)

    if not user:
        await create_user(user_id, update.effective_user.username, user_name, "")

    # 1.1 Приветствие с кнопкой "Мне уже есть 18"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Мне уже есть 18", callback_data="reg_age_confirm")]
    ])
    sent = await context.bot.send_message(
        chat_id=user_id,
        text=WELCOME_TEXT.format(name=user_name),
        parse_mode="HTML",
        reply_markup=keyboard
    )
    context.user_data['reg_msg_id'] = sent.message_id
    return WELCOME


async def welcome_age_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка '18+' нажата → меняем на 'Правила чата'"""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Правила чата", callback_data="reg_show_rules")]
    ])
    await query.edit_message_reply_markup(reply_markup=keyboard)
    return RULES


async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка 'Правила чата' → показываем правила с кнопкой 'Подать заявку'"""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Подать заявку", callback_data="reg_start_form")]
    ])
    msg_id = context.user_data.get('reg_msg_id')
    await _edit_form(context, query.from_user.id, msg_id, RULES_TEXT, keyboard)
    return RULES


async def start_form_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка 'Подать заявку' → начинаем анкету"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    msg_id = context.user_data.get('reg_msg_id')
    text = _build_form({}, "А. Как тебя зовут?")
    await _edit_form(context, user_id, msg_id, text)
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if _is_button_text(update.message.text):
        await _delete_user_msg(update.message)
        return NAME
    await _delete_user_msg(update.message)
    name = update.message.text.strip()
    if len(name) < 2:
        msg_id = context.user_data.get('reg_msg_id')
        if msg_id:
            await _edit_form(context, user_id, msg_id,
                _build_form(context.user_data, "А. Как тебя зовут?\n\n❌ Имя должно быть не менее 2 символов."))
        return NAME
    context.user_data['reg_name'] = name
    await update_user(user_id, questionnaire_state="AGE", q_name=name)

    msg_id = context.user_data.get('reg_msg_id')
    if msg_id:
        await _edit_form(context, user_id, msg_id, _build_form(context.user_data, "Б. Сколько тебе полных лет?"))
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    age_text = update.message.text

    if _is_button_text(age_text):
        await _delete_user_msg(update.message)
        return AGE

    if not age_text.isdigit():
        await _delete_user_msg(update.message)
        msg_id = context.user_data.get('reg_msg_id')
        if msg_id:
            await _edit_form(context, user_id, msg_id,
                _build_form(context.user_data, "Б. Сколько тебе полных лет?\n\n❌ Введи возраст числом."))
        return AGE

    age = int(age_text)
    await _delete_user_msg(update.message)

    if age < 1 or age > 120:
        msg_id = context.user_data.get('reg_msg_id')
        if msg_id:
            await _edit_form(context, user_id, msg_id,
                _build_form(context.user_data, "Б. Сколько тебе полных лет?\n\n❌ Укажи корректный возраст (от 1 до 120)."))
        return AGE

    context.user_data['reg_age'] = age
    await update_user(user_id, q_age=age)

    if age < 18:
        await update_user(user_id, questionnaire_state="BIRTH_DATE")
        msg_id = context.user_data.get('reg_msg_id')
        if msg_id:
            await _edit_form(context, user_id, msg_id,
                _build_form(context.user_data,
                    "⚠️ Доступ разрешён только совершеннолетним.\n\n"
                    "Е. Укажи точную дату рождения в формате ДД.ММ.ГГГГ\n(Например: 15.05.2010)"))
        return BIRTH_DATE

    await update_user(user_id, questionnaire_state="CITY")
    msg_id = context.user_data.get('reg_msg_id')
    if msg_id:
        await _edit_form(context, user_id, msg_id,
            _build_form(context.user_data, "В. В каком городе ты проживаешь?"))
    return CITY


async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text.strip()
    user_id = update.effective_user.id
    if _is_button_text(date_text):
        await _delete_user_msg(update.message)
        return BIRTH_DATE
    await _delete_user_msg(update.message)
    msg_id = context.user_data.get('reg_msg_id')

    try:
        birth_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        today = date.today()

        if birth_date > today:
            if msg_id:
                await _edit_form(context, user_id, msg_id,
                    _build_form(context.user_data,
                        "Е. Укажи точную дату рождения в формате ДД.ММ.ГГГГ\n\n"
                        "❌ Дата не может быть в будущем!"))
            return BIRTH_DATE

        real_age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

        if real_age < 18:
            unlock_date = (birth_date + relativedelta(years=18)).strftime("%d.%m.%Y")
            await update_user(user_id, birth_date=date_text, blocked_until=unlock_date,
                              status='blocked', questionnaire_state=None)
            if msg_id:
                await _edit_form(context, user_id, msg_id,
                    f"⛔️ <b>Доступ в чат разрешён только с 18 лет.</b>\n\n"
                    f"🔓 Доступ будет открыт: {unlock_date}\n"
                    f"Мы уведомим тебя, когда это произойдет.")
            return ConversationHandler.END
        else:
            context.user_data['reg_age'] = real_age
            await update_user(user_id, questionnaire_state="CITY")
            if msg_id:
                await _edit_form(context, user_id, msg_id,
                    _build_form(context.user_data, "В. В каком городе ты проживаешь?"))
            return CITY

    except ValueError:
        if msg_id:
            await _edit_form(context, user_id, msg_id,
                _build_form(context.user_data,
                    "Е. Укажи точную дату рождения в формате ДД.ММ.ГГГГ\n\n"
                    "❌ Неверный формат! Например: 01.01.2010"))
        return BIRTH_DATE


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if _is_button_text(update.message.text):
        await _delete_user_msg(update.message)
        return CITY
    await _delete_user_msg(update.message)
    city = update.message.text.strip()
    if len(city) < 2:
        msg_id = context.user_data.get('reg_msg_id')
        if msg_id:
            await _edit_form(context, user_id, msg_id,
                _build_form(context.user_data, "В. В каком городе ты проживаешь?\n\n❌ Название города — минимум 2 символа."))
        return CITY
    context.user_data['reg_city'] = city
    await update_user(user_id, questionnaire_state="THERAPY", q_city=city)

    msg_id = context.user_data.get('reg_msg_id')
    if msg_id:
        await _edit_form(context, user_id, msg_id,
            _build_form(context.user_data,
                "Г. Какую терапию ты принимаешь?\n(Укажи точное наименование препаратов)"))
    return THERAPY


async def get_therapy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if _is_button_text(update.message.text):
        await _delete_user_msg(update.message)
        return THERAPY
    await _delete_user_msg(update.message)
    therapy = update.message.text.strip()
    if len(therapy) < 2:
        msg_id = context.user_data.get('reg_msg_id')
        if msg_id:
            await _edit_form(context, user_id, msg_id,
                _build_form(context.user_data,
                    "Г. Какую терапию ты принимаешь?\n\n❌ Укажи терапию — минимум 2 символа."))
        return THERAPY
    context.user_data['reg_therapy'] = therapy
    await update_user(user_id, questionnaire_state="REF_CODE", q_therapy=therapy)

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_ref")]])
    msg_id = context.user_data.get('reg_msg_id')
    if msg_id:
        await _edit_form(context, user_id, msg_id,
            _build_form(context.user_data,
                "Д. Реф. код (ник пользователя)\n"
                "Если тебя кто-то пригласил, введи его ник. Если нет — нажми кнопку."),
            keyboard=keyboard)
    return REF_CODE


async def get_ref_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if _is_button_text(update.message.text):
        await _delete_user_msg(update.message)
        return REF_CODE
    await _delete_user_msg(update.message)

    raw = (update.message.text or '').strip()
    # Чистим: убираем @, пробелы; сравниваем case-insensitive
    username_clean = raw.lstrip('@').strip().lower()

    if not username_clean:
        # Пустой ввод — пропускаем как "без реферала"
        return await finish_registration(update, context, None)

    # Ищем пользователя по username — сначала в db_friend, потом в основной БД
    referrer_id = None
    try:
        from database.db_friend import get_user_by_username as _get_by_uname
        ref_user = await _get_by_uname(username_clean)
        if ref_user:
            referrer_id = ref_user.get('tg_id')
    except Exception as e:
        logger.warning(f"get_ref_code db_friend lookup failed: {e}")

    if not referrer_id:
        # Fallback — ищем в основной БД
        try:
            main_db = context.bot_data.get('db')
            if main_db:
                main_db.cursor.execute(
                    "SELECT user_id FROM users WHERE LOWER(username) = ? LIMIT 1",
                    (username_clean,)
                )
                row = main_db.cursor.fetchone()
                if row:
                    referrer_id = row['user_id']
        except Exception as e:
            logger.warning(f"get_ref_code main_db lookup failed: {e}")

    if not referrer_id:
        # Не нашли — даём шанс ввести заново или пропустить
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_ref")]])
        msg_id = context.user_data.get('reg_msg_id')
        if msg_id:
            await _edit_form(
                context, user_id, msg_id,
                _build_form(
                    context.user_data,
                    f"Д. Реф. код (ник пользователя)\n\n"
                    f"❌ Пользователь @{html.escape(username_clean)} не найден в Pulse 4ever.\n"
                    f"Введи корректный @username или пропусти."
                ),
                keyboard=keyboard,
            )
        return REF_CODE

    # Защита: не разрешаем ссылаться на себя
    if referrer_id == user_id:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_ref")]])
        msg_id = context.user_data.get('reg_msg_id')
        if msg_id:
            await _edit_form(
                context, user_id, msg_id,
                _build_form(
                    context.user_data,
                    "Д. Реф. код (ник пользователя)\n\n"
                    "❌ Нельзя пригласить самого себя. Введи другого пользователя или пропусти."
                ),
                keyboard=keyboard,
            )
        return REF_CODE

    return await finish_registration(update, context, referrer_id)


async def skip_ref_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await finish_registration(update, context, None)


async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE, ref_code):
    """ref_code теперь — это integer referrer_id (или None)."""
    user_id = update.effective_user.id
    await update_user(user_id, questionnaire_state=None)
    data = context.user_data

    # Приоритет: ref_code из deep-link > ввод на шаге REF_CODE
    deep_link_referrer = context.user_data.pop('pending_ref_referrer_id', None)
    pending_token = context.user_data.pop('pending_ref_token', None)

    final_referrer_id = None
    if deep_link_referrer:
        # Deep-link имеет приоритет — используем его
        final_referrer_id = deep_link_referrer
        # Помечаем токен использованным
        if pending_token:
            try:
                main_db = context.bot_data.get('db')
                if main_db:
                    main_db.use_referral_link(pending_token, user_id)
            except Exception as e:
                logger.warning(f"use_referral_link failed for {pending_token}: {e}")
    elif isinstance(ref_code, int):
        final_referrer_id = ref_code
    # ref_code строкой больше не приходит — get_ref_code конвертирует

    # Берём из context.user_data; если сессия потеряна — подтянем из БД ниже
    reg_name = data.get('reg_name')
    reg_age = data.get('reg_age')
    reg_city = data.get('reg_city')
    reg_therapy = data.get('reg_therapy')

    # Если данные не в сессии — читаем из БД (бот был перезапущен)
    if not all([reg_name, reg_age, reg_city, reg_therapy]):
        db_user = await get_user(user_id)
        if db_user:
            reg_name = reg_name or db_user.get('q_name')
            reg_age = reg_age or db_user.get('q_age')
            reg_city = reg_city or db_user.get('q_city')
            reg_therapy = reg_therapy or db_user.get('q_therapy')

    # Защита от пустой анкеты
    if not all([reg_name, reg_age, reg_city, reg_therapy]):
        logger.warning(f"finish_registration: user {user_id} has incomplete form data, aborting")
        msg_id = context.user_data.get('reg_msg_id')
        err_text = "❌ Не удалось сохранить анкету — некоторые поля пустые. Начни заново: /register"
        if msg_id:
            await _edit_form(context, user_id, msg_id, err_text)
        else:
            await context.bot.send_message(chat_id=user_id, text=err_text)
        return ConversationHandler.END

    await update_user(
        user_id,
        q_name=reg_name,
        q_age=reg_age,
        q_city=reg_city,
        q_therapy=reg_therapy,
        referred_by=final_referrer_id,
        status='pending'
    )

    app_id = await create_application(user_id)

    # Подтягиваем @username реферера для отображения
    referrer_display = 'нет'
    if final_referrer_id:
        try:
            ref_user = await get_user(final_referrer_id)
            if ref_user and ref_user.get('username'):
                referrer_display = f"@{ref_user['username']}"
            else:
                referrer_display = f"ID {final_referrer_id}"
        except Exception:
            referrer_display = f"ID {final_referrer_id}"

    # Обновляем окно анкеты — итоговое сообщение
    msg_id = context.user_data.get('reg_msg_id')
    final_text = (
        f"📋 <b>Анкета регистрации</b>\n\n"
        f"А. Имя: <b>{reg_name}</b> ✅\n"
        f"Б. Возраст: <b>{reg_age}</b> ✅\n"
        f"В. Город: <b>{reg_city}</b> ✅\n"
        f"Г. Терапия: <b>{reg_therapy}</b> ✅\n"
        f"Д. Реф. код: <b>{referrer_display}</b> ✅\n\n"
        f"✅ <b>Анкета отправлена администраторам!</b>\n"
        f"Ожидай уведомления об одобрении."
    )
    if msg_id:
        await _edit_form(context, user_id, msg_id, final_text)
    else:
        await context.bot.send_message(chat_id=user_id, text=final_text, parse_mode="HTML")

    # Карточка для администраторов
    msk = pytz.timezone('Europe/Moscow')
    now_msk = datetime.now(msk).strftime("%d %B %Y г. %H:%M:%S МСК")

    user_data = await get_user(user_id)
    last_rejection = user_data.get('last_rejection_reason') if user_data else None
    block_d = ""
    if last_rejection:
        block_d = (
            f"\n🚨 <b>Внимание! Пользователь уже подавал заявку.</b>\n"
            f"Причина отказа: {last_rejection}\n"
        )

    username_str = f"@{update.effective_user.username}" if update.effective_user.username else "нет"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_app_{user_id}_{app_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_rej_{user_id}_{app_id}"),
            InlineKeyboardButton("⏳ Отложить", callback_data=f"adm_skip_{user_id}_{app_id}"),
        ],
        [InlineKeyboardButton("✉️ Написать в ЛС", url=f"tg://user?id={user_id}")]
    ])

    admin_text = (
        f"📢 <b>НОВАЯ ЗАЯВКА #{app_id}</b>"
        f"{block_d}\n"
        f"👤 Имя: {html.escape(str(reg_name))} | <code>{user_id}</code> | <b>#user{user_id}</b>\n"
        f"🎂 Возраст: {reg_age}\n"
        f"🏙 Город: {html.escape(str(reg_city))}\n"
        f"💊 Терапия: {html.escape(str(reg_therapy))}\n"
        f"🤝 Реферал: {html.escape(str(ref_code)) if ref_code else 'Нет'}\n"
        f"🆔 Никнейм: {username_str}\n\n"
        f"📅 <b>Блок Е:</b>\n"
        f"Дата заявки: {now_msk}"
    )
    # Broadcast: рассылаем карточку заявки в ЛС всем админам и владельцу
    admins = await get_all_admins()
    logger.info(f"Рассылка заявки #{app_id}: получателей {len(admins)}")
    sent_count = 0
    last_sent = None
    for admin in admins:
        admin_id = admin.get('tg_id')
        if not admin_id:
            continue
        try:
            sent = await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            sent_count += 1
            last_sent = sent
            try:
                await add_application_message(app_id, admin_id, admin_id, sent.message_id)
            except Exception as db_err:
                logger.warning(f"Не удалось сохранить message_id заявки #{app_id} для {admin_id}: {db_err}")
        except Exception as e:
            logger.warning(f"Не удалось отправить заявку #{app_id} админу {admin_id}: {e}")
    if last_sent:
        try:
            await save_application_message_id(app_id, last_sent.message_id)
        except Exception:
            pass
    logger.info(f"Заявка #{app_id} разослана {sent_count}/{len(admins)} админам в ЛС")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_id = context.user_data.get('reg_msg_id')
    if msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_user.id,
                message_id=msg_id,
                text="❌ Регистрация отменена.",
                parse_mode="HTML"
            )
        except Exception:
            pass
    await _delete_user_msg(update.message)
    return ConversationHandler.END


registration_conv = ConversationHandler(
    entry_points=[
        CommandHandler("register", start_reg),
        CommandHandler("start", start_reg),
        # Fallback entry points — если бот перезапустился и потерял состояние
        CallbackQueryHandler(welcome_age_confirm, pattern="^reg_age_confirm$"),
        CallbackQueryHandler(show_rules, pattern="^reg_show_rules$"),
        CallbackQueryHandler(start_form_callback, pattern="^reg_start_form$"),
        CallbackQueryHandler(skip_ref_callback, pattern="^skip_ref$"),
    ],
    states={
        WELCOME: [
            CallbackQueryHandler(welcome_age_confirm, pattern="^reg_age_confirm$"),
        ],
        RULES: [
            CallbackQueryHandler(show_rules, pattern="^reg_show_rules$"),
            CallbackQueryHandler(start_form_callback, pattern="^reg_start_form$"),
        ],
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
        BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)],
        CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
        THERAPY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_therapy)],
        REF_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_ref_code),
            CallbackQueryHandler(skip_ref_callback, pattern="^skip_ref$")
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        # /register и /start работают как «жёсткий рестарт» из любого state —
        # иначе застрявший в анкете юзер не может выйти, и его команды уходят
        # в общий message_handler без эффекта.
        CommandHandler("register", start_reg),
        CommandHandler("start", start_reg),
    ],
    per_message=False
)
