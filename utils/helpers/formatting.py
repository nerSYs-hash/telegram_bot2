#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Форматирование чисел и текста.

Data Integrity: числовые операции выполняются через Decimal
для исключения ошибок округления с плавающей точкой.
"""
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


# ── Утилиты Decimal (Data Integrity) ─────────────────────────────────────────

def to_decimal(val) -> Decimal:
    """
    Безопасно конвертирует любое значение в Decimal.
    Используй вместо float() везде, где важна точность.
    """
    if isinstance(val, Decimal):
        return val
    if val is None:
        return Decimal('0')
    try:
        cleaned = str(val).replace(' ', '').replace(',', '.')
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal('0')


def to_float(val) -> float:
    """
    Конвертирует значение в float через Decimal (без потери точности).
    Используй для записи числа в Excel/PDF ячейку.
    """
    return float(to_decimal(val))


def round_decimal(val, places: int = 2) -> Decimal:
    """Округляет до заданного числа знаков через ROUND_HALF_UP."""
    d = to_decimal(val)
    q = Decimal('0.' + '0' * places) if places > 0 else Decimal('1')
    return d.quantize(q, rounding=ROUND_HALF_UP)


# ── Форматирование для отображения (строки) ───────────────────────────────────

def format_month_column(month_num, year, current_year):
    """
    Форматирует месяц для заголовка столбца Excel с учетом года.

    Примеры:
        Январь текущего года (2025) -> "01"
        Январь следующего года (2026) -> "1`26"
        Декабрь 2026 -> "12`26"

    Args:
        month_num (int): номер месяца (1-12)
        year (int): год месяца
        current_year (int): текущий год для сравнения

    Returns:
        str: отформатированный месяц для заголовка
    """
    if year != current_year:
        month_str = str(month_num)
        year_suffix = str(year)[-2:]
        return f"{month_str}`{year_suffix}"
    else:
        return f"{month_num:02d}"


def format_number(num) -> str:
    """
    Форматирует число для отображения в тексте/Telegram-сообщениях.
    Возвращает СТРОКУ с пробелами-разделителями и 2 знаками после запятой.

    ⚠️  Только для отображения!
    Для записи в Excel/PDF ячейку — используй to_float() или round_decimal().
    """
    d = to_decimal(num)
    formatted = "{:,.2f}".format(float(d)).replace(',', ' ')
    return formatted


def format_duration(seconds) -> str:
    """Format duration in human-readable format."""
    seconds = int(to_decimal(seconds))
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} мин"
    else:
        hours = seconds // 3600
        return f"{hours} ч"


def escape_markdown(text: str) -> str:
    """Escape markdown special characters."""
    special_chars = [
        '_', '*', '[', ']', '(', ')', '~', '`', '>',
        '#', '+', '-', '=', '|', '{', '}', '.', '!'
    ]
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


    """
    Преобразует текст с любыми разделителями в формат 'DD.MM.YYYY HH:MM'.
    Возвращает строку формата 'DD.MM.YYYY HH:MM' или None, если формат не распознан/неверен.
    """
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