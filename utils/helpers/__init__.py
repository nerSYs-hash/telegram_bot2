#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils/helpers — пакет-фасад.

Все старые импорты вида:
    from utils.helpers import format_number, get_moscow_time, ...
продолжают работать без изменений.
"""

# ── Formatting ──
from utils.helpers.formatting import (
    format_number,
    format_duration,
    format_month_column,
    escape_markdown,
    # Data Integrity helpers (новые)
    to_decimal,
    to_float,
    round_decimal,
)

# ── Time ──
from utils.helpers.time_utils import (
    get_moscow_time,
    get_today_date_msk,
    calculate_days_in_chat,
)

# ── Mining & Activity ──
from utils.helpers.mining import (
    calculate_mining_reward,
    calculate_user_activity_score,
    calculate_lottery_chances,
)

# ── Message Utils ──
from utils.helpers.message_utils import (
    is_media_message,
    count_words,
)

# ── Referral ──
from utils.helpers.referral_utils import (
    generate_referral_link,
    check_referral_qualification,
)

# ── Statistics ──
from utils.helpers.statistics import (
    Statistics,
    create_html_report,
)

# ── Export ──
from utils.helpers.export_excel import (
    export_stats_to_excel,
    export_users_stats_to_excel,
)
from utils.helpers.export_csv import export_stats_to_csv
from utils.helpers.export_pdf import export_stats_to_pdf

import re

def parse_flexible_datetime(text: str) -> str:
    """
    Преобразует текст с любыми разделителями в формат 'DD.MM.YYYY HH:MM'.
    Возвращает строку формата 'DD.MM.YYYY HH:MM' или None, если формат не распознан.
    """
    from datetime import datetime
    
    # Находим все группы цифр в тексте
    numbers = re.findall(r'\d+', text)
    
    # Если ввели 4 числа: День, Месяц, Часы, Минуты (без года)
    if len(numbers) == 4:
        d, m, h, min_ = numbers
        y = str(datetime.now().year)
        
    # Если ввели 5 чисел: День, Месяц, Год, Часы, Минуты
    elif len(numbers) == 5:
        d, m, y, h, min_ = numbers
        # Если год указан двумя цифрами (26 вместо 2026)
        if len(y) == 2:
            y = "20" + y
    else:
        return None # Неверное количество параметров

    # Добавляем нули слева, если ввели одну цифру (чтобы 5 превратилось в 05)
    d = d.zfill(2)
    m = m.zfill(2)
    h = h.zfill(2)
    min_ = min_.zfill(2)
    
    try:
        # Проверяем, существует ли такая дата (чтобы не ввели 32.13.2026)
        dt = datetime(int(y), int(m), int(d), int(h), int(min_))
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return None # Дата некорректна