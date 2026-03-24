#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import warnings
from telegram.warnings import PTBUserWarning
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

logger = logging.getLogger(__name__)

AGREEMENT, RULES, NAME, AGE, DOB_BAN, CITY, THERAPY = range(7)


def _has_job_queue(context):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PTBUserWarning)
        return context.job_queue is not None

def remove_reminder(user_id, context):
    if not _has_job_queue(context):
        return
    for job in context.job_queue.get_jobs_by_name(f"remind_{user_id}"):
        job.schedule_removal()

def set_reminder(user_id, context):
    if not _has_job_queue(context):
        return
    remove_reminder(user_id, context)
    context.job_queue.run_once(send_reminder, 300, chat_id=user_id, name=f"remind_{user_id}", data=user_id)

async def send_reminder(context):
    job = context.job
    try:
        await context.bot.send_message(
            chat_id=job.chat_id,
            text="⏳ <b>Ты не закончил заполнение анкеты!</b>\n\nПожалуйста, отправь ответ на предыдущее сообщение, чтобы продолжить.",
            parse_mode='HTML',
        )
    except Exception as e:
        logger.error(f"Ошибка напоминания {job.chat_id}: {e}")

def _get_notify_chat_id(context):
    return context.bot_data.get('admin_chat_id') or context.bot_data.get('main_admin_id')


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat.type != 'private':
        return ConversationHandler.END

    user = update.effective_user
    db = context.bot_data.get('db')
    target_chat_id = context.bot_data.get('target_chat_id')

    # Сохраняем пользователя в БД сразу
    if db:
        try:
            db.add_user(user_id=user.id, username=user.username, first_name=user.first_name, last_name=user.last_name)
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователя {user.id}: {e}")

    # Проверка 1: уже в чате?
    if target_chat_id:
        try:
            member = await context.bot.get_chat_member(chat_id=target_chat_id, user_id=user.id)
            if member.status in ('member', 'administrator', 'creator'):
                await update.message.reply_text(
                    f"С возвращением, {user.first_name}! 👋\nТы уже являешься участником нашего закрытого чата.\n\nИспользуй команду /menu для управления профилем."
                )
                return ConversationHandler.END
        except Exception as e:
            logger.warning(f"Не удалось проверить статус {user.id}: {e}")

    # Проверка 2: уже подавал заявку?
    if db:
        try:
            db.cursor.execute("SELECT status FROM applications WHERE user_id = ?", (user.id,))
            app = db.cursor.fetchone()
            if app:
                status = app[0] if isinstance(app, tuple) else app['status']
                if status in ('new', 'pending', 'in_work', 'in_progress'):
                    await update.message.reply_text(
                        "⏳ <b>Твоя заявка уже находится на рассмотрении!</b>\n\nПожалуйста, дождись решения администраторов.",
                        parse_mode='HTML',
                    )
                    return ConversationHandler.END
                elif status == 'rejected':
                    await update.message.reply_text("😔 Твоя заявка была отклонена. Нажми /start чтобы подать снова.")
                    try:
                        db.cursor.execute("DELETE FROM applications WHERE user_id = ?", (user.id,))
                        db.conn.commit()
                    except Exception:
                        pass
                    return ConversationHandler.END
        except Exception as e:
            logger.error(f"Ошибка проверки заявки: {e}")

    # Проверка 3: забанен?
    if db:
        try:
            db.cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user.id,))
            row = db.cursor.fetchone()
            if row:
                is_banned = row[0] if isinstance(row, tuple) else row.get('is_banned', 0)
                if is_banned:
                    await update.message.reply_text("🚫 Доступ запрещён. Твой аккаунт заблокирован.")
                    return ConversationHandler.END
        except Exception as e:
            logger.error(f"Ошибка проверки бана: {e}")

    # Рефералка
    if context.args and context.args[0].startswith('ref_'):
        context.user_data['ref_code'] = context.args[0]

    text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Это закрытое комьюнити для МСМ. У нас обсуждают терапию, ВИЧ и просто общаются в безопасной среде.\n\n"
        "⚠️ <b>ВНИМАНИЕ:</b> Доступ строго для лиц старше 18 лет."
    )
    keyboard = [[InlineKeyboardButton("✅ Мне уже есть 18", callback_data="age_18_plus")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    set_reminder(user.id, context)
    return AGREEMENT


async def handle_agreement(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    set_reminder(query.from_user.id, context)
    rules_text = (
        "📜 <b>ПРАВИЛА ЧАТА</b>\n\n"
        "1. Уважение к участникам.\n"
        "2. Запрещён аутинг и слив информации.\n"
        "3. Никакой продажи запрещённых веществ.\n\n"
        "Ознакомься с правилами. Если согласен — подавай заявку!"
    )
    keyboard = [[InlineKeyboardButton("📝 Подать заявку", callback_data="apply_form")]]
    await query.edit_message_text(rules_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    return RULES


async def handle_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    set_reminder(query.from_user.id, context)
    await query.edit_message_text("Отлично! Начнём.\n\nКак тебя зовут (или как к тебе обращаться)?")
    return NAME


async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    set_reminder(update.effective_user.id, context)
    await update.message.reply_text("Сколько тебе лет? (напиши цифрой)")
    return AGE


async def handle_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    age_str = update.message.text.strip()
    if not age_str.isdigit():
        await update.message.reply_text("Пожалуйста, введи возраст числом (например: 25).")
        return AGE
    age = int(age_str)
    set_reminder(update.effective_user.id, context)
    if age < 18:
        await update.message.reply_text("Для подтверждения возраста напиши свою дату рождения в формате ДД.ММ.ГГГГ:")
        return DOB_BAN
    context.user_data['age'] = age
    await update.message.reply_text("Из какого ты города?")
    return CITY


async def handle_dob_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    remove_reminder(user.id, context)
    db = context.bot_data.get('db')
    if db:
        try:
            db.cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user.id,))
            db.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка записи бана: {e}")
    await update.message.reply_text(
        "🚫 <b>Доступ запрещён.</b>\n\nНаше сообщество строго для лиц старше 18 лет.",
        parse_mode='HTML',
    )
    logger.info(f"User {user.id} забанен (младше 18).")
    return ConversationHandler.END


async def handle_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['city'] = update.message.text
    set_reminder(update.effective_user.id, context)
    await update.message.reply_text("На какой ты терапии?\n(Напиши схему или «Не на терапии» / «Статус отрицательный»)")
    return THERAPY


async def handle_therapy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    context.user_data['therapy'] = update.message.text
    remove_reminder(user.id, context)

    data = context.user_data
    db = context.bot_data.get('db')

    if db:
        try:
            db.cursor.execute("""
                INSERT INTO applications (user_id, username, first_name, name, age, city, therapy, ref_code, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username, first_name=excluded.first_name,
                    name=excluded.name, age=excluded.age, city=excluded.city,
                    therapy=excluded.therapy, ref_code=excluded.ref_code, status='new'
            """, (
                user.id, user.username, user.first_name,
                data.get('name'), data.get('age'), data.get('city'),
                data.get('therapy'), data.get('ref_code'),
            ))
            db.conn.commit()
            logger.info(f"Заявка от {user.id} (@{user.username}) сохранена.")
        except Exception as e:
            logger.error(f"Ошибка сохранения заявки: {e}")

    await update.message.reply_text(
        "✅ <b>Твоя заявка успешно отправлена!</b>\n\n"
        "Администраторы проверят её в ближайшее время. "
        "Если всё хорошо — бот пришлёт тебе одноразовую ссылку для входа.",
        parse_mode='HTML',
    )

    # Уведомление администраторам
    notify_id = _get_notify_chat_id(context)
    if notify_id:
        username_text = f"@{user.username}" if user.username else f"id{user.id}"
        admin_text = (
            "🔔 <b>Поступила новая заявка!</b>\n\n"
            f"<b>От:</b> {user.first_name} ({username_text})\n"
            f"<b>ID:</b> <code>{user.id}</code>\n\n"
            "Нажмите кнопку ниже или используйте /apps"
        )
        keyboard = [[InlineKeyboardButton("📋 Открыть заявки", callback_data="check_new_apps")]]
        try:
            await context.bot.send_message(
                chat_id=notify_id,
                text=admin_text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            logger.info(f"Уведомление отправлено в {notify_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления в {notify_id}: {e}")
    else:
        logger.warning("Не задан admin_chat_id/main_admin_id — уведомление не отправлено!")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    remove_reminder(update.effective_user.id, context)
    await update.message.reply_text("Заполнение анкеты отменено. Чтобы начать заново, нажми /start")
    context.user_data.clear()
    return ConversationHandler.END


def get_onboarding_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_onboarding)],
        states={
            AGREEMENT: [CallbackQueryHandler(handle_agreement, pattern="^age_18_plus$")],
            RULES:     [CallbackQueryHandler(handle_rules, pattern="^apply_form$")],
            NAME:      [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
            AGE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_age)],
            DOB_BAN:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dob_ban)],
            CITY:      [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_city)],
            THERAPY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_therapy)],
        },
        fallbacks=[CommandHandler("cancel", cancel_onboarding)],
        per_message=False,
    )
