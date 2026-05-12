#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Захват чатов и топиков, где есть бот (V1.16.14).

• handle_my_chat_member: ловит событие добавления/удаления бота → upsert в bot_chats
• track_topic_from_message: вызывается из MessageHandler — пишет thread_id+name
  в bot_chat_topics при сообщении в форум-топике
• backfill_known_chats: при старте бота — добавляет target_chat_id и известные топики
"""

import logging
from telegram import Update, ChatMemberUpdated
from telegram.ext import ContextTypes

from database.db_press_release import (
    upsert_bot_chat, mark_bot_chat_removed, upsert_bot_chat_topic,
)

logger = logging.getLogger(__name__)

# Multi-tenancy placeholder (V1.17.0a14). При добавлении бота в новый чат
# workspace=1 (Pulse Москва). Подпроект #2 (Bot connection flow) сделает
# onboarding нового workspace при добавлении бота владельцем.
_DEFAULT_WS_ID = 1


# ════════════════════════════════════════════════════════════════════
# my_chat_member — бота добавили / удалили / поменяли права
# ════════════════════════════════════════════════════════════════════

def _is_bot_present(status: str) -> bool:
    """status строка — присутствует ли бот в чате."""
    return status in ('member', 'administrator', 'creator', 'restricted')


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ChatMemberHandler.MY_CHAT_MEMBER — для самого бота."""
    cmu: ChatMemberUpdated = update.my_chat_member
    if not cmu:
        return

    chat = cmu.chat
    new_status = cmu.new_chat_member.status if cmu.new_chat_member else None
    old_status = cmu.old_chat_member.status if cmu.old_chat_member else None

    db = context.bot_data.get('db')
    if not db:
        return

    try:
        if _is_bot_present(new_status):
            upsert_bot_chat(
                db,
                _DEFAULT_WS_ID,
                chat_id=chat.id,
                chat_type=chat.type,
                title=chat.title or '',
                username=chat.username or '',
                is_forum=bool(getattr(chat, 'is_forum', False)),
            )
            logger.info(
                f"bot added/updated in chat {chat.id} ({chat.type}) "
                f"'{chat.title}' status={new_status}"
            )
        elif _is_bot_present(old_status) and not _is_bot_present(new_status):
            mark_bot_chat_removed(db, chat.id)
            logger.info(f"bot removed from chat {chat.id} '{chat.title}'")
    except Exception as e:
        logger.error(f"handle_my_chat_member error: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════
# Захват топиков по факту получения сообщения
# ════════════════════════════════════════════════════════════════════

def track_topic_from_message(message, db) -> None:
    """
    Если сообщение пришло в форум-топик — апсертим (chat_id, thread_id, name).
    Безопасно вызывать из MessageHandler.handle_message.
    """
    if not message or not db:
        return
    try:
        chat = message.chat
        if not chat or not getattr(chat, 'is_forum', False):
            return
        thread_id = getattr(message, 'message_thread_id', None)
        if not thread_id:
            return
        # Топик-имя, если это создание топика
        name = None
        if getattr(message, 'forum_topic_created', None):
            name = message.forum_topic_created.name
        elif getattr(message, 'forum_topic_edited', None):
            name = message.forum_topic_edited.name
        upsert_bot_chat_topic(db, _DEFAULT_WS_ID, chat.id, thread_id, name=name, source='auto')
    except Exception as e:
        logger.debug(f"track_topic_from_message: {e}")


# ════════════════════════════════════════════════════════════════════
# Бэкфил при старте: target_chat_id + ранее известные топики
# ════════════════════════════════════════════════════════════════════

async def backfill_known_chats(application, db, target_chat_id: int) -> None:
    """
    Разовый бэкфил при старте бота:
      1) Добавляем target_chat_id в bot_chats (через get_chat)
      2) Пробрасываем уже известные топики из db.get_all_topics() в bot_chat_topics
    """
    if not target_chat_id:
        return
    try:
        chat = await application.bot.get_chat(target_chat_id)
        upsert_bot_chat(
            db,
            _DEFAULT_WS_ID,
            chat_id=chat.id,
            chat_type=chat.type,
            title=chat.title or '',
            username=chat.username or '',
            is_forum=bool(getattr(chat, 'is_forum', False)),
        )
        logger.info(f"backfill: target chat {chat.id} '{chat.title}' → bot_chats")
    except Exception as e:
        logger.warning(f"backfill: get_chat({target_chat_id}) failed: {e}")

    # Старая таблица topics — переливаем в bot_chat_topics
    try:
        topics = db.get_all_topics(target_chat_id) if hasattr(db, 'get_all_topics') else []
        cnt = 0
        for t in topics or []:
            tid = t.get('thread_id') if isinstance(t, dict) else t['thread_id']
            tname = t.get('thread_name') if isinstance(t, dict) else t['thread_name']
            if tid:
                upsert_bot_chat_topic(db, _DEFAULT_WS_ID, target_chat_id, tid, name=tname, source='auto')
                cnt += 1
        if cnt:
            logger.info(f"backfill: {cnt} topics → bot_chat_topics")
    except Exception as e:
        logger.warning(f"backfill topics: {e}")
