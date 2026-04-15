from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import io
import re
import httpx
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
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

RU_MONTHS = {1:'Янв',2:'Фев',3:'Мар',4:'Апр',5:'Май',6:'Июн',
             7:'Июл',8:'Авг',9:'Сен',10:'Окт',11:'Ноя',12:'Дек'}

PERIOD_LABELS = {
    'today':     'Сегодня',
    'yesterday': 'Вчера',
    'week':      'Неделя',
    'month':     'Месяц',
    'year':      'Год',
}


def _clean_journal_html(text: str) -> str:
    """
    Подготавливает HTML из text_preview для отображения в браузере:
    - убирает незакрытый тег в конце (обрыв по 200 символов)
    - переносы строк → <br>
    - ссылки открываются в новой вкладке
    """
    if not text:
        return ''
    text = re.sub(r'<[^>]*$', '', text)                                  # незакрытый тег в конце
    text = re.sub(r'<a\s', '<a target="_blank" rel="noopener" ', text)   # ссылки в новой вкладке
    text = text.replace('\n', '<br>')                                     # переносы строк
    return text.strip()


def _build_daily_history(start_date, end_date):
    history = []
    cur = start_date
    while cur <= end_date:
        msgs = 0
        if db:
            db.cursor.execute(
                "SELECT COALESCE(SUM(total_messages),0) as s FROM user_stats WHERE date=?",
                (cur.isoformat(),)
            )
            r = db.cursor.fetchone()
            msgs = int(r['s']) if r else 0
        history.append({"day": cur.strftime("%d.%m"), "val": msgs})
        cur += timedelta(days=1)
    return history


def _build_monthly_history(start_date, end_date):
    if not db:
        return []
    db.cursor.execute('''
        SELECT strftime('%Y-%m', date) as mon, COALESCE(SUM(total_messages),0) as val
        FROM user_stats WHERE date >= ? AND date <= ?
        GROUP BY mon ORDER BY mon
    ''', (start_date.isoformat(), end_date.isoformat()))
    history = []
    for r in db.cursor.fetchall():
        r = dict(r)
        month_num = int(r['mon'].split('-')[1])
        history.append({"day": RU_MONTHS.get(month_num, r['mon']), "val": int(r['val'])})
    return history


def _compute_stats(period: str) -> dict:
    today = datetime.now().date()

    if period == 'yesterday':
        start_date = end_date = today - timedelta(days=1)
        hist_start = today - timedelta(days=6)
        hist_end   = today
        history    = _build_daily_history(hist_start, hist_end)
    elif period == 'week':
        start_date = today - timedelta(days=6)
        end_date   = today
        history    = _build_daily_history(start_date, end_date)
    elif period == 'month':
        start_date = today - timedelta(days=29)
        end_date   = today
        history    = _build_daily_history(start_date, end_date)
    elif period == 'year':
        start_date = today - timedelta(days=364)
        end_date   = today
        history    = _build_monthly_history(start_date, end_date)
    else:  # today
        start_date = end_date = today
        hist_start = today - timedelta(days=6)
        hist_end   = today
        history    = _build_daily_history(hist_start, hist_end)

    bank         = float(db.get_bank_balance()) if db else 0
    rate         = float(db.get_setting('pulse_rate', '1.42')) if db else 1.42
    difficulty_k = float(db.get_setting('difficulty_k', '5.0')) if db else 5.0
    active       = db.get_active_core_count(start_date.isoformat()) if db else 0

    total_users = messages = pulses = 0
    if db:
        db.cursor.execute(
            "SELECT COUNT(*) as c FROM users WHERE is_left=0 AND is_admin=0 AND is_owner=0"
        )
        r = db.cursor.fetchone(); total_users = r['c'] if r else 0

        db.cursor.execute(
            "SELECT COALESCE(SUM(total_messages),0) as s FROM user_stats WHERE date>=? AND date<=?",
            (start_date.isoformat(), end_date.isoformat())
        )
        r = db.cursor.fetchone(); messages = int(r['s']) if r else 0

        db.cursor.execute(
            "SELECT COALESCE(SUM(pulses_mined),0) as s FROM user_stats WHERE date>=? AND date<=?",
            (start_date.isoformat(), end_date.isoformat())
        )
        r = db.cursor.fetchone(); pulses = float(r['s']) if r else 0.0

    dynamics = db.get_user_dynamics_stats(start_date.isoformat(), end_date.isoformat()) if db else {}

    return {
        "period":       period,
        "periodLabel":  PERIOD_LABELS.get(period, period),
        "bankBalance":  bank,
        "pulseRate":    rate,
        "difficultyK":  difficulty_k,
        "activeUsers":  active,
        "totalUsers":   total_users,
        "messages":     messages,
        "pulsesMined":  pulses,
        "joined":       dynamics.get('joined', 0),
        "left":         dynamics.get('left', 0),
        "history":      history,
        "healthIndex":  84.5,
    }


@app.get("/api/stats")
async def get_stats(period: str = Query('today')):
    """Статистика за период: today / yesterday / week / month / year"""
    try:
        return _compute_stats(period)
    except Exception as e:
        logger.error(f"Error in /api/stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/export")
async def export_stats(period: str = Query('week')):
    """Экспорт статистики в Excel"""
    try:
        data = _compute_stats(period)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Статистика"
        ws.column_dimensions['A'].width = 28
        ws.column_dimensions['B'].width = 18

        header_font  = Font(bold=True, size=13, color="FFFFFF")
        header_fill  = PatternFill("solid", fgColor="1E293B")
        bold_font    = Font(bold=True, size=11)
        label_fill   = PatternFill("solid", fgColor="F1F5F9")
        center       = Alignment(horizontal='center')

        # ── Заголовок ──
        ws.merge_cells('A1:B1')
        ws['A1'] = f"Pulse Pro — Статистика ({data['periodLabel']})"
        ws['A1'].font = header_font
        ws['A1'].fill = header_fill
        ws['A1'].alignment = center

        ws.merge_cells('A2:B2')
        ws['A2'] = f"Экспорт: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        ws['A2'].alignment = center

        # ── Метрики ──
        ws['A4'] = "Показатель";  ws['A4'].font = bold_font; ws['A4'].fill = label_fill
        ws['B4'] = "Значение";    ws['B4'].font = bold_font; ws['B4'].fill = label_fill

        metrics = [
            ("Сообщений за период", data['messages']),
            ("Активных пользователей", data['activeUsers']),
            ("Всего пользователей", data['totalUsers']),
            ("Вступило за период", data['joined']),
            ("Вышло за период", data['left']),
            ("Баланс банка", data['bankBalance']),
            ("Курс пульса", data['pulseRate']),
            ("Пульсов намайнено", data['pulsesMined']),
        ]
        for i, (label, value) in enumerate(metrics, start=5):
            ws[f'A{i}'] = label
            ws[f'B{i}'] = value

        # ── История ──
        row = 5 + len(metrics) + 2
        ws[f'A{row}'] = "История активности"
        ws[f'A{row}'].font = bold_font
        ws[f'A{row}'].fill = label_fill
        ws[f'B{row}'] = "Сообщений"
        ws[f'B{row}'].font = bold_font
        ws[f'B{row}'].fill = label_fill
        row += 1
        for item in data['history']:
            ws[f'A{row}'] = item['day']
            ws[f'B{row}'] = item['val']
            row += 1

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        fname = f"pulse_stats_{period}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={fname}"}
        )
    except Exception as e:
        logger.error(f"Error in /api/stats/export: {e}")
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
    """Журнал событий из journal_messages"""
    try:
        EVENT_TAG = {
            'join':    ('#Вход',    'join'),
            'leave':   ('#Выход',   'leave'),
            'mute':    ('#Мут',     'mute'),
            'ban':     ('#Бан',     'ban'),
            'warn':    ('#Варн',    'warn'),
            'kick':    ('#Кик',     'ban'),
            'unban':   ('#Разбан',  'unban'),
            'unmute':  ('#Размут',  'unban'),
            'trigger': ('#Триггер', 'trigger'),
        }

        db.cursor.execute('''
            SELECT jm.id, jm.event_type, jm.user_id, jm.text_preview, jm.created_at,
                   u.username, u.first_name
            FROM journal_messages jm
            LEFT JOIN users u ON jm.user_id = u.user_id
            ORDER BY jm.id DESC
            LIMIT 100
        ''')
        entries = []
        for r in (dict(x) for x in db.cursor.fetchall()):
            ev = r.get('event_type') or 'other'
            tag, typ = EVENT_TAG.get(ev, (f'#{ev}', ev))
            uname = r.get('username') or r.get('first_name') or (str(r['user_id']) if r['user_id'] else '—')
            entries.append({
                'id':      r['id'],
                'time':    (r['created_at'] or '')[:16],
                'type':    typ,
                'tag':     tag,
                'user':    f"@{uname}" if r.get('username') else uname,
                'user_id': r.get('user_id', 0),
                'text':    _clean_journal_html(r.get('text_preview') or ev),
            })

        return entries
    except Exception as e:
        logger.error(f"Error in /api/journal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- GEMINI AI ---

GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'

GEMINI_SYSTEM = """Ты — умный ИИ-ассистент встроенный в панель управления Telegram-чатом "PULSE 4ever 18+".
Помогаешь владельцу чата:
- Писать тексты для триггеров (авто-ответы на сообщения)
- Составлять тексты предупреждений, мутов, банов
- Готовить рассылки для участников
- Анализировать ситуации в чате и давать советы по модерации
- Отвечать на любые вопросы по управлению чатом

Отвечай кратко, по делу, на русском языке. Форматируй ответ — используй списки и абзацы."""

class AiRequest(BaseModel):
    prompt: str
    context: str = ''   # опциональный контекст (например, текущая статистика)

@app.post("/api/ai")
async def ai_chat(req: AiRequest):
    if not GEMINI_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY не задан на сервере")
    try:
        full_prompt = GEMINI_SYSTEM
        if req.context:
            full_prompt += f"\n\nТекущий контекст панели:\n{req.context}"
        full_prompt += f"\n\nЗапрос пользователя:\n{req.prompt}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GEMINI_URL}?key={GEMINI_KEY}",
                json={"contents": [{"parts": [{"text": full_prompt}]}]}
            )
            data = resp.json()
            logger.info(f"Gemini response status: {resp.status_code}, keys: {list(data.keys())}")
            if resp.status_code != 200:
                logger.error(f"Gemini error body: {data}")
                raise HTTPException(status_code=502, detail=data.get('error', {}).get('message', f'HTTP {resp.status_code}'))

        if 'candidates' not in data:
            logger.error(f"Gemini unexpected response: {data}")
            raise HTTPException(status_code=502, detail=f"Gemini: {data.get('error', {}).get('message', 'нет candidates')}")
        text = data['candidates'][0]['content']['parts'][0]['text']
        return {"result": text}
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini API HTTP error {e.response.status_code}: {e.response.text}")
        raise HTTPException(status_code=502, detail=f"Gemini HTTP {e.response.status_code}")
    except Exception as e:
        logger.error(f"AI error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- ЗАПУСК ---
if __name__ == "__main__":
    # Запуск uvicorn напрямую. reload=True включен для удобства разработки.
    uvicorn.run(app, host="0.0.0.0", port=8000)