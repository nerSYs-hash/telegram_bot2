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


async def start_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db_friend import is_blacklisted, get_blacklist_reason
    user_id = update.effective_user.id

    # Проверка чёрного списка
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

    # Возврат к незавершённой анкете
    if user and user.get('questionnaire_state'):
        state = user['questionnaire_state']
        if state == "AGE":
            await update.message.reply_text("Продолжаем! Сколько тебе полных лет?")
            return AGE
        elif state == "CITY":
            await update.message.reply_text("Продолжаем! В каком городе ты проживаешь?")
            return CITY
        elif state == "THERAPY":
            await update.message.reply_text("Продолжаем! Какую терапию ты принимаешь?")
            return THERAPY
        elif state == "REF_CODE":
            await update.message.reply_text("Продолжаем! Введи реф. код или нажми пропустить.")
            return REF_CODE

    if not user:
        await create_user(user_id, update.effective_user.username, update.effective_user.first_name, "")

    await update.message.reply_text("📝 Начнем регистрацию!\n\n<b>А. Как тебя зовут?</b>", parse_mode="HTML")
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update_user(user_id, questionnaire_state="AGE")
    context.user_data['reg_name'] = update.message.text
    await update.message.reply_text("<b>Б. Сколько тебе полных лет?</b>", parse_mode="HTML")
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    age_text = update.message.text
    if not age_text.isdigit():
        await update.message.reply_text("Пожалуйста, введи возраст числом.")
        return AGE

    age = int(age_text)
    context.user_data['reg_age'] = age

    if age < 18:
        await update_user(user_id, questionnaire_state="BIRTH_DATE")
        await update.message.reply_text(
            "⚠️ Внимание! Доступ разрешен только совершеннолетним.\n\n"
            "<b>Е. Укажи точную дату своего рождения в формате ДД.ММ.ГГГГ</b>\n"
            "(Например: 15.05.2010)",
            parse_mode="HTML"
        )
        return BIRTH_DATE

    await update_user(user_id, questionnaire_state="CITY")
    await update.message.reply_text("<b>В. В каком городе ты проживаешь?</b>", parse_mode="HTML")
    return CITY


async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пункт Е: Проверка даты рождения для несовершеннолетних"""
    date_text = update.message.text.strip()
    user_id = update.effective_user.id

    try:
        birth_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        today = date.today()
        real_age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

        if real_age < 18:
            unlock_date = (birth_date + relativedelta(years=18)).strftime("%d.%m.%Y")
            await update_user(user_id, birth_date=date_text, blocked_until=unlock_date, status='blocked',
                              questionnaire_state=None)
            await update.message.reply_text(
                f"⛔️ Доступ в чат разрешен только с 18 лет.\n\n"
                f"🔓 Доступ будет автоматически открыт: {unlock_date}\n"
                f"Мы уведомим тебя, когда это произойдет."
            )
            return ConversationHandler.END
        else:
            context.user_data['reg_age'] = real_age
            await update_user(user_id, questionnaire_state="CITY")
            await update.message.reply_text(
                "✅ Возраст подтвержден. Продолжаем.\n\n<b>В. В каком городе ты проживаешь?</b>",
                parse_mode="HTML"
            )
            return CITY

    except ValueError:
        await update.message.reply_text("❌ Неверный формат! Введи дату в формате ДД.ММ.ГГГГ (например: 01.01.2010)")
        return BIRTH_DATE


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update_user(user_id, questionnaire_state="THERAPY")
    context.user_data['reg_city'] = update.message.text
    await update.message.reply_text(
        "<b>Г. Какую терапию ты принимаешь?</b>\n(Укажи точное наименование препаратов)",
        parse_mode="HTML"
    )
    return THERAPY


async def get_therapy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update_user(user_id, questionnaire_state="REF_CODE")
    context.user_data['reg_therapy'] = update.message.text

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_ref")]])
    await update.message.reply_text(
        "<b>Д. Реф. код (ник пользователя)</b>\n"
        "Если тебя кто-то пригласил, введи его ник. Если нет — нажми кнопку ниже.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    return REF_CODE


async def get_ref_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref_code = update.message.text
    return await finish_registration(update, context, ref_code)


async def skip_ref_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Реф. код пропущен.")
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

    msg_text = "✅ Анкета заполнена и отправлена администраторам! Жди уведомления об одобрении."
    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text)
    else:
        await update.message.reply_text(msg_text)

    # Формируем карточку для чата администраторов
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
    await update.message.reply_text("Регистрация отменена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


registration_conv = ConversationHandler(
    entry_points=[CommandHandler("register", start_reg)],
    states={
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
