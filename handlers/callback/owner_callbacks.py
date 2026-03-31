#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Callback-ы Пульта Владельца: дашборд, персонал, модерация, триггеры, журнал, система."""

import logging
from handlers.owner_handlers import (
    show_owner_dashboard,
    show_staff_menu, staff_add_start, staff_remove_start,
    show_economy_menu, emit_start, wipe_confirm_step1, wipe_execute,
    show_moderation_menu, bl_add_start, bl_remove_start,
    mute_start, unmute_start,
    show_system_menu, toggle_maintenance,
    send_database_backup,
    show_statistics_not_in_chat,
    show_recovery_menu, restore_bbs_confirm, restore_bbs_execute,
    restore_news_confirm, restore_news_execute,
    compensate_bbs_start, compensate_bbs_confirm,
)
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

    # ── Закрыть панель ──
    if data == "owner_close":
        try:
            await query.message.delete()
        except Exception:
            await query.answer("Закрыто.", show_alert=False)
        return True

    # ── Дашборд ──
    if data in ("owner_dashboard", "panel_main"):
        await show_owner_dashboard(query, context, db, admin_id)
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

    # ── Старая panel_* система (маршрутизация через panel_callback) ──
    elif data.startswith("panel_"):
        from handlers.admin_moderation import panel_callback
        class _FakeUpdate:
            callback_query = query
        await panel_callback(_FakeUpdate(), context)

    # ── Восстановление веток ──
    elif data == "owner_recovery_menu":
        await show_recovery_menu(query, db, admin_id)
    elif data == "owner_restore_bbs":
        await restore_bbs_confirm(query, db, admin_id)
    elif data == "owner_restore_bbs_confirm":
        await restore_bbs_execute(query, context, db, admin_id)
    elif data == "owner_restore_news":
        await restore_news_confirm(query, db, admin_id)
    elif data == "owner_restore_news_confirm":
        await restore_news_execute(query, context, db, admin_id)
    elif data == "owner_compensate_bbs":
        await compensate_bbs_start(query, context, db, admin_id)
    elif data == "confirm_compensate_bbs":
        await compensate_bbs_confirm(query, context, db, admin_id)

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
