"""
Pulse Site ↔ Bot Database Bridge
Bot: /root/economybot
Site: /home/pulse-site
"""
import sys
import os

# ═══ HARDCODED PATHS (your server layout) ═══
BOT_ROOT = '/root/economybot'
BOT_DB_PATH = os.path.join(BOT_ROOT, 'database', 'bot_database.db')

# Add bot root to Python path so we can import its modules
if BOT_ROOT not in sys.path:
    sys.path.insert(0, BOT_ROOT)

# Try to import bot's Database class
try:
    from database.db_manager import Database
    db = Database(db_path=BOT_DB_PATH)
    print(f"✅ db_bridge: Подключено к {BOT_DB_PATH}")
except ImportError as e:
    print(f"⚠️ db_bridge: Не найден database.db_manager в {BOT_ROOT}")
    print(f"   Ошибка: {e}")
    print(f"   Бот будет работать без данных из базы бота")
    db = None
except Exception as e:
    print(f"⚠️ db_bridge: Ошибка подключения к БД бота: {e}")
    db = None

def get_user_data(tg_id: int):
    """Get user data from bot's database"""
    if db is None:
        return None
    try:
        user = db.get_user(tg_id)
        return dict(user) if user else None
    except Exception as e:
        print(f"db_bridge.get_user_data({tg_id}) error: {e}")
        return None

def get_pulse_stats():
    """Get exchange rate from bot's database"""
    if db is None:
        return {"rate": 1.0}
    try:
        rate = db.get_exchange_rate()
        return {"rate": rate}
    except:
        return {"rate": 1.0}
