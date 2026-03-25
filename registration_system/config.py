"""
Конфигурация бота Pulse 4ever (aiogram).
Значения берутся из .env, с разумными дефолтами.
"""
import os
from dotenv import load_dotenv

# Загружаем .env из той же директории, что и этот файл
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(_env_path)

# ─── Основные параметры ───────────────────────────────────────
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
OWNER_ID  = int(os.getenv('OWNER_ID', '0'))
CHAT_ID   = int(os.getenv('CHAT_ID', '0'))

# ─── Интервалы фоновых задач (секунды) ───────────────────────
# Проверка неактивных пользователей (60+ дней) — раз в час
ACTIVITY_CHECK_INTERVAL = int(os.getenv('ACTIVITY_CHECK_INTERVAL', '3600'))

# Очистка старых фото из журнала — раз в сутки
PHOTO_CLEANUP_INTERVAL  = int(os.getenv('PHOTO_CLEANUP_INTERVAL', '86400'))

# ─── Логирование ─────────────────────────────────────────────
LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', 'INFO')
