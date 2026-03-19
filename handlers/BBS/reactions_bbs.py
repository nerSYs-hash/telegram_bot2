#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Система «Симпатий» BBS — подсчёт уникальных реакций и начисление бонуса.
"""

import logging
from datetime import datetime

from handlers.BBS.constants_bbs import BBS_BONUS_AMOUNT, BBS_BONUS_COOLDOWN


async def handle_bbs_reaction(reaction_update, context, db, target_chat_id):
    """
    Обработчик реакций для BBS-постов.
    Возвращает True если реакция относилась к BBS, False — нет.
    """
    if not reaction_update:
        return False

    message_id = reaction_update.message_id
    user = reaction_update.user
    if not user:
        return False

    try:
        db.cursor.execute(
            'SELECT id, user_id, reaction_count, bonus_paid_at FROM bbs_profiles WHERE message_ids LIKE ?',
            (f'%{message_id}%',),
        )
        profile = db.cursor.fetchone()
    except Exception:
        return False

    if not profile:
        return False

    profile = dict(profile)
    profile_id = profile['id']
    author_id = profile['user_id']

    if user.id == author_id:
        return True

    try:
        db.cursor.execute(
            'INSERT OR IGNORE INTO bbs_reactions (profile_id, user_id, message_id) VALUES (?, ?, ?)',
            (profile_id, user.id, message_id),
        )
        if db.cursor.rowcount > 0:
            db.cursor.execute(
                "UPDATE bbs_profiles SET reaction_count = reaction_count + 1, updated_at = datetime('now') WHERE id = ?",
                (profile_id,),
            )
            db.conn.commit()
            new_count = profile['reaction_count'] + 1
            logging.info(f"BBS: Profile {profile_id} reaction from {user.id}, total={new_count}")

            if new_count >= 10:
                await _try_award_bonus(db, profile, author_id)
    except Exception as e:
        logging.error(f"BBS: Error processing reaction: {e}")

    return True


async def _try_award_bonus(db, profile, author_id):
    """Начислить бонус за популярность (10 реакций, раз в месяц)."""
    last_paid = profile.get('bonus_paid_at')
    if last_paid:
        try:
            if (datetime.now() - datetime.fromisoformat(last_paid)).days < BBS_BONUS_COOLDOWN:
                return
        except Exception:
            pass

    bank_balance = db.get_bank_balance()
    if bank_balance < BBS_BONUS_AMOUNT:
        logging.warning("BBS: Not enough bank balance for bonus")
        return

    db.update_user_balance(author_id, BBS_BONUS_AMOUNT, 'add')
    db.update_bank_balance(BBS_BONUS_AMOUNT, 'subtract')
    db.add_transaction(None, author_id, BBS_BONUS_AMOUNT, 'bbs_popularity', 'Популярность BBS')

    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.cursor.execute('UPDATE bbs_profiles SET bonus_paid_at = ? WHERE user_id = ?', (now_iso, author_id))
    db.conn.commit()
    logging.info(f"BBS: Awarded {BBS_BONUS_AMOUNT} pulses to {author_id}")
