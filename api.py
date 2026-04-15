from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import sys
from datetime import datetime, timedelta
import logging
from decimal import Decimal

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PulseApi")

# Определение путей (api.py в корне бота)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

app = FastAPI(
    title="Pulse Pro API",
    description="Backend API для панели управления (из корня бота)",
    version="1.6.0"
)

# CORS настройки: критически важны для связи с React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://puls-chat.ru", "http://puls-chat.ru", "https://www.puls-chat.ru", "http://www.puls-chat.ru"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- БЕЗОПАСНАЯ ИНИЦИАЛИЗАЦИЯ МОДУЛЕЙ БОТА ---
db = None
calculate_health = None

try:
    from database.db_manager import Database
    db = Database()
    logger.info("✅ База данных подключена успешно")
except Exception as e:
    logger.warning(f"⚠️ Ошибка подключения БД: {e}")

try:
    # Явно указываем поиск в текущей папке для stats_calculators
    if os.path.exists(os.path.join(current_dir, "stats_calculators.py")):
        import stats_calculators
        calculate_health = stats_calculators.calculate_chat_health_indices
        logger.info("✅ Модуль калькулятора здоровья подключен")
    else:
        logger.warning("⚠️ Файл stats_calculators.py не найден в корне")
except Exception as e:
    logger.warning(f"⚠️ Ошибка импорта stats_calculators: {e}")

# --- ЭНДПОИНТЫ ДЛЯ AdminDashboard.jsx ---

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "API Pulse Pro работает!",
        "time": datetime.now().strftime("%H:%M:%S"),
        "db_connected": db is not None,
        "calculators_loaded": calculate_health is not None
    }

@app.get("/api/stats")
async def get_stats():
    """Реальная статистика из БД бота"""
    try:
        today = datetime.now().date().isoformat()
        week_start = (datetime.now() - timedelta(days=6)).date().isoformat()

        bank         = float(db.get_bank_balance()) if db else 0
        rate         = float(db.get_setting('pulse_rate', '1.42')) if db else 1.42
        difficulty_k = float(db.get_setting('difficulty_k', '5.0')) if db else 5.0
        active_today = db.get_active_core_count(today) if db else 0

        total_users    = 0
        today_messages = 0
        today_pulses   = 0.0

        if db:
            db.cursor.execute(
                "SELECT COUNT(*) as c FROM users WHERE is_left=0 AND is_admin=0 AND is_owner=0"
            )
            r = db.cursor.fetchone()
            total_users = r['c'] if r else 0

            db.cursor.execute(
                "SELECT COALESCE(SUM(total_messages),0) as s FROM user_stats WHERE date=?", (today,)
            )
            r = db.cursor.fetchone()
            today_messages = int(r['s']) if r else 0

            db.cursor.execute(
                "SELECT COALESCE(SUM(pulses_mined),0) as s FROM user_stats WHERE date=?", (today,)
            )
            r = db.cursor.fetchone()
            today_pulses = float(r['s']) if r else 0.0

        dynamics = db.get_user_dynamics_stats(week_start, today) if db else {}

        # История активности: сообщений в день за 7 дней
        history = []
        for i in range(6, -1, -1):
            d = (datetime.now() - timedelta(days=i)).date()
            msgs = 0
            if db:
                db.cursor.execute(
                    "SELECT COALESCE(SUM(total_messages),0) as s FROM user_stats WHERE date=?",
                    (d.isoformat(),)
                )
                r = db.cursor.fetchone()
                msgs = int(r['s']) if r else 0
            history.append({"day": d.strftime("%a"), "val": msgs})

        return {
            "bankBalance":  bank,
            "pulseRate":    rate,
            "difficultyK":  difficulty_k,
            "activeUsers":  active_today,
            "totalUsers":   total_users,
            "messages":     today_messages,
            "pulsesMined":  today_pulses,
            "joined":       dynamics.get('joined', 0),
            "left":         dynamics.get('left', 0),
            "history":      history,
            "healthIndex":  84.5,  # TODO: подключить stats_calculators
        }
    except Exception as e:
        logger.error(f"Error in /api/stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/top")
async def get_top():
    """Топы пользователей: баланс, майнеры, активисты"""
    try:
        today = datetime.now().date().isoformat()

        def fmt(row):
            r = dict(row)
            uname = r.get('username') or r.get('first_name') or str(r.get('user_id', '?'))
            r['display_name'] = f"@{uname}" if r.get('username') else uname
            return r

        top_balance   = [fmt(r) for r in db.get_top_users_by_balance(5)]   if db else []
        top_miners    = [fmt(r) for r in db.get_top_daily_earners(today, 5)] if db else []
        top_activists = [fmt(r) for r in db.get_top_activists(today, 5)]    if db else []

        return {
            "topBalance":   top_balance,
            "topMiners":    top_miners,
            "topActivists": top_activists,
        }
    except Exception as e:
        logger.error(f"Error in /api/top: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/shipper")
async def get_shipper():
    """Данные Шиппера"""
    return {
        "enabled": True,
        "mode": "active_48",
        "categories": [
            {"id": "hot18", "name": "🔥 Горячие / 18+", "count": 42, "active": True},
            {"id": "funny", "name": "😂 Смешные / Подколы", "count": 28, "active": True},
            {"id": "romantic", "name": "💘 Милые / Романтика", "count": 15, "active": False}
        ],
        "minHours": 2,
        "maxHours": 5
    }

@app.get("/api/system")
async def get_system():
    """Системные настройки"""
    try:
        bank = db.get_bank_balance() if db else 12500450.20
        pulse_rate = db.get_setting('pulse_rate', '1.42') if db else "1.42"
        
        return {
            "pulseRate": float(pulse_rate),
            "bankBalance": bank,
            "difficultyK": 5.0,
            "admins": ["@vitya_owner", "@alex_admin"],
            "blacklist": []
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/triggers")
async def get_triggers():
    """Список триггеров"""
    return [
        {"id": 1, "name": "Анти-Реклама", "keyword": "t.me", "action": "ban", "where": "chat"},
        {"id": 2, "name": "Приветствие", "keyword": "ку привет", "action": "text", "where": "global"}
    ]

# --- ЗАПУСК ---
if __name__ == "__main__":
    # Запуск uvicorn напрямую. reload=True включен для удобства разработки.
    uvicorn.run(app, host="0.0.0.0", port=8000)