from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import sys
import json
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
    db = Database(db_path='database/bot_database.db')
    logger.info("✅ База данных подключена: database/bot_database.db")
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

# ── Маппинг условий: wizard → DB ──
COND_TO_DB  = {'any_word': 'contains', 'exact_match': 'exact', 'regex': 'regex'}
COND_FROM_DB = {v: k for k, v in COND_TO_DB.items()}


class TriggerIn(BaseModel):
    name: str
    condition: str = 'any_word'
    keyword: str = ''
    probability: int = 100
    where: str = 'chat'
    from_who: str = 'all'
    action: str = 'send_text'
    duration: str = '0'
    reply_text: str = ''
    media_type: str = 'none'
    bot_msg_delete: str = 'no'
    bot_msg_delete_after: int = 60


def _row_to_trigger(row: dict) -> dict:
    cfg = {}
    try:
        cfg = json.loads(row.get('action_configs') or '{}')
    except Exception:
        pass
    return {
        'id':                  row['id'],
        'name':                row['name'],
        'condition':           COND_FROM_DB.get(row.get('condition', 'contains'), 'any_word'),
        'keyword':             row.get('keywords', ''),
        'probability':         row.get('probability', 100),
        'where':               row.get('where_fires', 'chat'),
        'from':                row.get('initiator', 'all'),
        'action':              row.get('action', 'send_text'),
        'duration':            row.get('action_value') or '0',
        'reply_text':          cfg.get('reply_text', ''),
        'media_type':          cfg.get('media_type', 'none'),
        'bot_msg_delete':      row.get('bot_msg_delete', 'no'),
        'bot_msg_delete_after':row.get('bot_msg_delete_after') or 60,
        'is_enabled':          bool(row.get('is_enabled', 1)),
    }


@app.get("/api/triggers")
async def get_triggers():
    """Список триггеров из БД"""
    try:
        db.cursor.execute("SELECT * FROM triggers ORDER BY id DESC")
        return [_row_to_trigger(dict(r)) for r in db.cursor.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/triggers")
async def create_trigger(t: TriggerIn):
    """Создать триггер"""
    try:
        cfg = json.dumps({'reply_text': t.reply_text, 'media_type': t.media_type})
        db.cursor.execute('''
            INSERT INTO triggers
                (name, keywords, condition, action, action_value, probability,
                 where_fires, initiator, bot_msg_delete, bot_msg_delete_after,
                 action_configs, is_enabled)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,1)
        ''', (t.name, t.keyword, COND_TO_DB.get(t.condition, 'contains'),
              t.action, t.duration, t.probability,
              t.where, t.from_who, t.bot_msg_delete, t.bot_msg_delete_after, cfg))
        db.conn.commit()
        return {'id': db.cursor.lastrowid, 'success': True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/triggers/{trigger_id}")
async def update_trigger(trigger_id: int, t: TriggerIn):
    """Обновить триггер"""
    try:
        cfg = json.dumps({'reply_text': t.reply_text, 'media_type': t.media_type})
        db.cursor.execute('''
            UPDATE triggers SET
                name=?, keywords=?, condition=?, action=?, action_value=?,
                probability=?, where_fires=?, initiator=?, bot_msg_delete=?,
                bot_msg_delete_after=?, action_configs=?
            WHERE id=?
        ''', (t.name, t.keyword, COND_TO_DB.get(t.condition, 'contains'),
              t.action, t.duration, t.probability,
              t.where, t.from_who, t.bot_msg_delete, t.bot_msg_delete_after,
              cfg, trigger_id))
        db.conn.commit()
        return {'success': True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/triggers/{trigger_id}")
async def delete_trigger(trigger_id: int):
    """Удалить триггер"""
    try:
        db.cursor.execute("DELETE FROM triggers WHERE id=?", (trigger_id,))
        db.conn.commit()
        return {'success': True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/journal")
async def get_journal():
    """Журнал событий: нарушения триггеров + транзакции модерации"""
    try:
        entries = []

        # ── Нарушения триггеров ──
        db.cursor.execute('''
            SELECT tv.user_id, tv.trigger_id, tv.count, tv.last_violation_at,
                   t.name AS trigger_name, t.action,
                   u.username, u.first_name
            FROM trigger_violations tv
            JOIN triggers t ON tv.trigger_id = t.id
            LEFT JOIN users u ON tv.user_id = u.user_id
            ORDER BY tv.last_violation_at DESC
            LIMIT 40
        ''')
        for r in (dict(x) for x in db.cursor.fetchall()):
            uname = r.get('username') or r.get('first_name') or str(r['user_id'])
            entries.append({
                'id':      f"tv_{r['trigger_id']}_{r['user_id']}",
                'time':    (r['last_violation_at'] or '')[:16],
                'type':    'trigger',
                'tag':     '#Триггер',
                'user':    f"@{uname}" if r.get('username') else uname,
                'user_id': r['user_id'],
                'text':    f'Триггер «{r["trigger_name"]}» — {r["count"]} раз. Действие: {r["action"]}',
            })

        # ── Транзакции модерации ──
        db.cursor.execute('''
            SELECT t.id, t.from_user_id, t.transaction_type, t.description, t.timestamp,
                   u.username, u.first_name
            FROM transactions t
            LEFT JOIN users u ON t.from_user_id = u.user_id
            WHERE t.transaction_type IN ('mute','ban','warn','kick','unban','unmute')
            ORDER BY t.timestamp DESC
            LIMIT 30
        ''')
        TYPE_TAG = {'mute':'#Мут','ban':'#Бан','warn':'#Варн',
                    'kick':'#Кик','unban':'#Разбан','unmute':'#Размут'}
        for r in (dict(x) for x in db.cursor.fetchall()):
            uname = r.get('username') or r.get('first_name') or str(r.get('from_user_id','?'))
            entries.append({
                'id':      f"tr_{r['id']}",
                'time':    (r['timestamp'] or '')[:16],
                'type':    r['transaction_type'],
                'tag':     TYPE_TAG.get(r['transaction_type'], f"#{r['transaction_type']}"),
                'user':    f"@{uname}" if r.get('username') else uname,
                'user_id': r.get('from_user_id', 0),
                'text':    r.get('description') or r['transaction_type'],
            })

        entries.sort(key=lambda x: x['time'], reverse=True)
        return entries[:60]
    except Exception as e:
        logger.error(f"Error in /api/journal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ЗАПУСК ---
if __name__ == "__main__":
    # Запуск uvicorn напрямую. reload=True включен для удобства разработки.
    uvicorn.run(app, host="0.0.0.0", port=8000)