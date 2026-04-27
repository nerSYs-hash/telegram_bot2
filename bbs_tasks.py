#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фоновые задачи VIP BBS — APScheduler jobs.

Регистрируются в bot.py::setup_scheduler():
    scheduler.add_job(vip_expire_check,       'interval', minutes=5,  args=[bot, db, target_chat_id, bbs_thread_id])
    scheduler.add_job(vip_custom_bump_tick,   'interval', minutes=5,  args=[bot, db, target_chat_id, bbs_thread_id])
    scheduler.add_job(promo_chat_dispatcher,  'interval', minutes=2,  args=[bot, db, target_chat_id])
    scheduler.add_job(global_cooldown_sync,   'interval', minutes=10, args=[db])

VIP1 (BUMP) — событийный: запускается через _trigger_vip1_queue() из publishing_bbs.py,
а НЕ через таймер. Здесь не регистрируется.
"""

import json
import logging
from telegram import InputMediaPhoto

logger = logging.getLogger(__name__)

PROMO_CHAT_THREAD_ID = 1   # General topic в основном чате
PROMO_MAX_ATTEMPTS   = 5   # Макс. попыток отправки одного слота

VIP_FAMILY_LABELS = {
    'BUMP':        '🚀 Перепубликация при чужих публикациях',
    'SILENT_PIN':  '📌 Тихий закреп',
    'LOUD_PIN':    '🔔 Громкий закреп с уведомлением',
    'CUSTOM_BUMP': '⚡ Автопубликация раз в сутки',
    'BUMP_PIN':    '🎯 Автопуб + закреп',
    'PROMO_CHAT':  '📣 Промо в общий чат',
}


# ════════════════════════════════════════════════════════════════════
# Job 1 — истечение подписок (каждые 5 мин)
# ════════════════════════════════════════════════════════════════════

async def vip_expire_check(bot, db, target_chat_id, bbs_thread_id):
    """
    Ищет активные подписки с истёкшим expires_at:
    — снимает закреп (пин-семьи)
    — ставит status='expired'
    — если у профиля не осталось активных VIP → убирает VIP-эмодзи (перепубликация)
    — шлёт DM юзеру (best-effort)
    """
    from database.db_bbs_vip import get_expired_subscriptions, expire_subscription, has_active_vip

    expired = get_expired_subscriptions(db)
    if not expired:
        return

    profiles_to_update_emoji = set()

    for s in expired:
        # 1. Unpin
        msg_id = s.get('silent_pin_msg_id') or s.get('loud_pin_msg_id')
        if msg_id:
            try:
                await bot.unpin_chat_message(chat_id=target_chat_id, message_id=msg_id)
            except Exception as e:
                logger.warning(f"vip unpin failed sub={s['id']} msg={msg_id}: {e}")

        # 2. Статус
        expire_subscription(db, s['id'])

        # 3. Запомнить профиль для проверки эмодзи
        profiles_to_update_emoji.add(s['profile_id'])

        # 4. DM
        try:
            label = VIP_FAMILY_LABELS.get(s['vip_family'], s['vip_family'])
            await bot.send_message(
                chat_id=s['user_id'],
                text=(
                    f"⏰ <b>Срок VIP-услуги истёк</b>\n\n"
                    f"Услуга: {label} (<code>{s['vip_code']}</code>)\n"
                    f"Куплена: {s['purchased_at']}\n"
                    f"Истекла: {s['expires_at']}\n\n"
                    f"Хотите продлить? Откройте свою анкету → 💎 Улучшить анкету (VIP)."
                ),
                parse_mode='HTML',
            )
        except Exception as e:
            logger.info(f"vip expire DM skip uid={s['user_id']}: {e}")

    # 5. Убрать VIP-эмодзи если у профиля больше нет активных подписок
    for profile_id in profiles_to_update_emoji:
        try:
            if not has_active_vip(db, profile_id):
                await _remove_vip_emoji_for_profile(bot, db, profile_id, target_chat_id, bbs_thread_id)
        except Exception as e:
            logger.error(f"vip_expire_check emoji removal failed profile={profile_id}: {e}")

    logger.info(f"vip_expire_check: expired {len(expired)} subscription(s)")


async def _remove_vip_emoji_for_profile(bot, db, profile_id: int, target_chat_id: int, bbs_thread_id: int):
    """Перепубликует профиль без VIP-эмодзи (все подписки истекли)."""
    from handlers.BBS.database_bbs import get_profile
    from handlers.BBS.helpers_bbs import build_profile_text
    from handlers.BBS.publishing_bbs import update_profile_in_place

    row = db.cursor.execute("SELECT user_id FROM bbs_profiles WHERE id=? AND deleted_at IS NULL",
                            (profile_id,)).fetchone()
    if not row:
        return
    user_id = row[0]
    try:
        await update_profile_in_place(bot, db, user_id, target_chat_id)
        logger.info(f"VIP emoji removed for profile={profile_id}")
    except Exception as e:
        logger.warning(f"VIP emoji removal via update_in_place failed profile={profile_id}: {e}")


# ════════════════════════════════════════════════════════════════════
# Job 2 — автопубликация CUSTOM_BUMP / BUMP_PIN (каждые 5 мин)
# ════════════════════════════════════════════════════════════════════

async def vip_custom_bump_tick(bot, db, target_chat_id, bbs_thread_id):
    """
    Перепубликует CUSTOM_BUMP и BUMP_PIN у которых прошло 24ч с last_bumped_at.
    VIP1 (BUMP) здесь НЕ обрабатывается — он событийный (publishing_bbs._trigger_vip1_queue).
    """
    from handlers.BBS.publishing_bbs import republish_profile
    from database.db_bbs_vip import get_due_custom_bump_subs

    subs = get_due_custom_bump_subs(db)
    if not subs:
        return

    bumped = 0
    for s in subs:
        try:
            # BUMP_PIN: снять старый закреп перед перепубликацией
            if s['vip_family'] == 'BUMP_PIN' and s.get('silent_pin_msg_id'):
                try:
                    await bot.unpin_chat_message(
                        chat_id=target_chat_id, message_id=s['silent_pin_msg_id']
                    )
                except Exception as e:
                    logger.warning(f"bump_pin pre-unpin failed sub={s['id']}: {e}")

            # Перепубликовать (vip1_trigger=True — не запускает VIP1-цепь)
            await republish_profile(
                bot, db, s['p_user_id'], target_chat_id, bbs_thread_id,
                vip1_trigger=True,
            )

            # BUMP_PIN: закрепить новое сообщение тихо
            new_msg_id = None
            if s['vip_family'] == 'BUMP_PIN':
                row2 = db.cursor.execute(
                    "SELECT message_ids FROM bbs_profiles WHERE id=?", (s['profile_id'],)
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

            # Обновить last_bumped_at и pin_msg_id
            if new_msg_id:
                db.cursor.execute("""
                    UPDATE bbs_vip_subscriptions
                    SET last_bumped_at=datetime('now'), silent_pin_msg_id=?
                    WHERE id=?
                """, (new_msg_id, s['id']))
            else:
                db.cursor.execute(
                    "UPDATE bbs_vip_subscriptions SET last_bumped_at=datetime('now') WHERE id=?",
                    (s['id'],)
                )
            bumped += 1

        except Exception as e:
            logger.error(f"vip_custom_bump_tick failed sub={s['id']} uid={s['p_user_id']}: {e}")

    try:
        db.conn.commit()
    except Exception as e:
        logger.error(f"vip_custom_bump_tick commit error: {e}")

    if bumped:
        logger.info(f"vip_custom_bump_tick: bumped {bumped}/{len(subs)} subscription(s)")


# ════════════════════════════════════════════════════════════════════
# Job 3 — промо в основной чат VIP6 (каждые 2 мин)
# ════════════════════════════════════════════════════════════════════

async def promo_chat_dispatcher(bot, db, target_chat_id):
    """Отправляет один слот VIP6 в основной чат (General, thread_id=1). Rate-limit: 1/2 мин."""
    from database.db_bbs_vip import get_next_promo_slot, mark_promo_slot_posted, increment_promo_attempts

    slot = get_next_promo_slot(db)
    if not slot:
        return

    if (slot.get('attempts') or 0) >= PROMO_MAX_ATTEMPTS:
        db.cursor.execute("UPDATE bbs_promo_chat_queue SET posted=2 WHERE id=?", (slot['id'],))
        db.conn.commit()
        logger.warning(f"promo_chat: max attempts exceeded, dropping queue={slot['id']}")
        return

    try:
        msg_ids = await _send_profile_to_main_chat(
            bot, db,
            profile_id=slot['profile_id'],
            target_chat_id=target_chat_id,
            message_thread_id=PROMO_CHAT_THREAD_ID,
        )
        mark_promo_slot_posted(db, slot['id'], slot['subscription_id'], msg_ids)
        logger.info(f"promo_chat: posted profile={slot['profile_id']} queue={slot['id']}")

    except Exception as e:
        logger.error(f"promo_chat dispatch failed queue={slot['id']}: {e}")
        increment_promo_attempts(db, slot['id'])


# ════════════════════════════════════════════════════════════════════
# Job 4 — сброс global cooldown VIP6 при удалении анкеты (каждые 10 мин)
# ════════════════════════════════════════════════════════════════════

async def global_cooldown_sync(db):
    """
    Снимает global cooldown VIP6 (PROMO_CHAT) если анкета купившего удалена.
    VIP3 (LOUD_PIN) не трогает — его cooldown остаётся при удалении.
    """
    from database.db_bbs_vip import release_promo_cooldown_if_deleted
    released = release_promo_cooldown_if_deleted(db)
    if released:
        logger.info(f"global_cooldown_sync: released {released} PROMO_CHAT cooldown(s)")


# ════════════════════════════════════════════════════════════════════
# Вспомогательная: публикация профиля в основной чат (VIP6)
# ════════════════════════════════════════════════════════════════════

async def _send_profile_to_main_chat(bot, db, profile_id: int,
                                      target_chat_id: int, message_thread_id: int) -> list:
    """
    Публикует анкету в указанный чат без изменения bbs_profiles.message_ids.
    Возвращает list[message_id] отправленных сообщений.
    """
    from handlers.BBS.helpers_bbs import build_profile_text, write_button
    from database.db_bbs_vip import has_active_vip

    row = db.cursor.execute("SELECT * FROM bbs_profiles WHERE id=?", (profile_id,)).fetchone()
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

    # VIP-эмодзи в промо-посте тоже
    try:
        _vip_active = has_active_vip(db, profile_id)
    except Exception:
        _vip_active = False
    profile_text = build_profile_text(profile, vip_active=_vip_active)

    valid_photos = [p for p in photos if p]
    sent_ids = []

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
            chat_id=target_chat_id, message_thread_id=message_thread_id, media=media,
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
