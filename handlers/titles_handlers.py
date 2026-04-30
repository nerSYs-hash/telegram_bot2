#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
titles_handlers.py — Кастомные титулы V1.16.0.

UI юзера (меню «Баланс → 🏷 Титулы», команда /titles), FSM покупки за Пульсы
и за Рубли, переименование, обработка кнопок Владельца на карточках заявок.

Применение титула — переиспользуем handlers/shop_mechanics.py.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

from handlers.shop_mechanics import apply_title_to_user

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
#  КОНСТАНТЫ
# ════════════════════════════════════════════════════════════════════════════════

# Telegram-лимит на set_chat_administrator_custom_title
MAX_TITLE_LEN = 16
MIN_TITLE_LEN = 1

# Регекс разрешённых символов: латиница, кириллица, цифры, пробел и базовая пунктуация.
_ALLOWED_RE = re.compile(r'^[\w \-_.,!?]+$', re.UNICODE)

# Колбэки
CB_USER_MENU       = 'titles_menu'
CB_PKG_PREFIX      = 'titles_pkg_'           # titles_pkg_<pkg_id>
CB_BUY_PULSES_PRE  = 'titles_buy_pulses_'    # titles_buy_pulses_<pkg_id>
CB_BUY_RUB_PRE     = 'titles_buy_rub_'       # titles_buy_rub_<pkg_id>
CB_RENAME          = 'titles_rename'
CB_CANCEL_REQ_PRE  = 'titles_cancel_req_'    # titles_cancel_req_<request_id>
CB_REQ_APPROVE_PRE = 'titles_req_approve_'   # titles_req_approve_<request_id>
CB_REQ_REJECT_PRE  = 'titles_req_reject_'    # titles_req_reject_<request_id>

# FSM-состояния (используются в ConversationHandler в bot.py)
STATE_AWAIT_TEXT_PULSES = 'TITLE_AWAIT_TEXT_PULSES'
STATE_AWAIT_TEXT_RUB    = 'TITLE_AWAIT_TEXT_RUB'
STATE_AWAIT_RENAME      = 'TITLE_AWAIT_RENAME'
STATE_AWAIT_REJECT_RSN  = 'TITLE_AWAIT_REJECT_REASON'

# user_data ключи (для прокидки контекста между шагами FSM)
UD_PKG_ID         = '_titles_pkg_id'
UD_REJECT_REQ_ID  = '_titles_reject_req_id'


# ════════════════════════════════════════════════════════════════════════════════
#  ВАЛИДАЦИЯ ТЕКСТА ТИТУЛА
# ════════════════════════════════════════════════════════════════════════════════

def validate_title_text(text: str) -> tuple[bool, Optional[str]]:
    """
    Проверка/нормализация текста титула.
    Возвращает (ok, reason). Если ok=True, reason — нормализованный текст.
    Если ok=False, reason — человеческая причина отказа.
    """
    if text is None:
        return False, 'пустой текст'

    # Нормализация: убрать невидимое + схлопнуть пробелы
    cleaned = unicodedata.normalize('NFKC', text).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)

    if not cleaned:
        return False, 'пустой текст'

    if len(cleaned) < MIN_TITLE_LEN or len(cleaned) > MAX_TITLE_LEN:
        return False, f'длина {MIN_TITLE_LEN}–{MAX_TITLE_LEN} символов (у тебя {len(cleaned)})'

    if '\n' in cleaned or '\t' in cleaned:
        return False, 'без переносов строк'

    # Запрещённые символы
    for ch in cleaned:
        cat = unicodedata.category(ch)
        # Пиктограммы, эмодзи и symbol-other — выкидываем
        if cat.startswith('S') and ch not in {'-', '_', '.'}:
            return False, 'без эмодзи и спецсимволов'
        # Контрольные/форматные символы
        if cat in ('Cc', 'Cf', 'Cs', 'Co'):
            return False, 'без управляющих символов'

    if not _ALLOWED_RE.match(cleaned):
        return False, 'разрешены только буквы, цифры, пробел и - _ . , ! ?'

    # Чёрный список явно опасных символов (на всякий случай)
    if any(c in cleaned for c in '<>/\\@#'):
        return False, 'без < > / \\ @ #'

    return True, cleaned


# ════════════════════════════════════════════════════════════════════════════════
#  ПОИСК АКТИВНОГО ТИТУЛА ЮЗЕРА В marketplace_services
# ════════════════════════════════════════════════════════════════════════════════

def get_active_title_row(db, user_id: int) -> Optional[dict]:
    """
    Вернуть dict активной записи title из marketplace_services или None.
    expires_at интерпретируем как в shop_mechanics: если NULL — бессрочно;
    если число (timestamp) и > now — активно.
    """
    import time
    db.cursor.execute(
        "SELECT id, content, expires_at, start_time, status "
        "FROM marketplace_services "
        "WHERE user_id = ? AND service_type = 'title' AND status = 'active' "
        "ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    row = db.cursor.fetchone()
    if not row:
        return None
    rec = dict(row)
    exp = rec.get('expires_at')
    if exp is None or exp == '':
        rec['_is_permanent'] = True
        return rec
    try:
        if float(exp) < time.time():
            return None
        rec['_is_permanent'] = False
    except (TypeError, ValueError):
        # неинтерпретируемое — считаем бессрочным
        rec['_is_permanent'] = True
    return rec


def format_title_remaining(row: dict) -> str:
    """Текст «активно до DD.MM.YYYY (осталось N дн)» или «Бессрочно»."""
    if row.get('_is_permanent'):
        return 'Бессрочно'
    import time
    try:
        exp_ts = float(row['expires_at'])
    except Exception:
        return 'до неизвестной даты'
    exp_dt = datetime.fromtimestamp(exp_ts)
    days_left = max(0, int((exp_ts - time.time()) // 86400))
    return f"до {exp_dt.strftime('%d.%m.%Y')} (осталось {days_left} дн)"


# ════════════════════════════════════════════════════════════════════════════════
#  ВЫДАЧА / ПРОДЛЕНИЕ ТИТУЛА
# ════════════════════════════════════════════════════════════════════════════════

async def apply_title_purchase(db, context, target_chat_id: int, user_id: int,
                               title_text: str,
                               duration_days: Optional[int]) -> dict:
    """
    Применить покупку: новая запись или продление существующей.
    Возвращает {'status': 'ok'|'already_permanent'|'apply_failed',
                'text': str|None, 'expires_at': float|None, 'extended': bool}.
    Списание денег делает вызывающий код ДО этой функции.

    Логика продления:
      - existing бессрочный → ничего не меняем (already_permanent)
      - existing срочный, новый бессрочный → expires_at = NULL
      - existing срочный, новый срочный → expires_at = max(now, existing) + duration
      - existing нет → новая запись с expires_at = now + duration (или NULL)
    Текст при продлении сохраняется (а не подменяется).
    """
    import time
    now_ts = time.time()
    existing = get_active_title_row(db, user_id)

    # Уже бессрочный — кнопку «купить» юзеру лучше не показывать,
    # но если как-то долетел — отвечаем сразу.
    if existing and existing.get('_is_permanent'):
        return {'status': 'already_permanent', 'text': existing.get('content'),
                'expires_at': None, 'extended': False}

    if existing:
        # Продлеваем
        if duration_days is None:
            new_expires = None
        else:
            try:
                base = max(now_ts, float(existing['expires_at']))
            except Exception:
                base = now_ts
            new_expires = base + duration_days * 86400
        title_to_apply = existing['content']
        try:
            db.cursor.execute(
                'UPDATE marketplace_services SET expires_at = ? WHERE id = ?',
                (new_expires, existing['id'])
            )
            db.conn.commit()
        except Exception as e:
            logger.error('apply_title_purchase: update failed: %s', e)
            return {'status': 'apply_failed', 'text': None,
                    'expires_at': None, 'extended': False}
        extended = True
    else:
        # Новая покупка
        if duration_days is None:
            new_expires = None
        else:
            new_expires = now_ts + duration_days * 86400
        title_to_apply = title_text
        try:
            db.cursor.execute(
                "INSERT INTO marketplace_services "
                "(user_id, service_type, status, content, expires_at, start_time) "
                "VALUES (?, 'title', 'active', ?, ?, ?)",
                (user_id, title_text, new_expires, now_ts)
            )
            db.conn.commit()
        except Exception as e:
            logger.error('apply_title_purchase: insert failed: %s', e)
            return {'status': 'apply_failed', 'text': None,
                    'expires_at': None, 'extended': False}
        extended = False

    ok = await apply_title_to_user(context, target_chat_id, user_id, title_to_apply)
    if not ok:
        # Откатываем БД-запись если применение провалилось
        try:
            if extended:
                # Возврат старого expires_at
                db.cursor.execute(
                    'UPDATE marketplace_services SET expires_at = ? WHERE id = ?',
                    (existing['expires_at'], existing['id'])
                )
            else:
                db.cursor.execute(
                    "DELETE FROM marketplace_services WHERE user_id = ? "
                    "AND service_type = 'title' AND status = 'active' "
                    "AND content = ? AND start_time = ?",
                    (user_id, title_text, now_ts)
                )
            db.conn.commit()
        except Exception:
            pass
        return {'status': 'apply_failed', 'text': title_to_apply,
                'expires_at': None, 'extended': extended}

    return {'status': 'ok', 'text': title_to_apply,
            'expires_at': new_expires, 'extended': extended}
