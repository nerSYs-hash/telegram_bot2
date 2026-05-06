#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Роутер всех bbs_vip_* callback-ов (пользовательские + владельца).
Вызывается из callback_router.py до общего BBS-блока.

Редакция: 2026-04-28 (без INSTANT_BUMP, новые VIP1-VIP6).
"""

import logging
from handlers.bbs_vip_handlers import (
    show_vip_storefront,
    show_vip_family,
    show_vip_confirmation,
    process_vip_purchase,
    show_topup_stub,
    show_cooldown_info,
    show_no_profile_info,
    show_already_active_info,
    handle_contact_admin,
)
from handlers.bbs_vip_owner import (
    show_vip_root_menu,
    show_vip_pricelist,
    start_edit_vip_price,
    show_vip_stats,
    show_vip_active_subs,
    cancel_vip_subscription,
    show_vip_discount_menu,
    cb_disc_toggle,
    cb_disc_delete,
    cb_disc_create_entry,
    cb_disc_toggle_code,
    cb_disc_scope_all,
    cb_disc_save_selected,
)

logger = logging.getLogger(__name__)


async def dispatch_bbs_vip(handler, query, data, user, context) -> bool:
    """
    Роутер callback-ов bbs_vip_*.
    Возвращает True если обработан, False — нет.
    """
    db            = handler.db
    target_chat_id = handler.target_chat_id
    bbs_thread_id  = handler.bbs_thread_id
    admin_id       = handler.main_admin_id

    # ── Пользовательские ────────────────────────────────────────────
    if data == "bbs_vip_storefront":
        await show_vip_storefront(query, user, context, db, target_chat_id, bbs_thread_id)

    elif data.startswith("bbs_vip_family_"):
        await show_vip_family(query, data, user, context, db)

    elif data.startswith("bbs_vip_confirm_"):
        await show_vip_confirmation(query, data, user, context, db)

    elif data.startswith("bbs_vip_buy_"):
        await process_vip_purchase(query, data, user, context, db, target_chat_id, bbs_thread_id)

    elif data == "bbs_vip_topup":
        await show_topup_stub(query, user)

    elif data == "bbs_vip_cooldown_info":
        await show_cooldown_info(query, user)

    elif data == "bbs_vip_no_profile":
        await show_no_profile_info(query, user)

    elif data == "bbs_vip_already_active":
        await show_already_active_info(query, user)

    elif data.startswith("bbs_vip_contact_admin_"):
        await handle_contact_admin(query, data, user, context, db, admin_id)

    # ── Владелец ─────────────────────────────────────────────────────
    elif data == "bbs_vip_root":
        await show_vip_root_menu(query, user, db, admin_id)

    elif data == "bbs_vip_pricelist":
        await show_vip_pricelist(query, user, db, admin_id)

    elif data == "bbs_vip_stats":
        await show_vip_stats(query, user, db, admin_id)

    elif data == "bbs_vip_active_subs":
        await show_vip_active_subs(query, user, db, admin_id)

    elif data.startswith("bbs_vip_subs_page_"):
        try:
            page = int(data.removeprefix("bbs_vip_subs_page_"))
        except (ValueError, TypeError):
            page = 0
        await show_vip_active_subs(query, user, db, admin_id, page=page)

    elif data.startswith("bbs_vip_price_edit_"):
        await start_edit_vip_price(query, data, user, context, db, admin_id)

    # ── Скидки ───────────────────────────────────────────────────────
    elif data == "bbs_vip_discount":
        await show_vip_discount_menu(query, user, db, admin_id)

    elif data == "bbs_vip_disc_toggle":
        await cb_disc_toggle(query, user, db, admin_id)

    elif data == "bbs_vip_disc_delete":
        await cb_disc_delete(query, user, db, admin_id)

    elif data == "bbs_vip_disc_create":
        await cb_disc_create_entry(query, user, context, db, admin_id)

    elif data.startswith("bbs_vip_disc_tog_"):
        await cb_disc_toggle_code(query, data, user, context, db, admin_id)

    elif data == "bbs_vip_disc_scope_all":
        await cb_disc_scope_all(query, user, context, db, admin_id)

    elif data == "bbs_vip_disc_save_sel":
        await cb_disc_save_selected(query, user, context, db, admin_id)

    elif data.startswith("bbs_vip_cancel_sub_"):
        await cancel_vip_subscription(query, data, user, db, admin_id)

    else:
        return False

    return True
