import logging
import pytz
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from database.db_friend import get_user, create_user, update_user, create_application, save_application_message_id
from config import OWNER_ID, ADMIN_CHAT_ID, APPLICATIONS_THREAD_ID

logger = logging.getLogger(__name__)

WELCOME, RULES, NAME, AGE, BIRTH_DATE, CITY, THERAPY, REF_CODE = range(8)


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
        logger.warning(f"_edit_form error: {e}")


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

    # Удаляем команду /register или /start
    if update.message:
        await _delete_user_msg(update.message)

    # Проверка чёрного списка
    if await is_blacklisted(user_id):
        reason = await get_blacklist_reason(user_id)
        try:
            owner_chat = await context.bot.get_chat(OWNER_ID)
            owner_name = owner_chat.full_name or str(OWNER_ID)
        except Exception:
            owner_name = str(OWNER_ID)
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"{user_name}, мы сожалеем, но ты заблокирован администрацией "
                f"чата Pulse 4ever из-за: {reason}.\n\n"
                f"Если считаешь, что попал в ЧС по ошибке, свяжись с администратором: "
                f'<a href="tg://user?id={OWNER_ID}">{owner_name}</a>'
            ),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    user = await get_user(user_id)

    # Проверка фактического членства в чате (is_member)
    try:
        from telegram import ChatMemberStatus
        from config import CHAT_ID
        member = await context.bot.get_chat_member(CHAT_ID, user_id)
        is_member = member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ) or (member.status == ChatMemberStatus.RESTRICTED and getattr(member, 'is_member', True))
    except Exception:
        is_member = False

    # Если пользователь уже одобрен или находится в чате — перенаправляем в меню
    if is_member or (user and user.get('status') in ('approved', 'in_chat', 'registered')):
        if is_member and user and user.get('status') not in ('approved', 'in_chat', 'registered'):
            try:
                from database.db_friend import update_user as update_reg_user
                await update_reg_user(user_id, status='in_chat')
            except Exception:
                pass
                
        # Получаем основную БД из bot_data (там её хранит CallbackRouter/Bot.py)
        main_db = context.bot_data.get('db')
        
        from handlers.commands.system_commands import menu_command
        from config import OWNER_ID
        await menu_command(update, context, main_db, OWNER_ID)
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
        state_map = {"AGE": AGE, "CITY": CITY, "THERAPY": THERAPY, "REF_CODE": REF_CODE}
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
    await _delete_user_msg(update.message)
    await update_user(user_id, questionnaire_state="AGE")
    context.user_data['reg_name'] = update.message.text

    msg_id = context.user_data.get('reg_msg_id')
    if msg_id:
        await _edit_form(context, user_id, msg_id, _build_form(context.user_data, "Б. Сколько тебе полных лет?"))
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    age_text = update.message.text

    if not age_text.isdigit():
        await _delete_user_msg(update.message)
        msg_id = context.user_data.get('reg_msg_id')
        if msg_id:
            await _edit_form(context, user_id, msg_id,
                _build_form(context.user_data, "Б. Сколько тебе полных лет?\n\n❌ Введи возраст числом."))
        return AGE

    age = int(age_text)
    await _delete_user_msg(update.message)
    context.user_data['reg_age'] = age

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
    await _delete_user_msg(update.message)
    msg_id = context.user_data.get('reg_msg_id')

    try:
        birth_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        today = date.today()
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
    await _delete_user_msg(update.message)
    await update_user(user_id, questionnaire_state="THERAPY")
    context.user_data['reg_city'] = update.message.text

    msg_id = context.user_data.get('reg_msg_id')
    if msg_id:
        await _edit_form(context, user_id, msg_id,
            _build_form(context.user_data,
                "Г. Какую терапию ты принимаешь?\n(Укажи точное наименование препаратов)"))
    return THERAPY


async def get_therapy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await _delete_user_msg(update.message)
    await update_user(user_id, questionnaire_state="REF_CODE")
    context.user_data['reg_therapy'] = update.message.text

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
    await _delete_user_msg(update.message)
    return await finish_registration(update, context, update.message.text)


async def skip_ref_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await finish_registration(update, context, None)


async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE, ref_code):
    user_id = update.effective_user.id
    await update_user(user_id, questionnaire_state=None)
    data = context.user_data

    await update_user(
        user_id,
        q_name=data['reg_name'],
        q_age=data['reg_age'],
        q_city=data['reg_city'],
        q_therapy=data['reg_therapy'],
        referred_by=ref_code,
        status='pending'
    )

    app_id = await create_application(user_id)

    # Обновляем окно анкеты — итоговое сообщение
    msg_id = context.user_data.get('reg_msg_id')
    final_text = (
        f"📋 <b>Анкета регистрации</b>\n\n"
        f"А. Имя: <b>{data['reg_name']}</b> ✅\n"
        f"Б. Возраст: <b>{data['reg_age']}</b> ✅\n"
        f"В. Город: <b>{data['reg_city']}</b> ✅\n"
        f"Г. Терапия: <b>{data['reg_therapy']}</b> ✅\n"
        f"Д. Реф. код: <b>{ref_code or 'нет'}</b> ✅\n\n"
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
        f"👤 Имя: {data['reg_name']} | <code>{user_id}</code> | <b>#user{user_id}</b>\n"
        f"🎂 Возраст: {data['reg_age']}\n"
        f"🏙 Город: {data['reg_city']}\n"
        f"💊 Терапия: {data['reg_therapy']}\n"
        f"🤝 Реферал: {ref_code or 'Нет'}\n"
        f"🆔 Никнейм: {username_str}\n\n"
        f"📅 <b>Блок Е:</b>\n"
        f"Дата заявки: {now_msk}"
    )
    sent = None
    try:
        sent = await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            message_thread_id=APPLICATIONS_THREAD_ID,
            text=admin_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить в тред {APPLICATIONS_THREAD_ID}: {e}. Пробуем без треда.")
        try:
            sent = await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e2:
            logger.error(f"Не удалось отправить заявку админам: {e2}")
    if sent:
        await save_application_message_id(app_id, sent.message_id)
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
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False
)
