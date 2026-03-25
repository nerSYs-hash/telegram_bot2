"""
Главный файл запуска бота Pulse 4ever
"""
import sys
import os
import asyncio
import logging
from datetime import datetime

# Получаем абсолютный путь к директории проекта
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Добавляем в начало sys.path
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Импорты aiogram
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent

# Импортируем наши модули
try:
    from config import BOT_TOKEN, OWNER_ID, ACTIVITY_CHECK_INTERVAL, CHAT_ID
    from database import (
        init_db,
        get_inactive_users,
        cleanup_expired_locks,
        update_user,
        get_user,
        create_user
    )
    from constants import UserStatus, UserRole
    from handlers.reminder_all import ReminderTasks  # <-- ДОБАВИТЬ ЭТУ СТРОКУ
    print("[OK] Основные модули загружены")
except ImportError as e:
    print(f"[ERROR] Ошибка импорта основных модулей: {e}")
    sys.exit(1)

# ─── НАСТРОЙКА КРАСИВОГО ЛОГИРОВАНИЯ ───
class ColoredFormatter(logging.Formatter):
    """Кастомный форматер для цветной и ровной консоли"""
    COLORS = {
        'WARNING':  '\033[93m',
        'INFO':     '\033[94m',
        'DEBUG':    '\033[92m',
        'CRITICAL': '\033[91m',
        'ERROR':    '\033[91m',
    }
    RESET = '\033[0m'
    GRAY  = '\033[90m'
    CYAN  = '\033[36m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        time_str = self.formatTime(record, "%H:%M:%S")
        module_name = (record.module[:13] + '..') if len(record.module) > 15 else record.module
        return (
            f"{self.GRAY}[{time_str}]{self.RESET} "
            f"{color}[{record.levelname:^8}]{self.RESET} "
            f"{self.CYAN}[{module_name:<15}]{self.RESET}: "
            f"{record.getMessage()}"
        )

# Настраиваем корневой логгер
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)

# 1. Запись в файл (без цветов)
_file_handler = logging.FileHandler('bot.log', encoding='utf-8')
_file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'))
_root_logger.addHandler(_file_handler)

# 2. Вывод в консоль (с цветами)
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(ColoredFormatter())
_root_logger.addHandler(_console_handler)

# 3. Заглушаем шумных
logging.getLogger('aiogram').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
# ──────────────────────────────────────────


async def sync_chat_members(bot: Bot):
    """Автоматическая синхронизация администраторов чата при запуске"""
    if not CHAT_ID:
        logger.warning("CHAT_ID не установлен, пропускаю синхронизацию")
        return
    
    try:
        logger.info("🔄 Автоматическая синхронизация администраторов чата...")
        
        # Получаем информацию о чате
        chat = await bot.get_chat(CHAT_ID)
        logger.info(f"Чат: {chat.title}, ID: {CHAT_ID}")
        
        # Получаем администраторов чата
        admins = await bot.get_chat_administrators(CHAT_ID)
        logger.info(f"Найдено администраторов: {len(admins)}")
        
        updated_count = 0
        created_count = 0
        
        # Синхронизируем администраторов
        for admin in admins:
            user_id = admin.user.id
            username = admin.user.username
            first_name = admin.user.first_name
            last_name = admin.user.last_name
            
            # Определяем роль
            role = UserRole.OWNER if admin.status == 'creator' else UserRole.ADMIN
            
            # Проверяем, есть ли пользователь в БД
            user = await get_user(user_id)
            
            if user:
                # Обновляем статус и роль
                updates = {'status': UserStatus.IN_CHAT}
                if user.get('role') != role:
                    updates['role'] = role
                
                await update_user(user_id, **updates)
                updated_count += 1
                logger.debug(f"Обновлен статус для администратора {user_id}")
            else:
                # Создаем нового пользователя
                await create_user(
                    tg_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    role=role
                )
                await update_user(user_id, status=UserStatus.IN_CHAT)
                created_count += 1
                logger.debug(f"Создан новый администратор {user_id}")
        
        logger.info(f"✅ Синхронизация администраторов завершена:")
        logger.info(f"   - Создано новых: {created_count}")
        logger.info(f"   - Обновлено: {updated_count}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка синхронизации администраторов: {e}")


class BackgroundTasks:
    """Управление фоновыми задачами"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.tasks = []
        self._running = False
        self.reminder_tasks = None

    async def activity_checker(self):
        """Проверка неактивных пользователей (60+ дней) - п.2.1 ТЗ"""
        while self._running:
            try:
                logger.info("🔍 Проверка неактивных пользователей...")
                inactive_users = await get_inactive_users(days=60)

                for user in inactive_users:
                    try:
                        from utils.journal import log_inactivity
                        await log_inactivity(self.bot, user['tg_id'])
                        logger.info(f"⚠️ Зарегистрирована неактивность пользователя {user['tg_id']}")
                    except Exception as e:
                        logger.error(f"Ошибка логирования неактивности: {e}")

                logger.info(f"✅ Проверка неактивных завершена. Найдено: {len(inactive_users)}")

            except Exception as e:
                logger.error(f"Ошибка в activity_checker: {e}", exc_info=True)

            await asyncio.sleep(ACTIVITY_CHECK_INTERVAL)

    async def lock_cleanup(self):
        """Очистка истекших блокировок заявок (каждые 2 минуты) - п.3.0 ТЗ"""
        while self._running:
            try:
                await cleanup_expired_locks()
                logger.debug("🧹 Очистка блокировок заявок выполнена")
            except Exception as e:
                logger.error(f"Ошибка в lock_cleanup: {e}", exc_info=True)

            await asyncio.sleep(120)  # Каждые 2 минуты

    async def start(self):
        """Запуск всех фоновых задач"""
        self._running = True

        # Создаем и запускаем единый менеджер напоминаний
        self.reminder_tasks = ReminderTasks(self.bot)
        await self.reminder_tasks.start()

        self.tasks = [
            asyncio.create_task(self.activity_checker(), name="activity_checker"),
            asyncio.create_task(self.lock_cleanup(), name="lock_cleanup"),
        ]

        logger.info(f"✅ Запущено {len(self.tasks) + len(self.reminder_tasks.tasks)} фоновых задач")
        logger.info("   - activity_checker (60 дней)")
        logger.info("   - lock_cleanup (2 минуты)")
        logger.info("   - incomplete_questionnaires (5 минут)")
        logger.info("   - unused_links_5min (5 минут)")
        logger.info("   - unused_links_10days (10 дней)")

    async def stop(self):
        """Остановка всех фоновых задач"""
        self._running = False

        if self.reminder_tasks:
            await self.reminder_tasks.stop()

        for task in self.tasks:
            task.cancel()

        await asyncio.gather(*self.tasks, return_exceptions=True)

        logger.info("⏹️ Все фоновые задачи остановлены")


async def on_startup(bot: Bot, background_tasks: BackgroundTasks):
    """Действия при запуске бота"""
    logger.info("📦 Инициализация базы данных...")
    await init_db()

    # Автоматическая синхронизация администраторов чата
    await sync_chat_members(bot)

    logger.info("🚀 Запуск фоновых задач...")
    await background_tasks.start()

    try:
        await bot.send_message(
            OWNER_ID,
            "✅ **Бот Pulse 4ever запущен и готов к работе!**\n\n"
            "• Регистрация и анкетирование\n"
            "• Модерация заявок\n"
            "• Черный список\n"
            "• Журнал событий\n"
            "• Опросы ушедших\n"
            "• Напоминания (5 мин, 10 дней, 60 дней)",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить владельца: {e}")

    logger.info("✅ Бот успешно запущен")


async def on_shutdown(bot: Bot, background_tasks: BackgroundTasks):
    """Действия при остановке бота"""
    logger.info("🛑 Остановка бота...")

    await background_tasks.stop()

    try:
        await bot.send_message(
            OWNER_ID,
            "⚠️ **Бот Pulse 4ever остановлен**",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить владельца: {e}")

    await bot.session.close()

    logger.info("👋 Бот остановлен")


async def main():
    """Главная функция запуска бота"""

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.error("❌ BOT_TOKEN не настроен в .env файле")
        return

    # Создаем бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Создаем диспетчер
    dp = Dispatcher(storage=MemoryStorage())

    # Фоновые задачи
    background_tasks = BackgroundTasks(bot)

    # Регистрируем middleware
    try:
        from middlewares.profile_tracker import ProfileTrackerMiddleware
        dp.message.middleware(ProfileTrackerMiddleware())
        logger.info("✅ Middleware ProfileTracker зарегистрирован")
    except ImportError as e:
        logger.warning(f"⚠️ Middleware не загружен: {e}")

    # Регистрируем роутеры
    try:
        from handlers import (
            registration_router,
            admin_router,
            owner_router,
            chat_member_router,
            triggers_router,
            exit_survey_router,
            reminder_all_router
        )

        dp.include_router(admin_router)
        dp.include_router(owner_router)
        dp.include_router(chat_member_router)
        dp.include_router(registration_router)
        dp.include_router(triggers_router)
        dp.include_router(exit_survey_router)
        dp.include_router(reminder_all_router)

        logger.info("✅ Все обработчики зарегистрированы")
        logger.info(f"   - Всего роутеров: 7")
    except ImportError as e:
        logger.error(f"❌ Ошибка загрузки обработчиков: {e}")
        logger.warning("⚠️ Бот будет работать с ограниченным функционалом")

    # Глобальный обработчик ошибок
    @dp.error()
    async def error_handler(event: ErrorEvent):
        """Глобальный обработчик ошибок"""
        logger.error(f"❌ Ошибка при обработке обновления: {event.exception}", exc_info=True)

    # Запуск
    await on_startup(bot, background_tasks)

    # Запускаем polling
    try:
        logger.info("📡 Запуск polling...")
        await dp.start_polling(
            bot,
            allowed_updates=['message', 'edited_message', 'callback_query',
                           'chat_member', 'my_chat_member'],
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"❌ Ошибка polling: {e}", exc_info=True)
    finally:
        await on_shutdown(bot, background_tasks)


if __name__ == "__main__":
    print("=" * 70)
    print("🚀 PULSE 4EVER BOT - ЗАПУСК")
    print("=" * 70)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка: {e}", exc_info=True)
        sys.exit(1)