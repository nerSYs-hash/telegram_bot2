import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

logger = logging.getLogger(__name__)

# ID чата админов (замени на реальный ID группы админов)
ADMIN_CHAT_ID = 7536752126 # <-- ВАЖНО: Укажи ID своего админского чата здесь!

# Состояния ConversationHandler
AGREEMENT, RULES, NAME, AGE, DOB_BAN, CITY, THERAPY = range(7)

# --- Вспомогательные функции для JobQueue (Напоминания) ---
def remove_reminder(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет существующее напоминание, если оно есть."""
    # --- ДОБАВЛЕНА ЗАЩИТА ---
    if context.job_queue is None:
        return 
    # ------------------------
    current_jobs = context.job_queue.get_jobs_by_name(f"remind_{user_id}")
    for job in current_jobs:
        job.schedule_removal()

def set_reminder(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает напоминание через 5 минут (300 секунд)."""
    # --- ДОБАВЛЕНА ЗАЩИТА ---
    if context.job_queue is None:
        logger.warning("JobQueue не настроен! Напоминания работать не будут, но бот продолжит работу.")
        return
    # ------------------------
    remove_reminder(user_id, context)
    context.job_queue.run_once(
        send_reminder, 
        300, 
        chat_id=user_id, 
        name=f"remind_{user_id}",
        data=user_id
    )
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет пуш юзеру, если он забросил анкету."""
    job = context.job
    try:
        await context.bot.send_message(
            chat_id=job.chat_id,
            text="⏳ <b>Ты не закончил заполнение анкеты!</b>\n\nПожалуйста, отправь ответ на предыдущее сообщение, чтобы продолжить.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания пользователю {job.chat_id}: {e}")

# --- Обработчики состояний ---

async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Точка входа. Проверка ЛС, статуса в чате, рефералки и приветствие."""
    if update.effective_chat.type != 'private':
        return ConversationHandler.END

    user = update.effective_user
    db = context.bot_data.get('db')
    target_chat_id = context.bot_data.get('target_chat_id')

    # --- ПРОВЕРКА 1: Состоит ли юзер уже в главном чате? ---
    if target_chat_id:
        try:
            member = await context.bot.get_chat_member(chat_id=target_chat_id, user_id=user.id)
            if member.status in ['member', 'administrator', 'creator']:
                # Юзер уже в чате! Просто выдаем ему меню.
                await update.message.reply_text(
                    f"С возвращением, {user.first_name}! 👋\n"
                    "Ты уже являешься участником нашего закрытого чата.\n\n"
                    "Используй команду /menu для управления профилем."
                )
                return ConversationHandler.END
        except Exception as e:
            logger.warning(f"Не удалось проверить статус пользователя {user.id} в чате: {e}")

    # --- ПРОВЕРКА 2: Отправлял ли юзер заявку ранее? ---
    if db:
        try:
            db.cursor.execute("SELECT status FROM applications WHERE user_id = ?", (user.id,))
            app = db.cursor.fetchone()
            if app:
                status = app[0] if isinstance(app, tuple) else app['status']
                if status in ('new', 'pending', 'in_work', 'in_progress'):
                    await update.message.reply_text(
                        "⏳ <b>Твоя заявка уже находится на рассмотрении!</b>\n\n"
                        "Пожалуйста, дождись решения администраторов. Тебе придет уведомление.",
                        parse_mode='HTML'
                    )
                    return ConversationHandler.END
                elif status == 'rejected':
                    await update.message.reply_text("К сожалению, твоя заявка была отклонена. 😔")
                    return ConversationHandler.END
        except Exception as e:
            logger.error(f"Ошибка проверки заявки в БД: {e}")

    # --- ПРОВЕРКА 3: Забанен ли юзер? (До 18 лет или блэклист) ---
    if db:
        try:
            db.cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user.id,))
            user_data = db.cursor.fetchone()
            if user_data:
                is_banned = user_data[0] if isinstance(user_data, tuple) else user_data.get('is_banned')
                if is_banned:
                    await update.message.reply_text("🚫 Доступ запрещен. Твой аккаунт заблокирован.")
                    return ConversationHandler.END
        except Exception as e:
            logger.error(f"Ошибка проверки бана в БД: {e}")

    # --- ОБРАБОТКА РЕФЕРАЛКИ ---
    if context.args and context.args[0].startswith('ref_'):
        context.user_data['ref_code'] = context.args[0]
        logger.info(f"User {user.id} used ref link: {context.args[0]}")

    # --- СТАРТ АНКЕТЫ ---
    text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Это закрытое комьюнити для МСМ. У нас обсуждают терапию, ВИЧ и просто общаются в безопасной среде.\n\n"
        "⚠️ <b>ВНИМАНИЕ:</b> Доступ строго для лиц старше 18 лет."
    )
    
    keyboard = [[InlineKeyboardButton("✅ Мне уже есть 18", callback_data="age_18_plus")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    set_reminder(user.id, context)
    return AGREEMENT

async def handle_agreement(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показ правил после подтверждения 18+."""
    query = update.callback_query
    await query.answer()
    
    set_reminder(query.from_user.id, context)

    rules_text = (
        "📜 <b>ПРАВИЛА ЧАТА</b>\n\n"
        "1. Уважение к участникам.\n"
        "2. Запрещен аутинг и слив информации.\n"
        "3. Никакой продажи запрещенных веществ.\n\n"
        "Ознакомься с правилами. Если согласен — подавай заявку!"
    )
    keyboard = [[InlineKeyboardButton("📝 Подать заявку", callback_data="apply_form")]]
    
    await query.edit_message_text(rules_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    return RULES

async def handle_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Старт анкеты: запрос имени."""
    query = update.callback_query
    await query.answer()
    
    set_reminder(query.from_user.id, context)
    
    await query.edit_message_text("Отлично! Начнем.\n\nКак тебя зовут (или как к тебе обращаться)?")
    return NAME

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем имя, запрашиваем возраст."""
    context.user_data['name'] = update.message.text
    set_reminder(update.effective_user.id, context)
    
    await update.message.reply_text("Сколько тебе лет? (напиши цифрой)")
    return AGE

async def handle_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Проверка возраста. Если < 18, просим дату рождения для бана."""
    age_str = update.message.text
    if not age_str.isdigit():
        await update.message.reply_text("Пожалуйста, введи возраст числом (например: 25).")
        return AGE
    
    age = int(age_str)
    set_reminder(update.effective_user.id, context)

    if age < 18:
        await update.message.reply_text(
            "Для подтверждения возраста, пожалуйста, напиши свою полную дату рождения в формате ДД.ММ.ГГГГ:"
        )
        return DOB_BAN
    
    context.user_data['age'] = age
    await update.message.reply_text("Из какого ты города?")
    return CITY

async def handle_dob_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Блокировка пользователя < 18."""
    user = update.effective_user
    remove_reminder(user.id, context)
    
    # TODO: Записать в БД users -> is_banned = 1
    
    await update.message.reply_text(
        "🚫 <b>Доступ запрещен.</b>\n\n"
        "Наше сообщество строго для лиц старше 18 лет. Ты заблокирован.",
        parse_mode='HTML'
    )
    logger.info(f"User {user.id} banned (Under 18).")
    return ConversationHandler.END

async def handle_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем город, запрашиваем терапию."""
    context.user_data['city'] = update.message.text
    set_reminder(update.effective_user.id, context)
    
    await update.message.reply_text("На какой ты терапии? (Напиши схему или 'Не на терапии'/'Статус отрицательный')")
    return THERAPY

async def handle_therapy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем терапию, завершаем анкету и отправляем админам."""
    user = update.effective_user
    context.user_data['therapy'] = update.message.text
    
    # Анкета завершена, удаляем напоминание
    remove_reminder(user.id, context)
    
    # Данные для записи
    data = context.user_data
    ref_code = data.get('ref_code', 'None')
    db = context.bot_data.get('db')
    
    if db:
        try:
            # Записываем заявку в БД
            db.cursor.execute("""
                INSERT INTO applications (user_id, username, first_name, name, age, city, therapy, ref_code, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
                ON CONFLICT(user_id) DO UPDATE SET 
                name=excluded.name, age=excluded.age, city=excluded.city, therapy=excluded.therapy, 
                first_name=excluded.first_name, status='new'
            """, (user.id, user.username, user.first_name, data['name'], data['age'], data['city'], data['therapy'], ref_code))
            db.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения заявки: {e}")
            
    await update.message.reply_text(
        "✅ <b>Твоя заявка успешно отправлена!</b>\n\n"
        "Администраторы проверят её в ближайшее время. Если всё хорошо, бот пришлет тебе одноразовую ссылку для входа.",
        parse_mode='HTML'
    )
    
    # Уведомление в админский чат
    admin_text = (
        "🔔 <b>Поступила новая заявка!</b>\n\n"
        f"<b>От:</b> {user.first_name} (@{user.username})\n"
        "Перейдите в панель заявок, чтобы взять её в работу."
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление админам: {e}")

    # Очищаем user_data
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Принудительная отмена анкеты."""
    remove_reminder(update.effective_user.id, context)
    await update.message.reply_text("Заполнение анкеты отменено. Чтобы начать заново, нажми /start")
    context.user_data.clear()
    return ConversationHandler.END

# --- Экспорт обработчика ---
def get_onboarding_handler() -> ConversationHandler:
    return ConversationHandler( 
        entry_points=[CommandHandler("start", start_onboarding)],
        states={
            AGREEMENT:[CallbackQueryHandler(handle_agreement, pattern="^age_18_plus$")],
            RULES:[CallbackQueryHandler(handle_rules, pattern="^apply_form$")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_age)],
            DOB_BAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dob_ban)],
            CITY:[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_city)],
            THERAPY:[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_therapy)],
        },
        fallbacks=[CommandHandler("cancel", cancel_onboarding)],
        per_message=False
    )