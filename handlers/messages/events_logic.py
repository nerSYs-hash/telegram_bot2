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
from utils.helpers import format_number, get_today_date_msk, get_moscow_time
from handlers.bbs_handlers import handle_bbs_reaction, on_member_left_cleanup
from handlers.journal_handlers import log_join, log_leave, log_kick
from handlers.messages.mining_logic import (
    calculate_social_combos, calculate_reaction_given_reward,
    calculate_reaction_received_reward, _get_claimed_combos,
    _save_combo_claims, GLOBAL_BASE_RATE,
)


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
    
    is_now_in_chat = new_status in ('member', 'creator', 'administrator') or (new_status == 'restricted' and getattr(new_member, 'is_member', True))
    was_in_chat = old_status in ('member', 'creator', 'administrator') or (old_status == 'restricted' and getattr(update.chat_member.old_chat_member, 'is_member', True))
    
    # 1. Мут / ограничение (пользователь осталось в чате)
    if is_now_in_chat and was_in_chat and old_status != new_status:
        logging.info(f"🔊/🔇 User {user_id} permissions changed (still in chat) — ignoring")
        return
        
    # 2. Временный бан (kicked с until_date) — рассматривается как мут
    if new_status == 'kicked' and getattr(new_member, 'until_date', None) and was_in_chat:
        logging.info(f"🔇 User {user_id} got TEMPORARY BAN until {new_member.until_date} — treating as mute, ignoring")
        return
        
    # === ПОЛЬЗОВАТЕЛЬ ИСКЛЮЧЁН АДМИНОМ ===
    if not is_now_in_chat and was_in_chat and new_status == 'kicked':
        kicker = update.chat_member.from_user
        if kicker and kicker.id != user_id:
            logging.info(f"🆘 Triggering KICK log for user {user_id} by {kicker.id}")
            try:
                await log_kick(
                    context.bot, db,
                    target_id=user_id,
                    admin_id=kicker.id,
                    chat_id=update.chat_member.chat.id,
                    chat_title=update.chat_member.chat.title,
                    kicked_at=update.chat_member.date,
                    target_user=update.chat_member.new_chat_member.user,
                    admin_user=kicker,
                )
            except Exception as e:
                logging.error(f"Journal log_kick error: {e}")

    # === ПОЛЬЗОВАТЕЛЬ УШЁЛ ===
    if not is_now_in_chat and was_in_chat:
        logging.info(f"👋 Triggering LEAVE logic for user {user_id}")
        await handle_user_left(update, context, user_id, db, admin_id, target_chat_id)
    
    # === ПОЛЬЗОВАТЕЛЬ ВЕРНУЛСЯ ===
    elif is_now_in_chat and not was_in_chat:
        logging.info(f"🔄 Triggering RETURN logic for user {user_id}")
        await handle_user_returned(update, context, user_id, db, admin_id, target_chat_id)

async def get_chat_invite_link(context, target_chat_id, chat_id=None, user_name=None):
    """Generate a ONE-TIME invite link (creates_join_request=True) for a specific user leaving the chat"""
    target_chat = chat_id or target_chat_id
    
    # Generate a unique one-time link via Telegram API
    try:
        link_name = f"Return: {user_name}" if user_name else "Return invite"
        link_obj = await context.bot.create_chat_invite_link(
            chat_id=target_chat,
            name=link_name[:32],  # Telegram limit 32 chars
            creates_join_request=True
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
        try:
            user = update.chat_member.new_chat_member.user
            db.add_user(user.id, user.username, user.first_name, user.last_name)
            user_data = db.get_user(user_id)
        except Exception as e:
            logging.error(f"Error adding missing user {user_id} on leave: {e}")
            return
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
    
    # Всегда фиксируем выход (транзакция нужна для подсчёта вышедших в статистике)
    if balance > 0:
        db.update_user_balance(user_id, 0, 'set')
        db.update_bank_balance(balance, 'add')
        db.add_transaction(
            user_id,
            None,
            balance,
            'return_on_leave',
            'Покинул чат, баланс заморожен на 30 дней и возвращён в банк'
        )
    else:
        # Баланс 0 — транзакцию всё равно создаём для учёта в статистике
        db.add_transaction(
            user_id,
            None,
            0,
            'return_on_leave',
            'Покинул чат (баланс 0)'
        )
    
    # ═══ db_friend: сохраняем last_exit_at (для метки #Возвращение при повторной заявке) ═══
    try:
        from database.db_friend import update_user as update_reg_user
        await update_reg_user(user_id, last_exit_at=datetime.now().isoformat(), status='left')
    except Exception as e:
        logging.error(f"db_friend last_exit_at update error: {e}")

    # ═══ ЖУРНАЛ: логируем выход ═══
    try:
        cm = update.chat_member
        await log_leave(
            context.bot, db, user_id,
            chat=cm.chat,
            tg_user=cm.new_chat_member.user,
            left_at=cm.date,
        )
    except Exception as e:
        logging.error(f"Journal log_leave error: {e}")

    # ═══ BBS: удалить анкету покинувшего пользователя ═══
    try:
        await on_member_left_cleanup(context.bot, db, user_id, target_chat_id)
    except Exception as e:
        logging.error(f"BBS cleanup error: {e}")

    # ═══ EXIT SURVEY: отправляем опрос пользователю ═══
    try:
        from database.db_friend import (
            should_send_survey,
            update_user as update_reg_user
        )

        if not await should_send_survey(user_id):
            logging.info(f"⏭ Skip exit survey for user {user_id} (already sent recently)")
            return

        user_link = f"@{username}" if username else (user_data['first_name'] or 'Друг')

        chat_id = update.chat_member.chat.id
        invite_link = await get_chat_invite_link(context, target_chat_id, chat_id, user_link)

        context.bot_data['exit_survey_chat_id'] = target_chat_id
        try:
            target_user_data = context.application.user_data.setdefault(user_id, {})
            target_user_data['exit_survey_chat_id'] = target_chat_id
            if invite_link:
                target_user_data['exit_survey_invite_link'] = invite_link
        except Exception:
            pass

        reasons = [
            ("😴 Скучно",            f"exit_boring_{user_id}"),
            ("👥 Одни и те же лица", f"exit_same_faces_{user_id}"),
            ("🧍 Мало народа",       f"exit_few_people_{user_id}"),
            ("🤔 Другие ожидания",   f"exit_other_expect_{user_id}"),
            ("🔇 Много флуда",       f"exit_flood_{user_id}"),
            ("⚠️ Угрозы/Шантаж",     f"exit_threats_{user_id}"),
            ("🙈 Меня игнорят",      f"exit_ignored_{user_id}"),
            ("😮‍💨 Надоело",           f"exit_tired_{user_id}"),
            ("💕 Нашел любовь",      f"exit_love_{user_id}"),
            ("📭 Нет нужной инфы",   f"exit_no_info_{user_id}"),
            ("🚫 Не зашло",          f"exit_not_fit_{user_id}"),
            ("☠️ Токсичность",        f"exit_toxic_{user_id}"),
            ("⏰ Нет времени",        f"exit_no_time_{user_id}"),
            ("🔔 Много уведомлений", f"exit_notifs_{user_id}"),
            ("📝 Другое",            f"exit_other_{user_id}"),
        ]
        keyboard = [
            [InlineKeyboardButton(reasons[i][0], callback_data=reasons[i][1]),
             InlineKeyboardButton(reasons[i+1][0], callback_data=reasons[i+1][1])]
            for i in range(0, len(reasons) - 1, 2)
        ]
        keyboard.append([InlineKeyboardButton(reasons[-1][0], callback_data=reasons[-1][1])])
        if invite_link:
            keyboard.insert(0, [InlineKeyboardButton("🔄 Вернуться в чат", url=invite_link)])

        frozen_msg = ""
        if balance > 0:
            frozen_msg = (
                f"\n\n❄️ Твои {format_number(balance)} Пульсов заморожены на 30 дней. "
                f"Если вернёшься — они вернутся на твой счёт!"
            )

        invite_text = (
            "Если это случайность — нажми кнопку «Вернуться в чат» ниже."
            if invite_link else
            "Если это случайность — попроси ссылку для возврата у администратора."
        )

        try:
            msg = await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"Привет, {user_link}! Мы заметили, что ты покинул чат Pulse 😔\n\n"
                    f"{invite_text}\n\n"
                    f"Pulse — это не просто чат. Здесь можно знакомиться, встречаться офлайн, "
                    f"получать консультации равного консультанта по теме здоровья.\n\n"
                    f"Нам очень жаль расставаться!{frozen_msg}\n\n"
                    f"Если не сложно — нажми кнопку и укажи причину ухода. Это займёт пару минут:"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await update_reg_user(
                user_id,
                survey_sent_at=datetime.now().isoformat(),
                invite_message_id=msg.message_id
            )
            logging.info(f"✅ Exit survey sent to user {user_id}, msg_id={msg.message_id}")

        except telegram.error.Forbidden:
            logging.warning(f"❌ Cannot send exit survey to {user_id} - bot not started by user")
            try:
                db.cursor.execute(
                    'INSERT INTO exit_interviews (user_id, reason_category) VALUES (?, ?)',
                    (user_id, 'bot_not_started')
                )
                db.conn.commit()
            except Exception:
                pass
        except Exception as send_error:
            logging.error(f"❌ Error sending exit survey to {user_id}: {send_error}")

    except Exception as e:
        logging.error(f"Error in exit survey flow: {e}")

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
            
            # СИНХРОНИЗАЦИЯ: помечаем пользователя как 'in_chat' в базе регистраций
            await update_reg_user(user_id, status='in_chat')
            logging.info(f"✅ Status synchronized to 'in_chat' for user {user_id}")
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

            # Уведомить только пользователя (информация для админа — в Журнале)
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
        # Нет замороженных Пульсов — информация в Журнале, ЛС админу не нужно
        logging.info(f"🔄 User {user_id} returned, no frozen balance")

    # ═══ ЖУРНАЛ: логируем вход ═══
    try:
        cm = update.chat_member
        try:
            _is_ret = bool(user_data['is_left'])
        except (KeyError, IndexError, TypeError):
            _is_ret = False
        # Подтягиваем имя из анкеты (регистрационная БД)
        _q_name = None
        if _is_ret:
            try:
                from database.db_friend import get_user as _get_reg_user
                _reg = await _get_reg_user(user_id)
                if _reg:
                    _q_name = _reg.get('q_name')
            except Exception:
                pass
        await log_join(
            context.bot, db, user_id,
            chat=cm.chat,
            tg_user=cm.new_chat_member.user,
            from_user=cm.from_user,
            invite_link=cm.invite_link,
            joined_at=cm.date,
            is_returning=_is_ret,
            q_name=_q_name,
        )
    except Exception as e:
        logging.error(f"Journal log_join error: {e}")

async def handle_reaction(update, context, db, target_chat_id):
    """обработка реакций (Защита от накрутки и инфляции)"""
    reaction_update = update.message_reaction
    
    if not reaction_update or reaction_update.chat.id != target_chat_id:
        return

    # ═══ BBS: проверить, относится ли реакция к BBS-анкете ═══
    await handle_bbs_reaction(reaction_update, context, db, target_chat_id)
    
    user = reaction_update.user
    today = get_today_date_msk()
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    new_reaction = reaction_update.new_reaction
    old_reaction = reaction_update.old_reaction
    
    added_count = len(new_reaction) if new_reaction else 0
    removed_count = len(old_reaction) if old_reaction else 0
    
    # Считаем чистую разницу
    net_change = added_count - removed_count
    # ВАЖНО: Если реакция удалена (net_change <= 0), мы просто выходим.
    # Мы не даем награду и не повышаем статистику за удаление лайка!
    if net_change <= 0:
        return

    actual_increment = 1
    message_id = reaction_update.message_id

    logging.info(f"👍 Reaction ADDED: user {user.id}")

    # 1. ОБНОВЛЯЕМ СТАТИСТИКУ ТОМУ, КТО ПОСТАВИЛ (Giver)
    react_given_eid = f"react_given_{user.id}_{message_id}_{today}"
    db.update_user_activity(user.id, today, event_id=react_given_eid, reactions_given=actual_increment)
    try:
        from utils.helpers import get_moscow_time
        now_msk = get_moscow_time()
        db.update_user_activity_hourly(user.id, today, now_msk.hour, reactions_given=actual_increment)
    except Exception: pass

    # 2. ИЩЕМ АВТОРА СООБЩЕНИЯ И ОБНОВЛЯЕМ ЕМУ
    try:
        db.cursor.execute('''
            SELECT user_id FROM messages
            WHERE chat_id = ? AND telegram_message_id = ?
            LIMIT 1
        ''', (reaction_update.chat.id, message_id))

        result = db.cursor.fetchone()

        if result:
            message_author_id = result['user_id']
            # Себе лайки не считаем в статистику полученных
            if message_author_id != user.id:
                react_recv_eid = f"react_recv_{message_author_id}_{message_id}_{today}"
                db.update_user_activity(message_author_id, today, event_id=react_recv_eid, reactions_received=actual_increment)
                try:
                    db.update_user_activity_hourly(message_author_id, today, now_msk.hour, reactions_received=actual_increment)
                except Exception: pass
                logging.info(f"👍 User {message_author_id} received reaction from {user.id}")
        
    except Exception as e:
        logging.error(f"Error updating reactions_received: {e}")

    # 3. НАЧИСЛЕНИЕ НАГРАД (Только за добавление!)
    try:
        # Награда тому, кто поставил
        rg_reward = calculate_reaction_given_reward()
        if rg_reward > 0:
            if db.get_bank_balance() >= rg_reward:
                db.update_user_balance(user.id, rg_reward, 'add')
                db.update_bank_balance(rg_reward, 'subtract')
                db.add_transaction(None, user.id, rg_reward, 'reaction_given_reward', 'Реакция')

        # Награда автору поста
        if result and result['user_id'] != user.id:
            author_id = result['user_id']
            rr_reward = calculate_reaction_received_reward()
            if rr_reward > 0:
                if db.get_bank_balance() >= rr_reward:
                    db.update_user_balance(author_id, rr_reward, 'add')
                    db.update_bank_balance(rr_reward, 'subtract')
                    db.add_transaction(None, author_id, rr_reward, 'reaction_received_reward', 'Получена реакция')

            # Проверка социальных комбо
            now = get_moscow_time()
            claimed_combos = _get_claimed_combos(db, author_id, now)

            db.cursor.execute('''
                SELECT COALESCE(reactions_received, 0) AS rr, COALESCE(replies_received, 0) AS rep
                FROM user_stats WHERE user_id = ? AND date = ?
            ''', (author_id, today))
            stats_row = db.cursor.fetchone()
            
            combo_reward, new_combos = calculate_social_combos(
                reply_count=stats_row['rep'] if stats_row else 0,
                reaction_count=stats_row['rr'] if stats_row else 0,
                completed_today=list(claimed_combos.keys()),
            )

            if combo_reward > 0 and new_combos:
                if db.get_bank_balance() >= combo_reward:
                    db.update_user_balance(author_id, combo_reward, 'add')
                    db.update_bank_balance(combo_reward, 'subtract')
                    db.add_transaction(None, author_id, combo_reward, 'combo_reward', 'Тайное Комбо (соц.)')
                    _save_combo_claims(db, author_id, new_combos, combo_reward, now)

    except Exception as e:
        logging.error(f"Error in reaction rewards: {e}")
