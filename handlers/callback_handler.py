#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import format_number, generate_referral_link, get_moscow_time, get_today_date_msk
from datetime import datetime, timedelta
from handlers.lottery_handlers import LotteryHandler
from handlers.bingo_handlers import BingoHandler
from handlers.profile_handlers import show_profile, show_profile_settings, toggle_profile_setting
from handlers.gift_handlers import GiftHandler
from handlers.stats_handlers import (
    generate_export_file, show_top, show_top5_menu,
    show_top5_activists, show_top5_rich,
    handle_stats_callback, handle_exit_interview,
    handle_stats_export, show_stats_menu, show_stats_period_menu,
)
from handlers.donate_handlers import (
    safe_name, show_donate_menu, donate_to_user_start, donate_pick_user,
    donate_user_amount, donate_user_custom, donate_user_confirm,
    donate_to_bank_start, donate_bank_custom, donate_bank_amount,
    donate_bank_confirm, donate_to_reactor_start, donate_reactor_custom,
    donate_reactor_amount, donate_reactor_confirm, donate_show_history,
)
from handlers.pr_handlers import (
    show_settings, start_press_release, handle_pr_target_selection,
    handle_pr_publish_now, handle_pr_schedule, show_scheduled_posts,
    handle_pr_delete, handle_pr_cancel,
    handle_pr_edit, handle_pr_edit_text, handle_pr_edit_photo,
    handle_pr_edit_remove_photo, handle_pr_edit_time, handle_pr_edit_target,
    handle_pr_retarget,
    handle_pr_add_photo, handle_pr_remove_photo,
    show_features_management, toggle_feature, handle_pr_edit_publish_now,
    handle_pr_refresh_topics,
)
from handlers.bank_handlers import (
    show_bank, show_bank_menu, adjust_difficulty, start_set_exchange_rate,
    show_exchange_rate, start_bank_transfer,
    select_transfer_amount, execute_bank_transfer,
)
from handlers.horoscope_handler import (
    show_horoscope_menu, publish_horoscope_today, preview_horoscope,
    diagnose_emoji,
)
from handlers.bbs_handlers import handle_bbs_callback
from handlers.reactor_handlers import (
    show_reactor_menu, handle_reactor_donate_fixed,
    handle_reactor_donate_custom_start, handle_reactor_feature,
    show_reactor_admin, reactor_admin_reset, reactor_admin_set_target,
    reactor_admin_set_status, reactor_admin_custom_target_start,
    ensure_reactor_tables,
)

class CallbackHandler:
    def __init__(self, db, target_chat_id, main_admin_id, bot_username):
        self.db = db
        self.target_chat_id = target_chat_id
        self.main_admin_id = main_admin_id
        self.bot_username = bot_username
        self.bbs_thread_id = int(os.getenv('BBS_THREAD_ID', 0))
        self.lottery_handler = LotteryHandler(db, target_chat_id, main_admin_id, bot_username)
        self.bingo_handler = BingoHandler(db, target_chat_id, main_admin_id, bot_username)
        self.gift_handler = GiftHandler(db, target_chat_id, main_admin_id)
        
        # Инициализация таблиц Реактора
        ensure_reactor_tables(db)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries"""
        query = update.callback_query
        
        data = query.data
        user = query.from_user
        
        # Эти callback-и отвечают САМИ через query.answer(show_alert=True),
        # поэтому НЕ вызываем query.answer() заранее.
        _self_answer = ("buy_ticket_", "my_tickets_", "lott_", "bcard_", "bbingo_")
        if not any(data.startswith(p) for p in _self_answer):
            await query.answer()
        
        # ═══ PRIVATE-ONLY для обычных пользователей ═══
        # Исключения: bbs_report_ (жалоба из группы), owner — без ограничений
        is_owner = user.id == self.main_admin_id
        _group_allowed = ("bbs_report_",)
        if not is_owner and query.message.chat.type != 'private':
            if not any(data.startswith(p) for p in _group_allowed):
                bot_me = await context.bot.get_me()
                try:
                    await query.edit_message_text(
                        "📋 Все функции бота доступны только в личных сообщениях.\n"
                        f"👉 Перейдите в ЛС: @{bot_me.username}",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("💬 Перейти в ЛС", url=f"https://t.me/{bot_me.username}")]
                        ])
                    )
                except Exception:
                    pass
                return
        
        # ═══ BBS CALLBACKS ═══
        if data.startswith('bbs_') or data == 'menu_bbs':
            # Проверка: фича BBS включена?
            if not self.db.is_feature_enabled('bbs'):
                await query.answer("📋 Pulse BBS временно отключена.", show_alert=True)
                return

            # ── Жалоба на анкету — работает ИЗ ГРУППЫ ──
            if data.startswith('bbs_report_'):
                reported_user_id = data.replace('bbs_report_', '')
                reporter = query.from_user
                msg = query.message
                # Формируем ссылку на сообщение
                chat_id = msg.chat.id
                msg_id = msg.message_id
                # Для супергрупп: -100XXXXXXXXXX → XXXXXXXXXX
                chat_id_short = str(chat_id).replace('-100', '')
                msg_link = f"https://t.me/c/{chat_id_short}/{msg_id}"
                # Отправляем жалобу админу
                try:
                    report_text = (
                        f"⚠️ <b>Жалоба на анкету BBS</b>\n\n"
                        f"👤 Пожаловался: @{reporter.username or reporter.first_name} "
                        f"(id: {reporter.id})\n"
                        f"📋 Анкета пользователя: <code>{reported_user_id}</code>\n"
                        f"🔗 <a href='{msg_link}'>Перейти к посту</a>"
                    )
                    await context.bot.send_message(
                        chat_id=self.main_admin_id,
                        text=report_text,
                        parse_mode='HTML',
                        disable_web_page_preview=True,
                    )
                    await query.answer("✅ Жалоба отправлена администратору!", show_alert=True)
                except Exception as e:
                    import logging
                    logging.error(f"BBS report error: {e}")
                    await query.answer("❌ Не удалось отправить жалобу.", show_alert=True)
                return

            # BBS работает ТОЛЬКО в личных сообщениях
            if query.message.chat.type != 'private':
                bot_me = await context.bot.get_me()
                await query.answer()
                await query.edit_message_text(
                    "📋 <b>Pulse BBS</b>\n\n"
                    "Работа с анкетами доступна только в личных сообщениях с ботом.\n"
                    "Нажмите кнопку ниже 👇",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💬 Перейти в ЛС", url=f"https://t.me/{bot_me.username}?start=bbs")],
                        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")],
                    ])
                )
                return
            handled = await handle_bbs_callback(
                query, context, self.db, self.target_chat_id, self.bbs_thread_id
            )
            if handled:
                return
        
        # Back to main menu
        if data == "back_to_menu":
            await self.show_main_menu(query, user)
        
        # Menu callbacks
        elif data == "menu_balance":
            await self.show_balance(query, user)
        elif data == "menu_top":
            await show_top(query, self.db, self.target_chat_id, context)
        elif data == "menu_bank":
            await show_bank_menu(query, user, self.db, self.main_admin_id)
        elif data == "bank_panel":
            await show_bank(query, user, self.db, self.main_admin_id)
        elif data == "menu_stats":
            await show_stats_menu(query, user, self.main_admin_id)
        elif data == "menu_settings":
            await self.show_main_menu(query, user)
        elif data == "owner_backup":
            from handlers.owner_handlers import send_database_backup
            await send_database_backup(query, user, self.db, self.main_admin_id, context)    
        elif data == "menu_lottery":
            await self.lottery_handler.show_lottery_menu(query, user)
        elif data == "menu_bingo":
            await self.bingo_handler.show_bingo_menu(query, user)
        elif data == "menu_monthly_gift":
            await self.gift_handler.show_monthly_gift_menu(query, user, context)
        elif data == "menu_referral":
            await self.show_referral(query, user, context)
        elif data == "referral_refresh":
            await self.refresh_referral_link(query, user, context)
        # Menu callbacks
        elif data == "menu_profile":
            try:
                await show_profile(query, context, self.db, user.id)
            except Exception as e:
                logging.error(f"[menu_profile] Ошибка: {e}", exc_info=True)
                try:
                    await query.answer(f"❌ Ошибка профиля: {e}", show_alert=True)
                except:
                    pass
        elif data == "profile_settings":
            await show_profile_settings(query, user, self.db)
        elif data.startswith("prof_notif_") or data.startswith("prof_age_"):
            await toggle_profile_setting(query, data, user, self.db)
            
        # Заглушки для профиля
        elif data in ["stub_quests", "stub_market", "stub_settings"]:
            await query.answer("🚧 Этот раздел находится в разработке! Следите за обновлениями.", show_alert=True)
        
        # Activities menu callback
        elif data == "menu_activities":
            await self.show_activities_menu(query, user)
        
        # FAQ callbacks
        elif data == "faq_commands":
            from handlers.commands.system_commands import FAQ_COMMANDS_USER, FAQ_COMMANDS_ADMIN
            text = FAQ_COMMANDS_USER
            if user.id == self.main_admin_id:
                text += FAQ_COMMANDS_ADMIN
            kb = [
                [InlineKeyboardButton("🔙 Назад к FAQ", callback_data="faq_back")],
            ]
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))
        elif data == "faq_functions":
            from handlers.commands.system_commands import FAQ_FUNCTIONS
            kb = [
                [InlineKeyboardButton("🔙 Назад к FAQ", callback_data="faq_back")],
            ]
            await query.edit_message_text(FAQ_FUNCTIONS, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))
        elif data == "faq_back":
            text = "❓ FAQ / ПОМОЩЬ\n\nВыберите раздел:"
            kb = [
                [InlineKeyboardButton("📚 Команды и их описание", callback_data="faq_commands")],
                [InlineKeyboardButton("📖 Описание функций", callback_data="faq_functions")],
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        
        # TOP-5 menu callbacks
        elif data == "menu_top5":
            await show_top5_menu(query, user)
        elif data == "top5_activists":
            await show_top5_activists(query, user, self.db, context)
        elif data == "top5_rich":
            await show_top5_rich(query, user, self.db, context)
        
        # Stats callbacks
        elif data.startswith("stats_"):
            if data.startswith("stats_type_"):
                await show_stats_period_menu(query, data, user, self.main_admin_id)
            elif data.startswith("stats_export_"):
                await handle_stats_export(query, data, user, context, self.main_admin_id)
            else:
                await handle_stats_callback(query, data, user, context, self.db, self.main_admin_id, self.target_chat_id)
        
        # Exit interview callbacks
        elif data.startswith("exit_"):
            await handle_exit_interview(query, data, context, self.db)
        
        # Bank callbacks
        elif data == "bank_k_up":
            await adjust_difficulty(query, user, 'up', self.db, self.main_admin_id)
        elif data == "bank_k_down":
            await adjust_difficulty(query, user, 'down', self.db, self.main_admin_id)
        elif data == "bank_refresh":
            await show_bank(query, user, self.db, self.main_admin_id)
        
        # Lottery callbacks — ПОЛЬЗОВАТЕЛЬСКИЕ (покупка, мои билеты)
        elif data.startswith("buy_ticket_"):
            await self.lottery_handler.handle_buy_ticket(query, data, user, context)
        elif data.startswith("my_tickets_"):
            await self.lottery_handler.handle_my_tickets(query, data, user, context)
        
        # Lottery — виджет +/− в ЛС (единый обработчик lott_*)
        elif data.startswith("lott_"):
            await self.lottery_handler.handle_lott_callback(query, data, user, context)    
        
        # Lottery callbacks — АДМИНСКИЕ (создание, список, розыгрыш)
        elif data.startswith("lottery_"):
            await self.lottery_handler.handle_lottery_callback(query, data, user, context)
        
        # ═══ BINGO CALLBACKS ═══
        elif data.startswith("bingo_"):
            await self.bingo_handler.handle_bingo_callback(query, data, user, context)
        elif data.startswith("bcard_"):
            await self.bingo_handler.handle_card_callback(query, data, user, context)
        elif data.startswith("bbingo_"):
            await self.bingo_handler.handle_bingo_claim(query, data, user, context)
        
        # Press release callbacks
        elif data == "press_release_start":
            await start_press_release(query, user, context, self.db, self.main_admin_id)
        elif data.startswith("pr_target_"):
            await handle_pr_target_selection(query, data, user, context, self.db, self.main_admin_id, self.target_chat_id)
        elif data == "pr_publish_now":
            await handle_pr_publish_now(query, user, context, self.db, self.main_admin_id, self.target_chat_id)
        elif data == "pr_schedule":
            await handle_pr_schedule(query, user, context, self.db, self.main_admin_id)
        elif data == "pr_scheduled_list":
            await show_scheduled_posts(query, user, context, self.db, self.main_admin_id, self.target_chat_id)
        elif data.startswith("pr_delete_"):
            await handle_pr_delete(query, data, user, context, self.db, self.main_admin_id, self.target_chat_id)
        elif data == "pr_cancel":
            await handle_pr_cancel(query, user, context, self.db, self.main_admin_id)
        elif data == "pr_refresh_topics":
            await handle_pr_refresh_topics(query, user, context, self.db, self.main_admin_id, self.target_chat_id)
        
        # Press release: add/remove photo
        elif data == "pr_add_photo":
            await handle_pr_add_photo(query, user, context, self.db, self.main_admin_id)
        elif data == "pr_remove_photo":
            await handle_pr_remove_photo(query, user, context, self.db, self.main_admin_id)
        
        # Press release: edit scheduled posts
        elif data.startswith("pr_edit_text_"):
            await handle_pr_edit_text(query, data, user, context, self.db, self.main_admin_id)
        elif data.startswith("pr_edit_photo_"):
            await handle_pr_edit_photo(query, data, user, context, self.db, self.main_admin_id)
        elif data.startswith("pr_edit_remove_photo_"):
            await handle_pr_edit_remove_photo(query, data, user, context, self.db, self.main_admin_id, self.target_chat_id)
        elif data.startswith("pr_edit_time_"):
            await handle_pr_edit_time(query, data, user, context, self.db, self.main_admin_id)
        elif data.startswith("pr_edit_target_"):
            await handle_pr_edit_target(query, data, user, context, self.db, self.main_admin_id, self.target_chat_id)
        elif data.startswith("pr_edit_publishnow_"):
            await handle_pr_edit_publish_now(query, data, user, context, self.db, self.main_admin_id, self.target_chat_id)
        elif data.startswith("pr_edit_"):
            await handle_pr_edit(query, data, user, context, self.db, self.main_admin_id, self.target_chat_id)
        
        # Press release: retarget (change thread of existing post)
        elif data.startswith("pr_retarget_"):
            await handle_pr_retarget(query, data, user, context, self.db, self.main_admin_id, self.target_chat_id)
        
        # Features management callbacks
        elif data == "manage_features":
            await show_features_management(query, user, self.db, self.main_admin_id)
        elif data.startswith("feature_on_") or data.startswith("feature_off_"):
            await toggle_feature(query, data, user, self.db, self.main_admin_id)
        elif data == "feature_info":
            # Just a label, do nothing
            await query.answer()
        
        # Horoscope callbacks
        elif data == "horoscope_menu":
            await show_horoscope_menu(query, user, self.db, self.main_admin_id)
        elif data == "horoscope_publish":
            await publish_horoscope_today(query, user, context, self.db, self.main_admin_id, self.target_chat_id)
        elif data == "horoscope_preview":
            await preview_horoscope(query, user, context, self.db, self.main_admin_id)
        elif data == "horoscope_diagnose":
            await diagnose_emoji(query, user, context, self.db, self.main_admin_id)
        
        # Exchange rate callbacks
        elif data == "set_exchange_rate":
            await start_set_exchange_rate(query, user, context, self.db, self.main_admin_id)
        elif data == "show_exchange_rate":
            await show_exchange_rate(query, user, self.db)
        
        # Monthly gift callbacks — OWNER
        elif data == "monthly_gift_draw":
            await self.gift_handler.handle_monthly_gift_draw(query, user, context)
        elif data == "monthly_gift_toggle":
            await self.gift_handler.handle_monthly_gift_toggle(query, user)
        elif data == "monthly_gift_history":
            await self.gift_handler.show_monthly_gift_history(query, user)
        elif data == "monthly_gift_create":
            await self.gift_handler.monthly_gift_create_start(query, user, context)
        elif data.startswith("mgift_set_amount_"):
            await self.gift_handler.monthly_gift_set_amount(query, data, user, context)
        elif data.startswith("mgift_set_type_"):
            await self.gift_handler.monthly_gift_set_type(query, data, user, context)
        elif data.startswith("mgift_set_condition_"):
            await self.gift_handler.monthly_gift_set_condition(query, data, user, context)
        elif data.startswith("mgift_set_minmsg_"):
            await self.gift_handler.monthly_gift_set_min_messages(query, data, user, context)
        elif data == "monthly_gift_participants":
            await self.gift_handler.show_monthly_gift_participants(query, user)
        elif data == "monthly_gift_announce":
            await self.gift_handler.monthly_gift_announce(query, user, context)
        elif data == "monthly_gift_confirm_draw":
            await self.gift_handler.monthly_gift_confirm_draw(query, user, context)
        
        # Monthly gift callbacks — USER
        elif data == "monthly_gift_user_view":
            await self.gift_handler.show_monthly_gift_user(query, user)
        elif data == "monthly_gift_participate":
            await self.gift_handler.monthly_gift_participate(query, user)
        elif data == "monthly_gift_my_progress":
            await self.gift_handler.monthly_gift_my_progress(query, user)
        elif data == "monthly_gift_winners":
            await self.gift_handler.show_monthly_gift_winners(query, user)
        
        # Bank transfer callbacks
        elif data == "bank_transfer_start":
            await start_bank_transfer(query, user, context, self.db, self.main_admin_id)
        elif data.startswith("bt_user_"):
            user_id = int(data.replace("bt_user_", ""))
            await select_transfer_amount(query, user_id, user, context, self.db, self.main_admin_id)
        elif data.startswith("bt_amount_"):
            parts = data.replace("bt_amount_", "").split("_")
            user_id = int(parts[0])
            amount = float(parts[1])
            await execute_bank_transfer(query, user_id, amount, user, context, self.db, self.main_admin_id)
        elif data.startswith("bt_custom_"):
            user_id = int(data.replace("bt_custom_", ""))
            context.user_data['bt_custom_user_id'] = user_id
            context.user_data['awaiting_bank_transfer'] = True
            target_user = self.db.get_user(user_id)
            username = target_user['username'] or target_user['first_name'] if target_user else "User"
            await query.edit_message_text(
                f"✏️ СВОЯ СУММА ДЛЯ @{username}\n\n"
                f"Отправьте сумму (например: 250.50)\n"
                f"Для отмены: /cancel",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отмена", callback_data="bank_transfer_start")
                ]])
            )
        
        # Export callbacks
        elif data.startswith("export_"):
            await generate_export_file(query, data, user, context, self.db, self.main_admin_id, self.target_chat_id)
        
        # Accruals (начисления) callbacks
        elif data == "my_accruals":
            await self.show_accruals_periods(query, user)
        elif data.startswith("accruals_"):
            await self.show_accruals(query, data, user)
        
        # Detalization (детализация Excel) callbacks
        elif data == "my_detalization":
            await self.show_detalization_periods(query, user)
        elif data.startswith("detail_export_"):
            await self.export_user_detalization(query, data, user, context)
        
        # ═══ REACTOR 2.0 CALLBACKS ═══
        elif data == "menu_reactor":
            if not self.db.is_feature_enabled('reactor'):
                await query.answer("🔋 Реактор временно отключён.", show_alert=True)
                return
            is_owner = user.id == self.main_admin_id
            await show_reactor_menu(query, context, self.db, user.id, is_owner=is_owner)

        elif data.startswith("reactor_donate_") and data != "reactor_donate_custom":
            if not self.db.is_feature_enabled('reactor'):
                await query.answer("🔋 Реактор временно отключён.", show_alert=True)
                return
            await handle_reactor_donate_fixed(query, data, user, context, self.db, self.target_chat_id)

        elif data == "reactor_donate_custom":
            if not self.db.is_feature_enabled('reactor'):
                await query.answer("🔋 Реактор временно отключён.", show_alert=True)
                return
            await handle_reactor_donate_custom_start(query, user, context, self.db)

        elif data.startswith("reactor_feat_"):
            if not self.db.is_feature_enabled('reactor'):
                await query.answer("🔋 Реактор временно отключён.", show_alert=True)
                return
            await handle_reactor_feature(query, data, self.db, user.id)

        elif data == "reactor_admin":
            await show_reactor_admin(query, context, self.db, user.id, self.main_admin_id)

        elif data == "reactor_admin_reset":
            await reactor_admin_reset(query, context, self.db, user.id, self.main_admin_id)

        elif data.startswith("reactor_admin_target_") and data != "reactor_admin_target_custom":
            target_val = data.replace("reactor_admin_target_", "")
            await reactor_admin_set_target(query, context, self.db, user.id, self.main_admin_id, target_val)

        elif data == "reactor_admin_target_custom":
            await reactor_admin_custom_target_start(query, user, context, self.db, self.main_admin_id)

        elif data.startswith("reactor_admin_status_"):
            new_status = data.replace("reactor_admin_status_", "")
            await reactor_admin_set_status(query, context, self.db, user.id, self.main_admin_id, new_status)

        # ═══ DONATE CALLBACKS ═══
        elif data == "donate_menu":
            await show_donate_menu(query, user, self.db)
        elif data == "donate_to_user_start":
            await donate_to_user_start(query, user, context, self.db)
        elif data.startswith("donate_pick_user_"):
            await donate_pick_user(query, data, user, context, self.db)
        elif data.startswith("donate_user_amount_"):
            await donate_user_amount(query, data, user, context, self.db)
        elif data.startswith("donate_user_custom_"):
            await donate_user_custom(query, data, user, context, self.db)
        elif data.startswith("donate_user_confirm_"):
            await donate_user_confirm(query, data, user, context, self.db)
        elif data == "donate_to_bank_start":
            await donate_to_bank_start(query, user, context, self.db)
        elif data.startswith("donate_bank_amount_"):
            await donate_bank_amount(query, data, user, context, self.db)
        elif data.startswith("donate_bank_confirm_"):
            await donate_bank_confirm(query, data, user, context, self.db)
        elif data == "donate_bank_custom":
            await donate_bank_custom(query, user, context, self.db)
        elif data == "donate_to_reactor_start":
            await donate_to_reactor_start(query, user, context, self.db)
        elif data.startswith("donate_reactor_amount_"):
            await donate_reactor_amount(query, data, user, context, self.db)
        elif data.startswith("donate_reactor_confirm_"):
            await donate_reactor_confirm(query, data, user, context, self.db)
        elif data == "donate_reactor_custom":
            await donate_reactor_custom(query, user, context, self.db)
        elif data == "donate_history":
            await donate_show_history(query, user, self.db)
    
    async def show_main_menu(self, query, user):
        """Show main menu — respects feature toggles"""
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("Сначала используй /start")
            return
        
        is_owner = user.id == self.main_admin_id
        balance = user_data['balance']
        
        message = f"📱 ГЛАВНОЕ МЕНЮ\n\n"
        message += f"👤 {user.first_name}\n"
        message += f"💰 Баланс: {format_number(balance)} 💎 Пульсов"
        
        keyboard = []
        
        # ── Кнопки для ВСЕХ (если функция включена) ──
        if self.db.is_feature_enabled('top') or self.db.is_feature_enabled('top_commands'):
            keyboard.append([InlineKeyboardButton("🏆 ТОП-5", callback_data="menu_top5")])

        if self.db.is_feature_enabled('activities'):
            keyboard.append([InlineKeyboardButton("🎯 Активности", callback_data="menu_activities")])

        if self.db.is_feature_enabled('bank'):
            keyboard.append([InlineKeyboardButton("🏦 Центробанк", callback_data="menu_bank")])

        if self.db.is_feature_enabled('detalization'):
            keyboard.append([InlineKeyboardButton("📋 Детализация", callback_data="my_detalization")])

        if self.db.is_feature_enabled('bbs'):
            keyboard.append([InlineKeyboardButton("❣️ Pulse BBS", callback_data="menu_bbs")])
        
        if self.db.is_feature_enabled('reactor'):
            keyboard.append([InlineKeyboardButton("🔋 Реактор 2.0", callback_data="menu_reactor")])
        
        keyboard.append([InlineKeyboardButton("📋 Правила", url="https://t.me/c/3153855971/13")])
        
        # ── Владелец ──
        if is_owner:
            if self.db.is_feature_enabled('statistics'):
                keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="menu_stats")])
            
            keyboard.append([InlineKeyboardButton("💾 Скачать БД (Бэкап)", callback_data="owner_backup")])
            keyboard.append([InlineKeyboardButton("🔧 Управление функциями", callback_data="manage_features")])
            keyboard.append([InlineKeyboardButton("📰 Пресс-релиз", callback_data="press_release_start")])

            if self.db.is_feature_enabled('horoscope'):
                keyboard.append([InlineKeyboardButton("🔮 Гороскоп", callback_data="horoscope_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def show_balance(self, query, user):
        """Show user balance"""
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("Сначала используй /start")
            return
        
        balance = user_data['balance']
        
        # Get user's title
        self.db.cursor.execute('''
            SELECT title_name, emoji, multiplier 
            FROM titles 
            WHERE user_id = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            ORDER BY granted_at DESC LIMIT 1
        ''', (user.id,))
        title = self.db.cursor.fetchone()
        
        message = f"💰 Ваш баланс: {format_number(balance)} 💎 Пульсов"
        
        if title:
            message += f"\n\n{title['emoji']} Титул: {title['title_name']}"
            message += f"\n⚡ Множитель: x{title['multiplier']}"
        
        keyboard = [
            [InlineKeyboardButton("💎 Начисления Пульса", callback_data="my_accruals")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    # ═══════════════════════════════════════════
    # НАЧИСЛЕНИЯ ПУЛЬСА (текстовый отчёт в чате)
    # ═══════════════════════════════════════════
    
    async def show_accruals_periods(self, query, user):
        """Show period selection for accruals history"""
        user_data = self.db.get_user(user.id)
        if not user_data:
            await query.edit_message_text("Сначала используй /start")
            return
        
        joined_at = user_data['joined_at']
        if joined_at:
            try:
                joined_date = datetime.strptime(str(joined_at)[:10], '%Y-%m-%d')
                days_in_chat = (datetime.now() - joined_date).days
            except (ValueError, TypeError):
                days_in_chat = 0
        else:
            days_in_chat = 0
        
        message = "💎 НАЧИСЛЕНИЯ ПУЛЬСА\n\n"
        message += "Выберите период для просмотра:"
        
        keyboard = [
            [InlineKeyboardButton("📅 Сегодня", callback_data="accruals_today")],
            [InlineKeyboardButton("📅 Вчера", callback_data="accruals_yesterday")],
            [InlineKeyboardButton("📅 За 7 дней", callback_data="accruals_week")],
            [InlineKeyboardButton("📅 За 30 дней", callback_data="accruals_month")],
        ]
        
        if days_in_chat > 30:
            keyboard.append([InlineKeyboardButton("📅 За 90 дней", callback_data="accruals_90d")])
        if days_in_chat > 90:
            keyboard.append([InlineKeyboardButton("📅 За полгода", callback_data="accruals_180d")])
        
        keyboard.append([InlineKeyboardButton("📅 За всё время", callback_data="accruals_all")])
        keyboard.append([InlineKeyboardButton("🔙 К балансу", callback_data="menu_balance")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def show_accruals(self, query, data, user):
        """Show accruals for selected period"""
        user_data = self.db.get_user(user.id)
        if not user_data:
            await query.edit_message_text("Сначала используй /start")
            return
        
        today = get_today_date_msk()
        period_key = data.replace("accruals_", "")
        
        if period_key == "today":
            date_from = str(today)
            period_name = f"Сегодня ({today.strftime('%d.%m.%Y')})"
        elif period_key == "yesterday":
            yesterday = today - timedelta(days=1)
            date_from = str(yesterday)
            period_name = f"Вчера ({yesterday.strftime('%d.%m.%Y')})"
        elif period_key == "week":
            date_from = str(today - timedelta(days=7))
            period_name = "Последние 7 дней"
        elif period_key == "month":
            date_from = str(today - timedelta(days=30))
            period_name = "Последние 30 дней"
        elif period_key == "90d":
            date_from = str(today - timedelta(days=90))
            period_name = "Последние 90 дней"
        elif period_key == "180d":
            date_from = str(today - timedelta(days=180))
            period_name = "Последние 180 дней"
        elif period_key == "all":
            date_from = "2000-01-01"
            period_name = "За всё время"
        else:
            date_from = str(today)
            period_name = "Сегодня"
        
        if period_key == "yesterday":
            date_condition = "AND DATE(t.timestamp) = ?"
        else:
            date_condition = "AND DATE(t.timestamp) >= ?"
        date_params = (user.id, date_from)
        
        # Доходы
        self.db.cursor.execute(f'''
            SELECT 
                COALESCE(SUM(CASE WHEN t.transaction_type = 'message_reward' THEN t.amount ELSE 0 END), 0) AS mining,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'referral_reward' THEN t.amount ELSE 0 END), 0) AS referral,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'lottery_win' THEN t.amount ELSE 0 END), 0) AS lottery,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'monthly_gift' THEN t.amount ELSE 0 END), 0) AS gift,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'transfer' THEN t.amount ELSE 0 END), 0) AS transfers_in,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'admin_give' THEN t.amount ELSE 0 END), 0) AS admin_give,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'donate_to_user' THEN t.amount ELSE 0 END), 0) AS donates_in,
                COALESCE(SUM(t.amount), 0) AS total_in,
                COUNT(t.id) AS tx_count
            FROM transactions t
            WHERE t.to_user_id = ? {date_condition}
        ''', date_params)
        income = self.db.cursor.fetchone()
        
        # Расходы
        self.db.cursor.execute(f'''
            SELECT 
                COALESCE(SUM(CASE WHEN t.transaction_type = 'transfer' THEN t.amount ELSE 0 END), 0) AS transfers_out,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'reactor_donation' THEN t.amount ELSE 0 END), 0) AS donations,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'lottery_ticket' THEN t.amount ELSE 0 END), 0) AS lottery_tickets,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'return_on_leave' THEN t.amount ELSE 0 END), 0) AS returned,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'donate_to_user' THEN t.amount ELSE 0 END), 0) AS donates_out,
                COALESCE(SUM(CASE WHEN t.transaction_type = 'donate_to_bank' THEN t.amount ELSE 0 END), 0) AS donates_bank,
                COALESCE(SUM(t.amount), 0) AS total_out,
                COUNT(t.id) AS tx_count
            FROM transactions t
            WHERE t.from_user_id = ? {date_condition}
        ''', date_params)
        expenses = self.db.cursor.fetchone()
        
        # Детализация по дням
        daily_breakdown = ""
        if period_key not in ("today", "yesterday"):
            self.db.cursor.execute(f'''
                SELECT DATE(t.timestamp) AS day,
                       COALESCE(SUM(t.amount), 0) AS daily_income,
                       COUNT(t.id) AS tx_count
                FROM transactions t
                WHERE t.to_user_id = ?
                  AND t.transaction_type = 'message_reward'
                  {date_condition}
                GROUP BY DATE(t.timestamp)
                ORDER BY day DESC
                LIMIT 10
            ''', date_params)
            daily_rows = self.db.cursor.fetchall()
            if daily_rows:
                daily_breakdown = "\n📊 Майнинг по дням (посл. 10):\n"
                for row_data in daily_rows:
                    day_str = row_data['day']
                    try:
                        day_formatted = datetime.strptime(day_str, '%Y-%m-%d').strftime('%d.%m')
                    except (ValueError, TypeError):
                        day_formatted = day_str
                    daily_breakdown += f"   {day_formatted} — {format_number(row_data['daily_income'])} 💎 ({row_data['tx_count']} сообщ.)\n"
        
        net = income['total_in'] - expenses['total_out']
        
        message = f"💎 НАЧИСЛЕНИЯ ПУЛЬСА\n📅 {period_name}\n\n"
        
        message += "📥 ДОХОДЫ:\n"
        if income['mining'] > 0:
            message += f"   ⛏ Майнинг: +{format_number(income['mining'])} 💎\n"
        if income['transfers_in'] > 0:
            message += f"   💸 Переводы: +{format_number(income['transfers_in'])} 💎\n"
        if income['referral'] > 0:
            message += f"   👥 Реферальные: +{format_number(income['referral'])} 💎\n"
        if income['lottery'] > 0:
            message += f"   🎰 Лотерея: +{format_number(income['lottery'])} 💎\n"
        if income['gift'] > 0:
            message += f"   🎁 Подарок месяца: +{format_number(income['gift'])} 💎\n"
        if income['admin_give'] > 0:
            message += f"   🏦 От Центробанка: +{format_number(income['admin_give'])} 💎\n"
        if income['donates_in'] > 0:
            message += f"   🎁 Донаты: +{format_number(income['donates_in'])} 💎\n"
        if income['total_in'] == 0:
            message += "   — нет начислений\n"
        message += f"   ▸ Итого: +{format_number(income['total_in'])} 💎 ({income['tx_count']} опер.)\n\n"
        
        message += "📤 РАСХОДЫ:\n"
        if expenses['transfers_out'] > 0:
            message += f"   💸 Переводы: -{format_number(expenses['transfers_out'])} 💎\n"
        if expenses['donations'] > 0:
            message += f"   🔋 Реактор: -{format_number(expenses['donations'])} 💎\n"
        if expenses['lottery_tickets'] > 0:
            message += f"   🎰 Билеты: -{format_number(expenses['lottery_tickets'])} 💎\n"
        if expenses['returned'] > 0:
            message += f"   ↩️ Возврат: -{format_number(expenses['returned'])} 💎\n"
        if expenses['donates_out'] > 0:
            message += f"   🎁 Донаты: -{format_number(expenses['donates_out'])} 💎\n"
        if expenses['donates_bank'] > 0:
            message += f"   🏦 Донат в банк: -{format_number(expenses['donates_bank'])} 💎\n"
        if expenses['total_out'] == 0:
            message += "   — нет расходов\n"
        message += f"   ▸ Итого: -{format_number(expenses['total_out'])} 💎 ({expenses['tx_count']} опер.)\n\n"
        
        sign = "+" if net >= 0 else ""
        message += f"📊 ИТОГО: {sign}{format_number(net)} 💎\n"
        message += f"💰 Текущий баланс: {format_number(user_data['balance'])} 💎"
        message += daily_breakdown
        
        if len(message) > 4000:
            message = message[:3950] + "\n\n... (данные обрезаны)"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Выбрать период", callback_data="my_accruals")],
            [InlineKeyboardButton("🔙 К балансу", callback_data="menu_balance")],
            [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    # ═══════════════════════════════════════════
    # ДЕТАЛИЗАЦИЯ (Excel-файл для пользователя)
    # ═══════════════════════════════════════════
    
    async def show_detalization_periods(self, query, user):
        """Show period selection for Excel detalization export"""
        message = "📋 ДЕТАЛИЗАЦИЯ\n\n"
        message += "Выберите период для выгрузки Excel-файла\n"
        message += "с полной историей операций:"
        
        keyboard = [
            [InlineKeyboardButton("📅 День", callback_data="detail_export_day")],
            [InlineKeyboardButton("📅 Неделя", callback_data="detail_export_week")],
            [InlineKeyboardButton("📅 Месяц", callback_data="detail_export_month")],
            [InlineKeyboardButton("📅 Год", callback_data="detail_export_year")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def export_user_detalization(self, query, data, user, context):
        """Generate and send personal Excel detalization"""
        import os
        
        user_data = self.db.get_user(user.id)
        if not user_data:
            await query.edit_message_text("Сначала используй /start")
            return
        
        period = data.replace("detail_export_", "")  # day, week, month, year
        
        period_names = {
            'day': 'день',
            'week': 'неделю',
            'month': 'месяц',
            'year': 'год'
        }
        
        await query.edit_message_text(f"⏳ Генерирую детализацию за {period_names.get(period, period)}...")
        
        try:
            from utils.detalization import generate_user_detalization
            
            timestamp = get_moscow_time().strftime('%Y%m%d_%H%M%S')
            username = user_data['username'] or user_data['first_name'] or f"user{user.id}"
            filename = f'detalization_{username}_{period}_{timestamp}.xlsx'
            filepath = os.path.join('logs', filename)
            os.makedirs('logs', exist_ok=True)
            
            result = generate_user_detalization(self.db, user.id, period, filepath)
            
            if result and os.path.exists(filepath):
                with open(filepath, 'rb') as file:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=file,
                        filename=filename,
                        caption=(
                            f"📋 Детализация операций @{username}\n"
                            f"📅 Период: {period_names.get(period, period)}\n"
                            f"💱 Курс на дату выгрузки: {self.db.get_exchange_rate():.6f} ₽/Пульс"
                        ),
                        reply_to_message_id=query.message.message_id
                    )
                
                try:
                    os.remove(filepath)
                except:
                    pass
                
                await query.edit_message_text(
                    f"✅ Детализация отправлена!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📋 Другой период", callback_data="my_detalization")],
                        [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
                    ])
                )
            else:
                await query.edit_message_text(
                    "❌ Ошибка при создании файла. Возможно, нет операций за выбранный период.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📋 Другой период", callback_data="my_detalization")],
                        [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
                    ])
                )
        except Exception as e:
            import logging
            logging.error(f"Error exporting detalization: {e}")
            await query.edit_message_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
                ]])
            )
    
    async def show_activities_menu(self, query, user):
        """Show Activities menu with Lottery, Monthly Gift, and Referral System"""
        is_owner = user.id == self.main_admin_id
        
        message = "🎯 АКТИВНОСТИ\n\n"
        message += "Выберите активность:"
        
        keyboard = []
        
        # Donate for ALL users
        if self.db.is_feature_enabled('donate'):
            keyboard.append([InlineKeyboardButton("🎁 Донаты", callback_data="donate_menu")])
        
        # Referral system - for ALL users if enabled
        if self.db.is_feature_enabled('referral'):
            keyboard.append([InlineKeyboardButton("👥 Реферальная система", callback_data="menu_referral")])
        
        # Lottery — видна ВСЕМ (owner → управление, user → активные лотереи)
        if self.db.is_feature_enabled('lottery'):
            if is_owner:
                keyboard.append([InlineKeyboardButton("🎰 Лотерея (управление)", callback_data="menu_lottery")])
            else:
                keyboard.append([InlineKeyboardButton("🎰 Лотерея", callback_data="menu_lottery")])
        
        # Бинго — видна ВСЕМ если включена
        if self.db.is_feature_enabled('bingo'):
            if is_owner:
                keyboard.append([InlineKeyboardButton("🎱 Бинго (управление)", callback_data="menu_bingo")])
            else:
                keyboard.append([InlineKeyboardButton("🎱 Бинго", callback_data="menu_bingo")])
        
        # Monthly gift - visible to ALL users
        monthly_gift_enabled = int(self.db.get_setting('monthly_gift_enabled', '1'))
        if is_owner:
            keyboard.append([InlineKeyboardButton("🎁 Подарок месяца (управление)", callback_data="menu_monthly_gift")])
        elif monthly_gift_enabled:
            keyboard.append([InlineKeyboardButton("🎁 Подарок месяца", callback_data="monthly_gift_user_view")])
        
        # Reactor 2.0
        if self.db.is_feature_enabled('reactor'):
            keyboard.append([InlineKeyboardButton("🔋 Реактор 2.0", callback_data="menu_reactor")])
        
        # Back button
        keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def show_referral(self, query, user, context):
        """Show referral info with one-time link"""
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("Сначала используй /start")
            return
        
        # Generate one-time referral link (auto-creates new if previous was used)
        ref_link = generate_referral_link(self.bot_username, user.id, db=self.db)
        
        # Get referral stats
        self.db.cursor.execute('''
            SELECT COUNT(*) as total
            FROM users
            WHERE referrer_id = ? AND is_qualified = 1
        ''', (user.id,))
        qualified = self.db.cursor.fetchone()['total']
        
        # Get one-time link stats
        link_stats = self.db.get_referral_link_stats(user.id)
        used_links = link_stats['used_links'] if link_stats else 0
        
        message = f"👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
        message += f"🔗 Ваша ссылка (одноразовая):\n{ref_link}\n\n"
        message += f"⚠️ Ссылка станет неактивной после перехода.\n"
        message += f"Новая ссылка создастся автоматически!\n\n"
        message += f"✅ Квалифицированных рефералов: {qualified}\n"
        message += f"🔗 Использовано ссылок: {used_links}\n\n"
        message += f"💡 Условия:\n"
        message += f"• Друг должен пробыть в чате 24 часа\n"
        message += f"• Написать минимум 5 сообщений\n"
        message += f"• ИЛИ получить 3+ реакции\n\n"
        message += f"🎁 Награда: 500 💎 за каждого друга"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить ссылку", callback_data="referral_refresh")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def refresh_referral_link(self, query, user, context):
        """Force refresh referral link — creates new one-time token"""
        # Invalidate current unused link and create new one
        self.db.cursor.execute('''
            UPDATE referral_links 
            SET is_used = 1, used_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND is_used = 0
        ''', (user.id,))
        self.db.conn.commit()
        
        # Create fresh link
        self.db.create_referral_link(user.id)
        
        await query.answer("🔄 Ссылка обновлена!", show_alert=True)
        
        # Refresh the referral view
        await self.show_referral(query, user, context)
    
