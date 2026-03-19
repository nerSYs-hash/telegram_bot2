#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Утилиты для работы со временем (МСК)."""

from datetime import datetime
import pytz


def get_moscow_time():
    """Get current Moscow time"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)

def get_today_date_msk():
    """Get today's date in MSK"""
    return get_moscow_time().date()

def calculate_days_in_chat(joined_at):
    """Calculate days user has been in chat"""
    if not joined_at:
        return 0
    
    from datetime import datetime
    
    if isinstance(joined_at, str):
        joined_at = datetime.fromisoformat(joined_at.replace('Z', '+00:00'))
    
    now = datetime.now(joined_at.tzinfo) if joined_at.tzinfo else datetime.now()
    delta = now - joined_at
    
    return delta.days
