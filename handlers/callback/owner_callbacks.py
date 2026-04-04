#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Callback-ы Пульта Владельца: дашборд, персонал, модерация, триггеры, журнал, система."""

import logging
from handlers.owner_handlers import (
    show_staff_menu, staff_add_start, staff_remove_start,
    show_economy_menu, emit_start, wipe_confirm_step1, wipe_execute,
    show_moderation_menu, bl_add_start, bl_remove_start,
    mute_start, unmute_start,
    show_system_menu, toggle_maintenance,
    send_database_backup,
    show_statistics_not_in_chat,
    show_recovery_menu, recovery_other_confirm, recovery_other_execute,
)
from handlers.shipper_handlers import (
    show_shipper_menu,
    toggle_shipper_enabled,
    start_shipper_timing_input,
    start_shipper_add_phrase,
    show_shipper_target_menu,
    set_shipper_target_mode,
    select_shipper_category,
    show_shipper_phrases,
    delete_shipper_phrase,
    run_shipper_now,
)
from handlers.admin_moderation import send_admin_panel
from handlers.moderation import handle_restrict_callback
from handlers.triggers_handlers import show_triggers_menu, handle_trigger_callback
from handlers.journal_handlers import (
    show_journal_menu, journal_connect_start,
    journal_disconnect, journal_test,
)

logger = logging.getLogger(__name__)


async def dispatch_owner(handler, query, data, user, context) -> bool:
    """Обрабатывает callback-ы Пульта Владельца. True если обработано."""
    db = handler.db
    admin_id = handler.main_admin_id
    target_chat_id = handler.target_chat_id

    # ── Панель ──
    if data in ("owner_dashboard", "panel_main"):
        await send_admin_panel(query.message._bot, query.message.chat.id, is_owner=True)
    elif data == "owner_backup":
        await send_database_backup(query, user, db, admin_id, context)

    # ── Персонал ──
    elif data == "owner_staff":
        await show_staff_menu(query, db, admin_id)
    elif data == "owner_staff_add":
        await staff_add_start(query, context, db, admin_id)
    elif data == "owner_staff_remove":
        await staff_remove_start(query, context, db, admin_id)

    # ── Экономика ──
    elif data == "owner_economy":
        await show_economy_menu(query, db, admin_id)
    elif data == "owner_emit":
        await emit_start(query, context, db, admin_id)
    elif data == "owner_wipe":
        await wipe_confirm_step1(query, db, admin_id)
    elif data == "owner_wipe_confirm":
        await wipe_execute(query, db, admin_id)

    # ── Шиппер ──
    elif data == "owner_shipper_menu":
        await show_shipper_menu(query, context, db, target_chat_id)
    elif data == "owner_shipper_toggle":
        await toggle_shipper_enabled(query, context, db, target_chat_id)
    elif data == "owner_shipper_timing":
        await start_shipper_timing_input(query, context, db)
    elif data == "owner_shipper_target_menu":
        await show_shipper_target_menu(query, db)
    elif data.startswith("owner_shipper_target_"):
        await set_shipper_target_mode(query, data, context, db, target_chat_id)
    elif data == "owner_shipper_add_phrase":
        await start_shipper_add_phrase(query, context, db)
    elif data.startswith("owner_shipper_cat_"):
        await select_shipper_category(query, data, context, db)
    elif data.startswith("owner_shipper_list_"):
        try:
            page = int(data.replace("owner_shipper_list_", ""))
        except Exception:
            page = 1
        await show_shipper_phrases(query, db, page=page)
    elif data.startswith("owner_shipper_listcat_"):
        await show_shipper_phrases(query, db, page=1)
    elif data.startswith("owner_shipper_phrase_delete_"):
        await delete_shipper_phrase(query, data, db)
    elif data == "owner_shipper_run_now":
        await run_shipper_now(query, context, db, target_chat_id)
    elif data == "owner_shipper_noop":
        await query.answer()

    # ── Модерация ──
    elif data == "owner_moderation":
        await show_moderation_menu(query, db, admin_id)
    elif data == "owner_bl_add":
        await bl_add_start(query, context, db, admin_id)
    elif data == "owner_bl_remove":
        await bl_remove_start(query, context, db, admin_id)
    elif data.startswith("owner_mute_"):
        duration_key = data.replace("owner_mute_", "")
        await mute_start(query, context, db, admin_id, duration_key)
    elif data == "owner_unmute_start":
        await unmute_start(query, context, db, admin_id)

    # ── Система ──
    elif data == "owner_system":
        await show_system_menu(query, db, admin_id)
    elif data == "owner_maintenance_toggle":
        await toggle_maintenance(query, db, admin_id)

    # ── Restrict (модерация в чате) ──
    elif data.startswith("restrict_"):
        await handle_restrict_callback(query, data, context, db, admin_id, target_chat_id)

    # ── Триггеры ──
    elif data == "owner_triggers":
        await show_triggers_menu(query, db, admin_id)
    elif data.startswith("trigger_"):
        await handle_trigger_callback(query, data, context, db, admin_id)

    # ── Статистика "Не в чате" ──
    elif data == "owner_stats_not_in_chat":
        await show_statistics_not_in_chat(query, admin_id)

    # ── Восстановление веток ──
    elif data == "owner_recovery":
        await show_recovery_menu(query, db, admin_id)
    elif data == "owner_recovery_other_confirm":
        await recovery_other_confirm(query, db, admin_id)
    elif data == "owner_recovery_other_execute":
        bbs_thread_id = handler.bbs_thread_id
        await recovery_other_execute(query, db, admin_id, context, target_chat_id, bbs_thread_id)

    # ── Старая panel_* система (маршрутизация через panel_callback) ──
    elif data.startswith("panel_"):
        from handlers.admin_moderation import panel_callback
        class _FakeUpdate:
            callback_query = query
        await panel_callback(_FakeUpdate(), context)

    # ── Журнал ──
    elif data == "owner_journal":
        await show_journal_menu(query, db, admin_id)
    elif data == "journal_connect":
        await journal_connect_start(query, context, db, admin_id)
    elif data == "journal_disconnect":
        await journal_disconnect(query, db, admin_id)
    elif data == "journal_test":
        await journal_test(query, context, db, admin_id)

    else:
        return False
    return True
