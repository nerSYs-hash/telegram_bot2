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
        "time": _now_msk().strftime("%H:%M:%S"),
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

# Московское время (UTC+3) — сервер может работать в UTC
MSK_OFFSET = timedelta(hours=3)

def _now_msk() -> datetime:
    """Текущее время по Москве (UTC+3)."""
    return datetime.utcnow() + MSK_OFFSET

def _today_msk():
    """Сегодняшняя дата по Москве."""
    return _now_msk().date()


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
    today = _today_msk()

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

    # Активные юзеры за ВЕСЬ период (DISTINCT user_id, хотя бы 1 сообщение)
    active = 0
    if db:
        db.cursor.execute(
            "SELECT COUNT(DISTINCT user_id) as c FROM user_stats "
            "WHERE date >= ? AND date <= ? AND total_messages > 0",
            (start_date.isoformat(), end_date.isoformat())
        )
        r = db.cursor.fetchone()
        active = int(r['c']) if r else 0

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

    # ── Субиндексы здоровья чата ──
    indices = {"oksp": 0.0, "sdsp": 0.0, "cho": 0.0, "media": 0.0, "korp": 0.0, "kopyup": 0.0}
    health = 0.0
    if db and messages > 0:
        try:
            db.cursor.execute(
                "SELECT COALESCE(SUM(replies_sent),0) as rpl, "
                "COALESCE(SUM(reactions_given),0) as rea, "
                "COALESCE(SUM(media_sent),0) as med "
                "FROM user_stats WHERE date>=? AND date<=?",
                (start_date.isoformat(), end_date.isoformat())
            )
            sr = db.cursor.fetchone()
            replies   = int(sr['rpl'])  if sr else 0
            reactions = int(sr['rea'])  if sr else 0
            media_cnt = int(sr['med'])  if sr else 0
            joined    = dynamics.get('joined', 0)
            left      = dynamics.get('left',   0)

            oksp       = round(min((messages / max(active, 1)) * 10, 100.0), 1)
            sdsp       = round(replies   / messages * 100, 1)
            cho        = round(reactions / messages * 100, 1)
            media_idx  = round(media_cnt / messages * 100, 1)
            korp       = round((replies + reactions) / messages * 100, 1)
            kopyup     = round((joined - left) / max(total_users, 1) * 100, 1)

            indices = {"oksp": oksp, "sdsp": sdsp, "cho": cho,
                       "media": media_idx, "korp": korp, "kopyup": kopyup}
            health = round(min(
                oksp * 0.25 + sdsp * 0.15 + cho * 0.15 +
                media_idx * 0.10 + korp * 0.20 + max(0, kopyup) * 0.15,
                100.0
            ), 1)
        except Exception as _he:
            logger.warning(f"health indices: {_he}")

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
        "healthIndex":  health,
        "indices":      indices,
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
        ws['A2'] = f"Экспорт: {_now_msk().strftime('%d.%m.%Y %H:%M')}"
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

        fname = f"pulse_stats_{period}_{_now_msk().strftime('%Y%m%d_%H%M')}.xlsx"
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
        today = _today_msk().isoformat()

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
        pulse_rate = db.get_setting('pulse_rate', '1.42') if db else "1.42"
        return {
            "pulseRate":   float(pulse_rate),
            "difficultyK": 5.0,
            "admins":      ["@vitya_owner", "@alex_admin"],
            "blacklist":   []
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


@app.patch("/api/triggers/{trigger_id}/toggle")
async def toggle_trigger(trigger_id: int):
    """Переключить активность триггера"""
    try:
        db.cursor.execute("SELECT is_enabled FROM triggers WHERE id=?", (trigger_id,))
        row = db.cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Trigger not found")
        new_val = 0 if row[0] else 1
        db.cursor.execute("UPDATE triggers SET is_enabled=? WHERE id=?", (new_val, trigger_id))
        db.conn.commit()
        return {'id': trigger_id, 'is_enabled': bool(new_val)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/triggers/{trigger_id}/copy")
async def copy_trigger(trigger_id: int):
    """Копировать триггер (создаёт выключенную копию)"""
    try:
        db.cursor.execute("SELECT * FROM triggers WHERE id=?", (trigger_id,))
        row = db.cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Trigger not found")
        r = dict(row)
        db.cursor.execute('''
            INSERT INTO triggers
                (name, keywords, condition, action, action_value, probability,
                 where_fires, initiator, bot_msg_delete, bot_msg_delete_after,
                 action_configs, is_enabled)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,0)
        ''', (
            r['name'] + ' (копия)',
            r.get('keywords', ''), r.get('condition', 'contains'),
            r.get('action', 'send_text'), r.get('action_value', ''),
            r.get('probability', 100), r.get('where_fires', 'chat'),
            r.get('initiator', 'all'), r.get('bot_msg_delete', 'no'),
            r.get('bot_msg_delete_after', 60), r.get('action_configs', '{}'),
        ))
        db.conn.commit()
        return {'id': db.cursor.lastrowid, 'success': True}
    except HTTPException:
        raise
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


# --- АВТООБНОВЛЕНИЯ ---

AI_UPDATES_FILE = 'ai_updates.json'
DEPLOY_SECRET   = os.environ.get('DEPLOY_SECRET', 'pulse-deploy-secret')

def _load_ai_updates() -> list:
    try:
        if os.path.exists(AI_UPDATES_FILE):
            with open(AI_UPDATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_ai_updates(data: list):
    with open(AI_UPDATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.get("/api/updates")
async def get_updates():
    """Список AI-сгенерированных заметок об обновлениях"""
    return _load_ai_updates()

@app.delete("/api/updates/{update_id}")
async def delete_update(update_id: int):
    """Удалить запись об обновлении"""
    updates = _load_ai_updates()
    new_list = [u for u in updates if u.get('id') != update_id]
    if len(new_list) == len(updates):
        raise HTTPException(status_code=404, detail="Not found")
    _save_ai_updates(new_list)
    return {"ok": True}

class DeployEvent(BaseModel):
    commit_message: str
    secret: str

@app.post("/api/updates/generate")
async def generate_update(event: DeployEvent):
    """Вызывается после деплоя — генерирует user-friendly заметку через Gemini"""
    if event.secret != DEPLOY_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not GEMINI_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY не задан")

    # Определяем версию из коммита (feat(V1.11) → V1.11, feat(V1.11.0a) → V1.11.0a)
    ver_match = re.search(r'V[\d]+\.[\d]+(?:\.[\d]+)?[a-z]?', event.commit_message)
    version = ver_match.group(0) if ver_match else ''

    # Определяем тег по ключевым словам
    msg_lower = event.commit_message.lower()
    if any(w in msg_lower for w in ['сайт', 'site', 'панел', 'dashboard', 'ui']):
        tag = 'site'
    elif any(w in msg_lower for w in ['триггер', 'trigger']):
        tag = 'triggers'
    elif any(w in msg_lower for w in ['журнал', 'journal']):
        tag = 'journal'
    elif any(w in msg_lower for w in ['статист', 'stat']):
        tag = 'statistics'
    else:
        tag = 'bot'

    # Определяем тип (fix/feat/improve)
    if event.commit_message.startswith('fix'):
        upd_type = 'fix'
    elif event.commit_message.startswith('feat'):
        upd_type = 'new'
    else:
        upd_type = 'improve'

    prompt = f"""Ты пишешь краткие заметки об обновлениях для Telegram-бота и веб-панели управления чатом "PULSE 4ever 18+".

Техническое описание коммита: "{event.commit_message}"

Напиши 2-4 коротких пункта на русском языке, понятных обычному пользователю (без технических терминов).
Каждый пункт начинай с одного из слов: «Добавлено», «Исправлено», «Улучшено» или «Теперь».
ВАЖНО: не используй markdown-разметку, звёздочки **, решётки # и другие спецсимволы.
Верни ТОЛЬКО список пунктов, каждый на новой строке, без заголовков и нумерации."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GEMINI_URL}?key={GEMINI_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}]}
            )
            try:
                data = resp.json()
            except Exception:
                logger.error(f"Gemini non-JSON response {resp.status_code}: {resp.text[:500]}")
                raise HTTPException(status_code=502, detail=f"Gemini вернул не-JSON (HTTP {resp.status_code})")
            if resp.status_code != 200:
                err_msg = (data.get('error') or {}).get('message') or f"HTTP {resp.status_code}"
                logger.error(f"Gemini API error: {err_msg} | raw: {str(data)[:300]}")
                raise HTTPException(status_code=502, detail=f"Gemini: {err_msg}")

        candidates = data.get('candidates') or []
        if not candidates:
            block = (data.get('promptFeedback') or {}).get('blockReason', 'пустой ответ')
            logger.error(f"Gemini без candidates: {str(data)[:300]}")
            raise HTTPException(status_code=502, detail=f"Gemini не ответил: {block}")
        try:
            raw = candidates[0]['content']['parts'][0]['text']
        except (KeyError, IndexError, TypeError) as pe:
            logger.error(f"Gemini parse error {pe}: {str(candidates[0])[:300]}")
            raise HTTPException(status_code=502, detail=f"Неожиданная структура ответа Gemini")
        # Убираем markdown: **, *, #, _ и т.д.
        raw = re.sub(r'\*{1,2}|_{1,2}|#{1,3}', '', raw)
        lines = [re.sub(r'^[-•\d.]+\s*', '', l).strip() for l in raw.split('\n') if l.strip()]

        # Определяем тип каждой строки по первому слову
        def _line_type(line: str) -> str:
            l = line.lower()
            if l.startswith('исправл'):
                return 'fix'
            elif l.startswith('улучш'):
                return 'improve'
            else:
                return 'new'  # «Добавлено», «Теперь» и всё остальное

        items = [{"type": _line_type(l), "text": l, "tag": tag} for l in lines]

        # Очищаем заголовок: убираем «feat(V1.11):» и лишние пробелы
        clean_title = re.sub(r'^(?:feat|fix|improve|chore|docs|refactor)\([^)]+\):\s*', '', event.commit_message).strip()

        entry = {
            "id":          int(_now_msk().timestamp()),
            "date":        _now_msk().strftime('%d.%m.%Y'),
            "version":     version,
            "title":       clean_title[:100],
            "tag":         tag,
            "type":        upd_type,
            "items":       items,
            "aiGenerated": True,
        }
        updates = [entry] + _load_ai_updates()
        _save_ai_updates(updates[:50])
        return entry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"generate_update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── УПРАВЛЕНИЕ ФУНКЦИЯМИ ───────────────────────────────────────────────────

FEATURES_LIST = [
    {'id': 'shipper',       'name': '💘 Шиппер (Рулетка пар)'},
    {'id': 'profile',       'name': '👤 Личный кабинет (Профиль)'},
    {'id': 'statistics',    'name': '📊 Статистика'},
    {'id': 'top',           'name': '🏆 ТОП-5 и команды'},
    {'id': 'bank',          'name': '🏦 Центробанк'},
    {'id': 'activities',    'name': '🎯 Активности'},
    {'id': 'detalization',  'name': '📋 Детализация'},
    {'id': 'lottery',       'name': '🎰 Лотерея'},
    {'id': 'bingo',         'name': '🎱 Бинго'},
    {'id': 'referral',      'name': '👥 Рефералы'},
    {'id': 'donate',        'name': '🎁 Донаты'},
    {'id': 'monthly_gift',  'name': '🎁 Подарок Месяца'},
    {'id': 'horoscope',     'name': '🔮 Гороскоп'},
    {'id': 'bbs',           'name': '❣️ Pulse BBS'},
    {'id': 'bbs_other',     'name': '📦 BBS: Другое'},
    {'id': 'bbs_edit',      'name': '✏️ Редактирование анкет BBS'},
    {'id': 'registration',  'name': '📝 Регистрация новых участников'},
]

def _get_feature_enabled(feature_id: str) -> bool:
    if not db:
        return False
    if feature_id == 'shipper':
        return db.get_setting('shipper_enabled', '0') == '1'
    return db.is_feature_enabled(feature_id)

def _set_feature_enabled(feature_id: str, enabled: bool):
    val = '1' if enabled else '0'
    db.set_setting(f'feature_{feature_id}', val)
    if feature_id == 'top':
        db.set_setting('feature_top_commands', val)
    if feature_id == 'shipper':
        db.set_setting('shipper_enabled', val)

@app.get("/api/features")
async def get_features():
    """Список функций бота с их состоянием вкл/выкл"""
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    result = []
    for f in FEATURES_LIST:
        result.append({**f, 'enabled': _get_feature_enabled(f['id'])})
    return result

@app.post("/api/features/{feature_id}/toggle")
async def toggle_feature_api(feature_id: str):
    """Переключить функцию вкл/выкл"""
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    if not any(f['id'] == feature_id for f in FEATURES_LIST):
        raise HTTPException(status_code=404, detail="Unknown feature")
    current = _get_feature_enabled(feature_id)
    _set_feature_enabled(feature_id, not current)
    return {'id': feature_id, 'enabled': not current}


# ─────────────── STAFF (администраторы) ────────────────

class StaffAddRequest(BaseModel):
    user_id: str  # принимаем строку — может быть числом или @username


@app.get("/api/staff")
async def get_staff():
    """Список владельца и всех администраторов"""
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        conn = db.get_connection()
        rows = conn.execute(
            "SELECT user_id, username, first_name, is_owner, is_admin "
            "FROM users WHERE is_admin = 1 OR is_owner = 1 "
            "ORDER BY is_owner DESC, first_name"
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "user_id":    r["user_id"],
                "username":   r["username"] or "",
                "first_name": r["first_name"] or "",
                "is_owner":   bool(r["is_owner"]),
                "is_admin":   bool(r["is_admin"]),
            })
        return result
    except Exception as e:
        logger.error(f"get_staff error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/staff")
async def add_staff(req: StaffAddRequest):
    """Назначить пользователя администратором по user_id или @username"""
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        conn = db.get_connection()
        uid_str = req.user_id.strip().lstrip('@')
        # Пробуем найти по числовому ID или по username
        if uid_str.isdigit():
            row = conn.execute(
                "SELECT user_id, username, first_name, is_owner FROM users WHERE user_id = ?",
                (int(uid_str),)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT user_id, username, first_name, is_owner FROM users "
                "WHERE lower(username) = lower(?)", (uid_str,)
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден в базе")
        if row["is_owner"]:
            raise HTTPException(status_code=400, detail="Нельзя изменить права Владельца")
        conn.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (row["user_id"],))
        conn.commit()
        return {"ok": True, "user_id": row["user_id"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"add_staff error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/staff/{user_id}")
async def remove_staff(user_id: int):
    """Снять права администратора"""
    if not db:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        conn = db.get_connection()
        row = conn.execute(
            "SELECT is_owner FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if row["is_owner"]:
            raise HTTPException(status_code=400, detail="Нельзя снять права Владельца")
        conn.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"remove_staff error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- ЗАПУСК ---
if __name__ == "__main__":
    # Запуск uvicorn напрямую. reload=True включен для удобства разработки.
    uvicorn.run(app, host="0.0.0.0", port=8000)