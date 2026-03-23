#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Опрос при выходе — многошаговый Exit Survey.

Путь: handlers/exit_survey_handlers.py

Шаги:
  1. Причина ухода (кнопки или свободный текст)
  2. Что можно улучшить? (кнопки)
  3. Вернулись бы при каком-то событии? (кнопки)
  4. Финал — благодарность

Результаты сохраняются в exit_interviews и доступны владельцу.
"""

import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import format_number

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  МИГРАЦИЯ: дополнительные колонки
# ═══════════════════════════════════════════════════════════════

def ensure_survey_columns(db) -> None:
    """Добавляет колонки improvement и would_return в exit_interviews."""
    try:
        db.cursor.execute("PRAGMA table_info(exit_interviews)")
        cols = {row[1] for row in db.cursor.fetchall()}
        for col, typ in [('improvement', 'TEXT'), ('would_return', 'TEXT')]:
            if col not in cols:
                db.cursor.execute(f'ALTER TABLE exit_interviews ADD COLUMN {col} {typ}')
        db.conn.commit()
    except Exception as e:
        logger.error(f"ensure_survey_columns error: {e}")


# ═══════════════════════════════════════════════════════════════
#  КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════

REASON_MAP = {
    'flood':    '🔇 Слишком много флуда',
    'boring':   '🥱 Стало скучно',
    'quality':  '📉 Низкое качество',
    'toxic':    '☠️ Токсичная атмосфера',
    'admins':   '👮 Действия админов',
    'personal': '👤 Личные причины',
}

IMPROVEMENT_MAP = {
    'content':    '📝 Интересный контент',
    'moderation': '🛡 Лучшая модерация',
    'events':     '🎉 Больше мероприятий',
    'community':  '👥 Атмосфера в сообществе',
    'nothing':    '🤷 Ничего / всё нормально',
}

RETURN_MAP = {
    'events':    '🎉 Если будут мероприятия',
    'changes':   '🔄 Если что-то изменится',
    'maybe':     '🤔 Может быть, позже',
    'no':        '❌ Точно нет',
}


# ═══════════════════════════════════════════════════════════════
#  ШАГ 1: ПРИЧИНА УХОДА (callback из events_logic)
# ═══════════════════════════════════════════════════════════════

async def handle_exit_reason(query, data: str, context, db, admin_id: int) -> None:
    """
    Обработчик callback-ов exit_{reason}_{user_id}.
    Сохраняет причину → показывает Шаг 2.
    """
    ensure_survey_columns(db)

    parts = data.split('_')
    # exit_reason_userid  → parts = ['exit', 'reason', 'userid']
    if len(parts) < 3:
        await query.answer("❌ Ошибка.", show_alert=True)
        return

    reason_key = parts[1]
    user_id = int(parts[2])

    # Кнопка «Написать причину» — ожидаем текстовый ввод
    if reason_key == 'custom':
        context.user_data['exit_survey_user_id'] = user_id
        context.user_data['exit_survey_awaiting'] = 'custom_reason'

        await query.edit_message_text(
            "📝 <b>Расскажите, почему вы покинули чат?</b>\n\n"
            "Напишите свободным текстом — это поможет нам стать лучше.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Пропустить", callback_data=f"exit_skip_reason_{user_id}")]
            ])
        )
        return

    reason_text = REASON_MAP.get(reason_key, 'Не указана')

    # Сохраняем причину в БД
    try:
        db.cursor.execute(
            'INSERT INTO exit_interviews (user_id, reason_category) VALUES (?, ?)',
            (user_id, reason_text)
        )
        db.conn.commit()
        interview_id = db.cursor.lastrowid
        context.user_data['exit_interview_id'] = interview_id
    except Exception as e:
        logger.error(f"Exit survey save reason error: {e}")
        await query.answer("❌ Ошибка сохранения.", show_alert=True)
        return

    # Уведомляем владельца о важных причинах
    if reason_key in ('toxic', 'admins'):
        await _notify_admin_about_reason(context, db, user_id, reason_text, admin_id)

    # → Шаг 2: Что улучшить?
    await _show_improvement_step(query, user_id)


async def handle_exit_skip_reason(query, data: str, context, db) -> None:
    """Пропуск текстового ввода причины."""
    parts = data.split('_')
    user_id = int(parts[-1])

    context.user_data.pop('exit_survey_awaiting', None)

    try:
        db.cursor.execute(
            'INSERT INTO exit_interviews (user_id, reason_category) VALUES (?, ?)',
            (user_id, 'Не указана')
        )
        db.conn.commit()
        context.user_data['exit_interview_id'] = db.cursor.lastrowid
    except Exception:
        pass

    await _show_improvement_step(query, user_id)


# ═══════════════════════════════════════════════════════════════
#  ШАГ 2: ЧТО МОЖНО УЛУЧШИТЬ?
# ═══════════════════════════════════════════════════════════════

async def _show_improvement_step(query, user_id: int) -> None:
    text = (
        "💡 <b>Что мы могли бы улучшить?</b>\n\n"
        "Выберите или пропустите:"
    )
    keyboard = []
    for key, label in IMPROVEMENT_MAP.items():
        keyboard.append([InlineKeyboardButton(label, callback_data=f"exitimp_{key}_{user_id}")])
    keyboard.append([InlineKeyboardButton("⏭ Пропустить", callback_data=f"exitimp_skip_{user_id}")])

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_exit_improvement(query, data: str, context, db) -> None:
    """Обработка шага 2 — что улучшить."""
    parts = data.replace("exitimp_", "").rsplit("_", 1)
    imp_key = parts[0]
    user_id = int(parts[1])

    interview_id = context.user_data.get('exit_interview_id')

    if imp_key != 'skip' and interview_id:
        imp_text = IMPROVEMENT_MAP.get(imp_key, imp_key)
        try:
            db.cursor.execute(
                'UPDATE exit_interviews SET improvement = ? WHERE id = ?',
                (imp_text, interview_id)
            )
            db.conn.commit()
        except Exception as e:
            logger.error(f"Exit survey improvement save error: {e}")

    # → Шаг 3: Вернулись бы?
    await _show_return_step(query, user_id)


# ═══════════════════════════════════════════════════════════════
#  ШАГ 3: ВЕРНУЛИСЬ БЫ?
# ═══════════════════════════════════════════════════════════════

async def _show_return_step(query, user_id: int) -> None:
    text = (
        "🔄 <b>Вы бы вернулись в чат?</b>\n\n"
        "Выберите вариант:"
    )
    keyboard = []
    for key, label in RETURN_MAP.items():
        keyboard.append([InlineKeyboardButton(label, callback_data=f"exitret_{key}_{user_id}")])
    keyboard.append([InlineKeyboardButton("⏭ Пропустить", callback_data=f"exitret_skip_{user_id}")])

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_exit_return(query, data: str, context, db) -> None:
    """Обработка шага 3 — вернулись бы."""
    parts = data.replace("exitret_", "").rsplit("_", 1)
    ret_key = parts[0]
    user_id = int(parts[1])

    interview_id = context.user_data.get('exit_interview_id')

    if ret_key != 'skip' and interview_id:
        ret_text = RETURN_MAP.get(ret_key, ret_key)
        try:
            db.cursor.execute(
                'UPDATE exit_interviews SET would_return = ? WHERE id = ?',
                (ret_text, interview_id)
            )
            db.conn.commit()
        except Exception as e:
            logger.error(f"Exit survey return save error: {e}")

    # → Финал
    await _show_survey_thanks(query, user_id, db)


# ═══════════════════════════════════════════════════════════════
#  ФИНАЛ: СПАСИБО
# ═══════════════════════════════════════════════════════════════

async def _show_survey_thanks(query, user_id: int, db) -> None:
    user_data = db.get_user(user_id)
    frozen = 0
    if user_data:
        frozen = user_data.get('frozen_balance', 0) if hasattr(user_data, 'get') else user_data['frozen_balance']

    frozen_text = ""
    if frozen and frozen > 0:
        frozen_text = (
            f"\n\n❄️ Напоминаем: твои <b>{format_number(frozen)}</b> Пульсов "
            f"заморожены на 30 дней. Вернись — и они вернутся к тебе!"
        )

    text = (
        "🙏 <b>Спасибо за обратную связь!</b>\n\n"
        "Мы ценим каждое мнение и обязательно учтём твой ответ "
        "при улучшении нашего сообщества."
        f"{frozen_text}\n\n"
        "Двери всегда открыты 💙"
    )

    await query.edit_message_text(text, parse_mode='HTML')


# ═══════════════════════════════════════════════════════════════
#  FSM: ОБРАБОТКА ТЕКСТОВОГО ВВОДА (свободная причина)
# ═══════════════════════════════════════════════════════════════

async def handle_exit_survey_text(update, context, db) -> bool:
    """
    Обработчик текстового ввода при exit survey.
    Вызывается из message_handler → handle_private_message.
    Возвращает True если обработано.
    """
    awaiting = context.user_data.get('exit_survey_awaiting')
    if not awaiting:
        return False

    message = update.effective_message
    text = message.text.strip() if message.text else ''
    user_id = context.user_data.get('exit_survey_user_id')

    if awaiting == 'custom_reason' and user_id:
        context.user_data.pop('exit_survey_awaiting', None)
        context.user_data.pop('exit_survey_user_id', None)

        reason_text = text[:500]  # Ограничиваем длину

        try:
            db.cursor.execute(
                'INSERT INTO exit_interviews (user_id, reason_category, reason_text) VALUES (?, ?, ?)',
                (user_id, '📝 Свой текст', reason_text)
            )
            db.conn.commit()
            context.user_data['exit_interview_id'] = db.cursor.lastrowid
        except Exception as e:
            logger.error(f"Exit survey custom reason save error: {e}")

        # → Шаг 2
        imp_text = (
            "💡 <b>Что мы могли бы улучшить?</b>\n\n"
            "Выберите или пропустите:"
        )
        keyboard = []
        for key, label in IMPROVEMENT_MAP.items():
            keyboard.append([InlineKeyboardButton(label, callback_data=f"exitimp_{key}_{user_id}")])
        keyboard.append([InlineKeyboardButton("⏭ Пропустить", callback_data=f"exitimp_skip_{user_id}")])

        await message.reply_text(imp_text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    return False


# ═══════════════════════════════════════════════════════════════
#  УВЕДОМЛЕНИЕ АДМИНА
# ═══════════════════════════════════════════════════════════════

async def _notify_admin_about_reason(context, db, user_id, reason_text, admin_id) -> None:
    """Уведомляет владельца о важных причинах ухода (токсичность, действия админов)."""
    try:
        user = db.get_user(user_id)
        if user:
            name = user['username'] or user['first_name'] or f"ID:{user_id}"
        else:
            name = f"ID:{user_id}"

        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"⚠️ <b>ВАЖНОЕ УВЕДОМЛЕНИЕ</b>\n\n"
                f"Пользователь @{name} покинул чат.\n"
                f"Причина: <b>{reason_text}</b>\n\n"
                f"Рекомендуется проверить ситуацию."
            ),
            parse_mode='HTML',
        )
    except Exception as e:
        logger.error(f"Exit survey admin notification error: {e}")


# ═══════════════════════════════════════════════════════════════
#  ДАШБОРД РЕЗУЛЬТАТОВ (для владельца)
# ═══════════════════════════════════════════════════════════════

async def show_survey_results(query, db, admin_id: int) -> None:
    """Показывает статистику exit-опросов."""
    ensure_survey_columns(db)

    # Общее количество
    db.cursor.execute('SELECT COUNT(*) as cnt FROM exit_interviews')
    total = db.cursor.fetchone()['cnt']

    # По причинам
    db.cursor.execute('''
        SELECT reason_category, COUNT(*) as cnt 
        FROM exit_interviews 
        GROUP BY reason_category 
        ORDER BY cnt DESC LIMIT 10
    ''')
    reasons = db.cursor.fetchall()

    # По улучшениям
    db.cursor.execute('''
        SELECT improvement, COUNT(*) as cnt 
        FROM exit_interviews 
        WHERE improvement IS NOT NULL 
        GROUP BY improvement 
        ORDER BY cnt DESC LIMIT 5
    ''')
    improvements = db.cursor.fetchall()

    # По возврату
    db.cursor.execute('''
        SELECT would_return, COUNT(*) as cnt 
        FROM exit_interviews 
        WHERE would_return IS NOT NULL 
        GROUP BY would_return 
        ORDER BY cnt DESC LIMIT 5
    ''')
    returns = db.cursor.fetchall()

    # Последние 5
    db.cursor.execute('''
        SELECT ei.*, u.username, u.first_name 
        FROM exit_interviews ei
        LEFT JOIN users u ON ei.user_id = u.user_id
        ORDER BY ei.left_at DESC LIMIT 5
    ''')
    recent = db.cursor.fetchall()

    text = (
        f"📊 <b>ОПРОСЫ ПРИ ВЫХОДЕ</b>\n"
        f"{'━' * 24}\n\n"
        f"📋 Всего ответов: <b>{total}</b>\n\n"
    )

    if reasons:
        text += "<b>Причины ухода:</b>\n"
        for r in reasons:
            text += f"  {r['reason_category']}: <b>{r['cnt']}</b>\n"
        text += "\n"

    if improvements:
        text += "<b>Что улучшить:</b>\n"
        for i in improvements:
            text += f"  {i['improvement']}: <b>{i['cnt']}</b>\n"
        text += "\n"

    if returns:
        text += "<b>Вернулись бы?:</b>\n"
        for r in returns:
            text += f"  {r['would_return']}: <b>{r['cnt']}</b>\n"
        text += "\n"

    if recent:
        text += "<b>Последние 5:</b>\n"
        for r in recent:
            name = r['username'] or r['first_name'] or f"ID:{r['user_id']}"
            reason = r['reason_category'] or '—'
            date = str(r['left_at'])[:10] if r['left_at'] else '—'
            text += f"  @{name} ({date}): {reason}\n"

    if len(text) > 4000:
        text = text[:3950] + "\n\n<i>...обрезано</i>"

    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="owner_dashboard")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
