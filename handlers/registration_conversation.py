import logging
import pytz
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from database.db_friend import get_user, create_user, update_user, create_application
from config import OWNER_ID, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

NAME, AGE, BIRTH_DATE, CITY, THERAPY, REF_CODE = range(6)

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


# ══════════════════════════════════════════════════════
#  Система одного окна
# ══════════════════════════════════════════════════════

def _build_form(context: ContextTypes.DEFAULT_TYPE, question: str, hint: str = "") -> str:
    """Строит текст формы — заполненные поля + текущий вопрос."""
    d = context.user_data
    lines = ["📝 <b>РЕГИСТРАЦИЯ</b>", "━━━━━━━━━━━━━━━━━━━━"]

    if 'reg_name' in d:
        lines.append(f"✅ А. Имя: <b>{d['reg_name']}</b>")
    if 'reg_age' in d:
        lines.append(f"✅ Б. Возраст: <b>{d['reg_age']}</b>")
    if 'reg_city' in d:
        lines.append(f"✅ В. Город: <b>{d['reg_city']}</b>")
    if 'reg_therapy' in d:
        lines.append(f"✅ Г. Терапия: <b>{d['reg_therapy']}</b>")

    lines.append("")
    lines.append(f"❓ {question}")
    if hint:
        lines.append(f"<i>{hint}</i>")

    return "\n".join(lines)


async def _edit_form(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    keyboard: InlineKeyboardMarkup = None,
):
    """Удаляет сообщение пользователя и редактирует окно регистрации."""
    # Удаляем ответ пользователя
    if update.message:
        try:
            await update.message.delete()
        except Exception:
            pass

    chat_id = context.user_data.get('reg_chat_id')
    msg_id  = context.user_data.get('reg_msg_id')

    if chat_id and msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    # Fallback: отправляем новое сообщение
    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    context.user_data['reg_chat_id'] = msg.chat_id
    context.user_data['reg_msg_id']  = msg.message_id


# ══════════════════════════════════════════════════════
#  Шаги регистрации
# ══════════════════════════════════════════════════════

async def start_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db_friend import is_blacklisted, get_blacklist_reason
    user_id = update.effective_user.id

    # Чёрный список
    if await is_blacklisted(user_id):
        reason = await get_blacklist_reason(user_id)
        try:
            owner_chat = await context.bot.get_chat(OWNER_ID)
            owner_name = owner_chat.full_name or str(OWNER_ID)
        except Exception:
            owner_name = str(OWNER_ID)
        await update.message.reply_text(
            f"{update.effective_user.first_name}, мы сожалеем, но ты заблокирован администрацией "
            f"чата Pulse 4ever из-за: {reason}.\n\n"
            f"Если считаешь, что попал в ЧС по ошибке, свяжись с администратором: "
            f'<a href="tg://user?id={OWNER_ID}">{owner_name}</a>',
            parse_mode="HTML"
        )
        return ConversationHandler.END

    user = await get_user(user_id)

    if not user:
        await create_user(user_id, update.effective_user.username, update.effective_user.first_name, "")

    # Сбрасываем старое окно
    context.user_data.pop('reg_msg_id', None)
    context.user_data.pop('reg_chat_id', None)
    context.user_data.pop('reg_name', None)
    context.user_data.pop('reg_age', None)
    context.user_data.pop('reg_city', None)
    context.user_data.pop('reg_therapy', None)

    # Возврат к незавершённой анкете
    if user and user.get('questionnaire_state'):
        state = user['questionnaire_state']
        question_map = {
            "AGE":     ("Б. Сколько тебе полных лет?", "", AGE),
            "CITY":    ("В. В каком городе ты проживаешь?", "", CITY),
            "THERAPY": ("Г. Какую терапию ты принимаешь?\n(Укажи точное наименование препаратов)", "", THERAPY),
            "REF_CODE": ("Д. Реф. код (ник пользователя)\nЕсли тебя кто-то пригласил, введи его ник.",
                         "", REF_CODE),
        }
        if state in question_map:
            q, hint, next_state = question_map[state]
            text = _build_form(context, q, hint)
            keyboard = None
            if next_state == REF_CODE:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_ref")]])
            msg = await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
            context.user_data['reg_chat_id'] = msg.chat_id
            context.user_data['reg_msg_id']  = msg.message_id
            return next_state

    text = _build_form(context, "А. Как тебя зовут?")
    msg = await update.message.reply_text(text, parse_mode="HTML")
    context.user_data['reg_chat_id'] = msg.chat_id
    context.user_data['reg_msg_id']  = msg.message_id
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if _is_button_text(update.message.text):
        try:
            await update.message.delete()
        except Exception:
            pass
        return NAME
    context.user_data['reg_name'] = update.message.text
    await update_user(user_id, questionnaire_state="AGE")
    text = _build_form(context, "Б. Сколько тебе полных лет?")
    await _edit_form(update, context, text)
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    age_text = update.message.text

    if _is_button_text(age_text):
        try:
            await update.message.delete()
        except Exception:
            pass
        return AGE

    if not age_text.isdigit():
        text = _build_form(context, "Б. Сколько тебе полных лет?", "⚠️ Введи возраст числом.")
        await _edit_form(update, context, text)
        return AGE

    age = int(age_text)
    context.user_data['reg_age'] = age

    if age < 18:
        await update_user(user_id, questionnaire_state="BIRTH_DATE")
        text = _build_form(
            context,
            "Е. Укажи точную дату своего рождения в формате ДД.ММ.ГГГГ",
            "⚠️ Доступ разрешён только совершеннолетним. Например: 15.05.2010"
        )
        await _edit_form(update, context, text)
        return BIRTH_DATE

    await update_user(user_id, questionnaire_state="CITY")
    text = _build_form(context, "В. В каком городе ты проживаешь?")
    await _edit_form(update, context, text)
    return CITY


async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text.strip()
    user_id   = update.effective_user.id

    if _is_button_text(date_text):
        try:
            await update.message.delete()
        except Exception:
            pass
        return BIRTH_DATE

    try:
        birth_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        today      = date.today()
        real_age   = today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )

        if real_age < 18:
            unlock_date = (birth_date + relativedelta(years=18)).strftime("%d.%m.%Y")
            await update_user(user_id, birth_date=date_text, blocked_until=unlock_date,
                              status='blocked', questionnaire_state=None)
            text = (
                "⛔️ <b>Доступ в чат разрешён только с 18 лет.</b>\n\n"
                f"🔓 Доступ будет автоматически открыт: <b>{unlock_date}</b>\n"
                "Мы уведомим тебя, когда это произойдёт."
            )
            await _edit_form(update, context, text)
            return ConversationHandler.END

        context.user_data['reg_age'] = real_age
        await update_user(user_id, questionnaire_state="CITY")
        text = _build_form(context, "В. В каком городе ты проживаешь?", "✅ Возраст подтверждён.")
        await _edit_form(update, context, text)
        return CITY

    except ValueError:
        text = _build_form(
            context,
            "Е. Укажи точную дату рождения в формате ДД.ММ.ГГГГ",
            "❌ Неверный формат. Например: 01.01.2010"
        )
        await _edit_form(update, context, text)
        return BIRTH_DATE


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if _is_button_text(update.message.text):
        try:
            await update.message.delete()
        except Exception:
            pass
        return CITY
    context.user_data['reg_city'] = update.message.text
    await update_user(user_id, questionnaire_state="THERAPY")
    text = _build_form(context, "Г. Какую терапию ты принимаешь?",
                       "Укажи точное наименование препаратов")
    await _edit_form(update, context, text)
    return THERAPY


async def get_therapy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if _is_button_text(update.message.text):
        try:
            await update.message.delete()
        except Exception:
            pass
        return THERAPY
    context.user_data['reg_therapy'] = update.message.text
    await update_user(user_id, questionnaire_state="REF_CODE")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_ref")]])
    text = _build_form(
        context,
        "Д. Реф. код (ник пользователя)",
        "Если тебя кто-то пригласил — введи его ник. Если нет — нажми Пропустить."
    )
    await _edit_form(update, context, text, keyboard)
    return REF_CODE


async def get_ref_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref_code = update.message.text
    if _is_button_text(ref_code):
        try:
            await update.message.delete()
        except Exception:
            pass
        return REF_CODE
    try:
        await update.message.delete()
    except Exception:
        pass
    return await finish_registration(update, context, ref_code)


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

    # Финальное сообщение в окне регистрации
    final_text = (
        "📝 <b>РЕГИСТРАЦИЯ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ А. Имя: <b>{data['reg_name']}</b>\n"
        f"✅ Б. Возраст: <b>{data['reg_age']}</b>\n"
        f"✅ В. Город: <b>{data['reg_city']}</b>\n"
        f"✅ Г. Терапия: <b>{data['reg_therapy']}</b>\n"
        f"✅ Д. Реферал: <b>{ref_code or 'нет'}</b>\n\n"
        "📨 Анкета отправлена администраторам!\n"
        "Ожидай уведомления об одобрении."
    )

    chat_id = context.user_data.get('reg_chat_id')
    msg_id  = context.user_data.get('reg_msg_id')

    if chat_id and msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=final_text,
                parse_mode="HTML",
            )
        except Exception:
            eff_chat = update.effective_chat
            if eff_chat:
                await context.bot.send_message(eff_chat.id, final_text, parse_mode="HTML")
    else:
        eff_chat = update.effective_chat
        if eff_chat:
            await context.bot.send_message(eff_chat.id, final_text, parse_mode="HTML")

    # Карточка для чата администраторов
    msk     = pytz.timezone('Europe/Moscow')
    now_msk = datetime.now(msk).strftime("%d %B %Y г. %H:%M:%S МСК")

    user_data_db  = await get_user(user_id)
    last_rejection = user_data_db.get('last_rejection_reason') if user_data_db else None
    block_d = ""
    if last_rejection:
        block_d = (
            f"\n🚨 <b>Внимание! Пользователь уже подавал заявку.</b>\n"
            f"Причина отказа: {last_rejection}\n"
        )

    username_str = f"@{update.effective_user.username}" if update.effective_user.username else "нет"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить",  callback_data=f"adm_app_{user_id}_{app_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_rej_{user_id}_{app_id}"),
            InlineKeyboardButton("⏳ Отложить",  callback_data=f"adm_skip_{user_id}_{app_id}"),
        ],
        [InlineKeyboardButton("✉️ Написать в ЛС", url=f"tg://user?id={user_id}")]
    ])

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=(
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
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.user_data.get('reg_chat_id')
    msg_id  = context.user_data.get('reg_msg_id')
    text = "❌ Регистрация отменена."
    if chat_id and msg_id:
        try:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
        except Exception:
            await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


registration_conv = ConversationHandler(
    entry_points=[CommandHandler("register", start_reg)],
    states={
        NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        AGE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
        BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)],
        CITY:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
        THERAPY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_therapy)],
        REF_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_ref_code),
            CallbackQueryHandler(skip_ref_callback, pattern="^skip_ref$")
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False
)
