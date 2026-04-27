#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BBS VIP — таблицы, CRUD, расчёт цены, global cooldown, атомарная покупка.

Редакция: 2026-04-28 (новые правила VIP1-VIP6, без INSTANT_BUMP).
Подключается в db_manager.py::create_tables() вызовом init_bbs_vip_tables(db).
"""

import json
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ─── МСК (UTC+3) ─────────────────────────────────────────────────────────────
_MSK = timezone(timedelta(hours=3))

def _now_msk() -> datetime:
    return datetime.now(_MSK)

def _now_msk_iso() -> str:
    return _now_msk().strftime('%Y-%m-%d %H:%M:%S')

def _midnight_today_msk_iso() -> str:
    """23:59:59 сегодня по МСК."""
    return _now_msk().strftime('%Y-%m-%d') + ' 23:59:59'


# ─── Константы ───────────────────────────────────────────────────────────────
# Семьи с пинами: их global cooldown НЕ сбрасывается при удалении анкеты
PIN_FAMILIES = frozenset({'SILENT_PIN', 'LOUD_PIN', 'BUMP_PIN'})

# Фиксированные слоты VIP6 (МСК)
PROMO_SLOTS_MSK = ['10:00', '15:00', '21:00']

# Дефолтные цены: (vip_code, vip_family, title, price_rub, duration_h, bump_h, sort)
_DEFAULT_SETTINGS = [
    # VIP1 — событийный BUMP, одна опция 24ч
    ('BUMP',              'BUMP',        'VIP1 — Перепубликация при чужих публикациях', 120.0,  24,  None, 10),
    # VIP2 — тихий закреп, одна опция 24ч
    ('SILENT_PIN',        'SILENT_PIN',  'VIP2 — Тихий закреп',                        250.0,  24,  None, 20),
    # VIP3 — громкий закреп, одна опция 24ч, global cooldown 168ч
    ('LOUD_PIN',          'LOUD_PIN',    'VIP3 — Громкий закреп + уведомление',        1500.0, 24,  None, 30),
    # VIP4 — авто-перепубликация раз в 24ч, три длительности
    ('CUSTOM_BUMP_72H',   'CUSTOM_BUMP', 'VIP4 — Автопубликация 3 дня',                300.0,  72,  24,   40),
    ('CUSTOM_BUMP_120H',  'CUSTOM_BUMP', 'VIP4 — Автопубликация 5 дней',               500.0,  120, 24,   41),
    ('CUSTOM_BUMP_168H',  'CUSTOM_BUMP', 'VIP4 — Автопубликация 7 дней',               700.0,  168, 24,   42),
    # VIP5 — авто-перепубликация + тихий закреп, три длительности
    ('BUMP_PIN_72H',      'BUMP_PIN',    'VIP5 — Автопуб + закреп 3 дня',              700.0,  72,  24,   50),
    ('BUMP_PIN_120H',     'BUMP_PIN',    'VIP5 — Автопуб + закреп 5 дней',             1100.0, 120, 24,   51),
    ('BUMP_PIN_168H',     'BUMP_PIN',    'VIP5 — Автопуб + закреп 7 дней',             1500.0, 168, 24,   52),
    # VIP6 — промо в общий чат, global cooldown до полночи
    ('PROMO_CHAT',        'PROMO_CHAT',  'VIP6 — Промо в общий чат (3 слота)',          300.0,  24,  None, 60),
]


# ════════════════════════════════════════════════════════════════════
# DDL
# ════════════════════════════════════════════════════════════════════

def init_bbs_vip_tables(db) -> None:
    """Создаёт 4 VIP-таблицы и сидирует дефолтные цены."""
    c = db.cursor

    # ── Прайс ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS bbs_vip_settings (
            vip_code             TEXT PRIMARY KEY,
            vip_family           TEXT NOT NULL,
            title                TEXT NOT NULL,
            price_rub            REAL NOT NULL,
            duration_hours       INTEGER,
            bump_interval_hours  INTEGER,
            is_enabled           INTEGER NOT NULL DEFAULT 1,
            sort_order           INTEGER NOT NULL DEFAULT 0,
            updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_bbs_vip_settings_family ON bbs_vip_settings(vip_family)")

    # ── Подписки ─────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS bbs_vip_subscriptions (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id               INTEGER NOT NULL,
            user_id                  INTEGER NOT NULL,
            vip_code                 TEXT NOT NULL,
            vip_family               TEXT NOT NULL,
            purchased_at             TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at               TEXT,
            status                   TEXT NOT NULL DEFAULT 'active',
            bump_interval_hours      INTEGER,
            last_bumped_at           TEXT,
            silent_pin_msg_id        INTEGER,
            loud_pin_msg_id          INTEGER,
            promo_chat_slots_total   INTEGER DEFAULT 0,
            promo_chat_slots_done    INTEGER DEFAULT 0,
            price_rub_paid           REAL NOT NULL,
            price_pulses_paid        REAL NOT NULL,
            pulse_rate_at_purchase   REAL NOT NULL,
            FOREIGN KEY (profile_id) REFERENCES bbs_profiles(id) ON DELETE CASCADE
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_bbs_vip_subs_profile     ON bbs_vip_subscriptions(profile_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bbs_vip_subs_user_family ON bbs_vip_subscriptions(user_id, vip_family)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bbs_vip_subs_status_exp  ON bbs_vip_subscriptions(status, expires_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bbs_vip_subs_bump_queue  ON bbs_vip_subscriptions(status, vip_family, purchased_at)")

    # ── Очередь VIP6 ─────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS bbs_promo_chat_queue (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription_id   INTEGER NOT NULL,
            profile_id        INTEGER NOT NULL,
            user_id           INTEGER NOT NULL,
            scheduled_at      TEXT NOT NULL,
            posted            INTEGER NOT NULL DEFAULT 0,
            posted_at         TEXT,
            posted_msg_ids    TEXT,
            attempts          INTEGER DEFAULT 0,
            FOREIGN KEY (subscription_id) REFERENCES bbs_vip_subscriptions(id) ON DELETE CASCADE
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_promo_queue_pending ON bbs_promo_chat_queue(posted, scheduled_at)")

    # ── Global cooldown VIP3 / VIP6 ──────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS bbs_vip_global_cooldowns (
            vip_family        TEXT PRIMARY KEY,
            locked_until      TEXT NOT NULL,
            locked_by_user_id INTEGER NOT NULL,
            locked_by_sub_id  INTEGER NOT NULL,
            profile_id        INTEGER NOT NULL
        )
    """)

    db.conn.commit()

    # ── Удалить устаревшие SKU (старые коды из прошлой редакции ТЗ) ──
    _OBSOLETE_CODES = [
        'BUMP_24', 'BUMP_48', 'BUMP_72', 'BUMP_168',
        'SILENT_PIN_24', 'SILENT_PIN_48', 'SILENT_PIN_72', 'SILENT_PIN_168',
        'LOUD_PIN_24', 'LOUD_PIN_48', 'LOUD_PIN_72',
        'CUSTOM_BUMP_3H', 'CUSTOM_BUMP_6H', 'CUSTOM_BUMP_12H',
        'BUMP_PIN_24', 'BUMP_PIN_48', 'BUMP_PIN_72',
        'INSTANT_BUMP',
    ]
    for code in _OBSOLETE_CODES:
        c.execute("DELETE FROM bbs_vip_settings WHERE vip_code=?", (code,))
    db.conn.commit()

    # ── Сид актуальных цен (INSERT OR IGNORE — не трогает уже изменённые владельцем) ──
    for code, family, title, price, dur, bump, sort in _DEFAULT_SETTINGS:
        c.execute("""
            INSERT OR IGNORE INTO bbs_vip_settings
                (vip_code, vip_family, title, price_rub, duration_hours,
                 bump_interval_hours, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (code, family, title, price, dur, bump, sort))
    db.conn.commit()

    # ── Миграция: добавить bump_interval_hours если колонка пропала ──
    for col, definition in [
        ('bump_interval_hours', 'INTEGER'),
        ('attempts',            'INTEGER DEFAULT 0'),
    ]:
        try:
            if col == 'attempts':
                c.execute(f"ALTER TABLE bbs_promo_chat_queue ADD COLUMN {col} {definition}")
            else:
                c.execute(f"ALTER TABLE bbs_vip_settings ADD COLUMN {col} {definition}")
            db.conn.commit()
        except Exception:
            pass

    logger.info("✅ BBS VIP tables initialised")


# ════════════════════════════════════════════════════════════════════
# Расчёт цены
# ════════════════════════════════════════════════════════════════════

def calc_pulse_price(rub: float, db) -> float:
    try:
        rate = float(db.get_setting('pulse_rate', '1.42') or '1.42')
    except (ValueError, TypeError):
        rate = 1.42
    if rate <= 0:
        rate = 1.42
    return round(rub / rate, 2)


# ════════════════════════════════════════════════════════════════════
# Прайс-лист
# ════════════════════════════════════════════════════════════════════

def get_vip_settings(db, code: str = None, family: str = None):
    """
    code → одна строка (dict или None).
    family → список строк данной семьи.
    иначе → все активные, sorted by sort_order.
    """
    try:
        if code:
            row = db.cursor.execute(
                "SELECT * FROM bbs_vip_settings WHERE vip_code=?", (code,)
            ).fetchone()
            return dict(row) if row else None
        if family:
            rows = db.cursor.execute(
                "SELECT * FROM bbs_vip_settings WHERE vip_family=? AND is_enabled=1 ORDER BY sort_order",
                (family,)
            ).fetchall()
            return [dict(r) for r in rows]
        rows = db.cursor.execute(
            "SELECT * FROM bbs_vip_settings WHERE is_enabled=1 ORDER BY sort_order"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_vip_settings error: {e}")
        return None


def set_vip_price(db, code: str, price_rub: float) -> bool:
    try:
        db.cursor.execute(
            "UPDATE bbs_vip_settings SET price_rub=?, updated_at=datetime('now') WHERE vip_code=?",
            (round(price_rub, 2), code)
        )
        db.conn.commit()
        return db.cursor.rowcount > 0
    except Exception as e:
        logger.error(f"set_vip_price error: {e}")
        return False


def toggle_vip_service(db, code: str) -> bool | None:
    """Вкл/выкл услугу. Возвращает новое состояние или None при ошибке."""
    try:
        row = db.cursor.execute(
            "SELECT is_enabled FROM bbs_vip_settings WHERE vip_code=?", (code,)
        ).fetchone()
        if not row:
            return None
        new_val = 0 if row[0] else 1
        db.cursor.execute(
            "UPDATE bbs_vip_settings SET is_enabled=?, updated_at=datetime('now') WHERE vip_code=?",
            (new_val, code)
        )
        db.conn.commit()
        return bool(new_val)
    except Exception as e:
        logger.error(f"toggle_vip_service error: {e}")
        return None


# ════════════════════════════════════════════════════════════════════
# Подписки — чтение
# ════════════════════════════════════════════════════════════════════

def get_active_subscriptions(db, profile_id: int) -> list:
    try:
        rows = db.cursor.execute(
            "SELECT * FROM bbs_vip_subscriptions WHERE profile_id=? AND status='active'",
            (profile_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_active_subscriptions error: {e}")
        return []


def get_active_by_family(db, profile_id: int, family: str) -> dict | None:
    """Активная подписка данной семьи у данного профиля."""
    try:
        row = db.cursor.execute("""
            SELECT * FROM bbs_vip_subscriptions
            WHERE profile_id=? AND vip_family=? AND status='active'
            LIMIT 1
        """, (profile_id, family)).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_active_by_family error: {e}")
        return None


def has_active_vip(db, profile_id: int) -> bool:
    """Есть ли хоть одна активная VIP-подписка у профиля (для эмодзи)."""
    try:
        row = db.cursor.execute(
            "SELECT COUNT(*) FROM bbs_vip_subscriptions WHERE profile_id=? AND status='active'",
            (profile_id,)
        ).fetchone()
        return row[0] > 0 if row else False
    except Exception as e:
        logger.error(f"has_active_vip error: {e}")
        return False


def get_all_active_bump_subs(db) -> list:
    """Все активные BUMP (VIP1) в порядке покупки — для VIP1-очереди."""
    try:
        rows = db.cursor.execute("""
            SELECT s.*, p.user_id AS p_user_id
            FROM bbs_vip_subscriptions s
            JOIN bbs_profiles p ON p.id = s.profile_id
            WHERE s.status='active' AND s.vip_family='BUMP' AND p.deleted_at IS NULL
            ORDER BY s.purchased_at ASC
        """).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_all_active_bump_subs error: {e}")
        return []


def get_expired_subscriptions(db) -> list:
    """Подписки с истёкшим expires_at (ещё со статусом active)."""
    try:
        rows = db.cursor.execute("""
            SELECT * FROM bbs_vip_subscriptions
            WHERE status='active' AND expires_at IS NOT NULL AND expires_at <= datetime('now')
        """).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_expired_subscriptions error: {e}")
        return []


def get_due_custom_bump_subs(db) -> list:
    """CUSTOM_BUMP и BUMP_PIN у которых прошло 24ч с last_bumped_at."""
    try:
        rows = db.cursor.execute("""
            SELECT s.*, p.user_id AS p_user_id
            FROM bbs_vip_subscriptions s
            JOIN bbs_profiles p ON p.id = s.profile_id
            WHERE s.status='active'
              AND s.vip_family IN ('CUSTOM_BUMP','BUMP_PIN')
              AND p.deleted_at IS NULL
              AND (s.last_bumped_at IS NULL
                   OR datetime(s.last_bumped_at, '+24 hours') <= datetime('now'))
            ORDER BY s.purchased_at ASC
        """).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_due_custom_bump_subs error: {e}")
        return []


def expire_subscription(db, sub_id: int) -> None:
    try:
        db.cursor.execute(
            "UPDATE bbs_vip_subscriptions SET status='expired' WHERE id=?", (sub_id,)
        )
        db.conn.commit()
    except Exception as e:
        logger.error(f"expire_subscription error: {e}")


def update_last_bumped(db, sub_id: int) -> None:
    try:
        db.cursor.execute(
            "UPDATE bbs_vip_subscriptions SET last_bumped_at=datetime('now') WHERE id=?",
            (sub_id,)
        )
        db.conn.commit()
    except Exception as e:
        logger.error(f"update_last_bumped error: {e}")


def update_pin_msg_id(db, sub_id: int, family: str, msg_id: int) -> None:
    col = 'loud_pin_msg_id' if family == 'LOUD_PIN' else 'silent_pin_msg_id'
    try:
        db.cursor.execute(
            f"UPDATE bbs_vip_subscriptions SET {col}=? WHERE id=?",
            (msg_id, sub_id)
        )
        db.conn.commit()
    except Exception as e:
        logger.error(f"update_pin_msg_id error: {e}")


def cancel_subscriptions_for_profile(db, profile_id: int) -> int:
    """
    Отменить все активные VIP подписки анкеты + дропнуть pending промо-слоты.
    Вызывать при удалении анкеты.
    """
    try:
        db.cursor.execute(
            "UPDATE bbs_vip_subscriptions SET status='cancelled' WHERE profile_id=? AND status='active'",
            (profile_id,)
        )
        cancelled = db.cursor.rowcount
        db.cursor.execute(
            "UPDATE bbs_promo_chat_queue SET posted=2 WHERE profile_id=? AND posted=0",
            (profile_id,)
        )
        dropped = db.cursor.rowcount
        db.conn.commit()
        if cancelled or dropped:
            logger.info(f"VIP cleanup profile={profile_id}: cancelled={cancelled}, dropped={dropped}")
        return cancelled
    except Exception as e:
        logger.error(f"cancel_subscriptions_for_profile error: {e}")
        return 0


def get_pin_message_ids_for_profile(db, profile_id: int) -> list:
    """(sub_id, msg_id) всех закреплений активных подписок анкеты."""
    try:
        rows = db.cursor.execute("""
            SELECT id, silent_pin_msg_id, loud_pin_msg_id
            FROM bbs_vip_subscriptions
            WHERE profile_id=? AND status='active'
        """, (profile_id,)).fetchall()
        result = []
        for r in rows:
            for col in ('silent_pin_msg_id', 'loud_pin_msg_id'):
                try:
                    mid = r[col]
                except Exception:
                    mid = None
                if mid:
                    result.append((r['id'], int(mid)))
        return result
    except Exception as e:
        logger.error(f"get_pin_message_ids_for_profile error: {e}")
        return []


# ════════════════════════════════════════════════════════════════════
# Global cooldown (VIP3 / VIP6)
# ════════════════════════════════════════════════════════════════════

def check_global_cooldown(db, vip_family: str) -> tuple[bool, str | None]:
    """
    ok=True → покупать можно.
    ok=False, locked_until → нельзя, показать таймер.
    """
    try:
        row = db.cursor.execute("""
            SELECT locked_until FROM bbs_vip_global_cooldowns
            WHERE vip_family=? AND locked_until > datetime('now')
        """, (vip_family,)).fetchone()
        if row:
            return False, row[0]
        return True, None
    except Exception as e:
        logger.error(f"check_global_cooldown error: {e}")
        return True, None


def set_global_cooldown(db, vip_family: str, locked_until_iso: str,
                        user_id: int, sub_id: int, profile_id: int) -> None:
    try:
        db.cursor.execute("""
            INSERT OR REPLACE INTO bbs_vip_global_cooldowns
                (vip_family, locked_until, locked_by_user_id, locked_by_sub_id, profile_id)
            VALUES (?, ?, ?, ?, ?)
        """, (vip_family, locked_until_iso, user_id, sub_id, profile_id))
        db.conn.commit()
    except Exception as e:
        logger.error(f"set_global_cooldown error: {e}")


def release_promo_cooldown_if_deleted(db) -> int:
    """
    Сбрасывает global cooldown VIP6 если анкета купившего удалена.
    VIP3 (LOUD_PIN) НЕ трогает — его cooldown остаётся при удалении анкеты.
    Возвращает количество сброшенных строк.
    """
    try:
        db.cursor.execute("""
            DELETE FROM bbs_vip_global_cooldowns
            WHERE vip_family = 'PROMO_CHAT'
              AND EXISTS (
                  SELECT 1 FROM bbs_profiles p
                  WHERE p.id = bbs_vip_global_cooldowns.profile_id
                    AND p.deleted_at IS NOT NULL
              )
        """)
        db.conn.commit()
        return db.cursor.rowcount
    except Exception as e:
        logger.error(f"release_promo_cooldown_if_deleted error: {e}")
        return 0


# ════════════════════════════════════════════════════════════════════
# VIP6 — слоты промо-очереди
# ════════════════════════════════════════════════════════════════════

def _next_promo_slots(count: int = 3) -> list[str]:
    """
    Ближайшие count незаполненных слотов из 10:00/15:00/21:00 МСК.
    Если сегодня все прошли — берёт из следующих дней.
    Возвращает список ISO-строк '2026-04-28 10:00:00'.
    """
    now = _now_msk()
    result = []
    day_offset = 0
    while len(result) < count and day_offset <= 10:
        d = now.date() + timedelta(days=day_offset)
        for slot in PROMO_SLOTS_MSK:
            hh, mm = map(int, slot.split(':'))
            slot_dt = datetime(d.year, d.month, d.day, hh, mm, 0, tzinfo=_MSK)
            if slot_dt > now and len(result) < count:
                result.append(slot_dt.strftime('%Y-%m-%d %H:%M:%S'))
        day_offset += 1
    return result


def enqueue_promo_slots(db, subscription_id: int, profile_id: int, user_id: int) -> list[str]:
    """Ставит 3 ближайших слота в очередь VIP6. Возвращает список scheduled_at."""
    slots = _next_promo_slots(3)
    try:
        for s in slots:
            db.cursor.execute("""
                INSERT INTO bbs_promo_chat_queue
                    (subscription_id, profile_id, user_id, scheduled_at)
                VALUES (?, ?, ?, ?)
            """, (subscription_id, profile_id, user_id, s))
        db.cursor.execute(
            "UPDATE bbs_vip_subscriptions SET promo_chat_slots_total=? WHERE id=?",
            (len(slots), subscription_id)
        )
        db.conn.commit()
    except Exception as e:
        logger.error(f"enqueue_promo_slots error: {e}")
    return slots


def get_next_promo_slot(db) -> dict | None:
    """Следующий незапощенный слот VIP6 у активной (не удалённой) анкеты."""
    try:
        row = db.cursor.execute("""
            SELECT q.*
            FROM bbs_promo_chat_queue q
            JOIN bbs_profiles p ON p.id = q.profile_id
            WHERE q.posted = 0
              AND q.scheduled_at <= datetime('now')
              AND p.deleted_at IS NULL
            ORDER BY q.scheduled_at ASC
            LIMIT 1
        """).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_next_promo_slot error: {e}")
        return None


def mark_promo_slot_posted(db, queue_id: int, sub_id: int, msg_ids: list) -> None:
    try:
        db.cursor.execute("""
            UPDATE bbs_promo_chat_queue
            SET posted=1, posted_at=datetime('now'), posted_msg_ids=?
            WHERE id=?
        """, (json.dumps(msg_ids), queue_id))
        db.cursor.execute(
            "UPDATE bbs_vip_subscriptions SET promo_chat_slots_done=promo_chat_slots_done+1 WHERE id=?",
            (sub_id,)
        )
        db.conn.commit()
    except Exception as e:
        logger.error(f"mark_promo_slot_posted error: {e}")


def increment_promo_attempts(db, queue_id: int) -> None:
    try:
        db.cursor.execute(
            "UPDATE bbs_promo_chat_queue SET attempts=COALESCE(attempts,0)+1 WHERE id=?",
            (queue_id,)
        )
        db.conn.commit()
    except Exception as e:
        logger.error(f"increment_promo_attempts error: {e}")


# ════════════════════════════════════════════════════════════════════
# Атомарная покупка
# ════════════════════════════════════════════════════════════════════

class VipPurchaseError(Exception):
    """Бизнес-ошибка при покупке VIP."""
    def __init__(self, code: str, message: str, extra: dict | None = None):
        super().__init__(message)
        self.code = code
        # Коды: 'not_found' / 'no_profile' / 'global_cooldown' / 'family_active' / 'not_enough'
        self.message = message
        self.extra = extra or {}


def purchase_vip(db, user_id: int, profile_id: int, vip_code: str) -> dict:
    """
    Атомарная покупка VIP-услуги (BEGIN IMMEDIATE).

    Шаги:
      1. Проверка: услуга активна
      2. Проверка: профиль опубликован (deleted_at IS NULL)
      3. Проверка global cooldown (VIP3/VIP6)
      4. Проверка: нет активной подписки той же семьи у profile_id
      5. Проверка: достаточно баланса
      6. Списание пульсов с юзера
      7. Начисление в bank_balance (замкнутый контур)
      8. Лог-транзакция
      9. INSERT bbs_vip_subscriptions
     10. INSERT bbs_vip_global_cooldowns (VIP3/VIP6)
     11. COMMIT
     12. (после коммита) enqueue_promo_slots для VIP6

    Возвращает dict: sub_id, vip_code, vip_family, price_rub, price_pulses,
                     expires_at, slots (список ISO для VIP6).
    Бросает VipPurchaseError при любой бизнес-ошибке.
    """
    # 1. Настройки услуги
    settings = get_vip_settings(db, code=vip_code)
    if not settings or not settings.get('is_enabled'):
        raise VipPurchaseError('not_found', f'Услуга {vip_code} не найдена или отключена.')

    family = settings['vip_family']
    price_rub = float(settings['price_rub'])
    duration_h = settings.get('duration_hours')
    bump_h = settings.get('bump_interval_hours')

    # 2. Профиль
    prof = db.cursor.execute(
        "SELECT id FROM bbs_profiles WHERE id=? AND deleted_at IS NULL", (profile_id,)
    ).fetchone()
    if not prof:
        raise VipPurchaseError('no_profile', 'Опубликуйте анкету сначала.')

    # 3. Global cooldown
    if family in ('LOUD_PIN', 'PROMO_CHAT'):
        ok, locked_until = check_global_cooldown(db, family)
        if not ok:
            raise VipPurchaseError(
                'global_cooldown',
                f'Услуга заблокирована до {locked_until}.',
                {'locked_until': locked_until}
            )

    # 4. Дубль семьи
    existing = get_active_by_family(db, profile_id, family)
    if existing:
        raise VipPurchaseError(
            'family_active',
            f'У вас уже активен {family} до {existing.get("expires_at", "—")}.',
            {'expires_at': existing.get('expires_at')}
        )

    # 5. Баланс
    try:
        rate = float(db.get_setting('pulse_rate', '1.42') or '1.42')
        if rate <= 0:
            rate = 1.42
    except Exception:
        rate = 1.42
    price_pulses = round(price_rub / rate, 2)

    user_row = db.cursor.execute(
        "SELECT balance FROM users WHERE user_id=?", (user_id,)
    ).fetchone()
    if not user_row:
        raise VipPurchaseError('not_enough', 'Пользователь не найден.')
    balance = float(user_row[0] or 0)
    if balance < price_pulses:
        short = round(price_pulses - balance, 2)
        raise VipPurchaseError(
            'not_enough',
            f'Не хватает {short} 💎.',
            {'short': short, 'price_pulses': price_pulses, 'balance': balance}
        )

    # ── Транзакция ──────────────────────────────────────────────────
    now_iso = _now_msk_iso()
    expires_at = None
    if duration_h:
        expires_at = (_now_msk() + timedelta(hours=duration_h)).strftime('%Y-%m-%d %H:%M:%S')

    db.conn.execute("BEGIN IMMEDIATE")
    try:
        # Списание
        db.cursor.execute(
            "UPDATE users SET balance=ROUND(balance-?,2), last_active=? WHERE user_id=?",
            (price_pulses, now_iso, user_id)
        )
        # В банк
        db.cursor.execute("""
            UPDATE settings SET value=ROUND(CAST(value AS REAL)+?,2), updated_at=?
            WHERE key='bank_balance'
        """, (price_pulses, now_iso))
        # Лог
        db.cursor.execute("""
            INSERT INTO transactions (from_user_id, to_user_id, amount, transaction_type, description)
            VALUES (?, NULL, ?, 'vip_purchase', ?)
        """, (user_id, price_pulses, f'VIP: {vip_code}'))

        # Подписка
        db.cursor.execute("""
            INSERT INTO bbs_vip_subscriptions
                (profile_id, user_id, vip_code, vip_family,
                 purchased_at, expires_at, status, bump_interval_hours,
                 price_rub_paid, price_pulses_paid, pulse_rate_at_purchase)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """, (profile_id, user_id, vip_code, family,
              now_iso, expires_at, bump_h,
              price_rub, price_pulses, rate))
        sub_id = db.cursor.lastrowid

        # Global cooldown
        if family == 'LOUD_PIN':
            lock_until = (datetime.fromisoformat(now_iso) + timedelta(hours=168)).strftime('%Y-%m-%d %H:%M:%S')
            db.cursor.execute("""
                INSERT OR REPLACE INTO bbs_vip_global_cooldowns
                    (vip_family, locked_until, locked_by_user_id, locked_by_sub_id, profile_id)
                VALUES ('LOUD_PIN', ?, ?, ?, ?)
            """, (lock_until, user_id, sub_id, profile_id))
        elif family == 'PROMO_CHAT':
            db.cursor.execute("""
                INSERT OR REPLACE INTO bbs_vip_global_cooldowns
                    (vip_family, locked_until, locked_by_user_id, locked_by_sub_id, profile_id)
                VALUES ('PROMO_CHAT', ?, ?, ?, ?)
            """, (_midnight_today_msk_iso(), user_id, sub_id, profile_id))

        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise

    # VIP6: слоты добавляем после коммита (не держим транзакцию открытой)
    slots = []
    if family == 'PROMO_CHAT':
        slots = enqueue_promo_slots(db, sub_id, profile_id, user_id)

    return {
        'sub_id':       sub_id,
        'vip_code':     vip_code,
        'vip_family':   family,
        'price_rub':    price_rub,
        'price_pulses': price_pulses,
        'expires_at':   expires_at,
        'slots':        slots,
    }


# ════════════════════════════════════════════════════════════════════
# Статистика (панель владельца)
# ════════════════════════════════════════════════════════════════════

def count_purchases_stats(db, period_hours: int = None):
    """COUNT + SUM пульсов за период (None = всё время)."""
    try:
        if period_hours:
            row = db.cursor.execute("""
                SELECT COUNT(*) AS cnt, COALESCE(SUM(price_pulses_paid),0) AS revenue
                FROM bbs_vip_subscriptions
                WHERE purchased_at >= datetime('now', ? || ' hours')
            """, (f'-{period_hours}',)).fetchone()
        else:
            row = db.cursor.execute(
                "SELECT COUNT(*) AS cnt, COALESCE(SUM(price_pulses_paid),0) AS revenue FROM bbs_vip_subscriptions"
            ).fetchone()
        return dict(row) if row else {'cnt': 0, 'revenue': 0}
    except Exception as e:
        logger.error(f"count_purchases_stats error: {e}")
        return {'cnt': 0, 'revenue': 0}


def get_vip_stats(db) -> dict:
    """Сводка за 24ч / 7д / 30д / всего + топ-3 услуги."""
    def _p(hours):
        return count_purchases_stats(db, hours)

    try:
        top_rows = db.cursor.execute("""
            SELECT vip_code, COUNT(*) AS cnt
            FROM bbs_vip_subscriptions
            GROUP BY vip_code ORDER BY cnt DESC LIMIT 3
        """).fetchall()
        top3 = [dict(r) for r in top_rows]
    except Exception:
        top3 = []

    return {
        'day':   _p(24),
        'week':  _p(168),
        'month': _p(720),
        'total': count_purchases_stats(db),
        'top3':  top3,
    }


def list_active_subscriptions(db, family: str = None, limit: int = 100) -> list:
    """Активные подписки с именем профиля (для панели владельца)."""
    try:
        if family:
            rows = db.cursor.execute("""
                SELECT s.*, p.name AS profile_name, p.user_id AS profile_user_id
                FROM bbs_vip_subscriptions s
                JOIN bbs_profiles p ON p.id = s.profile_id
                WHERE s.status='active' AND s.vip_family=?
                ORDER BY s.purchased_at DESC LIMIT ?
            """, (family, limit)).fetchall()
        else:
            rows = db.cursor.execute("""
                SELECT s.*, p.name AS profile_name, p.user_id AS profile_user_id
                FROM bbs_vip_subscriptions s
                JOIN bbs_profiles p ON p.id = s.profile_id
                WHERE s.status='active'
                ORDER BY s.purchased_at DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"list_active_subscriptions error: {e}")
        return []


def admin_cancel_subscription(db, sub_id: int) -> bool:
    """Принудительная отмена подписки владельцем."""
    try:
        db.cursor.execute(
            "UPDATE bbs_vip_subscriptions SET status='cancelled' WHERE id=? AND status='active'",
            (sub_id,)
        )
        db.conn.commit()
        return db.cursor.rowcount > 0
    except Exception as e:
        logger.error(f"admin_cancel_subscription error: {e}")
        return False
