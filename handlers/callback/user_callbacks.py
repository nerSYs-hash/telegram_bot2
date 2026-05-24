#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пользовательские callback-ы: меню, профиль, баланс, рефералы, начисления, детализация, FAQ, топы, exit survey."""

import logging
from handlers.profile_handlers import show_profile, show_profile_settings, toggle_profile_setting
from handlers.Stats.stats_tops import (
    show_top, 
    show_top5_menu, 
    show_top5_activists, 
    show_top5_rich
)
from handlers.exit_survey_handlers import (
    handle_exit_reason, handle_exit_skip_reason,
    handle_exit_love_place,
    handle_exit_improvement,
    handle_exit_event,
    handle_exitq4_skip,
    handle_exit_final,
    show_survey_results,
)
from config.emojis import ICON_ALARM_STRONG

logger = logging.getLogger(__name__)


async def dispatch_user(handler, query, data, user, context) -> bool:
    """Обрабатывает пользовательские callback-ы. True если обработано."""
    db = handler.db
    admin_id = handler.main_admin_id

    if data == "back_to_menu":
        await handler.show_main_menu(query, user)
    elif data == "menu_balance":
        await handler.show_balance(query, user)
    elif data == "menu_top":
        await show_top(query, db, handler.target_chat_id, context)
    elif data == "menu_profile":
        if not db.is_feature_enabled('profile'):
            await query.answer("👤 Профиль отключён.", show_alert=True)
            return True
        await show_profile(query, context, db, user.id)
    elif data == "profile_settings":
        await show_profile_settings(query, user, db)
    elif data == "form_settings_menu":
        from handlers.placeholder_handlers import show_form_settings
        await show_form_settings(query, db, user.id, edit=True)
    elif data.startswith("prof_notif_") or data.startswith("prof_age_"):
        await toggle_profile_setting(query, user, data, db)
    elif data in ("stub_quests", "stub_market", "stub_settings"):
        await query.answer(f"{ICON_ALARM_STRONG} В разработке!", show_alert=True)
    elif data == "menu_activities":
        await handler.show_activities_menu(query, user)
    elif data == "faq_menu":
        from handlers.commands.system_commands import _show_faq_menu
        await _show_faq_menu(query.message)
    elif data == "faq_commands":
        from handlers.commands.system_commands import faq_commands_user_text, FAQ_COMMANDS_ADMIN
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        text = faq_commands_user_text()
        if user.id == admin_id:
            text += FAQ_COMMANDS_ADMIN
        await query.edit_message_text(text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="faq_back")]]))
    elif data == "faq_functions":
        from handlers.commands.system_commands import show_faq_functions
        await show_faq_functions(query, db)
    elif data.startswith("faq_feat_"):
        from handlers.commands.system_commands import FAQ_FEATURES
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        feat_id = data.replace("faq_feat_", "")
        feat = FAQ_FEATURES.get(feat_id)
        if feat:
            await query.edit_message_text(feat['text'], parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку", callback_data="faq_functions")]]))
        else:
            await query.answer("Функция не найдена", show_alert=True)
    elif data == "faq_back":
        from handlers.commands.system_commands import _show_faq_menu
        try: await query.message.delete()
        except: pass
        await _show_faq_menu(query.message)
    elif data == "menu_top5":
        await show_top5_menu(query, user)
    elif data == "top5_activists":
        await show_top5_activists(query, user, db, context)
    elif data == "top5_rich":
        await show_top5_rich(query, user, db, context)
    elif data == "menu_referral":
        await handler.show_referral(query, user, context)
    elif data == "referral_refresh":
        await handler.refresh_referral_link(query, user, context)
        await handler.show_referral(query, user, context)
    elif data == "my_accruals":
        await handler.show_accruals_periods(query, user)
    elif data.startswith("accruals_"):
        await handler.show_accruals(query, data, user)
    elif data == "my_detalization":
        await handler.show_detalization_periods(query, user)
    elif data.startswith("detail_export_"):
        await handler.export_user_detalization(query, data, user, context)
    # ── Exit Survey ──
    elif data.startswith("exit_skip_reason_"):
        await handle_exit_skip_reason(query, data, context, db)
    elif data.startswith("exit_"):
        await handle_exit_reason(query, data, context, db, admin_id)
    elif data.startswith("exitlove_"):
        await handle_exit_love_place(query, data, context, db)
    elif data.startswith("exitimp_"):
        await handle_exit_improvement(query, data, context, db)
    elif data.startswith("exitev_"):
        await handle_exit_event(query, data, context, db)
    elif data.startswith("exitq4_skip_"):
        await handle_exitq4_skip(query, data, context, db)
    elif data.startswith("exitfinal_"):
        await handle_exit_final(query, data, context, db)
    elif data == "owner_survey_results":
        await show_survey_results(query, db, admin_id)
    else:
        return False
    return True


async def handle_report_callback(handler, query, context, data, user):
    await handler._handle_report_callback(query, context, data, user)

async def show_report_menu(handler, query, context, data, user):
    await handler._show_report_menu(query, context, data, user)
