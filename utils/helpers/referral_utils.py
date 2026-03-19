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
    # Check if user has:
    # 1. Been in chat for 24 hours
    # 2. Sent 5+ messages OR received 3+ reactions
    
    user = db.get_user(user_id)
    if not user:
        return False
    
    # Check time in chat (24 hours)
    joined_at = datetime.fromisoformat(user['joined_at'])
    if datetime.now() - joined_at < timedelta(hours=24):
        return False
    
    # Check activity
    today = get_today_date_msk()
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
    
    return messages >= 5 or reactions >= 3
