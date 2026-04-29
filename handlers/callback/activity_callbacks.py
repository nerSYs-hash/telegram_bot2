#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Callback-ы активностей: лотерея, бинго, донаты, подарки, банковские переводы."""

import logging
from handlers.donate_handlers import (
    show_donate_menu, donate_to_user_start, donate_pick_user,
    donate_user_amount, donate_user_custom, donate_user_confirm,
    donate_to_bank_start, donate_bank_custom, donate_bank_amount,
    donate_bank_confirm, donate_show_history,
    donate_cat_recent, donate_cat_activists, donate_cat_poor, donate_cat_manual,
)
from handlers.bank_handlers import start_bank_transfer, select_transfer_amount, execute_bank_transfer
from handlers.banner_utils import show_banner, enter_banner

logger = logging.getLogger(__name__)


async def dispatch_activity(handler, query, data, user, context) -> bool:
    """Обрабатывает callback-ы активностей. True если обработано."""
    db = handler.db

    # ── Баннеры-онбординг ──
    if data.startswith("banner_enter_"):
        await enter_banner(query, context, db, handler)
        return True

    # ── Лотерея ──
    if data == "menu_lottery":
        if await show_banner(query, context, db, 'lottery'):
            return True
        await handler.lottery_handler.show_lottery_menu(query, user)
    elif data.startswith("buy_ticket_"):
        await handler.lottery_handler.handle_buy_ticket(query, data, user, context)
    elif data.startswith("my_tickets_"):
        await handler.lottery_handler.handle_my_tickets(query, data, user, context)
    elif data.startswith("lott_"):
        await handler.lottery_handler.handle_lott_callback(query, data, user, context)
    elif data.startswith("lottery_"):
        await handler.lottery_handler.handle_lottery_callback(query, data, user, context)

    # ── Бинго ──
    elif data == "menu_bingo":
        if await show_banner(query, context, db, 'bingo'):
            return True
        await handler.bingo_handler.show_bingo_menu(query, user)
    elif data.startswith("bingo_"):
        await handler.bingo_handler.handle_bingo_callback(query, data, user, context)
    elif data.startswith("bcard_"):
        await handler.bingo_handler.handle_card_callback(query, data, user, context)
    elif data.startswith("bbingo_"):
        await handler.bingo_handler.handle_bingo_claim(query, data, user, context)

    # ── Донаты ──
    elif data == "donate_menu":
        if await show_banner(query, context, db, 'donate'):
            return True
        await show_donate_menu(query, user, db)
    elif data == "donate_to_user_start":
        await donate_to_user_start(query, user, context, db)
    elif data == "donate_cat_recent":
        await donate_cat_recent(query, user, context, db)
    elif data == "donate_cat_activists":
        await donate_cat_activists(query, user, context, db)
    elif data == "donate_cat_poor":
        await donate_cat_poor(query, user, context, db)
    elif data == "donate_cat_manual":
        await donate_cat_manual(query, user, context, db)
    elif data.startswith("donate_pick_user_"):
        await donate_pick_user(query, data, user, context, db)
    elif data.startswith("donate_user_amount_"):
        await donate_user_amount(query, data, user, context, db)
    elif data.startswith("donate_user_custom_"):
        await donate_user_custom(query, data, user, context, db)
    elif data.startswith("donate_user_confirm_"):
        await donate_user_confirm(query, data, user, context, db)
    elif data == "donate_to_bank_start":
        await donate_to_bank_start(query, user, context, db)
    elif data.startswith("donate_bank_amount_"):
        await donate_bank_amount(query, data, user, context, db)
    elif data.startswith("donate_bank_confirm_"):
        await donate_bank_confirm(query, data, user, context, db)
    elif data == "donate_bank_custom":
        await donate_bank_custom(query, user, context, db)
    elif data == "donate_history":
        await donate_show_history(query, user, db)

    # ── Подарки месяца ──
    elif data == "menu_monthly_gift":
        if await show_banner(query, context, db, 'gift'):
            return True
        await handler.gift_handler.handle_callback(query, data, user, context)
    elif data in ("monthly_gift_draw", "monthly_gift_toggle",
                  "monthly_gift_history", "monthly_gift_create", "monthly_gift_participants",
                  "monthly_gift_announce", "monthly_gift_confirm_draw",
                  "monthly_gift_user_view", "monthly_gift_participate",
                  "monthly_gift_my_progress", "monthly_gift_winners"):
        await handler.gift_handler.handle_callback(query, data, user, context)
    elif data.startswith("mgift_set_"):
        await handler.gift_handler.handle_callback(query, data, user, context)

    # ── Банковские переводы ──
    elif data == "bank_transfer_start":
        await start_bank_transfer(query, user, context, db, handler.main_admin_id)
    elif data.startswith("bt_user_"):
        target_id = int(data.replace("bt_user_", ""))
        await select_transfer_amount(query, target_id, user, context, db, handler.main_admin_id)
    elif data.startswith("bt_amount_"):
        parts = data.replace("bt_amount_", "").split("_")
        target_id, amount = int(parts[0]), float(parts[1])
        await execute_bank_transfer(query, user, db, handler.main_admin_id, target_id, amount, context)
    elif data.startswith("bt_custom_"):
        target_id = int(data.replace("bt_custom_", ""))
        context.user_data['awaiting_bank_transfer'] = True
        context.user_data['bt_custom_user_id'] = target_id
        await query.edit_message_text("💰 Введите сумму перевода:")
    elif data == "bt_username_input":
        if user.id != handler.main_admin_id:
            await query.answer("Нет доступа.", show_alert=True)
            return True
        context.user_data['awaiting_bt_username'] = True
        await query.edit_message_text("✏️ Введите @username получателя:")

    else:
        return False
    return True
