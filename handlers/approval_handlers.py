#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Обработка заявок (Анкет) администраторами.
Одобрение (с выдачей одноразовой ссылки) и Отклонение (с указанием причины).
"""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Состояния для FSM отказа
WAITING_FOR_REASON = 1

async def show_new_application(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Вызывается при нажатии кнопки [Новые заявки] админом"""
    query = update.callback_query
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message

    admin_id = update.effective_user.id

    try:
        # 1. Ищем новую заявку в базе
        db.cursor.execute('''
            SELECT user_id, name, age, city, therapy, username, first_name 
            FROM applications 
            WHERE status = 'new' 
            ORDER BY created_at ASC LIMIT 1
        ''')
        app = db.cursor.fetchone()

        if not app:
            # Проверим, может есть заявки "В работе", которые зависли (> 2 минут)
            db.cursor.execute('''
                UPDATE applications SET status = 'new', locked_by = NULL 
                WHERE status = 'in_progress' AND locked_at <= datetime('now', '-2 minutes')
            ''')
            if db.cursor.rowcount > 0:
                db.conn.commit()
                # Пробуем найти снова
                db.cursor.execute("SELECT * FROM applications WHERE status = 'new' ORDER BY created_at ASC LIMIT 1")
                app = db.cursor.fetchone()

        if not app:
            text = "📭 На текущий момент новые заявки отсутствуют."
            if query:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Обновить", callback_data="check_new_apps")]]))
            else:
                await message.reply_text(text)
            return

        user_id = app['user_id']

        # 2. Блокируем заявку за этим админом ("в работе")
        db.cursor.execute('''
            UPDATE applications 
            SET status = 'in_progress', locked_by = ?, locked_at = datetime('now') 
            WHERE user_id = ?
        ''', (admin_id, user_id))
        db.conn.commit()

        # 3. Формируем анкету для админа
        username_text = f"@{app['username']}" if app['username'] else app['first_name']
        
        text = (
            f"📋 <b>НОВАЯ ЗАЯВКА</b> #Новая_заявка\n\n"
            f"👤 <b>Пользователь:</b> <a href='tg://user?id={user_id}'>{app['first_name']}</a>\n"
            f"🔗 <b>Никнейм:</b> {username_text}\n"
            f"🆔 <b>ID:</b> <code>#user{user_id}</code>\n\n"
            f"📝 <b>АНКЕТА:</b>\n"
            f"Имя: {app['name']}\n"
            f"Возраст: {app['age']}\n"
            f"Город: {app['city']}\n"
            f"Терапия: {app['therapy']}\n"
        )

        keyboard = [[
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_app_{user_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_app_{user_id}")
            ],[InlineKeyboardButton("⏭ Пропустить (Вернуть в очередь)", callback_data=f"skip_app_{user_id}")]
        ]

        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        else:
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    except Exception as e:
        logger.error(f"Ошибка при загрузке заявки: {e}")
        if query:
            await query.edit_message_text("❌ Произошла ошибка при загрузке заявки!")


async def skip_application(query, context, db):
    """Админ пропустил заявку, возвращаем статус 'new'"""
    user_id = int(query.data.replace("skip_app_", ""))
    try:
        db.cursor.execute("UPDATE applications SET status = 'new', locked_by = NULL WHERE user_id = ?", (user_id,))
        db.conn.commit()
        await show_new_application(query, context, db) # Сразу показываем следующую
    except Exception as e:
        logger.error(f"Ошибка пропуска заявки: {e}")


async def approve_application(query, context, db, target_chat_id):
    """Одобрение заявки и выдача одноразовой ссылки"""
    user_id = int(query.data.replace("approve_app_", ""))
    admin_id = query.from_user.id
    admin_username = query.from_user.username or query.from_user.first_name

    try:
        # 1. Меняем статус в БД
        db.cursor.execute("UPDATE applications SET status = 'approved' WHERE user_id = ?", (user_id,))
        db.conn.commit()

        # 2. Получаем имя из анкеты
        db.cursor.execute("SELECT name FROM applications WHERE user_id = ?", (user_id,))
        row = db.cursor.fetchone()
        app_name = row['name'] if row else "Друг"

        # 3. ГЕНЕРИРУЕМ ОДНОРАЗОВУЮ ССЫЛКУ В ЧАТ
        try:
            invite = await context.bot.create_chat_invite_link(
                chat_id=target_chat_id,
                name=f"Invite: {app_name}",
                member_limit=1, # Ссылка сгорит после 1 входа!
                creates_join_request=False
            )
            invite_link = invite.invite_link
        except Exception as e:
            logger.error(f"Не удалось создать ссылку: {e}")
            await query.answer("❌ Ошибка генерации ссылки. Проверьте права бота в чате!", show_alert=True)
            return

        # 4. Отправляем юзеру ссылку с анимацией
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 {app_name}, ты на пороге входа в чат <b>PULSE</b>!\n\n"
                     f"Просто используй свою личную одноразовую ссылку:\n{invite_link}\n\n"
                     f"<i>⚠️ Ссылка сгорит сразу после перехода. Не передавай её никому!</i>",
                parse_mode='HTML',
                message_effect_id="5046509860389126442" # 🎉 Конфетти
            )
            
            # 5. Запускаем таймер на 1 минуту для отправки сообщения про рефералку
            context.job_queue.run_once(
                send_referral_promo, 
                60, # 60 секунд
                data={'user_id': user_id, 'app_name': app_name}, 
                name=f"ref_promo_{user_id}"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить ссылку юзеру {user_id}: {e}")

        # 6. Убираем кнопки у админа
        await query.edit_message_text(
            f"{query.message.text}\n\n"
            f"✅ <b>ЗАЯВКА ОДОБРЕНА</b> (@{admin_username})\n"
            f"Одноразовая ссылка отправлена пользователю.",
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Ошибка одобрения: {e}")
        await query.answer("❌ Ошибка при одобрении!", show_alert=True)


async def send_referral_promo(context: ContextTypes.DEFAULT_TYPE):
    """Отправка промо-сообщения про рефералку через 1 минуту после одобрения"""
    job = context.job
    user_id = job.data['user_id']
    app_name = job.data['app_name']

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎁 {app_name}, добро пожаловать!\n\n"
                 f"Приглашай своих знакомых и друзей в чат Pulse 💗💗💗.\n"
                 f"Отправь нашего бота своему статусному другу и зарабатывай Пульсы за каждого приглашенного!\n\n"
                 f"<i>Твою личную ссылку можно получить в меню бота.</i>",
            parse_mode='HTML'
        )
    except Exception:
        pass


# ─── БЛОК ОТКАЗА (FSM ДЛЯ АДМИНА) ───

async def reject_application_start(query, context):
    """Начало процедуры отказа — спрашиваем причину"""
    user_id = int(query.data.replace("reject_app_", ""))
    context.user_data['rejecting_user_id'] = user_id
    context.user_data['rejecting_msg_id'] = query.message.message_id
    context.user_data['rejecting_text'] = query.message.text

    await query.edit_message_text(
        f"{query.message.text}\n\n"
        f"✍️ <b>Напишите причину отказа для этого пользователя:</b>\n"
        f"<i>(Текст будет отправлен пользователю)</i>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_reject")]])
    )
    return WAITING_FOR_REASON


async def receive_rejection_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Получаем текст причины отказа от админа"""
    reason = update.message.text
    admin_id = update.effective_user.id
    admin_username = update.effective_user.username or update.effective_user.first_name
    user_id = context.user_data.get('rejecting_user_id')
    msg_id = context.user_data.get('rejecting_msg_id')
    orig_text = context.user_data.get('rejecting_text')

    # Удаляем сообщение админа с текстом причины, чтобы не засорять чат
    try:
        await update.message.delete()
    except:
        pass

    if not user_id:
        return ConversationHandler.END

    try:
        # 1. Сохраняем отказ в БД
        db.cursor.execute('''
            UPDATE applications 
            SET status = 'rejected', rejection_reason = ? 
            WHERE user_id = ?
        ''', (reason, user_id))
        
        # Сохраняем в общую историю юзера последнюю причину отказа
        db.cursor.execute('''
            UPDATE users SET last_rejection_reason = ? WHERE user_id = ?
        ''', (reason, user_id))
        db.conn.commit()

        # 2. Получаем имя юзера
        db.cursor.execute("SELECT name FROM applications WHERE user_id = ?", (user_id,))
        row = db.cursor.fetchone()
        app_name = row['name'] if row else "Пользователь"

        # 3. Отправляем уведомление юзеру
        try:
            keyboard = [[InlineKeyboardButton("📝 Подать заявку снова", callback_data="start_application")]]
            await context.bot.send_message(
                chat_id=user_id,
                text=f"😔 {app_name}, к сожалению, ваша анкета отклонена.\n\n"
                     f"<b>Причина:</b> {reason}\n\n"
                     f"Просьба исправить недочеты и подать заявку снова.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить отказ юзеру {user_id}: {e}")

        # 4. Обновляем сообщение у админа
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg_id,
            text=f"{orig_text}\n\n"
                 f"❌ <b>ЗАЯВКА ОТКЛОНЕНА</b> (@{admin_username})\n"
                 f"Причина: <i>{reason}</i>",
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Ошибка при сохранении отказа: {e}")
        await context.bot.send_message(chat_id=admin_id, text="❌ Ошибка при отклонении заявки.")

    # Очищаем кэш FSM
    context.user_data.pop('rejecting_user_id', None)
    context.user_data.pop('rejecting_msg_id', None)
    context.user_data.pop('rejecting_text', None)
    
    return ConversationHandler.END


async def cancel_reject(query, context, db):
    """Отмена процедуры отказа (возврат кнопок)"""
    user_id = context.user_data.get('rejecting_user_id')
    orig_text = context.user_data.get('rejecting_text')
    
    if user_id and orig_text:
        keyboard =[[
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_app_{user_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_app_{user_id}")
            ],[InlineKeyboardButton("⏭ Пропустить (Вернуть в очередь)", callback_data=f"skip_app_{user_id}")]
        ]
        await query.edit_message_text(orig_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    context.user_data.pop('rejecting_user_id', None)
    context.user_data.pop('rejecting_msg_id', None)
    context.user_data.pop('rejecting_text', None)
    return ConversationHandler.END