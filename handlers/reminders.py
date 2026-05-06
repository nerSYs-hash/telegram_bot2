#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Фоновые задачи и напоминания.

Путь: handlers/reminders.py

Задачи:
  - Проверка неактивных пользователей (60 дней) → лог в журнал
  - Автоочистка истёкших заморозок
  - Еженедельный отчёт владельцу

Регистрация в bot.py:
    from handlers.reminders import check_inactive_users, send_weekly_report
    self.scheduler.add_job(...)
"""

import logging
import json
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  НЕАКТИВНЫЕ ПОЛЬЗОВАТЕЛИ (60 дней)
# ═══════════════════════════════════════════════════════════════

async def check_inactive_users(bot, db, target_chat_id: int, admin_id: int) -> None:
    """
    Проверяет пользователей, не активных более 60 дней.
    Логирует в журнал, уведомляет владельца (с пагинацией).
    Вызывается из scheduler каждые 24 часа.
    """
    try:
        # Пользователи 60+ дней без активности, ещё не уведомлённые за последние 30 дней
        db.cursor.execute('''
            SELECT user_id, username, first_name, last_active
            FROM users
            WHERE is_left = 0
              AND is_admin = 0
              AND is_owner = 0
              AND last_active < datetime('now', '-60 days')
              AND user_id NOT IN (
                  SELECT user_id FROM journal_messages
                  WHERE event_type = 'inactivity'
                    AND created_at >= datetime('now', '-30 days')
              )
            ORDER BY last_active ASC
        ''')
        inactive = db.cursor.fetchall()

        if not inactive:
            return

        # Получаем инфо о чате один раз
        chat_title = None
        try:
            chat_obj = await bot.get_chat(target_chat_id)
            chat_title = chat_obj.title
        except Exception:
            pass

        # Журнал
        try:
            from handlers.journal_handlers import log_activity
            for u in inactive:
                await log_activity(
                    bot, db, u['user_id'],
                    chat_id=target_chat_id,
                    chat_title=chat_title,
                    days_inactive=60,
                )
        except Exception as e:
            logger.error(f"Journal inactive log error: {e}")

        # Сохраняем список в settings для пагинации
        inactive_data = [
            {'user_id': u['user_id'], 'username': u['username'], 'first_name': u['first_name'], 'last_active': u['last_active']}
            for u in inactive
        ]
        db.set_setting(f'inactive_users_list_{admin_id}', json.dumps(inactive_data))

        # Уведомление владельцу (первая страница + кнопка)
        try:
            await _send_inactive_page(bot, db, admin_id, inactive_data, page=0)
        except Exception as e:
            logger.error(f"Inactive users notification error: {e}")

        logger.info(f"INACTIVE CHECK: found {len(inactive)} users")

    except Exception as e:
        logger.error(f"check_inactive_users error: {e}")


# ═══════════════════════════════════════════════════════════════
#  АВТООЧИСТКА ИСТЁКШИХ ЗАМОРОЗОК
# ═══════════════════════════════════════════════════════════════

async def cleanup_expired_freezes(db) -> None:
    """
    Обнуляет frozen_balance у пользователей с истёкшей заморозкой.
    Вызывается из scheduler каждые 6 часов (уже зарегистрирован в bot.py).
    """
    try:
        db.cursor.execute('''
            UPDATE users
            SET frozen_balance = 0, freeze_until = NULL
            WHERE frozen_balance > 0
              AND freeze_until IS NOT NULL
              AND freeze_until < datetime('now')
        ''')
        affected = db.cursor.rowcount
        db.conn.commit()

        if affected > 0:
            logger.info(f"FREEZE CLEANUP: expired {affected} freezes")

    except Exception as e:
        logger.error(f"cleanup_expired_freezes error: {e}")


# ═══════════════════════════════════════════════════════════════
#  ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ ВЛАДЕЛЬЦУ
# ═══════════════════════════════════════════════════════════════

async def send_weekly_report(bot, db, admin_id: int) -> None:
    """
    Еженедельная сводка: новые/ушедшие, активность, триггеры.
    Вызывается по воскресеньям в 20:00 МСК.
    """
    try:
        # Пользователи за неделю
        db.cursor.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE joined_at >= datetime('now', '-7 days')"
        )
        new_users = db.cursor.fetchone()['cnt']

        db.cursor.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE is_left = 1 AND last_active >= datetime('now', '-7 days')"
        )
        left_users = db.cursor.fetchone()['cnt']

        # Активных за неделю
        db.cursor.execute(
            "SELECT COUNT(DISTINCT user_id) as cnt FROM user_stats WHERE date >= date('now', '-7 days')"
        )
        active_users = db.cursor.fetchone()['cnt']

        # Триггеры за неделю
        trigger_count = 0
        try:
            db.cursor.execute(
                "SELECT COUNT(*) as cnt FROM trigger_violations WHERE last_violation_at >= datetime('now', '-7 days')"
            )
            trigger_count = db.cursor.fetchone()['cnt']
        except Exception:
            pass

        # Опросы за неделю
        survey_count = 0
        try:
            db.cursor.execute(
                "SELECT COUNT(*) as cnt FROM exit_interviews WHERE left_at >= datetime('now', '-7 days')"
            )
            survey_count = db.cursor.fetchone()['cnt']
        except Exception:
            pass

        text = (
            f"📊 <b>ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ</b>\n\n"
            f"👥 Новых пользователей: <b>{new_users}</b>\n"
            f"🚪 Покинули чат: <b>{left_users}</b>\n"
            f"💬 Активных за неделю: <b>{active_users}</b>\n"
            f"⚡ Срабатываний триггеров: <b>{trigger_count}</b>\n"
            f"📋 Ответов на exit-опрос: <b>{survey_count}</b>\n"
        )

        await bot.send_message(chat_id=admin_id, text=text, parse_mode='HTML')
        logger.info("Weekly report sent")

    except Exception as e:
        logger.error(f"send_weekly_report error: {e}")


# ═══════════════════════════════════════════════════════════════
#  ПАГИНАЦИЯ НЕАКТИВНЫХ ПОЛЬЗОВАТЕЛЕЙ
# ═══════════════════════════════════════════════════════════════

async def _send_inactive_page(bot, db, admin_id: int, users_list: list, page: int = 0) -> None:
    """Отправляет страницу неактивных пользователей с кнопками пагинации."""
    per_page = 10
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users_list[start_idx:end_idx]

    if not page_users:
        logger.warning(f"No users for page {page}")
        return

    # Формируем текст
    lines = []
    for u in page_users:
        name = u['username'] or u['first_name'] or f"ID:{u['user_id']}"
        last = str(u['last_active'])[:10] if u['last_active'] else '—'
        lines.append(f"  💤 @{name} — {last}")

    total = len(users_list)
    current_count = min((page + 1) * per_page, total)
    text = (
        f"📋 <b>Неактивные пользователи</b>\n"
        f"(более 60 дней без сообщений)\n\n"
        + "\n".join(lines) + "\n\n"
        + f"<i>{current_count} из {total}</i>"
    )

    # Клавиатура с кнопками
    keyboard = []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"inactive_page:{page-1}:{admin_id}"))
    if end_idx < total:
        row.append(InlineKeyboardButton("Далее ➡️", callback_data=f"inactive_page:{page+1}:{admin_id}"))
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    await bot.send_message(
        chat_id=admin_id,
        text=text,
        parse_mode='HTML',
        reply_markup=reply_markup,
    )


async def handle_inactive_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE, db) -> None:
    """Обработчик пагинации списка неактивных пользователей."""
    query = update.callback_query
    if not query.data.startswith('inactive_page:'):
        return

    try:
        parts = query.data.split(':')
        page = int(parts[1])
        admin_id = int(parts[2])

        # Проверяем права
        if query.from_user.id != admin_id:
            await query.answer("Это не ваш отчёт", show_alert=True)
            return

        # Получаем сохранённый список
        inactive_json = db.get_setting(f'inactive_users_list_{admin_id}')
        if not inactive_json:
            await query.answer("Список истёк. Попросите отчёт снова.", show_alert=True)
            return

        inactive_list = json.loads(inactive_json)
        
        # Отправляем страницу
        await _send_inactive_page(context.bot, db, admin_id, inactive_list, page)
        await query.answer()
        # Удаляем старое сообщение
        await query.delete_message()

    except Exception as e:
        logger.error(f"handle_inactive_pagination error: {e}")
        await query.answer("Ошибка", show_alert=True)

