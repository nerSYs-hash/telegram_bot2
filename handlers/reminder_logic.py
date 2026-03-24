from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.db_friend import db_pool, rows_to_dict_list, update_user

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