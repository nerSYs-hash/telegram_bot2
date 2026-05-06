#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Утилиты для реферальной системы."""

from datetime import datetime, timedelta
from utils.helpers.time_utils import get_today_date_msk


def generate_referral_link(bot_username, user_id, db=None):
    """Generate referral link. If db is provided, uses one-time token system."""
    if db:
        # New one-time link system
        token = db.get_or_create_referral_link(user_id)
        return f"https://t.me/{bot_username}?start={token}"
    else:
        # Legacy static link (fallback)
        import hashlib
        code = f"ref_{hashlib.md5(str(user_id).encode()).hexdigest()[:8]}"
        return f"https://t.me/{bot_username}?start={code}"

def check_referral_qualification(db, user_id):
    """Check if referred user qualifies"""
    # Условия квалификации читаются из economy_settings (referral.qualification_*)
    # с фолбэком на исторические значения 24h / 5 сообщ. / 3 реакции.

    user = db.get_user(user_id)
    if not user:
        return False

    try:
        hours = int(db.get_econ('referral.qualification_hours', 24) or 24)
    except Exception:
        hours = 24

    joined_at = datetime.fromisoformat(user['joined_at'])
    if datetime.now() - joined_at < timedelta(hours=hours):
        return False

    db.cursor.execute('''
        SELECT SUM(total_messages) as msgs, SUM(reactions_received) as reactions
        FROM user_stats
        WHERE user_id = ?
    ''', (user_id,))

    result = db.cursor.fetchone()
    if not result:
        return False

    messages = result['msgs'] or 0
    reactions = result['reactions'] or 0

    try:
        min_msg = int(db.get_econ('referral.qualification_messages', 5) or 5)
        min_react = int(db.get_econ('referral.qualification_reactions', 3) or 3)
    except Exception:
        min_msg, min_react = 5, 3

    return messages >= min_msg or reactions >= min_react
