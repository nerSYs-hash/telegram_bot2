#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Callback-ы активностей: лотерея, бинго, донаты, подарки, банковские переводы."""

import logging
from handlers.donate_handlers import (
    show_donate_menu, donate_to_user_start, donate_pick_user,
    donate_user_amount, donate_user_custom, donate_user_confirm,
    donate_to_bank_start, donate_bank_custom, donate_bank_amount,
    donate_bank_confirm, donate_show_history,
)
from handlers.bank_handlers import start_bank_transfer, select_transfer_amount, execute_bank_transfer

logger = logging.getLogger(__name__)


async def dispatch_activity(handler, query, data, user, context) -> bool:
    """Обрабатывает callback-ы активностей. True если обработано."""
    db = handler.db

    # ── Лотерея ──
    if data == "menu_lottery":
        await handler.lottery_handler.show_lottery_menu(query, user)
    elif data.startswith("buy_ticket_"):
        await handler.lottery_handler.buy_ticket(query, user, data)
    elif data.startswith("my_tickets_"):
        await handler.lottery_handler.show_my_tickets(query, user, data)
    elif data.startswith("lott_"):
        await handler.lottery_handler.handle_admin_callback(query, data, user, context)
    elif data.startswith("lottery_"):
        await handler.lottery_handler.handle_admin_callback(query, data, user, context)

    # ── Бинго ──
    elif data == "menu_bingo":
        await handler.bingo_handler.handle_callback(query, data, user, context)
    elif data.startswith("bingo_") or data.startswith("bcard_") or data.startswith("bbingo_"):
        await handler.bingo_handler.handle_callback(query, data, user, context)

    # ── Донаты ──
    elif data == "donate_menu":
        await show_donate_menu(query, user, db)
    elif data == "donate_to_user_start":
        await donate_to_user_start(query, user, context, db)
    elif data.startswith("donate_pick_user_"):
        await donate_pick_user(query, data, user, context, db)
    elif data.startswith("donate_user_amount_"):
        await donate_user_amount(query, data, user, context, db)
    elif data.startswith("donate_user_custom_"):
        await donate_user_custom(query, user, context, db)
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
    elif data in ("menu_monthly_gift", "monthly_gift_draw", "monthly_gift_toggle",
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
