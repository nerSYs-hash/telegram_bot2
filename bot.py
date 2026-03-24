#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
    filters,
    ContextTypes
)

from handlers.admin_moderation import admin_moderation_callback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
from handlers.moderation import mute_command, unmute_command, ban_command, restrict_command
# Import custom modules
from database.db_manager import Database
from handlers.command_handler import CommandHandler as BotCommandHandler
from handlers.message_handler import MessageHandler as BotMessageHandler
from handlers.callback_handler import CallbackHandler
from handlers.commands.exchange_commands import recalc_rate_command
from utils.helpers import get_moscow_time, format_number
from utils.exchange_rate import rate_cache, scheduled_rate_update, scheduled_top5_update
from database.db_friend import init_db # Импортируем инициализацию друга
from database.db_friend import init_db
#from middlewares.registration_check import CheckRegistrationMiddleware
from handlers.registration_conversation import registration_conv
# Load environment variables
load_dotenv()

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)


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
    async def on_startup():
        await init_db() # Создаем таблицы друга, если их нет
        print("База данных друга подключена!")
    
    def __init__(self):
        """Initialize the bot"""
        # Get configuration from environment
        self.bot_token = os.getenv('BOT_TOKEN')
        self.main_admin_id = int(os.getenv('MAIN_ADMIN_ID'))
        self.target_chat_id = int(os.getenv('TARGET_CHAT_ID'))
        self.db_path = os.getenv('DATABASE_PATH', 'database/bot_database.db')
        self.bbs_thread_id = int(os.getenv('BBS_THREAD_ID', 0))
        
        # Initialize database
        self.db = Database(self.db_path)
        self.db.initialize_settings(
            initial_bank_balance=int(os.getenv('INITIAL_BANK_BALANCE', 1000000)),
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
        # --- ДОБАВЛЯЕМ ЭТО ---
        await init_db() 
        logger.info("✅ База данных регистрации друга инициализирована")
        bot = application.bot
        me = await bot.get_me()
        self.bot_username = me.username
        
        logger.info(f"Bot username: @{self.bot_username}")
        
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
        
        logger.info("Handlers initialized")
        
        # Setup handlers after initialization
        self.setup_handlers()
        
        # Setup scheduled jobs
        self.setup_jobs()
        
        # Initialize rate cache
        await self.init_rate_cache()
    
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
                    
                    # Award referrer
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

    def setup_handlers(self):
        """Setup all handlers"""
        # Command handlers
        self.application.add_handler(registration_conv)
        self.application.add_handler(CommandHandler("start", self.command_handler.start_command))
        self.application.add_handler(CommandHandler("menu", self.command_handler.menu_command))
        self.application.add_handler(CommandHandler("balance", self.command_handler.balance_command))
        self.application.add_handler(CommandHandler("top", self.command_handler.top_command))
        self.application.add_handler(CommandHandler("top5", self.command_handler.top5_command))
        self.application.add_handler(CommandHandler("kurs", self.command_handler.course_command))  # FIXED: латиница вместо кириллицы
        self.application.add_handler(CommandHandler("course", self.command_handler.course_command))
        self.application.add_handler(CommandHandler("give_pulse", self.command_handler.give_pulse_command))
        self.application.add_handler(CommandHandler("pay", self.command_handler.pay_command))
        self.application.add_handler(CommandHandler("donate", self.command_handler.donate_command))
        self.application.add_handler(CommandHandler("help", self.command_handler.help_command))
        self.application.add_handler(CommandHandler("recalc", lambda u, c: recalc_rate_command(u, c, self.db, self.main_admin_id, self.target_chat_id)))
        self.application.add_handler(CommandHandler("profile", self.command_handler.profile_command))
        self.application.add_handler(CommandHandler("wipe_balances", self.command_handler.wipe_balances_command))
        self.application.add_handler(CommandHandler("set_bank", self.command_handler.set_bank_command))
        self.application.add_handler(CommandHandler("mute", lambda u, c: mute_command(u, c, self.db, self.main_admin_id, self.target_chat_id)))
        self.application.add_handler(CommandHandler("unmute", lambda u, c: unmute_command(u, c, self.db, self.main_admin_id, self.target_chat_id)))
        self.application.add_handler(CommandHandler("ban", lambda u, c: ban_command(u, c, self.db, self.main_admin_id, self.target_chat_id)))
        self.application.add_handler(CommandHandler("restrict", lambda u, c: restrict_command(u, c, self.db, self.main_admin_id, self.target_chat_id)))
        self.application.add_handler(CallbackQueryHandler(admin_moderation_callback, pattern="^adm_"))

        # Панель администратора — кнопки
        from handlers.admin_moderation import (
            new_application_callback, send_admin_panel,
            panel_callback, handle_panel_input, handle_reject_reason
        )
        self.application.add_handler(CallbackQueryHandler(new_application_callback, pattern="^new_app$"))
        self.application.add_handler(CallbackQueryHandler(panel_callback, pattern="^panel_"))

        # Ввод текста — причина отказа и ввод данных для панели владельца
        async def _combined_text_handler(update, context):
            if not await handle_panel_input(update, context):
                await handle_reject_reason(update, context)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, _combined_text_handler),
            group=1
        )

        # Команда /panel — отправляет панель в чат администраторов
        async def panel_command(update, context):
            uid = update.effective_user.id
            is_owner = (uid == self.main_admin_id)
            user_data = self.db.get_user(uid)
            is_adm = is_owner or (user_data and (user_data.get('is_admin') or user_data.get('is_owner')))
            if is_adm:
                await send_admin_panel(context.bot, update.effective_chat.id, is_owner=is_owner)
        self.application.add_handler(CommandHandler("panel", panel_command))
        
        # Forum topic event handlers (MUST be before general message handler)
        self.application.add_handler(
            MessageHandler(
                (filters.StatusUpdate.FORUM_TOPIC_CREATED |
                filters.StatusUpdate.FORUM_TOPIC_EDITED |
                filters.StatusUpdate.FORUM_TOPIC_CLOSED |
                filters.StatusUpdate.FORUM_TOPIC_REOPENED) &
                ~filters.COMMAND,
                self.message_handler.handle_forum_topic_event
            )
        )
        
        # Message handler
        self.application.add_handler(
            MessageHandler(
                filters.TEXT | filters.PHOTO | filters.VIDEO | filters.VOICE | 
                filters.AUDIO | filters.ANIMATION | filters.Document.ALL,
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
        
        logger.info("✅ Handlers setup complete and ordered correctly")
        
    
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
        
        # Сброс просроченных блокировок заявок (каждую минуту)
        from database.db_friend import cleanup_expired_locks
        self.scheduler.add_job(
            cleanup_expired_locks,
            'interval',
            minutes=1,
            id='cleanup_expired_locks'
        )

        from handlers.reminder_logic import send_registration_reminders
        self.scheduler.add_job(
            send_registration_reminders,
            'interval',
            minutes=1,
            args=[self.application], # Передаем объект бота
            id='registration_reminders'
        )
        
        self.scheduler.start()
        logger.info("Scheduled jobs setup complete")
    
    def run(self):
        """Run the bot"""
        try:
            builder = Application.builder()
            builder.token(self.bot_token)
            builder.post_init(self.post_init)
            
            from telegram.ext import JobQueue
            builder.job_queue(None)
            
            self.application = builder.build()
            
            # Передаем базу данных в bot_data, чтобы она была доступна везде
            self.application.bot_data['db'] = self.db
            # Регистрируем обработчик ошибок
            self.application.add_error_handler(self.error_handler)
            
            logger.info("Starting bot...")
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
        finally:
            self.db.close()
            logger.info("Bot stopped")
            
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        import traceback
        logger.error(f"Exception while handling an update: {context.error}")
        traceback.print_exc()

def main():
    """Main entry point"""
    # Create and run bot
    bot = TelegramBot()
    bot.run()

if __name__ == '__main__':
    main()
