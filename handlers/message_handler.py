#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telegram
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
from handlers.messages.mining_logic import _is_emoji_only
import os
from utils.helpers import (
    is_media_message, count_words, get_today_date_msk,
    format_number
)
from handlers.messages.mining_logic import process_mining_reward

from handlers.messages.events_logic import (
    handle_member_left, handle_reaction,
)
from handlers.messages.admin_logic import (
    process_admin_input,
    publish_press_release,
    publish_press_release_to_target,
)
from handlers.messages.top_and_stats import show_top_rich, show_top_activists
from handlers.commands.exchange_commands import course_command as _course_command
from handlers.BBS.fsm_input_bbs import process_bbs_input


async def _delete_msg_job(context):
    """Job: удаляет сообщение бота через минуту после триггера курс/активисты/богач."""
    try:
        d = context.job.data
        await context.bot.delete_message(chat_id=d['chat_id'], message_id=d['message_id'])
    except Exception:
        pass


def _schedule_auto_delete(context, chat_id: int, message_id: int, delay: int = 60):
    """Планирует удаление сообщения через delay секунд."""
    try:
        context.job_queue.run_once(
            _delete_msg_job, when=delay,
            data={'chat_id': chat_id, 'message_id': message_id},
            name=f"autodel_{message_id}",
        )
    except Exception as e:
        logging.warning(f"_schedule_auto_delete: {e}")
from handlers.owner_handlers import handle_owner_text_input
from handlers.shipper_logic import try_activate_shipper_resonance


# ═══ Тексты кнопок ReplyKeyboard (должны совпадать с system_commands.py) ═══
REPLY_BTN_PROFILE = "👤 Профиль"
REPLY_BTN_BALANCE = "💰 Баланс"
REPLY_BTN_COURSE = "📊 Курс"
REPLY_BTN_TOP5 = "🏆 ТОП-5"
REPLY_BTN_MENU = "📋 Меню"
REPLY_BTN_ACTIVITIES = "🎯 Активности"
REPLY_BTN_BANK = "🏦 Центробанк"
REPLY_BTN_DETAIL = "📋 Детализация"
REPLY_BTN_FAQ = "❓ FAQ"
REPLY_BTN_OWNER_PANEL = "👑 Панель Владельца"
REPLY_BTN_SHIPPER = "💘 Шиппер"
REPLY_BTN_NEW_APPS = "📋 Новые заявки"
# Кнопки панели владельца в треде заявок
REPLY_BTN_ADMINS = "👥 Админы"
REPLY_BTN_BLACKLIST = "🚫 Черный список"
REPLY_BTN_CHECK_USER = "🔍 Проверка ника"
REPLY_BTN_TRIGGERS = "⚡ Триггеры"
REPLY_BTN_JOURNAL = "📓 Журнал"
REPLY_BTN_STATS = "📊 Статистика"
REPLY_BTN_NOT_IN_CHAT = "📊 Не в чате"
REPLY_BTN_ECONOMY = "💰 Экономика"
REPLY_BTN_SYSTEM = "⚙️ Система"
REPLY_BTN_BACKUP = "💾 Скачать БД"
REPLY_BUTTONS = {REPLY_BTN_BALANCE, REPLY_BTN_PROFILE, REPLY_BTN_COURSE, REPLY_BTN_TOP5, REPLY_BTN_MENU,
                 REPLY_BTN_ACTIVITIES, REPLY_BTN_BANK, REPLY_BTN_DETAIL, REPLY_BTN_FAQ,
                 REPLY_BTN_OWNER_PANEL, REPLY_BTN_SHIPPER, REPLY_BTN_NEW_APPS,
                 REPLY_BTN_ADMINS, REPLY_BTN_BLACKLIST, REPLY_BTN_CHECK_USER,
                 REPLY_BTN_TRIGGERS, REPLY_BTN_JOURNAL, REPLY_BTN_STATS,
                 REPLY_BTN_NOT_IN_CHAT, REPLY_BTN_ECONOMY, REPLY_BTN_SYSTEM, REPLY_BTN_BACKUP}


class MessageHandler:
    def __init__(self, db, target_chat_id, main_admin_id):
        self.db = db
        self.target_chat_id = target_chat_id
        self.main_admin_id = main_admin_id
        
        # Cache for chat administrators
        self.chat_admins_cache = set()
        self.last_admin_check = None
        self.admin_cache_duration = 300  # 5 minutes in seconds
        
        # Load excluded user IDs from environment
        excluded_ids = os.getenv('EXCLUDED_USER_IDS', '')
        self.excluded_user_ids = set()
        if excluded_ids:
            try:
                self.excluded_user_ids = {int(uid.strip()) for uid in excluded_ids.split(',') if uid.strip()}
            except ValueError:
                import logging
                logging.warning(f"Invalid EXCLUDED_USER_IDS format in .env: {excluded_ids}")
      
    async def get_chat_administrators(self, context):
        """Get list of chat administrators with caching"""
        import logging
        from datetime import datetime, timedelta
        
        # Check if cache is still valid
        now = datetime.now()
        if self.last_admin_check and (now - self.last_admin_check).total_seconds() < self.admin_cache_duration:
            return self.chat_admins_cache
        
        try:
            # Get administrators from Telegram API
            admins = await context.bot.get_chat_administrators(self.target_chat_id)
            self.chat_admins_cache = {admin.user.id for admin in admins}
            self.last_admin_check = now
            
            logging.info(f"👮 Updated admin cache: {len(self.chat_admins_cache)} administrators")
            return self.chat_admins_cache
            
        except Exception as e:
            logging.error(f"Error fetching chat administrators: {e}")
            return self.chat_admins_cache  # Return cached version on error
    
    def is_user_excluded(self, user_id, user_data, chat_admins=None):
        """Check if user should be excluded from rewards"""
        # 1. Check database flags
        if user_data and (user_data['is_admin'] or user_data['is_owner']):
            return True, "database_flag"
        
        # 2. Check main admin ID
        if user_id == self.main_admin_id:
            return True, "main_admin_id"
        
        # 3. Check manual exclusion list from .env
        if user_id in self.excluded_user_ids:
            return True, "excluded_list"
        
        # 4. Check Telegram chat administrators
        if chat_admins and user_id in chat_admins:
            return True, "telegram_admin"
        
        return False, None
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all messages in the chat"""
        message = update.message
        
        # DETAILED LOGGING FOR DEBUGGING
        import logging
        
        # Skip if no message
        if not message:
            logging.debug("❌ No message in update")
            return
        
        user = message.from_user

        # Игнорируем сообщения от ботов (ChatKeeper и т.д.)
        if user and user.is_bot:
            return

        # Get thread/topic information
        thread_id = message.message_thread_id  # None for main chat, int for topics
        # Передаем None для веток, чтобы БД не стирала реальное красивое имя фейковым!
        thread_name = "Главный чат" if thread_id is None else None
        
        logging.info(f"📨 Incoming message from user_id={user.id} (@{user.username}), "
                    f"chat_id={message.chat.id}, thread_id={thread_id} ({thread_name})")
        
        # Ввод причины отказа по заявке — работает и в ЛС, и в админ-чате
        if message.text and context.user_data.get('awaiting_reject_reason'):
            from handlers.admin_moderation import handle_reject_reason
            await handle_reject_reason(update, context)
            return

        # Only process messages from target chat
        # EXCEPTION: handle private messages from admin for press release / scheduled posts
        if message.chat.type == 'private':
            await self.handle_private_message(update, context)
            return
        
        if message.chat.id != self.target_chat_id:
            from config import ADMIN_CHAT_ID
            if message.chat.id == ADMIN_CHAT_ID:
                # Исключение: сообщения из ADMIN_CHAT_ID — обрабатываем кнопки и причину отказа
                if message.text and context.user_data.get('awaiting_reject_reason'):
                    from handlers.admin_moderation import handle_reject_reason
                    await handle_reject_reason(update, context)
                    return
                # FSM: ввод для панели (Админы, ЧС, Зам)
                if message.text and context.user_data.get('panel_awaiting'):
                    from handlers.admin_moderation import handle_panel_input
                    handled = await handle_panel_input(update, context)
                    if handled:
                        return
                # Обработка ReplyKeyboard кнопок в админском чате
                if message.text and message.text.strip() in REPLY_BUTTONS:
                    btn = message.text.strip()
                    if btn == REPLY_BTN_NEW_APPS:
                        from handlers.admin_moderation import handle_new_apps_text
                        await handle_new_apps_text(update, context)
                        return
                    elif btn in (REPLY_BTN_ADMINS, REPLY_BTN_BLACKLIST, REPLY_BTN_CHECK_USER,
                                 REPLY_BTN_TRIGGERS, REPLY_BTN_JOURNAL, REPLY_BTN_STATS,
                                 REPLY_BTN_NOT_IN_CHAT, REPLY_BTN_ECONOMY, REPLY_BTN_SYSTEM,
                                 REPLY_BTN_BACKUP):
                        from handlers.admin_moderation import handle_owner_panel_button
                        await handle_owner_panel_button(update, context, btn)
                        return
                    elif btn == REPLY_BTN_OWNER_PANEL:
                        from handlers.admin_moderation import send_admin_panel, _is_owner_or_deputy
                        is_owner = await _is_owner_or_deputy(user.id)
                        await send_admin_panel(context.bot, message.chat.id, is_owner=is_owner)
                        return
                    elif btn == REPLY_BTN_SHIPPER:
                        from handlers.shipper_handlers import send_shipper_panel
                        await send_shipper_panel(message, context, self.db, self.target_chat_id)
                        return
                # FSM: ввод комментария к баг-карточке прямо в треде
                if context.user_data.get('bug_awaiting_comment') and message.reply_to_message:
                    from handlers.bug_tracker_handlers import handle_bug_comment_input
                    if await handle_bug_comment_input(message, context, self.db):
                        return
                # FSM: редактирование анкеты (фото / примечание) в ADMIN_CHAT
                if context.user_data.get('anketa_edit'):
                    from handlers.anketa_edit_handlers import handle_anketa_edit_input
                    if await handle_anketa_edit_input(message, context, self.db):
                        return
                # Ветки багов: сообщения от владельца или разработчика → создаём трекер-карточку
                from config import BUG_THREAD_BOT, BUG_THREAD_SITE, OWNER_ID as _OWNER_ID, DEVELOPER_ID as _DEV_ID
                # Ответ на ДРУГОЕ сообщение (не на корень топика) — не создаём карточку
                _is_real_reply = (
                    message.reply_to_message is not None and
                    message.reply_to_message.message_id != message.message_thread_id
                )
                if user.id in (_OWNER_ID, _DEV_ID) and message.message_thread_id and not _is_real_reply:
                    if message.message_thread_id in (BUG_THREAD_BOT, BUG_THREAD_SITE):
                        from handlers.bug_tracker_handlers import handle_bug_message
                        try:
                            await handle_bug_message(message, context.bot, self.db)
                        except Exception as _bug_err:
                            logging.error(f"handle_bug_message exception: {_bug_err}", exc_info=True)
                            try:
                                await context.bot.send_message(
                                    chat_id=user.id,
                                    text=f"❌ BUG TRACKER ERROR:\n<code>{_bug_err}</code>",
                                    parse_mode="HTML"
                                )
                            except Exception:
                                pass
                        return
                return  # остальные сообщения из админского чата — игнорируем
            logging.warning(f"⚠️  Skipping: wrong chat. Got {message.chat.id}, expected {self.target_chat_id}")
            return
        
        # ═══ BBS THREAD: пропускаем всю обработку (триггеры, майнинг, статистику) ═══
        # В ветке BBS живут только анкеты, бот туда ничего не пишет
        bbs_thread_id = int(os.getenv('BBS_THREAD_ID', 0))
        if bbs_thread_id and message.message_thread_id == bbs_thread_id:
            logging.debug(f"⏭ Skipping BBS thread message from {user.id}")
            return
        
        # Skip if no text and no media
        if not message.text and not message.caption and not is_media_message(message):
            logging.warning(f"⚠️  Skipping: no text/caption/media from user {user.id}")
            return
        
        # Register/update topic in database
        self.db.register_topic(message.chat.id, thread_id, thread_name)
        
        # Log message processing
        logging.info(f"✅ Processing message from {user.id} (@{user.username}) in {thread_name}")
        
        # ═══ ТРЕКЕР ПРОФИЛЯ: вызываем ДО add_user, чтобы поймать старые данные ═══
        try:
            from handlers.profile_tracker import track_profile_changes
            await track_profile_changes(context.bot, self.db, user, chat=message.chat)
        except Exception as _pte:
            logging.debug(f"profile_tracker error: {_pte}")

        # Add/update user in database
        self.db.add_user(
            user.id,
            user.username,
            user.first_name,
            user.last_name
        )
        
        # Update last active
        self.db.cursor.execute(
            'UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?',
            (user.id,)
        )
        self.db.conn.commit()
        
        # ═══ БЛЭКЛИСТ: полностью игнорируем пользователя ═══
        try:
            _bl_check = self.db.get_user(user.id)
            if _bl_check and _bl_check['is_blacklisted']:
                return
        except (KeyError, IndexError):
            pass  # Колонка ещё не создана — пропускаем

        # ═══ ТЕХОБСЛУЖИВАНИЕ: игнорируем не-админов ═══
        if self.db.get_setting('maintenance_mode', '0') == '1':
            if user.id != self.main_admin_id:
                _maint_check = self.db.get_user(user.id)
                if not (_maint_check and (_maint_check['is_admin'] or _maint_check['is_owner'])):
                    return

        # Get today's date
        today = get_today_date_msk()
        
        # Calculate message stats
        text = message.text or message.caption or ""
        clean_text = text.lower().strip()
        char_count = len(text)
        word_count = count_words(text)
        is_media = is_media_message(message)
        is_reply = message.reply_to_message is not None
        
        # Слова-триггеры (не считаем как реальные сообщения)
        BOT_TRIGGERS = {'богач', 'богачи', 'активист', 'активисты', 'курс'}

        is_command    = text.strip().startswith('/')
        is_trigger    = clean_text in BOT_TRIGGERS
        is_btn_press  = text.strip() in REPLY_BUTTONS  # нажатие кнопки ReplyKeyboard

        # Игнорируем в статистике: команды, триггеры, нажатия кнопок
        should_ignore = is_command or is_trigger or is_btn_press
        
        # Check if reply is to self (exclude from statistics)
        is_self_reply = False
        if is_reply and message.reply_to_message.from_user:
            is_self_reply = message.reply_to_message.from_user.id == user.id
        
        # === ПАРСИМ УПОМЯНУТЫХ ПОЛЬЗОВАТЕЛЕЙ ===
        # Два типа entity:
        #   - mention (text @username) — нужно искать user_id по username
        #   - text_mention (тап по имени) — entity.user.id уже есть
        mentioned_user_ids = set()
        full_text = message.text or message.caption or ''
        if message.entities and full_text:
            for e in message.entities:
                if e.type == 'text_mention' and getattr(e, 'user', None):
                    mid = e.user.id
                    if mid != user.id and not e.user.is_bot:
                        mentioned_user_ids.add(mid)
                elif e.type == 'mention':
                    try:
                        raw = full_text[e.offset:e.offset + e.length]
                        username_clean = raw.lstrip('@').strip().lower()
                        if username_clean:
                            self.db.cursor.execute(
                                "SELECT user_id FROM users WHERE LOWER(username) = ? LIMIT 1",
                                (username_clean,)
                            )
                            row = self.db.cursor.fetchone()
                            if row and row['user_id'] != user.id:
                                mentioned_user_ids.add(row['user_id'])
                    except Exception as _me:
                        logging.debug(f"mention parse error: {_me}")

       # === ОБНОВЛЕНИЕ СТАТИСТИКИ ПОЛЬЗОВАТЕЛЯ ===
        if not should_ignore:
            _reply_to_real_user = (
                is_reply and not is_self_reply
                and message.reply_to_message.from_user
                and not message.reply_to_message.from_user.is_bot
            )
            stats_update = {
                'total_chars': char_count,
                'total_messages': 1,
                'total_words': word_count,
                'replies_sent': 1 if _reply_to_real_user else 0,
                'media_sent': 1 if is_media else 0,
                # mentions_received УБРАНО отсюда — это счётчик ПОЛУЧАТЕЛЯ упоминания, не отправителя
                'other_threads_posts': 1 if thread_id is not None else 0
            }

            # Записываем статистику отправителю (event_id = одно сообщение = один счёт)
            msg_eid = f"msg_{user.id}_{message.message_id}"
            self.db.update_user_activity(user.id, today, event_id=msg_eid, **stats_update)

            # --- ЛОГИКА ОТВЕТОВ (ВНУТРИ IF NOT SHOULD_IGNORE) ---
            if _reply_to_real_user:
                replied_to_user = message.reply_to_message.from_user
                reply_recv_eid = f"reply_recv_{replied_to_user.id}_{message.message_id}"
                self.db.update_user_activity(replied_to_user.id, today, event_id=reply_recv_eid, replies_received=1)
                try:
                    from utils.helpers import get_moscow_time
                    now_msk = get_moscow_time()
                    self.db.update_user_activity_hourly(replied_to_user.id, today, now_msk.hour, replies_received=1)
                except Exception: pass

            # --- ЛОГИКА УПОМИНАНИЙ: начисляем mentions_received КАЖДОМУ упомянутому ---
            for mentioned_id in mentioned_user_ids:
                mention_eid = f"mention_recv_{mentioned_id}_{message.message_id}"
                try:
                    self.db.update_user_activity(
                        mentioned_id, today,
                        event_id=mention_eid,
                        mentions_received=1,
                    )
                    try:
                        from utils.helpers import get_moscow_time
                        now_msk = get_moscow_time()
                        self.db.update_user_activity_hourly(
                            mentioned_id, today, now_msk.hour, mentions_received=1
                        )
                    except Exception: pass
                except Exception as _ue:
                    logging.warning(f"mentions_received update error for {mentioned_id}: {_ue}")
            
            # Почасовая статистика для отправителя
            try:
                from utils.helpers import get_moscow_time
                now_msk = get_moscow_time()
                self.db.update_user_activity_hourly(user.id, today, now_msk.hour, **stats_update)
            except Exception as e:
                logging.debug(f"Hourly stats error: {e}")

         # ═══ МГНОВЕННОЕ ОБНОВЛЕНИЕ КУРСА (дельта) ═══
        try:
            from utils.exchange_rate import rate_cache, calculate_message_delta
            if rate_cache.initialized and not rate_cache.is_manual:
                delta = calculate_message_delta(
                    char_count=char_count,
                    word_count=word_count,
                    is_reply=(is_reply and not is_self_reply),
                    is_media=is_media,
                    # has_mention применяется к КАЖДОМУ упомянутому (вес mentions_received)
                    has_mention=bool(mentioned_user_ids),
                    is_other_thread=(thread_id is not None)
                )
                rate_cache.apply_delta(delta)
        except Exception as e:
            logging.debug(f"Rate delta error: {e}")
        
        # Дельта курса за replies_received (статистика обновляется выше внутри should_ignore-блока)
        if is_reply and not is_self_reply and message.reply_to_message.from_user:
            replied_to_user_id = message.reply_to_message.from_user.id
            if replied_to_user_id != user.id:
                logging.info(f"📬 User {replied_to_user_id} received reply from {user.id}")
                try:
                    from utils.exchange_rate import rate_cache, calculate_reply_received_delta
                    if rate_cache.initialized and not rate_cache.is_manual:
                        rate_cache.apply_delta(calculate_reply_received_delta())
                except Exception:
                    pass
        
        # === ПРОВЕРКА АДМИНИСТРАТОРА (ПЕРЕД ИСПОЛЬЗОВАНИЕМ is_excluded) ===
        user_data = self.db.get_user(user.id)
        
        # Get current chat administrators from Telegram
        chat_admins = await self.get_chat_administrators(context)
        
        # Check if user should be excluded from rewards
        is_excluded, exclusion_reason = self.is_user_excluded(user.id, user_data, chat_admins)
        
        logging.info(f"👤 User {user.id}: is_admin={user_data['is_admin']}, is_owner={user_data['is_owner']}, "
                    f"in_chat_admins={user.id in chat_admins}, in_excluded_list={user.id in self.excluded_user_ids}, "
                    f"EXCLUDED={is_excluded}, reason={exclusion_reason}")
        
        # === СОХРАНЕНИЕ СООБЩЕНИЯ В БД ===
        # Save message to database with thread information and telegram message_id
        if message.video_note:
            message_type = 'video_note'
        elif message.voice:
            message_type = 'voice'
        elif message.video:
            message_type = 'video'
        elif message.photo:
            message_type = 'photo'
        elif message.audio:
            message_type = 'audio'
        elif message.animation:
            message_type = 'animation'
        elif message.text and _is_emoji_only(message.text.strip()):
            message_type = 'emoji'
        elif is_media:
            message_type = 'media'
        else:
            message_type = 'text'
            
        self.db.cursor.execute('''
            INSERT INTO messages (user_id, chat_id, message_text, message_type, message_thread_id, telegram_message_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user.id, message.chat.id, text[:500], message_type, thread_id, message.message_id))
        self.db.conn.commit()

        # Скрытое комбо "Мэтч дня": если сведенная пара взаимодействует в течение часа,
        # активируется x2 бафф майнинга для обоих участников.
        try:
            try_activate_shipper_resonance(message, self.db)
        except Exception as e:
            logging.error(f"shipper resonance hook error: {e}")
        
       # === ОБНОВЛЕНИЕ СТАТИСТИКИ ЧАТА ===
        # ЭТОТ БЛОК БОЛЬШЕ НЕ НУЖЕН, ТАК КАК МЫ БЕРЕМ ДАННЫЕ ИЗ USER_STATS
        # is_admin_message = is_excluded
        # 
        # self.db.cursor.execute('''
        #     INSERT INTO chat_stats (date, total_chars, total_messages, total_messages_with_admins,
        #                            total_messages_without_admins, total_words, total_replies, 
        #                            total_mentions, total_media, other_threads_posts)
        #     VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
        #     ON CONFLICT(date) DO UPDATE SET
        #         total_chars = total_chars + excluded.total_chars,
        #         total_messages = total_messages + 1,
        #         total_messages_with_admins = total_messages_with_admins + excluded.total_messages_with_admins,
        #         total_messages_without_admins = total_messages_without_admins + excluded.total_messages_without_admins,
        #         total_words = total_words + excluded.total_words,
        #         total_replies = total_replies + excluded.total_replies,
        #         total_mentions = total_mentions + excluded.total_mentions,
        #         total_media = total_media + excluded.total_media,
        #         other_threads_posts = other_threads_posts + excluded.other_threads_posts,
        #         avg_message_length = CAST(total_chars AS REAL) / total_messages
        # ''', (today, char_count, 
        #       1 if is_admin_message else 0,  # with admins
        #       0 if is_admin_message else 1,  # without admins
        #       word_count, 
        #       1 if (is_reply and not is_self_reply) else 0,
        #       mentions_count,
        #       1 if is_media else 0,
        #       1 if thread_id is not None else 0))
        # self.db.conn.commit()
        
        # === НАЧИСЛЕНИЕ НАГРАД ===
        _reward, _notification = process_mining_reward(
            user_id=user.id,
            today=today,
            user_data=user_data,
            is_excluded=is_excluded,
            exclusion_reason=exclusion_reason,
            db=self.db,
            message=message,          # Передаем само сообщение
            thread_id=thread_id       # Передаем ID ветки
        )

        # Уведомление о секретных механиках (Дефибриллятор и пр.)
        if _notification:
            try:
                await context.bot.send_message(
                    chat_id=_notification['user_id'],
                    text=_notification['text'],
                    parse_mode='HTML',
                )
            except Exception:
                pass
        
        # === ДАЛЕЕ КОД ВЫПОЛНЯЕТСЯ ДЛЯ ВСЕХ (включая админов и владельца) ===

        # === КНОПКИ ReplyKeyboard в ГРУППОВОМ ЧАТЕ ===
        if message.text and message.text.strip() in REPLY_BUTTONS and thread_id is None:
            btn = message.text.strip()
            try:
                await message.delete()
            except Exception:
                pass
            
            
            if btn == REPLY_BTN_BALANCE:
                from handlers.commands.economy_commands import balance_command
                await balance_command(update, context, self.db)
                return
            elif btn == REPLY_BTN_PROFILE:
                from handlers.profile_handlers import show_profile
                await show_profile(update, context, self.db, user.id)
                return
            elif btn == REPLY_BTN_COURSE:
                bot_msg = await _course_command(update=update, context=context, db=self.db, target_chat_id=self.target_chat_id)
                if bot_msg:
                    _schedule_auto_delete(context, bot_msg.chat.id, bot_msg.message_id, delay=60)
                try:
                    await message.delete()
                except Exception:
                    pass
                return
            elif btn == REPLY_BTN_TOP5:
                kb = [[InlineKeyboardButton("\u26a1 Активисты", callback_data="top5_activists")],[InlineKeyboardButton("\U0001f4b0 Богачи", callback_data="top5_rich")]]
                await context.bot.send_message(chat_id=message.chat.id, text="\U0001f3c6 ТОП-5\n\nВыберите категорию:", reply_markup=InlineKeyboardMarkup(kb))
                return
            elif btn == REPLY_BTN_ACTIVITIES:
                from handlers.donate_handlers import show_donate_menu
                kb = []
                if self.db.is_feature_enabled('donate'):
                    kb.append([InlineKeyboardButton("🎁 Донаты", callback_data="donate_menu")])
                if self.db.is_feature_enabled('referral'):
                    kb.append([InlineKeyboardButton("👥 Реферальная система", callback_data="menu_referral")])
                _u_act = self.db.get_user(user.id)
                is_owner = user.id == self.main_admin_id or bool(_u_act and _u_act['is_owner'])
                if self.db.is_feature_enabled('lottery'):
                    label = "🎰 Лотерея (управление)" if is_owner else "🎰 Лотерея"
                    kb.append([InlineKeyboardButton(label, callback_data="menu_lottery")])
                if self.db.is_feature_enabled('bingo'):
                    if is_owner:
                        kb.append([InlineKeyboardButton("🎱 Бинго (управление)", callback_data="menu_bingo")])
                    else:
                        kb.append([InlineKeyboardButton("🎱 Бинго", callback_data="menu_bingo")])
                monthly_gift_enabled = int(self.db.get_setting('monthly_gift_enabled', '1'))
                if is_owner:
                    kb.append([InlineKeyboardButton("🎁 Подарок месяца (управление)", callback_data="menu_monthly_gift")])
                elif monthly_gift_enabled:
                    kb.append([InlineKeyboardButton("🎁 Подарок месяца", callback_data="monthly_gift_user_view")])
                await context.bot.send_message(chat_id=message.chat.id, text="🎯 АКТИВНОСТИ\n\nВыберите активность:", reply_markup=InlineKeyboardMarkup(kb))
                return
            elif btn == REPLY_BTN_BANK:
                kb = [
                    [InlineKeyboardButton("💱 Курс Пульса", callback_data="show_exchange_rate")],
                ]
                _u_bank = self.db.get_user(user.id)
                is_owner = user.id == self.main_admin_id or bool(_u_bank and _u_bank['is_owner'])
                if is_owner:
                    kb.append([InlineKeyboardButton("💸 Перевод из банка", callback_data="bank_transfer_start")])
                await context.bot.send_message(chat_id=message.chat.id, text="🏦 ЦЕНТРОБАНК\n\nВыберите действие:", reply_markup=InlineKeyboardMarkup(kb))
                return
            elif btn == REPLY_BTN_DETAIL:
                _u_det = self.db.get_user(user.id)
                if not self.db.is_feature_enabled('detalization') and user.id != self.main_admin_id and not (_u_det and _u_det['is_owner']):
                    await context.bot.send_message(chat_id=message.chat.id, text="📋 Детализация временно отключена.")
                    return
                kb = [
                    [InlineKeyboardButton("📅 День", callback_data="detail_export_day")],
                    [InlineKeyboardButton("📅 Неделя", callback_data="detail_export_week")],
                    [InlineKeyboardButton("📅 Месяц", callback_data="detail_export_month")],
                    [InlineKeyboardButton("📅 Год", callback_data="detail_export_year")],
                ]
                await context.bot.send_message(chat_id=message.chat.id, text="📋 ДЕТАЛИЗАЦИЯ\n\nВыберите период для выгрузки Excel-файла:", reply_markup=InlineKeyboardMarkup(kb))
                return
            elif btn == REPLY_BTN_FAQ:
                from handlers.commands.system_commands import _show_faq_menu
                await _show_faq_menu(message)
                return
            elif btn == REPLY_BTN_OWNER_PANEL:
                from handlers.admin_moderation import send_admin_panel, _is_owner_or_deputy
                await send_admin_panel(context.bot, message.chat.id, is_owner=await _is_owner_or_deputy(user.id))
                return
            elif btn == REPLY_BTN_SHIPPER:
                from handlers.shipper_handlers import send_shipper_panel
                await send_shipper_panel(message, context, self.db, self.target_chat_id)
                return
            elif btn == REPLY_BTN_NEW_APPS:
                from handlers.admin_moderation import handle_new_apps_text
                await handle_new_apps_text(update, context)
                return
            elif btn in (REPLY_BTN_ADMINS, REPLY_BTN_BLACKLIST, REPLY_BTN_CHECK_USER,
                         REPLY_BTN_TRIGGERS, REPLY_BTN_JOURNAL, REPLY_BTN_STATS,
                         REPLY_BTN_NOT_IN_CHAT, REPLY_BTN_ECONOMY, REPLY_BTN_SYSTEM,
                         REPLY_BTN_BACKUP):
                from handlers.admin_moderation import handle_owner_panel_button
                await handle_owner_panel_button(update, context, btn)
                return
            elif btn == REPLY_BTN_MENU:
                from handlers.commands.system_commands import menu_command
                await menu_command(update, context, self.db, self.main_admin_id)
                return

        # === ОБРАБОТКА ТРИГГЕРНЫХ КОМАНД ===
        # Триггеры работают ТОЛЬКО в ГЛАВНОМ ЧАТЕ (thread_id is None).
        # В ветках (топиках) триггеры НЕ обрабатываются.
        # После ответа бота — триггерное сообщение пользователя УДАЛЯЕТСЯ.
        if message.text and thread_id is None:
            import string
            
            raw_text = message.text.lower().strip()
            # Убираем пунктуацию и лишние пробелы
            clean_text = raw_text.translate(str.maketrans('', '', string.punctuation)).strip()
            clean_text = ' '.join(clean_text.split())
            
            words = clean_text.split()
            
            triggered = False
            trigger_type = None
            
            # ── ЕДИНСТВЕННОЕ УСЛОВИЕ: ровно 1 слово и точное совпадение ──
            if len(words) == 1:
                if clean_text in ('богач', 'богачи'):
                    trigger_type = 'rich'
                    triggered = True
                elif clean_text in ('активист', 'активисты'):
                    trigger_type = 'activist'
                    triggered = True
                elif clean_text == 'курс':
                    trigger_type = 'course'
                    triggered = True
            
            # === ВЫПОЛНЕНИЕ ТРИГГЕРА ===
            if triggered:
                # Сначала отвечаем, потом удаляем триггер
                bot_msg = None
                if trigger_type in ('rich', 'activist') and self.db.is_feature_enabled('top_commands'):
                    if trigger_type == 'rich':
                        logging.info(f"✅ TRIGGER ACTIVATED: 'богач' by {message.from_user.id}")
                        bot_msg = await show_top_rich(message, context, self.db)
                    elif trigger_type == 'activist':
                        logging.info(f"✅ TRIGGER ACTIVATED: 'активист' by {message.from_user.id}")
                        bot_msg = await show_top_activists(message, context, self.db)
                elif trigger_type == 'course':
                    logging.info(f"✅ TRIGGER ACTIVATED: 'курс' by {message.from_user.id}")
                    bot_msg = await _course_command(update=update, context=context, db=self.db, target_chat_id=self.target_chat_id)

                # Удаляем ответ бота через 60 секунд
                if bot_msg:
                    _schedule_auto_delete(context, bot_msg.chat.id, bot_msg.message_id, delay=60)

                # Удаляем триггерное сообщение пользователя ПОСЛЕ ответа
                try:
                    await message.delete()
                    logging.info(f"🗑️ Deleted trigger message '{raw_text}' from {user.id}")
                except Exception as e:
                    logging.warning(f"⚠️ Could not delete trigger message: {e}")
                return
            
            # Логирование проигнорированных фраз для отладки
            elif any(kw in clean_text for kw in ['богач', 'богачи', 'активист', 'активисты']):
                logging.info(f"🛡️ Trigger IGNORED (not single-word match): '{raw_text}'")

        # === DB-ТРИГГЕРЫ АВТОМОДЕРАЦИИ (fix V1.8.1c) ===
        if message.text:
            from handlers.triggers_handlers import process_triggers
            if await process_triggers(update, context, self.db, self.target_chat_id, self.main_admin_id):
                return

        # === ОБРАБОТКА ВВОДА АДМИНА (пресс-релиз, курс, переводы, донаты) ===
        if await process_admin_input(message, user, context, self.db, self.main_admin_id, self.target_chat_id, update=update):
            return

    async def handle_forum_topic_event(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle forum topic created/edited/closed/reopened service messages to capture real topic names"""
        import logging
        message = update.message
        if not message:
            return
        
        chat_id = message.chat.id
        thread_id = message.message_thread_id
        
        topic_name = None
        
        # Topic created
        if message.forum_topic_created:
            topic_name = message.forum_topic_created.name
            logging.info(f"🏷️ Forum topic CREATED: #{thread_id} = '{topic_name}' in chat {chat_id}")
        
        # Topic edited (renamed)
        elif message.forum_topic_edited:
            if message.forum_topic_edited.name:
                topic_name = message.forum_topic_edited.name
                logging.info(f"🏷️ Forum topic EDITED: #{thread_id} = '{topic_name}' in chat {chat_id}")
        
        # Topic closed/reopened — just log, no name change
        elif message.forum_topic_closed:
            logging.info(f"🔒 Forum topic CLOSED: #{thread_id} in chat {chat_id}")
        elif message.forum_topic_reopened:
            logging.info(f"🔓 Forum topic REOPENED: #{thread_id} in chat {chat_id}")
        
        # Save real name to DB
        if topic_name and thread_id:
            self.db.update_topic_name(chat_id, thread_id, topic_name)
            logging.info(f"✅ Saved topic name: #{thread_id} = '{topic_name}'")
    
    
    async def handle_private_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle private messages from admin for press release / scheduling"""
        import logging
        message = update.message
        user = message.from_user
        chat_id = message.chat.id

        # ═══ ПРОВЕРКА ДОСТУПА — только члены чата + владелец/зам ═══
        _u_access = self.db.get_user(user.id)
        _is_owner_or_dep = user.id == self.main_admin_id or bool(_u_access and _u_access['is_owner'])
        if not _is_owner_or_dep:
            from utils.membership import verify_chat_membership
            is_member = await verify_chat_membership(
                context.bot, self.target_chat_id, user.id, db=self.db
            )

            if not is_member:
                # ── Exit survey: разрешаем текстовые ответы ──────
                if message.text and context.user_data.get('exit_survey_awaiting'):
                    from handlers.exit_survey_handlers import handle_exit_survey_text
                    if await handle_exit_survey_text(update, context, self.db):
                        return
                if message.text and not message.text.strip().startswith(('/start', '/register')):
                    try:
                        await message.reply_text("⏳ Доступ открывается после вступления в чат и одобрения заявки.")
                    except Exception:
                        pass  # Forbidden — бот заблокирован пользователем
                return

        # ═══ BUG TRACKER: ввод комментария от владельца/зама ═══
        if message.text and context.user_data.get('bug_awaiting_comment') and _is_owner_or_dep:
            from handlers.bug_tracker_handlers import handle_bug_comment_input
            if await handle_bug_comment_input(message, context, self.db):
                return

        # ═══ КНОПКИ ReplyKeyboard — обрабатываются ДЛЯ ВСЕХ в ЛС ═══
        if message.text and message.text.strip() in REPLY_BUTTONS:
            btn = message.text.strip()
            chat_id = message.chat.id

            # Удаляем кнопку пользователя
            try:
                await message.delete()
            except Exception:
                pass

            # Удаляем предыдущее бот-сообщение (single window)
            old_msg = context.user_data.get('menu_msg_id')
            if old_msg:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=old_msg)
                except Exception:
                    pass
                context.user_data.pop('menu_msg_id', None)

            if btn == REPLY_BTN_BALANCE:
                from handlers.commands.economy_commands import balance_command
                await balance_command(update, context, self.db)
                return
            elif btn == REPLY_BTN_PROFILE:
                from handlers.profile_handlers import show_profile
                await show_profile(update, context, self.db, user.id)
                return
            elif btn == REPLY_BTN_COURSE:
                await _course_command(update=update, context=context, db=self.db, target_chat_id=self.target_chat_id)
                return
            elif btn == REPLY_BTN_TOP5:
                kb = [[InlineKeyboardButton("\u26a1 Активисты", callback_data="top5_activists")],[InlineKeyboardButton("\U0001f4b0 Богачи", callback_data="top5_rich")],[InlineKeyboardButton("🔙 Меню", callback_data="back_to_menu")]]
                sent = await context.bot.send_message(chat_id=chat_id, text="\U0001f3c6 ТОП-5\n\nВыберите категорию:", reply_markup=InlineKeyboardMarkup(kb))
                context.user_data['menu_msg_id'] = sent.message_id
                return
            elif btn == REPLY_BTN_ACTIVITIES:
                kb = []
                if self.db.is_feature_enabled('donate'):
                    kb.append([InlineKeyboardButton("🎁 Донаты", callback_data="donate_menu")])
                if self.db.is_feature_enabled('referral'):
                    kb.append([InlineKeyboardButton("👥 Реферальная система", callback_data="menu_referral")])
                _u_act2 = self.db.get_user(user.id)
                is_owner = user.id == self.main_admin_id or bool(_u_act2 and _u_act2['is_owner'])
                if self.db.is_feature_enabled('lottery'):
                    label = "🎰 Лотерея (управление)" if is_owner else "🎰 Лотерея"
                    kb.append([InlineKeyboardButton(label, callback_data="menu_lottery")])
                if self.db.is_feature_enabled('bingo'):
                    if is_owner:
                        kb.append([InlineKeyboardButton("🎱 Бинго (управление)", callback_data="menu_bingo")])
                    else:
                        kb.append([InlineKeyboardButton("🎱 Бинго", callback_data="menu_bingo")])
                monthly_gift_enabled = int(self.db.get_setting('monthly_gift_enabled', '1'))
                if is_owner:
                    kb.append([InlineKeyboardButton("🎁 Подарок месяца (управление)", callback_data="menu_monthly_gift")])
                elif monthly_gift_enabled:
                    kb.append([InlineKeyboardButton("🎁 Подарок месяца", callback_data="monthly_gift_user_view")])
                kb.append([InlineKeyboardButton("🔙 Меню", callback_data="back_to_menu")])
                sent = await context.bot.send_message(chat_id=chat_id, text="🎯 АКТИВНОСТИ\n\nВыберите активность:", reply_markup=InlineKeyboardMarkup(kb))
                context.user_data['menu_msg_id'] = sent.message_id
                return
            elif btn == REPLY_BTN_BANK:
                kb = [
                    [InlineKeyboardButton("💱 Курс Пульса", callback_data="show_exchange_rate")],
                ]
                _u_bank2 = self.db.get_user(user.id)
                is_owner = user.id == self.main_admin_id or bool(_u_bank2 and _u_bank2['is_owner'])
                if is_owner:
                    kb.append([InlineKeyboardButton("💸 Перевод из банка", callback_data="bank_transfer_start")])
                kb.append([InlineKeyboardButton("🔙 Меню", callback_data="back_to_menu")])
                sent = await context.bot.send_message(chat_id=chat_id, text="🏦 ЦЕНТРОБАНК\n\nВыберите действие:", reply_markup=InlineKeyboardMarkup(kb))
                context.user_data['menu_msg_id'] = sent.message_id
                return
            elif btn == REPLY_BTN_DETAIL:
                _u_det2 = self.db.get_user(user.id)
                if not self.db.is_feature_enabled('detalization') and user.id != self.main_admin_id and not (_u_det2 and _u_det2['is_owner']):
                    await context.bot.send_message(chat_id=chat_id, text="📋 Детализация временно отключена.")
                    return
                kb = [
                    [InlineKeyboardButton("📅 День", callback_data="detail_export_day")],
                    [InlineKeyboardButton("📅 Неделя", callback_data="detail_export_week")],
                    [InlineKeyboardButton("📅 Месяц", callback_data="detail_export_month")],
                    [InlineKeyboardButton("📅 Год", callback_data="detail_export_year")],
                    [InlineKeyboardButton("🔙 Меню", callback_data="back_to_menu")],
                ]
                sent = await context.bot.send_message(chat_id=chat_id, text="📋 ДЕТАЛИЗАЦИЯ\n\nВыберите период:", reply_markup=InlineKeyboardMarkup(kb))
                context.user_data['menu_msg_id'] = sent.message_id
                return
            elif btn == REPLY_BTN_FAQ:
                from handlers.commands.system_commands import _show_faq_menu
                await _show_faq_menu(message)
                return
            elif btn == REPLY_BTN_OWNER_PANEL:
                from handlers.admin_moderation import send_admin_panel, _is_owner_or_deputy
                await send_admin_panel(context.bot, message.chat.id, is_owner=await _is_owner_or_deputy(user.id))
                return
            elif btn == REPLY_BTN_SHIPPER:
                from handlers.shipper_handlers import send_shipper_panel
                await send_shipper_panel(message, context, self.db, self.target_chat_id)
                return
            elif btn == REPLY_BTN_NEW_APPS:
                from handlers.admin_moderation import handle_new_apps_text
                await handle_new_apps_text(update, context)
                return
            elif btn in (REPLY_BTN_ADMINS, REPLY_BTN_BLACKLIST, REPLY_BTN_CHECK_USER,
                         REPLY_BTN_TRIGGERS, REPLY_BTN_JOURNAL, REPLY_BTN_STATS,
                         REPLY_BTN_NOT_IN_CHAT, REPLY_BTN_ECONOMY, REPLY_BTN_SYSTEM,
                         REPLY_BTN_BACKUP):
                from handlers.admin_moderation import handle_owner_panel_button
                await handle_owner_panel_button(update, context, btn)
                return
            elif btn == REPLY_BTN_MENU:
                from handlers.commands.system_commands import menu_command
                await menu_command(update, context, self.db, self.main_admin_id)
                return

        # ═══ ПЛЕЙСХОЛДЕРЫ FSM ═══
        if context.user_data.get('ph_state') and message.text:
            from handlers.placeholder_handlers import handle_placeholder_text
            if await handle_placeholder_text(update, context, self.db, self.main_admin_id):
                return

        # ═══ TRIGGER FSM v2 (создание/редактирование триггера) ═══
        if context.user_data.get('trigger_state') or context.user_data.get('owner_awaiting', '').startswith('trigger_'):
            from handlers.triggers_handlers import handle_trigger_text_input, handle_trigger_media_input
            if message.text:
                handled = await handle_trigger_text_input(update, context, self.db)
                if handled:
                    return
            elif message.photo or message.video or message.animation:
                handled = await handle_trigger_media_input(update, context, self.db)
                if handled:
                    return

        # ═══ ЖУРНАЛ: подключение канала или треда ═══
        _awaiting = context.user_data.get('owner_awaiting', '')
        if (
            _awaiting == 'journal_connect'
            or _awaiting.startswith('journal_connect_')
            or _awaiting.startswith('journal_thread_')
        ):
            from handlers.journal_handlers import handle_journal_text_input
            if await handle_journal_text_input(update, context, self.db):
                return

        # ═══ PANEL FSM (Админы, ЧС, Проверка ника, Зам) ═══
        if message.text and context.user_data.get('panel_awaiting'):
            from handlers.admin_moderation import handle_panel_input
            handled = await handle_panel_input(update, context)
            if handled:
                return

        # ═══ OWNER PANEL FSM (Персонал, Эмиссия, Блэклист, Мут) ═══
        if message.text and context.user_data.get('owner_awaiting'):
            handled = await handle_owner_text_input(
                update, context, self.db, self.main_admin_id, self.target_chat_id
            )
            if handled:
                return

        # ═══ BBS FSM — только для одобренных пользователей ═══
        if await process_bbs_input(message, context, self.db):
            return
        
        # Only admin can use private chat features
       # if user.id != self.main_admin_id and not context.user_data.get('bbs_state'):
            
         #   pass
        #    await message.reply_text(
        #        "👋 Привет! Я работаю в групповом чате.\n"
         #       "Используй /start в чате для начала."
         #   )
         #   return
        
        # Handle /cancel
        if message.text and message.text.strip() == '/cancel':
            context.user_data.pop('awaiting_press_release', None)
            context.user_data.pop('awaiting_schedule_time', None)
            context.user_data.pop('awaiting_thread_id', None)
            context.user_data.pop('awaiting_exchange_rate', None)
            context.user_data.pop('awaiting_bank_transfer', None)
            context.user_data.pop('bt_custom_user_id', None)
            context.user_data.pop('pr_data', None)
            # Состояния редактирования пресс-релизов
            context.user_data.pop('awaiting_pr_photo', None)
            context.user_data.pop('awaiting_edit_text', None)
            context.user_data.pop('awaiting_edit_photo', None)
            context.user_data.pop('awaiting_edit_time', None)
            context.user_data.pop('awaiting_edit_target_manual', None)
            context.user_data.pop('editing_post_target', None)
            context.user_data.pop('edit_photo_buffer', None)
            context.user_data.pop('pr_initial_mg_id', None)
            context.user_data.pop('pr_add_mg_id', None)
            for _tk in ('pr_mg_task', 'pr_add_mg_task'):
                _t = context.user_data.pop(_tk, None)
                if _t:
                    _t.cancel()
            # BBS FSM cleanup
            context.user_data.pop('bbs_state', None)
            context.user_data.pop('bbs_data', None)
            context.user_data.pop('bbs_param_editing', None)
            context.user_data.pop('bbs_photo_msg_id', None)
            context.user_data.pop('bbs_editing_profile_id', None)
            context.user_data.pop('bbs_edit_photos', None)
            context.user_data.pop('bbs_edit_cities', None)
            context.user_data.pop('bbs_edit_goals', None)
            context.user_data.pop('other_state', None)
            context.user_data.pop('other_data', None)
            context.user_data.pop('other_bot_msg_id', None)
            context.user_data.pop('other_preview_message_ids', None)
            # Owner panel cleanup
            context.user_data.pop('owner_awaiting', None)
            await message.reply_text("❌ Действие отменено.")
            return
        
        # === ВСЕ AWAITING-СОСТОЯНИЯ ОБРАБАТЫВАЮТСЯ ЕДИНЫМ ДИСПЕТЧЕРОМ ===
        # process_admin_input обрабатывает: thread_id, schedule_time, press_release,
        # exchange_rate, bank_transfer, donate, а также новые: pr_photo, edit_text,
        # edit_photo, edit_time, edit_target_manual
        if await process_admin_input(message, user, context, self.db, self.main_admin_id, self.target_chat_id, update=update):
            return

        # Default: suggest using menu
        await message.reply_text(
            "📱 Используйте /menu для навигации.\n\n"
            "Для создания пресс-релиза:\n"
            "➡️ /menu → ⚙️ Настройки → 📰 Пресс-релиз"
        )
    
    async def publish_press_release(self, message, context):
        """Delegates to admin_logic"""
        await publish_press_release(message, context, self.target_chat_id)
    
    async def publish_press_release_to_target(self, bot, text, photo_file_id, chat_id, thread_id=None):
        """Delegates to admin_logic"""
        return await publish_press_release_to_target(bot, text, photo_file_id, chat_id, thread_id)
    
    async def handle_member_left(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user leaving OR returning to chat — delegates to events_logic"""
        await handle_member_left(update, context, self.db, self.main_admin_id, self.target_chat_id)
    
    async def handle_reaction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle message reactions — delegates to events_logic"""
        await handle_reaction(update, context, self.db, self.target_chat_id)

        # ═══ МГНОВЕННОЕ ОБНОВЛЕНИЕ КУРСА (дельта реакции) ═══
        try:
            from utils.exchange_rate import rate_cache, calculate_reaction_delta
            if rate_cache.initialized and not rate_cache.is_manual:
                # Реакция поставлена = reactions_given + reactions_received
                rate_cache.apply_delta(calculate_reaction_delta(is_given=True))
                rate_cache.apply_delta(calculate_reaction_delta(is_given=False))
        except Exception:
            pass