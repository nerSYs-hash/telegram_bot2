#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Детектор мёртвых анкет BBS — удаление при уходе из чата.
"""

import logging

from handlers.BBS.database_bbs import get_profile
from handlers.BBS.publishing_bbs import delete_profile_messages


async def cleanup_dead_profiles(bot, db, target_chat_id):
    """Удаляет анкеты пользователей, покинувших чат. Вызывать из scheduler."""
    try:
        db.cursor.execute('SELECT * FROM bbs_profiles')
        profiles = [dict(row) for row in db.cursor.fetchall()]

        for profile in profiles:
            user_id = profile['user_id']
            should_delete = False
            try:
                member = await bot.get_chat_member(target_chat_id, user_id)
                if member.status in ('left', 'kicked'):
                    should_delete = True
            except Exception:
                should_delete = True

            if should_delete:
                await delete_profile_messages(
                    bot, db, profile, target_chat_id, profile.get('thread_id'),
                )
                logging.info(f"BBS: Cleaned up dead profile for user {user_id}")
    except Exception as e:
        logging.error(f"BBS: Error in cleanup: {e}")


async def on_member_left_cleanup(bot, db, user_id, target_chat_id):
    """Вызывается из events_logic при уходе пользователя."""
    profile = get_profile(db, user_id)
    if profile:
        await delete_profile_messages(
            bot, db, profile, target_chat_id, profile.get('thread_id'),
        )
        logging.info(f"BBS: Removed profile for leaving user {user_id}")
