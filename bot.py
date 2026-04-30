#!/usr/bin/env python3
# -*- coding: utf-8 -*-

BOT_VERSION = "1.9.1b"

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    MessageReactionHandler,  # ← ДОБАВЛЕНО для обработки реакций
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
# Import custom modules
from database.db_manager import Database
from handlers.command_handler import CommandHandler as BotCommandHandler
from handlers.message_handler import MessageHandler as BotMessageHandler
from handlers.callback import CallbackHandler
from handlers.commands.exchange_commands import recalc_rate_command
from handlers.shipper_logic import bootstrap_shipper
from utils.helpers import get_moscow_time, format_number
from utils.exchange_rate import rate_cache, scheduled_rate_update, scheduled_top5_update, scheduled_top5_percent_update

# Абсолютный путь к папке скрипта — не зависит от рабочей директории
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables — всегда из папки скрипта
load_dotenv(os.path.join(_BASE_DIR, '.env'))

# Ensure logs directory exists
os.makedirs(os.path.join(_BASE_DIR, 'logs'), exist_ok=True)


# ─── НАСТРОЙКА КРАСИВОГО ЛОГИРОВАНИЯ ───
class ColoredFormatter(logging.Formatter):
    """Кастомный форматер для цветной и ровной консоли"""
    COLORS = {
        'WARNING': '\033[93m',   # Желтый
        'INFO': '\033[94m',      # Синий
        'DEBUG': '\033[92m',     # Зеленый
        'CRITICAL': '\033[91m',  # Красный
        'ERROR': '\033[91m'      # Красный
    }
    RESET = '\033[0m'
    GRAY = '\033[90m'
    CYAN = '\033[36m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        # Оставляем только время (без даты), чтобы экономить место
        time_str = self.formatTime(record, "%H:%M:%S")
        # Выравниваем уровень лога по центру (8 символов), укорачиваем имя файла (до 15 симв.)
        module_name = (record.module[:13] + '..') if len(record.module) > 15 else record.module
        
        # Формат: [15:30:45][  INFO  ] [mining_logic ]: Ваше сообщение
        return f"{self.GRAY}[{time_str}]{self.RESET} {color}[{record.levelname:^8}]{self.RESET} {self.CYAN}[{module_name:<15}]{self.RESET}: {record.getMessage()}"

# Настраиваем базовый логгер
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 1. Запись в файл (оставляем обычный текст, без цветовых кодов)
file_handler = logging.FileHandler('logs/bot.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'))
logger.addHandler(file_handler)

# 2. Вывод в консоль (с нашими цветами и ровными столбиками)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredFormatter())
logger.addHandler(console_handler)

# 3. ЗАТЫКАЕМ СПАМЕРОВ!
# Отключаем ежесекундный спам от httpx и apscheduler (оставляем только ошибки)
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Наш главный логгер для файла bot.py
logger = logging.getLogger(__name__)
# ──────────────────────────────────────────

class TelegramBot:
    def __init__(self):
        """Initialize the bot"""
        # Get configuration from environment
        self.bot_token = os.getenv('BOT_TOKEN')
        self.main_admin_id = int(os.getenv('MAIN_ADMIN_ID'))
        self.target_chat_id = int(os.getenv('TARGET_CHAT_ID'))
        _db_rel = os.getenv('DATABASE_PATH', 'database/bot_database.db')
        self.db_path = _db_rel if os.path.isabs(_db_rel) else os.path.join(_BASE_DIR, _db_rel)
        self.bbs_thread_id = int(os.getenv('BBS_THREAD_ID', 0))
        
        # Initialize database
        self.db = Database(self.db_path)
        self.db.initialize_settings(
            initial_bank_balance=int(os.getenv('INITIAL_BANK_BALANCE', 10000000)),
            initial_difficulty_k=float(os.getenv('INITIAL_DIFFICULTY_K', 5.0))
        )
        
        # Add main admin to database
        self.db.add_user(
            self.main_admin_id,
            is_admin=True,
            is_owner=True
        )
        
        # Initialize handlers
        self.command_handler = None
        self.message_handler = None
        self.callback_handler = None
        
        # Initialize scheduler
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
        
        # Application
        self.application = None
        
        logger.info("Bot initialized successfully")
    
    async def post_init(self, application: Application):
        """Post initialization hook"""
        bot = application.bot
        me = await bot.get_me()
        self.bot_username = me.username

        logger.info(f"Bot username: @{self.bot_username}")

        # Инициализация БД регистрации (применяет миграции)
        from database.db_friend import init_db as init_friend_db
        await init_friend_db()

        # Отправляем кнопку "Новые заявки" в тред заявок (ОТКЛЮЧЕНО ПО ПРОСЬБЕ ЮЗЕРА, ЧТОБЫ НЕ СПАМИТЬ ПРИ ОБНОВЛЕНИЯХ)
        # from handlers.admin_moderation import send_applications_button
        # await send_applications_button(bot)
        
        # Initialize handlers with bot username
        self.command_handler = BotCommandHandler(
            self.db, 
            self.target_chat_id, 
            self.main_admin_id
        )
        
        self.message_handler = BotMessageHandler(
            self.db,
            self.target_chat_id,
            self.main_admin_id
        )
        
        self.callback_handler = CallbackHandler(
            self.db,
            self.target_chat_id,
            self.main_admin_id,
            self.bot_username
        )
        
        # Записываем db в bot_data — для доступа из ConversationHandler/admin_moderation
        application.bot_data['db'] = self.db

        # Шиппер: стартовая постановка в очередь job_queue
        await bootstrap_shipper(application, self.db, self.target_chat_id)

        logger.info("Handlers initialized")

        # Setup handlers after initialization
        self.setup_handlers()
        
        # Setup scheduled jobs
        self.setup_jobs()
        
        # Initialize rate cache
        await self.init_rate_cache()

        # Прогреваем кеш ТОП-5 активистов при старте (иначе первый час пустой)
        try:
            from utils.exchange_rate import scheduled_top5_percent_update
            import asyncio as _asyncio
            await _asyncio.get_event_loop().run_in_executor(
                None, scheduled_top5_percent_update, self.db
            )
            logger.info("TOP-5% cache warmed up on startup")
        except Exception as _e:
            logger.warning(f"TOP-5% warmup failed: {_e}")

        # ── Уведомление о версии при старте ──
        await self._notify_version(bot)

    async def _notify_version(self, bot):
        """Отправить уведомление о версии Владельцу, замам и разработчику."""
        try:
            from database.db_friend import get_all_deputies
            from config import DEVELOPER_ID
            now = get_moscow_time().strftime('%d.%m.%Y %H:%M')
            text = (
                f"🤖 Бот обновлён и запущен\n\n"
                f"📦 Версия: <b>{BOT_VERSION}</b>\n"
                f"🕐 {now} МСК"
            )
            notified = set()
            # Владелец
            try:
                await bot.send_message(self.main_admin_id, text, parse_mode='HTML')
                notified.add(self.main_admin_id)
            except Exception as e:
                logger.warning(f"Не удалось уведомить владельца: {e}")
            # Замы
            deputies = await get_all_deputies()
            for dep in deputies:
                tid = dep['tg_id']
                if tid not in notified:
                    try:
                        await bot.send_message(tid, text, parse_mode='HTML')
                        notified.add(tid)
                    except Exception as e:
                        logger.warning(f"Не удалось уведомить зама {tid}: {e}")
            # Разработчик
            if DEVELOPER_ID and DEVELOPER_ID not in notified:
                try:
                    await bot.send_message(DEVELOPER_ID, text, parse_mode='HTML')
                except Exception as e:
                    logger.warning(f"Не удалось уведомить разработчика: {e}")
        except Exception as e:
            logger.error(f"_notify_version error: {e}")

    async def daily_statistics(self):
        """Send daily statistics at 19:05 MSK"""
        try:
            logger.info("Running daily statistics...")
            
            # Get top 5 users
            top_users = self.db.get_top_users_by_balance(limit=5, exclude_admins=True)
            
            if not top_users:
                logger.info("No users to show in top")
                return
            
            message = "🏆 ТОП-5 БОГАЧЕЙ ЧАТА\n"
            message += f"(период: {get_moscow_time().strftime('%d.%m.%Y %H:%M')} МСК)\n\n"
            
            # Add "Всего добыто" header
            message += "    Всего добыто\n"
            
            emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
            
            for idx, user in enumerate(top_users):
                username = user['username'] or user['first_name'] or 'Unknown'
                balance = format_number(user['balance'])
                message += f"{emojis[idx]} @{username} — {balance} 💎\n"
            
            # Calculate total mined by all chat
            self.db.cursor.execute('''
                SELECT SUM(amount) as total FROM transactions
                WHERE transaction_type = 'message_reward'
            ''')
            result = self.db.cursor.fetchone()
            total_mined = result['total'] if result and result['total'] else 0
            
            message += f"\n💰 Всего добыто чатом за всё время: {format_number(total_mined)} 💎"
            
            # Send to target chat
            await self.application.bot.send_message(
                chat_id=self.target_chat_id,
                text=message
            )
            
            logger.info("Daily statistics sent successfully")
            
        except Exception as e:
            logger.error(f"Error in daily statistics: {e}")
    
    async def check_qualifications(self):
        """Check and qualify referrals"""
        try:
            from utils.helpers import check_referral_qualification
            
            # Get unqualified referred users
            self.db.cursor.execute('''
                SELECT user_id, referrer_id 
                FROM users 
                WHERE referrer_id IS NOT NULL AND is_qualified = 0
            ''')
            
            unqualified = self.db.cursor.fetchall()
            
            for user in unqualified:
                user_id = user['user_id']
                referrer_id = user['referrer_id']
                
                if check_referral_qualification(self.db, user_id):
                    # Qualify the user
                    self.db.cursor.execute('''
                        UPDATE users SET is_qualified = 1 WHERE user_id = ?
                    ''', (user_id,))

                    # Master-switch раздела «👥 Реферальная программа»
                    try:
                        if not self.db.is_econ_section_enabled('referral'):
                            self.db.conn.commit()
                            continue
                    except Exception:
                        pass

                    # Award referrer (размер берём из economy_settings, fallback — старый ENV)
                    try:
                        reward = int(self.db.get_econ('referral.qualified_reward',
                                                     int(os.getenv('REFERRAL_REWARD', 500))) or 500)
                    except Exception:
                        reward = int(os.getenv('REFERRAL_REWARD', 500))
                    self.db.update_user_balance(referrer_id, reward, 'add')
                    self.db.add_transaction(
                        None,
                        referrer_id,
                        reward,
                        'referral_reward',
                        f'Реферальная награда за пользователя {user_id}'
                    )
                    
                    self.db.conn.commit()
                    
                    # Notify referrer
                    try:
                        referred_user = self.db.get_user(user_id)
                        username = referred_user['username'] or referred_user['first_name']
                        
                        await self.application.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 Твой друг @{username} освоился!\n"
                                 f"💎 Тебе начислена награда: {format_number(reward)} Пульсов"
                        )
                    except Exception as e:
                        logger.error(f"Error notifying referrer: {e}")
            
            logger.info(f"Checked qualifications: {len(unqualified)} users")
            
        except Exception as e:
            logger.error(f"Error checking qualifications: {e}")
    
    async def check_scheduled_posts(self):
        """Check and publish scheduled posts"""
        try:
            from utils.helpers import get_moscow_time
            now = get_moscow_time()
            now_str = now.strftime('%Y-%m-%d %H:%M:%S')
            
            pending_posts = self.db.get_pending_scheduled_posts(now_str)
            
            for post in pending_posts:
                try:
                    success = await self.message_handler.publish_press_release_to_target(
                        bot=self.application.bot,
                        text=post['text'],
                        photo_file_id=post['photo_file_id'],
                        chat_id=post['target_chat_id'],
                        thread_id=post['thread_id']
                    )
                    
                    if success:
                        self.db.mark_scheduled_post_published(post['id'])
                        logger.info(f"Published scheduled post #{post['id']}")
                        
                        # Notify author
                        try:
                            await self.application.bot.send_message(
                                chat_id=post['author_id'],
                                text=f"✅ Запланированный пресс-релиз #{post['id']} опубликован!"
                            )
                        except Exception:
                            pass
                    else:
                        logger.error(f"Failed to publish scheduled post #{post['id']}")
                        
                except Exception as e:
                    logger.error(f"Error publishing scheduled post #{post['id']}: {e}")
            
        except Exception as e:
            logger.error(f"Error checking scheduled posts: {e}")
    
    async def cleanup_expired_freezes(self):
        """Clean up expired frozen balances"""
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.db.cursor.execute('''
                SELECT user_id, frozen_balance FROM users
                WHERE frozen_balance > 0 AND freeze_until IS NOT NULL AND freeze_until < ?
            ''', (now,))
            
            expired = self.db.cursor.fetchall()
            
            for user in expired:
                self.db.cursor.execute('''
                    UPDATE users 
                    SET frozen_balance = 0, freeze_until = NULL
                    WHERE user_id = ?
                ''', (user['user_id'],))
                
                logger.info(
                    f"🧹 Cleaned up expired freeze for user {user['user_id']}: "
                    f"{user['frozen_balance']} pulses"
                )
            
            if expired:
                self.db.conn.commit()
                logger.info(f"🧹 Cleaned up {len(expired)} expired freezes")
        
        except Exception as e:
            logger.error(f"Error cleaning up freezes: {e}")
    
    async def check_lottery_end(self):
        """Check and end finished lotteries via LotteryHandler"""
        try:
            # В вашей архитектуре lottery_handler лежит внутри callback_handler,
            # а объект бота доступен через self.application.bot
            if self.callback_handler and hasattr(self.callback_handler, 'lottery_handler'):
                await self.callback_handler.lottery_handler.check_lottery_end(self.application.bot)
        except Exception as e:
            logger.error(f"Error in check_lottery_end wrapper: {e}")
    
    async def check_bingo_balls(self):
        """Draw bingo balls for active games via BingoHandler"""
        try:
            if self.callback_handler and hasattr(self.callback_handler, 'bingo_handler'):
                await self.callback_handler.bingo_handler.draw_ball(self.application.bot)
        except Exception as e:
            logger.error(f"Error in check_bingo_balls: {e}")
    
    async def cleanup_bbs_profiles(self):
        """Cleanup BBS profiles for users who left the chat"""
        try:
            from handlers.bbs_handlers import cleanup_dead_profiles
            await cleanup_dead_profiles(
                self.application.bot, self.db, self.target_chat_id
            )
        except Exception as e:
            logger.error(f"Error in BBS cleanup: {e}")

    async def _cleanup_stat_events_log(self):
        """Удаляет старые записи из лога дедупликации (старше 3 дней)."""
        try:
            self.db.cleanup_stat_events_log(older_than_days=3)
        except Exception as e:
            logger.error(f"Error in stat_events_log cleanup: {e}")

    async def init_rate_cache(self):
        """Initialize rate cache at bot startup"""
        try:
            if self.db.is_rate_manual():
                rate_cache.set_manual(self.db.get_exchange_rate())
                logger.info(f"💱 Rate cache: manual rate = {rate_cache.current_rate}")
                return

            total_members = 1
            try:
                total_members = await self.application.bot.get_chat_member_count(self.target_chat_id)
                total_members = max(1, total_members - 1)
            except Exception:
                total_members = int(self.db.get_setting('total_chat_members', '1'))

            from utils.helpers import get_today_date_msk
            today = get_today_date_msk()
            rate_cache.full_recalculate(self.db, total_members, today)

            # Сохраняем в settings для быстрого доступа
            self.db.set_setting('total_chat_members', str(total_members))
            logger.info(f"💱 Rate cache initialized: {rate_cache.current_rate}")

        except Exception as e:
            logger.error(f"Error initializing rate cache: {e}")

    async def update_exchange_rate(self):
        """Scheduled: полный пересчёт курса каждые 30 минут"""
        try:
            if rate_cache.is_manual:
                return

            total_members = 1
            try:
                total_members = await self.application.bot.get_chat_member_count(self.target_chat_id)
                total_members = max(1, total_members - 1)
                self.db.set_setting('total_chat_members', str(total_members))
            except Exception:
                total_members = int(self.db.get_setting('total_chat_members', '1'))

            from utils.helpers import get_today_date_msk
            today = get_today_date_msk()
            new_rate = scheduled_rate_update(self.db, total_members, today)
            logger.info(f"💱 Scheduled rate update: {new_rate}")

        except Exception as e:
            logger.error(f"Error in scheduled rate update: {e}")

    async def update_top5_activists(self):
        """Scheduled: снапшот ТОП-5 активистов (2 раза в день)"""
        try:
            total_members = 1
            try:
                total_members = await self.application.bot.get_chat_member_count(self.target_chat_id)
                total_members = max(1, total_members - 1)
            except Exception:
                total_members = int(self.db.get_setting('total_chat_members', '1'))

            from utils.helpers import get_today_date_msk
            today = get_today_date_msk()
            top5 = scheduled_top5_update(self.db, today, total_members)
            logger.info(f"🏆 TOP-5 snapshot: {len(top5)} users saved")

        except Exception as e:
            logger.error(f"Error in TOP-5 update: {e}")

    async def update_top5_percent(self):
        """Scheduled: обновление % активности ТОП-5 (каждый час)"""
        try:
            entries = scheduled_top5_percent_update(self.db)
            logger.info(f"📊 TOP-5%% percent: {len(entries)} users cached")
        except Exception as e:
            logger.error(f"Error in TOP-5 percent update: {e}")

    async def error_handler(self, update, context):
        """Handle errors"""
        try:
            logger.error(f"Exception while handling an update: {context.error}")
            
            # Log full traceback
            import traceback
            tb_list = traceback.format_exception(type(context.error), context.error, context.error.__traceback__)
            tb_string = ''.join(tb_list)
            logger.error(tb_string)
            
            # Try to notify user if it's a user update
            if update and update.effective_user:
                try:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"❌ Произошла ошибка при обработке вашего запроса.\n\n"
                             f"Ошибка: {str(context.error)[:200]}\n\n"
                             f"Администратор уведомлен."
                    )
                except Exception as send_error:
                    logger.error(f"Failed to notify user about error: {send_error}")
            
            # Notify admin
            try:
                error_msg = f"⚠️ ОШИБКА БОТА\n\n"
                error_msg += f"Пользователь: {update.effective_user.first_name if update and update.effective_user else 'Unknown'}\n"
                error_msg += f"Ошибка: {str(context.error)[:500]}\n\n"
                error_msg += f"Время: {get_moscow_time().strftime('%d.%m.%Y %H:%M:%S')}"
                
                await context.bot.send_message(
                    chat_id=self.main_admin_id,
                    text=error_msg
                )
            except Exception as notify_error:
                logger.error(f"Failed to notify admin about error: {notify_error}")
        
        except Exception as e:
            logger.error(f"Error in error_handler itself: {e}")

    def setup_handlers(self):
        """Setup all handlers"""
        # Registration conversation handler (MUST be before general message handler)
        from handlers.registration_conversation import registration_conv
        self.application.add_handler(registration_conv)

        # Command handlers
        self.application.add_handler(CommandHandler("start", self.command_handler.start_command))
        self.application.add_handler(CommandHandler("menu", self.command_handler.menu_command))
        self.application.add_handler(CommandHandler("balance", self.command_handler.balance_command))
        self.application.add_handler(CommandHandler("top", self.command_handler.top_command))
        self.application.add_handler(CommandHandler("top5", self.command_handler.top5_command))
        self.application.add_handler(CommandHandler("kurs", self.command_handler.course_command))  # FIXED: латиница вместо кириллицы
        self.application.add_handler(CommandHandler("course", self.command_handler.course_command))
        self.application.add_handler(CommandHandler("give_pulse", self.command_handler.give_pulse_command))
        self.application.add_handler(CommandHandler("pay", self.command_handler.pay_command))
        self.application.add_handler(CommandHandler("tip", self.command_handler.tip_command))
        self.application.add_handler(CommandHandler("donate", self.command_handler.donate_command))
        self.application.add_handler(CommandHandler("help", self.command_handler.help_command))
        self.application.add_handler(CommandHandler("recalc", lambda u, c: recalc_rate_command(u, c, self.db, self.main_admin_id, self.target_chat_id)))
        self.application.add_handler(CommandHandler("profile", self.command_handler.profile_command))
        self.application.add_handler(CommandHandler("wipe_balances", self.command_handler.wipe_balances_command))
        self.application.add_handler(CommandHandler("set_bank", self.command_handler.set_bank_command))
        self.application.add_handler(CommandHandler("fix_left", self.command_handler.fix_left_command))
        # Убрать пользователя из топов по @username или ID
        self.application.add_handler(CommandHandler("remove_from_top", self.command_handler.remove_from_top_command))
        # Разморозить пульсы пользователя (вернуть баланс)
        self.application.add_handler(CommandHandler("unfreeze", self.command_handler.unfreeze_command))
        # Восстановить все анкеты BBS (только для владельца)
        self.application.add_handler(CommandHandler("restore_bbs", self.command_handler.restore_bbs_command))
        # Восстановить все посты НьюзON (только для владельца)
        self.application.add_handler(CommandHandler("restore_news", self.command_handler.restore_news_command))
        self.application.add_handler(CommandHandler("resend_dossier", self.command_handler.resend_dossier_command))
        self.application.add_handler(CommandHandler("mute", self.command_handler.mute_command))
        self.application.add_handler(CommandHandler("unmute", self.command_handler.unmute_command))
        self.application.add_handler(CommandHandler("ban", self.command_handler.ban_command))
        self.application.add_handler(CommandHandler("unban", self.command_handler.unban_command))
        # Forum topic event handlers (MUST be before general message handler)
        self.application.add_handler(
            MessageHandler(
                filters.StatusUpdate.FORUM_TOPIC_CREATED | 
                filters.StatusUpdate.FORUM_TOPIC_EDITED |
                filters.StatusUpdate.FORUM_TOPIC_CLOSED |
                filters.StatusUpdate.FORUM_TOPIC_REOPENED,
                self.message_handler.handle_forum_topic_event
            )
        )
        
        # Message handler
        self.application.add_handler(
            MessageHandler(
                (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.VOICE | 
                 filters.AUDIO | filters.ANIMATION | filters.Document.ALL |
                 filters.VIDEO_NOTE | filters.Sticker.ALL) & (~filters.StatusUpdate.ALL),
                self.message_handler.handle_message
            )
        )
        
        # Callback handler
        self.application.add_handler(CallbackQueryHandler(self.callback_handler.handle_callback))
        
        # Message reaction handler (для подсчёта реакций)
        self.application.add_handler(MessageReactionHandler(self.message_handler.handle_reaction))
        
        # Chat member handler
        self.application.add_handler(
            ChatMemberHandler(
                self.message_handler.handle_member_left,
                ChatMemberHandler.CHAT_MEMBER
            )
        )
        
        # Заявки на вступление (ChatJoinRequest)
        from telegram.ext import ChatJoinRequestHandler
        self.application.add_handler(ChatJoinRequestHandler(self.handle_join_request))

        # Кастомные титулы (V1.16.0): UI юзера + панель Владельца
        try:
            from handlers.titles_handlers import register_titles
            from handlers.owner_titles_panel import register_owner_titles
            register_titles(
                self.application, self.db,
                self.target_chat_id, self.main_admin_id
            )
            register_owner_titles(self.application)
            logger.info("Titles (V1.16.0) handlers registered")
        except Exception as e:
            logger.error(f"Failed to register titles handlers: {e}")

        # Error handler (MUST be last)
        self.application.add_error_handler(self.error_handler)

        logger.info("Handlers setup complete")
    
    async def handle_join_request(self, update: Update, context):
        """Обработка заявок на вступление по одноразовым ссылкам.
        Одобряем только тех, кто:
          - есть в БД регистраций
          - имеет заполненную анкету (q_name)
          - не в чёрном списке
          - не забанен и не отклонён
          - имеет приемлемый статус (не pending/new/blocked)
        """
        request = update.chat_join_request
        user_id = request.from_user.id

        try:
            from database.db_friend import get_user as get_reg_user, is_blacklisted

            reg_user = await get_reg_user(user_id)

            # 1. Нет в БД регистраций — попытка входа по чужой ссылке
            if not reg_user:
                await request.decline()
                logger.warning(f"❌ JoinRequest: user {user_id} not in registration DB — declined")
                return

            # 2. В чёрном списке
            if await is_blacklisted(user_id):
                await request.decline()
                logger.warning(f"❌ JoinRequest: user {user_id} is blacklisted — declined")
                return

            # 3. Забанен
            if reg_user.get('is_banned'):
                await request.decline()
                logger.warning(f"❌ JoinRequest: user {user_id} is banned — declined")
                return

            # 4. Анкета не заполнена
            if not reg_user.get('q_name'):
                await request.decline()
                logger.warning(f"❌ JoinRequest: user {user_id} has no q_name — declined")
                return

            # 5. Недопустимый статус (не должен попасть в чат напрямую)
            bad_statuses = {'pending', 'new', 'in_work', 'blocked', 'rejected', 'banned'}
            current_status = (reg_user.get('status') or '').lower()
            if current_status in bad_statuses:
                await request.decline()
                logger.warning(
                    f"❌ JoinRequest: user {user_id} has bad status='{current_status}' — declined"
                )
                return

            # ✅ Все проверки пройдены — одобряем
            await request.approve()
            logger.info(f"✅ JoinRequest: user {user_id} approved (status={current_status})")

            # Синхронизируем основную БД сразу — is_left=0
            try:
                main_user = self.db.get_user(user_id)
                if main_user:
                    self.db.cursor.execute(
                        "UPDATE users SET is_left = 0 WHERE user_id = ?", (user_id,)
                    )
                    self.db.conn.commit()
            except Exception as sync_err:
                logger.warning(f"JoinRequest sync error for {user_id}: {sync_err}")

        except Exception as e:
            logger.error(f"Ошибка при обработке заявки на вступление: {e}")
    
    async def check_inactive_users_job(self):
        """Scheduled: проверка неактивных пользователей (60+ дней)"""
        try:
            from handlers.reminders import check_inactive_users
            await check_inactive_users(
                self.application.bot, self.db,
                self.target_chat_id, self.main_admin_id
            )
        except Exception as e:
            logger.error(f"Error in check_inactive_users: {e}")

    async def cleanup_title_requests_job(self):
        """Scheduled: авто-expire pending заявок на титулы (V1.16.0)."""
        try:
            from handlers.titles_handlers import _get_request_ttl_hours, _format_number
            ttl_hours = _get_request_ttl_hours(self.db)
            expired = self.db.expire_old_title_requests(ttl_hours)
            if not expired:
                return
            logger.info(f"🏷 Title requests auto-expired: {len(expired)}")
            for req in expired:
                chat_id = req.get('owner_chat_id')
                msg_id = req.get('owner_msg_id')
                if not chat_id or not msg_id:
                    continue
                try:
                    await self.application.bot.edit_message_text(
                        chat_id=chat_id, message_id=msg_id,
                        text=(f"📨 ЗАЯВКА #{req['id']} — ⌛ ИСТЕКЛА (TTL {ttl_hours} ч)\n\n"
                              f"🏷 «{req['title_text']}» · "
                              f"{_format_number(req['price_rub'])} ₽"),
                        parse_mode='HTML',
                    )
                except Exception as e:
                    logger.debug(f"Title cleanup edit failed for #{req['id']}: {e}")
        except Exception as e:
            logger.error(f"cleanup_title_requests_job: {e}")

    async def send_weekly_report_job(self):
        """Scheduled: еженедельный отчёт владельцу"""
        try:
            from handlers.reminders import send_weekly_report
            await send_weekly_report(
                self.application.bot, self.db, self.main_admin_id
            )
        except Exception as e:
            logger.error(f"Error in weekly report: {e}")

    def setup_jobs(self):
        """Setup scheduled jobs"""
        # Daily statistics DISABLED - use /top5 command instead
        # stats_hour = int(os.getenv('STATS_HOUR', 23))
        # stats_minute = int(os.getenv('STATS_MINUTE', 59))
        # 
        # self.scheduler.add_job(
        #     self.daily_statistics,
        #     'cron',
        #     hour=stats_hour,
        #     minute=stats_minute,
        #     id='daily_stats'
        # )
        
        # Check referral qualifications every hour
        self.scheduler.add_job(
            self.check_qualifications,
            'interval',
            hours=1,
            id='check_qualifications'
        )

        # V1.16.0: cleanup истёкших pending-заявок на титулы (раз в час)
        self.scheduler.add_job(
            self.cleanup_title_requests_job,
            'interval',
            hours=1,
            id='cleanup_title_requests'
        )
        
        # Check lottery endings every minute
        self.scheduler.add_job(
            self.check_lottery_end,
            'interval',
            minutes=1,
            id='check_lottery'
        )
        
        # Draw bingo balls every 30 seconds (actual interval per-game)
        self.scheduler.add_job(
            self.check_bingo_balls,
            'interval',
            seconds=30,
            id='check_bingo'
        )
        
        # Cleanup expired frozen balances every 6 hours
        self.scheduler.add_job(
            self.cleanup_expired_freezes,
            'interval',
            hours=6,
            id='cleanup_freezes'
        )
        
        # Check scheduled posts every 30 seconds
        self.scheduler.add_job(
            self.check_scheduled_posts,
            'interval',
            seconds=30,
            id='check_scheduled_posts'
        )
        
        # Cleanup dead BBS profiles every 12 hours
        self.scheduler.add_job(
            self.cleanup_bbs_profiles,
            'interval',
            hours=12,
            id='bbs_cleanup'
        )

        # Очистка лога дедупликации stat_events_log — раз в сутки
        self.scheduler.add_job(
            self._cleanup_stat_events_log,
            'interval',
            hours=24,
            id='cleanup_stat_events_log'
        )
        
        # ═══ КУРС: полный пересчёт каждые 30 минут ═══
        self.scheduler.add_job(
            self.update_exchange_rate,
            'interval',
            minutes=30,
            id='update_exchange_rate'
        )
        
        # ═══ ТОП-5: снапшот в 10:00 и 22:00 МСК ═══
        self.scheduler.add_job(
            self.update_top5_activists,
            'cron',
            hour=10,
            minute=0,
            id='top5_morning'
        )
        self.scheduler.add_job(
            self.update_top5_activists,
            'cron',
            hour=22,
            minute=0,
            id='top5_evening'
        )

        # ═══ ТОП-5 % активности: каждый час ═══
        self.scheduler.add_job(
            self.update_top5_percent,
            'interval',
            hours=1,
            id='top5_percent_hourly'
        )

        # ═══ Проверка неактивных пользователей (раз в 24 часа) ═══
        self.scheduler.add_job(
            self.check_inactive_users_job,
            'interval',
            hours=24,
            id='check_inactive'
        )
        
        # ═══ Еженедельный отчёт владельцу (воскресенье 20:00 МСК) ═══
        self.scheduler.add_job(
            self.send_weekly_report_job,
            'cron',
            day_of_week='sun',
            hour=20,
            minute=0,
            id='weekly_report'
        )
        
        self.scheduler.start()
        logger.info("Scheduled jobs setup complete")
    
    def run(self):
        """Run the bot"""
        try:
            # Create application (job_queue включен для модулей, которым нужен run_once)
            builder = Application.builder()
            builder.token(self.bot_token)
            builder.post_init(self.post_init)
            
            self.application = builder.build()
            
            logger.info("Starting bot...")
            
            # Run the bot
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
        finally:
            # Cleanup
            self.db.close()
            logger.info("Bot stopped")

def main():
    """Main entry point"""
    # ── Защита от двойного запуска (PID-файл) ───────────────────────────────
    pid_file = os.path.join(_BASE_DIR, 'bot.pid')
    my_pid = os.getpid()

    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)   # проверяем жив ли процесс (0 = не убиваем)
            logging.critical(
                f"⛔ Бот уже запущен (PID={old_pid})! "
                f"Остановите предыдущий процесс перед новым запуском."
            )
            import sys; sys.exit(1)
        except (ProcessLookupError, ValueError, OSError):
            pass  # процесс мёртв — перезаписываем pid

    with open(pid_file, 'w') as f:
        f.write(str(my_pid))

    try:
        bot = TelegramBot()
        bot.run()
    finally:
        try:
            os.remove(pid_file)
        except OSError:
            pass

if __name__ == '__main__':
    main()