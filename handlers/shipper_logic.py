#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Логика рулетки пар (шиппер) + скрытый резонанс для майнинга."""

import html
import logging
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

SHIPPER_JOB_NAME = "shipper_roulette_job"

TARGET_MODES = {
    "inactive_long": "давно не писали",
    "active_48": "активные 48ч",
    "active_72": "активные 72ч",
    "all_random": "полный рандом",
}


def _safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _format_user_link(row):
    user_id = row["user_id"]
    first_name = row["first_name"] or "Участник"
    safe_name = html.escape(first_name)
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


def _extract_mention_targets(message):
    targets = set()
    try:
        entities = (message.entities or []) + (message.caption_entities or [])
        for ent in entities:
            if ent.type == "text_mention" and ent.user:
                targets.add(ent.user.id)
            elif ent.type == "text_link" and ent.url and "tg://user?id=" in ent.url:
                try:
                    targets.add(int(ent.url.split("tg://user?id=", 1)[1]))
                except Exception:
                    pass
    except Exception:
        pass
    return targets


def _select_users_sql(mode):
    base = """
        SELECT user_id, first_name, username
        FROM users
        WHERE is_left = 0
          AND LOWER(COALESCE(username, '')) NOT LIKE '%bot%'
          AND LOWER(COALESCE(first_name, '')) NOT LIKE '%bot%'
    """
    if mode == "inactive_long":
        base += " AND last_active <= datetime('now', '-72 hours') "
    elif mode == "active_48":
        base += " AND last_active >= datetime('now', '-48 hours') "
    elif mode == "active_72":
        base += " AND last_active >= datetime('now', '-72 hours') "
    elif mode == "all_random":
        pass
    else:
        base += " AND last_active >= datetime('now', '-48 hours') "

    base += " ORDER BY RANDOM() LIMIT 2 "
    return base


async def schedule_next_shipper_run(context, db, target_chat_id):
    """Планирует следующий запуск шиппера через случайный интервал."""
    try:
        if not context or not getattr(context, "job_queue", None):
            logger.warning("Shipper: job_queue не инициализирован, планирование пропущено")
            return

        enabled = db.get_setting("shipper_enabled", "0") == "1"
        if not enabled:
            return

        min_hours = _safe_int(db.get_setting("shipper_min_hours", "2"), 2)
        max_hours = _safe_int(db.get_setting("shipper_max_hours", "5"), 5)

        if min_hours < 1:
            min_hours = 1
        if max_hours < min_hours:
            max_hours = min_hours

        random_hours = random.randint(min_hours, max_hours)
        delay = random_hours * 3600

        for job in context.job_queue.get_jobs_by_name(SHIPPER_JOB_NAME):
            job.schedule_removal()

        context.job_queue.run_once(
            run_shipper_roulette,
            when=delay,
            data={"target_chat_id": target_chat_id},
            name=SHIPPER_JOB_NAME,
        )
        logger.info(f"Shipper: следующий запуск через {random_hours} ч.")
    except Exception as e:
        logger.error(f"schedule_next_shipper_run error: {e}")


async def bootstrap_shipper(context, db, target_chat_id):
    """Стартовый запуск планировщика при старте бота."""
    try:
        await schedule_next_shipper_run(context, db, target_chat_id)
    except Exception as e:
        logger.error(f"bootstrap_shipper error: {e}")


def activate_shipper_resonance_for_pair(db, match_row, trigger_type):
    """Активирует скрытое комбо «Мэтч дня»: x2 бафф майнинга на 1 час для пары."""
    try:
        match_id = match_row["id"]
        user1_id = match_row["user1_id"]
        user2_id = match_row["user2_id"]
        expires_at = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

        db.mark_shipper_match_triggered(match_id)

        for uid in (user1_id, user2_id):
            db.cursor.execute(
                '''
                SELECT mining_buff_multiplier, mining_buff_expires_at
                FROM users WHERE user_id = ?
                ''',
                (uid,),
            )
            row = db.cursor.fetchone()
            current_mult = float(row["mining_buff_multiplier"] or 1.0) if row else 1.0
            current_exp = (row["mining_buff_expires_at"] if row else None) or ""

            new_mult = max(current_mult, 2.0)
            new_exp = expires_at
            if current_exp and current_exp > expires_at:
                new_exp = current_exp

            db.cursor.execute(
                '''
                UPDATE users
                SET mining_buff_multiplier = ?, mining_buff_expires_at = ?
                WHERE user_id = ?
                ''',
                (new_mult, new_exp, uid),
            )
            db.add_shipper_resonance_stat(uid, match_id, trigger_type, new_exp, multiplier=2.0)

        db.conn.commit()
        logger.info(f"Shipper resonance activated for users {user1_id} & {user2_id} by {trigger_type}")
        return True
    except Exception as e:
        logger.error(f"activate_shipper_resonance_for_pair error: {e}")
        return False


def try_activate_shipper_resonance(message, db):
    """Проверяет условия резонанса по входящему сообщению и активирует x2 бафф."""
    try:
        if not message or not message.chat or not message.from_user:
            return False

        chat_id = message.chat.id
        author_id = message.from_user.id
        match_row = db.get_active_shipper_match_for_user(chat_id, author_id)
        if not match_row:
            return False

        partner_id = match_row["user2_id"] if match_row["user1_id"] == author_id else match_row["user1_id"]

        # 1) Reply на сообщение шиппера
        if message.reply_to_message and match_row["message_id"]:
            if message.reply_to_message.message_id == match_row["message_id"]:
                return activate_shipper_resonance_for_pair(db, match_row, "reply")

        # 2) Тег партнера
        targets = _extract_mention_targets(message)
        if partner_id in targets:
            return activate_shipper_resonance_for_pair(db, match_row, "mention")

        # 3) Тег через @username
        text = (message.text or message.caption or "").lower()
        if text:
            partner = db.get_user(partner_id)
            partner_username = (partner["username"] or "").lower() if partner else ""
            if partner_username and f"@{partner_username}" in text:
                return activate_shipper_resonance_for_pair(db, match_row, "mention")

        return False
    except Exception as e:
        logger.error(f"try_activate_shipper_resonance error: {e}")
        return False


async def run_shipper_roulette(context, db=None, target_chat_id=None):
    """
    Рулетка пар:
    1) Проверка включения
    2) Выбор 2 разных пользователей по режиму таргета
    3) Выбор случайной фразы
    4) Подстановка user1/user2 ссылками
    5) Отправка в целевой чат
    6) Самопланирование следующего запуска через случайный интервал
    """
    try:
        if db is None:
            db = context.application.bot_data.get("db") if getattr(context, "application", None) else None
        if target_chat_id is None:
            target_chat_id = context.job.data.get("target_chat_id") if getattr(context, "job", None) and context.job.data else None

        if not db or not target_chat_id:
            logger.warning("Shipper: db или target_chat_id не переданы")
            return

        enabled = db.get_setting("shipper_enabled", "0") == "1"
        if not enabled:
            return

        mode = db.get_setting("shipper_target_mode", "active_48")
        sql = _select_users_sql(mode)
        db.cursor.execute(sql)
        users = db.cursor.fetchall()

        if not users or len(users) < 2:
            logger.info(f"Shipper: недостаточно пользователей для режима {mode}")
            return

        user1, user2 = users[0], users[1]
        if user1["user_id"] == user2["user_id"]:
            logger.info("Shipper: выпали одинаковые пользователи")
            return

        phrase_row = db.get_random_shipper_phrase()
        if not phrase_row:
            db.seed_shipper_phrases_if_empty()
            phrase_row = db.get_random_shipper_phrase()
        if not phrase_row:
            logger.warning("Shipper: нет фраз в базе")
            return

        phrase = phrase_row["text"]
        msg = phrase.replace("{user1}", _format_user_link(user1)).replace("{user2}", _format_user_link(user2))

        sent = await context.bot.send_message(
            chat_id=target_chat_id,
            text=msg,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        try:
            expires_at = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            db.create_shipper_match(
                user1_id=user1["user_id"],
                user2_id=user2["user_id"],
                chat_id=target_chat_id,
                message_id=sent.message_id,
                expires_at=expires_at,
            )
        except Exception as e:
            logger.error(f"Shipper: failed to create match tracking: {e}")

        # GC
        try:
            from bot_core.workspace_context import resolve_workspace_for_chat
            from services.garbage_collector import schedule_deletion
            ws_id = resolve_workspace_for_chat(db.conn, target_chat_id) or 1
            schedule_deletion(db, ws_id, target_chat_id, sent.message_id, 60, 'shipper')
        except Exception as e:
            logger.error(f"Shipper GC error: {e}")
    except Exception as e:
        logger.error(f"run_shipper_roulette error: {e}")
    finally:
        try:
            if db and db.get_setting("shipper_enabled", "0") == "1":
                await schedule_next_shipper_run(context, db, target_chat_id)
        except Exception as e:
            logger.error(f"run_shipper_roulette schedule next error: {e}")
