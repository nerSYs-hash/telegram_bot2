#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Железобетонная проверка членства в чате через Telegram API.
API — единственный источник правды. БД — фоллбэк только при сбое API.
"""
import logging
from telegram import Bot
from telegram.constants import ChatMemberStatus

logger = logging.getLogger(__name__)

# Статусы, означающие «пользователь в чате»
_MEMBER_STATUSES = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.OWNER,
}


async def verify_chat_membership(
    bot: Bot,
    chat_id: int,
    user_id: int,
    db=None,
) -> bool:
    """
    Проверяет, находится ли user_id в чате chat_id.

    Логика:
    1. Вызываем Telegram API getChatMember — это ИСТИНА.
    2. Если API ответил — синхронизируем БД (is_left + status в db_friend).
    3. Если API упал (исключение) — фоллбэк на is_left в основной БД.

    Returns True если пользователь реально в чате.
    """
    api_answered = False
    is_member = False

    # ── 1. Telegram API — единственный источник правды ──
    try:
        if chat_id and chat_id != 0:
            member = await bot.get_chat_member(chat_id, user_id)
            api_answered = True

            is_member = (
                member.status in _MEMBER_STATUSES
                or (
                    member.status == ChatMemberStatus.RESTRICTED
                    and getattr(member, 'is_member', True)
                )
            )

            logger.info(
                f"membership_check: user {user_id} -> "
                f"API status={member.status}, is_member={is_member}"
            )
    except Exception as e:
        logger.warning(
            f"membership_check: API call failed for user {user_id}: {e}"
        )

    # ── 2. Если API ответил — синхронизируем обе БД ──
    if api_answered:
        _sync_main_db(db, user_id, is_member)
        await _sync_friend_db(user_id, is_member)
        return is_member

    # ── 3. API не ответил — фоллбэк на основную БД ──
    if db:
        try:
            main_user = db.get_user(user_id)
            if main_user:
                try:
                    is_left = main_user['is_left']
                except (KeyError, IndexError):
                    is_left = 1
                if not is_left:
                    logger.info(
                        f"membership_check: API failed, DB fallback -> "
                        f"user {user_id} is_left=0, treating as member"
                    )
                    return True
        except Exception as e:
            logger.warning(f"membership_check: DB fallback failed for {user_id}: {e}")

    return False


def _sync_main_db(db, user_id: int, is_member: bool):
    """Синхронизирует is_left в основной БД по ответу API."""
    if not db:
        return
    try:
        main_user = db.get_user(user_id)
        if main_user:
            try:
                current_is_left = main_user['is_left']
            except (KeyError, IndexError):
                current_is_left = 1

            new_is_left = 0 if is_member else 1
            if current_is_left != new_is_left:
                db.cursor.execute(
                    "UPDATE users SET is_left = ? WHERE user_id = ?",
                    (new_is_left, user_id),
                )
                db.conn.commit()
                logger.info(
                    f"membership_sync: user {user_id} is_left: "
                    f"{current_is_left} -> {new_is_left}"
                )
    except Exception as e:
        logger.warning(f"membership_sync: main DB sync failed for {user_id}: {e}")


async def _sync_friend_db(user_id: int, is_member: bool):
    """Синхронизирует status в БД друга по ответу API."""
    try:
        from database.db_friend import get_user, update_user
        friend_user = await get_user(user_id)
        if friend_user:
            current_status = friend_user.get('status', '')
            if is_member:
                # В чате — если статус не актуальный, ставим in_chat
                if current_status not in ('in_chat', 'registered'):
                    await update_user(user_id, status='in_chat')
                    logger.info(
                        f"membership_sync: friend DB user {user_id} "
                        f"status: {current_status} -> in_chat"
                    )
            else:
                # Не в чате — если статус говорит что в чате, ставим left
                if current_status in ('in_chat', 'registered', 'approved'):
                    await update_user(user_id, status='left')
                    logger.info(
                        f"membership_sync: friend DB user {user_id} "
                        f"status: {current_status} -> left"
                    )
    except Exception as e:
        logger.warning(f"membership_sync: friend DB sync failed for {user_id}: {e}")
