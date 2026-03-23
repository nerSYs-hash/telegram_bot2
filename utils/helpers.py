#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Facade for utility modules.
This file maintains backward compatibility after refactoring.
"""

# Из formatting.py
from .formatting import (
    to_decimal, to_float, round_decimal, 
    format_number, format_duration, format_month_column,
    escape_markdown, parse_flexible_datetime
)

# Из time_utils.py
from .time_utils import (
    get_moscow_time, get_today_date_msk, calculate_days_in_chat
)

# Из mining.py
from .mining import (
    calculate_mining_reward, calculate_user_activity_score,
    calculate_lottery_chances, calculate_message_quality_score_A,
    calculate_historical_score_B, calculate_combined_quality_multiplier,
    calculate_heat_multiplier
)

# Из message_utils.py
from .message_utils import is_media_message, count_words

# Из referral_utils.py
from .referral_utils import generate_referral_link, check_referral_qualification

# Из statistics.py
from .statistics import Statistics, create_html_report

# Из экспортных модулей
from .export_excel import export_stats_to_excel, export_users_stats_to_excel
from .export_pdf import export_stats_to_pdf
from .export_csv import export_stats_to_csv