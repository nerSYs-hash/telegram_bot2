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
from handlers.placeholder_handlers import (
    show_placeholder_menu,
    handle_placeholder_callback,
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
from handlers.owner_handlers import show_owner_dashboard
from handlers.moderation import handle_restrict_callback
from handlers.triggers_handlers import show_triggers_menu, handle_trigger_callback
from handlers.journal_handlers import (
    show_journal_menu, show_journal_channel_menu,
    journal_connect_start, journal_thread_start,
    journal_disconnect, journal_test,
    log_kick, log_ban, log_unban, log_unmute, log_mute,
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
    # Старый «Пульт Владельца» отключён — оба алиаса ведут на новую Панель Владельца.
    if data in ("owner_dashboard", "panel_main"):
        from handlers.admin_moderation import send_admin_panel
        await send_admin_panel(context.bot, query.message.chat.id, is_owner=True)
        try:
            await query.message.delete()
        except Exception:
            pass
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

    # ── Плейсхолдеры ──
    elif data.startswith("ph_"):
        await handle_placeholder_callback(query, data, context, db, admin_id)

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

    # ── Журнал: действия из записи (jban/jkick/jmute) ──
    elif data.startswith("jremute_"):
        uid = int(data.split("_", 1)[1])
        from telegram import ChatPermissions
        try:
            await context.bot.restrict_chat_member(
                chat_id=target_chat_id,
                user_id=uid,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
            await query.answer("✅ Ограничения сняты.", show_alert=True)
            try:
                chat_obj = await context.bot.get_chat(target_chat_id)
                await log_unmute(
                    context.bot, db,
                    target_id=uid,
                    admin_id=user.id,
                    chat=chat_obj,
                    admin_user=user,
                )
            except Exception as je:
                logger.error(f"Journal log_unmute error: {je}")
        except Exception as e:
            await query.answer(f"❌ {e}", show_alert=True)

    elif data.startswith("junban_"):
        uid = int(data.split("_", 1)[1])
        try:
            await context.bot.unban_chat_member(
                chat_id=target_chat_id,
                user_id=uid,
                only_if_banned=True,
            )
            await query.answer("✅ Пользователь разбанен.", show_alert=True)
            try:
                chat_obj = await context.bot.get_chat(target_chat_id)
                await log_unban(
                    context.bot, db,
                    target_id=uid,
                    admin_id=user.id,
                    chat=chat_obj,
                    admin_user=user,
                )
            except Exception as je:
                logger.error(f"Journal log_unban error: {je}")
        except Exception as e:
            await query.answer(f"❌ {e}", show_alert=True)

    elif data.startswith("jban_"):
        uid = int(data.split("_", 1)[1])
        try:
            await context.bot.ban_chat_member(chat_id=target_chat_id, user_id=uid)
            await query.answer("✅ Пользователь забанен.", show_alert=True)
            try:
                chat_obj = await context.bot.get_chat(target_chat_id)
                await log_ban(
                    context.bot, db,
                    target_id=uid,
                    admin_id=user.id,
                    chat=chat_obj,
                    admin_user=user,
                )
            except Exception as je:
                logger.error(f"Journal log_ban error: {je}")
        except Exception as e:
            await query.answer(f"❌ {e}", show_alert=True)

    elif data.startswith("jkick_"):
        uid = int(data.split("_", 1)[1])
        try:
            await context.bot.ban_chat_member(chat_id=target_chat_id, user_id=uid)
            await context.bot.unban_chat_member(chat_id=target_chat_id, user_id=uid, only_if_banned=True)
            await query.answer("✅ Пользователь удалён из чата.", show_alert=True)
            try:
                chat_obj = await context.bot.get_chat(target_chat_id)
                await log_kick(
                    context.bot, db,
                    target_id=uid,
                    admin_id=user.id,
                    chat_id=target_chat_id,
                    chat_title=chat_obj.title,
                    admin_user=user,
                )
            except Exception as je:
                logger.error(f"Journal log_kick error: {je}")
        except Exception as e:
            await query.answer(f"❌ {e}", show_alert=True)

    elif data.startswith("jmute_"):
        uid = int(data.split("_", 1)[1])
        from telegram import ChatPermissions
        try:
            await context.bot.restrict_chat_member(
                chat_id=target_chat_id,
                user_id=uid,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_audios=False,
                    can_send_documents=False,
                    can_send_photos=False,
                    can_send_videos=False,
                    can_send_video_notes=False,
                    can_send_voice_notes=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                ),
            )
            await query.answer("✅ Пользователь заглушён навсегда.", show_alert=True)
            try:
                chat_obj = await context.bot.get_chat(target_chat_id)
                await log_mute(
                    context.bot, db,
                    target_id=uid,
                    admin_id=user.id,
                    duration_human="навсегда",
                    chat=chat_obj,
                    admin_user=user,
                )
            except Exception as je:
                logger.error(f"Journal log_mute error: {je}")
        except Exception as e:
            await query.answer(f"❌ {e}", show_alert=True)

    # ── Журнал ──
    elif data == "owner_journal":
        await show_journal_menu(query, db, admin_id)
    # Обратная совместимость (старый journal_connect → канал 1)
    elif data == "journal_connect":
        await journal_connect_start(query, context, db, admin_id, num=1)
    elif data == "journal_disconnect":
        await journal_disconnect(query, db, admin_id, num=1)
    elif data == "journal_test":
        await journal_test(query, context, db, admin_id, num=1)
    # Sub-меню каналов
    elif data in ("journal_ch1_menu", "journal_ch2_menu", "journal_ch3_menu"):
        num = int(data[10])  # "journal_chN_menu"
        await show_journal_channel_menu(query, db, admin_id, num)
    elif data in ("journal_ch1_connect", "journal_ch2_connect", "journal_ch3_connect"):
        num = int(data[10])
        await journal_connect_start(query, context, db, admin_id, num=num)
    elif data in ("journal_ch2_thread", "journal_ch3_thread"):
        num = int(data[10])
        await journal_thread_start(query, context, db, admin_id, num=num)
    elif data in ("journal_ch1_disconnect", "journal_ch2_disconnect", "journal_ch3_disconnect"):
        num = int(data[10])
        await journal_disconnect(query, db, admin_id, num=num)
    elif data in ("journal_ch1_test", "journal_ch2_test", "journal_ch3_test"):
        num = int(data[10])
        await journal_test(query, context, db, admin_id, num=num)

    else:
        return False
    return True
