#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Панель владельца: управление VIP BBS — прайс, статистика, активные подписки."""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

FAMILY_ORDER = ['BUMP', 'SILENT_PIN', 'LOUD_PIN', 'CUSTOM_BUMP', 'BUMP_PIN', 'PROMO_CHAT']

FAMILY_META = {
    'BUMP':        ('🚀', 'VIP1 — Перепубликация при чужих публикациях'),
    'SILENT_PIN':  ('📌', 'VIP2 — Тихий закреп, 24 ч'),
    'LOUD_PIN':    ('🔔', 'VIP3 — Громкий закреп (global cooldown 7 дней)'),
    'CUSTOM_BUMP': ('⚡', 'VIP4 — Автопубликация раз в сутки (72/120/168 ч)'),
    'BUMP_PIN':    ('🎯', 'VIP5 — Автопуб + тихий закреп (72/120/168 ч)'),
    'PROMO_CHAT':  ('📣', 'VIP6 — Промо в общий чат 10:00/15:00/21:00 МСК'),
}

FAMILY_VIP_NUM = {
    'BUMP': 'VIP1', 'SILENT_PIN': 'VIP2', 'LOUD_PIN': 'VIP3',
    'CUSTOM_BUMP': 'VIP4', 'BUMP_PIN': 'VIP5', 'PROMO_CHAT': 'VIP6',
}


def _is_owner(db, user_id: int, admin_id: int) -> bool:
    if user_id == admin_id:
        return True
    user_data = db.get_user(user_id)
    return bool(user_data and user_data['is_owner'])


async def show_vip_root_menu(query, user, db, admin_id):
    """Корневое меню «👑 Управление VIP BBS»."""
    if not _is_owner(db, user.id, admin_id):
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    text = "👑 <b>Управление VIP BBS</b>\n\nВыберите раздел:"
    keyboard = [
        [InlineKeyboardButton("📋 Прайс-лист (RUB / 💎)", callback_data="bbs_vip_pricelist")],
        [InlineKeyboardButton("📊 Статистика", callback_data="bbs_vip_stats")],
        [InlineKeyboardButton("📜 Активные подписки", callback_data="bbs_vip_active_subs")],
        [InlineKeyboardButton("🔙 Назад", callback_data="panel_main")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def show_vip_pricelist(query, user, db, admin_id):
    """Прайс-лист VIP услуг с кнопками ✏️ для каждой позиции."""
    if not _is_owner(db, user.id, admin_id):
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    rate_str = db.get_setting('pulse_rate', '1.42') or '1.42'
    try:
        rate = float(rate_str)
    except (ValueError, TypeError):
        rate = 1.42
    if rate <= 0:
        rate = 1.42

    all_settings = db.get_vip_settings()
    if not all_settings:
        await query.answer("❌ Прайс не загружен.", show_alert=True)
        return

    by_family = {}
    for row in all_settings:
        by_family.setdefault(row['vip_family'], []).append(row)

    lines = [
        "👑 <b>Управление VIP BBS — Прайс-лист</b>",
        f"Курс: {rate:.2f} RUB/💎\n",
    ]
    edit_buttons = []

    for fam in FAMILY_ORDER:
        items = by_family.get(fam)
        if not items:
            continue
        icon, label = FAMILY_META.get(fam, ('•', fam))
        lines.append(f"{icon} <b>{label}</b>")
        for item in items:
            pulse_price = round(item['price_rub'] / rate, 2)
            dur_str = f"{item['duration_hours']} ч" if item['duration_hours'] else "разовая"
            lines.append(f"   • {dur_str}  — {item['price_rub']:.2f} RUB ≈ {pulse_price:.2f} 💎")
            vip_num = FAMILY_VIP_NUM.get(fam, '')
            btn_label = f"✏️ {vip_num}·{item['vip_code']}" if vip_num else f"✏️ {item['vip_code']}"
            edit_buttons.append(
                InlineKeyboardButton(
                    btn_label,
                    callback_data=f"bbs_vip_price_edit_{item['vip_code']}",
                )
            )

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3980] + "\n\n<i>...обрезано</i>"

    keyboard = []
    for i in range(0, len(edit_buttons), 2):
        keyboard.append(edit_buttons[i:i + 2])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_vip_root")])

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def start_edit_vip_price(query, data, user, context, db, admin_id):
    """Точка входа FSM изменения цены. data = 'bbs_vip_price_edit_<code>'."""
    if not _is_owner(db, user.id, admin_id):
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    code = data.removeprefix("bbs_vip_price_edit_")
    setting = db.get_vip_settings(code=code)
    if not setting:
        await query.answer("❌ Услуга не найдена.", show_alert=True)
        return

    context.user_data['vip_price_edit'] = code
    context.user_data['owner_awaiting'] = f'vip_price_edit_{code}'

    vip_num = FAMILY_VIP_NUM.get(setting['vip_family'], '')
    vip_tag = f" [{vip_num}]" if vip_num else ''
    text = (
        f"✏️ <b>Изменить цену</b>{vip_tag}\n\n"
        f"Услуга: <b>{code}</b>\n"
        f"Семья: <b>{setting['vip_family']}</b>{vip_tag}\n"
        f"{setting['title']}\n"
        f"Текущая цена: <b>{setting['price_rub']:.2f} RUB</b>\n\n"
        f"Введите новую цену в RUB (от 0.01 до 999999.99):"
    )
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="bbs_vip_pricelist")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_vip_price_input(message, context, db):
    """
    Обработчик ввода новой цены.
    Вызывается из handle_owner_text_input при owner_awaiting = 'vip_price_edit_<code>'.
    """
    code = context.user_data.pop('vip_price_edit', None)
    context.user_data.pop('owner_awaiting', None)

    raw = (message.text or '').strip().replace(',', '.')
    try:
        price = round(float(raw), 2)
        if not (0.01 <= price <= 999999.99):
            raise ValueError("out of range")
    except (ValueError, TypeError):
        # Возвращаем в FSM-состояние
        context.user_data['vip_price_edit'] = code
        context.user_data['owner_awaiting'] = f'vip_price_edit_{code}'
        await message.reply_text(
            "❌ Некорректная цена. Введите число от 0.01 до 999999.99:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="bbs_vip_pricelist"),
            ]]),
        )
        return

    ok = db.set_vip_price(code, price)
    if not ok:
        await message.reply_text(
            f"❌ Услуга <code>{code}</code> не найдена.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="bbs_vip_pricelist"),
            ]]),
        )
        return

    rate_str = db.get_setting('pulse_rate', '1.42') or '1.42'
    try:
        rate = float(rate_str)
    except (ValueError, TypeError):
        rate = 1.42
    if rate <= 0:
        rate = 1.42
    pulse_price = round(price / rate, 2)

    try:
        await message.delete()
    except Exception:
        pass

    resp_text = (
        f"✅ <b>Сохранено</b>\n\n"
        f"Услуга: <b>{code}</b>\n"
        f"Новая цена: <b>{price:.2f} RUB ≈ {pulse_price:.2f} 💎</b>"
    )
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 К прайс-листу", callback_data="bbs_vip_pricelist"),
    ]])

    panel_msg_id = context.user_data.get('owner_panel_msg_id')
    panel_chat_id = context.user_data.get('owner_panel_chat_id')
    if panel_msg_id and panel_chat_id:
        from handlers.owner_handlers import _edit_panel
        await _edit_panel(context, panel_chat_id, panel_msg_id, resp_text, markup)
    else:
        await message.reply_text(resp_text, parse_mode='HTML', reply_markup=markup)


async def show_vip_stats(query, user, db, admin_id):
    """Статистика VIP покупок: 24ч / 7д / 30д / всего + топ-3 услуги."""
    if not _is_owner(db, user.id, admin_id):
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    def _stat(period_hours):
        row = db.count_vip_purchases_stats(period_hours)
        if row:
            return int(row['cnt']), float(row['revenue'])
        return 0, 0.0

    cnt_24, rev_24 = _stat(24)
    cnt_7d, rev_7d = _stat(168)
    cnt_30d, rev_30d = _stat(720)
    cnt_all, rev_all = _stat(None)

    try:
        db.cursor.execute("""
            SELECT vip_code, COUNT(*) AS cnt
            FROM bbs_vip_subscriptions
            GROUP BY vip_code
            ORDER BY cnt DESC
            LIMIT 3
        """)
        top3 = db.cursor.fetchall()
        top3_lines = "\n".join(
            f"   {i + 1}. {r['vip_code']} — {r['cnt']} шт." for i, r in enumerate(top3)
        ) or "   — нет данных —"
    except Exception:
        top3_lines = "   — нет данных —"

    text = (
        f"📊 <b>Статистика VIP BBS</b>\n\n"
        f"За 24ч:  <b>{cnt_24}</b> покупок / <b>{rev_24:.2f}</b> 💎\n"
        f"За 7д:   <b>{cnt_7d}</b> покупок / <b>{rev_7d:.2f}</b> 💎\n"
        f"За 30д:  <b>{cnt_30d}</b> покупок / <b>{rev_30d:.2f}</b> 💎\n"
        f"Всего:   <b>{cnt_all}</b> покупок / <b>{rev_all:.2f}</b> 💎\n\n"
        f"🏆 <b>Топ-3 услуги:</b>\n{top3_lines}"
    )
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="bbs_vip_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="bbs_vip_root")],
    ]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def show_vip_active_subs(query, user, db, admin_id, page: int = 0):
    """Список активных подписок с пагинацией и кнопками ручной отмены."""
    if not _is_owner(db, user.id, admin_id):
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    PAGE_SIZE = 8
    subs = db.list_active_vip_subscriptions(limit=200)
    total = len(subs)

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_subs = subs[start:end]

    if not page_subs:
        text = "📜 <b>Активные подписки VIP</b>\n\n<i>Нет активных подписок.</i>"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="bbs_vip_root")]]
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    lines = [f"📜 <b>Активные подписки VIP</b> (стр. {page + 1}, всего {total}):\n"]
    for s in page_subs:
        uid = s['profile_user_id']
        username = s.get('profile_username')
        display = f"@{username}" if username else (s['profile_name'] or f"ID:{uid}")
        user_link = f'<a href="tg://user?id={uid}">{display}</a>'
        expires = s['expires_at'][:16] if s['expires_at'] else 'разовая'
        lines.append(f"• <b>{s['vip_code']}</b> | {user_link} | до {expires} | {s['price_rub_paid']:.0f}₽")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3980] + "\n<i>...обрезано</i>"

    keyboard = []
    cancel_btns = [
        InlineKeyboardButton(f"✖ {s['vip_code']}", callback_data=f"bbs_vip_cancel_sub_{s['id']}")
        for s in page_subs
    ]
    for i in range(0, len(cancel_btns), 2):
        keyboard.append(cancel_btns[i:i + 2])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Назад", callback_data=f"bbs_vip_subs_page_{page - 1}"))
    if end < total:
        nav.append(InlineKeyboardButton("▶ Вперёд", callback_data=f"bbs_vip_subs_page_{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bbs_vip_root")])

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def cancel_vip_subscription(query, data, user, db, admin_id):
    """Ручная отмена подписки владельцем."""
    if not _is_owner(db, user.id, admin_id):
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    try:
        sub_id = int(data.removeprefix("bbs_vip_cancel_sub_"))
    except (ValueError, TypeError):
        await query.answer("❌ Некорректный ID.", show_alert=True)
        return

    try:
        db.cursor.execute(
            "UPDATE bbs_vip_subscriptions SET status = 'cancelled' WHERE id = ? AND status = 'active'",
            (sub_id,),
        )
        db.conn.commit()
        affected = db.cursor.rowcount
    except Exception as e:
        logger.error(f"cancel_vip_subscription error: {e}")
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)
        return

    if affected:
        await query.answer("✅ Подписка отменена.", show_alert=True)
    else:
        await query.answer("⚠️ Подписка не найдена или уже отменена.", show_alert=True)

    await show_vip_active_subs(query, user, db, admin_id)
