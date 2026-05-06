#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIP BBS — пользовательский интерфейс: витрина, подтверждение, покупка.

Редакция: 2026-04-28 (новые правила VIP1-VIP6, без INSTANT_BUMP).
"""

import json
import logging
from datetime import datetime, timezone, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

_MSK = timezone(timedelta(hours=3))

# ─── Метаданные семей ─────────────────────────────────────────────────────────
FAMILY_ORDER = ['BUMP', 'SILENT_PIN', 'LOUD_PIN', 'CUSTOM_BUMP', 'BUMP_PIN', 'PROMO_CHAT']

FAMILY_META = {
    'BUMP':        ('🚀', 'VIP1 — Перепубликация', 'При каждой чужой публикации — ваша анкета поднимается наверх'),
    'SILENT_PIN':  ('📌', 'VIP2 — Тихий закреп',   'Анкета закреплена в шапке без уведомлений, 24 ч'),
    'LOUD_PIN':    ('🔔', 'VIP3 — Громкий закреп',  'Закреп + уведомление всем участникам (1 раз в 7 дней)'),
    'CUSTOM_BUMP': ('⚡', 'VIP4 — Автопубликация',   'Перепубликация раз в сутки на выбранный срок'),
    'BUMP_PIN':    ('🎯', 'VIP5 — Автопуб + закреп', 'Перепубликация раз в сутки + тихий закреп'),
    'PROMO_CHAT':  ('📣', 'VIP6 — Промо в чат',      '3 публикации в общий чат: 10:00 / 15:00 / 21:00 МСК'),
}

GLOBAL_COOLDOWN_FAMILIES = frozenset({'LOUD_PIN', 'PROMO_CHAT'})


def _get_rate(db) -> float:
    try:
        rate = float(db.get_setting('pulse_rate', '1.42') or '1.42')
    except (ValueError, TypeError):
        rate = 1.42
    return rate if rate > 0 else 1.42


def _fmt_pulses(rub: float, rate: float) -> str:
    return f"{round(rub / rate, 0):.0f}"


def _fmt_countdown(locked_until_iso: str) -> str:
    """Форматирует «через ДД дн ЧЧ:ММ» до конца cooldown."""
    try:
        # locked_until_iso — МСК без tzinfo
        lu = datetime.fromisoformat(locked_until_iso).replace(tzinfo=_MSK)
        now = datetime.now(_MSK)
        diff = lu - now
        if diff.total_seconds() <= 0:
            return ''
        total_s = int(diff.total_seconds())
        days, rem = divmod(total_s, 86400)
        hh, rem = divmod(rem, 3600)
        mm = rem // 60
        if days:
            return f"через {days} дн {hh:02d}:{mm:02d}"
        return f"через {hh:02d}:{mm:02d}"
    except Exception:
        return '?'


def _get_profile(db, user_id):
    from handlers.BBS.database_bbs import get_profile
    return get_profile(db, user_id)


# ════════════════════════════════════════════════════════════════════
# Витрина (корневой экран)
# ════════════════════════════════════════════════════════════════════

async def show_vip_storefront(query, user, context, db, target_chat_id=None, bbs_thread_id=None):
    """Корневой экран VIP: все семьи, мин. цена, таймер global cooldown."""
    from database.db_bbs_vip import check_global_cooldown

    rate = _get_rate(db)
    all_settings = db.get_vip_settings()
    if not all_settings:
        await query.answer("VIP услуги временно недоступны.", show_alert=True)
        return

    # min цена по каждой семье
    by_family: dict = {}
    for row in all_settings:
        fam = row['vip_family']
        if fam not in by_family or row['price_rub'] < by_family[fam]['price_rub']:
            by_family[fam] = row

    # Проверить профиль
    profile = _get_profile(db, user.id)
    has_profile = bool(profile and profile.get('published_at') and not profile.get('deleted_at'))

    text_lines = ["💎 <b>VIP-услуги для вашей анкеты BBS</b>\n"]
    if not has_profile:
        text_lines.append("⚠️ <i>Опубликуйте анкету чтобы купить VIP-услугу.</i>\n")

    keyboard = []
    for fam in FAMILY_ORDER:
        row = by_family.get(fam)
        if not row:
            continue
        icon, name, _ = FAMILY_META.get(fam, ('•', fam, ''))
        min_pulses = _fmt_pulses(row['price_rub'], rate)

        # Global cooldown
        cooldown_suffix = ''
        if fam in GLOBAL_COOLDOWN_FAMILIES:
            ok, locked_until = check_global_cooldown(db, fam)
            if not ok and locked_until:
                cooldown_suffix = f' ⏱ {_fmt_countdown(locked_until)}'

        # Уже активна?
        active_suffix = ''
        if has_profile and fam not in GLOBAL_COOLDOWN_FAMILIES:
            active_sub = db.get_active_vip_by_family(profile['id'], fam)
            if active_sub:
                active_suffix = ' ✅'

        label = f"{icon} {name} — от {min_pulses} 💎{cooldown_suffix}{active_suffix}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"bbs_vip_family_{fam}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_dating")])

    await query.edit_message_text(
        '\n'.join(text_lines),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ════════════════════════════════════════════════════════════════════
# Детальный экран семьи
# ════════════════════════════════════════════════════════════════════

async def show_vip_family(query, data, user, context, db):
    """Детальный экран с вариантами услуги и состоянием active/cooldown."""
    from database.db_bbs_vip import check_global_cooldown

    family = data.removeprefix("bbs_vip_family_")
    rate = _get_rate(db)

    items = db.get_vip_settings(family=family)
    if not items:
        await query.answer("Семья услуг не найдена.", show_alert=True)
        return

    profile = _get_profile(db, user.id)
    has_profile = bool(profile and profile.get('published_at') and not profile.get('deleted_at'))
    profile_id = profile['id'] if has_profile else None

    icon, name, desc = FAMILY_META.get(family, ('•', family, ''))

    text_lines = [f"{icon} <b>{name}</b>", desc, ""]

    # Global cooldown
    global_locked = False
    global_until = None
    if family in GLOBAL_COOLDOWN_FAMILIES:
        ok, global_until = check_global_cooldown(db, family)
        if not ok:
            global_locked = True
            countdown = _fmt_countdown(global_until) if global_until else '?'
            text_lines.append(f"⏱ <b>Заблокировано</b> — {countdown}")
            text_lines.append(f"<i>Другой участник уже использует эту услугу.</i>\n")

    # Активная подписка у этого профиля
    active_sub = None
    if has_profile and profile_id:
        active_sub = db.get_active_vip_by_family(profile_id, family)
        if active_sub:
            exp = active_sub['expires_at'][:16] if active_sub.get('expires_at') else '∞'
            text_lines.append(f"✅ <b>Активна до {exp}</b>\n")

    if not has_profile:
        text_lines.append("⚠️ <i>Опубликуйте анкету для покупки.</i>")

    keyboard = []
    for item in items:
        pulse_price = round(item['price_rub'] / rate, 2)
        dur = f"{item['duration_hours']} ч" if item['duration_hours'] else "разовая"
        label_detail = f"{dur} — {pulse_price:.0f} 💎"

        if not has_profile:
            btn = InlineKeyboardButton(
                f"{label_detail} [нет анкеты]",
                callback_data="bbs_vip_no_profile",
            )
        elif global_locked:
            btn = InlineKeyboardButton(
                f"⏱ {label_detail}",
                callback_data="bbs_vip_cooldown_info",
            )
        elif active_sub:
            btn = InlineKeyboardButton(
                f"✅ Активна — {label_detail}",
                callback_data="bbs_vip_already_active",
            )
        else:
            btn = InlineKeyboardButton(
                f"🛒 {label_detail}",
                callback_data=f"bbs_vip_confirm_{item['vip_code']}",
            )
        keyboard.append([btn])

    keyboard.append([InlineKeyboardButton("🔙 К услугам", callback_data="bbs_vip_storefront")])

    await query.edit_message_text(
        '\n'.join(text_lines),
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ════════════════════════════════════════════════════════════════════
# Экран подтверждения
# ════════════════════════════════════════════════════════════════════

async def show_vip_confirmation(query, data, user, context, db):
    """Экран подтверждения покупки с балансом и предупреждением при нехватке."""
    from database.db_bbs_vip import check_global_cooldown

    vip_code = data.removeprefix("bbs_vip_confirm_")
    setting = db.get_vip_settings(code=vip_code)
    if not setting or not setting.get('is_enabled'):
        await query.answer("Услуга недоступна.", show_alert=True)
        return

    family = setting['vip_family']

    # Профиль
    profile = _get_profile(db, user.id)
    if not profile or not profile.get('published_at') or profile.get('deleted_at'):
        await query.answer("⛔ Опубликуйте анкету сначала.", show_alert=True)
        return

    # Global cooldown
    if family in GLOBAL_COOLDOWN_FAMILIES:
        ok, locked_until = check_global_cooldown(db, family)
        if not ok:
            countdown = _fmt_countdown(locked_until) if locked_until else '?'
            await query.answer(f"Заблокировано другим участником. Доступно {countdown}", show_alert=True)
            return

    # Уже активна?
    existing = db.get_active_vip_by_family(profile['id'], family)
    if existing:
        exp = existing['expires_at'][:16] if existing.get('expires_at') else '?'
        await query.answer(f"Уже активна до {exp}", show_alert=True)
        return

    rate = _get_rate(db)
    price_pulses = round(setting['price_rub'] / rate, 2)
    user_db = db.get_user(user.id)
    balance = float(user_db['balance'] if user_db else 0)
    after = balance - price_pulses

    dur = f"{setting['duration_hours']} ч" if setting.get('duration_hours') else "разовая"
    icon, name, _ = FAMILY_META.get(family, ('💎', family, ''))

    text = (
        f"💎 <b>Подтверждение покупки</b>\n\n"
        f"{icon} <b>{setting['title']}</b>\n"
        f"Длительность: {dur}\n"
        f"Цена: <b>{price_pulses:.2f} 💎</b>\n\n"
        f"Ваш баланс: <b>{balance:.2f} 💎</b>\n"
        f"После покупки: <b>{after:.2f} 💎</b>"
    )

    if after < 0:
        need = -after
        text += (
            f"\n\n❌ <b>Не хватает {need:.2f} 💎</b>\n\n"
            f"<i>⏱ После обращения к администратору курс фиксируется на 24 часа.</i>"
        )
        keyboard = [
            [InlineKeyboardButton("📨 Обратиться к администратору",
                                  callback_data=f"bbs_vip_contact_admin_{vip_code}")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"bbs_vip_family_{family}")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"bbs_vip_buy_{vip_code}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"bbs_vip_family_{family}")],
        ]

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


# ════════════════════════════════════════════════════════════════════
# Покупка
# ════════════════════════════════════════════════════════════════════

async def process_vip_purchase(query, data, user, context, db, target_chat_id, bbs_thread_id):
    """Атомарная покупка через purchase_vip() + побочные эффекты (пин, эмодзи)."""
    from database.db_bbs_vip import purchase_vip, VipPurchaseError

    vip_code = data.removeprefix("bbs_vip_buy_")

    # Профиль
    profile = _get_profile(db, user.id)
    if not profile or not profile.get('published_at') or profile.get('deleted_at'):
        await query.answer("⛔ Опубликуйте анкету сначала.", show_alert=True)
        return

    # ─── Атомарная покупка ──────────────────────────────────────────
    try:
        result = purchase_vip(db, user_id=user.id, profile_id=profile['id'], vip_code=vip_code)
    except VipPurchaseError as e:
        if e.code == 'not_enough':
            extra = e.extra
            _s = db.get_vip_settings(code=vip_code)
            await _show_insufficient_balance(
                query,
                extra.get('price_pulses', 0),
                extra.get('balance', 0),
                _s['vip_family'] if _s else '',
                vip_code=vip_code,
            )
            return
        if e.code == 'global_cooldown':
            lu = e.extra.get('locked_until', '')
            countdown = _fmt_countdown(lu) if lu else '?'
            await query.answer(f"Заблокировано. Доступно {countdown}", show_alert=True)
            return
        if e.code == 'family_active':
            exp = e.extra.get('expires_at', '?')
            await query.answer(f"Уже активна до {exp[:16] if exp else '?'}", show_alert=True)
            return
        await query.answer(f"❌ {e.message}", show_alert=True)
        return
    except Exception as e:
        logger.exception(f"process_vip_purchase unexpected error uid={user.id} code={vip_code}: {e}")
        await query.answer("❌ Внутренняя ошибка. Деньги не списаны.", show_alert=True)
        return

    sub_id   = result['sub_id']
    family   = result['vip_family']
    expires_at = result.get('expires_at')

    # ─── Побочные эффекты (после коммита, не держим транзакцию) ────
    await _apply_side_effects(
        bot=context.bot,
        db=db,
        user_id=user.id,
        profile=profile,
        sub_id=sub_id,
        family=family,
        target_chat_id=target_chat_id,
        bbs_thread_id=bbs_thread_id,
    )

    # ─── Ответ юзеру ───────────────────────────────────────────────
    setting = db.get_vip_settings(code=vip_code) or {}
    icon, name, _ = FAMILY_META.get(family, ('💎', family, ''))
    expires_str = expires_at[:16] if expires_at else '—'

    text = (
        f"✅ <b>Покупка успешна!</b>\n\n"
        f"{icon} <b>{setting.get('title', name)}</b>\n"
        f"Списано: <b>{result['price_pulses']:.2f} 💎</b>\n"
        f"Действует до: <b>{expires_str}</b>"
    )
    if family == 'PROMO_CHAT' and result.get('slots'):
        slots_str = ' / '.join(s[11:16] for s in result['slots'][:3])
        text += f"\n\nПубликации запланированы: <b>{slots_str}</b>"

    keyboard = [[InlineKeyboardButton("🔙 К услугам", callback_data="bbs_vip_storefront")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def _apply_side_effects(bot, db, user_id, profile, sub_id, family,
                               target_chat_id, bbs_thread_id):
    """Пин, VIP-эмодзи — всё после коммита транзакции."""
    profile_id = profile['id']

    # Пин для VIP2, VIP3, VIP5
    if family in ('SILENT_PIN', 'LOUD_PIN', 'BUMP_PIN'):
        try:
            msg_ids = json.loads(profile.get('message_ids') or '[]')
            if msg_ids:
                disable_notif = (family != 'LOUD_PIN')
                await bot.pin_chat_message(
                    chat_id=target_chat_id,
                    message_id=msg_ids[0],
                    disable_notification=disable_notif,
                )
                col = 'loud_pin_msg_id' if family == 'LOUD_PIN' else 'silent_pin_msg_id'
                db.cursor.execute(
                    f"UPDATE bbs_vip_subscriptions SET {col}=? WHERE id=?",
                    (msg_ids[0], sub_id)
                )
                db.conn.commit()
        except Exception as e:
            logger.error(f"pin failed sub={sub_id} family={family}: {e}")

    # VIP-эмодзи: перепубликовать с эмодзи (update_profile_in_place)
    try:
        from handlers.BBS.publishing_bbs import update_profile_in_place
        await update_profile_in_place(bot, db, user_id, target_chat_id)
    except Exception as e:
        logger.warning(f"VIP emoji update failed user={user_id}: {e}")


# ════════════════════════════════════════════════════════════════════
# Вспомогательные экраны
# ════════════════════════════════════════════════════════════════════

async def _show_insufficient_balance(query, price_pulses: float, balance: float,
                                      family: str, vip_code: str = ''):
    need = max(0, price_pulses - balance)
    contact_cb = f"bbs_vip_contact_admin_{vip_code}" if vip_code else "bbs_vip_storefront"
    text = (
        f"❌ <b>Недостаточно Пульсов</b>\n\n"
        f"Нужно: <b>{price_pulses:.2f} 💎</b>\n"
        f"На балансе: <b>{balance:.2f} 💎</b>\n"
        f"Не хватает: <b>{need:.2f} 💎</b>\n\n"
        f"Обратитесь к администратору — он зачислит Пульсы за ручной платёж.\n\n"
        f"<i>⏱ После обращения курс фиксируется на 24 часа.</i>"
    )
    keyboard = [
        [InlineKeyboardButton("📨 Обратиться к администратору", callback_data=contact_cb)],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"bbs_vip_family_{family}" if family else "bbs_vip_storefront")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_contact_admin(query, data, user, context, db, admin_id):
    """Пользователь нажал «Обратиться к администратору» — шлём DM Владельцу."""
    vip_code = data.removeprefix("bbs_vip_contact_admin_")
    setting = db.get_vip_settings(code=vip_code)
    rate = _get_rate(db)

    user_db = db.get_user(user.id)
    balance = float(user_db['balance'] if user_db else 0)
    price_pulses = round(setting['price_rub'] / rate, 2) if setting else 0
    need = max(0.0, price_pulses - balance)

    username = f"@{user.username}" if user.username else f"id:{user.id}"
    service_name = setting.get('title', vip_code) if setting else vip_code

    from datetime import datetime
    now_str = datetime.now().strftime('%d.%m.%Y %H:%M')

    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"📨 <b>Запрос на VIP BBS</b>\n\n"
                f"👤 {username}\n"
                f"🛒 Услуга: <b>{service_name}</b> (<code>{vip_code}</code>)\n"
                f"💎 Нужно: <b>{price_pulses:.2f}</b> / Баланс: <b>{balance:.2f}</b>\n"
                f"❗ Не хватает: <b>{need:.2f} 💎</b>\n\n"
                f"💱 Курс на момент обращения: 1 💎 = {rate:.4f} ₽\n"
                f"🕐 {now_str} — курс действует 24 часа"
            ),
            parse_mode='HTML',
        )
        logger.info(f"contact_admin: sent to admin_id={admin_id} for user={user.id} code={vip_code}")
    except Exception as e:
        logger.warning(f"contact_admin send failed: {e}")

    await query.edit_message_text(
        f"✅ <b>Запрос отправлен!</b>\n\n"
        f"Администратор получил уведомление.\n\n"
        f"💱 Курс на момент обращения: <b>1 💎 = {rate:.4f} ₽</b>\n"
        f"⏱ Этот курс действует <b>24 часа</b> с момента обращения.\n\n"
        f"<i>Ожидайте ответа.</i>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 К услугам", callback_data="bbs_vip_storefront"),
        ]]),
    )


async def show_topup_stub(query, user=None):
    """Заглушка «Пополнить баланс»."""
    text = (
        "💳 <b>Пополнение баланса</b>\n\n"
        "Напишите владельцу <b>@LockUp11</b> — он переведёт вам Пульсы за ручной платёж.\n\n"
        "<i>Telegram Stars сознательно не подключены.</i>"
    )
    keyboard = [
        [InlineKeyboardButton("💬 Написать @LockUp11", url="https://t.me/LockUp11")],
        [InlineKeyboardButton("🔙 Назад к услугам", callback_data="bbs_vip_storefront")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def show_cooldown_info(query, user=None):
    """Информация о заблокированной услуге (нажатие на кнопку с таймером)."""
    await query.answer(
        "Эта услуга временно заблокирована. Дождитесь окончания cooldown.",
        show_alert=True,
    )


async def show_no_profile_info(query, user=None):
    await query.answer(
        "⛔ Сначала опубликуйте анкету в BBS.",
        show_alert=True,
    )


async def show_already_active_info(query, user=None):
    await query.answer(
        "Эта услуга уже активна. Дождитесь истечения срока.",
        show_alert=True,
    )
