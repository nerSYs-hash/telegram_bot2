#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import get_moscow_time

async def send_database_backup(query, user, db, admin_id, context):
    """Отправка дампа базы данных (Бэкап) Владельцу в ЛС"""
    
    # Жесткая проверка: только главный Владелец (ID из .env) может качать базу
    if user.id != admin_id:
        await query.answer("⛔️ Эта функция доступна только главному Владельцу!", show_alert=True)
        return

    await query.answer("⏳ Подготовка резервной копии...", show_alert=False)

    # Получаем путь к файлу БД из вашего db_manager
    db_path = db.db_path 
    
    if not os.path.exists(db_path):
        await query.edit_message_text("❌ Ошибка: Файл базы данных не найден на сервере.")
        return

    # Генерируем красивое имя файла с датой и временем
    now_str = get_moscow_time().strftime('%d_%m_%Y__%H_%M')
    filename = f"pulse_database_{now_str}.db"

    try:
        # Открываем файл базы данных и отправляем как документ
        with open(db_path, 'rb') as doc:
            await context.bot.send_document(
                chat_id=user.id,
                document=doc,
                filename=filename,
                caption=(
                    f"📦 <b>Резервная копия базы данных</b>\n\n"
                    f"📅 Дата: {get_moscow_time().strftime('%d.%m.%Y %H:%M')} МСК\n"
                    f"🛡 <i>Храните этот файл в надежном месте. Никому его не пересылайте!</i>"
                ),
                parse_mode='HTML'
            )
            
        # Обновляем меню
        await query.edit_message_text(
            "✅ Резервная копия успешно отправлена вам в ЛС!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]])
        )
        
    except Exception as e:
        logging.error(f"Ошибка бэкапа БД: {e}")
        await query.edit_message_text(
            f"❌ Ошибка при отправке файла: {e}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]])
        )