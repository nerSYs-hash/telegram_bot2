#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль событий пользователей — уход, возврат, реакции.

Вынесено из message_handler.py.
Все функции — модульного уровня (без класса).
db, admin_id, target_chat_id передаются явно.

Использование в message_handler.py:
    from handlers.messages.events_logic import (
        handle_member_left, handle_reaction,
    )
"""

import logging
import telegram.error
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import format_number, get_today_date_msk
from handlers.bbs_handlers import handle_bbs_reaction, on_member_left_cleanup
from handlers.journal_handlers import log_join, log_leave


async def handle_member_left(update, context, db, admin_id, target_chat_id):
    """Handle user leaving OR returning to chat"""
    if update.chat_member.chat.id != target_chat_id:
        return
    
    old_status = update.chat_member.old_chat_member.status
    new_status = update.chat_member.new_chat_member.status
    new_member = update.chat_member.new_chat_member
    user_id = new_member.user.id
    
    logging.info(f"👤 Chat member update: user {user_id}, {old_status} → {new_status}")
    
    # ═══ ОПРЕДЕЛЯЕМ ТИП СОБЫТИЯ ═══
    
    # 1. Мут / ограничение (restricted, но пользователь ещё в чате)
    #    → НЕ считается уходом
    if new_status == 'restricted' and getattr(new_member, 'is_member', True):
        logging.info(f"🔇 User {user_id} was MUTED/RESTRICTED (still in chat) — ignoring")
        return
    
    # 2. Временный бан (kicked с until_date) — модботы так делают мут
    #    → НЕ считается уходом
    if new_status == 'kicked' and getattr(new_member, 'until_date', None):
        logging.info(
            f"🔇 User {user_id} got TEMPORARY BAN until {new_member.until_date} "
            f"— treating as mute, ignoring"
        )
        return
    
    # 3. Снятие ограничений (restricted → member) — просто размут
    #    → НЕ считается возвращением
    if new_status == 'member' and old_status == 'restricted':
        logging.info(f"🔊 User {user_id} was UNMUTED (restricted → member) — ignoring")
        return
    
    # === ПОЛЬЗОВАТЕЛЬ УШЁЛ ===
    if new_status in ('left', 'kicked') and old_status in ('member', 'restricted', 'administrator', 'creator'):
        await handle_user_left(update, context, user_id, db, admin_id, target_chat_id)
    
    # === ПОЛЬЗОВАТЕЛЬ ВЕРНУЛСЯ ===
    elif new_status in ('member', 'restricted') and old_status in ('left', 'kicked'):
        await handle_user_returned(update, context, user_id, db, admin_id, target_chat_id)

async def get_chat_invite_link(context, target_chat_id, chat_id=None, user_name=None):
    """Generate a ONE-TIME invite link (member_limit=1) for a specific user leaving the chat"""
    target_chat = chat_id or target_chat_id
    
    # Generate a unique one-time link via Telegram API
    try:
        link_name = f"Return: {user_name}" if user_name else "Return invite"
        link_obj = await context.bot.create_chat_invite_link(
            chat_id=target_chat,
            name=link_name[:32],  # Telegram limit 32 chars
            member_limit=1,  # ← одноразовая ссылка!
            creates_join_request=False
        )
        invite_link = link_obj.invite_link
        logging.info(f"🔗 Generated ONE-TIME invite for chat {target_chat}: {invite_link}")
        return invite_link
    except Exception as e:
        logging.error(f"Error creating one-time invite link for chat {target_chat}: {e}")
    
    # Fallback: try to get existing export link (not one-time, but better than nothing)
    try:
        chat = await context.bot.get_chat(target_chat)
        if chat.invite_link:
            logging.warning(f"⚠️ Using generic chat invite link as fallback for {target_chat}")
            return chat.invite_link
    except Exception as e:
        logging.error(f"Error getting chat info for {target_chat}: {e}")
    
    return None

async def handle_user_left(update, context, user_id, db, admin_id, target_chat_id):
    """Handle user leaving the chat — freeze balance for 30 days"""
    user_data = db.get_user(user_id)
    if not user_data:
        return
    
    balance = user_data['balance']
    
    # Пометить пользователя как покинувшего чат
    db.cursor.execute('UPDATE users SET is_left = 1 WHERE user_id = ?', (user_id,))
    db.conn.commit()
    
    # Get user info for notification
    username = user_data['username']
    first_name = user_data['first_name'] or 'Unknown'
    user_mention = f"@{username}" if username else first_name
    
    # Get current Moscow time
    now = datetime.now()
    months_ru = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    formatted_time = f"{now.day} {months_ru[now.month]} {now.year} / {now.strftime('%H:%M:%S')} MSK"
    
    # Freeze balance for 30 days BEFORE zeroing
    freeze_until = now + timedelta(days=30)
    db.cursor.execute('''
        UPDATE users 
        SET frozen_balance = ?, freeze_until = ?
        WHERE user_id = ?
    ''', (balance, freeze_until, user_id))
    db.conn.commit()
    
    if balance > 0:
        db.update_user_balance(user_id, 0, 'set')
        db.update_bank_balance(balance, 'add')
        db.add_transaction(
            user_id,
            None,  # To bank
            balance,
            'return_on_leave',
            f'Покинул чат, баланс заморожен на 30 дней и возвращён в банк'
        )
        
        # Notify owner with detailed info
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"Пользователь покинул чат.\n"
                     f"Имя {user_mention} [{user_id}] #user{user_id}\n"
                     f"👋 Время: {formatted_time}\n"
                     f"❄️ {format_number(balance)} Пульсов заморожено на 30 дней.\n"
                     f"🏦 Баланс Банка: {format_number(db.get_bank_balance())} Пульсов"
            )
        except Exception as e:
            logging.error(f"Error sending leave notification: {e}")
    else:
        # Notify even if balance is 0
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"Пользователь покинул чат.\n"
                     f"Имя {user_mention} [{user_id}] #user{user_id}\n"
                     f"👋 Время: {formatted_time}\n"
                     f"💎 Баланс: 0 Пульсов"
            )
        except Exception as e:
            logging.error(f"Error sending leave notification: {e}")
    
    # ═══ ЖУРНАЛ: логируем выход ═══
    try:
        await log_leave(context.bot, db, user_id)
    except Exception as e:
        logging.error(f"Journal log_leave error: {e}")

    # ═══ BBS: удалить анкету покинувшего пользователя ═══
    try:
        await on_member_left_cleanup(context.bot, db, user_id, target_chat_id)
    except Exception as e:
        logging.error(f"BBS cleanup error: {e}")

    # ═══ Запуск exit-опроса при любом выходе пользователя ═══
    try:
        from handlers.exit_survey_handlers import handle_exit_reason
        # Имитация нажатия первой кнопки (Q1) — можно доработать под свою функцию старта
        class DummyQuery:
            def __init__(self, user_id):
                self.data = f"exit_boring_{user_id}"
            async def answer(self, *a, **kw):
                pass
            async def edit_message_text(self, *a, **kw):
                pass
        dummy_query = DummyQuery(user_id)
        await handle_exit_reason(dummy_query, f"exit_boring_{user_id}", context, db, admin_id)
    except Exception as e:
        logging.error(f"Exit survey trigger error: {e}")

    # ═══ EXIT SURVEY: отправляем опрос ═══
    try:
        user_link = f"@{username}" if username else (user_data['first_name'] or 'Друг')
        
        # Get ONE-TIME invite link for THIS chat and THIS user
        chat_id = update.chat_member.chat.id
        invite_link = await get_chat_invite_link(context, target_chat_id, chat_id, user_link)
        
        keyboard = [
            [
                InlineKeyboardButton("🔇 Много флуда", callback_data=f"exit_flood_{user_id}"),
                InlineKeyboardButton("🥱 Стало скучно", callback_data=f"exit_boring_{user_id}")
            ],
            [
                InlineKeyboardButton("📉 Низкое качество", callback_data=f"exit_quality_{user_id}"),
                InlineKeyboardButton("☠️ Токсичность", callback_data=f"exit_toxic_{user_id}")
            ],
            [
                InlineKeyboardButton("👮‍♂️ Действия админов", callback_data=f"exit_admins_{user_id}"),
                InlineKeyboardButton("👤 Личное", callback_data=f"exit_personal_{user_id}")
            ],
            [InlineKeyboardButton("📝 Написать причину", callback_data=f"exit_custom_{user_id}")]
        ]
        
        # Add "Return to chat" button if invite link is available
        if invite_link:
            keyboard.insert(0, [InlineKeyboardButton("🔄 Вернуться в чат", url=invite_link)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        frozen_msg = ""
        if balance > 0:
            frozen_msg = (
                f"\n\n❄️ Твои {format_number(balance)} Пульсов заморожены на 30 дней. "
                f"Если вернёшься — они вернутся на твой счёт!"
            )
        
        # Build invite text
        if invite_link:
            invite_text = (
                f"Если ты это сделал случайно — держи свою личную одноразовую ссылку для возвращения. "
                f"Нажми кнопку «Вернуться в чат» ниже или перейди по ссылке: {invite_link}"
            )
        else:
            invite_text = (
                f"Если ты это сделал случайно — попроси ссылку для возврата у администратора."
            )
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Привет, {user_link}! Мы заметили, что ты покинул чат Pulse. "
                     f"{invite_text}\n\n"
                     f"Мы напоминаем, что Pulse – это не просто чат, а место, где ты можешь не только общаться, "
                     f"но и знакомиться, встречаться офлайн, а также задавать вопросы, касающиеся твоего здоровья. "
                     f"В чате работают равные консультанты, которые подскажут, в каком направлении двигаться или "
                     f"помогут с интерпретацией твоих анализов.\n\n"
                     f"Если ты действительно решил покинуть чат, знай, нам очень жаль расставаться! 😔"
                     f"{frozen_msg}\n\n"
                     f"Мы хотим стать лучше. Если не сложно, нажми на кнопку, чтобы указать причину ухода?",
                reply_markup=reply_markup
            )
            
            logging.info(f"✅ Exit interview sent to user {user_id}")
            
        except telegram.error.Forbidden:
            logging.warning(f"❌ Cannot send exit interview to {user_id} - bot not started by user")
            db.cursor.execute('''
                INSERT INTO exit_interviews (user_id, reason, response_text, submitted_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, 'bot_not_started', 'Не удалось отправить - бот не запущен пользователем'))
            db.conn.commit()
        except Exception as send_error:
            logging.error(f"❌ Error sending exit interview to {user_id}: {send_error}")
        
    except Exception as e:
        logging.error(f"Error in exit interview flow: {e}")

async def handle_user_returned(update, context, user_id, db, admin_id, target_chat_id):
    """Handle user returning to chat — unfreeze balance if within 30 days"""
    # Удаляем сообщение с одноразовой ссылкой (если было отправлено при одобрении)
    try:
        from database.db_friend import get_user as get_reg_user, deactivate_invite_link, get_active_invite_link, update_user as update_reg_user
        reg_user = await get_reg_user(user_id)
        if reg_user:
            invite_msg_id = reg_user.get('invite_message_id')
            if invite_msg_id:
                try:
                    await context.bot.delete_message(chat_id=user_id, message_id=invite_msg_id)
                    logging.info(f"🗑 Deleted invite link message for user {user_id}")
                except Exception:
                    pass  # Сообщение уже удалено или недоступно
                await update_reg_user(user_id, invite_message_id=None)

            # Деактивируем ссылку в БД
            active_link = await get_active_invite_link(user_id)
            if active_link:
                await deactivate_invite_link(active_link)
                logging.info(f"🔗 Invite link deactivated for user {user_id}")
    except Exception as e:
        logging.error(f"Error cleaning up invite link for {user_id}: {e}")

    user_data = db.get_user(user_id)
    if not user_data:
        return

    # Пометить пользователя как вернувшегося
    db.cursor.execute('UPDATE users SET is_left = 0 WHERE user_id = ?', (user_id,))
    db.conn.commit()
    
    # sqlite3.Row does NOT support .get() — use bracket access
    try:
        frozen_balance = float(user_data['frozen_balance'] or 0)
    except (KeyError, IndexError):
        frozen_balance = 0
    
    try:
        freeze_until_str = user_data['freeze_until']
    except (KeyError, IndexError):
        freeze_until_str = None
    
    username = user_data['username']
    first_name = user_data['first_name'] or 'Unknown'
    user_mention = f"@{username}" if username else first_name
    
    logging.info(f"🔄 User {user_id} returned. frozen_balance={frozen_balance}, freeze_until={freeze_until_str}")
    
    if frozen_balance > 0 and freeze_until_str:
        # Parse freeze_until from database
        freeze_until = None
        try:
            if isinstance(freeze_until_str, str):
                # Try multiple datetime formats
                for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                    try:
                        freeze_until = datetime.strptime(freeze_until_str, fmt)
                        break
                    except ValueError:
                        continue
            else:
                freeze_until = freeze_until_str
        except Exception as e:
            logging.error(f"Error parsing freeze_until for user {user_id}: {e}")
        
        now = datetime.now()
        
        if freeze_until and now <= freeze_until:
            # ✅ В пределах 30 дней — РАЗМОРОЗИТЬ!
            
            # Забрать Пульсы из Банка обратно
            bank_balance = db.get_bank_balance()
            restore_amount = frozen_balance
            
            if bank_balance >= frozen_balance:
                db.update_bank_balance(frozen_balance, 'subtract')
            else:
                # Банк не может покрыть полностью — разморозить сколько есть
                logging.warning(
                    f"⚠️ Bank has {bank_balance}, need {frozen_balance} for unfreeze. "
                    f"Unfreezing {bank_balance} instead."
                )
                restore_amount = bank_balance
                db.update_bank_balance(bank_balance, 'subtract')
            
            # Вернуть баланс пользователю
            db.update_user_balance(user_id, restore_amount, 'add')
            db.add_transaction(
                None,  # From bank
                user_id,
                restore_amount,
                'unfreeze_on_return',
                f'Вернулся в чат, замороженный баланс восстановлен'
            )
            
            # Обнулить заморозку
            db.cursor.execute('''
                UPDATE users 
                SET frozen_balance = 0, freeze_until = NULL
                WHERE user_id = ?
            ''', (user_id,))
            db.conn.commit()
            
            logging.info(f"✅ Unfroze {restore_amount} pulses for user {user_id}")
            
            # Уведомить админа
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔄 Пользователь вернулся в чат!\n"
                         f"Имя {user_mention} [{user_id}] #user{user_id}\n"
                         f"✅ {format_number(restore_amount)} Пульсов разморожено и возвращено.\n"
                         f"🏦 Баланс Банка: {format_number(db.get_bank_balance())} Пульсов"
                )
            except Exception as e:
                logging.error(f"Error sending return notification: {e}")
            
            # Уведомить пользователя
            try:
                current_balance = db.get_user(user_id)['balance']
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 С возвращением!\n\n"
                         f"✅ Твои {format_number(restore_amount)} Пульсов разморожены "
                         f"и возвращены на твой счёт!\n"
                         f"💰 Текущий баланс: {format_number(current_balance)} 💎"
                )
            except Exception as e:
                logging.error(f"Error sending welcome back message: {e}")
        
        else:
            # ❌ Прошло больше 30 дней — заморозка истекла
            db.cursor.execute('''
                UPDATE users 
                SET frozen_balance = 0, freeze_until = NULL
                WHERE user_id = ?
            ''', (user_id,))
            db.conn.commit()
            
            logging.info(f"⏰ Freeze expired for user {user_id}, {frozen_balance} pulses lost")
            
            # Уведомить админа
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔄 Пользователь вернулся в чат.\n"
                         f"Имя {user_mention} [{user_id}]\n"
                         f"⏰ Заморозка истекла — {format_number(frozen_balance)} Пульсов остались в Банке."
                )
            except Exception as e:
                logging.error(f"Error sending return notification: {e}")
            
            # Уведомить пользователя
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"👋 С возвращением!\n\n"
                         f"К сожалению, 30 дней заморозки истекли, "
                         f"и твои Пульсы вернуть не удалось.\n"
                         f"Но ты можешь начать зарабатывать заново! 💪"
                )
            except Exception as e:
                logging.error(f"Error sending expired freeze message: {e}")
    
    else:
        # Нет замороженных Пульсов — просто уведомить админа
        logging.info(f"🔄 User {user_id} returned, no frozen balance")
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔄 Пользователь вернулся в чат.\n"
                     f"Имя {user_mention} [{user_id}]\n"
                     f"💎 Замороженных Пульсов нет."
            )
        except Exception as e:
            logging.error(f"Error sending return notification: {e}")

    # ═══ ЖУРНАЛ: логируем вход ═══
    try:
        await log_join(context.bot, db, user_id)
    except Exception as e:
        logging.error(f"Journal log_join error: {e}")

async def handle_reaction(update, context, db, target_chat_id):
    """Handle message reactions"""
    
    reaction_update = update.message_reaction
    
    if not reaction_update:
        logging.debug("❌ No reaction in update")
        return
    
    # Only process reactions from target chat
    if reaction_update.chat.id != target_chat_id:
        logging.debug(f"⚠️ Skipping reaction: wrong chat {reaction_update.chat.id}")
        return
    
    # ═══ BBS: проверить, относится ли реакция к BBS-анкете ═══
    await handle_bbs_reaction(reaction_update, context, db, target_chat_id)
    
    user = reaction_update.user  # Кто поставил реакцию
    
    today = get_today_date_msk()
    
    db.add_user(
        user.id,
        user.username,
        user.first_name,
        user.last_name
    )
    
    new_reaction = reaction_update.new_reaction
    old_reaction = reaction_update.old_reaction
    
    added_count = len(new_reaction) if new_reaction else 0
    removed_count = len(old_reaction) if old_reaction else 0
    
    net_change = added_count - removed_count
    
    if net_change == 0:
        return
    
    logging.info(f"👍 Reaction update: user {user.id} net_change={net_change}")
    
    if net_change != 0:
        db.update_user_activity(user.id, today, reactions_given=abs(net_change))
    
    try:
        message_id = reaction_update.message_id
        
        db.cursor.execute('''
            SELECT user_id FROM messages 
            WHERE chat_id = ? AND telegram_message_id = ?
            LIMIT 1
        ''', (reaction_update.chat.id, message_id))
        
        result = db.cursor.fetchone()
        
        if result:
            message_author_id = result['user_id']
            if message_author_id != user.id:
                db.update_user_activity(message_author_id, today, reactions_received=abs(net_change))
                logging.info(f"👍 User {message_author_id} received {abs(net_change)} reactions from {user.id}")
        else:
            logging.warning(f"⚠️ Could not find message author for reaction")
    
    except Exception as e:
        logging.error(f"Error updating reactions_received: {e}")
    
    try:
        db.cursor.execute('''
            INSERT INTO chat_stats (date, total_reactions)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_reactions = total_reactions + excluded.total_reactions
        ''', (today, abs(net_change)))
        db.conn.commit()
    except Exception as e:
        logging.error(f"Error updating chat_stats reactions: {e}")
