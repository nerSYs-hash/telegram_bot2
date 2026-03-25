#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Журнал событий бота Pulse.
Отправляет логи (вход, выход, заявки, баны) в специальный Telegram-канал.
"""

import os
import logging
from telegram.ext import ContextTypes
from utils.helpers import get_moscow_time

logger = logging.getLogger(__name__)

async def log_event(context: ContextTypes.DEFAULT_TYPE, event_type: str, user_data: dict, extra_data: dict = None):
    """
    Формирует и отправляет сообщение в канал-журнал.
    """
    # Получаем ID канала из .env
    channel_id = os.getenv('JOURNAL_CHANNEL_ID')
    if not channel_id:
        return  # Если канал не настроен, просто игнорируем логирование

    if extra_data is None:
        extra_data = {}

    now = get_moscow_time().strftime('%d.%m.%Y %H:%M:%S МСК')
    
    # Формируем стандартный блок пользователя
    first_name = user_data.get('first_name', 'Без имени')
    user_id = user_data.get('user_id', '0')
    username = f"@{user_data['username']}" if user_data.get('username') else "не указан"
    
    user_link = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
    user_id_text = f"<code>#user{user_id}</code>"
    
    block_b = (
        f"👤 <b>Пользователь:</b> {user_link}\n"
        f"🔗 <b>Никнейм:</b> {username}\n"
        f"🆔 <b>ID:</b> {user_id_text}"
    )
    
    text = ""
    
    # ── СОБЫТИЯ ──
    if event_type == 'new_app':
        text = (
            f"📝 <b>#Новая_заявка</b>\n\n"
            f"{block_b}\n\n"
            f"📋 <b>Анкета:</b>\n"
            f"Имя: {extra_data.get('name')}\n"
            f"Возраст: {extra_data.get('age')}\n"
            f"Город: {extra_data.get('city')}\n"
            f"Терапия: {extra_data.get('therapy')}\n\n"
            f"🕒 Дата: {now}"
        )
        
    elif event_type == 'approved':
        admin_text = f"Одобрил(а): @{extra_data.get('admin_username', 'Система')}"
        text = f"✅ <b>#Одобрено</b>\n{admin_text}\n\n{block_b}\n\n🕒 Дата: {now}"
        
    elif event_type == 'rejected':
        admin_text = f"Отклонил(а): @{extra_data.get('admin_username', 'Система')}"
        reason = extra_data.get('reason', 'Не указана')
        text = f"❌ <b>#Отказ</b>\n{admin_text}\nПричина: <i>{reason}</i>\n\n{block_b}\n\n🕒 Дата: {now}"
        
    elif event_type == 'joined':
        text = f"📥 <b>#Вход</b>\nПользователь зашел в чат.\n\n{block_b}\n\n🕒 Дата: {now}"
        
    elif event_type == 'left':
        text = f"🚪 <b>#Выход</b>\nПользователь покинул чат.\n\n{block_b}\n\n🕒 Дата: {now}"
        
    elif event_type == 'blacklist':
        admin_text = f"Заблокировал(а): @{extra_data.get('admin_username', 'Система')}"
        reason = extra_data.get('reason', 'Не указана')
        text = f"☠️ <b>#Блокировка (ЧС)</b>\n{admin_text}\nПричина: <i>{reason}</i>\n\n{block_b}\n\n🕒 Дата: {now}"

    # Отправляем в канал
    if text:
        try:
            await context.bot.send_message(chat_id=channel_id, text=text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Ошибка отправки в канал-журнал: {e}")