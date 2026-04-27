#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Фоновые задачи VIP BBS — APScheduler jobs."""

import json
import logging
from telegram import InputMediaPhoto

logger = logging.getLogger(__name__)

PROMO_CHAT_THREAD_ID = 1  # General topic в главном чате (https://t.me/c/3153855971/1)
PROMO_MAX_ATTEMPTS = 5    # Максимальное количество попыток отправки промо

VIP_FAMILY_LABELS = {
    'BUMP':         '🚀 Авто-перепубликация',
    'SILENT_PIN':   '📌 Тихий закреп',
    'LOUD_PIN':     '🔔 Громкий закреп',
    'CUSTOM_BUMP':  '⚡ Custom Bump',
    'BUMP_PIN':     '🎯 Bump + закреп',
    'PROMO_CHAT':   '📣 Промо в главный чат',
}


async def vip_expire_check(bot, db, target_chat_id):
    """Истечение подписок: unpin, status='expired', DM юзеру (best-effort)."""
    try:
        rows = db.cursor.execute("""
            SELECT id, user_id, profile_id, vip_code, vip_family,
                   purchased_at, expires_at, silent_pin_msg_id, loud_pin_msg_id
            FROM bbs_vip_subscriptions
            WHERE status = 'active'
              AND expires_at IS NOT NULL
              AND expires_at <= datetime('now')
        """).fetchall()
    except Exception as e:
        logger.error(f"vip_expire_check DB read error: {e}")
        return

    for row in rows:
        s = dict(row)
        # 1. Снять закреп
        msg_id = s['silent_pin_msg_id'] or s['loud_pin_msg_id']
        if msg_id:
            try:
                await bot.unpin_chat_message(chat_id=target_chat_id, message_id=msg_id)
            except Exception as e:
                logger.warning(f"vip unpin failed sub={s['id']} msg={msg_id}: {e}")

        # 2. Пометить истёкшим
        try:
            db.cursor.execute(
                "UPDATE bbs_vip_subscriptions SET status = 'expired' WHERE id = ?",
                (s['id'],),
            )
        except Exception as e:
            logger.error(f"vip expire update failed sub={s['id']}: {e}")
            continue

        # 3. Уведомить юзера в ЛС (best-effort — не ронять job при блокировке)
        try:
            label = VIP_FAMILY_LABELS.get(s['vip_family'], s['vip_family'])
            await bot.send_message(
                chat_id=s['user_id'],
                text=(
                    f"⏰ <b>Срок VIP-услуги истёк</b>\n\n"
                    f"Услуга: {label} (<code>{s['vip_code']}</code>)\n"
                    f"Куплена: {s['purchased_at']}\n"
                    f"Истекла: {s['expires_at']}\n\n"
                    f"Хотите продлить? Откройте свою анкету → 💎 Улучшить анкету."
                ),
                parse_mode='HTML',
            )
        except Exception as e:
            logger.info(f"vip expire DM skip uid={s['user_id']}: {e}")

    try:
        db.conn.commit()
    except Exception as e:
        logger.error(f"vip_expire_check commit error: {e}")

    if rows:
        logger.info(f"vip_expire_check: expired {len(rows)} subscription(s)")


async def vip_bump_tick(bot, db, target_chat_id, bbs_thread_id):
    """Re-publish для активных BUMP/CUSTOM_BUMP/BUMP_PIN у которых пора делать bump."""
    from handlers.BBS.publishing_bbs import republish_profile

    try:
        rows = db.cursor.execute("""
            SELECT s.id, s.profile_id, s.vip_family, s.vip_code,
                   s.bump_interval_hours, s.silent_pin_msg_id,
                   p.user_id AS p_user_id
            FROM bbs_vip_subscriptions s
            JOIN bbs_profiles p ON p.id = s.profile_id
            WHERE s.status = 'active'
              AND s.bump_interval_hours IS NOT NULL
              AND s.vip_family IN ('BUMP', 'CUSTOM_BUMP', 'BUMP_PIN')
              AND p.deleted_at IS NULL
              AND (
                  s.last_bumped_at IS NULL
                  OR datetime(s.last_bumped_at, '+' || s.bump_interval_hours || ' hours') <= datetime('now')
              )
        """).fetchall()
    except Exception as e:
        logger.error(f"vip_bump_tick DB read error: {e}")
        return

    bumped = 0
    for row in rows:
        s = dict(row)
        try:
            # BUMP_PIN: снять старый pin перед republish
            if s['vip_family'] == 'BUMP_PIN' and s['silent_pin_msg_id']:
                try:
                    await bot.unpin_chat_message(
                        chat_id=target_chat_id, message_id=s['silent_pin_msg_id']
                    )
                except Exception as e:
                    logger.warning(f"bump_pin pre-unpin failed sub={s['id']}: {e}")

            # republish — удаляет старые msg и публикует новые, обновляет message_ids в БД
            await republish_profile(bot, db, s['p_user_id'], target_chat_id, bbs_thread_id)

            # BUMP_PIN: закрепить первое новое сообщение тихо
            new_msg_id = None
            if s['vip_family'] == 'BUMP_PIN':
                row2 = db.cursor.execute(
                    "SELECT message_ids FROM bbs_profiles WHERE id = ?", (s['profile_id'],)
                ).fetchone()
                if row2:
                    msg_ids = json.loads(row2['message_ids'] or '[]')
                    if msg_ids:
                        new_msg_id = msg_ids[0]
                        try:
                            await bot.pin_chat_message(
                                chat_id=target_chat_id,
                                message_id=new_msg_id,
                                disable_notification=True,
                            )
                        except Exception as e:
                            logger.warning(f"bump_pin post-pin failed sub={s['id']}: {e}")

            # Обновить last_bumped_at (и silent_pin_msg_id для BUMP_PIN)
            if new_msg_id:
                db.cursor.execute(
                    "UPDATE bbs_vip_subscriptions "
                    "SET last_bumped_at = datetime('now'), silent_pin_msg_id = ? WHERE id = ?",
                    (new_msg_id, s['id']),
                )
            else:
                db.cursor.execute(
                    "UPDATE bbs_vip_subscriptions SET last_bumped_at = datetime('now') WHERE id = ?",
                    (s['id'],),
                )
            bumped += 1

        except Exception as e:
            logger.error(f"vip_bump_tick failed sub={s['id']} uid={s['p_user_id']}: {e}")

    try:
        db.conn.commit()
    except Exception as e:
        logger.error(f"vip_bump_tick commit error: {e}")

    if bumped:
        logger.info(f"vip_bump_tick: bumped {bumped}/{len(rows)} subscription(s)")


async def promo_chat_dispatcher(bot, db, target_chat_id):
    """VIP6 — отправка промо в главный чат (General topic). Rate-limit: 1 пост/2 мин."""
    try:
        row = db.cursor.execute("""
            SELECT q.id, q.subscription_id, q.profile_id, q.user_id,
                   COALESCE(q.attempts, 0) AS attempts
            FROM bbs_promo_chat_queue q
            JOIN bbs_profiles p ON p.id = q.profile_id
            WHERE q.posted = 0
              AND q.scheduled_at <= datetime('now')
              AND p.deleted_at IS NULL
            ORDER BY q.scheduled_at ASC
            LIMIT 1
        """).fetchone()
    except Exception as e:
        logger.error(f"promo_chat_dispatcher DB read error: {e}")
        return

    if not row:
        return

    row = dict(row)

    # Пропустить если превышен лимит попыток
    if row['attempts'] >= PROMO_MAX_ATTEMPTS:
        db.cursor.execute(
            "UPDATE bbs_promo_chat_queue SET posted = 2 WHERE id = ?", (row['id'],)
        )
        db.conn.commit()
        logger.warning(f"promo_chat: max attempts exceeded, dropping queue={row['id']}")
        return

    try:
        msg_ids = await _send_profile_to_main_chat(
            bot, db,
            profile_id=row['profile_id'],
            target_chat_id=target_chat_id,
            message_thread_id=PROMO_CHAT_THREAD_ID,
        )
        db.cursor.execute(
            "UPDATE bbs_promo_chat_queue "
            "SET posted = 1, posted_at = datetime('now'), posted_msg_ids = ? WHERE id = ?",
            (json.dumps(msg_ids), row['id']),
        )
        db.cursor.execute(
            "UPDATE bbs_vip_subscriptions "
            "SET promo_chat_slots_done = promo_chat_slots_done + 1 WHERE id = ?",
            (row['subscription_id'],),
        )
        db.conn.commit()
        logger.info(f"promo_chat: posted profile={row['profile_id']} (queue={row['id']})")

    except Exception as e:
        logger.error(f"promo_chat dispatch failed queue={row['id']}: {e}")
        # Увеличиваем счётчик попыток, НЕ помечаем posted=1 — будет ретрай
        try:
            db.cursor.execute(
                "UPDATE bbs_promo_chat_queue "
                "SET attempts = COALESCE(attempts, 0) + 1 WHERE id = ?",
                (row['id'],),
            )
            db.conn.commit()
        except Exception as e2:
            logger.error(f"promo_chat attempts update failed: {e2}")


async def _send_profile_to_main_chat(bot, db, profile_id, target_chat_id, message_thread_id):
    """
    Публикует анкету в указанный чат+thread без изменения bbs_profiles.message_ids.
    Возвращает list[message_id] отправленных сообщений.
    """
    from handlers.BBS.helpers_bbs import build_profile_text, write_button

    db.cursor.execute("SELECT * FROM bbs_profiles WHERE id = ?", (profile_id,))
    row = db.cursor.fetchone()
    if not row:
        raise ValueError(f"Profile id={profile_id} not found")

    profile = dict(row)
    for field in ['photos', 'params', 'roles', 'city', 'goals']:
        if isinstance(profile.get(field), str):
            try:
                profile[field] = json.loads(profile[field])
            except Exception:
                profile[field] = [] if field != 'params' else {}

    photos = profile.get('photos') or []
    user_id = profile['user_id']
    profile_text = build_profile_text(profile)
    sent_ids = []

    valid_photos = [p for p in photos if p]

    if len(valid_photos) == 1:
        msg = await bot.send_photo(
            chat_id=target_chat_id,
            message_thread_id=message_thread_id,
            photo=valid_photos[0],
            caption=profile_text,
            parse_mode='HTML',
            reply_markup=write_button(user_id, bot.username),
        )
        sent_ids.append(msg.message_id)

    elif len(valid_photos) > 1:
        media = [InputMediaPhoto(media=valid_photos[0], caption=profile_text, parse_mode='HTML')]
        media += [InputMediaPhoto(media=fid) for fid in valid_photos[1:]]
        messages = await bot.send_media_group(
            chat_id=target_chat_id,
            message_thread_id=message_thread_id,
            media=media,
        )
        sent_ids = [m.message_id for m in messages]
        try:
            btn_msg = await bot.send_message(
                chat_id=target_chat_id,
                message_thread_id=message_thread_id,
                text=" 👆<b>Понравился?</b>",
                parse_mode='HTML',
                reply_markup=write_button(user_id, bot.username),
            )
            sent_ids.append(btn_msg.message_id)
        except Exception as e:
            logger.warning(f"promo button send failed profile={profile_id}: {e}")

    else:
        msg = await bot.send_message(
            chat_id=target_chat_id,
            message_thread_id=message_thread_id,
            text=profile_text,
            parse_mode='HTML',
            reply_markup=write_button(user_id, bot.username),
        )
        sent_ids.append(msg.message_id)

    return sent_ids
