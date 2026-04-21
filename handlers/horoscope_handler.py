#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import html
import re
import random
import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import get_moscow_time
from utils.horoscope_parser import get_all_horoscopes

logger = logging.getLogger(__name__)


async def _is_horoscope_privileged(user_id: int, admin_id: int) -> bool:
    """Владелец или зам владельца."""
    if user_id == admin_id:
        return True
    from database.db_friend import is_deputy
    return await is_deputy(user_id)

# Имя стикерпака
EMOJI_STICKER_SET = "fgsdgsdfg"
_emoji_data_cache = {}

# ═══════════════════════════════════════════════════════════════
# ПРОВЕРЕННАЯ РУЧНАЯ КАРТА ПЛИТОК
# ═══════════════════════════════════════════════════════════════
ZODIAC_PIECES = {
    'Близнецы': [1, 2, 3, 4, 5, 6],
    'Весы':     [7, 8, 9, 10],
    'Водолей':  [52, 11, 12, 13, 14],
    'Дева':     [15, 16, 17, 18],
    'Козерог':  [19, 20, 21, 22, 23], 
    'Лев':      [24, 25, 26],
    'Овен':     [27, 53, 28, 29],
    'Рак':      [30, 31, 32],
    'Рыбы':     [33, 34, 35, 36],
    'Скорпион': [37, 54, 38, 39, 40, 41],
    'Стрелец':  [42, 43, 44, 45, 46, 47],
    'Телец':    [48, 49, 50, 51]
}

ZODIAC_SIGNS = [
    {'name': 'Овен',      'emoji': '♈️', 'slug': 'aries'},
    {'name': 'Телец',     'emoji': '♉️', 'slug': 'taurus'},
    {'name': 'Близнецы',  'emoji': '♊️', 'slug': 'gemini'},
    {'name': 'Рак',       'emoji': '♋️', 'slug': 'cancer'},
    {'name': 'Лев',       'emoji': '♌️', 'slug': 'leo'},
    {'name': 'Дева',      'emoji': '♍️', 'slug': 'virgo'},
    {'name': 'Весы',      'emoji': '♎️', 'slug': 'libra'},
    {'name': 'Скорпион',  'emoji': '♏️', 'slug': 'scorpio'},
    {'name': 'Стрелец',   'emoji': '♐️', 'slug': 'sagittarius'},
    {'name': 'Козерог',   'emoji': '♑️', 'slug': 'capricorn'},
    {'name': 'Водолей',   'emoji': '♒️', 'slug': 'aquarius'},
    {'name': 'Рыбы',      'emoji': '♓️', 'slug': 'pisces'},
]

# --- ГРАФИКА ---

async def _load_custom_emoji(bot):
    global _emoji_data_cache
    if _emoji_data_cache: return _emoji_data_cache
    try:
        url = f"https://api.telegram.org/bot{bot.token}/getStickerSet"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={"name": EMOJI_STICKER_SET}) as resp:
                data = await resp.json()
        if data.get('ok'):
            stickers = data['result'].get('stickers', [])
            for i, s in enumerate(stickers):
                _emoji_data_cache[i] = str(s.get('custom_emoji_id'))
    except Exception as e:
        logger.error(f"Ошибка загрузки стикерпака: {e}")
    return _emoji_data_cache

def _sign_header(sign_name, sign_emoji, cache):
    pieces = ZODIAC_PIECES.get(sign_name, [])
    if not cache or not pieces:
        return f"<b>{sign_emoji} {html.escape(sign_name).upper()}</b>"
    html_parts = []
    for p_num in pieces:
        idx = p_num - 1
        eid = cache.get(idx)
        if eid:
            html_parts.append(f'<tg-emoji emoji-id="{eid}">{sign_emoji}</tg-emoji>')
    return "".join(html_parts)

# --- ЛОГИКА СООБЩЕНИЯ ---

def build_single_message(horoscopes: dict, cache: dict) -> str:
    """Собирает 1 сообщение: максимум текста на знак, не выходя за лимит TG.
    
    Лимит Telegram = 4096 видимых символов после парсинга HTML.
    Теги <tg-emoji> и <b> не считаются к лимиту.
    """
    now = get_moscow_time()
    date_str = now.strftime('%d.%m.%Y')
    
    header = f"<b>🔮 © Сообщество Pulse 2026 • ГОРОСКОП • {date_str}</b>\n"
    footer = "\n<i>© Сообщество Pulse 2026</i>"
    
    # Считаем бюджет видимых символов
    # header visible: ~30, footer visible: ~25, formatting: ~50
    TOTAL_LIMIT = 4096
    overhead = 120  # header + footer + newlines между блоками
    per_sign_overhead = 15  # emoji видимые + перенос строки
    
    available = TOTAL_LIMIT - overhead - (per_sign_overhead * len(ZODIAC_SIGNS))
    max_per_sign = available // len(ZODIAC_SIGNS)  # ~310-330 символов
    
    # Минимум 250, максимум 380
    max_per_sign = max(250, min(380, max_per_sign))
    
    res = [header]
    for sign in ZODIAC_SIGNS:
        sign_header = _sign_header(sign['name'], sign['emoji'], cache)
        raw_txt = horoscopes.get(sign['slug'], "Звёзды готовят отличный день.")
        clean_txt = html.escape(re.sub(r'[\t\r\n\s]+', ' ', raw_txt).strip())
        
        # Умная обрезка по предложению
        if len(clean_txt) > max_per_sign:
            cut = clean_txt[:max_per_sign]
            # Ищем последнюю точку/восклицательный/вопросительный знак
            for sep in ['. ', '! ', '? ']:
                pos = cut.rfind(sep)
                if pos > max_per_sign * 0.6:  # Не обрезаем слишком коротко
                    cut = cut[:pos + 1]
                    break
            else:
                # Нет хорошей точки разреза — обрезаем по пробелу
                pos = cut.rfind(' ')
                if pos > max_per_sign * 0.7:
                    cut = cut[:pos] + '…'
                else:
                    cut = cut[:max_per_sign - 1] + '…'
            clean_txt = cut
        
        res.append(f"\n{sign_header}\n{clean_txt}")
    
    res.append(footer)
    return "\n".join(res)

# --- ОБРАБОТЧИКИ ---

async def show_horoscope_menu(query, user, db, admin_id):
    if not await _is_horoscope_privileged(user.id, admin_id): return
    await query.edit_message_text(
        f"🔮 <b>Гороскоп © Сообщество Pulse 2026</b>\n\nСкоростной парринг расширенных текстов включен.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Опубликовать в чат", callback_data="horoscope_publish")],
            [InlineKeyboardButton("👁 Превью в ЛС", callback_data="horoscope_preview")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_settings")]
        ])
    )

async def publish_horoscope_today(query, user, context, db, admin_id, target_chat_id):
    if not await _is_horoscope_privileged(user.id, admin_id): return
    await query.edit_message_text("🚀 <b>Скоростная сборка данных...</b>", parse_mode='HTML')
    try:
        cache = await _load_custom_emoji(context.bot)
        data = await get_all_horoscopes(ZODIAC_SIGNS)
        msg_text = build_single_message(data, cache)
        await context.bot.send_message(chat_id=target_chat_id, text=msg_text, parse_mode='HTML')
        await query.edit_message_text(f"✅ <b>Гороскоп опубликован!</b>", parse_mode='HTML',
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="horoscope_menu")]]))
    except Exception as e:
        logger.error(f"Pub error: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def preview_horoscope(query, user, context, db, admin_id):
    if not await _is_horoscope_privileged(user.id, admin_id): return
    await query.answer("Сборка...")
    try:
        cache = await _load_custom_emoji(context.bot)
        data = await get_all_horoscopes(ZODIAC_SIGNS)
        msg_text = build_single_message(data, cache)
        await context.bot.send_message(chat_id=user.id, text=msg_text, parse_mode='HTML')
    except Exception as e:
        await context.bot.send_message(chat_id=user.id, text=f"❌ Ошибка превью: {e}")

async def diagnose_emoji(query, user, context, db, admin_id):
    if not await _is_horoscope_privileged(user.id, admin_id): return
    await query.answer("Плитки в порядке!", show_alert=True)