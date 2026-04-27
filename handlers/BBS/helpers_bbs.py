#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вспомогательные функции BBS: работа с FSM-стейтом, парсеры, сборка текста анкеты.
"""

import re
import json
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from handlers.BBS.constants_bbs import CITY_MAP, NAME_REGEX


# ═══════════════════════════════════════════════════════════════
# FSM-УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════

def get_bbs_state(context) -> str | None:
    return context.user_data.get('bbs_state')


def set_bbs_state(context, state):
    context.user_data['bbs_state'] = state


def get_bbs_data(context) -> dict:
    if 'bbs_data' not in context.user_data:
        context.user_data['bbs_data'] = {
            'photos': [],
            'name': None,
            'age': None,
            'params': {},
            'roles': [],
            'city': [],
            'goals': [],
            'about': None,
        }
    return context.user_data['bbs_data']


def clear_bbs(context):
    """Сбросить FSM и все временные данные BBS."""
    for key in (
        'bbs_state', 'bbs_data', 'bbs_param_editing', 'bbs_photo_msg_id',
        'bbs_editing_profile_id', 'bbs_edit_photos', 'bbs_edit_cities',
        'bbs_edit_goals', 'bbs_edit_roles', 'bbs_edit_params',
        'bbs_edit_param_editing', 'bbs_edit_chat_id', 'bbs_edit_thread_id',
    ):
        context.user_data.pop(key, None)


# ═══════════════════════════════════════════════════════════════
# ПАРСЕРЫ
# ═══════════════════════════════════════════════════════════════

def city_to_hashtag(city_text: str) -> str:
    """
    Конвертирует город в хештег:
    1) Ищет в словаре CITY_MAP (нижний регистр)
    2) Если не найден — пробелы/дефисы → _, убирает спецсимволы, ставит #
    Примеры:
      'Нижний Новгород' → '#Ниж_Новгород' (из словаря)
      'Кудрово'         → '#Кудрово'       (авто)
      'Верхняя Пышма'   → '#Верхняя_Пышма' (авто)
    """
    city_text = city_text.strip()
    key = city_text.lower().strip()

    # 1) Поиск в словаре
    if key in CITY_MAP:
        return CITY_MAP[key]

    # 2) Авто: пробелы/дефисы → _, убрать всё кроме букв/цифр/_
    cleaned = re.sub(r'[\s\-]+', '_', city_text)
    cleaned = re.sub(r'[^\w]', '', cleaned)
    if not cleaned.startswith('#'):
        cleaned = f'#{cleaned}'
    return cleaned


def parse_age(text: str) -> int | None:
    """
    Парсит возраст: число '25' или дата '15.03.1998' / '15,03,1998'.
    Возвращает полных лет (18–99) или None.
    """
    text = text.strip()

    if text.isdigit():
        age = int(text)
        return age if 18 <= age <= 99 else None

    # Нормализация разделителей
    normalized = text.replace(',', '.').replace('-', '.').replace('/', '.')

    try:
        birth = datetime.strptime(normalized, '%d.%m.%Y')
        today = datetime.now()
        age = today.year - birth.year
        if (today.month, today.day) < (birth.month, birth.day):
            age -= 1
        return age if 18 <= age <= 99 else None
    except ValueError:
        return None


# ═══════════════════════════════════════════════════════════════
# СБОРКА ТЕКСТА АНКЕТЫ
# ═══════════════════════════════════════════════════════════════

def _json_load(val, default=None):
    """Безопасный JSON-парсинг."""
    if default is None:
        default = []
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return default
    return val if val else default


VIP_EMOJI = '<tg-emoji emoji-id="5949775417274536507">👑</tg-emoji>'


def build_profile_text(data: dict, vip_active: bool = False) -> str:
    """Собирает текст анкеты для публикации (HTML).
    vip_active=True добавляет VIP-эмодзи в начало текста.
    Пропущенные шаги не показываются. Названия полей убраны — только значения."""
    lines = []

    # Строка 1: 👤 Имя, Возраст  #Город
    city = _json_load(data.get('city'))
    city_str = ' '.join(city) if city else ''
    name_line = f"👤 <b>{data['name']}, {data['age']}</b>"
    if city_str:
        name_line += f"  {city_str}"
    lines.append(name_line)

    # Строка 2: 📏 Рост ⚖️ Вес 💦 Размер  #Роль
    params = _json_load(data.get('params'), {})
    roles = _json_load(data.get('roles'))

    second_parts = []
    if isinstance(params, dict) and params:
        if params.get('height'):
            second_parts.append(f"📏 {params['height']}см")
        if params.get('weight'):
            second_parts.append(f"⚖️ {params['weight']}кг")
        if params.get('size'):
            second_parts.append(f"💦 {params['size']}см")
    if roles:
        second_parts.append(' '.join(roles))
    if second_parts:
        lines.append('  '.join(second_parts))

    goals = _json_load(data.get('goals'))
    if goals:
        lines.append(' '.join(goals))

    about = data.get('about')
    if about:
        lines.append(f"\n{about}")

    text = '\n'.join(lines)
    if vip_active:
        text = VIP_EMOJI + '\n' + text
    return text


def write_button(user_id: int, bot_username: str = None) -> InlineKeyboardMarkup:
    """Кнопки под анкетой: Написать | Пожаловаться | Подать объявление.
    Пожаловаться — через Deep Link в ЛС бота (работает из группы)."""
    row1 = [
        InlineKeyboardButton("💌 Написать в ЛС", url=f"tg://user?id={user_id}"),
    ]
    row2 = []
    if bot_username:
        row1.append(
            InlineKeyboardButton("⚠️Пожаловаться", url=f"https://t.me/{bot_username}?start=report_{user_id}")
        )
        row2.append(InlineKeyboardButton(
            "📝 Подать объявление", url=f"https://t.me/{bot_username}?start=bbs"
        ))
    return InlineKeyboardMarkup([row1] + ([row2] if row2 else []))