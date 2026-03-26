#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mining_logic.py — Ядро экономики «Конструктор ценности» (Proof-of-Value).

Итоговая награда за сообщение:
    total_reward = (Σ Base + Σ Combos + Σ Sprints + Σ Penalties) × GLOBAL_BASE_RATE

БЛОК 1 — Базовая стоимость контента (BASE_COEFFICIENTS)
БЛОК 2 — Комбо-система / Daily Quests (COMBO_COEFFICIENTS)
БЛОК 3 — Спринты / накопительные квесты (SPRINTS_CONFIG)
БЛОК 4 — Штрафы (PENALTY_COEFFICIENTS)

Точка входа: process_mining_reward() — вызывается из message_handler.py.
Социальные хелперы (лайки, ответы) вызываются отдельно из handle_reaction().
"""

from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  ГЛОБАЛЬНАЯ СТАВКА
# ══════════════════════════════════════════════════════════════════════════════

GLOBAL_BASE_RATE: float = 0.002
"""Единая базовая ставка экономики. Все коэффициенты умножаются на неё."""


# ══════════════════════════════════════════════════════════════════════════════
#  БЛОК 1 — КОЭФФИЦИЕНТЫ БАЗОВОЙ СТОИМОСТИ
# ══════════════════════════════════════════════════════════════════════════════

BASE_COEFFICIENTS: dict[str, int] = {

    # ── Контент ──────────────────────────────────────────────────────────
    'text_message':                1,
    'emoji_only':                  1,
    'photo':                       2,
    'photo_album_special_thread':  6,
    'video_regular':               5,
    'video_note':                  7,
    'audio_or_link':               2,
    'voice':                       3,
    'gif':                         1,

    # ── Социал ───────────────────────────────────────────────────────────
    'reply_sent':                  1,
    'reply_received':              1,   # задним числом
    'reaction_given':              1,   # задним числом
    'reaction_received':           1,   # задним числом
}


# ══════════════════════════════════════════════════════════════════════════════
#  БЛОК 2 — КОЭФФИЦИЕНТЫ КОМБО (Daily Quests, 1 раз в 24 ч)
# ══════════════════════════════════════════════════════════════════════════════

COMBO_COEFFICIENTS: dict[str, int] = {

    # ── Instant (при отправке) ───────────────────────────────────────────
    'writer':       20,   # текст > 50 символов
    'illustrator':  40,   # текст > 50 символов + фото
    'reviewer':     40,   # видео + текст > 100 слов
    'dj':           30,   # ссылка на плейлист

    # ── Social (задним числом) ───────────────────────────────────────────
    'sharp_tongue':  6,   # > 2 ответов на пост
    'viral_post':    3,   # > 2 лайков
    'hit_post':     10,   # 4+ лайков
    'legend_post':  20,   # 6+ лайков
}


# ══════════════════════════════════════════════════════════════════════════════
#  БЛОК 3 — СПРИНТЫ (Накопительные квесты на время)
# ══════════════════════════════════════════════════════════════════════════════

THREAD_IDS: dict[str, int] = {
    'https://t.me/c/3890785443/762': 11,
    'https://t.me/c/3890785443/3204':    24,
    'https://t.me/c/3890785443/3206':   15,
    'https://t.me/c/3890785443/3202':    6,
}

SPRINTS_CONFIG: dict[str, dict] = {

    # ── 24 ч ─────────────────────────────────────────────────────────────
    'chat_core':    {'target': 10, 'hours': 24, 'coeff':  50, 'metric': 'messages',           'allowed_threads': 'ALL',                                                            'label': '💬 Основа чата'},
    'emotional':    {'target': 10, 'hours': 24, 'coeff':  20, 'metric': 'emoji_messages',     'allowed_threads': 'ALL',                                                            'label': '😍 Эмоциональный'},
    'photographer': {'target':  3, 'hours': 24, 'coeff':  40, 'metric': 'photos',             'allowed_threads': 'ALL',                                                            'label': '📸 Фотограф'},
    'director':     {'target':  2, 'hours': 24, 'coeff': 140, 'metric': 'videos',             'allowed_threads': [THREAD_IDS['https://t.me/c/3890785443/762'], THREAD_IDS['https://t.me/c/3890785443/3204'], THREAD_IDS['https://t.me/c/3890785443/3206']], 'label': '🎬 Режиссёр'},
    'music_lover':  {'target':  5, 'hours': 24, 'coeff': 120, 'metric': 'audio',              'allowed_threads': [THREAD_IDS['https://t.me/c/3890785443/3202']],                                            'label': '🎧 Меломан'},

    # ── 12 ч ─────────────────────────────────────────────────────────────
    'face_seller':  {'target':  5, 'hours': 12, 'coeff':  60, 'metric': 'video_notes',        'allowed_threads': 'ALL', 'label': '🫧 Лицом торгуешь'},
    'center':       {'target': 20, 'hours': 12, 'coeff':  50, 'metric': 'replies_received',   'allowed_threads': 'ALL', 'label': '🎯 Центр внимания'},

    # ── 1 ч ──────────────────────────────────────────────────────────────
    'radio':        {'target':  4, 'hours':  1, 'coeff':  20, 'metric': 'voices',             'allowed_threads': 'ALL', 'label': '🎙 Радио'},
    'gif_room':     {'target': 10, 'hours':  1, 'coeff':  30, 'metric': 'gifs',               'allowed_threads': 'ALL', 'label': '🎞 Гифошная'},
    'chatterbox':   {'target': 20, 'hours':  1, 'coeff':  40, 'metric': 'replies_sent',       'allowed_threads': 'ALL', 'label': '🗣 Болтун'},
    'generous':     {'target':  5, 'hours':  1, 'coeff':  20, 'metric': 'reactions_given',    'allowed_threads': 'ALL', 'label': '💝 Щедрая душа'},
    'favorite':     {'target': 10, 'hours':  1, 'coeff':  40, 'metric': 'reactions_received', 'allowed_threads': 'ALL', 'label': '⭐ Любимчик'},
}


# ══════════════════════════════════════════════════════════════════════════════
#  БЛОК 4 — ШТРАФЫ
# ══════════════════════════════════════════════════════════════════════════════

PENALTY_COEFFICIENTS: dict[str, int] = {
    'copypaste':   -50,   # дубликат своего же сообщения за последний час
    'wrong_door':  -50,   # контент не по теме ветки
    'toxic':      -100,   # токсичное сообщение (для будущего модератора)
}


# ══════════════════════════════════════════════════════════════════════════════
#  УТИЛИТЫ
# ══════════════════════════════════════════════════════════════════════════════

def _is_emoji_only(text: str) -> bool:
    """Строка целиком из эмодзи (без букв, цифр, ASCII-знаков)."""
    if not text or not text.strip():
        return False
    for ch in text.strip():
        if ch.isspace():
            continue
        if ch.isalpha() or ch.isdigit() or ord(ch) < 256:
            return False
    return True


def _has_link(text: str) -> bool:
    """Наличие URL в тексте."""
    if not text:
        return False
    low = text.lower()
    return any(m in low for m in ('http://', 'https://', 't.me/', 'www.'))


def _is_playlist_link(text: str) -> bool:
    """Ссылка на плейлист (Spotify, YT Music, Apple, Яндекс, VK, SoundCloud, Deezer)."""
    if not text:
        return False
    low = text.lower()
    for p in ('open.spotify.com/playlist/', 'music.youtube.com/playlist',
              'youtube.com/playlist', 'vk.com/music/playlist/'):
        if p in low:
            return True
    if 'music.apple.com/' in low and '/playlist/' in low:
        return True
    if 'music.yandex.ru/users/' in low and '/playlists/' in low:
        return True
    # Новый формат Яндекс Музыки (без /users/)
    if 'music.yandex.ru/playlists/' in low:
        return True
    if 'soundcloud.com/' in low and '/sets/' in low:
        return True
    if 'deezer.com/' in low and '/playlist/' in low:
        return True
    return False


def _count_words(text: str) -> int:
    return len(text.split()) if text else 0


# ══════════════════════════════════════════════════════════════════════════════
#  БЛОК 1: РАСЧЁТ БАЗОВЫХ КОЭФФИЦИЕНТОВ
# ══════════════════════════════════════════════════════════════════════════════

def calculate_base_coefficients(
    text: str = '',
    has_photo: bool = False,
    photo_count: int = 0,
    has_video: bool = False,
    is_video_note: bool = False,
    has_voice: bool = False,
    has_audio: bool = False,
    has_gif: bool = False,
    is_reply: bool = False,
    thread_id: Optional[int] = None,
    special_thread_ids: Optional[set[int]] = None,
) -> tuple[int, list[str]]:
    """
    Считает сумму базовых коэффициентов за одно сообщение.

    Возвращает (сумма_коэффициентов, список_сработавших).
    Умножение на GLOBAL_BASE_RATE делает вызывающий код.
    """
    total: int = 0
    triggered: list[str] = []
    clean = (text or '').strip()

    # ── Текст ─────────────────────────────────────────────────────────────
    if clean:
        if _is_emoji_only(clean):
            total += BASE_COEFFICIENTS['emoji_only']
            triggered.append('emoji_only')
        else:
            total += BASE_COEFFICIENTS['text_message']
            triggered.append('text_message')

    # ── Медиа ─────────────────────────────────────────────────────────────
    if has_photo:
        is_special = (special_thread_ids and thread_id and thread_id in special_thread_ids)
        if photo_count >= 2 and is_special:
            total += BASE_COEFFICIENTS['photo_album_special_thread']
            triggered.append('photo_album_special_thread')
        else:
            total += BASE_COEFFICIENTS['photo']
            triggered.append('photo')

    if is_video_note:
        total += BASE_COEFFICIENTS['video_note']
        triggered.append('video_note')
    elif has_video:
        total += BASE_COEFFICIENTS['video_regular']
        triggered.append('video_regular')

    if has_voice:
        total += BASE_COEFFICIENTS['voice']
        triggered.append('voice')

    if has_audio or _has_link(clean):
        total += BASE_COEFFICIENTS['audio_or_link']
        triggered.append('audio_or_link')

    if has_gif:
        total += BASE_COEFFICIENTS['gif']
        triggered.append('gif')

    # ── Reply ─────────────────────────────────────────────────────────────
    if is_reply:
        total += BASE_COEFFICIENTS['reply_sent']
        triggered.append('reply_sent')

    return total, triggered


# ══════════════════════════════════════════════════════════════════════════════
#  БЛОК 2: КОМБО — МГНОВЕННЫЕ (при отправке)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_instant_combos(
    text: str = '',
    char_count: int = 0,
    word_count: int = 0,
    has_photo: bool = False,
    has_video: bool = False,
    has_playlist_link: bool = False,
    completed_today: Optional[list[str]] = None,
) -> tuple[int, list[str]]:
    """
    Проверяет instant-комбо: writer, illustrator, reviewer, dj.
    Каждое — макс. 1 раз в сутки.

    Возвращает (сумма_коэффициентов, список_новых_комбо).
    """
    done: set[str] = set(completed_today or [])
    new: list[str] = []
    total: int = 0

    clean = (text or '').strip()
    if char_count == 0 and clean:
        char_count = len(clean)
    if word_count == 0 and clean:
        word_count = _count_words(clean)
    if not has_playlist_link and clean:
        has_playlist_link = _is_playlist_link(clean)

    if char_count > 50 and 'writer' not in done:
        new.append('writer');       total += COMBO_COEFFICIENTS['writer']
    if char_count > 50 and has_photo and 'illustrator' not in done:
        new.append('illustrator');  total += COMBO_COEFFICIENTS['illustrator']
    if has_video and word_count > 100 and 'reviewer' not in done:
        new.append('reviewer');     total += COMBO_COEFFICIENTS['reviewer']
    if has_playlist_link and 'dj' not in done:
        new.append('dj');           total += COMBO_COEFFICIENTS['dj']

    return total, new


# ══════════════════════════════════════════════════════════════════════════════
#  БЛОК 2: КОМБО — СОЦИАЛЬНЫЕ (задним числом, вызывается из handle_reaction)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_social_combos(
    reply_count: int = 0,
    reaction_count: int = 0,
    completed_today: Optional[list[str]] = None,
) -> tuple[float, list[str]]:
    """
    Проверяет social-комбо: sharp_tongue, viral, hit, legend.
    Лайковые комбо НЕ исключают друг друга.

    Возвращает (награда_в_Пульсах, список_новых_комбо).
    """
    done: set[str] = set(completed_today or [])
    new: list[str] = []
    total: int = 0

    if reply_count > 2 and 'sharp_tongue' not in done:
        new.append('sharp_tongue'); total += COMBO_COEFFICIENTS['sharp_tongue']
    if reaction_count > 2 and 'viral_post' not in done:
        new.append('viral_post');   total += COMBO_COEFFICIENTS['viral_post']
    if reaction_count >= 4 and 'hit_post' not in done:
        new.append('hit_post');     total += COMBO_COEFFICIENTS['hit_post']
    if reaction_count >= 6 and 'legend_post' not in done:
        new.append('legend_post');  total += COMBO_COEFFICIENTS['legend_post']

    reward = round(total * GLOBAL_BASE_RATE, 4)
    if new:
        logger.info(f"🏆 SOCIAL COMBO: {reward} | new={new}")
    return reward, new


# ══════════════════════════════════════════════════════════════════════════════
#  СОЦИАЛЬНЫЕ ХЕЛПЕРЫ (вызываются из handle_reaction / handle_message)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_reply_received_reward() -> float:
    """Награда автору поста, на который кто-то ответил."""
    return round(BASE_COEFFICIENTS['reply_received'] * GLOBAL_BASE_RATE, 4)

def calculate_reaction_given_reward() -> float:
    """Награда тому, кто поставил реакцию."""
    return round(BASE_COEFFICIENTS['reaction_given'] * GLOBAL_BASE_RATE, 4)

def calculate_reaction_received_reward() -> float:
    """Награда автору поста, который лайкнули."""
    return round(BASE_COEFFICIENTS['reaction_received'] * GLOBAL_BASE_RATE, 4)


# ══════════════════════════════════════════════════════════════════════════════
#  БЛОК 3: ПРОВЕРКА СПРИНТОВ
# ══════════════════════════════════════════════════════════════════════════════

def _is_thread_allowed(cfg: dict, thread_id: Optional[int]) -> bool:
    allowed = cfg['allowed_threads']
    if allowed == 'ALL':
        return True
    if thread_id is None:
        return False
    return thread_id in allowed


def check_completed_sprints(
    metrics_1h:  dict[str, int],
    metrics_12h: dict[str, int],
    metrics_24h: dict[str, int],
    current_thread_id: Optional[int] = None,
    already_claimed: Optional[list[str]] = None,
) -> tuple[int, list[str]]:
    """
    Проверяет, какие спринты завершены прямо сейчас.
    НЕ делает SQL — принимает готовые метрики.

    Возвращает (сумма_коэффициентов, список_новых_спринтов).
    """
    claimed: set[str] = set(already_claimed or [])
    by_hours = {1: metrics_1h, 12: metrics_12h, 24: metrics_24h}

    new: list[str] = []
    total: int = 0

    for name, cfg in SPRINTS_CONFIG.items():
        if name in claimed:
            continue
        if not _is_thread_allowed(cfg, current_thread_id):
            continue
        metrics = by_hours.get(cfg['hours'], {})
        if metrics.get(cfg['metric'], 0) >= cfg['target']:
            new.append(name)
            total += cfg['coeff']

    return total, new


# ══════════════════════════════════════════════════════════════════════════════
#  БЛОК 4: РАСЧЁТ ШТРАФОВ
# ══════════════════════════════════════════════════════════════════════════════

def calculate_penalties(
    text: str,
    thread_id: Optional[int],
    db,
    user_id: int,
    chat_id: int,
    is_copypaste: bool = False,
    is_wrong_door: bool = False,
) -> tuple[int, list[str]]:
    """
    Проверяет штрафные условия для текущего сообщения.

    Если флаги не переданы — copypaste определяется автоматически.
    wrong_door и toxic — только через внешние флаги.

    Возвращает (сумма_отрицательных_коэффициентов, список_штрафов).
    """
    penalties: list[str] = []
    total: int = 0

    # ── Copypaste ─────────────────────────────────────────────────────────
    if not is_copypaste and text and len(text.strip()) >= 30:
        is_copypaste = _detect_copypaste(db, user_id, chat_id, text.strip())

    if is_copypaste:
        penalties.append('copypaste')
        total += PENALTY_COEFFICIENTS['copypaste']

    # ── Wrong door ────────────────────────────────────────────────────────
    if is_wrong_door:
        penalties.append('wrong_door')
        total += PENALTY_COEFFICIENTS['wrong_door']

    # toxic — зарезервировано для будущего AI-модератора

    if penalties:
        logger.info(f"⚠️ PENALTY: coeff={total} | {penalties} | user={user_id}")

    return total, penalties


def _detect_copypaste(db, user_id: int, chat_id: int, text: str) -> bool:
    """
    Ищет точный дубликат текста от того же юзера за последний час.
    Сравнивает первые 500 символов (как хранятся в messages).
    
    ВАЖНО: >= 2 потому что текущее сообщение уже записано в БД
    до вызова process_mining_reward. COUNT=1 — это само сообщение,
    COUNT=2 — есть дубликат.
    """
    try:
        db.cursor.execute('''
            SELECT COUNT(*) AS cnt FROM messages
            WHERE user_id = ? AND chat_id = ?
              AND message_text = ?
              AND created_at >= datetime('now', '-1 hour')
        ''', (user_id, chat_id, text[:500]))
        row = db.cursor.fetchone()
        return (row['cnt'] or 0) >= 2 if row else False
    except Exception as e:
        logger.debug(f"Copypaste check skipped: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  ЛЕЙБЛЫ КОМБО (для красивого лога)
# ══════════════════════════════════════════════════════════════════════════════

COMBO_LABELS: dict[str, str] = {
    'writer':       '✍️ Писатель',
    'illustrator':  '🖼 Иллюстратор',
    'reviewer':     '🎬 Обозреватель',
    'dj':           '🎧 Диджей',
    'sharp_tongue': '🗡 Острый язык',
    'viral_post':   '📢 Вирусный пост',
    'hit_post':     '💥 Хит-пост',
    'legend_post':  '👑 Легенда',
}

PENALTY_LABELS: dict[str, str] = {
    'copypaste':  '📋 Копипаста',
    'wrong_door': '🚪 Не та дверь',
    'toxic':      '☠️ Токсик',
}


def _calc_combo_cooldown(claimed_at: datetime, now: datetime) -> str:
    """Время до конца КД конкретного комбо (24ч от момента получения)."""
    expires = claimed_at + timedelta(hours=24)
    delta = expires - now
    if delta.total_seconds() <= 0:
        return "готово!"
    total_min = int(delta.total_seconds()) // 60
    h = total_min // 60
    m = total_min % 60
    if h > 0:
        return f"{h}ч {m}мин"
    return f"{m}мин"


def _calc_sprint_cooldown(hours: int, now: datetime) -> str:
    """Время до конца окна спринта."""
    if hours == 24:
        end = now.replace(hour=23, minute=59, second=59)
    elif hours == 12:
        if now.hour < 12:
            end = now.replace(hour=11, minute=59, second=59)
        else:
            end = now.replace(hour=23, minute=59, second=59)
    else:  # 1h
        end = now.replace(minute=59, second=59)

    delta = end - now
    total_min = max(delta.seconds // 60, 0)
    h = total_min // 60
    m = total_min % 60
    if h > 0:
        return f"{h}ч {m}мин"
    return f"{m}мин"


# ══════════════════════════════════════════════════════════════════════════════
#  DB-ХЕЛПЕРЫ: чтение/запись комбо и спринтов
#
#  НУЖНЫЕ ТАБЛИЦЫ (создайте в db_manager.py → initialize()):
#
#    CREATE TABLE IF NOT EXISTS combo_claims (
#        user_id    INTEGER NOT NULL,
#        combo_name TEXT    NOT NULL,
#        reward     REAL    DEFAULT 0,
#        claimed_at TEXT    NOT NULL,
#        PRIMARY KEY (user_id, combo_name)
#    );
#
#    CREATE TABLE IF NOT EXISTS sprint_claims (
#        user_id     INTEGER NOT NULL,
#        sprint_name TEXT    NOT NULL,
#        window_key  TEXT    NOT NULL,
#        reward      REAL    DEFAULT 0,
#        claimed_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
#        PRIMARY KEY (user_id, sprint_name, window_key)
#    );
# ══════════════════════════════════════════════════════════════════════════════

def _get_claimed_combos(db, user_id: int, now: datetime) -> dict[str, datetime]:
    """
    Комбо, которые ещё на КД (получены менее 24ч назад).
    Возвращает {combo_name: claimed_at_datetime}.
    """
    try:
        cutoff = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        db.cursor.execute(
            'SELECT combo_name, claimed_at FROM combo_claims WHERE user_id = ? AND claimed_at > ?',
            (user_id, cutoff))
        result = {}
        for r in db.cursor.fetchall():
            try:
                ca = datetime.strptime(r['claimed_at'][:19], '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                ca = now  # fallback
            result[r['combo_name']] = ca
        return result
    except Exception:
        return {}


def _save_combo_claims(db, user_id: int, combos: list[str], reward: float, now: datetime) -> None:
    """Записать новые комбо-клеймы с точным временем получения."""
    if not combos:
        return
    try:
        per = round(reward / len(combos), 4) if combos else 0
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        for name in combos:
            db.cursor.execute(
                'INSERT OR REPLACE INTO combo_claims (user_id, combo_name, reward, claimed_at) VALUES (?,?,?,?)',
                (user_id, name, per, now_str))
        db.conn.commit()
    except Exception as e:
        logger.debug(f"Save combo claims: {e}")


def _get_sprint_window_key(hours: int, now: datetime) -> str:
    """
    Ключ временного окна:
      24h → '2026-03-15_24h'
      12h → '2026-03-15T00_12h' / '2026-03-15T12_12h'
       1h → '2026-03-15T14_1h'
    """
    d = now.strftime('%Y-%m-%d')
    if hours == 24:
        return f"{d}_24h"
    elif hours == 12:
        block = 0 if now.hour < 12 else 12
        return f"{d}T{block:02d}_12h"
    else:
        return f"{d}T{now.hour:02d}_1h"


def _get_claimed_sprints(db, user_id: int, now: datetime) -> list[str]:
    """Список спринтов, закрытых в текущих временных окнах."""
    try:
        keys = [
            _get_sprint_window_key(1, now),
            _get_sprint_window_key(12, now),
            _get_sprint_window_key(24, now),
        ]
        ph = ','.join('?' * len(keys))
        db.cursor.execute(
            f'SELECT sprint_name FROM sprint_claims WHERE user_id = ? AND window_key IN ({ph})',
            (user_id, *keys))
        return [r['sprint_name'] for r in db.cursor.fetchall()]
    except Exception:
        return []


def _save_sprint_claims(db, user_id: int, sprints: list[str], reward: float, now: datetime) -> None:
    """Записать новые спринт-клеймы."""
    if not sprints:
        return
    try:
        per = round(reward / len(sprints), 4) if sprints else 0
        for name in sprints:
            hours = SPRINTS_CONFIG[name]['hours']
            wk = _get_sprint_window_key(hours, now)
            db.cursor.execute(
                'INSERT OR IGNORE INTO sprint_claims (user_id, sprint_name, window_key, reward) VALUES (?,?,?,?)',
                (user_id, name, wk, per))
        db.conn.commit()
    except Exception as e:
        logger.debug(f"Save sprint claims: {e}")


def _query_user_sprint_metrics(db, user_id: int, today_str: str) -> tuple[dict, dict, dict]:
    """
    Агрегированные метрики пользователя за 1ч / 12ч / 24ч.

    Берёт базовые счётчики из user_stats + гранулярные медиа-типы
    из messages (там message_type хранит тип контента).
    
    Для 1ч и 12ч — считает из messages с фильтром по created_at.
    Для 24ч — берёт суточный агрегат из user_stats + messages за день.
    """
    empty: dict[str, int] = {}
    try:
        # ── Базовые метрики из user_stats (суточные) ──────────────────────
        db.cursor.execute('''
            SELECT
                COALESCE(SUM(total_messages), 0)   AS messages,
                COALESCE(SUM(replies_sent), 0)      AS replies_sent,
                COALESCE(SUM(replies_received), 0)  AS replies_received,
                COALESCE(SUM(reactions_given), 0)    AS reactions_given,
                COALESCE(SUM(reactions_received), 0) AS reactions_received,
                COALESCE(SUM(media_sent), 0)         AS media_sent
            FROM user_stats
            WHERE user_id = ? AND date = ?
        ''', (user_id, today_str))
        stats_row = db.cursor.fetchone()

        base_24h = {
            'messages':           stats_row['messages'] if stats_row else 0,
            'replies_sent':       stats_row['replies_sent'] if stats_row else 0,
            'replies_received':   stats_row['replies_received'] if stats_row else 0,
            'reactions_given':    stats_row['reactions_given'] if stats_row else 0,
            'reactions_received': stats_row['reactions_received'] if stats_row else 0,
        }

        # ── Гранулярные медиа-метрики из messages ─────────────────────────
        # Считаем по message_type для каждого временного окна
        media_metrics = {}
        for label, interval in [('1h', '-1 hour'), ('12h', '-12 hours'), ('24h', '-24 hours')]:
            db.cursor.execute('''
                SELECT
                    COALESCE(SUM(CASE WHEN message_type = 'photo'      THEN 1 ELSE 0 END), 0) AS photos,
                    COALESCE(SUM(CASE WHEN message_type = 'video'      THEN 1 ELSE 0 END), 0) AS videos,
                    COALESCE(SUM(CASE WHEN message_type = 'video_note' THEN 1 ELSE 0 END), 0) AS video_notes,
                    COALESCE(SUM(CASE WHEN message_type = 'voice'      THEN 1 ELSE 0 END), 0) AS voices,
                    COALESCE(SUM(CASE WHEN message_type = 'audio'      THEN 1 ELSE 0 END), 0) AS audio,
                    COALESCE(SUM(CASE WHEN message_type = 'animation'  THEN 1 ELSE 0 END), 0) AS gifs,
                    COALESCE(SUM(CASE WHEN message_type = 'emoji'      THEN 1 ELSE 0 END), 0) AS emoji_messages,
                    COUNT(*) AS total_msgs
                FROM messages
                WHERE user_id = ? AND chat_id = (
                    SELECT chat_id FROM messages WHERE user_id = ? ORDER BY rowid DESC LIMIT 1
                )
                AND created_at >= datetime('now', ?)
            ''', (user_id, user_id, interval))
            row = db.cursor.fetchone()
            media_metrics[label] = {
                'photos':       row['photos'] if row else 0,
                'videos':       row['videos'] if row else 0,
                'video_notes':  row['video_notes'] if row else 0,
                'voices':       row['voices'] if row else 0,
                'audio':        row['audio'] if row else 0,
                'gifs':         row['gifs'] if row else 0,
                'emoji_messages': row['emoji_messages'] if row else 0,
            }

        # ── Собираем метрики по окнам ─────────────────────────────────────

        # 1ч: social из user_stats (приблизительно), media из messages (точно)
        m1h = {**media_metrics['1h']}
        # Для 1ч social-метрики берём из messages count (приблизительно)
        db.cursor.execute('''
            SELECT COUNT(*) AS cnt FROM messages
            WHERE user_id = ? AND created_at >= datetime('now', '-1 hour')
        ''', (user_id,))
        r1 = db.cursor.fetchone()
        m1h['messages'] = r1['cnt'] if r1 else 0
        # replies/reactions за 1ч — пока берём суточные (верхняя оценка)
        m1h['replies_sent']       = base_24h['replies_sent']
        m1h['replies_received']   = base_24h['replies_received']
        m1h['reactions_given']    = base_24h['reactions_given']
        m1h['reactions_received'] = base_24h['reactions_received']

        # 12ч: аналогично
        m12h = {**media_metrics['12h']}
        db.cursor.execute('''
            SELECT COUNT(*) AS cnt FROM messages
            WHERE user_id = ? AND created_at >= datetime('now', '-12 hours')
        ''', (user_id,))
        r12 = db.cursor.fetchone()
        m12h['messages'] = r12['cnt'] if r12 else 0
        m12h['replies_sent']       = base_24h['replies_sent']
        m12h['replies_received']   = base_24h['replies_received']
        m12h['reactions_given']    = base_24h['reactions_given']
        m12h['reactions_received'] = base_24h['reactions_received']

        # 24ч: user_stats + media из messages
        m24h = {**base_24h, **media_metrics['24h']}

        return m1h, m12h, m24h

    except Exception as e:
        logger.debug(f"Sprint metrics query: {e}")
        return empty, empty, empty


# ══════════════════════════════════════════════════════════════════════════════
#  ГЛАВНАЯ ФУНКЦИЯ
# ══════════════════════════════════════════════════════════════════════════════

def process_mining_reward(
    user_id: int,
    today,
    user_data: dict,
    is_excluded: bool,
    exclusion_reason: Optional[str],
    db,
    message,
    thread_id: Optional[int],
) -> float:
    """
    Полный цикл начисления награды за одно сообщение.

    1. Извлекает данные из telegram.Message
    2. Считает базовые коэффициенты      (Блок 1)
    3. Проверяет мгновенные комбо         (Блок 2)
    4. Проверяет спринты                  (Блок 3)
    5. Считает штрафы                     (Блок 4)
    6. total = (Σ коэффициентов) × GLOBAL_BASE_RATE
    7. Списывает из банка, начисляет юзеру, пишет транзакцию

    Возвращает начисленную награду (0.0 если не начислена).
    """

    if is_excluded:
        logger.info(f"ℹ️ SKIP user {user_id} ({exclusion_reason})")
        return 0.0

    if not user_data:
        logger.warning(f"⚠️ No user_data for {user_id}")
        return 0.0

    try:
        # ══════════════════════════════════════════════════════════════════
        #  ИЗВЛЕЧЕНИЕ ДАННЫХ ИЗ telegram.Message
        # ══════════════════════════════════════════════════════════════════

        text       = message.text or message.caption or ''
        has_photo  = bool(message.photo)
        has_video  = bool(message.video)
        is_vnote   = bool(message.video_note)
        has_voice  = bool(message.voice)
        has_audio  = bool(message.audio)
        has_gif    = bool(message.animation)

        is_reply = False
        if message.reply_to_message and message.reply_to_message.from_user:
            is_reply = message.reply_to_message.from_user.id != user_id

        clean_text = text.strip()
        char_count = len(clean_text)
        word_count = _count_words(clean_text)
        chat_id    = message.chat.id
        today_str  = str(today)

        # ══════════════════════════════════════════════════════════════════
        #  БЛОК 1: БАЗА
        # ══════════════════════════════════════════════════════════════════

        base_coeff, base_triggered = calculate_base_coefficients(
            text=text, has_photo=has_photo, has_video=has_video,
            is_video_note=is_vnote, has_voice=has_voice,
            has_audio=has_audio, has_gif=has_gif,
            is_reply=is_reply, thread_id=thread_id,
        )

        # ══════════════════════════════════════════════════════════════════
        #  БЛОК 2: МГНОВЕННЫЕ КОМБО
        # ══════════════════════════════════════════════════════════════════

        from utils.helpers import get_moscow_time
        now = get_moscow_time()

        # claimed_combos = {combo_name: claimed_at_datetime} — на КД
        claimed_combos = _get_claimed_combos(db, user_id, now)

        combo_coeff, new_combos = calculate_instant_combos(
            text=text, char_count=char_count, word_count=word_count,
            has_photo=has_photo, has_video=has_video,
            completed_today=list(claimed_combos.keys()),
        )

        # ══════════════════════════════════════════════════════════════════
        #  БЛОК 3: СПРИНТЫ
        # ══════════════════════════════════════════════════════════════════

        claimed_sprints = _get_claimed_sprints(db, user_id, now)
        m1, m12, m24 = _query_user_sprint_metrics(db, user_id, today_str)

        sprint_coeff, new_sprints = check_completed_sprints(
            metrics_1h=m1, metrics_12h=m12, metrics_24h=m24,
            current_thread_id=thread_id, already_claimed=claimed_sprints,
        )

        # ══════════════════════════════════════════════════════════════════
        #  БЛОК 4: ШТРАФЫ
        # ══════════════════════════════════════════════════════════════════

        penalty_coeff, penalties = calculate_penalties(
            text=text, thread_id=thread_id, db=db,
            user_id=user_id, chat_id=chat_id,
        )

        # ══════════════════════════════════════════════════════════════════
        #  ЛОГИРОВАНИЕ (подробное, по блокам)
        # ══════════════════════════════════════════════════════════════════

        # ── БАЗА (всегда) ─────────────────────────────────────────────────
        base_rw_log = round(base_coeff * GLOBAL_BASE_RATE, 4)
        logger.info(
            f"💰 БАЗА | user={user_id} | "
            f"{' + '.join(base_triggered)} = {base_coeff}×{GLOBAL_BASE_RATE} = {base_rw_log} 💎"
        )

        # ── КОМБО ─────────────────────────────────────────────────────────
        if new_combos:
            combo_rw_log = round(combo_coeff * GLOBAL_BASE_RATE, 4)
            combo_names = [f"{COMBO_LABELS.get(c, c)} ({COMBO_COEFFICIENTS[c]}x)" for c in new_combos]
            logger.info(
                f"🎭 КОМБО ВЫПОЛНЕНО | user={user_id} | "
                f"{', '.join(combo_names)} = +{combo_rw_log} 💎"
            )

        if claimed_combos:
            cd_parts = [
                f"{COMBO_LABELS.get(c, c)} ({_calc_combo_cooldown(ca, now)})"
                for c, ca in claimed_combos.items()
            ]
            logger.info(
                f"🎭 КОМБО НА КД | user={user_id} | "
                f"{', '.join(cd_parts)}"
            )

        # ── СПРИНТЫ ───────────────────────────────────────────────────────
        if new_sprints:
            sprint_rw_log = round(sprint_coeff * GLOBAL_BASE_RATE, 4)
            sprint_names = [
                f"{SPRINTS_CONFIG[s]['label']} ({SPRINTS_CONFIG[s]['coeff']}x)"
                for s in new_sprints
            ]
            logger.info(
                f"⚡ СПРИНТ ВЫПОЛНЕН | user={user_id} | "
                f"{', '.join(sprint_names)} = +{sprint_rw_log} 💎"
            )

        if claimed_sprints:
            sprint_cd_parts = []
            for s in claimed_sprints:
                if s in SPRINTS_CONFIG:
                    h = SPRINTS_CONFIG[s]['hours']
                    cd = _calc_sprint_cooldown(h, now)
                    sprint_cd_parts.append(f"{SPRINTS_CONFIG[s]['label']} ({cd})")
            if sprint_cd_parts:
                logger.info(
                    f"⚡ СПРИНТ НА КД | user={user_id} | "
                    f"{', '.join(sprint_cd_parts)}"
                )

        # ── ШТРАФЫ ────────────────────────────────────────────────────────
        if penalties:
            penalty_rw_log = round(abs(penalty_coeff) * GLOBAL_BASE_RATE, 4)
            pen_names = [f"{PENALTY_LABELS.get(p, p)} ({PENALTY_COEFFICIENTS.get(p, 0)}x)" for p in penalties]
            logger.warning(
                f"🚫 ШТРАФ | user={user_id} | "
                f"{', '.join(pen_names)} = -{penalty_rw_log} 💎"
            )

        # ══════════════════════════════════════════════════════════════════
        #  ЗАПИСЬ В БД — каждый блок пишет свою транзакцию
        # ══════════════════════════════════════════════════════════════════

        # Считаем награды по блокам (каждая ≥ 0)
        base_rw   = round(max(base_coeff * GLOBAL_BASE_RATE, 0.0), 4)
        combo_rw  = round(combo_coeff * GLOBAL_BASE_RATE, 4) if new_combos else 0.0
        sprint_rw = round(sprint_coeff * GLOBAL_BASE_RATE, 4) if new_sprints else 0.0
        penalty_rw = round(abs(penalty_coeff) * GLOBAL_BASE_RATE, 4) if penalties else 0.0

        # Итого к начислению (база + комбо + спринт - штраф)
        total_reward = round(max(base_rw + combo_rw + sprint_rw - penalty_rw, 0.0), 4)

        if total_reward <= 0:
            return 0.0

        bank_balance = db.get_bank_balance()
        if bank_balance < total_reward:
            logger.warning(f"⚠️ Bank: {bank_balance} < {total_reward}")
            return 0.0

        db.update_user_balance(user_id, total_reward, 'add')
        db.update_bank_balance(total_reward, 'subtract')

        # ── Транзакция 1: База (всегда) ──────────────────────────────────
        if base_rw > 0:
            db.add_transaction(
                None, user_id, base_rw,
                'message_reward',
                'Награда'
            )

        # ── Транзакция 2: Тайное Комбо ───────────────────────────────────
        if combo_rw > 0:
            db.add_transaction(
                None, user_id, combo_rw,
                'combo_reward',
                'Тайное Комбо'
            )

        # ── Транзакция 3: Тайный Спринт ──────────────────────────────────
        if sprint_rw > 0:
            db.add_transaction(
                None, user_id, sprint_rw,
                'sprint_reward',
                'Тайный Спринт'
            )

        # ── Транзакция 4: Штраф (записываем как расход от юзера в банк) ──
        if penalty_rw > 0:
            # Причина штрафа
            penalty_reasons = {
                'copypaste':  'Копипаст',
                'wrong_door': 'Не в ту дверь (Нарушение)',
                'toxic':      'Удаление (Токсик)',
            }
            reason = ', '.join(penalty_reasons.get(p, p) for p in penalties)
            db.add_transaction(
                user_id, None, penalty_rw,
                'penalty_deduct',
                f'Штраф: {reason}'
            )

        db.cursor.execute('''
            INSERT INTO user_stats (user_id, date, pulses_mined)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                pulses_mined = pulses_mined + excluded.pulses_mined
        ''', (user_id, today_str, total_reward))

        db.cursor.execute('''
            INSERT INTO chat_stats (date, total_pulses_mined)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_pulses_mined = total_pulses_mined + excluded.total_pulses_mined
        ''', (today_str, total_reward))

        db.conn.commit()

        # Сохраняем клеймы
        if new_combos:
            _save_combo_claims(db, user_id, new_combos, combo_rw, now)

        if new_sprints:
            _save_sprint_claims(db, user_id, new_sprints, sprint_rw, now)

        # ── Итоговая строка с формулой ─────────────────────────────────
        parts = [f"база:{base_rw}"]
        if combo_rw > 0:
            parts.append(f"комбо:+{combo_rw}")
        if sprint_rw > 0:
            parts.append(f"спринт:+{sprint_rw}")
        if penalty_rw > 0:
            parts.append(f"штраф:-{penalty_rw}")
        logger.info(
            f"✅ НАЧИСЛЕНО | user={user_id} | "
            f"{' | '.join(parts)} | ИТОГО: {total_reward} 💎"
        )
        return total_reward

    except Exception as e:
        logger.error(f"❌ process_mining_reward error user={user_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0.0
