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


async def track_profile_changes(bot, db, user, chat=None) -> None:
    """
    Сравнивает текущий профиль с БД, логирует изменения в журнал.
    Должен вызываться ДО db.add_user(), чтобы получить старое состояние.

    Args:
        bot: telegram.Bot
        db: Database
        user: telegram.User (from_user) — новое состояние
        chat: telegram.Chat — чат где произошло событие (опционально)
    """
    if not user:
        return

    try:
        user_data = db.get_user(user.id)
    except Exception:
        user_data = None

    has_changes = False

    if user_data:
        # ── Username ──
        try:
            old_username = user_data['username']
        except (KeyError, IndexError):
            old_username = None
        if old_username != user.username:
            has_changes = True

        # ── Имя ──
        try:
            old_first = user_data['first_name']
        except (KeyError, IndexError):
            old_first = None
        if old_first != user.first_name:
            has_changes = True

        # ── Фамилия ──
        try:
            old_last = user_data['last_name']
        except (KeyError, IndexError):
            old_last = None
        if old_last != user.last_name:
            has_changes = True

    if has_changes and user_data:
        try:
            from handlers.journal_handlers import log_profile_change
            from datetime import datetime, timezone
            await log_profile_change(
                bot, db, user.id,
                tg_user=user,
                old_user_data=user_data,
                chat=chat,
                changed_at=datetime.now(timezone.utc),
            )
            logger.info(f"PROFILE CHANGE: user {user.id}")
        except Exception as e:
            logger.error(f"Profile tracker journal error: {e}")

    # ── Фото профиля ──
    try:
        photos = await bot.get_user_profile_photos(user.id, limit=1)
        if photos and photos.total_count > 0:
            current_uid = photos.photos[0][0].file_unique_id
        else:
            current_uid = ''

        stored_raw = db.get_setting(f'photo_uid_{user.id}')
        # None = ещё не отслеживали этого юзера (первое сообщение) — инициализируем без лога
        first_seen = stored_raw is None
        stored_uid = stored_raw or ''

        if first_seen:
            db.set_setting(f'photo_uid_{user.id}', current_uid)
            logger.info(f"PHOTO TRACKER INIT: user {user.id} uid={current_uid!r}")
        elif current_uid != stored_uid:
            db.set_setting(f'photo_uid_{user.id}', current_uid)
            if stored_uid == '' and current_uid:
                action = 'opened'   # раньше не было / скрыто — открыл
            elif current_uid == '':
                action = 'removed'  # скрыл/удалил фото
            else:
                action = 'changed'  # сменил фото

            from handlers.journal_handlers import log_photo
            await log_photo(bot, db, user.id, chat=chat, tg_user=user, action=action)
            logger.info(f"PHOTO CHANGE ({action}): user {user.id} {stored_uid!r} -> {current_uid!r}")
    except Exception as e:
        logger.error(f"Photo tracker error (user {user.id}): {e}", exc_info=True)
