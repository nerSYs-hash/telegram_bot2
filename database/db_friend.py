"""
Оптимизированный модуль работы с базой данных
Включает индексы, улучшенную структуру таблиц и connection pooling
"""
import os
import sqlite3
import json
import asyncio
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import aiosqlite
from contextlib import asynccontextmanager
import logging

# Импортируем константы
from constants import UserStatus, ApplicationStatus, UserRole
from config import OWNER_ID

DB_PATH = "pulse_bot.db"

# Connection pool для оптимизации
class DatabasePool:
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @asynccontextmanager
    async def get_connection(self):
        """Получение подключения к БД из пула"""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            yield db

db_pool = DatabasePool()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def row_to_dict(row: aiosqlite.Row) -> dict:
    """Преобразование sqlite3.Row в словарь"""
    if not row:
        return None
    return {key: row[key] for key in row.keys()}

def rows_to_dict_list(rows: List[aiosqlite.Row]) -> List[dict]:
    """Преобразование списка sqlite3.Row в список словарей"""
    return [row_to_dict(row) for row in rows]

def generate_referral_code(length: int = 6) -> str:
    """Генерация уникального реферального кода"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# ==================== ИНИЦИАЛИЗАЦИЯ БД ====================

async def init_db():
    """Инициализация базы данных с индексами и оптимизациями"""
    async with db_pool.get_connection() as db:
        # Users table с оптимизированной структурой
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'not_in_chat',
                is_banned BOOLEAN DEFAULT 0,
                ban_reason TEXT,
                q_name TEXT,
                q_age INTEGER,
                q_city TEXT,
                q_therapy TEXT,
                birth_date TEXT,
                blocked_until TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_exit_at TIMESTAMP,
                survey_sent_at TIMESTAMP,
                last_rejection_reason TEXT,
                invite_link TEXT,
                invite_message_id INTEGER,
                previous_username TEXT,
                previous_first_name TEXT,
                previous_last_name TEXT,
                last_activity TIMESTAMP,
                questionnaire_state TEXT,
                referral_code TEXT,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0,
                referral_earnings INTEGER DEFAULT 0,
                FOREIGN KEY(referred_by) REFERENCES users(tg_id)
            )
        """)
        
        # ===== МИГРАЦИИ: добавляем недостающие колонки =====
        
        # Проверяем и добавляем колонку last_activity, если её нет
        try:
            await db.execute("SELECT last_activity FROM users LIMIT 1")
        except sqlite3.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN last_activity TIMESTAMP")
            await db.execute("UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE last_activity IS NULL")
            print("✅ Added last_activity column to users table")
        
        # Проверяем и добавляем колонку questionnaire_state, если её нет
        try:
            await db.execute("SELECT questionnaire_state FROM users LIMIT 1")
        except sqlite3.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN questionnaire_state TEXT")
            print("✅ Added questionnaire_state column to users table")
        
        # Проверяем и добавляем колонку referral_code, если её нет
        try:
            await db.execute("SELECT referral_code FROM users LIMIT 1")
        except sqlite3.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
            print("✅ Added referral_code column to users table")
            
            # Генерируем уникальные коды для существующих пользователей
            async with db.execute("SELECT tg_id FROM users") as cursor:
                users = await cursor.fetchall()
                for user in users:
                    user_id = user[0]
                    while True:
                        code = generate_referral_code()
                        existing = await db.execute(
                            "SELECT 1 FROM users WHERE referral_code = ?", 
                            (code,)
                        )
                        if not await existing.fetchone():
                            break
                    await db.execute(
                        "UPDATE users SET referral_code = ? WHERE tg_id = ?",
                        (code, user_id)
                    )
            
            try:
                await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code_unique ON users(referral_code)")
                print("✅ Created unique index for referral_code")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Could not create unique index: {e}")
        
        # Проверяем и добавляем колонку referred_by, если её нет
        try:
            await db.execute("SELECT referred_by FROM users LIMIT 1")
        except sqlite3.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
            print("✅ Added referred_by column to users table")
        
        # Проверяем и добавляем колонку referral_count, если её нет
        try:
            await db.execute("SELECT referral_count FROM users LIMIT 1")
        except sqlite3.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0")
            print("✅ Added referral_count column to users table")
        
        # Проверяем и добавляем колонку referral_earnings, если её нет
        try:
            await db.execute("SELECT referral_earnings FROM users LIMIT 1")
        except sqlite3.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN referral_earnings INTEGER DEFAULT 0")
            print("✅ Added referral_earnings column to users table")
        
        # Индексы для оптимизации запросов
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users(last_activity)")
        except sqlite3.OperationalError:
            pass
        
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by)")
        except sqlite3.OperationalError:
            pass
        
        # Applications table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT DEFAULT 'new',
                admin_id INTEGER,
                rejection_reason TEXT,
                message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                locked_until TIMESTAMP,
                locked_by INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(tg_id),
                FOREIGN KEY(admin_id) REFERENCES users(tg_id),
                FOREIGN KEY(locked_by) REFERENCES users(tg_id)
            )
        """)
        
        # Миграция: добавляем message_id если нет
        try:
            await db.execute("ALTER TABLE applications ADD COLUMN message_id INTEGER")
            await db.commit()
            logger.info("✅ Миграция: добавлена колонка message_id в applications")
        except Exception:
            pass  # колонка уже есть

        await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_applications_locked_until ON applications(locked_until)")
        
        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS update_applications_updated_at 
            AFTER UPDATE ON applications
            BEGIN
                UPDATE applications SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
            END;
        """)
        
        # Admins table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                tg_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(added_by) REFERENCES users(tg_id)
            )
        """)
        
        # Blacklist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                tg_id INTEGER PRIMARY KEY,
                reason TEXT NOT NULL,
                admin_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(admin_id) REFERENCES users(tg_id)
            )
        """)
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_tg_id ON blacklist(tg_id)")
        
        # Triggers
        await db.execute("""
            CREATE TABLE IF NOT EXISTS triggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                keywords TEXT NOT NULL,
                condition TEXT NOT NULL,
                scope TEXT NOT NULL,
                branches TEXT,
                initiator_role TEXT NOT NULL,
                target_type TEXT NOT NULL,
                cumulative_enabled BOOLEAN DEFAULT 0,
                cumulative_actions TEXT,
                cumulative_threshold INTEGER,
                cumulative_period TEXT,
                cumulative_final_action TEXT,
                cumulative_reset TEXT,
                actions TEXT NOT NULL,
                probability INTEGER DEFAULT 100,
                delay_enabled BOOLEAN DEFAULT 0,
                delay_period TEXT,
                silent BOOLEAN DEFAULT 0,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_triggers_enabled ON triggers(enabled)")
        
        # Violations
        await db.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                user_id INTEGER NOT NULL,
                trigger_id INTEGER NOT NULL,
                count INTEGER DEFAULT 0,
                last_violation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reset_at TIMESTAMP,
                PRIMARY KEY(user_id, trigger_id),
                FOREIGN KEY(user_id) REFERENCES users(tg_id),
                FOREIGN KEY(trigger_id) REFERENCES triggers(id) ON DELETE CASCADE
            )
        """)
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_violations_user_id ON violations(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_violations_trigger_id ON violations(trigger_id)")
        
        # Referral Transactions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referral_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                amount INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY(referrer_id) REFERENCES users(tg_id),
                FOREIGN KEY(referred_id) REFERENCES users(tg_id)
            )
        """)
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_referral_referrer ON referral_transactions(referrer_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_referral_referred ON referral_transactions(referred_id)")
        
        # Survey Results
        await db.execute("""
            CREATE TABLE IF NOT EXISTS survey_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                q1 TEXT,
                q_details TEXT,
                q2 TEXT,
                q3 TEXT,
                q4 TEXT,
                q5 TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(tg_id)
            )
        """)
        
        # Journal Messages
        await db.execute("""
            CREATE TABLE IF NOT EXISTS journal_messages (
                message_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                msg_type TEXT NOT NULL,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(tg_id)
            )
        """)
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_journal_msg_type ON journal_messages(msg_type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_journal_created_at ON journal_messages(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_journal_user_id ON journal_messages(user_id)")
        
        # Settings
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Invite links
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invite_links (
                link TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(tg_id)
            )
        """)
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_invite_links_user_id ON invite_links(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_invite_links_active ON invite_links(is_active)")
        
        await db.commit()

# ==================== USER OPERATIONS ====================

async def get_user(tg_id: int) -> Optional[dict]:
    """Получение пользователя по ID - возвращает словарь"""
    async with db_pool.get_connection() as db:
        async with db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)) as cursor:
            row = await cursor.fetchone()
            return row_to_dict(row)

async def get_user_by_referral_code(code: str) -> Optional[dict]:
    """Получение пользователя по реферальному коду"""
    async with db_pool.get_connection() as db:
        async with db.execute("SELECT * FROM users WHERE referral_code = ?", (code,)) as cursor:
            row = await cursor.fetchone()
            return row_to_dict(row)

async def create_user(tg_id: int, username: str, first_name: str, last_name: str, role: str = UserRole.USER):
    """Создание нового пользователя с уникальным реферальным кодом"""
    async with db_pool.get_connection() as db:
        # Генерируем уникальный реферальный код
        while True:
            referral_code = generate_referral_code()
            # Проверяем, что код уникальный
            existing = await db.execute(
                "SELECT 1 FROM users WHERE referral_code = ?", 
                (referral_code,)
            )
            if not await existing.fetchone():
                break
        
        await db.execute(
            """INSERT OR IGNORE INTO users 
               (tg_id, username, first_name, last_name, role, previous_username, 
                previous_first_name, previous_last_name, last_activity, referral_code) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tg_id, username, first_name, last_name, role, username, 
             first_name, last_name, datetime.now().isoformat(), referral_code)
        )
        await db.commit()

async def update_user(tg_id: int, **kwargs):
    """Обновление данных пользователя"""
    if not kwargs:
        return
    
    # Всегда обновляем last_activity при любом обновлении
    if 'last_activity' not in kwargs:
        kwargs['last_activity'] = datetime.now().isoformat()
    
    async with db_pool.get_connection() as db:
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [tg_id]
        query = f"UPDATE users SET {set_clause} WHERE tg_id = ?"
        await db.execute(query, values)
        await db.commit()

async def get_user_by_username(username: str) -> Optional[dict]:
    """Получение пользователя по username - возвращает словарь"""
    async with db_pool.get_connection() as db:
        async with db.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", 
            (username.lstrip('@'),)
        ) as cursor:
            row = await cursor.fetchone()
            return row_to_dict(row)

async def update_last_seen(tg_id: int):
    """Обновление времени последней активности"""
    async with db_pool.get_connection() as db:
        await db.execute(
            "UPDATE users SET last_seen = ?, last_activity = ? WHERE tg_id = ?",
            (datetime.now().isoformat(), datetime.now().isoformat(), tg_id)
        )
        await db.commit()

async def get_users_with_incomplete_questionnaire(minutes: int = 5) -> List[dict]:
    """Получение пользователей с незаконченными анкетами"""
    async with db_pool.get_connection() as db:
        cutoff_time = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        async with db.execute(
            """SELECT tg_id, q_name, first_name, questionnaire_state 
               FROM users 
               WHERE questionnaire_state IS NOT NULL 
               AND last_activity < ?""",
            (cutoff_time,)
        ) as cursor:
            rows = await cursor.fetchall()
            return rows_to_dict_list(rows)

async def get_users_with_unused_link(minutes: int = None, days: int = None) -> List[dict]:
    """
    Получение пользователей, которые получили ссылку,
    но до сих пор не в чате
    
    Args:
        minutes: если указано, ищем пользователей, которые получили ссылку более minutes назад
        days: если указано, ищем пользователей, которые получили ссылку более days назад
    """
    async with db_pool.get_connection() as db:
        if minutes:
            cutoff_time = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        elif days:
            cutoff_time = (datetime.now() - timedelta(days=days)).isoformat()
        else:
            return []
        
        async with db.execute(
            """SELECT tg_id, q_name, first_name, invite_link, invite_message_id 
               FROM users 
               WHERE invite_link IS NOT NULL 
               AND status != ? 
               AND last_activity < ?""",
            (UserStatus.IN_CHAT, cutoff_time)
        ) as cursor:
            rows = await cursor.fetchall()
            return rows_to_dict_list(rows)

# ==================== REFERRAL OPERATIONS ====================

async def process_referral(referred_id: int, referral_code: str) -> bool:
    """
    Обработка реферального кода при регистрации
    Возвращает True, если реферал успешно засчитан
    """
    if not referral_code:
        return False
    
    # Находим пригласившего по коду
    referrer = await get_user_by_referral_code(referral_code)
    if not referrer:
        return False
    
    referrer_id = referrer['tg_id']
    
    # Нельзя пригласить самого себя
    if referrer_id == referred_id:
        return False
    
    async with db_pool.get_connection() as db:
        # Проверяем, не был ли уже этот пользователь приглашен
        existing = await db.execute(
            "SELECT 1 FROM referral_transactions WHERE referred_id = ?",
            (referred_id,)
        )
        if await existing.fetchone():
            return False
        
        # Обновляем пользователя: указываем, кто пригласил
        await db.execute(
            "UPDATE users SET referred_by = ? WHERE tg_id = ?",
            (referrer_id, referred_id)
        )
        
        # Создаем запись о реферальной транзакции (статус pending)
        await db.execute(
            """INSERT INTO referral_transactions 
               (referrer_id, referred_id, amount, status) 
               VALUES (?, ?, ?, 'pending')""",
            (referrer_id, referred_id, 1)
        )
        
        await db.commit()
        return True

async def confirm_referral(referred_id: int):
    """
    Подтверждение реферала после вступления пользователя в чат
    """
    async with db_pool.get_connection() as db:
        # Находим pending транзакцию
        async with db.execute(
            """SELECT id, referrer_id FROM referral_transactions 
               WHERE referred_id = ? AND status = 'pending'""",
            (referred_id,)
        ) as cursor:
            transaction = await cursor.fetchone()
        
        if not transaction:
            return
        
        transaction_id = transaction[0]
        referrer_id = transaction[1]
        
        # Обновляем статус транзакции
        await db.execute(
            "UPDATE referral_transactions SET status = 'credited' WHERE id = ?",
            (transaction_id,)
        )
        
        # Увеличиваем счетчик рефералов у пригласившего
        await db.execute(
            """UPDATE users 
               SET referral_count = referral_count + 1,
                   referral_earnings = referral_earnings + 1
               WHERE tg_id = ?""",
            (referrer_id,)
        )
        
        await db.commit()

async def get_referral_stats(user_id: int) -> dict:
    """Получение статистики рефералов пользователя"""
    async with db_pool.get_connection() as db:
        async with db.execute(
            """SELECT 
                COUNT(CASE WHEN status = 'credited' THEN 1 END) as successful,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending
               FROM referral_transactions 
               WHERE referrer_id = ?""",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            successful = row[0] if row else 0
            pending = row[1] if row else 0
        
        # Получаем данные пользователя
        user = await get_user(user_id)
        referral_code = user.get('referral_code') if user else None
        referral_count = user.get('referral_count', 0) if user else 0
        referral_earnings = user.get('referral_earnings', 0) if user else 0
        
        return {
            'referral_code': referral_code,
            'total': successful,
            'pending': pending,
            'successful': successful,
            'earnings': referral_earnings,
            'count': referral_count
        }

async def get_referral_code(user_id: int) -> Optional[str]:
    """Получение реферального кода пользователя"""
    user = await get_user(user_id)
    if user:
        return user.get('referral_code')
    return None

# ==================== APPLICATION OPERATIONS ====================

async def create_application(user_id: int) -> int:
    """Создание новой заявки"""
    async with db_pool.get_connection() as db:
        cursor = await db.execute(
            "INSERT INTO applications (user_id, status) VALUES (?, ?)",
            (user_id, ApplicationStatus.NEW)
        )
        await db.commit()
        return cursor.lastrowid

async def get_new_applications(exclude_locked: bool = True) -> List[dict]:
    """Получение новых заявок - возвращает список словарей"""
    # Сначала чистим просроченные блокировки (IN_WORK → NEW)
    await cleanup_expired_locks()

    async with db_pool.get_connection() as db:
        now = datetime.now().isoformat()

        if exclude_locked:
            query = """
                SELECT * FROM applications
                WHERE status IN (?, ?)
                AND (locked_until IS NULL OR locked_until < ?)
                ORDER BY status ASC, created_at ASC
            """
            params = (ApplicationStatus.NEW, ApplicationStatus.SKIPPED, now)
        else:
            query = "SELECT * FROM applications WHERE status IN (?, ?) ORDER BY status ASC, created_at ASC"
            params = (ApplicationStatus.NEW, ApplicationStatus.SKIPPED)
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return rows_to_dict_list(rows)

async def lock_application(app_id: int, admin_id: int, duration_minutes: int = 2) -> bool:
    """Блокировка заявки для обработки администратором"""
    async with db_pool.get_connection() as db:
        locked_until = (datetime.now() + timedelta(minutes=duration_minutes)).isoformat()
        
        result = await db.execute(
            """UPDATE applications 
               SET status = ?, locked_by = ?, locked_until = ?, updated_at = ?
               WHERE id = ? AND (status IN (?, ?) OR (locked_until IS NOT NULL AND locked_until < ?))""",
            (ApplicationStatus.IN_WORK, admin_id, locked_until, datetime.now().isoformat(),
             app_id, ApplicationStatus.NEW, ApplicationStatus.SKIPPED, datetime.now().isoformat())
        )
        await db.commit()
        
        return result.rowcount > 0

async def unlock_application(app_id: int):
    """Разблокировка заявки (возврат в предыдущий статус после истечения lock)"""
    async with db_pool.get_connection() as db:
        # Сначала проверяем, была ли заявка SKIPPED до блокировки
        async with db.execute("SELECT status FROM applications WHERE id = ?", (app_id,)) as cursor:
            row = await cursor.fetchone()
        # Если заявка уже одобрена/отклонена — не трогаем
        if row and row[0] not in (ApplicationStatus.IN_WORK,):
            return
        await db.execute(
            """UPDATE applications
               SET status = ?, locked_by = NULL, locked_until = NULL, updated_at = ?
               WHERE id = ? AND status = ?""",
            (ApplicationStatus.NEW, datetime.now().isoformat(), app_id, ApplicationStatus.IN_WORK)
        )
        await db.commit()


async def save_application_message_id(app_id: int, message_id: int):
    """Сохраняет message_id карточки заявки в треде администраторов"""
    async with db_pool.get_connection() as db:
        await db.execute(
            "UPDATE applications SET message_id = ? WHERE id = ?",
            (message_id, app_id)
        )
        await db.commit()


async def set_application_skipped(app_id: int):
    """Отложить заявку (SKIPPED) — возвращается в очередь с особым статусом"""
    async with db_pool.get_connection() as db:
        await db.execute(
            """UPDATE applications
               SET status = ?, locked_by = NULL, locked_until = NULL, updated_at = ?
               WHERE id = ?""",
            (ApplicationStatus.SKIPPED, datetime.now().isoformat(), app_id)
        )
        await db.commit()

async def delete_application(app_id: int, admin_id: int):
    """Удаление заявки администратором — статус DELETED, не возвращается в очередь"""
    async with db_pool.get_connection() as db:
        await db.execute(
            """UPDATE applications
               SET status = ?, admin_id = ?, locked_by = NULL, locked_until = NULL, updated_at = ?
               WHERE id = ?""",
            (ApplicationStatus.DELETED, admin_id, datetime.now().isoformat(), app_id)
        )
        await db.commit()


async def approve_application(app_id: int, admin_id: int):
    """Одобрение заявки"""
    async with db_pool.get_connection() as db:
        await db.execute(
            """UPDATE applications 
               SET status = ?, admin_id = ?, updated_at = ?, locked_by = NULL, locked_until = NULL
               WHERE id = ?""",
            (ApplicationStatus.APPROVED, admin_id, datetime.now().isoformat(), app_id)
        )
        await db.commit()

async def reject_application(app_id: int, admin_id: int, reason: str):
    """Отклонение заявки"""
    async with db_pool.get_connection() as db:
        await db.execute(
            """UPDATE applications 
               SET status = ?, admin_id = ?, rejection_reason = ?, updated_at = ?, 
                   locked_by = NULL, locked_until = NULL
               WHERE id = ?""",
            (ApplicationStatus.REJECTED, admin_id, reason, datetime.now().isoformat(), app_id)
        )
        
        # Обновляем последнюю причину отказа в профиле пользователя
        user_id = await db.execute(
            "SELECT user_id FROM applications WHERE id = ?", (app_id,)
        )
        user_row = await user_id.fetchone()
        if user_row:
            await db.execute(
                "UPDATE users SET last_rejection_reason = ? WHERE tg_id = ?",
                (reason, user_row[0])
            )
        
        await db.commit()

async def get_application(app_id: int) -> Optional[dict]:
    """Получение заявки по ID - возвращает словарь"""
    async with db_pool.get_connection() as db:
        async with db.execute("SELECT * FROM applications WHERE id = ?", (app_id,)) as cursor:
            row = await cursor.fetchone()
            return row_to_dict(row)

async def cancel_user_applications(user_id: int):
    """Отменяет все активные заявки пользователя (при перезапуске регистрации)."""
    async with db_pool.get_connection() as db:
        await db.execute(
            """UPDATE applications SET status = ?, locked_by = NULL, locked_until = NULL
               WHERE user_id = ? AND status IN (?, ?, ?)""",
            (ApplicationStatus.CANCELLED, user_id,
             ApplicationStatus.NEW, ApplicationStatus.IN_WORK, ApplicationStatus.SKIPPED)
        )
        await db.commit()


async def get_user_pending_application(user_id: int) -> Optional[dict]:
    """Возвращает активную заявку пользователя, если она есть."""
    async with db_pool.get_connection() as db:
        async with db.execute(
            """SELECT * FROM applications WHERE user_id = ? AND status IN (?, ?, ?)
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, ApplicationStatus.NEW, ApplicationStatus.IN_WORK, ApplicationStatus.SKIPPED)
        ) as cursor:
            row = await cursor.fetchone()
            return row_to_dict(row)


async def close_user_applications(user_id: int, status: str = 'approved'):
    """Переводит все активные заявки пользователя в указанный статус (авто-закрытие)."""
    async with db_pool.get_connection() as db:
        await db.execute(
            """UPDATE applications 
               SET status = ?, updated_at = ?, locked_by = NULL, locked_until = NULL 
               WHERE user_id = ? AND status IN (?, ?, ?)""",
            (status, datetime.now().isoformat(), user_id,
             ApplicationStatus.NEW, ApplicationStatus.IN_WORK, ApplicationStatus.SKIPPED)
        )
        await db.commit()


async def cleanup_expired_locks():
    """Очистка истекших блокировок заявок"""
    async with db_pool.get_connection() as db:
        now = datetime.now().isoformat()
        await db.execute(
            """UPDATE applications 
               SET status = ?, locked_by = NULL, locked_until = NULL
               WHERE status = ? AND locked_until < ?""",
            (ApplicationStatus.NEW, ApplicationStatus.IN_WORK, now)
        )
        await db.commit()

# ==================== ADMIN OPERATIONS ====================

async def is_admin(tg_id: int) -> bool:
    """Проверка является ли пользователь администратором"""
    async with db_pool.get_connection() as db:
        async with db.execute("SELECT 1 FROM admins WHERE tg_id = ?", (tg_id,)) as cursor:
            result = await cursor.fetchone()
            return result is not None

async def add_admin(tg_id: int, added_by: int):
    """Добавление администратора"""
    async with db_pool.get_connection() as db:
        await db.execute(
            "INSERT OR IGNORE INTO admins (tg_id, added_by) VALUES (?, ?)",
            (tg_id, added_by)
        )
        await db.execute(
            "UPDATE users SET role = ? WHERE tg_id = ?",
            (UserRole.ADMIN, tg_id)
        )
        await db.commit()

async def remove_admin(tg_id: int):
    """Удаление администратора"""
    async with db_pool.get_connection() as db:
        await db.execute("DELETE FROM admins WHERE tg_id = ?", (tg_id,))
        await db.execute(
            "UPDATE users SET role = ? WHERE tg_id = ?",
            (UserRole.USER, tg_id)
        )
        await db.commit()

async def get_all_admins() -> List[dict]:
    """Получение списка всех администраторов И владельца"""
    async with db_pool.get_connection() as db:
        # Получаем администраторов из таблицы admins
        async with db.execute(
            """SELECT u.* FROM users u 
               INNER JOIN admins a ON u.tg_id = a.tg_id"""
        ) as cursor:
            rows = await cursor.fetchall()
            admins = rows_to_dict_list(rows)
    
    # Добавляем владельца в список (если его там еще нет)
    owner_in_list = any(admin['tg_id'] == OWNER_ID for admin in admins)
    if not owner_in_list:
        owner = await get_user(OWNER_ID)
        if owner:
            admins.append(owner)
            logger = logging.getLogger(__name__)
            logger.info(f"Added owner {OWNER_ID} to admins list")
    
    logger = logging.getLogger(__name__)
    logger.info(f"Total recipients for notifications: {len(admins)}")
    return admins

# ==================== BLACKLIST OPERATIONS ====================

async def is_blacklisted(tg_id: int) -> bool:
    """Проверка находится ли пользователь в черном списке"""
    async with db_pool.get_connection() as db:
        async with db.execute("SELECT 1 FROM blacklist WHERE tg_id = ?", (tg_id,)) as cursor:
            result = await cursor.fetchone()
            return result is not None

async def get_blacklist_reason(tg_id: int) -> Optional[str]:
    """Получение причины блокировки"""
    async with db_pool.get_connection() as db:
        async with db.execute("SELECT reason FROM blacklist WHERE tg_id = ?", (tg_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

async def add_to_blacklist(tg_id: int, reason: str, admin_id: int):
    """Добавление в черный список"""
    async with db_pool.get_connection() as db:
        await db.execute(
            "INSERT OR REPLACE INTO blacklist (tg_id, reason, admin_id) VALUES (?, ?, ?)",
            (tg_id, reason, admin_id)
        )
        await db.execute(
            "UPDATE users SET is_banned = 1, ban_reason = ? WHERE tg_id = ?",
            (reason, tg_id)
        )
        await db.commit()

async def remove_from_blacklist(tg_id: int):
    """Удаление из черного списка"""
    async with db_pool.get_connection() as db:
        await db.execute("DELETE FROM blacklist WHERE tg_id = ?", (tg_id,))
        await db.execute(
            "UPDATE users SET is_banned = 0, ban_reason = NULL WHERE tg_id = ?",
            (tg_id,)
        )
        await db.commit()

async def get_blacklist_count() -> int:
    """Получение количества пользователей в черном списке"""
    async with db_pool.get_connection() as db:
        async with db.execute("SELECT COUNT(*) FROM blacklist") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_blacklist_with_users() -> List[dict]:
    """Получение черного списка с данными пользователей"""
    async with db_pool.get_connection() as db:
        async with db.execute(
            """SELECT b.*, u.first_name, u.last_name, u.username 
               FROM blacklist b
               LEFT JOIN users u ON b.tg_id = u.tg_id
               ORDER BY b.created_at DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                result.append({
                    'tg_id': row[0],
                    'reason': row[1],
                    'admin_id': row[2],
                    'created_at': row[3],
                    'user': {
                        'first_name': row[4],
                        'last_name': row[5],
                        'username': row[6]
                    }
                })
            return result

# ==================== SETTINGS OPERATIONS ====================

async def get_setting(key: str) -> Optional[str]:
    """Получение настройки"""
    async with db_pool.get_connection() as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def set_setting(key: str, value: str):
    """Установка настройки"""
    async with db_pool.get_connection() as db:
        await db.execute(
            """INSERT OR REPLACE INTO settings (key, value, updated_at) 
               VALUES (?, ?, ?)""",
            (key, str(value), datetime.now().isoformat())
        )
        await db.commit()

# ==================== INVITE LINKS OPERATIONS ====================

async def create_invite_link(user_id: int, link: str):
    """Создание записи о пригласительной ссылке"""
    async with db_pool.get_connection() as db:
        await db.execute(
            "INSERT INTO invite_links (link, user_id, is_active) VALUES (?, ?, 1)",
            (link, user_id)
        )
        await db.commit()

async def deactivate_invite_link(link: str):
    """Деактивация пригласительной ссылки"""
    async with db_pool.get_connection() as db:
        await db.execute(
            "UPDATE invite_links SET is_active = 0, used_at = ? WHERE link = ?",
            (datetime.now().isoformat(), link)
        )
        await db.commit()

async def get_active_invite_link(user_id: int) -> Optional[str]:
    """Получение активной ссылки пользователя"""
    async with db_pool.get_connection() as db:
        async with db.execute(
            "SELECT link FROM invite_links WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# ==================== JOURNAL MESSAGES OPERATIONS ====================

async def add_journal_message(message_id: int, chat_id: int, msg_type: str, user_id: Optional[int] = None):
    """Добавление сообщения в журнал"""
    async with db_pool.get_connection() as db:
        await db.execute(
            "INSERT INTO journal_messages (message_id, chat_id, msg_type, user_id) VALUES (?, ?, ?, ?)",
            (message_id, chat_id, msg_type, user_id)
        )
        await db.commit()

async def get_last_profile_message(user_id: int, chat_id: int) -> Optional[int]:
    """Получение ID последнего сообщения с обновлением профиля"""
    async with db_pool.get_connection() as db:
        async with db.execute(
            """SELECT message_id FROM journal_messages 
               WHERE user_id = ? AND chat_id = ? AND msg_type = 'profile' 
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, chat_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def delete_journal_message(message_id: int):
    """Удаление сообщения из журнала"""
    async with db_pool.get_connection() as db:
        await db.execute("DELETE FROM journal_messages WHERE message_id = ?", (message_id,))
        await db.commit()

async def get_old_journal_photos(days: int = 14) -> List[dict]:
    """Получение старых фотографий из журнала"""
    async with db_pool.get_connection() as db:
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        async with db.execute(
            "SELECT * FROM journal_messages WHERE msg_type = 'photo' AND created_at < ?",
            (cutoff_date,)
        ) as cursor:
            rows = await cursor.fetchall()
            return rows_to_dict_list(rows)

# ==================== INACTIVE USERS ====================

async def get_inactive_users(days: int = 60) -> List[dict]:
    """Получение неактивных пользователей - возвращает список словарей"""
    async with db_pool.get_connection() as db:
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        async with db.execute(
            """SELECT * FROM users 
               WHERE status = ? AND last_seen < ?""",
            (UserStatus.IN_CHAT, cutoff_date)
        ) as cursor:
            rows = await cursor.fetchall()
            return rows_to_dict_list(rows)

# ==================== SURVEY OPERATIONS ====================

async def save_survey_result(user_id: int, answers: Dict[str, str]):
    """Сохранение результатов опроса"""
    async with db_pool.get_connection() as db:
        await db.execute(
            """INSERT INTO survey_results (user_id, q1, q_details, q2, q3, q4, q5) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, answers.get('q1'), answers.get('q_details'), 
             answers.get('q2'), answers.get('q3'), answers.get('q4'), answers.get('q5'))
        )
        await db.commit()

async def should_send_survey(user_id: int) -> bool:
    """Проверка нужно ли отправлять опрос (не чаще 1 раза в 30 дней)"""
    async with db_pool.get_connection() as db:
        user = await get_user(user_id)
        if not user or not user.get('survey_sent_at'):
            return True
        
        try:
            survey_date = datetime.fromisoformat(user['survey_sent_at'])
            days_since = (datetime.now() - survey_date).days
            return days_since >= 30
        except:
            return True

async def get_survey_stats() -> dict:
    """Получение статистики по опросам"""
    async with db_pool.get_connection() as db:
        # Общее количество опросов
        async with db.execute("SELECT COUNT(*) FROM survey_results") as cursor:
            total = (await cursor.fetchone())[0]
        
        # Статистика по причинам
        async with db.execute(
            """SELECT q1, COUNT(*) as count 
               FROM survey_results 
               GROUP BY q1 
               ORDER BY count DESC 
               LIMIT 10"""
        ) as cursor:
            rows = await cursor.fetchall()
            reasons = [{"reason": row[0], "count": row[1]} for row in rows]
        
        return {
            "total": total,
            "top_reasons": reasons
        }

# ==================== TRIGGER OPERATIONS ====================

async def get_enabled_triggers() -> List[dict]:
    """Получение активных триггеров - возвращает список словарей"""
    async with db_pool.get_connection() as db:
        async with db.execute("SELECT * FROM triggers WHERE enabled = 1") as cursor:
            rows = await cursor.fetchall()
            return rows_to_dict_list(rows)

async def create_trigger(trigger_data: Dict[str, Any]) -> int:
    """Создание нового триггера"""
    async with db_pool.get_connection() as db:
        cursor = await db.execute(
            """INSERT INTO triggers 
               (name, keywords, condition, scope, branches, initiator_role, target_type,
                cumulative_enabled, cumulative_actions, cumulative_threshold, cumulative_period,
                cumulative_final_action, cumulative_reset, actions, probability, delay_enabled,
                delay_period, silent, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trigger_data['name'], 
                trigger_data['keywords'], 
                trigger_data['condition'],
                trigger_data['scope'], 
                trigger_data.get('branches'),
                trigger_data['initiator_role'], 
                trigger_data['target_type'],
                trigger_data.get('cumulative_enabled', False),
                trigger_data.get('cumulative_actions'),
                trigger_data.get('cumulative_threshold'),
                trigger_data.get('cumulative_period'),
                trigger_data.get('cumulative_final_action'),
                trigger_data.get('cumulative_reset'),
                trigger_data['actions'], 
                trigger_data.get('probability', 100),
                trigger_data.get('delay_enabled', False),
                trigger_data.get('delay_period'),
                trigger_data.get('silent', False),
                trigger_data.get('enabled', True)
            )
        )
        await db.commit()
        return cursor.lastrowid

async def update_trigger(trigger_id: int, trigger_data: Dict[str, Any]):
    """Обновление триггера"""
    async with db_pool.get_connection() as db:
        set_parts = []
        values = []
        
        for key, value in trigger_data.items():
            set_parts.append(f"{key} = ?")
            values.append(value)
        
        set_parts.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(trigger_id)
        
        query = f"UPDATE triggers SET {', '.join(set_parts)} WHERE id = ?"
        await db.execute(query, values)
        await db.commit()

async def delete_trigger(trigger_id: int):
    """Удаление триггера"""
    async with db_pool.get_connection() as db:
        await db.execute("DELETE FROM triggers WHERE id = ?", (trigger_id,))
        await db.commit()

async def toggle_trigger(trigger_id: int, enabled: bool):
    """Включение/выключение триггера"""
    async with db_pool.get_connection() as db:
        await db.execute(
            "UPDATE triggers SET enabled = ?, updated_at = ? WHERE id = ?",
            (enabled, datetime.now().isoformat(), trigger_id)
        )
        await db.commit()

async def get_all_triggers() -> List[dict]:
    """Получение всех триггеров - возвращает список словарей"""
    async with db_pool.get_connection() as db:
        async with db.execute("SELECT * FROM triggers ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return rows_to_dict_list(rows)

# ==================== VIOLATION OPERATIONS ====================

async def increment_violation(user_id: int, trigger_id: int) -> int:
    """Увеличение счетчика нарушений"""
    async with db_pool.get_connection() as db:
        # Проверяем, существует ли запись
        async with db.execute(
            "SELECT count FROM violations WHERE user_id = ? AND trigger_id = ?",
            (user_id, trigger_id)
        ) as cursor:
            row = await cursor.fetchone()
        
        if row:
            # Обновляем существующую запись
            await db.execute(
                """UPDATE violations 
                   SET count = count + 1, last_violation_at = ?
                   WHERE user_id = ? AND trigger_id = ?""",
                (datetime.now().isoformat(), user_id, trigger_id)
            )
            new_count = row[0] + 1
        else:
            # Создаем новую запись
            await db.execute(
                """INSERT INTO violations (user_id, trigger_id, count, last_violation_at)
                   VALUES (?, ?, 1, ?)""",
                (user_id, trigger_id, datetime.now().isoformat())
            )
            new_count = 1
        
        await db.commit()
        return new_count

async def reset_violations(user_id: int, trigger_id: int):
    """Сброс счетчика нарушений"""
    async with db_pool.get_connection() as db:
        await db.execute(
            """UPDATE violations 
               SET count = 0, reset_at = ?
               WHERE user_id = ? AND trigger_id = ?""",
            (datetime.now().isoformat(), user_id, trigger_id)
        )
        await db.commit()

async def get_violation_count(user_id: int, trigger_id: int) -> int:
    """Получение количества нарушений"""
    async with db_pool.get_connection() as db:
        async with db.execute(
            "SELECT count FROM violations WHERE user_id = ? AND trigger_id = ?",
            (user_id, trigger_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def cleanup_old_violations(days: int = 30):
    """Очистка старых записей о нарушениях"""
    async with db_pool.get_connection() as db:
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        await db.execute(
            "DELETE FROM violations WHERE last_violation_at < ?",
            (cutoff_date,)
        )
        await db.commit()