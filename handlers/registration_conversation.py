import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta # Нужно установить: pip install python-dateutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from database.db_friend import get_user, create_user, update_user, create_application
from config import OWNER_ID, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

# Этапы анкеты (добавили новые шаги)
NAME, AGE, BIRTH_DATE, CITY, THERAPY, REF_CODE = range(6)

async def start_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    
    # ПРОВЕРКА НА ВОЗВРАТ (ТЗ 1.4.2.2)
    # Если юзер нажал "Продолжить" или просто снова ввел /register
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
            # Тут можно вывести кнопку "Пропустить" снова
            await update.message.reply_text("Продолжаем! Введи реф. код или нажми пропустить.")
            return REF_CODE

    # Если это совсем новый юзер или стейта нет - начинаем с начала
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
    await update_user(user_id, questionnaire_state="CITY")
    age_text = update.message.text
    if not age_text.isdigit():
        await update.message.reply_text("Пожалуйста, введи возраст числом.")
        return AGE
    
    age = int(age_text)
    context.user_data['reg_age'] = age

    # ЛОГИКА 18+: Если меньше 18, идем к пункту Е (дата рождения)
    if age < 18:
        await update.message.reply_text(
            "⚠️ Внимание! Доступ разрешен только совершеннолетним.\n\n"
            "<b>Е. Укажи точную дату своего рождения в формате ДД.ММ.ГГГГ</b>\n"
            "(Например: 15.05.2010)", 
            parse_mode="HTML"
        )
        return BIRTH_DATE
    
    # Если 18+, идем к городу
    
    await update.message.reply_text("<b>В. В каком городе ты проживаешь?</b>", parse_mode="HTML")
    return CITY

async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пункт Е: Проверка даты рождения для несовершеннолетних"""
    date_text = update.message.text.strip()
    user_id = update.effective_user.id
    await update_user(user_id, questionnaire_state="NAME")
    
    try:
        birth_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        today = date.today()
        # Считаем реальный возраст
        real_age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        if real_age < 18:
            # Вычисляем дату разблокировки (день 18-летия)
            unlock_date = (birth_date + relativedelta(years=18)).strftime("%d.%m.%Y")
            
            # Сохраняем блокировку в базу друга
            await update_user(user_id, birth_date=date_text, blocked_until=unlock_date, status='blocked')
            
            await update.message.reply_text(
                f"⛔️ Доступ в чат разрешен только с 18 лет.\n\n"
                f"🔓 Доступ будет автоматически открыт: {unlock_date}\n"
                f"Мы уведомим тебя, когда это произойдет."
            )
            return ConversationHandler.END
        else:
            # Если по дате всё же 18+, продолжаем
            context.user_data['reg_age'] = real_age
            await update.message.reply_text("✅ Возраст подтвержден. Продолжаем.\n\n<b>В. В каком городе ты проживаешь?</b>", parse_mode="HTML")
            return CITY
            
    except ValueError:
        await update.message.reply_text("❌ Неверный формат! Введи дату в формате ДД.ММ.ГГГГ (например: 01.01.2010)")
        return BIRTH_DATE

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update_user(user_id, questionnaire_state="THERAPY")
    context.user_data['reg_city'] = update.message.text
    await update.message.reply_text(
        "<b>Г. Какую терапию ты принимаешь?</b>\n"
        "(Укажи точное наименование препаратов)", 
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
    user_id = update.effective_user.id
    # Если юзер ввел текст вместо нажатия кнопки
    ref_code = update.message.text
    return await finish_registration(update, context, ref_code)

async def skip_ref_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Если юзер нажал кнопку пропустить
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Реф. код пропущен.")
    return await finish_registration(update, context, None)

async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE, ref_code):
    user_id = update.effective_user.id
    # Обязательно ставим None, чтобы напоминалка больше не беспокоила!
    await update_user(user_id, questionnaire_state=None)
    user_id = update.effective_user.id
    data = context.user_data
    
    # Сохраняем ВСЁ в базу друга
    await update_user(
        user_id,
        q_name=data['reg_name'],
        q_age=data['reg_age'],
        q_city=data['reg_city'],
        q_therapy=data['reg_therapy'],
        referred_by=ref_code,
        status='pending' # Ставим статус "На проверке"
    )
    
    app_id = await create_application(user_id)
    
    msg_text = "✅ Анкета заполнена и отправлена администраторам! Жди уведомления об одобрении."
    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text)
    else:
        await update.message.reply_text(msg_text)

    # Формируем текст заявки для чата администраторов
    from datetime import datetime
    import pytz
    msk = pytz.timezone('Europe/Moscow')
    now_msk = datetime.now(msk).strftime("%d %B %Y г. %H:%M:%S МСК")

    # Блок Д: предыдущий отказ
    user_data = await get_user(user_id)
    last_rejection = user_data.get('last_rejection_reason') if user_data else None
    block_d = ""
    if last_rejection:
        block_d = (
            f"\n🚨 <b>Внимание! Пользователь уже подавал заявку.</b>\n"
            f"Причина отказа: {last_rejection}\n"
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_app_{user_id}_{app_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_rej_{user_id}_{app_id}"),
         InlineKeyboardButton("⏳ Отложить", callback_data=f"adm_skip_{user_id}_{app_id}")
        ],
        [InlineKeyboardButton("✉️ Написать в ЛС", url=f"tg://user?id={user_id}")]
    ])

    username_str = f"@{update.effective_user.username}" if update.effective_user.username else "нет"

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=(
            f"📢 <b>НОВАЯ ЗАЯВКА #{app_id}</b>\n"
            f"{block_d}\n"
            f"👤 Имя: {data['reg_name']}\n"
            f"🎂 Возраст: {data['reg_age']}\n"
            f"🏙 Город: {data['reg_city']}\n"
            f"💊 Терапия: {data['reg_therapy']}\n"
            f"🤝 Реферал: {ref_code or 'Нет'}\n"
            f"🆔 ID: <code>{user_id}</code> | {username_str}\n\n"
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

# Обновленный ConversationHandler
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
