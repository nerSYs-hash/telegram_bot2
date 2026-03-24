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
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", 3794322036))  # ID чата администраторов
JOURNAL_CHANNEL_ID: Optional[str] = os.getenv("JOURNAL_CHANNEL_ID")  # Устанавливается через бота

# Проверка обязательных параметров
if not BOT_TOKEN:
    # Для демонстрации в AI Studio, если токен не задан, мы не будем падать сразу, 
    # но в реальной работе он обязателен.
    BOT_TOKEN = "8594974597:AAG7w-wl9lTcG1QfJTVkS4PYW47UI3VvIqE" 

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