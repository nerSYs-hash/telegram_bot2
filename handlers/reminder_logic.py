import logging
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.db_friend import db_pool, rows_to_dict_list, update_user, get_users_with_unused_link

logger = logging.getLogger(__name__)

async def send_registration_reminders(context):
    """Задача для планировщика: ищет тех, кто не закончил анкету"""
    async with db_pool.get_connection() as db:
        # Ищем юзеров, у которых есть стейт, но анкета не завершена (status IS NULL)
        # И последнее действие (last_activity) было более 5 минут назад
        cutoff = (datetime.now() - timedelta(minutes=5)).isoformat()
        
        async with db.execute(
            "SELECT tg_id, q_name, first_name, last_name, questionnaire_state "
            "FROM users WHERE questionnaire_state IS NOT NULL "
            "AND last_activity < ? AND status IS NULL", (cutoff,)
        ) as cursor:
            users = rows_to_dict_list(await cursor.fetchall())

    for user in users:
        user_id = user['tg_id']
        # Имя из анкеты (если есть) или из Телеграма (First + Last)
        display_name = user['q_name'] or f"{user['first_name'] or ''} {user['last_name'] or ''}".strip() or "Пользователь"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏩ Продолжить регистрацию", callback_data=f"continue_reg")]
        ])
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"<b>{display_name}</b>,\nты не закончил заполнение анкеты, возможно, тебя отвлекли.",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            # Чтобы не спамить напоминанием каждую минуту, сбрасываем стейт 
            # или можно добавить колонку reminder_sent
            await update_user(user_id, questionnaire_state=None) 
            print(f"🔔 Отправлено напоминание пользователю {user_id}")
        except Exception as e:
            print(f"❌ Не удалось отправить напоминание {user_id}: {e}")


async def send_unused_link_reminders_5min(context):
    """Задача для планировщика: напоминание о неиспользованной ссылке через 5 минут (п.3.3.2)"""
    users = await get_users_with_unused_link(minutes=5)

    for user in users:
        user_id = user['tg_id']
        display_name = user.get('q_name') or f"{user.get('first_name') or ''} {user.get('last_name') or ''}".strip() or "Пользователь"
        invite_link = user.get('invite_link')
        invite_message_id = user.get('invite_message_id')

        try:
            # Удаляем предыдущее сообщение со ссылкой
            if invite_message_id:
                try:
                    await context.bot.delete_message(chat_id=user_id, message_id=invite_message_id)
                except Exception:
                    pass

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Войти в чат", url=invite_link)]
            ]) if invite_link else None

            msg = await context.bot.send_message(
                chat_id=user_id,
                text=f"<b>{display_name}</b>,\nМы заметили, что ты ещё не воспользовался ссылкой и не перешёл в чат PositivЭ. Ждём тебя!",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await update_user(user_id, invite_message_id=msg.message_id)
            logger.info(f"🔔 Напоминание о ссылке (5 мин) отправлено {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка напоминания о ссылке (5 мин) {user_id}: {e}")


async def send_unused_link_reminders_10days(context):
    """Задача для планировщика: напоминание о неиспользованной ссылке через 10 дней (п.8.3)"""
    users = await get_users_with_unused_link(days=10)

    for user in users:
        user_id = user['tg_id']
        display_name = user.get('q_name') or f"{user.get('first_name') or ''} {user.get('last_name') or ''}".strip() or "Пользователь"
        invite_link = user.get('invite_link')
        invite_message_id = user.get('invite_message_id')

        try:
            # Удаляем предыдущее сообщение со ссылкой
            if invite_message_id:
                try:
                    await context.bot.delete_message(chat_id=user_id, message_id=invite_message_id)
                except Exception:
                    pass

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Войти в чат", url=invite_link)]
            ]) if invite_link else None

            msg = await context.bot.send_message(
                chat_id=user_id,
                text=f"<b>{display_name}</b>, с возвращением! 👋\n\nМы заметили, что ты не воспользовался своей персональной ссылкой для входа в чат PositivЭ.\nВозможно, ты отвлёкся или потерял её — не проблема!",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await update_user(user_id, invite_message_id=msg.message_id)
            logger.info(f"📅 Напоминание о ссылке (10 дней) отправлено {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка напоминания о ссылке (10 дней) {user_id}: {e}")