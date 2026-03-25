"""
Launcher для бота Pulse 4ever
Гарантированно работающая версия с правильными путями
"""
import sys
import os

# Получаем абсолютный путь к директории проекта
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Добавляем в начало sys.path
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

print("=" * 70)
print("PULSE 4EVER BOT - LAUNCHER")
print("=" * 70)
print(f"Проект: {PROJECT_DIR}")
print(f"Python: {sys.version.split()[0]}")
print()

# Проверяем структуру
print("Проверка структуры проекта...")
required = {
    'handlers': os.path.join(PROJECT_DIR, 'handlers'),
    'middlewares': os.path.join(PROJECT_DIR, 'middlewares'),
    'utils': os.path.join(PROJECT_DIR, 'utils'),
}

missing = []
for name, path in required.items():
    if os.path.isdir(path):
        init_file = os.path.join(path, '__init__.py')
        if os.path.isfile(init_file):
            print(f"  ✓ {name}/")
        else:
            print(f"  ✗ {name}/ (отсутствует __init__.py)")
            missing.append(f"{name}/__init__.py")
    else:
        print(f"  ✗ {name}/ (директория не найдена)")
        missing.append(f"{name}/")

if missing:
    print(f"\n❌ ОШИБКА: Не найдены следующие компоненты:")
    for item in missing:
        print(f"   - {item}")
    print(f"\nУстановите все файлы в: {PROJECT_DIR}")
    sys.exit(1)

print("\n✓ Структура проекта корректна")
print("\nЗапуск бота...\n")
print("=" * 70)

# Теперь запускаем main
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Импортируем наши модули
from config import BOT_TOKEN, OWNER_ID, ACTIVITY_CHECK_INTERVAL, PHOTO_CLEANUP_INTERVAL
from database import (
    init_db, 
    get_inactive_users, 
    get_old_journal_photos, 
    delete_journal_message,
    cleanup_expired_locks
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class BackgroundTasks:
    """Управление фоновыми задачами"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.tasks = []
        self._running = False
    
    async def activity_checker(self):
        """Проверка неактивных пользователей (60+ дней)"""
        while self._running:
            try:
                logger.info("Running activity checker...")
                inactive_users = await get_inactive_users(days=60)
                
                for user in inactive_users:
                    try:
                        from utils.journal import log_inactivity
                        await log_inactivity(self.bot, user['tg_id'])
                        logger.info(f"Logged inactivity for user {user['tg_id']}")
                    except Exception as e:
                        logger.error(f"Error logging inactivity: {e}")
                
                logger.info(f"Activity check complete. Found {len(inactive_users)} inactive users.")
                
            except Exception as e:
                logger.error(f"Activity checker error: {e}", exc_info=True)
            
            await asyncio.sleep(ACTIVITY_CHECK_INTERVAL)
    
    async def photo_cleaner(self):
        """Очистка старых фотографий из журнала (14+ дней)"""
        while self._running:
            try:
                logger.info("Running photo cleaner...")
                old_photos = await get_old_journal_photos(days=14)
                
                deleted_count = 0
                for photo in old_photos:
                    try:
                        await self.bot.delete_message(
                            chat_id=photo['chat_id'],
                            message_id=photo['message_id']
                        )
                        await delete_journal_message(photo['message_id'])
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete photo: {e}")
                
                logger.info(f"Photo cleanup complete. Deleted {deleted_count} photos.")
                
            except Exception as e:
                logger.error(f"Photo cleaner error: {e}", exc_info=True)
            
            await asyncio.sleep(PHOTO_CLEANUP_INTERVAL)
    
    async def lock_cleanup(self):
        """Очистка истекших блокировок заявок"""
        while self._running:
            try:
                await cleanup_expired_locks()
                logger.debug("Lock cleanup complete")
            except Exception as e:
                logger.error(f"Lock cleanup error: {e}", exc_info=True)
            
            await asyncio.sleep(120)
    
    async def start(self):
        """Запуск всех фоновых задач"""
        self._running = True
        
        self.tasks = [
            asyncio.create_task(self.activity_checker()),
            asyncio.create_task(self.photo_cleaner()),
            asyncio.create_task(self.lock_cleanup())
        ]
        
        logger.info("Background tasks started")
    
    async def stop(self):
        """Остановка всех фоновых задач"""
        self._running = False
        
        for task in self.tasks:
            task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logger.info("Background tasks stopped")


async def on_startup(bot: Bot, background_tasks: BackgroundTasks):
    """Действия при запуске бота"""
    logger.info("Initializing database...")
    await init_db()
    
    logger.info("Starting background tasks...")
    await background_tasks.start()
    
    try:
        await bot.send_message(
            OWNER_ID,
            "✅ Бот Pulse 4ever запущен и готов к работе!"
        )
    except Exception as e:
        logger.error(f"Failed to notify owner: {e}")
    
    logger.info("Bot started successfully")


async def on_shutdown(bot: Bot, background_tasks: BackgroundTasks):
    """Действия при остановке бота"""
    logger.info("Shutting down...")
    
    await background_tasks.stop()
    
    try:
        await bot.send_message(
            OWNER_ID,
            "⚠️ Бот Pulse 4ever остановлен"
        )
    except Exception as e:
        logger.error(f"Failed to notify owner: {e}")
    
    await bot.session.close()
    
    logger.info("Bot stopped")


async def main():
    """Главная функция запуска бота"""
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        sys.exit(1)
    
    # Создаем бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создаем диспетчер
    dp = Dispatcher(storage=MemoryStorage())
    
    # Background tasks
    background_tasks = BackgroundTasks(bot)
    
    # Регистрируем middleware
    try:
        from middlewares.profile_tracker import ProfileTrackerMiddleware
        dp.message.middleware(ProfileTrackerMiddleware())
        logger.info("✓ Middleware registered")
    except ImportError as e:
        logger.warning(f"Middleware not loaded: {e}")
    
    # Регистрируем роутеры
    try:
        from handlers import (
            registration_router,
            admin_router,
            owner_router,
            chat_events_router
        )
        
        dp.include_router(registration_router)
        dp.include_router(admin_router)
        dp.include_router(owner_router)
        dp.include_router(chat_events_router)
        
        logger.info("✓ All handlers registered successfully")
    except ImportError as e:
        logger.error(f"Failed to load handlers: {e}")
        logger.warning("Bot will run with limited functionality")
    
    # Startup
    await on_startup(bot, background_tasks)
    
    # Запускаем polling
    try:
        logger.info("Starting polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"Polling error: {e}", exc_info=True)
    finally:
        await on_shutdown(bot, background_tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
