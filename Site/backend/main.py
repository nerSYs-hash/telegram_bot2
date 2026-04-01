"""
Pulse Chat — Backend (FastAPI + WebSocket)
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os, sys, json, sqlite3, uuid, secrets

# ── Import db_bridge ──
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db_bridge

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ══════════════════════════════════════════════
# DATABASE: Таблицы для сайта (рядом с базой бота)
# ══════════════════════════════════════════════

SITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pulse_site.db')

def get_site_db():
    conn = sqlite3.connect(SITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_site_db():
    """Create site-specific tables"""
    conn = get_site_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS site_chats (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id INTEGER,
            is_group INTEGER DEFAULT 1,
            avatar_color TEXT DEFAULT '#7bc862',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS site_messages (
            id TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL,
            from_id INTEGER NOT NULL,
            from_name TEXT,
            text TEXT NOT NULL,
            reply_to TEXT,
            edited INTEGER DEFAULT 0,
            ts INTEGER NOT NULL,
            FOREIGN KEY (chat_id) REFERENCES site_chats(id)
        );
        
        CREATE TABLE IF NOT EXISTS site_topics (
            id TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES site_chats(id)
        );
        
        /* ═══ ADMIN TABLES ═══ */
        
        CREATE TABLE IF NOT EXISTS site_members (
            chat_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'member',  /* owner, admin, moderator, member */
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, user_id)
        );
        
        CREATE TABLE IF NOT EXISTS site_mutes (
            chat_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            muted_by INTEGER,
            reason TEXT,
            until_ts INTEGER,  /* Unix timestamp, NULL = permanent */
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, user_id)
        );
        
        CREATE TABLE IF NOT EXISTS site_bans (
            chat_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            banned_by INTEGER,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, user_id)
        );
        
        CREATE TABLE IF NOT EXISTS site_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            admin_id INTEGER,
            action TEXT,  /* mute, unmute, ban, kick, delete_msg, pin, create_topic, delete_topic, set_role */
            target_id INTEGER,
            details TEXT,
            ts INTEGER
        );
        
        CREATE INDEX IF NOT EXISTS idx_msg_chat ON site_messages(chat_id);
        CREATE INDEX IF NOT EXISTS idx_msg_ts ON site_messages(ts);
        CREATE INDEX IF NOT EXISTS idx_topics_chat ON site_topics(chat_id);
        CREATE INDEX IF NOT EXISTS idx_members_chat ON site_members(chat_id);
        CREATE INDEX IF NOT EXISTS idx_mutes_chat ON site_mutes(chat_id);
        CREATE INDEX IF NOT EXISTS idx_audit ON site_audit_log(chat_id, ts);
        
        /* ═══ INVITE LINKS ═══ */
        CREATE TABLE IF NOT EXISTS site_invites (
            code TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL,
            created_by INTEGER,
            uses INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 0,  /* 0 = unlimited */
            expires_at INTEGER,          /* Unix ts, NULL = never */
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES site_chats(id)
        );
        CREATE INDEX IF NOT EXISTS idx_invites_chat ON site_invites(chat_id);
    """);
    conn.commit()
    conn.close()
    print("✅ Site DB initialized (with admin tables)")

init_site_db()

# Create uploads directory
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Migrate: add media columns if missing
def _migrate_media_columns():
    conn = get_site_db()
    for col in ['media_url', 'media_type', 'media_name']:
        try: conn.execute(f"ALTER TABLE site_messages ADD COLUMN {col} TEXT")
        except: pass
    conn.commit()
    conn.close()
_migrate_media_columns()

# ══════════════════════════════════════════════
# WEBSOCKET: Connection Manager
# ══════════════════════════════════════════════

class ConnectionManager:
    def __init__(self):
        # chat_id -> list of (ws, user_id, user_name)
        self.rooms: dict[str, list] = {}
        # user_id -> ws (global registry for direct messages / calls)
        self.users: dict[int, WebSocket] = {}

    async def connect(self, ws: WebSocket, chat_id: str, user_id: int, user_name: str):
        await ws.accept()
        if chat_id not in self.rooms:
            self.rooms[chat_id] = []
        self.rooms[chat_id].append((ws, user_id, user_name))
        self.users[user_id] = ws  # Track globally
        print(f"🔗 WS: {user_name} joined {chat_id} ({len(self.rooms[chat_id])} online)")

    def disconnect(self, ws: WebSocket, chat_id: str):
        if chat_id in self.rooms:
            self.rooms[chat_id] = [(w, u, n) for w, u, n in self.rooms[chat_id] if w != ws]
            if not self.rooms[chat_id]:
                del self.rooms[chat_id]
        # Remove from global user registry
        self.users = {k: v for k, v in self.users.items() if v != ws}

    async def broadcast(self, chat_id: str, message: dict, exclude_user: int = None):
        if chat_id not in self.rooms:
            return
        dead = []
        for ws, uid, uname in self.rooms[chat_id]:
            if exclude_user and uid == exclude_user:
                continue
            try:
                await ws.send_json(message)
            except:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, chat_id)

    async def send_to_user(self, user_id: int, message: dict):
        """Send a message directly to a specific user (for calls)"""
        ws = self.users.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
                return True
            except:
                del self.users[user_id]
        return False

manager = ConnectionManager()

# ══════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════

class AuthData(BaseModel):
    id: int
    first_name: str = ''
    last_name: str = ''
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: Optional[int] = None
    hash: Optional[str] = None

class CreateChatData(BaseModel):
    owner_id: int
    name: str
    is_group: bool = True

class SendMessageData(BaseModel):
    user_id: int
    text: str
    reply_to: Optional[str] = None
    forwarded_from: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    media_name: Optional[str] = None

class CreateTopicData(BaseModel):
    chat_id: str
    title: str
    created_by: int = 0

class DeleteMessageData(BaseModel):
    user_id: int

class CreateInviteData(BaseModel):
    chat_id: str
    user_id: int
    max_uses: int = 0       # 0 = unlimited
    expires_hours: int = 0  # 0 = never

class JoinInviteData(BaseModel):
    user_id: int

# ══════════════════════════════════════════════
# Telegram Auth: Верификация хеша
# ══════════════════════════════════════════════

def verify_telegram_auth(data: dict, bot_token: str) -> bool:
    """Проверяем что данные реально пришли от Telegram"""
    import hashlib, hmac
    check_hash = data.get('hash', '')
    if not check_hash:
        return False
    filtered = {k: v for k, v in data.items() if k != 'hash' and v is not None}
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(filtered.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return calculated == check_hash

# Автоматически читаем BOT_TOKEN из .env бота
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
if not BOT_TOKEN:
    env_path = os.path.join('/root/economybot', '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('BOT_TOKEN='):
                    BOT_TOKEN = line.split('=', 1)[1].strip()
                    break
        if BOT_TOKEN:
            print(f"✅ BOT_TOKEN загружен из .env бота")
        else:
            print("⚠️ BOT_TOKEN не найден")

# ══════════════════════════════════════════════
# API: Auth
# ══════════════════════════════════════════════

@app.post("/api/auth/telegram")
async def auth_telegram(data: AuthData):
    print(f"👉 Вход ID: {data.id}, username: {data.username}")
    
    # Верифицируем хеш (если пришёл от Telegram виджета)
    if data.hash and BOT_TOKEN:
        data_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        if not verify_telegram_auth(data_dict, BOT_TOKEN):
            return {"status": "error", "detail": "Невалидный хеш Telegram"}
        import time
        if data.auth_date and (time.time() - data.auth_date) > 86400:
            return {"status": "error", "detail": "Авторизация устарела"}
    
    # Ищем в базе бота
    user = db_bridge.get_user_data(data.id)
    if user:
        return {
            "status": "success", "is_new": False,
            "user": {
                "id": user['user_id'],
                "username": user['username'] or user.get('first_name', data.first_name),
                "balance": user['balance'],
                "is_admin": bool(user.get('is_admin', False))
            }
        }
    return {
        "status": "success", "is_new": True,
        "user": {"id": data.id, "username": data.username or data.first_name or f"User_{data.id}", "balance": 0, "is_admin": False}
    }

# ══════════════════════════════════════════════
# API: Chats
# ══════════════════════════════════════════════

@app.get("/api/chats")
async def get_chats(user_id: int):
    conn = get_site_db()
    
    # System chats (always present)
    # Get last bot message
    bot_last = conn.execute(
        "SELECT text, ts FROM site_messages WHERE chat_id = 'pulse_bot' ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    
    result = [
        {
            "id": "pulse_bot", "name": "Pulse AI Bot", "is_bot": True,
            "avatar_color": "#0088cc",
            "last_msg": bot_last['text'][:50] if bot_last else "Напиши /help для начала",
            "last_msg_ts": bot_last['ts'] if bot_last else None,
            "online": True, "unread": 0
        },
    ]
    
    # User-created chats from DB
    rows = conn.execute("SELECT * FROM site_chats ORDER BY created_at DESC").fetchall()
    for row in rows:
        # Get last message with timestamp and sender
        last_msg_row = conn.execute(
            "SELECT text, ts, from_name FROM site_messages WHERE chat_id = ? ORDER BY ts DESC LIMIT 1",
            (row['id'],)
        ).fetchone()
        
        # Also check messages in topics of this chat
        if not last_msg_row and bool(row['is_group']):
            last_msg_row = conn.execute("""
                SELECT m.text, m.ts, m.from_name FROM site_messages m
                JOIN site_topics t ON m.chat_id = t.id
                WHERE t.chat_id = ? ORDER BY m.ts DESC LIMIT 1
            """, (row['id'],)).fetchone()
        
        last_msg = last_msg_row['text'] if last_msg_row else "Нет сообщений"
        last_msg_ts = last_msg_row['ts'] if last_msg_row else None
        last_msg_sender = last_msg_row['from_name'] if last_msg_row else None
        
        # Count unread (simplified)
        unread = conn.execute(
            "SELECT COUNT(*) as c FROM site_messages WHERE chat_id = ? AND from_id != ?",
            (row['id'], user_id)
        ).fetchone()['c']
        
        # Check if user is a member
        is_member = conn.execute(
            "SELECT 1 FROM site_members WHERE chat_id = ? AND user_id = ?",
            (row['id'], user_id)
        ).fetchone()
        is_owner = row['owner_id'] == user_id
        
        result.append({
            "id": row['id'],
            "name": row['name'],
            "is_group": bool(row['is_group']),
            "avatar_color": row['avatar_color'],
            "last_msg": last_msg[:60],
            "last_msg_ts": last_msg_ts,
            "last_msg_sender": last_msg_sender,
            "online": False,
            "unread": min(unread, 99),
            "is_member": bool(is_member or is_owner),
        })
    
    conn.close()
    return result

@app.post("/api/chats/create")
async def create_chat(data: CreateChatData):
    chat_id = f"group_{uuid.uuid4().hex[:8]}"
    colors = ['#e17076','#eda86c','#a695e7','#7bc862','#6ec9cb','#65aadd','#ee7aae']
    color = colors[hash(data.name) % len(colors)]
    
    conn = get_site_db()
    conn.execute(
        "INSERT INTO site_chats (id, name, owner_id, is_group, avatar_color) VALUES (?,?,?,?,?)",
        (chat_id, data.name, data.owner_id, int(data.is_group), color)
    )
    
    # Add welcome message
    msg_id = f"sys_{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO site_messages (id, chat_id, from_id, from_name, text, ts) VALUES (?,?,?,?,?,?)",
        (msg_id, chat_id, 0, "Система", f"Группа «{data.name}» создана!", int(datetime.now().timestamp() * 1000))
    )
    
    # Add creator as owner in members
    conn.execute(
        "INSERT OR IGNORE INTO site_members (chat_id, user_id, role) VALUES (?,?,?)",
        (chat_id, data.owner_id, 'owner')
    )
    
    # Auto-add owner as member with role 'owner'
    conn.execute(
        "INSERT OR IGNORE INTO site_members (chat_id, user_id, role) VALUES (?,?,?)",
        (chat_id, data.owner_id, 'owner')
    )
    
    conn.commit()
    conn.close()
    
    print(f"📁 Создано сообщество: {data.name}")
    return {
        "status": "success",
        "chat": {"id": chat_id, "name": data.name, "is_group": True, "avatar_color": color}
    }

# ══════════════════════════════════════════════
# (Old invite endpoints removed — see /api/invites/ section below)
# ══════════════════════════════════════════════

# ══════════════════════════════════════════════
# API: Messages
# ══════════════════════════════════════════════

@app.get("/api/messages/{chat_id}")
async def get_messages(chat_id: str, user_id: int, limit: int = 100):
    conn = get_site_db()
    
    # Ensure forwarded_from column exists
    try: conn.execute("ALTER TABLE site_messages ADD COLUMN forwarded_from TEXT")
    except: pass
    
    rows = conn.execute(
        "SELECT * FROM site_messages WHERE chat_id = ? ORDER BY ts ASC LIMIT ?",
        (chat_id, limit)
    ).fetchall()
    
    # Load reactions
    conn.execute("""CREATE TABLE IF NOT EXISTS site_reactions (
        msg_id TEXT, user_id INTEGER, emoji TEXT, PRIMARY KEY (msg_id, user_id, emoji))""")
    
    # Load pinned
    conn.execute("""CREATE TABLE IF NOT EXISTS site_pins (chat_id TEXT PRIMARY KEY, msg_id TEXT)""")
    pin_row = conn.execute("SELECT msg_id FROM site_pins WHERE chat_id = ?", (chat_id,)).fetchone()
    
    messages = []
    for row in rows:
        # Get reactions for this message
        reacts_raw = conn.execute("SELECT emoji, user_id FROM site_reactions WHERE msg_id = ?", (row['id'],)).fetchall()
        reactions = {}
        for r in reacts_raw:
            if r['emoji'] not in reactions: reactions[r['emoji']] = []
            reactions[r['emoji']].append(str(r['user_id']))
        
        messages.append({
            "id": row['id'],
            "from_id": row['from_id'],
            "from_name": row['from_name'] or "Аноним",
            "text": row['text'],
            "ts": row['ts'],
            "reply_to": row['reply_to'],
            "edited": bool(row['edited']),
            "status": "delivered",
            "reactions": reactions,
            "forwarded_from": row['forwarded_from'] if 'forwarded_from' in row.keys() else None,
            "media_url": row['media_url'] if 'media_url' in row.keys() else None,
            "media_type": row['media_type'] if 'media_type' in row.keys() else None,
            "media_name": row['media_name'] if 'media_name' in row.keys() else None,
        })
    
    # Find pinned message
    pinned = None
    if pin_row:
        pm = next((m for m in messages if m['id'] == pin_row['msg_id']), None)
        if pm: pinned = pm
    
    conn.close()
    return {"messages": messages, "pinned": pinned}

@app.post("/api/messages/{chat_id}/send")
async def send_message(chat_id: str, data: SendMessageData):
    # Check mute/ban
    conn = get_site_db()
    if is_user_muted(conn, chat_id, data.user_id):
        conn.close()
        return {"status": "error", "detail": "Вы замучены в этом чате"}
    banned = conn.execute("SELECT 1 FROM site_bans WHERE chat_id = ? AND user_id = ?", (chat_id, data.user_id)).fetchone()
    if banned:
        conn.close()
        return {"status": "error", "detail": "Вы заблокированы в этом чате"}
    conn.close()
    
    msg_id = f"msg_{uuid.uuid4().hex[:8]}"
    ts = int(datetime.now().timestamp() * 1000)
    
    # Get sender name from bot DB
    user = db_bridge.get_user_data(data.user_id)
    from_name = (user['username'] or user['first_name']) if user else f"User_{data.user_id}"
    
    # Media fields (optional)
    media_url = data.media_url if hasattr(data, 'media_url') else None
    media_type = data.media_type if hasattr(data, 'media_type') else None
    media_name = data.media_name if hasattr(data, 'media_name') else None
    
    conn = get_site_db()
    try: conn.execute("ALTER TABLE site_messages ADD COLUMN forwarded_from TEXT")
    except: pass
    conn.execute(
        "INSERT INTO site_messages (id, chat_id, from_id, from_name, text, reply_to, forwarded_from, media_url, media_type, media_name, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (msg_id, chat_id, data.user_id, from_name, data.text, data.reply_to, data.forwarded_from, media_url, media_type, media_name, ts)
    )
    conn.commit()
    conn.close()
    
    msg_payload = {
        "type": "message", "id": msg_id, "chat_id": chat_id,
        "from_id": data.user_id, "from_name": from_name,
        "text": data.text, "ts": ts, "reply_to": data.reply_to,
        "forwarded_from": data.forwarded_from, "reactions": {},
        "media_url": media_url, "media_type": media_type, "media_name": media_name,
    }
    
    await manager.broadcast(chat_id, msg_payload, exclude_user=data.user_id)
    
    # ═══ BOT REPLY (if sending to pulse_bot) ═══
    bot_reply_payload = None
    if chat_id == 'pulse_bot':
        try:
            bot_text = await _generate_bot_reply(data.user_id, data.text)
            if bot_text:
                bot_msg_id = f"bot_{uuid.uuid4().hex[:8]}"
                bot_ts = int(datetime.now().timestamp() * 1000) + 1
                conn = get_site_db()
                conn.execute(
                    "INSERT INTO site_messages (id, chat_id, from_id, from_name, text, ts) VALUES (?,?,?,?,?,?)",
                    (bot_msg_id, chat_id, 0, 'Pulse AI Bot', bot_text, bot_ts)
                )
                conn.commit()
                conn.close()
                bot_reply_payload = {
                    "id": bot_msg_id, "from_id": 0, "from_name": "Pulse AI Bot",
                    "text": bot_text, "ts": bot_ts, "reactions": {},
                }
                print(f"🤖 Bot reply to '{data.text[:30]}': {bot_text[:50]}...")
        except Exception as e:
            print(f"❌ Bot reply error: {e}")
            import traceback
            traceback.print_exc()
    
    return {
        "status": "success",
        "message": msg_payload,
        "bot_reply": bot_reply_payload,
    }


# ══════════════════════════════════════════════
# BOT: Command Handler
# ══════════════════════════════════════════════

async def _generate_bot_reply(user_id: int, text: str) -> str:
    """Process bot commands and return reply text"""
    import random
    cmd = text.strip().lower()
    
    try:
        user = db_bridge.get_user_data(user_id)
    except:
        user = None
    user_name = (user.get('username') or user.get('first_name')) if user else f"User_{user_id}"
    
    # /start, /help
    if cmd in ('/start', '/help', '/помощь', 'помощь', 'помоги', 'help'):
        return (
            f"👋 Привет, {user_name}!\n\n"
            "Я — Pulse AI Bot. Вот что я умею:\n\n"
            "💰 /баланс — проверить баланс\n"
            "🏆 /топ — топ-5 богачей\n"
            "📊 /стат — твоя статистика\n"
            "💱 /курс — курс Пульса\n"
            "🎰 /лотерея — информация о лотерее\n"
            "🎲 /кубик — бросить кубик\n"
            "🪙 /бонус — ежедневный бонус\n"
            "❓ /help — эта справка"
        )
    
    # /balance
    if cmd in ('/balance', '/bal', '/баланс', 'баланс', 'balance'):
        if user:
            bal = user.get('balance', 0)
            return f"💰 Баланс {user_name}: {int(bal):,} 💎 Пульсов".replace(',', ' ')
        return "❌ Пользователь не найден в базе. Зарегистрируйтесь через Telegram-бота."
    
    # /top
    if cmd in ('/top', '/top5', '/топ', 'топ', 'top', 'богач', 'богачи', 'рейтинг'):
        try:
            rows = db_bridge.db.cursor.execute(
                "SELECT username, first_name, balance FROM users ORDER BY balance DESC LIMIT 5"
            ).fetchall()
            if not rows:
                return "📊 Пока нет данных для топа."
            
            medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
            lines = ["🏆 ТОП-5 богачей Pulse:\n"]
            for i, r in enumerate(rows):
                name = r['username'] or r['first_name'] or '???'
                bal = int(r['balance'])
                lines.append(f"{medals[i]} {name} — {bal:,} 💎".replace(',', ' '))
            return '\n'.join(lines)
        except Exception as e:
            print(f"Bot /top error: {e}")
            return "❌ Ошибка загрузки топа. Попробуйте позже."
    
    # /stats
    if cmd in ('/stats', '/stat', '/стат', '/статистика', 'статистика', 'стат', 'stats'):
        try:
            conn = get_site_db()
            msg_count = conn.execute(
                "SELECT COUNT(*) as c FROM site_messages WHERE from_id = ?", (user_id,)
            ).fetchone()['c']
            groups = conn.execute(
                "SELECT COUNT(*) as c FROM site_members WHERE user_id = ?", (user_id,)
            ).fetchone()['c']
            conn.close()
            
            bal = int(user['balance']) if user else 0
            return (
                f"📊 Статистика {user_name}:\n\n"
                f"💎 Баланс: {bal:,}\n"
                f"💬 Сообщений: {msg_count}\n"
                f"👥 Групп: {groups}"
            ).replace(',', ' ')
        except Exception as e:
            print(f"Bot /stats error: {e}")
            return "❌ Ошибка загрузки статистики."
    
    # /rate
    if cmd in ('/rate', '/курс', 'курс', 'rate'):
        try:
            rate = db_bridge.db.get_exchange_rate()
            return f"💱 Курс Пульса: 1 💎 = {rate:.2f} ₽"
        except:
            return "💱 Курс Пульса: 1 💎 = 1.00 ₽ (стандартный)"
    
    # /lottery
    if cmd in ('/lottery', '/лотерея', 'лотерея', 'lottery'):
        try:
            conn = get_site_db()
            conn.execute("CREATE TABLE IF NOT EXISTS site_lottery (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tickets INTEGER DEFAULT 1, purchased_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            total = conn.execute("SELECT COALESCE(SUM(tickets),0) as t FROM site_lottery").fetchone()['t']
            players = conn.execute("SELECT COUNT(DISTINCT user_id) as c FROM site_lottery").fetchone()['c']
            my = conn.execute("SELECT COALESCE(SUM(tickets),0) as t FROM site_lottery WHERE user_id = ?", (user_id,)).fetchone()['t']
            jackpot = total * 100
            conn.close()
        except:
            jackpot, players, my = 0, 0, 0
        
        return (
            f"🎰 Лотерея Pulse\n\n"
            f"💰 Джекпот: {jackpot:,} 💎\n"
            f"👥 Участников: {players}\n"
            f"🎫 Ваших билетов: {my}\n\n"
            "Купить билеты → меню → Лотерея"
        ).replace(',', ' ')
    
    # /dice
    if cmd in ('/dice', '/кубик', 'кубик', 'dice', '🎲'):
        dice = random.randint(1, 6)
        emoji_dice = ['⚀','⚁','⚂','⚃','⚄','⚅']
        bonus = dice * 5
        if user:
            try:
                db_bridge.db.cursor.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, user_id)
                )
                db_bridge.db.conn.commit()
            except: pass
        return f"🎲 Выпало: {emoji_dice[dice-1]} ({dice})\n💎 Бонус: +{bonus} Пульсов!"
    
    # /daily
    if cmd in ('/daily', '/бонус', '/ежедневный', 'бонус', 'daily'):
        import time as time_mod
        try:
            conn = get_site_db()
            conn.execute("CREATE TABLE IF NOT EXISTS site_daily (user_id INTEGER PRIMARY KEY, last_ts INTEGER)")
            row = conn.execute("SELECT last_ts FROM site_daily WHERE user_id = ?", (user_id,)).fetchone()
            now = int(time_mod.time())
            
            if row and (now - row['last_ts']) < 86400:
                remaining = 86400 - (now - row['last_ts'])
                hours = remaining // 3600
                mins = (remaining % 3600) // 60
                conn.close()
                return f"⏰ Бонус уже получен!\nСледующий через {hours}ч {mins}мин."
            
            bonus = random.randint(50, 200)
            conn.execute("INSERT OR REPLACE INTO site_daily (user_id, last_ts) VALUES (?, ?)", (user_id, now))
            conn.commit()
            conn.close()
            
            if user:
                try:
                    db_bridge.db.cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, user_id))
                    db_bridge.db.conn.commit()
                except: pass
            
            return f"🎁 Ежедневный бонус: +{bonus} 💎!\nПриходите завтра за новым."
        except Exception as e:
            print(f"Bot /daily error: {e}")
            return "❌ Ошибка ежедневного бонуса."
    
    # Active users (custom command for "активисты")
    if cmd in ('активисты', 'актив', '/актив', '/активисты'):
        try:
            conn = get_site_db()
            rows = conn.execute("""
                SELECT from_name, COUNT(*) as c FROM site_messages 
                WHERE from_id > 0 GROUP BY from_id ORDER BY c DESC LIMIT 5
            """).fetchall()
            conn.close()
            if not rows:
                return "📊 Пока нет активных пользователей."
            medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
            lines = ["⚡ ТОП-5 активистов Pulse:\n"]
            for i, r in enumerate(rows):
                lines.append(f"{medals[i]} {r['from_name'] or '???'} — {r['c']} сообщ.")
            return '\n'.join(lines)
        except:
            return "❌ Ошибка загрузки."
    
    # Unknown slash command
    if cmd.startswith('/'):
        return f"❓ Неизвестная команда: {cmd}\nНапиши /help для списка команд."
    
    # Casual conversation
    greetings = ['привет', 'здравствуй', 'хай', 'hi', 'hello', 'ку', 'здарова', 'йо', 'хей']
    if any(g in cmd for g in greetings):
        return f"👋 Привет, {user_name}! Напиши /help чтобы узнать мои команды."
    
    thanks = ['спасибо', 'спс', 'thanks', 'благодарю', 'thx']
    if any(t in cmd for t in thanks):
        return "🤗 Всегда рад помочь!"
    
    # Default — always reply with something helpful
    return f"🤔 Не понял: «{text[:40]}»\nНапиши /help для списка команд."

# ══════════════════════════════════════════════
# API: File Upload
# ══════════════════════════════════════════════

ALLOWED_EXTENSIONS = {'.jpg','.jpeg','.png','.gif','.webp','.svg','.mp4','.webm','.pdf','.doc','.docx','.xls','.xlsx','.zip','.rar','.txt','.mp3','.ogg','.wav'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), user_id: int = Form(0)):
    """Upload a file and return its URL"""
    if not file.filename:
        return {"status": "error", "detail": "Нет файла"}
    
    # Check extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"status": "error", "detail": f"Формат {ext} не поддерживается"}
    
    # Read file
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return {"status": "error", "detail": "Файл слишком большой (макс. 20MB)"}
    
    # Generate unique filename
    unique_name = f"{uuid.uuid4().hex[:12]}{ext}"
    filepath = os.path.join(UPLOADS_DIR, unique_name)
    
    with open(filepath, 'wb') as f:
        f.write(content)
    
    # Determine media type
    image_exts = {'.jpg','.jpeg','.png','.gif','.webp','.svg'}
    video_exts = {'.mp4','.webm'}
    audio_exts = {'.mp3','.ogg','.wav'}
    
    if ext in image_exts:
        media_type = 'image'
    elif ext in video_exts:
        media_type = 'video'
    elif ext in audio_exts:
        media_type = 'audio'
    else:
        media_type = 'file'
    
    # Override: .webm/.ogg from voice recorder = 'voice'
    # (frontend sends media_type='voice' in the message, but upload just returns file type)
    
    url = f"/uploads/{unique_name}"
    print(f"📎 Upload: {file.filename} → {url} ({len(content)} bytes)")
    
    return {
        "status": "success",
        "url": url,
        "media_type": media_type,
        "original_name": file.filename,
        "size": len(content),
    }

@app.post("/api/messages/{msg_id}/delete")
async def delete_message(msg_id: str, data: DeleteMessageData):
    conn = get_site_db()
    conn.execute("DELETE FROM site_messages WHERE id = ? AND from_id = ?", (msg_id, data.user_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

class EditMessageData(BaseModel):
    user_id: int
    text: str

@app.post("/api/messages/{msg_id}/edit")
async def edit_message(msg_id: str, data: EditMessageData):
    conn = get_site_db()
    conn.execute(
        "UPDATE site_messages SET text = ?, edited = 1 WHERE id = ? AND from_id = ?",
        (data.text, msg_id, data.user_id)
    )
    conn.commit()
    row = conn.execute("SELECT chat_id FROM site_messages WHERE id = ?", (msg_id,)).fetchone()
    conn.close()
    if row:
        await manager.broadcast(row['chat_id'], {"type":"edit","id":msg_id,"text":data.text}, exclude_user=data.user_id)
    return {"status": "success"}

# ── Reactions ──
class ReactionData(BaseModel):
    user_id: int
    emoji: str

@app.post("/api/messages/{msg_id}/react")
async def react_to_message(msg_id: str, data: ReactionData):
    conn = get_site_db()
    # Create reactions table if not exists
    conn.execute("""CREATE TABLE IF NOT EXISTS site_reactions (
        msg_id TEXT, user_id INTEGER, emoji TEXT,
        PRIMARY KEY (msg_id, user_id, emoji)
    )""")
    # Toggle: if exists delete, else insert
    existing = conn.execute("SELECT 1 FROM site_reactions WHERE msg_id=? AND user_id=? AND emoji=?",
        (msg_id, data.user_id, data.emoji)).fetchone()
    if existing:
        conn.execute("DELETE FROM site_reactions WHERE msg_id=? AND user_id=? AND emoji=?",
            (msg_id, data.user_id, data.emoji))
    else:
        conn.execute("INSERT INTO site_reactions (msg_id, user_id, emoji) VALUES (?,?,?)",
            (msg_id, data.user_id, data.emoji))
    conn.commit()
    conn.close()
    return {"status": "success"}

# ── Pin / Unpin ──
class PinData(BaseModel):
    chat_id: str
    user_id: int = 0

@app.post("/api/messages/{msg_id}/pin")
async def pin_message(msg_id: str, data: PinData):
    conn = get_site_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS site_pins (
        chat_id TEXT PRIMARY KEY, msg_id TEXT
    )""")
    conn.execute("INSERT OR REPLACE INTO site_pins (chat_id, msg_id) VALUES (?,?)",
        (data.chat_id, msg_id))
    
    # Get message text for broadcast
    msg_row = conn.execute("SELECT text, from_name FROM site_messages WHERE id = ?", (msg_id,)).fetchone()
    conn.commit()
    conn.close()
    
    # Broadcast pin to all in chat
    await manager.broadcast(data.chat_id, {
        "type": "pin",
        "msg_id": msg_id,
        "text": msg_row['text'] if msg_row else '',
        "from_name": msg_row['from_name'] if msg_row else '',
    })
    
    # Audit log
    _log_audit(data.chat_id, data.user_id, 'pin', 0, msg_id)
    
    return {"status": "success"}

@app.post("/api/messages/unpin")
async def unpin_message(data: PinData):
    conn = get_site_db()
    conn.execute("DELETE FROM site_pins WHERE chat_id = ?", (data.chat_id,))
    conn.commit()
    conn.close()
    
    # Broadcast unpin
    await manager.broadcast(data.chat_id, {"type": "unpin"})
    
    return {"status": "success"}

def _log_audit(chat_id, admin_id, action, target_id, details):
    """Helper to log admin actions"""
    try:
        import time as time_mod
        conn = get_site_db()
        conn.execute(
            "INSERT INTO site_audit_log (chat_id, admin_id, action, target_id, details, ts) VALUES (?,?,?,?,?,?)",
            (chat_id, admin_id, action, target_id, details, int(time_mod.time() * 1000))
        )
        conn.commit()
        conn.close()
    except: pass

# ══════════════════════════════════════════════
# API: Topics (ветки внутри группы)
# ══════════════════════════════════════════════

@app.get("/api/topics/{chat_id}")
async def get_topics(chat_id: str):
    conn = get_site_db()
    rows = conn.execute(
        "SELECT * FROM site_topics WHERE chat_id = ? ORDER BY created_at ASC", (chat_id,)
    ).fetchall()
    
    result = []
    for r in rows:
        # Count messages in this topic (topic_id is used as chat_id for messages)
        msg_count = conn.execute(
            "SELECT COUNT(*) as c FROM site_messages WHERE chat_id = ?", (r['id'],)
        ).fetchone()['c']
        
        # Get last message
        last_msg_row = conn.execute(
            "SELECT text, from_name FROM site_messages WHERE chat_id = ? ORDER BY ts DESC LIMIT 1",
            (r['id'],)
        ).fetchone()
        last_msg = f"{last_msg_row['from_name']}: {last_msg_row['text'][:40]}" if last_msg_row else None
        
        result.append({
            "id": r['id'],
            "title": r['title'],
            "created_by": r['created_by'],
            "msg_count": msg_count,
            "last_msg": last_msg,
        })
    
    conn.close()
    return result

@app.post("/api/topics/create")
async def create_topic(data: CreateTopicData):
    topic_id = f"topic_{uuid.uuid4().hex[:8]}"
    conn = get_site_db()
    conn.execute(
        "INSERT INTO site_topics (id, chat_id, title, created_by) VALUES (?,?,?,?)",
        (topic_id, data.chat_id, data.title, data.created_by)
    )
    conn.commit()
    conn.close()
    print(f"📑 Topic created: {data.title} in {data.chat_id}")
    return {"status": "success", "topic_id": topic_id, "title": data.title}

# ══════════════════════════════════════════════
# API: Profile (реальные данные из БД бота + сайта)
# ══════════════════════════════════════════════

@app.get("/api/profile/{user_id}")
async def get_profile(user_id: int):
    """Full user profile with stats"""
    user = db_bridge.get_user_data(user_id)
    
    # Base data
    profile = {
        "user_id": user_id,
        "name": "Пользователь",
        "username": None,
        "first_name": None,
        "photo_url": None,
        "balance": 0,
        "is_admin": False,
        "registered_at": None,
        "msg_count": 0,
        "groups_count": 0,
        "status": "",
    }
    
    if user:
        profile["name"] = user.get('username') or user.get('first_name') or f"User_{user_id}"
        profile["username"] = user.get('username')
        profile["first_name"] = user.get('first_name')
        profile["balance"] = user.get('balance', 0)
        profile["is_admin"] = bool(user.get('is_admin', False))
        profile["registered_at"] = user.get('created_at') or user.get('join_date')
        profile["photo_url"] = user.get('photo_url')
    
    # Message count from site DB
    conn = get_site_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM site_messages WHERE from_id = ?",
            (user_id,)
        ).fetchone()
        profile["msg_count"] = row['c'] if row else 0
    except:
        pass
    
    # Groups count
    try:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM site_members WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        owned = conn.execute(
            "SELECT COUNT(*) as c FROM site_chats WHERE owner_id = ?",
            (user_id,)
        ).fetchone()
        profile["groups_count"] = (row['c'] if row else 0) + (owned['c'] if owned else 0)
    except:
        pass
    
    # Custom status
    try:
        status_row = conn.execute(
            "SELECT value FROM site_user_settings WHERE user_id = ? AND key = 'status'",
            (user_id,)
        ).fetchone()
        if status_row:
            profile["status"] = status_row['value']
    except:
        pass  # Table may not exist yet
    
    conn.close()
    return profile

class UpdateStatusData(BaseModel):
    user_id: int
    status: str

@app.post("/api/profile/status")
async def update_status(data: UpdateStatusData):
    """Update user status"""
    conn = get_site_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_user_settings (
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            PRIMARY KEY (user_id, key)
        )
    """)
    conn.execute(
        "INSERT OR REPLACE INTO site_user_settings (user_id, key, value) VALUES (?, 'status', ?)",
        (data.user_id, data.status[:100])  # Limit 100 chars
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

# ══════════════════════════════════════════════
# API: Search
# ══════════════════════════════════════════════

@app.get("/api/search")
async def search_all(q: str):
    results = []
    try:
        users = db_bridge.db.cursor.execute(
            "SELECT user_id, username, first_name FROM users WHERE username LIKE ? OR first_name LIKE ? LIMIT 5",
            (f"%{q}%", f"%{q}%")
        ).fetchall()
        for u in users:
            results.append({
                "type": "user", "id": str(u['user_id']),
                "name": u['username'] or u['first_name'],
                "sub": "Пользователь Pulse", "avatar_color": "var(--accent)"
            })
    except Exception as e:
        print(f"Search error: {e}")
    return results

# ══════════════════════════════════════════════
# ADMIN: Helper functions
# ══════════════════════════════════════════════

def get_user_role(conn, chat_id: str, user_id: int) -> str:
    """Get user's role in a chat: owner/admin/moderator/member"""
    # Check if chat owner
    chat = conn.execute("SELECT owner_id FROM site_chats WHERE id = ?", (chat_id,)).fetchone()
    if chat and chat['owner_id'] == user_id:
        return 'owner'
    # Check site_members table
    row = conn.execute("SELECT role FROM site_members WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)).fetchone()
    if row:
        return row['role']
    # Check bot DB for admin status
    bot_user = db_bridge.get_user_data(user_id)
    if bot_user and bot_user.get('is_admin'):
        return 'admin'
    return 'member'

def can_moderate(role: str) -> bool:
    return role in ('owner', 'admin', 'moderator')

def is_user_muted(conn, chat_id: str, user_id: int) -> bool:
    import time
    row = conn.execute("SELECT until_ts FROM site_mutes WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)).fetchone()
    if not row:
        return False
    if row['until_ts'] is None:
        return True  # permanent
    return row['until_ts'] > int(time.time())

def log_admin_action(conn, chat_id, admin_id, action, target_id=None, details=None):
    import time
    conn.execute("INSERT INTO site_audit_log (chat_id, admin_id, action, target_id, details, ts) VALUES (?,?,?,?,?,?)",
        (chat_id, admin_id, action, target_id, details, int(time.time() * 1000)))

# ══════════════════════════════════════════════
# API: Admin — Role Management
# ══════════════════════════════════════════════

class SetRoleData(BaseModel):
    admin_id: int
    target_id: int
    role: str  # admin, moderator, member

@app.post("/api/admin/{chat_id}/set-role")
async def set_role(chat_id: str, data: SetRoleData):
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, data.admin_id)
    if admin_role != 'owner':
        conn.close()
        return {"status": "error", "detail": "Только владелец может менять роли"}
    if data.role not in ('admin', 'moderator', 'member'):
        conn.close()
        return {"status": "error", "detail": "Неизвестная роль"}
    conn.execute("INSERT OR REPLACE INTO site_members (chat_id, user_id, role) VALUES (?,?,?)",
        (chat_id, data.target_id, data.role))
    log_admin_action(conn, chat_id, data.admin_id, 'set_role', data.target_id, data.role)
    conn.commit()
    conn.close()
    return {"status": "success", "role": data.role}

@app.get("/api/admin/{chat_id}/members")
async def get_members(chat_id: str, admin_id: int):
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, admin_id)
    if not can_moderate(admin_role):
        conn.close()
        return {"status": "error", "detail": "Нет прав"}
    # Get all who sent messages in this chat + members table
    members_db = conn.execute("""
        SELECT DISTINCT from_id as user_id, from_name as name FROM site_messages WHERE chat_id = ?
        UNION
        SELECT user_id, NULL as name FROM site_members WHERE chat_id = ?
    """, (chat_id, chat_id)).fetchall()
    
    result = []
    for m in members_db:
        uid = m['user_id']
        if uid == 0: continue  # system messages
        role = get_user_role(conn, chat_id, uid)
        muted = is_user_muted(conn, chat_id, uid)
        # Try to get name from bot DB
        bot_user = db_bridge.get_user_data(uid)
        name = (bot_user['username'] or bot_user.get('first_name', '')) if bot_user else (m['name'] or f'User_{uid}')
        online = uid in [u for _, u, _ in manager.rooms.get(chat_id, [])]
        result.append({"id": uid, "name": name, "role": role, "muted": muted, "online": online})
    
    # Deduplicate by id
    seen = set()
    unique = []
    for m in result:
        if m['id'] not in seen:
            seen.add(m['id'])
            unique.append(m)
    
    conn.close()
    return {"status": "success", "members": unique, "your_role": admin_role}

# ══════════════════════════════════════════════
# API: Admin — Mute / Unmute
# ══════════════════════════════════════════════

class MuteData(BaseModel):
    admin_id: int
    target_id: int
    duration: int = 0  # seconds, 0 = permanent
    reason: str = ''

@app.post("/api/admin/{chat_id}/mute")
async def mute_user(chat_id: str, data: MuteData):
    import time
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, data.admin_id)
    if not can_moderate(admin_role):
        conn.close()
        return {"status": "error", "detail": "Нет прав для мута"}
    target_role = get_user_role(conn, chat_id, data.target_id)
    if target_role in ('owner', 'admin') and admin_role != 'owner':
        conn.close()
        return {"status": "error", "detail": "Нельзя мутить админа"}
    
    until_ts = None if data.duration == 0 else int(time.time()) + data.duration
    conn.execute("INSERT OR REPLACE INTO site_mutes (chat_id, user_id, muted_by, reason, until_ts) VALUES (?,?,?,?,?)",
        (chat_id, data.target_id, data.admin_id, data.reason, until_ts))
    log_admin_action(conn, chat_id, data.admin_id, 'mute', data.target_id, f"{data.duration}s: {data.reason}")
    conn.commit()
    conn.close()
    
    # Notify via WS
    await manager.broadcast(chat_id, {"type": "system", "text": f"🔇 Пользователь замучен", "target_id": data.target_id})
    return {"status": "success"}

@app.post("/api/admin/{chat_id}/unmute")
async def unmute_user(chat_id: str, data: MuteData):
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, data.admin_id)
    if not can_moderate(admin_role):
        conn.close()
        return {"status": "error", "detail": "Нет прав"}
    conn.execute("DELETE FROM site_mutes WHERE chat_id = ? AND user_id = ?", (chat_id, data.target_id))
    log_admin_action(conn, chat_id, data.admin_id, 'unmute', data.target_id)
    conn.commit()
    conn.close()
    return {"status": "success"}

# ══════════════════════════════════════════════
# API: Admin — Ban / Kick
# ══════════════════════════════════════════════

class BanData(BaseModel):
    admin_id: int
    target_id: int
    reason: str = ''

@app.post("/api/admin/{chat_id}/ban")
async def ban_user(chat_id: str, data: BanData):
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, data.admin_id)
    if not can_moderate(admin_role):
        conn.close()
        return {"status": "error", "detail": "Нет прав"}
    target_role = get_user_role(conn, chat_id, data.target_id)
    if target_role in ('owner', 'admin') and admin_role != 'owner':
        conn.close()
        return {"status": "error", "detail": "Нельзя банить админа"}
    conn.execute("INSERT OR REPLACE INTO site_bans (chat_id, user_id, banned_by, reason) VALUES (?,?,?,?)",
        (chat_id, data.target_id, data.admin_id, data.reason))
    log_admin_action(conn, chat_id, data.admin_id, 'ban', data.target_id, data.reason)
    conn.commit()
    conn.close()
    await manager.broadcast(chat_id, {"type": "system", "text": f"⛔ Пользователь заблокирован"})
    return {"status": "success"}

@app.post("/api/admin/{chat_id}/unban")
async def unban_user(chat_id: str, data: BanData):
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, data.admin_id)
    if not can_moderate(admin_role):
        conn.close()
        return {"status": "error", "detail": "Нет прав"}
    conn.execute("DELETE FROM site_bans WHERE chat_id = ? AND user_id = ?", (chat_id, data.target_id))
    log_admin_action(conn, chat_id, data.admin_id, 'unban', data.target_id)
    conn.commit()
    conn.close()
    return {"status": "success"}

# ══════════════════════════════════════════════
# API: Admin — Delete messages (bulk)
# ══════════════════════════════════════════════

class BulkDeleteData(BaseModel):
    admin_id: int
    message_ids: list[str] = []
    from_user_id: int = 0  # Delete all from this user if set

@app.post("/api/admin/{chat_id}/delete-messages")
async def admin_delete_messages(chat_id: str, data: BulkDeleteData):
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, data.admin_id)
    if not can_moderate(admin_role):
        conn.close()
        return {"status": "error", "detail": "Нет прав"}
    
    deleted = 0
    if data.from_user_id:
        r = conn.execute("DELETE FROM site_messages WHERE chat_id = ? AND from_id = ?", (chat_id, data.from_user_id))
        deleted = r.rowcount
    elif data.message_ids:
        for mid in data.message_ids:
            conn.execute("DELETE FROM site_messages WHERE id = ? AND chat_id = ?", (mid, chat_id))
            deleted += 1
    
    log_admin_action(conn, chat_id, data.admin_id, 'delete_msg', data.from_user_id, f"Deleted {deleted} msgs")
    conn.commit()
    conn.close()
    return {"status": "success", "deleted": deleted}

# ══════════════════════════════════════════════
# API: Admin — Manage Topics (rename, delete, reorder)
# ══════════════════════════════════════════════

class AdminTopicData(BaseModel):
    admin_id: int
    title: str = ''

@app.post("/api/admin/topics/{topic_id}/rename")
async def rename_topic(topic_id: str, data: AdminTopicData):
    conn = get_site_db()
    topic = conn.execute("SELECT chat_id FROM site_topics WHERE id = ?", (topic_id,)).fetchone()
    if not topic:
        conn.close()
        return {"status": "error", "detail": "Ветка не найдена"}
    admin_role = get_user_role(conn, topic['chat_id'], data.admin_id)
    if not can_moderate(admin_role):
        conn.close()
        return {"status": "error", "detail": "Нет прав"}
    conn.execute("UPDATE site_topics SET title = ? WHERE id = ?", (data.title, topic_id))
    log_admin_action(conn, topic['chat_id'], data.admin_id, 'rename_topic', details=f"{topic_id}: {data.title}")
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/admin/topics/{topic_id}/delete")
async def delete_topic(topic_id: str, data: AdminTopicData):
    conn = get_site_db()
    topic = conn.execute("SELECT chat_id FROM site_topics WHERE id = ?", (topic_id,)).fetchone()
    if not topic:
        conn.close()
        return {"status": "error", "detail": "Ветка не найдена"}
    admin_role = get_user_role(conn, topic['chat_id'], data.admin_id)
    if not can_moderate(admin_role):
        conn.close()
        return {"status": "error", "detail": "Нет прав"}
    # Delete topic and its messages
    conn.execute("DELETE FROM site_messages WHERE chat_id = ?", (topic_id,))
    conn.execute("DELETE FROM site_topics WHERE id = ?", (topic_id,))
    log_admin_action(conn, topic['chat_id'], data.admin_id, 'delete_topic', details=topic_id)
    conn.commit()
    conn.close()
    return {"status": "success"}

# ══════════════════════════════════════════════
# API: Admin — Chat Settings
# ══════════════════════════════════════════════

class ChatSettingsData(BaseModel):
    admin_id: int
    name: str = ''

@app.post("/api/admin/{chat_id}/rename")
async def rename_chat(chat_id: str, data: ChatSettingsData):
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, data.admin_id)
    if admin_role != 'owner':
        conn.close()
        return {"status": "error", "detail": "Только владелец может переименовать"}
    conn.execute("UPDATE site_chats SET name = ? WHERE id = ?", (data.name, chat_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/admin/{chat_id}/delete")
async def delete_chat(chat_id: str, data: ChatSettingsData):
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, data.admin_id)
    if admin_role != 'owner':
        conn.close()
        return {"status": "error", "detail": "Только владелец может удалить"}
    conn.execute("DELETE FROM site_messages WHERE chat_id IN (SELECT id FROM site_topics WHERE chat_id = ?)", (chat_id,))
    conn.execute("DELETE FROM site_messages WHERE chat_id = ?", (chat_id,))
    conn.execute("DELETE FROM site_topics WHERE chat_id = ?", (chat_id,))
    conn.execute("DELETE FROM site_members WHERE chat_id = ?", (chat_id,))
    conn.execute("DELETE FROM site_mutes WHERE chat_id = ?", (chat_id,))
    conn.execute("DELETE FROM site_bans WHERE chat_id = ?", (chat_id,))
    conn.execute("DELETE FROM site_chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# ══════════════════════════════════════════════
# API: Admin — Audit Log
# ══════════════════════════════════════════════

@app.get("/api/admin/{chat_id}/audit-log")
async def get_audit_log(chat_id: str, admin_id: int, limit: int = 50):
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, admin_id)
    if not can_moderate(admin_role):
        conn.close()
        return {"status": "error", "detail": "Нет прав"}
    rows = conn.execute("SELECT * FROM site_audit_log WHERE chat_id = ? ORDER BY ts DESC LIMIT ?", (chat_id, limit)).fetchall()
    conn.close()
    return [{"id": r['id'], "admin_id": r['admin_id'], "action": r['action'], "target_id": r['target_id'], "details": r['details'], "ts": r['ts']} for r in rows]

# ══════════════════════════════════════════════
# API: Import topics from Telegram bot
# ══════════════════════════════════════════════

@app.post("/api/admin/{chat_id}/import-tg-topics")
async def import_tg_topics(chat_id: str, admin_id: int):
    """Import real topics from Telegram bot's database into a Pulse group"""
    conn = get_site_db()
    admin_role = get_user_role(conn, chat_id, admin_id)
    if admin_role != 'owner':
        conn.close()
        return {"status": "error", "detail": "Только владелец может импортировать"}
    
    try:
        # Read TARGET_CHAT_ID from bot's .env
        target_chat_id = None
        env_path = os.path.join('/root/economybot', '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith('TARGET_CHAT_ID='):
                        target_chat_id = int(line.split('=', 1)[1].strip())
                        break
        
        if not target_chat_id:
            conn.close()
            return {"status": "error", "detail": "TARGET_CHAT_ID не найден в .env бота"}
        
        # Fetch topics from bot's database
        tg_topics = db_bridge.db.get_all_topics(target_chat_id)
        
        if not tg_topics:
            conn.close()
            return {"status": "error", "detail": "Нет топиков в базе бота"}
        
        imported = 0
        for topic in tg_topics:
            thread_name = topic['thread_name']
            if not thread_name:
                continue  # Skip unnamed
            
            topic_id = f"tg_{topic['thread_id']}"
            
            # Check if already imported
            existing = conn.execute("SELECT 1 FROM site_topics WHERE id = ? AND chat_id = ?", (topic_id, chat_id)).fetchone()
            if existing:
                continue
            
            conn.execute(
                "INSERT INTO site_topics (id, chat_id, title, created_by) VALUES (?,?,?,?)",
                (topic_id, chat_id, thread_name, admin_id)
            )
            imported += 1
        
        conn.commit()
        conn.close()
        
        print(f"📥 Imported {imported} topics from TG into {chat_id}")
        return {"status": "success", "imported": imported, "total_in_tg": len(tg_topics)}
    
    except Exception as e:
        conn.close()
        print(f"Import error: {e}")
        return {"status": "error", "detail": str(e)}

# ══════════════════════════════════════════════
# API: Economy (Кошелёк — реальные данные из БД бота)
# ══════════════════════════════════════════════

@app.get("/api/economy/balance")
async def get_balance(user_id: int):
    """Get user balance and recent transactions"""
    user = db_bridge.get_user_data(user_id)
    if not user:
        return {"balance": 0, "transactions": []}
    
    # Get recent transactions from bot DB
    transactions = []
    try:
        rows = db_bridge.db.cursor.execute(
            """SELECT * FROM transactions 
               WHERE user_id = ? OR target_id = ? 
               ORDER BY created_at DESC LIMIT 20""",
            (user_id, user_id)
        ).fetchall()
        for r in rows:
            is_income = (r['target_id'] == user_id) if r.get('target_id') else (r['amount'] > 0)
            transactions.append({
                "id": r['id'] if 'id' in r.keys() else 0,
                "type": r.get('type', 'unknown'),
                "amount": abs(r['amount']) if 'amount' in r.keys() else 0,
                "income": is_income,
                "description": r.get('description', ''),
                "ts": r.get('created_at', ''),
            })
    except Exception as e:
        print(f"Transactions query: {e}")
        # Try alternative table structure
        try:
            rows = db_bridge.db.cursor.execute(
                "SELECT * FROM economy_log WHERE user_id = ? ORDER BY rowid DESC LIMIT 20",
                (user_id,)
            ).fetchall()
            for r in rows:
                transactions.append({
                    "type": r.get('action', 'unknown'),
                    "amount": abs(r.get('amount', 0)),
                    "income": r.get('amount', 0) > 0,
                    "description": r.get('description', r.get('action', '')),
                    "ts": r.get('timestamp', r.get('created_at', '')),
                })
        except:
            pass
    
    # Exchange rate
    rate = 1.0
    try:
        rate = db_bridge.db.get_exchange_rate()
    except:
        pass
    
    return {
        "balance": user.get('balance', 0),
        "rate": rate,
        "transactions": transactions
    }

@app.get("/api/economy/rate")
async def get_rate():
    """Get current exchange rate"""
    try:
        rate = db_bridge.db.get_exchange_rate()
        return {"rate": rate}
    except:
        return {"rate": 1.0}

class TransferData(BaseModel):
    from_id: int
    to_id: int
    amount: float

@app.post("/api/economy/transfer")
async def transfer_pulses(data: TransferData):
    """Transfer pulses between users"""
    if data.amount <= 0:
        return {"status": "error", "detail": "Сумма должна быть больше 0"}
    
    sender = db_bridge.get_user_data(data.from_id)
    if not sender:
        return {"status": "error", "detail": "Отправитель не найден"}
    if sender['balance'] < data.amount:
        return {"status": "error", "detail": f"Недостаточно средств. Баланс: {sender['balance']:.0f} 💎"}
    
    receiver = db_bridge.get_user_data(data.to_id)
    if not receiver:
        return {"status": "error", "detail": "Получатель не найден"}
    
    try:
        # Update balances
        db_bridge.db.cursor.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (data.amount, data.from_id)
        )
        db_bridge.db.cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (data.amount, data.to_id)
        )
        db_bridge.db.conn.commit()
        
        new_balance = sender['balance'] - data.amount
        recv_name = receiver['username'] or receiver['first_name'] or f"User_{data.to_id}"
        return {
            "status": "success",
            "new_balance": new_balance,
            "receiver_name": recv_name
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# ══════════════════════════════════════════════
# API: TOP-5 (реальные данные)
# ══════════════════════════════════════════════

AVATAR_COLORS = ['#e17076','#7bc862','#e5ca77','#65aadd','#a695e7','#ee7aae','#6ec9cb','#faa774']

@app.get("/api/top/rich")
async def get_top_rich(limit: int = 10):
    """Top users by balance"""
    try:
        rows = db_bridge.db.cursor.execute(
            "SELECT user_id, username, first_name, balance FROM users ORDER BY balance DESC LIMIT ?",
            (limit,)
        ).fetchall()
        result = []
        for i, r in enumerate(rows):
            name = r['username'] or r['first_name'] or f"User_{r['user_id']}"
            result.append({
                "rank": i + 1,
                "user_id": r['user_id'],
                "name": name,
                "initials": name[:2].upper(),
                "value": r['balance'],
                "color": AVATAR_COLORS[r['user_id'] % len(AVATAR_COLORS)],
            })
        return result
    except Exception as e:
        print(f"Top rich error: {e}")
        return []

@app.get("/api/top/active")
async def get_top_active(limit: int = 10):
    """Top users by message count in site chats"""
    conn = get_site_db()
    try:
        rows = conn.execute("""
            SELECT from_id, from_name, COUNT(*) as msg_count
            FROM site_messages
            WHERE from_id > 0
            GROUP BY from_id
            ORDER BY msg_count DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        
        result = []
        for i, r in enumerate(rows):
            # Enrich with bot DB data
            user = db_bridge.get_user_data(r['from_id'])
            name = r['from_name'] or (user['username'] if user else f"User_{r['from_id']}")
            result.append({
                "rank": i + 1,
                "user_id": r['from_id'],
                "name": name,
                "initials": name[:2].upper(),
                "value": r['msg_count'],
                "color": AVATAR_COLORS[r['from_id'] % len(AVATAR_COLORS)],
            })
        return result
    except Exception as e:
        conn.close()
        print(f"Top active error: {e}")
        return []

# ══════════════════════════════════════════════
# API: Lottery
# ══════════════════════════════════════════════

@app.get("/api/lottery/info")
async def get_lottery_info(user_id: int = 0):
    """Get current lottery information"""
    conn = get_site_db()
    
    # Ensure lottery table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_lottery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tickets INTEGER DEFAULT 1,
            purchased_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_lottery_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    
    # Total pool
    total_tickets = conn.execute("SELECT COALESCE(SUM(tickets),0) as t FROM site_lottery").fetchone()['t']
    participants = conn.execute("SELECT COUNT(DISTINCT user_id) as c FROM site_lottery").fetchone()['c']
    
    # Current user's tickets
    my_tickets = 0
    if user_id:
        row = conn.execute("SELECT COALESCE(SUM(tickets),0) as t FROM site_lottery WHERE user_id = ?", (user_id,)).fetchone()
        my_tickets = row['t']
    
    jackpot = total_tickets * 100  # 100 pulses per ticket
    chance = round((my_tickets / total_tickets * 100), 1) if total_tickets > 0 else 0
    
    conn.close()
    return {
        "jackpot": jackpot,
        "total_tickets": total_tickets,
        "participants": participants,
        "my_tickets": my_tickets,
        "chance": chance,
    }

class BuyTicketData(BaseModel):
    user_id: int
    count: int = 1

@app.post("/api/lottery/buy")
async def buy_lottery_ticket(data: BuyTicketData):
    """Buy lottery tickets"""
    cost_per_ticket = 100
    total_cost = data.count * cost_per_ticket
    
    user = db_bridge.get_user_data(data.user_id)
    if not user:
        return {"status": "error", "detail": "Пользователь не найден"}
    if user['balance'] < total_cost:
        return {"status": "error", "detail": f"Недостаточно средств. Нужно {total_cost} 💎, у вас {user['balance']:.0f} 💎"}
    
    # Deduct balance
    try:
        db_bridge.db.cursor.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (total_cost, data.user_id)
        )
        db_bridge.db.conn.commit()
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    
    # Add tickets
    conn = get_site_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_lottery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tickets INTEGER DEFAULT 1,
            purchased_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "INSERT INTO site_lottery (user_id, tickets) VALUES (?, ?)",
        (data.user_id, data.count)
    )
    conn.commit()
    
    new_balance = user['balance'] - total_cost
    my_tickets = conn.execute(
        "SELECT COALESCE(SUM(tickets),0) as t FROM site_lottery WHERE user_id = ?",
        (data.user_id,)
    ).fetchone()['t']
    conn.close()
    
    return {
        "status": "success",
        "tickets_bought": data.count,
        "new_balance": new_balance,
        "total_tickets": my_tickets,
    }

# ══════════════════════════════════════════════
# WEBSOCKET: Real-time (with mute check + online tracking)
# ══════════════════════════════════════════════

@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(ws: WebSocket, chat_id: str, user_id: int = 0):
    user = db_bridge.get_user_data(user_id)
    user_name = (user['username'] or user['first_name']) if user else f"User_{user_id}"
    
    # Check ban
    conn = get_site_db()
    banned = conn.execute("SELECT 1 FROM site_bans WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)).fetchone()
    conn.close()
    if banned:
        await ws.close(code=4003, reason="Вы заблокированы в этом чате")
        return
    
    await manager.connect(ws, chat_id, user_id, user_name)
    
    # Broadcast online status
    await manager.broadcast(chat_id, {"type": "online", "user_id": user_id, "user_name": user_name, "online": True}, exclude_user=user_id)
    
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except:
                continue
            
            if data.get('type') == 'typing':
                await manager.broadcast(chat_id, {
                    "type": "typing", "user_id": user_id, "user_name": user_name,
                }, exclude_user=user_id)
            
            elif data.get('type') == 'ping':
                await ws.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(ws, chat_id)
        await manager.broadcast(chat_id, {"type": "online", "user_id": user_id, "user_name": user_name, "online": False}, exclude_user=user_id)
        print(f"🔌 WS: {user_name} left {chat_id}")

# ══════════════════════════════════════════════
# API: Invite Links (Виральность)
# ══════════════════════════════════════════════

import hashlib, secrets, time as time_mod

@app.post("/api/invites/create")
async def create_invite(data: CreateInviteData):
    """Generate a unique invite link for a group"""
    conn = get_site_db()
    
    # Only owner/admin can create invites
    member = conn.execute(
        "SELECT role FROM site_members WHERE chat_id = ? AND user_id = ?",
        (data.chat_id, data.user_id)
    ).fetchone()
    
    chat = conn.execute("SELECT * FROM site_chats WHERE id = ?", (data.chat_id,)).fetchone()
    is_owner = chat and chat['owner_id'] == data.user_id
    is_admin = member and member['role'] in ('owner', 'admin')
    
    if not (is_owner or is_admin):
        conn.close()
        return {"status": "error", "detail": "Только владелец или админ может создать ссылку"}
    
    # Generate short unique code
    code = secrets.token_urlsafe(8)  # ~11 chars, URL-safe
    
    expires_at = None
    if data.expires_hours > 0:
        expires_at = int(time_mod.time()) + (data.expires_hours * 3600)
    
    conn.execute(
        "INSERT INTO site_invites (code, chat_id, created_by, max_uses, expires_at) VALUES (?,?,?,?,?)",
        (code, data.chat_id, data.user_id, data.max_uses, expires_at)
    )
    conn.commit()
    conn.close()
    
    print(f"🔗 Invite created: {code} → {data.chat_id}")
    return {
        "status": "success",
        "code": code,
        "max_uses": data.max_uses,
        "expires_at": expires_at,
    }


@app.get("/api/invites/{code}")
async def get_invite_info(code: str):
    """Get info about an invite link (for the join page)"""
    conn = get_site_db()
    
    invite = conn.execute("SELECT * FROM site_invites WHERE code = ?", (code,)).fetchone()
    if not invite:
        conn.close()
        return {"status": "error", "detail": "Ссылка недействительна"}
    
    # Check expiry
    if invite['expires_at'] and int(time_mod.time()) > invite['expires_at']:
        conn.close()
        return {"status": "error", "detail": "Ссылка истекла"}
    
    # Check max uses
    if invite['max_uses'] > 0 and invite['uses'] >= invite['max_uses']:
        conn.close()
        return {"status": "error", "detail": "Лимит использований исчерпан"}
    
    # Get chat info
    chat = conn.execute("SELECT * FROM site_chats WHERE id = ?", (invite['chat_id'],)).fetchone()
    if not chat:
        conn.close()
        return {"status": "error", "detail": "Группа не найдена"}
    
    # Count members
    member_count = conn.execute(
        "SELECT COUNT(*) as c FROM site_members WHERE chat_id = ?",
        (invite['chat_id'],)
    ).fetchone()['c']
    
    conn.close()
    return {
        "status": "ok",
        "chat_id": invite['chat_id'],
        "chat_name": chat['name'],
        "avatar_color": chat['avatar_color'],
        "member_count": member_count,
        "uses": invite['uses'],
        "max_uses": invite['max_uses'],
    }


@app.post("/api/invites/{code}/join")
async def join_via_invite(code: str, data: JoinInviteData):
    """Join a group via invite link"""
    conn = get_site_db()
    
    invite = conn.execute("SELECT * FROM site_invites WHERE code = ?", (code,)).fetchone()
    if not invite:
        conn.close()
        return {"status": "error", "detail": "Ссылка недействительна"}
    
    # Check expiry
    if invite['expires_at'] and int(time_mod.time()) > invite['expires_at']:
        conn.close()
        return {"status": "error", "detail": "Ссылка истекла"}
    
    # Check max uses
    if invite['max_uses'] > 0 and invite['uses'] >= invite['max_uses']:
        conn.close()
        return {"status": "error", "detail": "Лимит исчерпан"}
    
    chat_id = invite['chat_id']
    
    # Check if already a member
    existing = conn.execute(
        "SELECT 1 FROM site_members WHERE chat_id = ? AND user_id = ?",
        (chat_id, data.user_id)
    ).fetchone()
    
    chat = conn.execute("SELECT * FROM site_chats WHERE id = ?", (chat_id,)).fetchone()
    is_owner = chat and chat['owner_id'] == data.user_id
    
    if existing or is_owner:
        conn.close()
        return {
            "status": "already_member",
            "chat_id": chat_id,
            "chat_name": chat['name'] if chat else "Группа"
        }
    
    # Check ban
    banned = conn.execute(
        "SELECT 1 FROM site_bans WHERE chat_id = ? AND user_id = ?",
        (chat_id, data.user_id)
    ).fetchone()
    if banned:
        conn.close()
        return {"status": "error", "detail": "Вы заблокированы в этой группе"}
    
    # Add as member
    conn.execute(
        "INSERT INTO site_members (chat_id, user_id, role) VALUES (?,?,?)",
        (chat_id, data.user_id, 'member')
    )
    
    # Increment uses
    conn.execute("UPDATE site_invites SET uses = uses + 1 WHERE code = ?", (code,))
    
    # Add system message
    user = db_bridge.get_user_data(data.user_id)
    user_name = (user['username'] or user.get('first_name', '')) if user else f"User_{data.user_id}"
    
    msg_id = f"sys_{uuid.uuid4().hex[:8]}"
    ts = int(datetime.now().timestamp() * 1000)
    conn.execute(
        "INSERT INTO site_messages (id, chat_id, from_id, from_name, text, ts) VALUES (?,?,?,?,?,?)",
        (msg_id, chat_id, 0, "Система", f"👋 {user_name} вступил(а) в группу", ts)
    )
    
    # Audit log
    conn.execute(
        "INSERT INTO site_audit_log (chat_id, admin_id, action, target_id, details, ts) VALUES (?,?,?,?,?,?)",
        (chat_id, data.user_id, 'join', data.user_id, f'via invite {code}', ts)
    )
    
    conn.commit()
    conn.close()
    
    print(f"✅ {user_name} joined {chat_id} via invite {code}")
    return {
        "status": "joined",
        "chat_id": chat_id,
        "chat_name": chat['name'] if chat else "Группа"
    }


@app.get("/api/invites/chat/{chat_id}")
async def list_chat_invites(chat_id: str, user_id: int):
    """List all active invites for a group (for admins)"""
    conn = get_site_db()
    rows = conn.execute(
        "SELECT * FROM site_invites WHERE chat_id = ? ORDER BY created_at DESC",
        (chat_id,)
    ).fetchall()
    
    now = int(time_mod.time())
    invites = []
    for row in rows:
        expired = row['expires_at'] and now > row['expires_at']
        exhausted = row['max_uses'] > 0 and row['uses'] >= row['max_uses']
        if expired or exhausted:
            continue
        invites.append({
            "code": row['code'],
            "uses": row['uses'],
            "max_uses": row['max_uses'],
            "expires_at": row['expires_at'],
            "created_at": row['created_at'],
        })
    
    conn.close()
    return invites


# ══════════════════════════════════════════════
# API: Polls (Опросы)
# ══════════════════════════════════════════════

def _init_polls_tables():
    conn = get_site_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS site_polls (
            id TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL,
            question TEXT NOT NULL,
            created_by INTEGER,
            anonymous INTEGER DEFAULT 1,
            multiple INTEGER DEFAULT 0,
            closed INTEGER DEFAULT 0,
            ts INTEGER
        );
        CREATE TABLE IF NOT EXISTS site_poll_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id TEXT NOT NULL,
            text TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS site_poll_votes (
            poll_id TEXT NOT NULL,
            option_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (poll_id, option_id, user_id)
        );
    """)
    conn.commit()
    conn.close()
_init_polls_tables()

class CreatePollData(BaseModel):
    chat_id: str
    user_id: int
    question: str
    options: list  # list of strings
    anonymous: bool = True
    multiple: bool = False

@app.post("/api/polls/create")
async def create_poll(data: CreatePollData):
    if len(data.options) < 2:
        return {"status": "error", "detail": "Минимум 2 варианта"}
    if len(data.options) > 10:
        return {"status": "error", "detail": "Максимум 10 вариантов"}
    
    poll_id = f"poll_{uuid.uuid4().hex[:8]}"
    ts = int(datetime.now().timestamp() * 1000)
    
    conn = get_site_db()
    conn.execute(
        "INSERT INTO site_polls (id, chat_id, question, created_by, anonymous, multiple, ts) VALUES (?,?,?,?,?,?,?)",
        (poll_id, data.chat_id, data.question, data.user_id, int(data.anonymous), int(data.multiple), ts)
    )
    for i, opt_text in enumerate(data.options):
        conn.execute(
            "INSERT INTO site_poll_options (poll_id, text, sort_order) VALUES (?,?,?)",
            (poll_id, opt_text.strip(), i)
        )
    conn.commit()
    
    # Also create a message for the poll
    user = db_bridge.get_user_data(data.user_id)
    from_name = (user['username'] or user['first_name']) if user else f"User_{data.user_id}"
    msg_id = f"msg_{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO site_messages (id, chat_id, from_id, from_name, text, media_type, media_url, ts) VALUES (?,?,?,?,?,?,?,?)",
        (msg_id, data.chat_id, data.user_id, from_name, f"📊 {data.question}", 'poll', poll_id, ts)
    )
    conn.commit()
    conn.close()
    
    msg_payload = {
        "type": "message", "id": msg_id, "chat_id": data.chat_id,
        "from_id": data.user_id, "from_name": from_name,
        "text": f"📊 {data.question}", "ts": ts,
        "media_type": "poll", "media_url": poll_id,
        "reactions": {},
    }
    await manager.broadcast(data.chat_id, msg_payload, exclude_user=data.user_id)
    
    return {"status": "success", "poll_id": poll_id, "message": msg_payload}

@app.get("/api/polls/{poll_id}")
async def get_poll(poll_id: str, user_id: int = 0):
    conn = get_site_db()
    poll = conn.execute("SELECT * FROM site_polls WHERE id = ?", (poll_id,)).fetchone()
    if not poll:
        conn.close()
        return {"status": "error", "detail": "Опрос не найден"}
    
    options = conn.execute(
        "SELECT * FROM site_poll_options WHERE poll_id = ? ORDER BY sort_order", (poll_id,)
    ).fetchall()
    
    total_votes = conn.execute(
        "SELECT COUNT(DISTINCT user_id) as c FROM site_poll_votes WHERE poll_id = ?", (poll_id,)
    ).fetchone()['c']
    
    result_options = []
    my_votes = set()
    for opt in options:
        votes = conn.execute(
            "SELECT COUNT(*) as c FROM site_poll_votes WHERE poll_id = ? AND option_id = ?",
            (poll_id, opt['id'])
        ).fetchone()['c']
        
        voted = conn.execute(
            "SELECT 1 FROM site_poll_votes WHERE poll_id = ? AND option_id = ? AND user_id = ?",
            (poll_id, opt['id'], user_id)
        ).fetchone()
        if voted: my_votes.add(opt['id'])
        
        result_options.append({
            "id": opt['id'], "text": opt['text'],
            "votes": votes, "percent": round(votes / max(total_votes, 1) * 100),
        })
    
    conn.close()
    return {
        "id": poll_id, "question": poll['question'],
        "anonymous": bool(poll['anonymous']), "multiple": bool(poll['multiple']),
        "closed": bool(poll['closed']), "total_votes": total_votes,
        "options": result_options, "my_votes": list(my_votes),
    }

class VotePollData(BaseModel):
    user_id: int
    option_id: int

@app.post("/api/polls/{poll_id}/vote")
async def vote_poll(poll_id: str, data: VotePollData):
    conn = get_site_db()
    poll = conn.execute("SELECT * FROM site_polls WHERE id = ?", (poll_id,)).fetchone()
    if not poll:
        conn.close()
        return {"status": "error", "detail": "Опрос не найден"}
    if poll['closed']:
        conn.close()
        return {"status": "error", "detail": "Опрос завершён"}
    
    # Check if already voted for this option
    existing = conn.execute(
        "SELECT 1 FROM site_poll_votes WHERE poll_id = ? AND option_id = ? AND user_id = ?",
        (poll_id, data.option_id, data.user_id)
    ).fetchone()
    
    if existing:
        # Toggle off (remove vote)
        conn.execute(
            "DELETE FROM site_poll_votes WHERE poll_id = ? AND option_id = ? AND user_id = ?",
            (poll_id, data.option_id, data.user_id)
        )
    else:
        # If not multiple choice, remove previous vote first
        if not poll['multiple']:
            conn.execute(
                "DELETE FROM site_poll_votes WHERE poll_id = ? AND user_id = ?",
                (poll_id, data.user_id)
            )
        conn.execute(
            "INSERT OR IGNORE INTO site_poll_votes (poll_id, option_id, user_id) VALUES (?,?,?)",
            (poll_id, data.option_id, data.user_id)
        )
    
    conn.commit()
    conn.close()
    
    # Broadcast poll update via WebSocket
    await manager.broadcast(poll['chat_id'], {
        "type": "poll_update", "poll_id": poll_id,
    })
    
    return {"status": "success"}

# ══════════════════════════════════════════════
# API: Link Preview (OpenGraph parser)
# ══════════════════════════════════════════════

import re
from urllib.parse import urlparse
import urllib.request

@app.get("/api/link-preview")
async def get_link_preview(url: str):
    """Fetch OpenGraph metadata from a URL"""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {"status": "error"}
        
        # Fetch page with timeout
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 PulseBot/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read(50000).decode('utf-8', errors='ignore')  # Read first 50KB
        
        # Parse OpenGraph tags
        def extract_og(prop):
            match = re.search(rf'<meta[^>]*property=["\']og:{prop}["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
            if not match:
                match = re.search(rf'<meta[^>]*content=["\']([^"\']*)["\'][^>]*property=["\']og:{prop}["\']', html, re.I)
            return match.group(1) if match else None
        
        title = extract_og('title')
        if not title:
            # Fallback to <title>
            m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
            title = m.group(1).strip() if m else parsed.netloc
        
        description = extract_og('description')
        if not description:
            m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
            description = m.group(1) if m else None
        
        image = extract_og('image')
        # Make relative image URLs absolute
        if image and not image.startswith('http'):
            image = f"{parsed.scheme}://{parsed.netloc}{image}"
        
        site_name = extract_og('site_name') or parsed.netloc
        
        return {
            "status": "success",
            "title": (title or '')[:120],
            "description": (description or '')[:200],
            "image": image,
            "site_name": site_name,
            "url": url,
        }
    except Exception as e:
        print(f"Link preview error: {e}")
        return {"status": "error"}

# ══════════════════════════════════════════════
# API: Chat Members (for @mentions autocomplete)
# ══════════════════════════════════════════════

@app.get("/api/members/{chat_id}")
async def get_chat_members(chat_id: str):
    """Get all members for @mention autocomplete"""
    conn = get_site_db()
    
    # Get from site_members
    members = conn.execute("""
        SELECT DISTINCT user_id FROM site_members WHERE chat_id = ?
        UNION
        SELECT owner_id FROM site_chats WHERE id = ?
        UNION
        SELECT DISTINCT from_id FROM site_messages WHERE chat_id = ? AND from_id > 0
    """, (chat_id, chat_id, chat_id)).fetchall()
    
    result = []
    for row in members:
        uid = row['user_id'] if 'user_id' in row.keys() else row[0]
        user = db_bridge.get_user_data(uid)
        if user:
            name = user.get('username') or user.get('first_name') or f"User_{uid}"
            result.append({
                "user_id": uid,
                "name": name,
                "username": user.get('username') or '',
            })
    
    conn.close()
    return result


# ══════════════════════════════════════════════
# API: WebRTC Calls (Signaling)
# ══════════════════════════════════════════════

class CallStartData(BaseModel):
    caller_id: int
    callee_id: int
    video: bool = False

@app.post("/api/call/start")
async def call_start(data: CallStartData):
    """Initiate a call — sends ring event to callee via WS"""
    caller = db_bridge.get_user_data(data.caller_id)
    caller_name = (caller.get('username') or caller.get('first_name')) if caller else f"User_{data.caller_id}"
    
    sent = await manager.send_to_user(data.callee_id, {
        "type": "call_incoming",
        "caller_id": data.caller_id,
        "caller_name": caller_name,
        "video": data.video,
    })
    
    if not sent:
        return {"status": "error", "detail": "Пользователь не в сети"}
    
    print(f"📞 Call: {caller_name} → User_{data.callee_id} ({'video' if data.video else 'audio'})")
    return {"status": "success"}

class CallSignalData(BaseModel):
    from_id: int
    to_id: int
    signal_type: str  # "offer", "answer", "ice", "reject", "end"
    data: Optional[dict] = None

@app.post("/api/call/signal")
async def call_signal(data: CallSignalData):
    """Forward WebRTC signaling data between peers"""
    await manager.send_to_user(data.to_id, {
        "type": "call_signal",
        "signal_type": data.signal_type,
        "from_id": data.from_id,
        "data": data.data,
    })
    return {"status": "success"}


# ══════════════════════════════════════════════
# STATIC: Serve frontend
# ══════════════════════════════════════════════

site_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/uploads", StaticFiles(directory=os.path.join(site_path, "uploads")), name="uploads")
app.mount("/icons", StaticFiles(directory=os.path.join(site_path, "icons")), name="icons")
app.mount("/css", StaticFiles(directory=os.path.join(site_path, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(site_path, "js")), name="js")
app.mount("/api_docs", StaticFiles(directory=os.path.join(site_path, "api")), name="api_docs")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(site_path, "index.html"))

@app.get("/join/{code}")
async def join_page(code: str):
    """SPA: serve index.html, frontend handles the invite code"""
    return FileResponse(os.path.join(site_path, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
