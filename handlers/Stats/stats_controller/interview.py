#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание: Обработка анкеты при выходе пользователя из чата (exit interview).
Функции: handle_exit_interview.
"""

import logging


async def handle_exit_interview(query, data, context, db):
    """Handle exit interview responses."""
    parts      = data.split('_')
    reason     = parts[1]
    user_id    = int(parts[2])

    reason_map = {
        'flood':    'Слишком много флуда',
        'boring':   'Стало скучно',
        'quality':  'Низкое качество',
        'toxic':    'Токсичная атмосфера',
        'admins':   'Действия админов',
        'personal': 'Личное',
    }
    reason_text = reason_map.get(reason, 'Неизвестная причина')

    db.cursor.execute('INSERT INTO exit_interviews (user_id, reason_category) VALUES (?, ?)', (user_id, reason_text))
    db.conn.commit()

    await query.edit_message_text(
        "Спасибо за ответ! Мы учтем это при улучшении чата.\n\n"
        "Если передумаешь - твои Пульсы заморожены на 30 дней. "
        "Просто вернись в чат, и они вернутся к тебе!"
    )

    if reason in ['toxic', 'admins']:
        try:
            user = db.get_user(user_id)
            username = user['username'] or user['first_name']
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"⚠️ ВАЖНОЕ УВЕДОМЛЕНИЕ\n\n"
                    f"Пользователь @{username} покинул чат.\n"
                    f"Причина: {reason_text}\n\n"
                    f"Рекомендуется проверить ситуацию."
                )
            )
        except Exception:
            pass
