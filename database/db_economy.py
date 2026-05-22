"""
Модуль управления настройками экономики.
4 таблицы: economy_settings, economy_section_toggles, economy_history, economy_cancellations

Все публичные DB-функции принимают workspace_id первым аргументом после db.
TODO(multi-tenancy-pk): см. database/migrations/multi_tenancy.py — composite PK долг.
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── DDL ──────────────────────────────────────────────────────────────────────

ECONOMY_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS economy_settings (
    key            TEXT PRIMARY KEY,
    category       TEXT NOT NULL,
    subcategory    TEXT,
    label          TEXT NOT NULL,
    description    TEXT,
    value          TEXT NOT NULL,
    value_type     TEXT NOT NULL,
    unit           TEXT DEFAULT '',
    min_value      REAL,
    max_value      REAL,
    is_enabled     INTEGER NOT NULL DEFAULT 1,
    is_hidden      INTEGER NOT NULL DEFAULT 0,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_economy_settings_category ON economy_settings(category);
CREATE INDEX IF NOT EXISTS idx_economy_settings_sort     ON economy_settings(category, sort_order);

CREATE TABLE IF NOT EXISTS economy_section_toggles (
    category       TEXT PRIMARY KEY,
    is_enabled     INTEGER NOT NULL DEFAULT 1,
    updated_by     INTEGER,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS economy_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key     TEXT NOT NULL,
    action          TEXT NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    old_enabled     INTEGER,
    new_enabled     INTEGER,
    comment         TEXT NOT NULL,
    changed_by      INTEGER NOT NULL,
    changed_by_role TEXT NOT NULL,
    rollback_of     INTEGER,
    changed_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (rollback_of) REFERENCES economy_history(id)
);
CREATE INDEX IF NOT EXISTS idx_economy_history_key  ON economy_history(setting_key, changed_at);
CREATE INDEX IF NOT EXISTS idx_economy_history_user ON economy_history(changed_by, changed_at);
CREATE INDEX IF NOT EXISTS idx_economy_history_date ON economy_history(changed_at);

CREATE TABLE IF NOT EXISTS economy_cancellations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cancellation_type   TEXT NOT NULL,
    target_user_id      INTEGER,
    source_tx_id        INTEGER,
    source_filter       TEXT,
    amount              REAL NOT NULL,
    affected_users      INTEGER,
    mode                TEXT NOT NULL,
    actually_deducted   REAL DEFAULT 0,
    comment             TEXT NOT NULL,
    executed_by         INTEGER NOT NULL,
    executed_by_role    TEXT NOT NULL,
    executed_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_economy_cancel_user ON economy_cancellations(target_user_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_economy_cancel_date ON economy_cancellations(executed_at);
"""

# ── SEED DATA ────────────────────────────────────────────────────────────────

# (key, category, subcategory, label, description, value, value_type, unit, min, max, sort_order)
SEED_ECONOMY_SETTINGS = [
    ('mining.per_reaction_given',       'mining', 'base',    'За поставленную реакцию',    'Начисляется автору реакции (задним числом)',    '0.002','float', '💎', 0,    100,    11),
    ('mining.per_reaction_received',    'mining', 'base',    'За полученную реакцию',      'Начисляется автору поста когда его лайкнули',   '0.002','float', '💎', 0,    100,    12),
    ('mining.per_reply',                'mining', 'base',    'За реплай (автору поста)',   'Начисляется автору поста когда ему ответили',   '0.002','float', '💎', 0,    100,    13),

    ('shipper.resonance_multiplier',    'mining', 'shipper', 'Множитель резонанса',        'Бонус к майнингу после матча шиппера',          '2.0',  'float', 'x',  1,    10,     50),
    ('shipper.resonance_duration_hours','mining', 'shipper', 'Длительность буста',         'Часов действия резонанса',                      '24',   'int',   'ч',  1,    168,    51),

    ('defib.buff_multiplier',            'mining', 'defib',   'Множитель дефибриллятора',   'Бонус к майнингу при дефибрилляторе','3.0', 'float', 'x',  1,    10,     60),
    ('defib.buff_duration_min',         'mining', 'defib',   'Длительность буста (мин)',   'Минут действия дефибриллятора',                 '10',   'int',   'мин',1,   120,    61),
    ('defib.silence_min_minutes',       'mining', 'defib',   'Мин. тишина для активации',  'Чат должен молчать минимум N минут',            '5',    'int',   'мин',1,   60,     62),
    ('defib.silence_max_minutes',       'mining', 'defib',   'Макс. тишина (рандом до)',   'Верхняя граница рандомного порога тишины',      '15',   'int',   'мин',1,   120,    63),

    # ── Базовая ставка (мультипликатор для коэффициентов) ─────────────────
    ('mining.global_rate',              'mining', 'base',    'Базовая ставка',             'Единый множитель: итог = Σ коэф × базовую ставку',      '0.002','float', 'x',  0.0001, 1.0, 9),

    # ── Базовые коэффициенты контента ─────────────────────────────────────
    ('base.text_message',              'mining', 'base_coeff', 'Текстовое сообщение',      'Коэфф за обычный текст',                        '1',    'int',   'x',  0, 1000, 20),
    ('base.emoji_only',                'mining', 'base_coeff', 'Только эмодзи',            'Коэфф за сообщение из эмодзи',                  '1',    'int',   'x',  0, 1000, 21),
    ('base.photo',                     'mining', 'base_coeff', 'Фото',                     'Коэфф за фотографию',                           '2',    'int',   'x',  0, 1000, 22),
    ('base.photo_album_special_thread','mining', 'base_coeff', 'Фотоальбом (спец. тема)',  'Коэфф за альбом 2+ фото в тематической ветке',  '6',    'int',   'x',  0, 1000, 23),
    ('base.video_regular',             'mining', 'base_coeff', 'Видео',                    'Коэфф за обычное видео',                        '5',    'int',   'x',  0, 1000, 24),
    ('base.video_note',                'mining', 'base_coeff', 'Видеосообщение',            'Коэфф за видеокружок',                          '7',    'int',   'x',  0, 1000, 25),
    ('base.audio_or_link',             'mining', 'base_coeff', 'Аудио / ссылка',           'Коэфф за аудио или ссылку',                     '2',    'int',   'x',  0, 1000, 26),
    ('base.voice',                     'mining', 'base_coeff', 'Голосовое',                'Коэфф за голосовое сообщение',                  '3',    'int',   'x',  0, 1000, 27),
    ('base.gif',                       'mining', 'base_coeff', 'GIF',                      'Коэфф за анимацию/гифку',                       '1',    'int',   'x',  0, 1000, 28),
    ('base.reply_sent',                'mining', 'base_coeff', 'Отправлен ответ',          'Коэфф за реплай на чужое сообщение',            '1',    'int',   'x',  0, 1000, 29),
    ('base.reply_received',            'mining', 'base_coeff', 'Получен ответ',            'Коэфф: автору поста когда ему ответили',         '1',    'int',   'x',  0, 1000, 30),
    ('base.reaction_given',            'mining', 'base_coeff', 'Поставлена реакция',       'Коэфф: тому кто лайкнул',                       '1',    'int',   'x',  0, 1000, 31),
    ('base.reaction_received',         'mining', 'base_coeff', 'Получена реакция',         'Коэфф: автору поста который лайкнули',          '1',    'int',   'x',  0, 1000, 32),

    # ── Штрафы ────────────────────────────────────────────────────────────
    ('penalty.copypaste',              'mining', 'penalty',    'Копипаст',                 'Штраф за дублирование своего же текста за 1ч',  '-50',  'int',   'x', -10000, 0, 40),
    ('penalty.wrong_door',             'mining', 'penalty',    'Не та дверь',              'Штраф за контент не по теме ветки',             '-50',  'int',   'x', -10000, 0, 41),
    ('penalty.toxic',                  'mining', 'penalty',    'Токсик',                   'Штраф за токсичное сообщение',   '-100', 'int',   'x', -10000, 0, 42),

    # ── Комбо-квесты (1 раз в 24 ч, instant при отправке) ─────────────────
    ('combo.writer',       'mining', 'combo', 'Писатель',      'Текст > 50 символов → коэфф × базовую ставку',            '20',  'int', 'x', 0, 10000, 70),
    ('combo.illustrator',  'mining', 'combo', 'Иллюстратор',   'Текст > 50 символов + фото → коэфф × базовую ставку',    '40',  'int', 'x', 0, 10000, 71),
    ('combo.reviewer',     'mining', 'combo', 'Рецензент',     'Видео + текст > 100 слов → коэфф × базовую ставку',      '40',  'int', 'x', 0, 10000, 72),
    ('combo.dj',           'mining', 'combo', 'DJ',            'Ссылка на плейлист → коэфф × базовую ставку',             '30',  'int', 'x', 0, 10000, 73),
    ('combo.sharp_tongue', 'mining', 'combo', 'Острослов',     '> 2 ответов на пост (за сутки) → коэфф × базовую ставку', '6',   'int', 'x', 0, 10000, 74),
    ('combo.viral_post',   'mining', 'combo', 'Вирусный пост', '> 2 реакций на пост → коэфф × базовую ставку',            '3',   'int', 'x', 0, 10000, 75),
    ('combo.hit_post',     'mining', 'combo', 'Хит',           '4+ реакций на пост → коэфф × базовую ставку',             '10',  'int', 'x', 0, 10000, 76),
    ('combo.legend_post',  'mining', 'combo', 'Легенда',       '6+ реакций на пост → коэфф × базовую ставку',             '20',  'int', 'x', 0, 10000, 77),

    # ── Спринты (накопительные квесты за временное окно) ──────────────────
    ('sprint.chat_core',    'mining', 'sprint', '💬 Основа чата',    'цель 10 сообщ. / окно 12ч / любая тема',          '50',  'int', 'x', 0, 100000, 80),
    ('sprint.emotional',    'mining', 'sprint', '😍 Эмоциональный',  'цель 10 эмодзи-сообщ. / окно 24ч',                '20',  'int', 'x', 0, 100000, 81),
    ('sprint.photographer', 'mining', 'sprint', '📸 Фотограф',       'цель 3 фото / окно 24ч',                           '40',  'int', 'x', 0, 100000, 82),
    ('sprint.director',     'mining', 'sprint', '🎬 Режиссёр',       'цель 2 видео / окно 24ч / темы видео',             '140', 'int', 'x', 0, 100000, 83),
    ('sprint.music_lover',  'mining', 'sprint', '🎧 Меломан',        'цель 5 аудио / окно 24ч / тема музыки',            '120', 'int', 'x', 0, 100000, 84),
    ('sprint.face_seller',  'mining', 'sprint', '🫧 Лицом торгуешь', 'цель 5 видеосообщ. / окно 12ч',                    '60',  'int', 'x', 0, 100000, 85),
    ('sprint.center',       'mining', 'sprint', '🎯 Центр внимания', 'цель 20 полученных ответов / окно 12ч',            '50',  'int', 'x', 0, 100000, 86),
    ('sprint.radio',        'mining', 'sprint', '🎙 Радио',          'цель 4 голосовых / окно 1ч',                       '20',  'int', 'x', 0, 100000, 87),
    ('sprint.gif_room',     'mining', 'sprint', '🎞 Гифошная',       'цель 10 гифок / окно 1ч',                          '30',  'int', 'x', 0, 100000, 88),
    ('sprint.chatterbox',   'mining', 'sprint', '🗣 Болтун',         'цель 20 отправленных ответов / окно 1ч',           '40',  'int', 'x', 0, 100000, 89),
    ('sprint.generous',     'mining', 'sprint', '💝 Щедрая душа',    'цель 5 поставленных реакций / окно 1ч',            '20',  'int', 'x', 0, 100000, 90),
    ('sprint.favorite',     'mining', 'sprint', '⭐ Любимчик',       'цель 10 полученных реакций / окно 1ч',             '40',  'int', 'x', 0, 100000, 91),

    ('lottery.default_ticket_price',    'lottery','base',    'Цена билета по умолчанию',   'Стоимость одного билета в лотерее',             '10',   'int',   '💎', 1,    1000,   10),
    ('lottery.bank_commission_pct',     'lottery','base',    'Комиссия банку',             'Процент от пула идёт в банк',                   '10',   'int',   '%',  0,    100,    11),
    ('lottery.min_tickets_to_draw',     'lottery','base',    'Минимум билетов для розыгрыша','Меньше этого — лотерея не разыгрывается',     '3',    'int',   'шт', 1,    1000,   12),

    ('bingo.card_price',                'bingo',  'base',    'Стоимость карточки',         'Цена одной карточки бинго',                     '5',    'int',   '💎', 1,    1000,   10),
    ('bingo.prize_default',             'bingo',  'base',    'Дефолтный приз',             'Приз за победу в бинго',                        '50',   'int',   '💎', 1,    100000, 11),
    ('bingo.bingo_multiplier',          'bingo',  'base',    'Множитель за бинго',         'Умножается на базовый приз',                    '2.0',  'float', 'x',  1,    10,     12),

    ('monthly_gift.default_amount',     'monthly_gift','base','Размер приза по умолчанию', 'Базовый приз подарка месяца',                   '500',  'int',   '💎', 1,    1000000,10),
    ('monthly_gift.condition_min_messages','monthly_gift','base','Минимум сообщений',      'Нужно написать для участия',                    '10',   'int',   'шт', 1,    10000,  11),
    ('monthly_gift.draw_day',           'monthly_gift','base','День розыгрыша',            'Число месяца для автоматического розыгрыша',    '1',    'int',   'день',1,   28,     12),

    ('referral.qualified_reward',       'referral','base',   'Награда за реферала',        'Начисляется при квалификации друга',            '100',  'int',   '💎', 1,    10000,  10),
    ('referral.qualification_messages', 'referral','base',   'Минимум сообщений друга',    'Сколько сообщений должен написать реферал',     '5',    'int',   'шт', 1,    1000,   11),
    ('referral.qualification_reactions','referral','base',   'Альтернатива: реакций',      'Или столько реакций вместо сообщений',          '3',    'int',   'шт', 1,    1000,   12),
    ('referral.qualification_hours',    'referral','base',   'Должен пробыть (часов)',     'Минимальное время нахождения в чате',           '24',   'int',   'ч',  1,    720,    13),

    ('bbs.bonus_per_reaction',          'bbs_bonus','base',  '💎 за реакцию на анкету',   'Начисляется автору анкеты за каждую реакцию',  '5',    'int',   '💎', 0,    1000,   10),
    ('bbs.bonus_max_per_profile',       'bbs_bonus','base',  'Максимум 💎 с одной анкеты','Потолок бонуса за одну анкету',                 '50',   'int',   '💎', 0,    10000,  11),
]

CATEGORIES_META = [
    # (key, label, icon, sort_order)
    ('mining',       '💰 Майнинг',                  'Coins',        1),
    ('vip_bbs',      '💎 VIP BBS',                  'Sparkles',     2),
    ('lottery',      '🎰 Лотерея',                  'Dices',        3),
    ('bingo',        '🎱 Бинго',                    'Dices',        4),
    ('monthly_gift', '🎁 Подарок месяца',           'PartyPopper',  5),
    ('referral',     '👥 Реферальная программа',    'UserCheck',    6),
    ('bbs_bonus',    '❤️ BBS — бонус за реакции',  'Heart',        7),
]

# ── INIT ─────────────────────────────────────────────────────────────────────

def init_economy_tables(db) -> None:
    """Создаёт 4 таблицы и сидирует дефолтные значения. Безопасно вызывать многократно.
    Сидинг идёт без явного workspace_id → попадает в DEFAULT 1 (Pulse Москва)."""
    try:
        for statement in ECONOMY_TABLES_SQL.strip().split(';'):
            s = statement.strip()
            if s:
                db.cursor.execute(s)
        db.conn.commit()
        _seed_economy_settings(db)
        _seed_section_toggles(db)
        logger.info("✅ economy: таблицы созданы/проверены")
    except Exception as e:
        logger.error(f"init_economy_tables error: {e}")


def _seed_economy_settings(db) -> None:
    for row in SEED_ECONOMY_SETTINGS:
        db.cursor.execute(
            "INSERT OR IGNORE INTO economy_settings "
            "(key, category, subcategory, label, description, value, value_type, unit, min_value, max_value, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row
        )
    db.conn.commit()


def _seed_section_toggles(db) -> None:
    for key, _label, _icon, _sort in CATEGORIES_META:
        db.cursor.execute(
            "INSERT OR IGNORE INTO economy_section_toggles (category, is_enabled) VALUES (?, 1)",
            (key,)
        )
    db.conn.commit()


# ── READ ──────────────────────────────────────────────────────────────────────

def get_econ(db, workspace_id: int, key: str, default=None, value_type: str = 'float'):
    """Читает значение настройки экономики. Без кеша — всегда актуальное."""
    try:
        db.cursor.execute(
            "SELECT value, value_type, is_enabled FROM economy_settings "
            "WHERE workspace_id = ? AND key = ?",
            (workspace_id, key)
        )
        row = db.cursor.fetchone()
        if not row or not row['is_enabled']:
            return default
        raw = row['value']
        vt = row['value_type'] or value_type
        if vt == 'int':   return int(raw)
        if vt == 'float': return float(raw)
        if vt == 'bool':  return raw == '1'
        if vt == 'json':  return json.loads(raw)
        return raw
    except Exception:
        return default


def is_section_enabled(db, workspace_id: int, category: str) -> bool:
    """Проверяет мастер-свич раздела. По умолчанию True если записи нет."""
    try:
        db.cursor.execute(
            "SELECT is_enabled FROM economy_section_toggles "
            "WHERE workspace_id = ? AND category = ?",
            (workspace_id, category)
        )
        row = db.cursor.fetchone()
        return row['is_enabled'] == 1 if row else True
    except Exception:
        return True


def get_econ_categories(db, workspace_id: int) -> list:
    """Список категорий с метаданными для аккордеона."""
    result = []
    try:
        for key, label, icon, sort_order in CATEGORIES_META:
            db.cursor.execute(
                "SELECT COUNT(*) as cnt FROM economy_settings "
                "WHERE workspace_id = ? AND category = ?",
                (workspace_id, key)
            )
            cnt_row = db.cursor.fetchone()
            rows_count = cnt_row['cnt'] if cnt_row else 0

            db.cursor.execute(
                "SELECT is_enabled FROM economy_section_toggles "
                "WHERE workspace_id = ? AND category = ?",
                (workspace_id, key)
            )
            toggle_row = db.cursor.fetchone()
            is_enabled = toggle_row['is_enabled'] == 1 if toggle_row else True

            db.cursor.execute(
                "SELECT subcategory, COUNT(*) as cnt FROM economy_settings "
                "WHERE workspace_id = ? AND category = ? "
                "GROUP BY subcategory ORDER BY MIN(sort_order)",
                (workspace_id, key)
            )
            subs = []
            for sub_row in db.cursor.fetchall():
                subs.append({
                    "key": sub_row['subcategory'] or 'base',
                    "label": sub_row['subcategory'] or 'base',
                    "rows_count": sub_row['cnt'],
                })

            result.append({
                "key":        key,
                "label":      label,
                "icon":       icon,
                "is_enabled": is_enabled,
                "rows_count": rows_count,
                "subcategories": subs,
            })
    except Exception as e:
        logger.error(f"get_econ_categories error: {e}")
    return result


def get_econ_settings(db, workspace_id: int, category: str = None, subcategory: str = None) -> list:
    """Настройки по категории (и опционально подкатегории)."""
    try:
        sql = """
            SELECT s.*,
                   (SELECT COUNT(*) FROM economy_history h
                    WHERE h.workspace_id = s.workspace_id AND h.setting_key = s.key) as history_count,
                   (SELECT h2.changed_at FROM economy_history h2
                    WHERE h2.workspace_id = s.workspace_id AND h2.setting_key = s.key
                    ORDER BY h2.changed_at DESC LIMIT 1) as last_change
            FROM economy_settings s
            WHERE s.workspace_id = ?
        """
        params = [workspace_id]
        if category:
            sql += " AND s.category = ?"
            params.append(category)
        if subcategory:
            sql += " AND s.subcategory = ?"
            params.append(subcategory)
        sql += " ORDER BY s.sort_order"

        db.cursor.execute(sql, params)
        rows = db.cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "key":          r['key'],
                "category":     r['category'],
                "subcategory":  r['subcategory'],
                "label":        r['label'],
                "description":  r['description'],
                "value":        _parse_value(r['value'], r['value_type']),
                "value_type":   r['value_type'],
                "unit":         r['unit'] or '',
                "min_value":    r['min_value'],
                "max_value":    r['max_value'],
                "is_enabled":   bool(r['is_enabled']),
                "is_hidden":    bool(r['is_hidden']),
                "sort_order":   r['sort_order'],
                "history_count": r['history_count'] or 0,
                "last_change":  r['last_change'],
                "created_at":   r['created_at'],
                "updated_at":   r['updated_at'],
            })
        return result
    except Exception as e:
        logger.error(f"get_econ_settings error: {e}")
        return []


# ── WRITE ─────────────────────────────────────────────────────────────────────

def set_econ(db, workspace_id: int, key: str, value, comment: str, changed_by: int, changed_by_role: str) -> dict:
    """Обновляет значение настройки + пишет историю. Атомарно."""
    db.cursor.execute(
        "SELECT value, value_type, min_value, max_value FROM economy_settings "
        "WHERE workspace_id = ? AND key = ?",
        (workspace_id, key)
    )
    row = db.cursor.fetchone()
    if not row:
        raise ValueError(f"Настройка '{key}' не найдена")

    old_value = row['value']
    vt = row['value_type']
    new_value_str = _validate_and_stringify(value, vt, row['min_value'], row['max_value'])

    db.cursor.execute("BEGIN IMMEDIATE")
    try:
        db.cursor.execute(
            "UPDATE economy_settings SET value = ?, updated_at = datetime('now') "
            "WHERE workspace_id = ? AND key = ?",
            (new_value_str, workspace_id, key)
        )
        db.cursor.execute(
            "INSERT INTO economy_history "
            "(workspace_id, setting_key, action, old_value, new_value, comment, changed_by, changed_by_role) "
            "VALUES (?, ?, 'edit', ?, ?, ?, ?, ?)",
            (workspace_id, key, old_value, new_value_str, comment, changed_by, changed_by_role)
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise

    return {
        "key": key,
        "old_value": _parse_value(old_value, vt),
        "new_value": _parse_value(new_value_str, vt),
    }


def toggle_econ(db, workspace_id: int, key: str, comment: str, changed_by: int, changed_by_role: str) -> dict:
    """Переключает is_enabled строки настройки."""
    db.cursor.execute(
        "SELECT is_enabled FROM economy_settings WHERE workspace_id = ? AND key = ?",
        (workspace_id, key)
    )
    row = db.cursor.fetchone()
    if not row:
        raise ValueError(f"Настройка '{key}' не найдена")

    old_enabled = row['is_enabled']
    new_enabled = 0 if old_enabled else 1

    db.cursor.execute("BEGIN IMMEDIATE")
    try:
        db.cursor.execute(
            "UPDATE economy_settings SET is_enabled = ?, updated_at = datetime('now') "
            "WHERE workspace_id = ? AND key = ?",
            (new_enabled, workspace_id, key)
        )
        db.cursor.execute(
            "INSERT INTO economy_history "
            "(workspace_id, setting_key, action, old_enabled, new_enabled, comment, changed_by, changed_by_role) "
            "VALUES (?, ?, 'toggle', ?, ?, ?, ?, ?)",
            (workspace_id, key, old_enabled, new_enabled, comment, changed_by, changed_by_role)
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise

    return {"key": key, "is_enabled": bool(new_enabled)}


def toggle_section(db, workspace_id: int, category: str, comment: str, changed_by: int, changed_by_role: str) -> dict:
    """Мастер-свич раздела."""
    db.cursor.execute(
        "SELECT is_enabled FROM economy_section_toggles "
        "WHERE workspace_id = ? AND category = ?",
        (workspace_id, category)
    )
    row = db.cursor.fetchone()
    old_enabled = row['is_enabled'] if row else 1
    new_enabled = 0 if old_enabled else 1

    db.cursor.execute("BEGIN IMMEDIATE")
    try:
        db.cursor.execute(
            "INSERT OR REPLACE INTO economy_section_toggles "
            "(workspace_id, category, is_enabled, updated_by, updated_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (workspace_id, category, new_enabled, changed_by)
        )
        setting_key = f"@category.{category}"
        db.cursor.execute(
            "INSERT INTO economy_history "
            "(workspace_id, setting_key, action, old_enabled, new_enabled, comment, changed_by, changed_by_role) "
            "VALUES (?, ?, 'toggle', ?, ?, ?, ?, ?)",
            (workspace_id, setting_key, old_enabled, new_enabled, comment, changed_by, changed_by_role)
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise

    return {"category": category, "is_enabled": bool(new_enabled)}


def rollback_econ(db, workspace_id: int, history_id: int, comment: str, changed_by: int, changed_by_role: str) -> dict:
    """Откат к old_value конкретной записи истории."""
    db.cursor.execute(
        "SELECT h.*, s.value_type FROM economy_history h "
        "LEFT JOIN economy_settings s ON s.key = h.setting_key AND s.workspace_id = h.workspace_id "
        "WHERE h.workspace_id = ? AND h.id = ?",
        (workspace_id, history_id)
    )
    h_row = db.cursor.fetchone()
    if not h_row:
        raise ValueError(f"Запись истории {history_id} не найдена")
    if not h_row['old_value']:
        raise ValueError("Нет старого значения для отката")

    key = h_row['setting_key']
    restore_value = h_row['old_value']
    vt = h_row['value_type'] or 'float'

    db.cursor.execute(
        "SELECT value FROM economy_settings WHERE workspace_id = ? AND key = ?",
        (workspace_id, key)
    )
    cur_row = db.cursor.fetchone()
    if not cur_row:
        raise ValueError(f"Настройка '{key}' не найдена")
    current_value = cur_row['value']

    db.cursor.execute("BEGIN IMMEDIATE")
    try:
        db.cursor.execute(
            "UPDATE economy_settings SET value = ?, updated_at = datetime('now') "
            "WHERE workspace_id = ? AND key = ?",
            (restore_value, workspace_id, key)
        )
        db.cursor.execute(
            "INSERT INTO economy_history "
            "(workspace_id, setting_key, action, old_value, new_value, comment, changed_by, changed_by_role, rollback_of) "
            "VALUES (?, ?, 'rollback', ?, ?, ?, ?, ?, ?)",
            (workspace_id, key, current_value, restore_value, comment, changed_by, changed_by_role, history_id)
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise

    return {
        "key": key,
        "restored_to": _parse_value(restore_value, vt),
        "from_value": _parse_value(current_value, vt),
    }


# ── CANCELLATIONS ─────────────────────────────────────────────────────────────

def cancel_pointwise(db, workspace_id: int, tx_id: int, mode: str, comment: str,
                     executed_by: int, executed_by_role: str) -> dict:
    """Точечная отмена выплаты. mode: deduct / debt / log_only.

    transactions фильтруется по workspace_id (тенантизированная таблица).
    users — глобальная таблица, балансы общие. settings — глобальная (банк)."""
    db.cursor.execute(
        "SELECT id, to_user_id, amount FROM transactions "
        "WHERE workspace_id = ? AND id = ?",
        (workspace_id, tx_id)
    )
    tx = db.cursor.fetchone()
    if not tx:
        raise ValueError(f"Транзакция {tx_id} не найдена")

    db.cursor.execute(
        "SELECT id FROM economy_cancellations "
        "WHERE workspace_id = ? AND source_tx_id = ? AND mode != 'log_only'",
        (workspace_id, tx_id)
    )
    if db.cursor.fetchone():
        raise ValueError("Эта транзакция уже была отменена")

    user_id = tx['to_user_id']
    amount = float(tx['amount'])
    actually_deducted = 0.0

    db.cursor.execute("BEGIN IMMEDIATE")
    try:
        if mode == 'deduct':
            db.cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            u = db.cursor.fetchone()
            if not u or float(u['balance']) < amount:
                db.conn.rollback()
                bal = float(u['balance']) if u else 0
                raise ValueError(
                    f"У юзера {bal:.1f} 💎, доступно меньше — выберите Долг или Только лог"
                )
            db.cursor.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id)
            )
            db.cursor.execute(
                "UPDATE settings SET value = CAST(CAST(value AS REAL) + ? AS TEXT) WHERE key = 'bank_balance'",
                (amount,)
            )
            db.cursor.execute(
                "INSERT INTO transactions "
                "(workspace_id, from_user_id, to_user_id, amount, transaction_type, description) "
                "VALUES (?, ?, NULL, ?, 'cancel_deduct', ?)",
                (workspace_id, user_id, amount, comment)
            )
            actually_deducted = amount

        elif mode == 'debt':
            db.cursor.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id)
            )
            db.cursor.execute(
                "UPDATE settings SET value = CAST(CAST(value AS REAL) + ? AS TEXT) WHERE key = 'bank_balance'",
                (amount,)
            )
            db.cursor.execute(
                "INSERT INTO transactions "
                "(workspace_id, from_user_id, to_user_id, amount, transaction_type, description) "
                "VALUES (?, ?, NULL, ?, 'cancel_debt', ?)",
                (workspace_id, user_id, amount, comment)
            )
            actually_deducted = amount

        # log_only — ничего с балансами не делаем

        db.cursor.execute(
            "INSERT INTO economy_cancellations "
            "(workspace_id, cancellation_type, target_user_id, source_tx_id, amount, mode, "
            " actually_deducted, comment, executed_by, executed_by_role) "
            "VALUES (?, 'pointwise', ?, ?, ?, ?, ?, ?, ?, ?)",
            (workspace_id, user_id, tx_id, amount, mode, actually_deducted,
             comment, executed_by, executed_by_role)
        )
        db.conn.commit()
    except ValueError:
        raise
    except Exception:
        db.conn.rollback()
        raise

    return {"ok": True, "mode": mode, "amount": amount, "actually_deducted": actually_deducted}


def cancel_mass(db, workspace_id: int, filter_dict: dict, mode: str, comment: str,
                executed_by: int, executed_by_role: str) -> dict:
    """Массовая отмена — только log_only."""
    category = filter_dict.get('category', '')
    date_from = filter_dict.get('date_from', '')
    date_to = filter_dict.get('date_to', '')
    user_ids = filter_dict.get('user_ids')

    sql = (
        "SELECT id, to_user_id, amount FROM transactions "
        "WHERE workspace_id = ? "
        "AND transaction_type LIKE ? "
        "AND DATE(timestamp) BETWEEN ? AND ?"
    )
    params = [workspace_id, f"{category}_%", date_from, date_to]

    if user_ids:
        placeholders = ','.join('?' * len(user_ids))
        sql += f" AND to_user_id IN ({placeholders})"
        params.extend(user_ids)

    db.cursor.execute(sql, params)
    txs = db.cursor.fetchall()

    total = sum(float(t['amount']) for t in txs)
    affected_users = len(set(t['to_user_id'] for t in txs))

    db.cursor.execute(
        "INSERT INTO economy_cancellations "
        "(workspace_id, cancellation_type, source_filter, amount, affected_users, mode, "
        " actually_deducted, comment, executed_by, executed_by_role) "
        "VALUES (?, 'mass', ?, ?, ?, 'log_only', 0, ?, ?, ?)",
        (workspace_id, json.dumps(filter_dict), total, affected_users,
         comment, executed_by, executed_by_role)
    )
    db.conn.commit()

    return {"ok": True, "total": total, "affected_users": affected_users, "mode": "log_only"}


def get_cancellations(db, workspace_id: int, limit: int = 50, offset: int = 0) -> list:
    try:
        db.cursor.execute(
            "SELECT * FROM economy_cancellations "
            "WHERE workspace_id = ? ORDER BY executed_at DESC LIMIT ? OFFSET ?",
            (workspace_id, limit, offset)
        )
        rows = db.cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_cancellations error: {e}")
        return []


# ── METRICS ───────────────────────────────────────────────────────────────────

def get_economy_metrics(db, workspace_id: int) -> dict:
    """Live-метрики для шапки: курс, банк, суммы балансов, эмиссия.

    settings, users — глобальные таблицы (курс/банк/балансы общие).
    transactions фильтруется по workspace_id."""
    try:
        db.cursor.execute("SELECT value FROM settings WHERE key = 'pulse_rate'")
        r = db.cursor.fetchone()
        pulse_rate = float(r['value']) if r else 0.0

        db.cursor.execute("SELECT value FROM settings WHERE key = 'bank_balance'")
        r = db.cursor.fetchone()
        bank_balance = float(r['value']) if r else 0.0

        db.cursor.execute("SELECT COALESCE(SUM(balance), 0) as total FROM users WHERE is_left = 0")
        r = db.cursor.fetchone()
        users_balance = float(r['total']) if r else 0.0

        total_supply = bank_balance + users_balance

        db.cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) as s FROM transactions "
            "WHERE workspace_id = ? AND from_user_id IS NULL "
            "AND timestamp >= datetime('now', '-24 hours')",
            (workspace_id,)
        )
        r = db.cursor.fetchone()
        emission_24h = float(r['s']) if r else 0.0

        db.cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) as s FROM transactions "
            "WHERE workspace_id = ? AND from_user_id IS NULL "
            "AND timestamp >= datetime('now', '-7 days')",
            (workspace_id,)
        )
        r = db.cursor.fetchone()
        emission_7d = float(r['s']) if r else 0.0

        db.cursor.execute(
            "SELECT transaction_type, COALESCE(SUM(amount), 0) as total FROM transactions "
            "WHERE workspace_id = ? AND from_user_id IS NULL "
            "AND timestamp >= datetime('now', '-7 days') "
            "GROUP BY transaction_type ORDER BY total DESC LIMIT 5",
            (workspace_id,)
        )
        top_sources = [
            {"type": row['transaction_type'], "amount": float(row['total'])}
            for row in db.cursor.fetchall()
        ]

        return {
            "pulse_rate":         pulse_rate,
            "bank_balance":       bank_balance,
            "users_balance":      users_balance,
            "total_supply":       total_supply,
            "emission_24h":       emission_24h,
            "emission_7d":        emission_7d,
            "top_income_sources_7d": top_sources,
        }
    except Exception as e:
        logger.error(f"get_economy_metrics error: {e}")
        return {
            "pulse_rate": 0, "bank_balance": 0, "users_balance": 0,
            "total_supply": 0, "emission_24h": 0, "emission_7d": 0,
            "top_income_sources_7d": [],
        }


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _parse_value(raw: str, vt: str):
    try:
        if vt == 'int':   return int(raw)
        if vt == 'float': return float(raw)
        if vt == 'bool':  return raw == '1'
        if vt == 'json':  return json.loads(raw)
    except Exception:
        pass
    return raw


def _validate_and_stringify(value, vt: str, min_val, max_val) -> str:
    """Парсит и валидирует значение, возвращает строку для хранения."""
    if isinstance(value, str):
        value = value.replace(',', '.')
    if vt == 'int':
        v = int(float(value))
    elif vt == 'float':
        v = float(value)
    elif vt == 'bool':
        return '1' if value else '0'
    else:
        return str(value)

    if min_val is not None and v < min_val:
        raise ValueError(f"Значение {v} меньше минимального {min_val}")
    if max_val is not None and v > max_val:
        raise ValueError(f"Значение {v} больше максимального {max_val}")

    if vt == 'int':
        return str(int(v))
    return str(v)
