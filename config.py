"""
Оптимизированный конфигурационный модуль
"""
import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Основные настройки
BOT_TOKEN: Optional[str] = os.getenv("BOT_TOKEN")
OWNER_ID: int = int(os.getenv("MAIN_ADMIN_ID", 7536752126))
CHAT_ID: int = int(os.getenv("CHAT_ID", 0))  # ID основного чата
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", -1003794322036))  # ID чата администраторов
DEVELOPER_ID: Optional[int] = int(os.getenv("DEVELOPER_ID", 7536752126))  # ID разработчика (@Nersys)
DOSSIER_THREAD_ID: int = int(os.getenv("DOSSIER_THREAD_ID", 176))       # Тред для досье после одобрения
APPLICATIONS_THREAD_ID: int = int(os.getenv("APPLICATIONS_THREAD_ID", 241))  # Тред для входящих заявок
BUG_THREAD_BOT: int = int(os.getenv("BUG_THREAD_BOT", 12195))           # Тред багов бота
BUG_THREAD_SITE: int = int(os.getenv("BUG_THREAD_SITE", 14235))         # Тред багов сайта
JOURNAL_CHANNEL_ID: Optional[str] = os.getenv("JOURNAL_CHANNEL_ID")  # Устанавливается через бота

# Проверка обязательных параметров
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Положи его в .env (BOT_TOKEN=...) — "
        "никогда не хардкодь токен в коде/документации, иначе бот будет угнан."
    )

if not OWNER_ID:
    OWNER_ID = 7536752126

# Настройки базы данных
DATABASE_PATH = "pulse_bot.db"

# Таймауты и интервалы (в секундах)
APPLICATION_LOCK_TIMEOUT = 120  # секунд (2 минуты)
ACTIVITY_CHECK_INTERVAL = 86400  # секунд (24 часа)
PHOTO_CLEANUP_INTERVAL = 86400  # секунд (24 часа)
INACTIVE_THRESHOLD_DAYS = 60
PHOTO_RETENTION_DAYS = 14
SURVEY_COOLDOWN_DAYS = 30

# Логирование
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")

ICON_MONEY_BAG = "💰"
ICON_ROCKET = "🚀"
ICON_MILITARY_MEDAL = "🎖️"