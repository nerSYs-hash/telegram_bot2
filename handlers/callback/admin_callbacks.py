#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Callback-ы админа: банк, статистика, пресс-релизы, гороскоп, экспорт."""

import logging
from handlers.bank_handlers import (
    show_bank, show_bank_menu,
    show_exchange_rate,
)
from handlers.Stats.stats_controller import (
    show_stats_menu,
    show_stats_period_menu,
    handle_stats_callback,
    handle_stats_export,
    generate_export_file
)
from handlers.pr_handlers import (
    show_settings, start_press_release, handle_pr_target_selection,
    handle_pr_publish_now, handle_pr_schedule, show_scheduled_posts,
    handle_pr_delete, handle_pr_cancel,
    handle_pr_edit, handle_pr_edit_text, handle_pr_edit_photo,
    handle_pr_edit_remove_photo, handle_pr_edit_media_done,
    handle_pr_edit_time, handle_pr_edit_target,
    handle_pr_retarget, handle_pr_add_photo, handle_pr_remove_photo,
    handle_pr_media_done, handle_pr_full_preview,
    show_features_management, toggle_feature, handle_pr_edit_publish_now,
    handle_pr_refresh_topics,
)
from handlers.horoscope_handler import (
    show_horoscope_menu, publish_horoscope_today,
    preview_horoscope, diagnose_emoji,
    show_horoscope_schedule_menu, toggle_horoscope_schedule,
    toggle_horoscope_mode, show_horoscope_thread_picker,
    handle_horoscope_sched_thread, prompt_horoscope_schedule_time,
)

logger = logging.getLogger(__name__)


async def dispatch_admin(handler, query, data, user, context) -> bool:
    """Обрабатывает админские callback-ы. True если обработано."""
    db = handler.db
    admin_id = handler.main_admin_id
    target_chat_id = handler.target_chat_id

    # Эффективный admin_id для проверок уровня владельца: зам получает свой user.id
    _u_caller = db.get_user(user.id)
    _is_owner_caller = user.id == admin_id or (_u_caller and _u_caller['is_owner'])
    eff_admin = user.id if _is_owner_caller else admin_id

    # ── Модерация заявок (adm_app_, adm_rej_, adm_skip_) и новые заявки ──
    if data == "new_app":
        from handlers.admin_moderation import new_application_callback

        class _FakeUpdateNew:
            callback_query = query
            effective_user = query.from_user

        await new_application_callback(_FakeUpdateNew(), context)
        return True

    if data.startswith("adm_app_") or data.startswith("adm_rej_") or data.startswith("adm_skip_"):
        from handlers.admin_moderation import admin_moderation_callback

        class _FakeUpdate:
            callback_query = query
            effective_user = query.from_user

        await admin_moderation_callback(_FakeUpdate(), context)
        return True

    # ── Банк ──
    if data == "menu_bank":
        await show_bank_menu(query, user, db, eff_admin)
    elif data == "bank_panel":
        await show_bank(query, user, db, eff_admin)
    elif data == "bank_refresh":
        await show_bank(query, user, db, eff_admin)
    elif data == "show_exchange_rate":
        await show_exchange_rate(query, user, db)

    # ── Статистика ──
    elif data == "menu_stats":
        _u = db.get_user(user.id)
        _is_staff = user.id == admin_id or (_u and (_u['is_admin'] or _u['is_owner']))
        if _is_staff:
            await show_stats_menu(query, user, user.id)
        else:
            await query.answer("⛔ Нет доступа.", show_alert=True)
    elif data.startswith("stats_"):
        _u = db.get_user(user.id)
        _is_staff = user.id == admin_id or (_u and (_u['is_admin'] or _u['is_owner']))
        _eff_id = user.id if _is_staff else admin_id
        if data.startswith("stats_type_"):
            await show_stats_period_menu(query, data, user, _eff_id)
        elif data.startswith("stats_export_"):
            await handle_stats_export(query, data, user, context, _eff_id)
        else:
            await handle_stats_callback(query, data, user, context, db, _eff_id, target_chat_id)

    # ── Экспорт файлов ──
    elif data.startswith("export_"):
        await generate_export_file(query, data, user, context, db, eff_admin, target_chat_id)

    # ── Пресс-релиз ──
    elif data == "menu_settings":
        await handler.show_main_menu(query, user)
    elif data == "press_release_start":
        await start_press_release(query, user, context, db, eff_admin)
    elif data == "pr_migration_info":
        from handlers.PR.press_release_pr import show_migration_info
        await show_migration_info(query, user, context, db, eff_admin)
    elif data.startswith("pr_target_"):
        await handle_pr_target_selection(query, data, user, context, db, eff_admin, target_chat_id)
    elif data == "pr_publish_now":
        await handle_pr_publish_now(query, user, context, db, eff_admin, target_chat_id)
    elif data == "pr_schedule":
        await handle_pr_schedule(query, user, context, db, eff_admin)
    elif data == "pr_scheduled_list":
        await show_scheduled_posts(query, user, context, db, eff_admin)
    elif data.startswith("pr_delete_"):
        await handle_pr_delete(query, data, user, db, eff_admin)
    elif data == "pr_full_preview":
        await handle_pr_full_preview(query, user, context, db, eff_admin)
    elif data == "pr_cancel":
        await handle_pr_cancel(query, user, context, db, eff_admin)
    elif data == "pr_refresh_topics":
        await handle_pr_refresh_topics(query, user, context, db, eff_admin, target_chat_id)
    elif data == "pr_add_photo":
        await handle_pr_add_photo(query, user, context, db, eff_admin)
    elif data == "pr_remove_photo":
        await handle_pr_remove_photo(query, user, context, db, eff_admin)
    elif data == "pr_media_done":
        await handle_pr_media_done(query, user, context, db, eff_admin, target_chat_id)
    elif data.startswith("pr_edit_media_done_"):
        await handle_pr_edit_media_done(query, data, user, context, db, eff_admin, target_chat_id)
    elif data.startswith("pr_edit_text_"):
        await handle_pr_edit_text(query, data, user, context, db, eff_admin)
    elif data.startswith("pr_edit_photo_"):
        await handle_pr_edit_photo(query, data, user, context, db, eff_admin)
    elif data.startswith("pr_edit_remove_photo_"):
        await handle_pr_edit_remove_photo(query, data, user, db, eff_admin)
    elif data.startswith("pr_edit_time_"):
        await handle_pr_edit_time(query, data, user, context, db, eff_admin)
    elif data.startswith("pr_edit_target_"):
        await handle_pr_edit_target(query, data, user, context, db, eff_admin, target_chat_id)
    elif data.startswith("pr_edit_publishnow_"):
        await handle_pr_edit_publish_now(query, data, user, context, db, eff_admin, target_chat_id)
    elif data.startswith("pr_edit_"):
        await handle_pr_edit(query, data, user, db, eff_admin)
    elif data.startswith("pr_retarget_"):
        await handle_pr_retarget(query, data, user, context, db, eff_admin, target_chat_id)

    # ── Управление фичами ──
    elif data == "manage_features":
        await show_features_management(query, user, db, eff_admin)
    elif data.startswith("feature_on_") or data.startswith("feature_off_"):
        await toggle_feature(query, data, user, db, eff_admin)
    elif data == "feature_info":
        await query.answer("ℹ️ Нажмите переключатель справа", show_alert=False)

    # ── Гороскоп ──
    elif data == "horoscope_menu":
        await show_horoscope_menu(query, user, db, eff_admin)
    elif data == "horoscope_publish":
        await publish_horoscope_today(query, user, context, db, eff_admin, target_chat_id)
    elif data == "horoscope_preview":
        await preview_horoscope(query, user, db, eff_admin)
    elif data == "horoscope_diagnose":
        await diagnose_emoji(query, user, db, eff_admin)

    # ── Расписание гороскопа ──
    elif data == "horoscope_sched_menu":
        await show_horoscope_schedule_menu(query, user, db, eff_admin, target_chat_id)
    elif data == "horoscope_sched_toggle":
        await toggle_horoscope_schedule(query, user, db, eff_admin, target_chat_id)
    elif data == "horoscope_sched_toggle_mode":
        await toggle_horoscope_mode(query, user, db, eff_admin, target_chat_id)
    elif data == "horoscope_sched_thread_pick":
        await show_horoscope_thread_picker(query, user, context, db, eff_admin, target_chat_id)
    elif data == "horoscope_sched_set_time":
        await prompt_horoscope_schedule_time(query, user, context, db, eff_admin)
    elif data.startswith("horoscope_sched_thread_"):
        await handle_horoscope_sched_thread(query, data, user, db, eff_admin, target_chat_id)

    else:
        return False
    return True
