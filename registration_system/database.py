"""
База данных бота Pulse 4ever (aiogram).
Асинхронный доступ через aiosqlite.
"""
import os
import logging
import aiosqlite
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pulse_bot.db')

MSK = timezone(timedelta(hours=3))


# ═══════════════════════════════════════════════════════════════
#  ИНИЦИАЛИЗАЦИЯ
# ═══════════════════════════════════════════════════════════════

async def init_db():
    """Создаёт таблицы и добавляет недостающие колонки (миграции)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                tg_id            INTEGER PRIMARY KEY,
                username         TEXT,
                first_name       TEXT,
                last_name        TEXT,
                role             TEXT DEFAULT 'user',
                status           TEXT DEFAULT 'not_in_chat',
                q_name           TEXT,
                q_age            TEXT,
                q_city           TEXT,
                q_therapy        TEXT,
                invite_link      TEXT,
                invite_message_id INTEGER,
                questionnaire_state TEXT,
                previous_username   TEXT,
                previous_first_name TEXT,
                previous_last_name  TEXT,
                referred_by      INTEGER,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_rejection_reason TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                status      TEXT DEFAULT 'new',
                locked_by   INTEGER,
                locked_until TIMESTAMP,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                reviewed_by INTEGER,
                last_rejection_reason TEXT,
                FOREIGN KEY (user_id) REFERENCES users(tg_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS blacklist (
                tg_id      INTEGER PRIMARY KEY,
                reason     TEXT,
                added_by   INTEGER,
                added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key        TEXT PRIMARY KEY,
                value      TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS journal_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                chat_id    INTEGER,
                event_type TEXT,
                user_id    INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS triggers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT,
                pattern     TEXT,
                action      TEXT,
                enabled     INTEGER DEFAULT 1,
                violations  INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ── Миграции: добавляем колонки если их нет ──
        migrations = [
            ("users", "last_activity_at", "TIMESTAMP"),
            ("users", "last_survey_at",   "TIMESTAMP"),
            ("users", "survey_reason",    "TEXT"),
            ("users", "violations",       "INTEGER DEFAULT 0"),
            ("journal_messages", "event_type", "TEXT"),
        ]
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
            existing_tables = {r[0] for r in await cur.fetchall()}

        for table, col, col_type in migrations:
            if table not in existing_tables:
                continue
            async with db.execute(f"PRAGMA table_info({table})") as cur:
                cols = {r[1] for r in await cur.fetchall()}
            if col not in cols:
                try:
                    await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                    logger.info(f"Migration: added {table}.{col}")
                except Exception as e:
                    logger.warning(f"Migration {table}.{col}: {e}")

        await db.commit()
    logger.info("✅ Database initialized")


# ═══════════════════════════════════════════════════════════════
#  ПОЛЬЗОВАТЕЛИ
# ═══════════════════════════════════════════════════════════════

async def get_user(tg_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM users WHERE tg_id = ?', (tg_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_user_by_username(username: str) -> Optional[Dict]:
    username = username.lstrip('@')
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM users WHERE LOWER(username) = LOWER(?)', (username,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user(tg_id: int, username: str = None, first_name: str = None,
                      last_name: str = None, role: str = 'user') -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''INSERT OR IGNORE INTO users (tg_id, username, first_name, last_name, role)
               VALUES (?, ?, ?, ?, ?)''',
            (tg_id, username, first_name, last_name, role)
        )
        await db.commit()
    return await get_user(tg_id)


async def update_user(tg_id: int, **kwargs) -> None:
    if not kwargs:
        return
    cols = ', '.join(f'{k} = ?' for k in kwargs)
    vals = list(kwargs.values()) + [tg_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f'UPDATE users SET {cols} WHERE tg_id = ?', vals)
        await db.commit()


async def get_inactive_users(days: int = 60) -> List[Dict]:
    cutoff = datetime.now(MSK) - timedelta(days=days)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT * FROM users
               WHERE status = 'in_chat'
                 AND (last_activity_at < ?
                      OR (last_activity_at IS NULL AND created_at < ?))''',
            (cutoff.isoformat(), cutoff.isoformat())
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ═══════════════════════════════════════════════════════════════
#  РОЛИ / ПРАВА
# ═══════════════════════════════════════════════════════════════

async def is_admin(tg_id: int) -> bool:
    user = await get_user(tg_id)
    return bool(user and user.get('role') in ('admin', 'owner'))


async def add_admin(tg_id: int, added_by: int = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (tg_id, role) VALUES (?, 'admin')", (tg_id,)
        )
        await db.execute(
            "UPDATE users SET role = 'admin' WHERE tg_id = ?", (tg_id,)
        )
        await db.commit()


async def remove_admin(tg_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET role = 'user' WHERE tg_id = ? AND role = 'admin'", (tg_id,)
        )
        await db.commit()


async def get_all_admins() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE role IN ('admin', 'owner')"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ═══════════════════════════════════════════════════════════════
#  ЗАЯВКИ
# ═══════════════════════════════════════════════════════════════

async def create_application(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO applications (user_id, status) VALUES (?, 'new')", (user_id,)
        )
        await db.commit()
        return cur.lastrowid


async def get_application(app_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM applications WHERE id = ?', (app_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_new_applications(exclude_locked: bool = True) -> List[Dict]:
    now = datetime.now(MSK).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if exclude_locked:
            q = '''SELECT * FROM applications
                   WHERE status = 'new'
                     AND (locked_until IS NULL OR locked_until < ?)
                   ORDER BY created_at ASC'''
            args = (now,)
        else:
            q = "SELECT * FROM applications WHERE status = 'new' ORDER BY created_at ASC"
            args = ()
        async with db.execute(q, args) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def lock_application(app_id: int, admin_id: int, duration_minutes: int = 2) -> bool:
    locked_until = (datetime.now(MSK) + timedelta(minutes=duration_minutes)).isoformat()
    now = datetime.now(MSK).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            '''SELECT id FROM applications
               WHERE id = ? AND status = 'new'
                 AND (locked_until IS NULL OR locked_until < ?)''',
            (app_id, now)
        ) as cur:
            if not await cur.fetchone():
                return False
        await db.execute(
            'UPDATE applications SET locked_by = ?, locked_until = ? WHERE id = ?',
            (admin_id, locked_until, app_id)
        )
        await db.commit()
        return True


async def unlock_application(app_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE applications SET locked_by = NULL, locked_until = NULL WHERE id = ?',
            (app_id,)
        )
        await db.commit()


async def approve_application(app_id: int, admin_id: int) -> None:
    now = datetime.now(MSK).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''UPDATE applications
               SET status = 'approved', reviewed_at = ?, reviewed_by = ?
               WHERE id = ?''',
            (now, admin_id, app_id)
        )
        await db.commit()


async def reject_application(app_id: int, admin_id: int, reason: str = None) -> None:
    now = datetime.now(MSK).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''UPDATE applications
               SET status = 'rejected', reviewed_at = ?, reviewed_by = ?,
                   last_rejection_reason = ?
               WHERE id = ?''',
            (now, admin_id, reason, app_id)
        )
        # Сохраняем причину отказа в users
        async with db.execute(
            'SELECT user_id FROM applications WHERE id = ?', (app_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                await db.execute(
                    'UPDATE users SET last_rejection_reason = ? WHERE tg_id = ?',
                    (reason, row[0])
                )
        await db.commit()


async def cleanup_expired_locks() -> None:
    now = datetime.now(MSK).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''UPDATE applications
               SET locked_by = NULL, locked_until = NULL
               WHERE locked_until IS NOT NULL AND locked_until < ?''',
            (now,)
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════════
#  ИНВАЙТ-ССЫЛКИ
# ═══════════════════════════════════════════════════════════════

async def create_invite_link(tg_id: int, link: str, message_id: int = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET invite_link = ?, invite_message_id = ? WHERE tg_id = ?',
            (link, message_id, tg_id)
        )
        await db.commit()


async def deactivate_invite_link(tg_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET invite_link = NULL, invite_message_id = NULL WHERE tg_id = ?',
            (tg_id,)
        )
        await db.commit()


async def get_active_invite_link(tg_id: int) -> Optional[str]:
    user = await get_user(tg_id)
    return user.get('invite_link') if user else None


# ═══════════════════════════════════════════════════════════════
#  ЧЁРНЫЙ СПИСОК
# ═══════════════════════════════════════════════════════════════

async def is_blacklisted(tg_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM blacklist WHERE tg_id = ?', (tg_id,)) as cur:
            return bool(await cur.fetchone())


async def add_to_blacklist(tg_id: int, reason: str = None, added_by: int = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''INSERT OR REPLACE INTO blacklist (tg_id, reason, added_by)
               VALUES (?, ?, ?)''',
            (tg_id, reason, added_by)
        )
        await db.commit()


async def remove_from_blacklist(tg_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM blacklist WHERE tg_id = ?', (tg_id,))
        await db.commit()


async def get_blacklist_reason(tg_id: int) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT reason FROM blacklist WHERE tg_id = ?', (tg_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def get_blacklist_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM blacklist') as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_blacklist_with_users() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT b.tg_id, b.reason, b.added_by, b.added_at,
                      u.username, u.first_name, u.last_name
               FROM blacklist b
               LEFT JOIN users u ON b.tg_id = u.tg_id
               ORDER BY b.added_at DESC'''
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ═══════════════════════════════════════════════════════════════
#  НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════════

async def get_setting(key: str, default: Any = None) -> Any:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT value FROM settings WHERE key = ?', (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default


async def set_setting(key: str, value: Any) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''INSERT OR REPLACE INTO settings (key, value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)''',
            (key, str(value) if value is not None else None)
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════════
#  НАПОМИНАНИЯ / СТАТИСТИКА
# ═══════════════════════════════════════════════════════════════

async def get_users_with_incomplete_questionnaire(minutes: int = None, days: int = None) -> List[Dict]:
    """БЗА — бросил заполнение анкеты."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if minutes or days:
            delta = timedelta(minutes=minutes or 0, days=days or 0)
            cutoff = (datetime.now(MSK) - delta).isoformat()
            async with db.execute(
                '''SELECT * FROM users
                   WHERE questionnaire_state IS NOT NULL
                     AND status = 'not_in_chat'
                     AND created_at <= ?''',
                (cutoff,)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]
        else:
            async with db.execute(
                "SELECT * FROM users WHERE questionnaire_state IS NOT NULL AND status = 'not_in_chat'"
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]


async def get_users_with_unused_link(minutes: int = None, days: int = None) -> List[Dict]:
    """НПС — получили ссылку, но не вступили."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if minutes or days:
            delta = timedelta(minutes=minutes or 0, days=days or 0)
            cutoff = (datetime.now(MSK) - delta).isoformat()
            async with db.execute(
                '''SELECT * FROM users
                   WHERE invite_link IS NOT NULL
                     AND status = 'not_in_chat'
                     AND created_at <= ?''',
                (cutoff,)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]
        else:
            async with db.execute(
                "SELECT * FROM users WHERE invite_link IS NOT NULL AND status = 'not_in_chat'"
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]


# ═══════════════════════════════════════════════════════════════
#  ЖУРНАЛ
# ═══════════════════════════════════════════════════════════════

async def add_journal_message(message_id: int, chat_id: int,
                               event_type: str, user_id: int = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            '''INSERT INTO journal_messages (message_id, chat_id, event_type, user_id)
               VALUES (?, ?, ?, ?)''',
            (message_id, chat_id, event_type, user_id)
        )
        await db.commit()
        return cur.lastrowid


async def get_last_profile_message(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT * FROM journal_messages
               WHERE user_id = ? AND event_type = 'profile'
               ORDER BY created_at DESC LIMIT 1''',
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def delete_journal_message(record_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM journal_messages WHERE id = ?', (record_id,))
        await db.commit()


async def get_old_journal_photos(days: int = 14) -> List[Dict]:
    cutoff = (datetime.now(MSK) - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT * FROM journal_messages
               WHERE event_type = 'photo' AND created_at < ?''',
            (cutoff,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ═══════════════════════════════════════════════════════════════
#  ТРИГГЕРЫ
# ═══════════════════════════════════════════════════════════════

async def get_enabled_triggers() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM triggers WHERE enabled = 1') as cur:
            return [dict(r) for r in await cur.fetchall()]


async def increment_violation(tg_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET violations = COALESCE(violations, 0) + 1 WHERE tg_id = ?',
            (tg_id,)
        )
        await db.commit()
        async with db.execute(
            'SELECT COALESCE(violations, 0) FROM users WHERE tg_id = ?', (tg_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def reset_violations(tg_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET violations = 0 WHERE tg_id = ?', (tg_id,))
        await db.commit()


# ═══════════════════════════════════════════════════════════════
#  ОПРОС ПРИ ВЫХОДЕ
# ═══════════════════════════════════════════════════════════════

async def should_send_survey(tg_id: int) -> bool:
    """Нужно ли отправлять опрос ушедшему пользователю."""
    user = await get_user(tg_id)
    if not user:
        return False
    # Не слать если уже отвечал недавно (30 дней)
    last = user.get('last_survey_at')
    if last:
        try:
            dt = datetime.fromisoformat(str(last))
            if datetime.now(MSK) - dt.replace(tzinfo=MSK) < timedelta(days=30):
                return False
        except Exception:
            pass
    return True


async def save_survey_result(tg_id: int, reason: str) -> None:
    """Сохраняет результат опроса."""
    now = datetime.now(MSK).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        # Убедимся что колонка существует
        try:
            await db.execute(
                'ALTER TABLE users ADD COLUMN last_survey_at TIMESTAMP'
            )
            await db.execute(
                'ALTER TABLE users ADD COLUMN survey_reason TEXT'
            )
        except Exception:
            pass
        await db.execute(
            'UPDATE users SET last_survey_at = ?, survey_reason = ? WHERE tg_id = ?',
            (now, reason, tg_id)
        )
        await db.commit()


async def get_referral_code(tg_id: int) -> Optional[str]:
    """Возвращает реферальный код (username) пользователя."""
    user = await get_user(tg_id)
    if user:
        return user.get('username')
    return None


# ─── Совместимость: send_to_journal (legacy alias) ───────────
async def send_to_journal(*args, **kwargs):
    """Устаревший псевдоним — логирование теперь в utils/journal.py."""
    pass
