#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль расчёта динамического курса Пульса и ТОП-5 Активистов.

ЕДИНАЯ ФОРМУЛА АКТИВНОСТИ (применяется везде):

  Индекс = ОКС/100 × 0.05 + СДС/100 × 0.05 + КС × 0.05 +
           КОР × 0.08 + КПР × 0.10 +
           КОтв × 0.18 + КОтп × 0.15 +
           КУП × 0.15 + Медиа × 0.07 + ПДВ × 0.12

  Сумма весов = 1.00

КУРС (реальное время):
  При каждом сообщении/реакции → +дельта в памяти → курс обновлён
  Каждые 30 мин → полный пересчёт из БД + запись в exchange_rate_history

ТОП-5 (2 раза в день):
  В 10:00 и 22:00 МСК → снапшот в top_activists_history
"""

import os
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════
# ЕДИНАЯ ФОРМУЛА — ВЕСА (сумма = 1.00)
# ═══════════════════════════════════════════════════
# Ручная настройка 
CHARS_NORM = 100  # Нормализатор для ОКС и СДС
RATE_SCALE = 2.1    # Масштабирующий коэффициент (делитель курса ранее был 5) "при 3 курс на тесте 2.92"
MAX_RATE = 5.5   # Потолок курса в рублях ( ранее было 1.2)

WEIGHTS = {
    'total_chars':          0.05,   # ОКС  — Общее Количество Символов (/ CHARS_NORM)
    'avg_message_length':   0.05,   # СДС  — Средняя Длина Сообщения  (/ CHARS_NORM)
    'total_words':          0.05,   # КС   — Количество Слов
    'reactions_given':      0.08,   # КОР  — Количество Оставленных Реакций
    'reactions_received':   0.10,   # КПР  — Количество Полученных Реакций
    'replies_received':     0.18,   # КОтв — Количество Ответов (полученных)
    'replies_sent':         0.15,   # КОтп — Количество Ответов (отправленных)
    'mentions_received':    0.15,   # КУП  — Количество Упоминаний Полученных
    'media_sent':           0.07,   # Медиа — Медиа контент
    'other_threads_posts':  0.12,   # ПДВ  — Публикации в Других Ветках
}

# Для SQL-запросов (тот же порядок)
SQL_WEIGHTS = {
    'total_chars':          f'0.05 * (SUM(us.total_chars) * 1.0 / {CHARS_NORM})',
    'avg_message_length':   f'0.05 * (CASE WHEN SUM(us.total_messages) > 0 '
                            f'THEN (SUM(us.total_chars) * 1.0 / SUM(us.total_messages)) / {CHARS_NORM} '
                            f'ELSE 0 END)',
    'total_words':          '0.05 * SUM(us.total_words)',
    'reactions_given':      '0.08 * SUM(us.reactions_given)',
    'reactions_received':   '0.10 * SUM(us.reactions_received)',
    'replies_received':     '0.18 * SUM(us.replies_received)',
    'replies_sent':         '0.15 * SUM(us.replies_sent)',
    'mentions_received':    '0.15 * SUM(us.mentions_received)',
    'media_sent':           '0.07 * SUM(us.media_sent)',
    'other_threads_posts':  '0.12 * SUM(us.other_threads_posts)',
}

# SQL-выражение для индекса (используется в TOP-5 и статистике)
ACTIVITY_INDEX_SQL = ' + '.join(SQL_WEIGHTS.values())


# ═══════════════════════════════════════════════════
# РАСЧЁТ ИНДЕКСА (Python)
# ═══════════════════════════════════════════════════

def calculate_index(stats):
    """
    Рассчитать Индекс Активности по единой формуле.

    Args:
        stats: dict с ключами total_chars, total_messages, total_words,
               reactions_given, reactions_received, replies_received,
               replies_sent, mentions_received, media_sent, other_threads_posts

    Returns:
        float — значение индекса
    """
    total_msgs = stats.get('total_messages', 0) or 0
    total_chars = stats.get('total_chars', 0) or 0

    if total_msgs == 0:
        avg_len = 0
    else:
        avg_len = total_chars / total_msgs

    idx = (
        (total_chars / CHARS_NORM)                       * WEIGHTS['total_chars'] +
        (avg_len / CHARS_NORM)                           * WEIGHTS['avg_message_length'] +
        (stats.get('total_words', 0) or 0)               * WEIGHTS['total_words'] +
        (stats.get('reactions_given', 0) or 0)           * WEIGHTS['reactions_given'] +
        (stats.get('reactions_received', 0) or 0)        * WEIGHTS['reactions_received'] +
        (stats.get('replies_received', 0) or 0)          * WEIGHTS['replies_received'] +
        (stats.get('replies_sent', 0) or 0)              * WEIGHTS['replies_sent'] +
        (stats.get('mentions_received', 0) or 0)         * WEIGHTS['mentions_received'] +
        (stats.get('media_sent', 0) or 0)                * WEIGHTS['media_sent'] +
        (stats.get('other_threads_posts', 0) or 0)       * WEIGHTS['other_threads_posts']
    )
    return round(idx, 6)


# ═══════════════════════════════════════════════════
# ДЕЛЬТА — МГНОВЕННОЕ ОБНОВЛЕНИЕ ПРИ КАЖДОМ ДЕЙСТВИИ
# ═══════════════════════════════════════════════════

def calculate_message_delta(char_count, word_count, is_reply, is_media, has_mention, is_other_thread):
    """
    Рассчитать дельту AI от одного сообщения.
    Вызывается при каждом сообщении для мгновенного обновления курса.

    Returns:
        float — дельта для добавления к текущему AI
    """
    delta = (
        (char_count / CHARS_NORM)       * WEIGHTS['total_chars'] +
        word_count                      * WEIGHTS['total_words'] +
        (1 if is_reply else 0)          * WEIGHTS['replies_sent'] +
        (1 if is_media else 0)          * WEIGHTS['media_sent'] +
        (1 if has_mention else 0)       * WEIGHTS['mentions_received'] +
        (1 if is_other_thread else 0)   * WEIGHTS['other_threads_posts']
    )
    # avg_message_length не добавляем как дельту — она пересчитывается
    # при full_recalculate из соотношения total_chars / total_messages
    return delta


def calculate_reaction_delta(is_given=True):
    """Дельта от одной реакции."""
    if is_given:
        return WEIGHTS['reactions_given']
    else:
        return WEIGHTS['reactions_received']


def calculate_reply_received_delta():
    """Дельта когда пользователю ответили."""
    return WEIGHTS['replies_received']


# ═══════════════════════════════════════════════════
# КЕШ КУРСА В ПАМЯТИ
# ═══════════════════════════════════════════════════

class RateCache:
    """
    Кеш курса в памяти бота.
    Обновляется дельтами при каждом действии.
    Полный пересчёт каждые 30 минут.
    """

    def __init__(self):
        self.ai_30d = 0.0          # Сумма AI за 30 дней
        self.days_with_data = 0     # Дней с данными
        self.avg_active = 0.0       # Среднее активных за 30 дней
        self.total_members = 1      # Всего людей в чате
        self.current_rate = 0.0     # Текущий курс
        self.denominator = 1.0      # Знаменатель формулы
        self.is_manual = False      # Ручной курс?
        self.last_full_recalc = None  # Время последнего полного пересчёта
        self._initialized = False

    @property
    def initialized(self):
        return self._initialized

    def full_recalculate(self, db, total_members, today):
        """
        Полный пересчёт из БД. Вызывается:
        - При старте бота
        - Каждые 30 минут
        """
        if self.is_manual:
            logger.info("💱 Rate is manual — skipping recalculation")
            return

        # Считаем AI за каждый из 30 дней
        total_ai = 0.0
        total_active = 0
        days_count = 0

        for i in range(30):
            date = today - timedelta(days=i)
            stats = _get_chat_stats_for_date(db, date)
            if stats and (stats['total_messages'] > 0 or stats['reactions_given'] > 0):
                ai = calculate_index(stats)
                total_ai += ai
                total_active += stats['active_users']
                days_count += 1

        self.ai_30d = total_ai
        self.days_with_data = days_count
        self.total_members = max(1, total_members)
        self.avg_active = (total_active / days_count) if days_count > 0 else 0

        # Знаменатель: меньше неактивных → выше курс
        denom = self.total_members - self.avg_active
        if denom <= 0:
            denom = max(1.0, self.total_members * 0.1)
        self.denominator = denom

        # Курс
        if days_count > 0 and denom > 0:
            avg_ai = total_ai / days_count
            raw_rate = avg_ai / denom
            self.current_rate = round(min(raw_rate / RATE_SCALE, MAX_RATE), 6)
        else:
            self.current_rate = 0.0

        from utils.helpers import get_moscow_time
        self.last_full_recalc = get_moscow_time()
        self._initialized = True

        logger.info(
            f"💱 Full recalc: rate={self.current_rate} | "
            f"AI_30d_sum={total_ai:.2f} | days={days_count} | "
            f"members={total_members} | avg_active={self.avg_active:.1f} | "
            f"denom={denom:.1f}"
        )

    def apply_delta(self, delta):
        """
        Применить дельту от одного действия.
        Мгновенно обновляет курс в памяти.
        Дельта добавляется только к «сегодняшнему» AI.
        """
        if self.is_manual or not self._initialized:
            return

        # Дельта влияет на 1 день из N дней с данными
        days = max(1, self.days_with_data)
        self.ai_30d += delta

        # Пересчитываем курс с масштабом и потолком
        if days > 0 and self.denominator > 0:
            avg_ai = self.ai_30d / days
            raw_rate = avg_ai / self.denominator
            self.current_rate = round(min(raw_rate / RATE_SCALE, MAX_RATE), 6)

    def set_manual(self, rate):
        """Установить ручной курс."""
        self.current_rate = rate
        self.is_manual = True

    def unset_manual(self):
        """Вернуть автоматический курс."""
        self.is_manual = False

    def get_rate_data(self):
        """Получить данные о курсе для отображения."""
        return {
            'rate': self.current_rate,
            'ai_30d': round(self.ai_30d / max(1, self.days_with_data), 2),
            'avg_active': round(self.avg_active, 1),
            'total_members': self.total_members,
            'denominator': round(self.denominator, 1),
            'days_with_data': self.days_with_data,
            'is_manual': self.is_manual,
        }


# Глобальный кеш — используется из bot.py и message_handler.py
rate_cache = RateCache()


# ═══════════════════════════════════════════════════
# ПОЛНЫЙ ПЕРЕСЧЁТ ДЛЯ SCHEDULER (каждые 30 мин)
# ═══════════════════════════════════════════════════

def scheduled_rate_update(db, total_members, today):
    """
    Вызывается из bot.py каждые 30 минут.
    Полный пересчёт + запись в историю.
    """
    rate_cache.full_recalculate(db, total_members, today)

    # Сохраняем в БД
    if not rate_cache.is_manual:
        data = rate_cache.get_rate_data()
        db.set_exchange_rate(
            rate=data['rate'],
            is_manual=False,
            ai_value=data['ai_30d'],
            total_members=data['total_members'],
            avg_active=data['avg_active'],
            denominator=data['denominator']
        )

    return rate_cache.current_rate


# ═══════════════════════════════════════════════════
# ТОП-5 АКТИВИСТОВ — % ЗА 4-ЧАСОВОЕ ОКНО
# ═══════════════════════════════════════════════════

# SQL-формула для hourly-таблицы (аналогична ACTIVITY_INDEX_SQL, но по ush)
SQL_WEIGHTS_HOURLY = {
    'total_chars':          f'0.05 * (SUM(ush.total_chars) * 1.0 / {CHARS_NORM})',
    'avg_message_length':   f'0.05 * (CASE WHEN SUM(ush.total_messages) > 0 '
                            f'THEN (SUM(ush.total_chars) * 1.0 / SUM(ush.total_messages)) / {CHARS_NORM} '
                            f'ELSE 0 END)',
    'total_words':          '0.05 * SUM(ush.total_words)',
    'reactions_given':      '0.08 * SUM(ush.reactions_given)',
    'reactions_received':   '0.10 * SUM(ush.reactions_received)',
    'replies_received':     '0.18 * SUM(ush.replies_received)',
    'replies_sent':         '0.15 * SUM(ush.replies_sent)',
    'mentions_received':    '0.15 * SUM(ush.mentions_received)',
    'media_sent':           '0.07 * SUM(ush.media_sent)',
    'other_threads_posts':  '0.12 * SUM(ush.other_threads_posts)',
}
ACTIVITY_INDEX_HOURLY_SQL = ' + '.join(SQL_WEIGHTS_HOURLY.values())


def calculate_top5_percent(db):
    """
    Рассчитать ТОП-5 % активности за скользящее 4-часовое окно.
    Каждый пользователь = его AI / сумма AI всех × 100%.

    Returns:
        list of dict: [{'user_id', 'username', 'percent', 'activity_index', 'rank'}, ...]
        + window_start, window_end (строки)
    """
    from utils.helpers import get_moscow_time
    now = get_moscow_time()

    # Определяем окно: последние 4 часа
    window_end = now
    window_start = now - timedelta(hours=4)

    # Строим условие WHERE для часов
    # Окно может пересекать границу дней (напр. 22:00 - 02:00)
    date_end = window_end.strftime('%Y-%m-%d')
    date_start = window_start.strftime('%Y-%m-%d')

    if date_start == date_end:
        # Простой случай — один день
        where = "ush.date = ? AND ush.hour >= ? AND ush.hour <= ?"
        params = [date_start, window_start.hour, window_end.hour]
    else:
        # Пересечение дней
        where = ("(ush.date = ? AND ush.hour >= ?) OR "
                 "(ush.date = ? AND ush.hour <= ?)")
        params = [date_start, window_start.hour, date_end, window_end.hour]

    # Считаем AI для каждого юзера за окно
    query = f'''
        SELECT
            u.user_id, u.username, u.first_name,
            ({ACTIVITY_INDEX_HOURLY_SQL}) as activity_index
        FROM user_stats_hourly ush
        JOIN users u ON ush.user_id = u.user_id
        WHERE ({where}) AND u.is_admin = 0 AND u.is_owner = 0 AND u.is_left = 0
        GROUP BY ush.user_id
        HAVING SUM(ush.total_messages) > 0 OR SUM(ush.reactions_given) > 0
               OR SUM(ush.reactions_received) > 0 OR SUM(ush.replies_sent) > 0
        ORDER BY activity_index DESC
    '''
    db.cursor.execute(query, params)
    rows = db.cursor.fetchall()

    # Общая сумма AI всех
    total_ai = sum(float(r['activity_index']) for r in rows) if rows else 0

    result = []
    for rank, row in enumerate(rows[:5], 1):
        ai = float(row['activity_index'])
        pct = (ai / total_ai * 100) if total_ai > 0 else 0
        result.append({
            'user_id': row['user_id'],
            'username': row['username'] or row['first_name'] or f"ID:{row['user_id']}",
            'activity_index': round(ai, 3),
            'percent': round(pct, 1),
            'rank': rank,
        })

    ws = window_start.strftime('%Y-%m-%d %H:%M')
    we = window_end.strftime('%Y-%m-%d %H:%M')
    return result, ws, we


def scheduled_top5_percent_update(db):
    """
    Вызывается каждый час из bot.py.
    Считает % активности за 4ч окно и кеширует в БД.
    """
    try:
        entries, ws, we = calculate_top5_percent(db)
        db.save_top5_percent(entries, ws, we)
        # Чистим старые hourly-данные (оставляем 2 дня)
        db.cleanup_old_hourly_stats(days_to_keep=2)
        logger.info(f"📊 TOP-5%% updated: {len(entries)} users | window {ws} → {we}")
        return entries
    except Exception as e:
        logger.error(f"Error in top5 percent update: {e}")
        return []


# ═══════════════════════════════════════════════════
# ТОП-5 АКТИВИСТОВ — СНАПШОТ (2 раза в день)
# ═══════════════════════════════════════════════════

def calculate_top5_snapshot(db, today, total_members):
    """
    Рассчитать ТОП-5 активистов за скользящие 30 дней.
    Вызывается из bot.py в 10:00 и 22:00 МСК.

    Returns:
        list of dict: [{'user_id': int, 'username': str, 'activity_index': float, 'rank': int}, ...]
    """
    date_30 = (today - timedelta(days=30)).strftime('%Y-%m-%d')

    db.cursor.execute(f'''
        SELECT
            u.user_id,
            u.username,
            u.first_name,
            ({ACTIVITY_INDEX_SQL}) as activity_index
        FROM user_stats us
        JOIN users u ON us.user_id = u.user_id
        WHERE us.date >= ? AND u.is_admin = 0 AND u.is_owner = 0
        GROUP BY us.user_id
        HAVING SUM(us.total_messages) > 0 OR SUM(us.reactions_given) > 0
               OR SUM(us.reactions_received) > 0 OR SUM(us.replies_sent) > 0
        ORDER BY activity_index DESC
        LIMIT 5
    ''', (date_30,))

    rows = db.cursor.fetchall()
    result = []
    for rank, row in enumerate(rows, 1):
        result.append({
            'user_id': row['user_id'],
            'username': row['username'] or row['first_name'] or f"ID:{row['user_id']}",
            'activity_index': round(float(row['activity_index']), 3),
            'rank': rank,
        })

    return result


def scheduled_top5_update(db, today, total_members):
    """
    Вызывается из bot.py в 10:00 и 22:00 МСК.
    Считает ТОП-5 и сохраняет снапшот в БД.
    """
    top5 = calculate_top5_snapshot(db, today, total_members)

    from utils.helpers import get_moscow_time
    now = get_moscow_time()
    time_slot = 'morning' if now.hour < 16 else 'evening'
    date_str = today.strftime('%Y-%m-%d') if hasattr(today, 'strftime') else str(today)

    for entry in top5:
        db.save_top_snapshot(
            date=date_str,
            time_slot=time_slot,
            user_id=entry['user_id'],
            rank=entry['rank'],
            activity_index=entry['activity_index']
        )

    logger.info(f"🏆 TOP-5 snapshot saved: {time_slot} | {len(top5)} users")
    return top5


# ═══════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════

def _get_chat_stats_for_date(db, date):
    """Агрегированная статистика чата за дату (без админов)."""
    try:
        db.cursor.execute('''
            SELECT
                COALESCE(SUM(us.total_chars), 0)         AS total_chars,
                COALESCE(SUM(us.total_messages), 0)      AS total_messages,
                COALESCE(SUM(us.total_words), 0)         AS total_words,
                COALESCE(SUM(us.reactions_given), 0)     AS reactions_given,
                COALESCE(SUM(us.reactions_received), 0)  AS reactions_received,
                COALESCE(SUM(us.replies_received), 0)    AS replies_received,
                COALESCE(SUM(us.replies_sent), 0)        AS replies_sent,
                COALESCE(SUM(us.mentions_received), 0)   AS mentions_received,
                COALESCE(SUM(us.media_sent), 0)          AS media_sent,
                COALESCE(SUM(us.other_threads_posts), 0) AS other_threads_posts,
                COUNT(DISTINCT us.user_id)               AS active_users
            FROM user_stats us
            JOIN users u ON us.user_id = u.user_id
            WHERE us.date = ?
              AND u.is_admin = 0 AND u.is_owner = 0
              AND (us.total_messages > 0 OR us.reactions_given > 0
                   OR us.reactions_received > 0 OR us.media_sent > 0)
        ''', (str(date),))
        row = db.cursor.fetchone()
        if not row or (row['total_messages'] == 0 and row['reactions_given'] == 0):
            return None
        return dict(row)
    except Exception as e:
        logger.error(f"Error getting stats for {date}: {e}")
        return None


def format_rate_message(rate_data, user_balance=None):
    """Форматирует сообщение о курсе."""
    rate = rate_data['rate']
    ai_avg = rate_data.get('ai_30d', 0)
    days = rate_data.get('days_with_data', 0)
    avg_active = rate_data.get('avg_active', 0)
    members = rate_data.get('total_members', 0)

    msg = "💱 <b>КУРС ПУЛЬСА</b>\n\n"
    msg += f"📊 1 💎 = <b>{rate:.6f}</b> ₽\n"
    msg += f"\n📈 Сред. AI (30д): <b>{ai_avg:.2f}</b>\n"
    msg += f"📅 Дней с данными: <b>{days}</b>/30\n"
    msg += f"👥 Активных (сред.): <b>{avg_active:.0f}</b> / {members}\n"

    if rate >= MAX_RATE:
        msg += f"\n⚠️ Достигнут потолок: {MAX_RATE} ₽\n"

    if user_balance is not None and rate > 0:
        rub_value = user_balance * rate
        from utils.helpers import format_number
        msg += f"\n💰 Ваш баланс:\n"
        msg += f"   💎 {format_number(user_balance)} Пульсов\n"
        msg += f"   💵 ≈ {rub_value:.4f} ₽"

    return msg
