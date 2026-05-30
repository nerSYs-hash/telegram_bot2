#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Центральный роутер callback-ов.

handlers/callback/callback_router.py

Импортирует sub-dispatchers и направляет callback-ы по категориям.
"""

import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import format_number, generate_referral_link, get_moscow_time, get_today_date_msk

from handlers.lottery_handlers import LotteryHandler
from handlers.bingo_handlers import BingoHandler
from handlers.gift_handlers import GiftHandler
from handlers.BBS.callback_bbs import handle_bbs_callback

from handlers.owner_handlers import ensure_owner_columns
from handlers.exit_survey_handlers import ensure_survey_columns
from handlers.journal_handlers import ensure_journal_tables

from handlers.callback.user_callbacks import dispatch_user
from handlers.callback.activity_callbacks import dispatch_activity
from handlers.callback.admin_callbacks import dispatch_admin
from handlers.callback.owner_callbacks import dispatch_owner

logger = logging.getLogger(__name__)


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

        ensure_owner_columns(db)
        ensure_survey_columns(db)
        ensure_journal_tables(db)
        from handlers.anketa_edit_handlers import ensure_anketa_edit_tables
        ensure_anketa_edit_tables(db)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries — dispatches to sub-modules."""
        query = update.callback_query
        data = query.data
        user = query.from_user

        if not data:
            return

        # V1.16.0: titles_* и owner_titles_* обрабатываются выделенными
        # хэндлерами в группе 1 — не перехватываем здесь.
        if data.startswith('titles_') or data.startswith('owner_titles_'):
            return

        try:
            await query.answer()
        except Exception:
            pass

        # ═══ PRIVATE-ONLY для обычных пользователей ═══
        _u_caller = self.db.get_user(user.id)
        is_owner = user.id == self.main_admin_id or bool(_u_caller and _u_caller['is_owner'])
        if not is_owner and query.message and query.message.chat.type != 'private':
            private_callbacks = {
                'menu_profile', 'menu_balance', 'menu_lottery', 'menu_bingo',
                'menu_monthly_gift', 'menu_referral', 'my_accruals', 'my_detalization',
                'donate_menu', 'monthly_gift_user_view', 'monthly_gift_participate',
                'monthly_gift_my_progress', 'monthly_gift_winners', 'profile_settings',
            }
            if data in private_callbacks or data.startswith(('accruals_', 'detail_export_',
                'donate_', 'prof_notif_', 'prof_age_', 'monthly_gift_')):
                try:
                    bot_me = await context.bot.get_me()
                    await query.edit_message_text(
                        f"📋 Эта функция доступна в личных сообщениях.\n👉 @{bot_me.username}"
                    )
                except Exception:
                    pass
                return

        # ═══ BUG TRACKER CALLBACKS ═══
        if data.startswith('bug_'):
            from handlers.bug_tracker_handlers import handle_bug_callback
            if await handle_bug_callback(query, context, self.db):
                return

        # ═══ ANKETA EDIT CALLBACKS ═══
        if data.startswith('anketa_edit_'):
            from handlers.anketa_edit_handlers import handle_anketa_edit_callback, ensure_anketa_edit_tables
            ensure_anketa_edit_tables(self.db)
            await handle_anketa_edit_callback(query, context, self.db, data)
            return

        # ═══ НАСТРОЙКИ АНКЕТЫ (%_form%) ═══
        if data.startswith('form_toggle_') or data == 'form_done':
            from handlers.placeholder_handlers import handle_form_settings_callback
            await handle_form_settings_callback(query, data, self.db, user.id)
            return

        # ═══ BBS CALLBACKS (ранний возврат) ═══
        if data.startswith('report_reason_') or data == 'report_cancel':
            from handlers.callback.user_callbacks import handle_report_callback
            await handle_report_callback(self, query, context, data, user)
            return

        if data.startswith('bbs_report_'):
            from handlers.callback.user_callbacks import show_report_menu
            await show_report_menu(self, query, context, data, user)
            return

        if data.startswith('bbs_') or data.startswith('other_') or data == 'menu_bbs':
            await handle_bbs_callback(query, context, self.db, self.target_chat_id, self.bbs_thread_id)
            return

        # ═══ INACTIVE USERS PAGINATION ═══
        if data.startswith('inactive_page:'):
            from handlers.reminders import handle_inactive_pagination
            await handle_inactive_pagination(update, context, self.db)
            return

        # ═══ DISPATCH TO SUB-MODULES ═══
        if await dispatch_user(self, query, data, user, context):
            return
        if await dispatch_activity(self, query, data, user, context):
            return
        if await dispatch_admin(self, query, data, user, context):
            return
        if await dispatch_owner(self, query, data, user, context):
            return

        # Перезапуск регистрации
        if data in ("restart_registration", "reapply"):
            from database.db_friend import update_user, cancel_user_applications, get_user as _get_friend_user, db_pool
            from constants import ApplicationStatus
            from config import OWNER_ID

            # Защита: если юзер УЖЕ регистрировался (есть q_name)
            # ИЛИ был ранее одобрен (есть запись APPROVED в applications) —
            # это возвращающийся, его данные стирать нельзя.
            existing = await _get_friend_user(user.id)
            has_q_name = bool(existing and existing.get('q_name'))

            has_approved_app = False
            if not has_q_name:
                try:
                    async with db_pool.get_connection() as _db:
                        async with _db.execute(
                            "SELECT 1 FROM applications WHERE user_id = ? AND status = ? LIMIT 1",
                            (user.id, ApplicationStatus.APPROVED)
                        ) as _cur:
                            has_approved_app = bool(await _cur.fetchone())
                except Exception as e:
                    logger.error(f"restart_registration: approved_app check failed for {user.id}: {e}")

            if has_q_name or has_approved_app:
                await query.answer()
                await query.edit_message_text(
                    "✅ Ты уже регистрировался ранее.\n\n"
                    "Отправь команду /register — бот проверит твой статус и пришлёт ссылку для возвращения в чат."
                )
                return

            await cancel_user_applications(user.id)
            await update_user(user.id, status='new', questionnaire_state=None)
            await query.answer()
            await query.edit_message_text(
                "✅ Готово! Теперь отправь команду /register чтобы заполнить анкету заново."
            )
            return

        # Неизвестный callback
        logger.warning(f"Unhandled callback: {data}")

    async def show_main_menu(self, query, user):
        """Show main menu — respects feature toggles"""
        user_data = self.db.get_user(user.id)

        if not user_data:
            await query.edit_message_text("Сначала используй /start")
            return

        is_owner = user.id == self.main_admin_id or bool(user_data and user_data['is_owner'])
        balance = user_data['balance']

        message = f"📱 ГЛАВНОЕ МЕНЮ\n\n"
        message += f"👤 {user.first_name}\n"
        message += f"💰 Баланс: {format_number(balance)} 💎 Пульсов"

        # Видимость функций per-ws: ws по членству юзера (в ЛС chat не в bot_chats).
        # ws=None → feature_enabled_ws мягко падает в legacy-глобал.
        from bot_core.ws_resolver import resolve_user_primary_workspace
        ws_id = resolve_user_primary_workspace(self.db.conn, user.id)

        keyboard = []

        # ── Кнопки для ВСЕХ (если функция включена) ──
        if self.db.feature_enabled_ws('top', ws_id) or self.db.feature_enabled_ws('top_commands', ws_id):
            keyboard.append([InlineKeyboardButton("🏆 ТОП-5", callback_data="menu_top5")])

        if self.db.activities_visible(ws_id):  # 🎯 хаб виден, если включена хоть одна вложенная функция
            keyboard.append([InlineKeyboardButton("🎯 Активности", callback_data="menu_activities")])

        if self.db.feature_enabled_ws('bank', ws_id):
            keyboard.append([InlineKeyboardButton("🏦 Центробанк", callback_data="menu_bank")])

        if self.db.feature_enabled_ws('detalization', ws_id):
            keyboard.append([InlineKeyboardButton("📋 Детализация", callback_data="my_detalization")])

        if self.db.feature_enabled_ws('bbs', ws_id):
            keyboard.append([InlineKeyboardButton("❣️ Pulse BBS", callback_data="menu_bbs")])

        keyboard.append([InlineKeyboardButton("📋 Правила", url="https://t.me/c/3153855971/13")])

        # ── Статистика: для админов И владельца/зама ──
        is_admin_user = user_data and (user_data['is_admin'] or user_data['is_owner'])
        if (is_owner or is_admin_user) and self.db.feature_enabled_ws('statistics', ws_id):
            keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="menu_stats")])

        # ── Владелец/Зам ──
        if is_owner:
            keyboard.append([InlineKeyboardButton("💘 Шиппер", callback_data="owner_shipper_menu")])
            keyboard.append([InlineKeyboardButton("📰 Пресс-релиз", callback_data="press_release_start")])

            if self.db.feature_enabled_ws('horoscope', ws_id):
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
        ]
        if self.db.is_feature_enabled('titles'):
            keyboard.append([InlineKeyboardButton("🏷 Титулы", callback_data="titles_menu")])
        keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
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

        # Скрытое комбо "Мэтч дня" (активации резонанса)
        if period_key == "yesterday":
            resonance_date_condition = "AND DATE(activated_at) = ?"
        else:
            resonance_date_condition = "AND DATE(activated_at) >= ?"
        self.db.cursor.execute(f'''
            SELECT COUNT(*) AS cnt
            FROM shipper_resonance_stats
            WHERE user_id = ? {resonance_date_condition}
        ''', date_params)
        resonance_row = self.db.cursor.fetchone()
        resonance_count = int(resonance_row['cnt']) if resonance_row and resonance_row['cnt'] is not None else 0

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
        if resonance_count > 0:
            message += f"   💘 Мэтч дня (x2): {resonance_count} сраб.\n"
        if income['total_in'] == 0:
            message += "   — нет начислений\n"
        message += f"   ▸ Итого: +{format_number(income['total_in'])} 💎 ({income['tx_count']} опер.)\n\n"

        message += "📤 РАСХОДЫ:\n"
        if expenses['transfers_out'] > 0:
            message += f"   💸 Переводы: -{format_number(expenses['transfers_out'])} 💎\n"
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
                except Exception:
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

        from bot_core.ws_resolver import resolve_user_primary_workspace
        ws_id = resolve_user_primary_workspace(self.db.conn, user.id)

        keyboard = []

        # Donate for ALL users
        if self.db.feature_enabled_ws('donate', ws_id):
            keyboard.append([InlineKeyboardButton("🎁 Донаты", callback_data="donate_menu")])

        # Referral system - for ALL users if enabled
        if self.db.feature_enabled_ws('referral', ws_id):
            keyboard.append([InlineKeyboardButton("👥 Реферальная система", callback_data="menu_referral")])

        # Lottery — видна ВСЕМ (owner → управление, user → активные лотереи)
        if self.db.feature_enabled_ws('lottery', ws_id):
            if is_owner:
                keyboard.append([InlineKeyboardButton("🎰 Лотерея (управление)", callback_data="menu_lottery")])
            else:
                keyboard.append([InlineKeyboardButton("🎰 Лотерея", callback_data="menu_lottery")])

        # Бинго — видна ВСЕМ если включена
        if self.db.feature_enabled_ws('bingo', ws_id):
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

        # Get qualification settings from economy_settings with fallbacks
        try:
            hours = int(self.db.get_econ('referral.qualification_hours', 24) or 24)
        except Exception:
            hours = 24
        
        try:
            min_messages = int(self.db.get_econ('referral.qualification_messages', 5) or 5)
        except Exception:
            min_messages = 5
        
        try:
            min_reactions = int(self.db.get_econ('referral.qualification_reactions', 3) or 3)
        except Exception:
            min_reactions = 3
        
        try:
            reward = int(self.db.get_econ('referral.qualified_reward', 100) or 100)
        except Exception:
            reward = 100
        
        message = f"👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
        message += f"🔗 Ваша ссылка (одноразовая):\n{ref_link}\n\n"
        message += f"⚠️ Ссылка станет неактивной после перехода.\n"
        message += f"Новая ссылка создастся автоматически!\n\n"
        message += f"✅ Квалифицированных рефералов: {qualified}\n"
        message += f"🔗 Использовано ссылок: {used_links}\n\n"
        message += f"💡 Условия:\n"
        message += f"• Друг должен пробыть в чате {hours} часа\n"
        message += f"• Написать минимум {min_messages} сообщений\n"
        message += f"• ИЛИ получить {min_reactions}+ реакции\n\n"
        message += f"🎁 Награда: {reward} 💎 за каждого друга"

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

    # ═══════════════════════════════════════════
    # ЖАЛОБЫ BBS (Deep Link flow)
    # ═══════════════════════════════════════════

    REPORT_REASONS = {
        'spam': '🔞 Спам / Реклама',
        'fake': '🤡 Фейк / Мошенник',
        'toxic': '🤬 Оскорбления / Токсичность',
        'nsfw': '🔞 Откровенный контент',
    }

    async def _show_report_menu(self, query, context, data, user):
        """Показ меню выбора причины жалобы (callback от кнопки ⚠️)."""
        import html

        try:
            reported_user_id = int(data.replace('bbs_report_', ''))
        except (ValueError, IndexError):
            await query.answer("❌ Ошибка данных", show_alert=True)
            return

        context.user_data['reporting_user_id'] = reported_user_id

        try:
            reported_user = self.db.get_user(reported_user_id)
            if reported_user:
                reported_name = html.escape(reported_user['username'] or reported_user['first_name'] or str(reported_user_id))
            else:
                reported_name = str(reported_user_id)
        except Exception:
            reported_name = str(reported_user_id)

        text = (
            f"🚨 <b>Жалоба на пользователя</b>\n\n"
            f"👤 <b>Нарушитель:</b> @{reported_name}\n\n"
            f"Выберите причину жалобы:"
        )

        keyboard = []
        for reason_key, reason_text in self.REPORT_REASONS.items():
            keyboard.append([InlineKeyboardButton(
                reason_text,
                callback_data=f"report_reason_{reason_key}"
            )])

        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="report_cancel")])

        try:
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        except Exception:
            try:
                await query.message.reply_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Failed to show report menu: {e}")
                await query.answer("❌ Ошибка отображения меню", show_alert=True)

    async def _handle_report_callback(self, query, context, data, user):
        """Обработка выбора причины жалобы."""
        import html

        # ── Отмена ──
        if data == 'report_cancel':
            context.user_data.pop('reporting_user_id', None)
            try:
                await query.edit_message_text("❌ Жалоба отменена.")
            except Exception:
                pass
            return

        # ── Выбор причины ──
        reason_key = data.replace('report_reason_', '')
        reason_text = self.REPORT_REASONS.get(reason_key, reason_key)

        reported_user_id = context.user_data.pop('reporting_user_id', None)
        if not reported_user_id:
            try:
                await query.edit_message_text("❌ Ошибка: данные жалобы устарели. Попробуйте ещё раз.")
            except Exception:
                pass
            return

        # Данные заявителя
        reporter_name = html.escape(user.username or user.first_name or str(user.id))

        # Данные нарушителя + ссылка на пост
        try:
            reported_user = self.db.get_user(reported_user_id)
            if reported_user:
                reported_name = html.escape(reported_user['username'] or reported_user['first_name'] or str(reported_user_id))
            else:
                reported_name = str(reported_user_id)
        except Exception:
            reported_name = str(reported_user_id)

        # Ссылка на анкету из БД
        post_link_text = ""
        try:
            from handlers.BBS.database_bbs import get_profile
            import json
            profile = get_profile(self.db, reported_user_id)
            if profile:
                msg_ids = profile.get('message_ids', '[]')
                if isinstance(msg_ids, str):
                    msg_ids = json.loads(msg_ids)
                if msg_ids:
                    chat_id_short = str(self.target_chat_id).replace('-100', '')
                    first_msg_id = msg_ids[0]
                    post_link = f"https://t.me/c/{chat_id_short}/{first_msg_id}"
                    post_link_text = f"\n🔗 <a href='{post_link}'>Перейти к анкете</a>"
        except Exception:
            pass

        # Формируем сообщение для админа
        report_msg = (
            f"🚨 <b>НОВАЯ ЖАЛОБА (BBS)</b>\n\n"
            f"👤 <b>От кого:</b> @{reporter_name} (<code>{user.id}</code>)\n"
            f"👤 <b>На кого:</b> @{reported_name} (<code>{reported_user_id}</code>)\n"
            f"📌 <b>Причина:</b> {reason_text}"
            f"{post_link_text}"
        )

        try:
            await context.bot.send_message(
                chat_id=self.main_admin_id,
                text=report_msg,
                parse_mode='HTML',
                disable_web_page_preview=True,
            )
        except Exception as e:
            logging.error(f"Report send to admin failed: {e}")
            try:
                await query.edit_message_text("❌ Не удалось отправить жалобу. Попробуйте позже.")
            except Exception:
                pass
            return

        # Подтверждение заявителю
        try:
            await query.edit_message_text(
                "✅ <b>Ваша жалоба отправлена администрации.</b>\n\n"
                "Спасибо за бдительность! Мы рассмотрим её в ближайшее время.",
                parse_mode='HTML',
            )
        except Exception:
            pass
