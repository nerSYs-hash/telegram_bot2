#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Трекер изменений профиля.

Путь: handlers/profile_tracker.py

Сравнивает текущие данные Telegram-пользователя с БД.
При изменении username/first_name/last_name → логирует в журнал.

Использование в message_handler.py:
    from handlers.profile_tracker import track_profile_changes
    # Вызвать ПОСЛЕ db.add_user() в handle_message
    await track_profile_changes(context.bot, db, user)
"""

import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


async def track_profile_changes(bot, db, user) -> None:
    """
    Сравнивает текущий профиль с БД, логирует изменения в журнал.

    Args:
        bot: telegram.Bot
        db: Database
        user: telegram.User (from_user)
    """
    if not user:
        return

    try:
        user_data = db.get_user(user.id)
    except Exception:
        return

    if not user_data:
        return

    changes: List[str] = []

    # ── Username ──
    old_username = user_data['username']
    new_username = user.username
    if old_username != new_username:
        old_val = f"@{old_username}" if old_username else "<i>пусто</i>"
        new_val = f"@{new_username}" if new_username else "<i>пусто</i>"
        changes.append(f"📛 Ник: {old_val} → {new_val}")

    # ── Имя ──
    old_first = user_data['first_name']
    new_first = user.first_name
    if old_first != new_first:
        old_val = old_first or "<i>пусто</i>"
        new_val = new_first or "<i>пусто</i>"
        changes.append(f"👤 Имя: {old_val} → {new_val}")

    # ── Фамилия ──
    old_last = user_data['last_name']
    new_last = user.last_name
    if old_last != new_last:
        old_val = old_last or "<i>пусто</i>"
        new_val = new_last or "<i>пусто</i>"
        changes.append(f"👤 Фамилия: {old_val} → {new_val}")

    if not changes:
        return

    # Логируем в журнал
    try:
        from handlers.journal_handlers import log_profile_change
        changes_text = "\n".join(changes)
        await log_profile_change(bot, db, user.id, changes_text)
        logger.info(f"PROFILE CHANGE: user {user.id} — {len(changes)} changes")
    except Exception as e:
        logger.error(f"Profile tracker journal error: {e}")
