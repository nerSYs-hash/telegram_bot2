#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VIP BBS — пользовательский интерфейс: витрина, подтверждение, покупка."""

import json
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

FAMILY_ORDER = ['BUMP', 'SILENT_PIN', 'LOUD_PIN', 'CUSTOM_BUMP', 'BUMP_PIN', 'PROMO_CHAT', 'INSTANT_BUMP']

FAMILY_META = {
    'BUMP':         ('🚀', 'BUMP', 'Авто-перепубликация каждые 4ч'),
    'SILENT_PIN':   ('📌', 'Тихий закреп', 'Анкета закреплена без уведомлений'),
    'LOUD_PIN':     ('🔔', 'Громкий закреп', 'Закреп с уведомлением (1×/неделю)'),
    'CUSTOM_BUMP':  ('⚡', 'Custom BUMP', 'Авто-перепубликация с кастомной частотой'),
    'BUMP_PIN':     ('🎯', 'BUMP + PIN', 'Авто-перепубликация + тихий закреп'),
    'PROMO_CHAT':   ('📣', 'Промо в чат', '3 публикации в главный чат за сутки (1×/сутки)'),
    'INSTANT_BUMP': ('🚀', 'Мгновенный подъём', 'Сброс таймера — поднять анкету прямо сейчас'),
}


def _get_rate(db) -> float:
    try:
        rate = float(db.get_setting('pulse_rate', '1.42') or '1.42')
    except (ValueError, TypeError):
        rate = 1.42
    return rate if rate > 0 else 1.42


def _get_profile(db, user_id):
    """Получить анкету пользователя. Возвращает dict или None."""
    from handlers.BBS.database_bbs import get_profile
    return get_profile(db, user_id)


async def show_vip_storefront(query, user, context, db, target_chat_id, bbs_thread_id):
    """Корневой экран витрины VIP BBS с ценами от минимальной по каждой семье."""
    rate = _get_rate(db)
    all_settings = db.get_vip_settings()
    if not all_settings:
        await query.answer("VIP услуги временно недоступны.", show_alert=True)
        return

    # min цена по каждой семье
    by_family = {}
    for row in all_settings:
        if not row['is_enabled']:
            continue
        fam = row['vip_family']
        if fam not in by_family or row['price_rub'] < by_family[fam]['price_rub']:
            by_family[fam] = row

    lines = ["💎 <b>VIP-услуги для анкеты BBS</b>\n\nВыберите тип услуги:\n"]
    keyboard = []
    for fam in FAMILY_ORDER:
        row = by_family.get(fam)
        if not row:
            continue
        icon, name, desc = FAMILY_META.get(fam, ('•', fam, ''))
        min_pulses = round(row['price_rub'] / rate, 2)
        label = f"{icon} {name} — от {min_pulses:.0f} 💎"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"bbs_vip_family_{fam}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_dating")])

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_vip_family(query, data, user, context, db):
    """Детальный экран семьи услуг с вариантами и статусом активных подписок."""
    family = data.removeprefix("bbs_vip_family_")
    rate = _get_rate(db)

    items = db.get_vip_settings(family=family)
    if not items:
        await query.answer("Семья услуг не найдена.", show_alert=True)
        return

    profile = _get_profile(db, user.id)
    has_profile = bool(profile and profile.get('message_ids') and not profile.get('deleted_at'))

    icon, name, desc = FAMILY_META.get(family, ('•', family, ''))
    lines = [f"{icon} <b>{name}</b>\n{desc}\n"]

    if not has_profile:
        lines.append("⚠️ <i>Опубликуйте анкету для покупки VIP-услуг</i>")

    keyboard = []

    # Активная подписка этой семьи
    active = None
    if has_profile:
        active = db.get_active_by_family(profile['id'], family)

    for item in items:
        if not item['is_enabled']:
            continue
        pulse_price = round(item['price_rub'] / rate, 2)
        if item['duration_hours']:
            dur = f"{item['duration_hours']} ч"
        else:
            dur = "разовая"
        if item['bump_interval_hours']:
            dur += f", bump каждые {item['bump_interval_hours']}ч"

        lines.append(f"• {dur} — <b>{pulse_price:.0f} 💎</b> ({item['price_rub']:.0f} ₽)")

        if not has_profile:
            btn = InlineKeyboardButton(
                f"{item['vip_code']} — {pulse_price:.0f} 💎 (нет анкеты)",
                callback_data="bbs_vip_no_profile",
            )
        elif active:
            exp = active['expires_at'][:16] if active['expires_at'] else 'активна'
            btn = InlineKeyboardButton(
                f"✅ Активна до {exp}",
                callback_data="bbs_vip_already_active",
            )
        else:
            btn = InlineKeyboardButton(
                f"🛒 {item['vip_code']} — {pulse_price:.0f} 💎",
                callback_data=f"bbs_vip_confirm_{item['vip_code']}",
            )
        keyboard.append([btn])

    keyboard.append([InlineKeyboardButton("🔙 Назад к услугам", callback_data="bbs_vip_storefront")])

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_vip_confirmation(query, data, user, context, db):
    """Экран подтверждения покупки."""
    vip_code = data.removeprefix("bbs_vip_confirm_")
    setting = db.get_vip_settings(code=vip_code)
    if not setting or not setting['is_enabled']:
        await query.answer("Услуга недоступна.", show_alert=True)
        return

    # Проверить анкету
    profile = _get_profile(db, user.id)
    if not profile or not profile.get('message_ids') or profile.get('deleted_at'):
        await query.answer("⛔ Опубликуйте анкету сначала.", show_alert=True)
        return

    # Проверить cooldown
    if setting['cooldown_hours']:
        ok, retry_at = db.check_purchase_cooldown(user.id, setting['vip_family'])
        if not ok:
            retry_str = retry_at[:16] if retry_at else '?'
            await query.answer(f"Доступно после: {retry_str}", show_alert=True)
            return

    # Проверить конфликт активной подписки (кроме INSTANT_BUMP)
    if setting['vip_family'] != 'INSTANT_BUMP':
        existing = db.get_active_by_family(profile['id'], setting['vip_family'])
        if existing:
            exp = existing['expires_at'][:16] if existing['expires_at'] else '?'
            await query.answer(f"Уже активна до {exp}", show_alert=True)
            return

    rate = _get_rate(db)
    price_pulses = round(setting['price_rub'] / rate, 2)
    user_db = db.get_user(user.id)
    balance = float(user_db['balance']) if user_db else 0.0
    after_balance = balance - price_pulses

    if setting['duration_hours']:
        dur_str = f"{setting['duration_hours']} ч"
    else:
        dur_str = "разовая"
    if setting['bump_interval_hours']:
        dur_str += f", bump каждые {setting['bump_interval_hours']}ч"

    icon = FAMILY_META.get(setting['vip_family'], ('💎',))[0]

    text = (
        f"✅ <b>Подтверждение покупки</b>\n\n"
        f"{icon} <b>{setting['title']}</b>\n"
        f"Цена: <b>{price_pulses:.2f} 💎</b> ({setting['price_rub']:.2f} ₽ по курсу {rate:.2f})\n"
        f"Длительность: {dur_str}\n\n"
        f"Ваш баланс: <b>{balance:.2f} 💎</b>\n"
        f"После покупки: <b>{after_balance:.2f} 💎</b>"
    )

    if after_balance < 0:
        need = abs(after_balance)
        text += f"\n\n❌ <b>Не хватает {need:.2f} 💎</b>"
        keyboard = [
            [InlineKeyboardButton("💳 Пополнить баланс", callback_data="bbs_vip_topup")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"bbs_vip_family_{setting['vip_family']}")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"bbs_vip_buy_{vip_code}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"bbs_vip_family_{setting['vip_family']}")],
        ]

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def process_vip_purchase(query, data, user, context, db, target_chat_id, bbs_thread_id):
    """Атомарная покупка VIP услуги."""
    vip_code = data.removeprefix("bbs_vip_buy_")
    setting = db.get_vip_settings(code=vip_code)
    if not setting or not setting['is_enabled']:
        await query.answer("Услуга недоступна.", show_alert=True)
        return

    profile = _get_profile(db, user.id)
    if not profile or not profile.get('message_ids') or profile.get('deleted_at'):
        await query.answer("⛔ Опубликуйте анкету сначала.", show_alert=True)
        return

    if setting['cooldown_hours']:
        ok, retry_at = db.check_purchase_cooldown(user.id, setting['vip_family'])
        if not ok:
            retry_str = retry_at[:16] if retry_at else '?'
            await query.answer(f"Доступно после: {retry_str}", show_alert=True)
            return

    if setting['vip_family'] != 'INSTANT_BUMP':
        existing = db.get_active_by_family(profile['id'], setting['vip_family'])
        if existing:
            exp = existing['expires_at'][:16] if existing['expires_at'] else '?'
            await query.answer(f"Уже активна до {exp}", show_alert=True)
            return

    rate = _get_rate(db)
    price_pulses = round(setting['price_rub'] / rate, 2)

    # Проверить баланс до транзакции
    user_db = db.get_user(user.id)
    if not user_db or float(user_db['balance']) < price_pulses:
        await _show_insufficient_balance(query, price_pulses, float(user_db['balance']) if user_db else 0.0,
                                         setting['vip_family'])
        return

    # ═══ АТОМАРНАЯ ТРАНЗАКЦИЯ ═══
    sub_id = None
    expires_at = None
    try:
        db.cursor.execute("BEGIN IMMEDIATE")
        # Повторно читаем баланс под локом
        db.cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user.id,))
        bal_row = db.cursor.fetchone()
        if not bal_row or float(bal_row['balance']) < price_pulses:
            db.conn.rollback()
            await query.answer("Баланс изменился, попробуйте ещё раз.", show_alert=True)
            return

        # Списать с юзера
        db.cursor.execute(
            "UPDATE users SET balance = ROUND(balance - ?, 2), last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (price_pulses, user.id),
        )
        # Вернуть в банк (замкнутый контур экономики)
        db.cursor.execute(
            "UPDATE settings SET value = CAST(ROUND(CAST(value AS REAL) + ?, 2) AS TEXT), "
            "updated_at = CURRENT_TIMESTAMP WHERE key = 'bank_balance'",
            (price_pulses,),
        )

        # Вычислить expires_at
        if setting['duration_hours']:
            db.cursor.execute(
                "SELECT datetime('now', '+' || ? || ' hours') AS exp",
                (setting['duration_hours'],),
            )
            expires_at = db.cursor.fetchone()['exp']

        # Для INSTANT_BUMP — сразу expired (разовая, не активная подписка)
        status = 'expired' if setting['vip_family'] == 'INSTANT_BUMP' else 'active'

        db.cursor.execute(
            """
            INSERT INTO bbs_vip_subscriptions
                (profile_id, user_id, vip_code, vip_family,
                 expires_at, status, bump_interval_hours,
                 price_rub_paid, price_pulses_paid, pulse_rate_at_purchase)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile['id'], user.id, vip_code, setting['vip_family'],
                expires_at, status, setting['bump_interval_hours'],
                setting['price_rub'], price_pulses, rate,
            ),
        )
        sub_id = db.cursor.lastrowid
        db.conn.commit()
    except Exception as e:
        try:
            db.conn.rollback()
        except Exception:
            pass
        logger.exception(f"vip purchase failed uid={user.id} code={vip_code}: {e}")
        await query.answer("❌ Ошибка покупки. Деньги не списаны.", show_alert=True)
        return

    # ═══ ПОБОЧНЫЕ ЭФФЕКТЫ (после коммита) ═══
    family = setting['vip_family']
    try:
        if family == 'INSTANT_BUMP':
            from handlers.BBS.publishing_bbs import republish_profile
            await republish_profile(context.bot, db, user.id, target_chat_id, bbs_thread_id)
            db.cursor.execute(
                "UPDATE bbs_vip_subscriptions SET last_bumped_at = datetime('now') WHERE id = ?",
                (sub_id,),
            )
            db.conn.commit()

        elif family in ('SILENT_PIN', 'LOUD_PIN', 'BUMP_PIN'):
            msg_ids = json.loads(profile.get('message_ids') or '[]')
            if msg_ids:
                disable_notif = (family != 'LOUD_PIN')
                await context.bot.pin_chat_message(
                    chat_id=target_chat_id,
                    message_id=msg_ids[0],
                    disable_notification=disable_notif,
                )
                col = 'loud_pin_msg_id' if family == 'LOUD_PIN' else 'silent_pin_msg_id'
                db.cursor.execute(
                    f"UPDATE bbs_vip_subscriptions SET {col} = ? WHERE id = ?",
                    (msg_ids[0], sub_id),
                )
                db.conn.commit()

        elif family == 'PROMO_CHAT':
            for h in (0, 8, 16):
                db.cursor.execute(
                    """
                    INSERT INTO bbs_promo_chat_queue
                        (subscription_id, profile_id, user_id, scheduled_at)
                    VALUES (?, ?, ?, datetime('now', '+' || ? || ' hours'))
                    """,
                    (sub_id, profile['id'], user.id, h),
                )
            db.cursor.execute(
                "UPDATE bbs_vip_subscriptions SET promo_chat_slots_total = 3 WHERE id = ?",
                (sub_id,),
            )
            db.conn.commit()
        # BUMP/CUSTOM_BUMP/BUMP_PIN BUMP-часть — job подхватит по bump_interval_hours

    except Exception as e:
        logger.exception(f"vip side-effect failed sub={sub_id} family={family}: {e}")

    # ═══ ОТВЕТ ЮЗЕРУ ═══
    expires_str = expires_at[:16] if expires_at else "разовая"
    icon = FAMILY_META.get(family, ('💎',))[0]
    text = (
        f"✅ <b>Покупка успешна!</b>\n\n"
        f"{icon} <b>{setting['title']}</b>\n"
        f"Списано: <b>{price_pulses:.2f} 💎</b>\n"
        f"Действует до: <b>{expires_str}</b>"
    )
    keyboard = [[InlineKeyboardButton("🔙 К услугам", callback_data="bbs_vip_storefront")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_insufficient_balance(query, price_pulses: float, balance: float, family: str):
    """Показать экран недостаточного баланса."""
    need = price_pulses - balance
    text = (
        f"❌ <b>Недостаточно Пульсов</b>\n\n"
        f"Нужно: <b>{price_pulses:.2f} 💎</b>\n"
        f"На балансе: <b>{balance:.2f} 💎</b>\n"
        f"Не хватает: <b>{need:.2f} 💎</b>\n\n"
        f"Для пополнения баланса напишите владельцу — он переведёт Пульсы за ручной платёж."
    )
    keyboard = [
        [InlineKeyboardButton("💳 Пополнить баланс", callback_data="bbs_vip_topup")],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"bbs_vip_family_{family}")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def show_topup_stub(query, user):
    """Заглушка 'Пополнить баланс' — контакт владельца."""
    text = (
        "💳 <b>Пополнение баланса</b>\n\n"
        "Для пополнения баланса напишите владельцу <b>@LockUp11</b> — "
        "он переведёт вам Пульсы за ручной платёж.\n\n"
        "<i>Telegram Stars сознательно не подключены.</i>"
    )
    keyboard = [
        [InlineKeyboardButton("💬 Написать @LockUp11", url="https://t.me/LockUp11")],
        [InlineKeyboardButton("🔙 Назад к услугам", callback_data="bbs_vip_storefront")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def process_instant_bump(query, user, context, db, target_chat_id, bbs_thread_id):
    """Быстрый INSTANT_BUMP — показывает экран подтверждения."""
    await show_vip_confirmation(query, "bbs_vip_confirm_INSTANT_BUMP", user, context, db)
