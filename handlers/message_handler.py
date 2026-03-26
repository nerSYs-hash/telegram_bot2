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
from handlers.bbs_handlers import process_bbs_input
from handlers.owner_handlers import handle_owner_text_input


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
REPLY_BTN_NEW_APPS = "📋 Новые заявки"
REPLY_BUTTONS = {REPLY_BTN_BALANCE, REPLY_BTN_PROFILE, REPLY_BTN_COURSE, REPLY_BTN_TOP5, REPLY_BTN_MENU,
                 REPLY_BTN_ACTIVITIES, REPLY_BTN_BANK, REPLY_BTN_DETAIL, REPLY_BTN_FAQ,
                 REPLY_BTN_OWNER_PANEL, REPLY_BTN_NEW_APPS}


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
        if self.last_admin_check and (now - self.last_admin_check).seconds < self.admin_cache_duration:
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
        
        # Get thread/topic information
        thread_id = message.message_thread_id  # None for main chat, int for topics
        # Передаем None для веток, чтобы БД не стирала реальное красивое имя фейковым!
        thread_name = "Главный чат" if thread_id is None else None
        
        logging.info(f"📨 Incoming message from user_id={user.id} (@{user.username}), "
                    f"chat_id={message.chat.id}, thread_id={thread_id} ({thread_name})")
        
        # Only process messages from target chat
        # EXCEPTION: handle private messages from admin for press release / scheduled posts
        if message.chat.type == 'private':
            await self.handle_private_message(update, context)
            return
        
        if message.chat.id != self.target_chat_id:
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
        char_count = len(text)
        word_count = count_words(text)
        is_media = is_media_message(message)
        is_reply = message.reply_to_message is not None
        
        # Check if reply is to self (exclude from statistics)
        is_self_reply = False
        if is_reply and message.reply_to_message.from_user:
            is_self_reply = message.reply_to_message.from_user.id == user.id
        
        # Count mentions
        mentions_count = 0
        if message.entities:
            mentions_count = sum(1 for e in message.entities if e.type == 'mention')
        
        # Update user statistics (exclude self-replies)
        stats_update = {
            'total_chars': char_count,
            'total_messages': 1,
            'total_words': word_count,
            'replies_sent': 1 if (is_reply and not is_self_reply) else 0,  # Exclude self-replies
            'media_sent': 1 if is_media else 0,
            'mentions_received': mentions_count,
            'other_threads_posts': 1 if thread_id is not None else 0
        }
        
        self.db.update_user_activity(user.id, today, **stats_update)
   
         # ═══ МГНОВЕННОЕ ОБНОВЛЕНИЕ КУРСА (дельта) ═══
        try:
            from utils.exchange_rate import rate_cache, calculate_message_delta
            if rate_cache.initialized and not rate_cache.is_manual:
                delta = calculate_message_delta(
                    char_count=char_count,
                    word_count=word_count,
                    is_reply=(is_reply and not is_self_reply),
                    is_media=is_media,
                    has_mention=(mentions_count > 0),
                    is_other_thread=(thread_id is not None)
                )
                rate_cache.apply_delta(delta)
        except Exception as e:
            logging.debug(f"Rate delta error: {e}")
        
        # Обновить replies_received для того, кому ответили
        if is_reply and not is_self_reply and message.reply_to_message.from_user:
            replied_to_user_id = message.reply_to_message.from_user.id
            # Не обновляем если ответили самому себе (уже проверено выше)
            if replied_to_user_id != user.id:
                self.db.update_user_activity(replied_to_user_id, today, replies_received=1)
                logging.info(f"📬 User {replied_to_user_id} received reply from {user.id}")
                # Дельта для replies_received
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
        
        # === ОБНОВЛЕНИЕ СТАТИСТИКИ ЧАТА ===
        # Check if user is admin for message counting
        is_admin_message = is_excluded
        
        self.db.cursor.execute('''
            INSERT INTO chat_stats (date, total_chars, total_messages, total_messages_with_admins,
                                   total_messages_without_admins, total_words, total_replies, 
                                   total_mentions, total_media, other_threads_posts)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_chars = total_chars + excluded.total_chars,
                total_messages = total_messages + 1,
                total_messages_with_admins = total_messages_with_admins + excluded.total_messages_with_admins,
                total_messages_without_admins = total_messages_without_admins + excluded.total_messages_without_admins,
                total_words = total_words + excluded.total_words,
                total_replies = total_replies + excluded.total_replies,
                total_mentions = total_mentions + excluded.total_mentions,
                total_media = total_media + excluded.total_media,
                other_threads_posts = other_threads_posts + excluded.other_threads_posts,
                avg_message_length = CAST(total_chars AS REAL) / total_messages
        ''', (today, char_count, 
              1 if is_admin_message else 0,  # with admins
              0 if is_admin_message else 1,  # without admins
              word_count, 
              1 if (is_reply and not is_self_reply) else 0,
              mentions_count,
              1 if is_media else 0,
              1 if thread_id is not None else 0))
        self.db.conn.commit()
        
        # === НАЧИСЛЕНИЕ НАГРАД ===
        process_mining_reward(
            user_id=user.id,
            today=today,
            user_data=user_data,
            is_excluded=is_excluded,
            exclusion_reason=exclusion_reason,
            db=self.db,
            message=message,          # Передаем само сообщение
            thread_id=thread_id       # Передаем ID ветки
        )
        
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
                await _course_command(update=update, context=context, db=self.db, target_chat_id=self.target_chat_id)
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
                if self.db.is_feature_enabled('lottery'):
                    is_owner = user.id == self.main_admin_id
                    label = "🎰 Лотерея (управление)" if is_owner else "🎰 Лотерея"
                    kb.append([InlineKeyboardButton(label, callback_data="menu_lottery")])
                is_owner = user.id == self.main_admin_id
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
                is_owner = user.id == self.main_admin_id
                if is_owner:
                    kb.append([InlineKeyboardButton("💸 Перевод из банка", callback_data="bank_transfer_start")])
                await context.bot.send_message(chat_id=message.chat.id, text="🏦 ЦЕНТРОБАНК\n\nВыберите действие:", reply_markup=InlineKeyboardMarkup(kb))
                return
            elif btn == REPLY_BTN_DETAIL:
                if not self.db.is_feature_enabled('detalization') and user.id != self.main_admin_id:
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
                from handlers.owner_handlers import show_owner_dashboard
                await show_owner_dashboard(update, context, self.db, self.main_admin_id)
                return
            elif btn == REPLY_BTN_NEW_APPS:
                from handlers.owner_handlers import show_owner_dashboard
                await show_owner_dashboard(update, context, self.db, self.main_admin_id)
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
                if clean_text == 'богач':
                    trigger_type = 'rich'
                    triggered = True
                elif clean_text == 'активист':
                    trigger_type = 'activist'
                    triggered = True
                elif clean_text == 'курс':
                    trigger_type = 'course'
                    triggered = True
            
            # === ВЫПОЛНЕНИЕ ТРИГГЕРА ===
            if triggered:
                # Сначала отвечаем, потом удаляем триггер
                if trigger_type in ('rich', 'activist') and self.db.is_feature_enabled('top_commands'):
                    if trigger_type == 'rich':
                        logging.info(f"✅ TRIGGER ACTIVATED: 'богач' by {message.from_user.id}")
                        await show_top_rich(message, context, self.db)
                    elif trigger_type == 'activist':
                        logging.info(f"✅ TRIGGER ACTIVATED: 'активист' by {message.from_user.id}")
                        await show_top_activists(message, context, self.db)
                elif trigger_type == 'course':
                    logging.info(f"✅ TRIGGER ACTIVATED: 'курс' by {message.from_user.id}")
                    await _course_command(update=update, context=context, db=self.db, target_chat_id=self.target_chat_id)
                
                # Удаляем триггерное сообщение пользователя ПОСЛЕ ответа
                try:
                    await message.delete()
                    logging.info(f"🗑️ Deleted trigger message '{raw_text}' from {user.id}")
                except Exception as e:
                    logging.warning(f"⚠️ Could not delete trigger message: {e}")
                return
            
            # Логирование проигнорированных фраз для отладки
            elif any(kw in clean_text for kw in ['богач', 'активист']):
                logging.info(f"🛡️ Trigger IGNORED (not single-word match): '{raw_text}'")

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
                if self.db.is_feature_enabled('lottery'):
                    is_owner = user.id == self.main_admin_id
                    label = "🎰 Лотерея (управление)" if is_owner else "🎰 Лотерея"
                    kb.append([InlineKeyboardButton(label, callback_data="menu_lottery")])
                is_owner = user.id == self.main_admin_id
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
                is_owner = user.id == self.main_admin_id
                if is_owner:
                    kb.append([InlineKeyboardButton("💸 Перевод из банка", callback_data="bank_transfer_start")])
                kb.append([InlineKeyboardButton("🔙 Меню", callback_data="back_to_menu")])
                sent = await context.bot.send_message(chat_id=chat_id, text="🏦 ЦЕНТРОБАНК\n\nВыберите действие:", reply_markup=InlineKeyboardMarkup(kb))
                context.user_data['menu_msg_id'] = sent.message_id
                return
            elif btn == REPLY_BTN_DETAIL:
                if not self.db.is_feature_enabled('detalization') and user.id != self.main_admin_id:
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
                from handlers.owner_handlers import show_owner_dashboard
                await show_owner_dashboard(update, context, self.db, self.main_admin_id)
                return
            elif btn == REPLY_BTN_NEW_APPS:
                from handlers.owner_handlers import show_owner_dashboard
                await show_owner_dashboard(update, context, self.db, self.main_admin_id)
                return
            elif btn == REPLY_BTN_MENU:
                from handlers.commands.system_commands import menu_command
                await menu_command(update, context, self.db, self.main_admin_id)
                return

        # ═══ OWNER PANEL FSM (Персонал, Эмиссия, Блэклист, Мут) ═══
        #if message.text and context.user_data.get('owner_awaiting'):
        #    handled = await handle_owner_text_input(
        #        update, context, self.db, self.main_admin_id, self.target_chat_id
        #    )
         #   if handled:
        #        return

        # ═══ BBS FSM — доступен ВСЕМ пользователям в ЛС ═══
        #if await process_bbs_input(message, context, self.db):
         #   return
        
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
            # Новые состояния редактирования пресс-релизов
            context.user_data.pop('awaiting_pr_photo', None)
            context.user_data.pop('awaiting_edit_text', None)
            context.user_data.pop('awaiting_edit_photo', None)
            context.user_data.pop('awaiting_edit_time', None)
            context.user_data.pop('awaiting_edit_target_manual', None)
            context.user_data.pop('editing_post_target', None)
            # BBS FSM cleanup
            context.user_data.pop('bbs_state', None)
            context.user_data.pop('bbs_data', None)
            context.user_data.pop('bbs_param_editing', None)
            context.user_data.pop('bbs_photo_msg_id', None)
            context.user_data.pop('bbs_editing_profile_id', None)
            context.user_data.pop('bbs_edit_photos', None)
            context.user_data.pop('bbs_edit_cities', None)
            context.user_data.pop('bbs_edit_goals', None)
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