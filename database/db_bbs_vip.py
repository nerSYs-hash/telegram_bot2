#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VIP BBS: таблицы, CRUD, расчёт цены."""

import logging

logger = logging.getLogger(__name__)

BBS_VIP_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS bbs_vip_settings (
    vip_code             TEXT PRIMARY KEY,
    vip_family           TEXT NOT NULL,
    title                TEXT NOT NULL,
    price_rub            REAL NOT NULL,
    duration_hours       INTEGER,
    bump_interval_hours  INTEGER,
    cooldown_hours       REAL,
    is_enabled           INTEGER NOT NULL DEFAULT 1,
    sort_order           INTEGER NOT NULL DEFAULT 0,
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_bbs_vip_settings_family ON bbs_vip_settings(vip_family);

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
);
CREATE INDEX IF NOT EXISTS idx_bbs_vip_subs_profile     ON bbs_vip_subscriptions(profile_id);
CREATE INDEX IF NOT EXISTS idx_bbs_vip_subs_user_family ON bbs_vip_subscriptions(user_id, vip_family);
CREATE INDEX IF NOT EXISTS idx_bbs_vip_subs_status_exp  ON bbs_vip_subscriptions(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_bbs_vip_subs_bumped      ON bbs_vip_subscriptions(status, last_bumped_at);

CREATE TABLE IF NOT EXISTS bbs_promo_chat_queue (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id   INTEGER NOT NULL,
    profile_id        INTEGER NOT NULL,
    user_id           INTEGER NOT NULL,
    scheduled_at      TEXT NOT NULL,
    posted            INTEGER NOT NULL DEFAULT 0,
    posted_at         TEXT,
    posted_msg_ids    TEXT,
    FOREIGN KEY (subscription_id) REFERENCES bbs_vip_subscriptions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_promo_queue_pending ON bbs_promo_chat_queue(posted, scheduled_at);
"""

# (code, family, title, price_rub, duration_hours, bump_interval_hours, cooldown_hours, sort_order)
_DEFAULT_SETTINGS = [
    ('BUMP_24',         'BUMP',         'BUMP 24ч',                   120.0,  24,   4,    None, 10),
    ('BUMP_48',         'BUMP',         'BUMP 48ч',                   220.0,  48,   4,    None, 11),
    ('BUMP_72',         'BUMP',         'BUMP 72ч',                   300.0,  72,   4,    None, 12),
    ('BUMP_168',        'BUMP',         'BUMP 168ч',                  600.0,  168,  4,    None, 13),
    ('SILENT_PIN_24',   'SILENT_PIN',   'Тихий закреп 24ч',           250.0,  24,   None, None, 20),
    ('SILENT_PIN_48',   'SILENT_PIN',   'Тихий закреп 48ч',           450.0,  48,   None, None, 21),
    ('SILENT_PIN_72',   'SILENT_PIN',   'Тихий закреп 72ч',           650.0,  72,   None, None, 22),
    ('SILENT_PIN_168',  'SILENT_PIN',   'Тихий закреп 168ч',         1500.0,  168,  None, None, 23),
    ('LOUD_PIN_24',     'LOUD_PIN',     'Громкий закреп 24ч',        1500.0,  24,   None, 168.0, 30),
    ('LOUD_PIN_48',     'LOUD_PIN',     'Громкий закреп 48ч',        2500.0,  48,   None, 168.0, 31),
    ('LOUD_PIN_72',     'LOUD_PIN',     'Громкий закреп 72ч',        3500.0,  72,   None, 168.0, 32),
    ('CUSTOM_BUMP_3H',  'CUSTOM_BUMP',  'Custom Bump каждые 3ч',      800.0,  24,   3,    None, 40),
    ('CUSTOM_BUMP_6H',  'CUSTOM_BUMP',  'Custom Bump каждые 6ч',      500.0,  24,   6,    None, 41),
    ('CUSTOM_BUMP_12H', 'CUSTOM_BUMP',  'Custom Bump каждые 12ч',     300.0,  24,   12,   None, 42),
    ('BUMP_PIN_24',     'BUMP_PIN',     'BUMP+PIN 24ч',               400.0,  24,   4,    None, 50),
    ('BUMP_PIN_48',     'BUMP_PIN',     'BUMP+PIN 48ч',               700.0,  48,   4,    None, 51),
    ('BUMP_PIN_72',     'BUMP_PIN',     'BUMP+PIN 72ч',              1000.0,  72,   4,    None, 52),
    ('PROMO_CHAT',      'PROMO_CHAT',   'Промо в главный чат',        300.0,  24,   None, 24.0,  60),
    ('INSTANT_BUMP',    'INSTANT_BUMP', 'Мгновенный подъём анкеты',    50.0,  None, None, 0.5,   70),
]


def init_bbs_vip_tables(db):
    """Создать VIP BBS таблицы и сидировать дефолтные цены."""
    try:
        db.cursor.executescript(BBS_VIP_TABLES_SQL)
        db.conn.commit()
        for row in _DEFAULT_SETTINGS:
            code, family, title, price_rub, duration_hours, bump_interval_hours, cooldown_hours, sort_order = row
            db.cursor.execute(
                """
                INSERT OR IGNORE INTO bbs_vip_settings
                    (vip_code, vip_family, title, price_rub, duration_hours,
                     bump_interval_hours, cooldown_hours, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (code, family, title, price_rub, duration_hours, bump_interval_hours, cooldown_hours, sort_order),
            )
        db.conn.commit()

        # Миграция: колонка attempts для отслеживания неудачных попыток промо
        try:
            db.cursor.execute(
                "ALTER TABLE bbs_promo_chat_queue ADD COLUMN attempts INTEGER DEFAULT 0"
            )
            db.conn.commit()
        except Exception:
            pass  # колонка уже существует

        logger.info("✅ BBS VIP tables initialized")
    except Exception as e:
        logger.error(f"❌ Error initializing BBS VIP tables: {e}")


def get_vip_settings(db, code=None, family=None):
    """Настройки: по code — одна строка; по family — список; иначе все, sorted by sort_order."""
    try:
        if code:
            db.cursor.execute("SELECT * FROM bbs_vip_settings WHERE vip_code = ?", (code,))
            return db.cursor.fetchone()
        if family:
            db.cursor.execute(
                "SELECT * FROM bbs_vip_settings WHERE vip_family = ? ORDER BY sort_order ASC",
                (family,),
            )
            return db.cursor.fetchall()
        db.cursor.execute("SELECT * FROM bbs_vip_settings ORDER BY sort_order ASC")
        return db.cursor.fetchall()
    except Exception as e:
        logger.error(f"get_vip_settings error: {e}")
        return None


def set_vip_price(db, code, price_rub):
    """Обновить цену VIP услуги."""
    try:
        db.cursor.execute(
            "UPDATE bbs_vip_settings SET price_rub = ?, updated_at = datetime('now') WHERE vip_code = ?",
            (price_rub, code),
        )
        db.conn.commit()
        return db.cursor.rowcount > 0
    except Exception as e:
        logger.error(f"set_vip_price error: {e}")
        return False


def calc_pulse_price(rub: float, db) -> float:
    """Рассчитать цену в Пульсах по текущему курсу из settings.pulse_rate."""
    try:
        rate = float(db.get_setting('pulse_rate', '1.42') or '1.42')
    except (ValueError, TypeError):
        rate = 1.42
    if rate <= 0:
        rate = 1.42
    return round(rub / rate, 2)


def get_active_subscriptions(db, profile_id):
    """Все активные подписки анкеты."""
    try:
        db.cursor.execute(
            "SELECT * FROM bbs_vip_subscriptions WHERE profile_id = ? AND status = 'active'",
            (profile_id,),
        )
        return db.cursor.fetchall()
    except Exception as e:
        logger.error(f"get_active_subscriptions error: {e}")
        return []


def get_active_by_family(db, profile_id, family):
    """Активная подписка конкретной семьи для анкеты (для проверки конфликтов)."""
    try:
        db.cursor.execute(
            "SELECT * FROM bbs_vip_subscriptions WHERE profile_id = ? AND vip_family = ? AND status = 'active'",
            (profile_id, family),
        )
        return db.cursor.fetchone()
    except Exception as e:
        logger.error(f"get_active_by_family error: {e}")
        return None


def check_purchase_cooldown(db, user_id, family) -> tuple:
    """
    Проверить cooldown на покупку по user_id и семье.
    Возвращает (can_buy: bool, retry_at_iso: str|None).
    cooldown_hours REAL — поддерживает дробные значения (0.5 = 30 мин).
    """
    try:
        db.cursor.execute(
            "SELECT cooldown_hours FROM bbs_vip_settings WHERE vip_family = ? AND cooldown_hours IS NOT NULL LIMIT 1",
            (family,),
        )
        row = db.cursor.fetchone()
        if not row:
            return (True, None)
        cooldown_hours = float(row['cooldown_hours'])
        if cooldown_hours <= 0:
            return (True, None)

        db.cursor.execute(
            """
            SELECT purchased_at FROM bbs_vip_subscriptions
            WHERE user_id = ? AND vip_family = ?
            ORDER BY purchased_at DESC LIMIT 1
            """,
            (user_id, family),
        )
        last = db.cursor.fetchone()
        if not last:
            return (True, None)

        # Конвертируем часы в минуты: SQLite не поддерживает дробные часы в datetime модификаторе
        # 0.5 ч = 30 минут, 168 ч = 10080 минут и т.д.
        cooldown_minutes = int(round(cooldown_hours * 60))
        db.cursor.execute(
            """
            SELECT
                datetime(?, '+' || ? || ' minutes') > datetime('now') AS in_cooldown,
                datetime(?, '+' || ? || ' minutes') AS retry_at
            """,
            (last['purchased_at'], cooldown_minutes, last['purchased_at'], cooldown_minutes),
        )
        check = db.cursor.fetchone()
        if check and check['in_cooldown']:
            return (False, check['retry_at'])
        return (True, None)
    except Exception as e:
        logger.error(f"check_purchase_cooldown error: {e}")
        return (True, None)


def count_purchases_stats(db, period_hours: int = None):
    """Статистика: количество и выручка в Пульсах. period_hours=None — за всё время."""
    try:
        if period_hours:
            db.cursor.execute(
                """
                SELECT COUNT(*) AS cnt, COALESCE(SUM(price_pulses_paid), 0) AS revenue
                FROM bbs_vip_subscriptions
                WHERE purchased_at >= datetime('now', '-' || ? || ' hours')
                """,
                (period_hours,),
            )
        else:
            db.cursor.execute(
                "SELECT COUNT(*) AS cnt, COALESCE(SUM(price_pulses_paid), 0) AS revenue FROM bbs_vip_subscriptions"
            )
        return db.cursor.fetchone()
    except Exception as e:
        logger.error(f"count_purchases_stats error: {e}")
        return None


def get_pin_message_ids_for_profile(db, profile_id):
    """
    Возвращает список (sub_id, msg_id) всех закреплений активных VIP подписок анкеты.
    Используется при удалении анкеты, чтобы снять закрепы.
    """
    try:
        db.cursor.execute(
            """
            SELECT id, silent_pin_msg_id, loud_pin_msg_id
            FROM bbs_vip_subscriptions
            WHERE profile_id = ? AND status = 'active'
            """,
            (profile_id,),
        )
        rows = db.cursor.fetchall()
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


def cancel_subscriptions_for_profile(db, profile_id):
    """
    Отменить все активные VIP подписки анкеты + дропнуть pending промо-слоты.
    Вызывать при удалении анкеты пользователем/админом/системой.
    """
    try:
        db.cursor.execute(
            "UPDATE bbs_vip_subscriptions SET status = 'cancelled' "
            "WHERE profile_id = ? AND status = 'active'",
            (profile_id,),
        )
        cancelled = db.cursor.rowcount
        # posted=2 — failed/dropped, чтобы dispatcher не пытался публиковать удалённую анкету
        db.cursor.execute(
            "UPDATE bbs_promo_chat_queue SET posted = 2 "
            "WHERE profile_id = ? AND posted = 0",
            (profile_id,),
        )
        dropped = db.cursor.rowcount
        db.conn.commit()
        if cancelled or dropped:
            logger.info(
                f"VIP cleanup for profile={profile_id}: "
                f"cancelled={cancelled} subs, dropped={dropped} promo slots"
            )
        return cancelled
    except Exception as e:
        logger.error(f"cancel_subscriptions_for_profile error: {e}")
        return 0


def list_active_subscriptions(db, family=None, limit=100):
    """Активные подписки с JOIN на bbs_profiles для имени анкеты."""
    try:
        if family:
            db.cursor.execute(
                """
                SELECT s.*, p.user_id AS profile_user_id, p.name AS profile_name
                FROM bbs_vip_subscriptions s
                JOIN bbs_profiles p ON p.id = s.profile_id
                WHERE s.status = 'active' AND s.vip_family = ?
                ORDER BY s.purchased_at DESC
                LIMIT ?
                """,
                (family, limit),
            )
        else:
            db.cursor.execute(
                """
                SELECT s.*, p.user_id AS profile_user_id, p.name AS profile_name
                FROM bbs_vip_subscriptions s
                JOIN bbs_profiles p ON p.id = s.profile_id
                WHERE s.status = 'active'
                ORDER BY s.purchased_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        return db.cursor.fetchall()
    except Exception as e:
        logger.error(f"list_active_subscriptions error: {e}")
        return []
