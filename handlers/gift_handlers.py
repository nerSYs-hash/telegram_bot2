#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Обработчики Подарка Месяца — вынесены из callback_handler.py
"""

import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import format_number, get_moscow_time
from datetime import datetime, timedelta


class GiftHandler:
    def __init__(self, db, target_chat_id, main_admin_id):
        self.db = db
        self.target_chat_id = target_chat_id
        self.main_admin_id = main_admin_id
        # V1.17.0T (M5): изоляция per-ws — миграция колонки + ws этого хендлера.
        try:
            self.db.cursor.execute(
                "ALTER TABLE monthly_gifts ADD COLUMN workspace_id INTEGER DEFAULT 1")
            self.db.conn.commit()
        except Exception:
            pass  # колонка уже есть / таблица создастся позже
        try:
            from bot_core.workspace_context import resolve_workspace_for_chat
            self.ws_id = resolve_workspace_for_chat(db.conn, target_chat_id) or 1
        except Exception:
            self.ws_id = 1

    def _get_current_gift(self):
        """Get or create current month's gift config"""
        from datetime import datetime
        current_month = datetime.now().strftime('%Y-%m')

        self.db.cursor.execute('''
            SELECT * FROM monthly_gifts WHERE month = ? AND workspace_id = ? ORDER BY id DESC LIMIT 1
        ''', (current_month, self.ws_id))
        gift = self.db.cursor.fetchone()
        return gift, current_month
    
    def _get_user_messages_this_month(self, user_id):
        """Count user messages in current month"""
        from datetime import datetime
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        self.db.cursor.execute('''
            SELECT COUNT(*) as cnt FROM messages
            WHERE user_id = ? AND timestamp >= ?
        ''', (user_id, month_start))
        result = self.db.cursor.fetchone()
        return result['cnt'] if result else 0
    
    def _get_gift_participants_count(self, gift_id):
        """Get number of participants"""
        self.db.cursor.execute('''
            SELECT COUNT(*) as cnt FROM monthly_gift_participants WHERE gift_id = ?
        ''', (gift_id,))
        result = self.db.cursor.fetchone()
        return result['cnt'] if result else 0
    
    def _is_user_participating(self, gift_id, user_id):
        """Check if user is already participating"""
        self.db.cursor.execute('''
            SELECT id FROM monthly_gift_participants WHERE gift_id = ? AND user_id = ?
        ''', (gift_id, user_id))
        return self.db.cursor.fetchone() is not None
    
    def _make_progress_bar(self, current, target, length=10):
        """Create a visual progress bar"""
        if target <= 0:
            return "▓" * length
        ratio = min(current / target, 1.0)
        filled = int(ratio * length)
        return "▓" * filled + "░" * (length - filled)
    
    # ──────────────────────────────────────
    # OWNER: Главное меню подарка
    # ──────────────────────────────────────
    
    async def show_monthly_gift_menu(self, query, user, context):
        """Show monthly gift admin panel (owner only)"""
        if user.id != self.main_admin_id:
            await query.answer("У вас нет доступа к этой функции.", show_alert=True)
            return
        
        enabled = int(self.db.get_setting('monthly_gift_enabled', '1'))
        gift, current_month = self._get_current_gift()
        
        # Prize type labels
        type_labels = {
            'pulses': '💎 Пульсы',
            'title': '👑 VIP-титул',
            'custom': '🎯 Свой приз'
        }
        
        # Condition type labels
        cond_labels = {
            'random': '🎲 Случайный',
            'weighted': '⚖️ По активности',
            'top_active': '🏆 Самый активный'
        }
        
        message = "🎁 ПОДАРОК МЕСЯЦА — УПРАВЛЕНИЕ\n"
        message += f"📅 {current_month}\n\n"
        
        if enabled:
            message += "📊 Статус: ✅ Включено\n\n"
        else:
            message += "📊 Статус: ❌ Отключено\n\n"
        
        if gift:
            prize_type = type_labels.get(gift['prize_type'], gift['prize_type'])
            cond_type = cond_labels.get(gift['condition_type'], gift['condition_type'])
            participants = self._get_gift_participants_count(gift['id'])
            
            message += f"🎁 Приз: {prize_type}\n"
            message += f"💰 Сумма: {format_number(gift['prize_amount'])} Пульсов\n"
            
            if gift['prize_description']:
                message += f"📝 Описание: {gift['prize_description']}\n"
            
            message += f"\n⚙️ Режим: {cond_type}\n"
            message += f"✉️ Мин. сообщений: {gift['condition_min_messages']}\n"
            message += f"👥 Участников: {participants}\n"
            
            if gift['status'] == 'completed' and gift['winner_id']:
                winner = self.db.get_user(gift['winner_id'])
                w_name = (winner['username'] or winner['first_name'] or str(gift['winner_id'])) if winner else str(gift['winner_id'])
                message += f"\n🏆 Победитель: @{w_name}\n"
                message += f"📅 Вручен: {gift['awarded_at']}\n"
            elif gift['status'] == 'active':
                message += f"\n⏳ Статус: Ожидает розыгрыша\n"
        else:
            message += "📭 Подарок на этот месяц не создан\n"
            message += "Нажмите «Создать подарок» чтобы настроить"
        
        # Build keyboard
        keyboard = []
        
        if not gift or gift['status'] == 'completed':
            keyboard.append([InlineKeyboardButton("🆕 Создать подарок", callback_data="monthly_gift_create")])
        
        if gift and gift['status'] == 'active':
            keyboard.append([InlineKeyboardButton("⚙️ Настроить приз", callback_data="monthly_gift_create")])
            keyboard.append([InlineKeyboardButton(f"👥 Участники ({self._get_gift_participants_count(gift['id'])})", callback_data="monthly_gift_participants")])
            keyboard.append([InlineKeyboardButton("📢 Анонс в чат", callback_data="monthly_gift_announce")])
            keyboard.append([InlineKeyboardButton("🎲 ПРОВЕСТИ РОЗЫГРЫШ", callback_data="monthly_gift_confirm_draw")])
        
        # Toggle button
        if enabled:
            keyboard.append([InlineKeyboardButton("❌ Выключить", callback_data="monthly_gift_toggle")])
        else:
            keyboard.append([InlineKeyboardButton("✅ Включить", callback_data="monthly_gift_toggle")])
        
        keyboard.append([InlineKeyboardButton("📊 История розыгрышей", callback_data="monthly_gift_history")])
        keyboard.append([InlineKeyboardButton("🔙 Активности", callback_data="menu_activities")])
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ──────────────────────────────────────
    # OWNER: Создание / настройка подарка
    # ──────────────────────────────────────
    
    async def monthly_gift_create_start(self, query, user, context):
        """Create or configure monthly gift — step 1: choose prize amount"""
        if user.id != self.main_admin_id:
            await query.answer("Нет доступа", show_alert=True)
            return
        
        gift, current_month = self._get_current_gift()
        
        try:
            _default_amount = int(self.db.get_econ('monthly_gift.default_amount', 500) or 500)
        except Exception:
            _default_amount = 500
        current_amount = gift['prize_amount'] if gift else _default_amount
        
        message = "🎁 НАСТРОЙКА ПОДАРКА\n"
        message += f"📅 {current_month}\n\n"
        message += f"💰 Текущая сумма: {format_number(current_amount)} Пульсов\n\n"
        message += "Выберите сумму приза:"
        
        keyboard = [
            [
                InlineKeyboardButton("250 💎", callback_data="mgift_set_amount_250"),
                InlineKeyboardButton("500 💎", callback_data="mgift_set_amount_500"),
            ],
            [
                InlineKeyboardButton("1000 💎", callback_data="mgift_set_amount_1000"),
                InlineKeyboardButton("2500 💎", callback_data="mgift_set_amount_2500"),
            ],
            [
                InlineKeyboardButton("5000 💎", callback_data="mgift_set_amount_5000"),
                InlineKeyboardButton("10000 💎", callback_data="mgift_set_amount_10000"),
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_monthly_gift")]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def monthly_gift_set_amount(self, query, data, user, context):
        """Set prize amount, then choose type"""
        if user.id != self.main_admin_id:
            return
        
        amount = float(data.replace("mgift_set_amount_", ""))
        gift, current_month = self._get_current_gift()
        
        if gift and gift['status'] == 'active':
            self.db.cursor.execute('''
                UPDATE monthly_gifts SET prize_amount = ? WHERE id = ?
            ''', (amount, gift['id']))
        else:
            self.db.cursor.execute('''
                INSERT INTO monthly_gifts (month, prize_amount, status, workspace_id) VALUES (?, ?, 'active', ?)
            ''', (current_month, amount, self.ws_id))
        self.db.conn.commit()
        
        message = f"✅ Сумма: {format_number(amount)} Пульсов\n\n"
        message += "Выберите тип приза:"
        
        keyboard = [
            [InlineKeyboardButton("💎 Пульсы на баланс", callback_data="mgift_set_type_pulses")],
            [InlineKeyboardButton("👑 VIP-титул + Пульсы", callback_data="mgift_set_type_title")],
            [InlineKeyboardButton("🎯 Кастомный приз + Пульсы", callback_data="mgift_set_type_custom")],
            [InlineKeyboardButton("🔙 Назад", callback_data="monthly_gift_create")]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def monthly_gift_set_type(self, query, data, user, context):
        """Set prize type, then choose condition"""
        if user.id != self.main_admin_id:
            return
        
        prize_type = data.replace("mgift_set_type_", "")
        gift, current_month = self._get_current_gift()
        
        if not gift:
            await query.answer("Сначала создайте подарок", show_alert=True)
            return
        
        type_descriptions = {
            'pulses': 'Победитель получает Пульсы на баланс',
            'title': 'Победитель получает VIP-титул на месяц + Пульсы',
            'custom': 'Победитель получает особый приз + Пульсы'
        }
        
        self.db.cursor.execute('''
            UPDATE monthly_gifts SET prize_type = ?, prize_description = ? WHERE id = ?
        ''', (prize_type, type_descriptions.get(prize_type, ''), gift['id']))
        self.db.conn.commit()
        
        type_labels = {'pulses': '💎 Пульсы', 'title': '👑 VIP-титул', 'custom': '🎯 Свой приз'}
        
        message = f"✅ Тип приза: {type_labels.get(prize_type, prize_type)}\n\n"
        message += "Выберите режим розыгрыша:\n\n"
        message += "🎲 Случайный — равные шансы у всех\n"
        message += "⚖️ По активности — больше сообщений = больше шансов\n"
        message += "🏆 Самый активный — приз за 1 место по сообщениям"
        
        keyboard = [
            [InlineKeyboardButton("🎲 Случайный", callback_data="mgift_set_condition_random")],
            [InlineKeyboardButton("⚖️ Взвешенный по активности", callback_data="mgift_set_condition_weighted")],
            [InlineKeyboardButton("🏆 Самый активный", callback_data="mgift_set_condition_top_active")],
            [InlineKeyboardButton("🔙 Назад", callback_data="monthly_gift_create")]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def monthly_gift_set_condition(self, query, data, user, context):
        """Set draw condition, then choose min messages"""
        if user.id != self.main_admin_id:
            return
        
        condition = data.replace("mgift_set_condition_", "")
        gift, _ = self._get_current_gift()
        
        if not gift:
            await query.answer("Сначала создайте подарок", show_alert=True)
            return
        
        cond_descs = {
            'random': 'Случайный выбор среди всех подходящих участников',
            'weighted': 'Шансы пропорциональны количеству сообщений за месяц',
            'top_active': 'Побеждает участник с наибольшим количеством сообщений'
        }
        
        self.db.cursor.execute('''
            UPDATE monthly_gifts SET condition_type = ?, condition_description = ? WHERE id = ?
        ''', (condition, cond_descs.get(condition, ''), gift['id']))
        self.db.conn.commit()
        
        message = "✅ Режим установлен!\n\n"
        message += "Минимум сообщений для участия:"
        
        keyboard = [
            [
                InlineKeyboardButton("5 ✉️", callback_data="mgift_set_minmsg_5"),
                InlineKeyboardButton("10 ✉️", callback_data="mgift_set_minmsg_10"),
            ],
            [
                InlineKeyboardButton("25 ✉️", callback_data="mgift_set_minmsg_25"),
                InlineKeyboardButton("50 ✉️", callback_data="mgift_set_minmsg_50"),
            ],
            [
                InlineKeyboardButton("100 ✉️", callback_data="mgift_set_minmsg_100"),
                InlineKeyboardButton("0 (без порога)", callback_data="mgift_set_minmsg_0"),
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="monthly_gift_create")]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def monthly_gift_set_min_messages(self, query, data, user, context):
        """Final step — save min messages and show summary"""
        if user.id != self.main_admin_id:
            return
        
        min_msg = int(data.replace("mgift_set_minmsg_", ""))
        gift, current_month = self._get_current_gift()
        
        if not gift:
            await query.answer("Сначала создайте подарок", show_alert=True)
            return
        
        self.db.cursor.execute('''
            UPDATE monthly_gifts SET condition_min_messages = ? WHERE id = ?
        ''', (min_msg, gift['id']))
        self.db.conn.commit()
        
        # Reload gift
        gift, _ = self._get_current_gift()
        
        type_labels = {'pulses': '💎 Пульсы', 'title': '👑 VIP-титул + Пульсы', 'custom': '🎯 Свой приз + Пульсы'}
        cond_labels = {'random': '🎲 Случайный', 'weighted': '⚖️ По активности', 'top_active': '🏆 Самый активный'}
        
        message = "✅ ПОДАРОК МЕСЯЦА НАСТРОЕН!\n\n"
        message += f"📅 Месяц: {current_month}\n"
        message += f"🎁 Тип: {type_labels.get(gift['prize_type'], gift['prize_type'])}\n"
        message += f"💰 Сумма: {format_number(gift['prize_amount'])} Пульсов\n"
        message += f"⚙️ Режим: {cond_labels.get(gift['condition_type'], gift['condition_type'])}\n"
        message += f"✉️ Мин. сообщений: {gift['condition_min_messages']}\n\n"
        message += "Теперь можно:\n"
        message += "📢 Отправить анонс в чат\n"
        message += "🎲 Провести розыгрыш когда будете готовы"
        
        keyboard = [
            [InlineKeyboardButton("📢 Анонс в чат", callback_data="monthly_gift_announce")],
            [InlineKeyboardButton("🔙 К управлению", callback_data="menu_monthly_gift")]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ──────────────────────────────────────
    # OWNER: Участники
    # ──────────────────────────────────────
    
    async def show_monthly_gift_participants(self, query, user):
        """Show list of participants"""
        if user.id != self.main_admin_id:
            return
        
        gift, current_month = self._get_current_gift()
        if not gift:
            await query.answer("Подарок не создан", show_alert=True)
            return
        
        self.db.cursor.execute('''
            SELECT p.user_id, p.registered_at, p.is_qualified, u.username, u.first_name
            FROM monthly_gift_participants p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.gift_id = ?
            ORDER BY p.registered_at ASC
        ''', (gift['id'],))
        
        participants = self.db.cursor.fetchall()
        
        message = f"👥 УЧАСТНИКИ ПОДАРКА МЕСЯЦА\n"
        message += f"📅 {current_month}\n\n"
        
        if not participants:
            message += "Пока никто не зарегистрировался.\n"
            message += "Отправьте анонс в чат!"
        else:
            min_msg = gift['condition_min_messages']
            qualified = 0
            
            for idx, p in enumerate(participants, 1):
                name = p['username'] or p['first_name'] or 'Unknown'
                msgs = self._get_user_messages_this_month(p['user_id'])
                is_q = msgs >= min_msg
                if is_q:
                    qualified += 1
                
                status = "✅" if is_q else "⏳"
                message += f"{idx}. {status} @{name} — {msgs} сообщ.\n"
                
                if len(message) > 3500:
                    message += f"\n... и ещё {len(participants) - idx} участников"
                    break
            
            message += f"\n📊 Итого: {len(participants)} зарегистрировано, {qualified} прошли порог ({min_msg} сообщ.)"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="monthly_gift_participants")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_monthly_gift")]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ──────────────────────────────────────
    # OWNER: Анонс в чат
    # ──────────────────────────────────────
    
    async def monthly_gift_announce(self, query, user, context):
        """Announce monthly gift in chat"""
        if user.id != self.main_admin_id:
            return
        
        gift, current_month = self._get_current_gift()
        if not gift or gift['status'] != 'active':
            await query.answer("Нет активного подарка для анонса", show_alert=True)
            return
        
        type_labels = {'pulses': '💎 Пульсы', 'title': '👑 VIP-титул + Пульсы', 'custom': '🎯 Особый приз + Пульсы'}
        cond_labels = {
            'random': '🎲 Случайный розыгрыш среди участников',
            'weighted': '⚖️ Чем больше сообщений — тем выше шансы!',
            'top_active': '🏆 Побеждает самый активный!'
        }
        
        participants = self._get_gift_participants_count(gift['id'])
        
        announce = "🎁✨ ПОДАРОК МЕСЯЦА ✨🎁\n\n"
        announce += f"🏆 Приз: {type_labels.get(gift['prize_type'], '💎 Пульсы')}\n"
        announce += f"💰 Сумма: {format_number(gift['prize_amount'])} Пульсов\n\n"
        announce += f"📋 Условия:\n"
        announce += f"   {cond_labels.get(gift['condition_type'], '')}\n"
        
        if gift['condition_min_messages'] > 0:
            announce += f"   ✉️ Минимум {gift['condition_min_messages']} сообщений за месяц\n"
        
        announce += f"\n👥 Уже участвуют: {participants} чел.\n\n"
        announce += "Напишите боту /menu → Активности → 🎁 Подарок месяца\n"
        announce += "и нажмите «Участвовать»! 🚀"
        
        try:
            await context.bot.send_message(
                chat_id=self.target_chat_id,
                text=announce
            )
            
            self.db.cursor.execute('''
                UPDATE monthly_gifts SET announced_in_chat = 1 WHERE id = ?
            ''', (gift['id'],))
            self.db.conn.commit()
            
            await query.answer("✅ Анонс отправлен в чат!", show_alert=True)
        except Exception as e:
            await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
        
        await self.show_monthly_gift_menu(query, user, context)
    
    # ──────────────────────────────────────
    # OWNER: Подтверждение + Розыгрыш
    # ──────────────────────────────────────
    
    async def monthly_gift_confirm_draw(self, query, user, context):
        """Ask for confirmation before draw"""
        if user.id != self.main_admin_id:
            return
        
        gift, current_month = self._get_current_gift()
        if not gift or gift['status'] != 'active':
            await query.answer("Нет активного подарка", show_alert=True)
            return
        
        participants = self._get_gift_participants_count(gift['id'])
        
        # Count qualified
        min_msg = gift['condition_min_messages']
        self.db.cursor.execute('''
            SELECT p.user_id FROM monthly_gift_participants p WHERE p.gift_id = ?
        ''', (gift['id'],))
        all_p = self.db.cursor.fetchall()
        qualified = sum(1 for p in all_p if self._get_user_messages_this_month(p['user_id']) >= min_msg)
        
        message = "⚠️ ПОДТВЕРЖДЕНИЕ РОЗЫГРЫША\n\n"
        message += f"🎁 Приз: {format_number(gift['prize_amount'])} Пульсов\n"
        message += f"👥 Зарегистрировано: {participants}\n"
        message += f"✅ Прошли порог: {qualified}\n\n"
        
        if qualified == 0:
            message += "❌ Нет участников, прошедших порог!\n"
            message += "Розыгрыш невозможен."
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu_monthly_gift")]]
        else:
            message += "Провести розыгрыш? Это действие необратимо."
            keyboard = [
                [InlineKeyboardButton("🎲 ДА, РАЗЫГРАТЬ!", callback_data="monthly_gift_draw")],
                [InlineKeyboardButton("🔙 Отмена", callback_data="menu_monthly_gift")]
            ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def handle_monthly_gift_draw(self, query, user, context):
        """Execute the actual draw"""
        if user.id != self.main_admin_id:
            await query.answer("У вас нет доступа к этой функции.", show_alert=True)
            return
        
        enabled = int(self.db.get_setting('monthly_gift_enabled', '1'))
        if not enabled:
            await query.answer("❌ Функция отключена!", show_alert=True)
            return
        
        gift, current_month = self._get_current_gift()
        
        if not gift or gift['status'] != 'active':
            await query.answer("❌ Нет активного подарка для розыгрыша!", show_alert=True)
            return
        
        min_msg = gift['condition_min_messages']
        condition_type = gift['condition_type']
        
        # Get qualified participants
        self.db.cursor.execute('''
            SELECT p.user_id, u.username, u.first_name
            FROM monthly_gift_participants p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.gift_id = ?
        ''', (gift['id'],))
        all_participants = self.db.cursor.fetchall()
        
        # Filter by message count
        qualified = []
        for p in all_participants:
            msgs = self._get_user_messages_this_month(p['user_id'])
            if msgs >= min_msg:
                qualified.append({
                    'user_id': p['user_id'],
                    'username': p['username'] or p['first_name'] or 'Unknown',
                    'messages': msgs
                })
        
        # If no registered participants qualify, fallback to all active users
        if not qualified:
            from datetime import datetime
            month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            self.db.cursor.execute('''
                SELECT DISTINCT m.user_id, u.username, u.first_name, COUNT(m.id) as msg_count
                FROM messages m
                JOIN users u ON m.user_id = u.user_id
                WHERE m.timestamp >= ?
                    AND u.is_admin = 0 AND u.is_owner = 0
                GROUP BY m.user_id
                HAVING msg_count >= ?
            ''', (month_start, min_msg))
            
            fallback_users = self.db.cursor.fetchall()
            
            if not fallback_users:
                await query.answer("❌ Нет подходящих пользователей!", show_alert=True)
                return
            
            for u in fallback_users:
                qualified.append({
                    'user_id': u['user_id'],
                    'username': u['username'] or u['first_name'] or 'Unknown',
                    'messages': u['msg_count']
                })
        
        # Select winner based on condition type
        import random
        
        if condition_type == 'random':
            winner = random.choice(qualified)
        
        elif condition_type == 'weighted':
            # Weight by message count
            total_msgs = sum(q['messages'] for q in qualified)
            if total_msgs == 0:
                winner = random.choice(qualified)
            else:
                weights = [q['messages'] / total_msgs for q in qualified]
                winner = random.choices(qualified, weights=weights, k=1)[0]
        
        elif condition_type == 'top_active':
            # Most active wins
            winner = max(qualified, key=lambda q: q['messages'])
        
        else:
            winner = random.choice(qualified)
        
        winner_id = winner['user_id']
        winner_username = winner['username']
        gift_amount = gift['prize_amount']

        # Master-switch раздела «🎁 Подарок месяца»
        try:
            if not self.db.is_econ_section_enabled('monthly_gift'):
                await query.edit_message_text(
                    "⏸ Раздел «Подарок месяца» временно отключён в панели экономики.")
                return
        except Exception:
            pass

        # Award the prize (from bank) — банк своего workspace
        bank_balance = self.db.get_bank_balance(ws_id=self.ws_id)
        if bank_balance < gift_amount:
            await query.edit_message_text(
                f"❌ Недостаточно средств в Банке!\n"
                f"🏦 В банке: {format_number(bank_balance)} 💎\n"
                f"🎁 Нужно: {format_number(gift_amount)} 💎")
            return

        self.db.update_bank_balance(gift_amount, 'subtract', ws_id=self.ws_id)
        self.db.update_user_balance(winner_id, gift_amount, 'add')
        self.db.add_transaction(
            None,
            winner_id,
            gift_amount,
            'monthly_gift',
            f'Monthly gift winner - {current_month}'
        )
        
        # Update gift record
        self.db.cursor.execute('''
            UPDATE monthly_gifts 
            SET winner_id = ?, awarded_by = ?, status = 'completed', 
                awarded_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (winner_id, user.id, gift['id']))
        self.db.conn.commit()
        
        # Grant VIP title if prize type is 'title'
        if gift['prize_type'] == 'title':
            try:
                from datetime import datetime, timedelta
                expires = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
                self.db.cursor.execute('''
                    INSERT INTO titles (user_id, title_name, emoji, multiplier, expires_at, granted_by)
                    VALUES (?, '🎁 Везунчик месяца', '🎁', 1.5, ?, ?)
                ''', (winner_id, expires, user.id))
                self.db.conn.commit()
            except Exception:
                pass
        
        # Announce in chat
        cond_labels = {
            'random': '🎲 Случайный розыгрыш',
            'weighted': '⚖️ Взвешенный по активности',
            'top_active': '🏆 Самый активный'
        }
        
        chat_message = "🎁✨ ПОДАРОК МЕСЯЦА — РОЗЫГРЫШ! ✨🎁\n\n"
        chat_message += f"🎉 Победитель: @{winner_username}\n"
        chat_message += f"💎 Награда: {format_number(gift_amount)} Пульсов\n"
        
        if gift['prize_type'] == 'title':
            chat_message += f"👑 + VIP-титул «Везунчик месяца» на 30 дней!\n"
        
        chat_message += f"\n📊 Режим: {cond_labels.get(condition_type, condition_type)}\n"
        chat_message += f"👥 Участвовало: {len(qualified)} чел.\n"
        chat_message += f"✉️ Сообщений победителя: {winner['messages']}\n\n"
        chat_message += "Поздравляем! 🎊🎊🎊"
        
        try:
            await context.bot.send_message(chat_id=self.target_chat_id, text=chat_message)
        except Exception:
            pass
        
        # Notify winner personally
        try:
            pm = "🎁🎉 ПОЗДРАВЛЯЕМ!\n\n"
            pm += f"Вы выиграли Подарок месяца ({current_month})!\n"
            pm += f"💎 Начислено: {format_number(gift_amount)} Пульсов\n"
            if gift['prize_type'] == 'title':
                pm += f"👑 Вам присвоен VIP-титул «Везунчик месяца»!\n"
            pm += "\nСпасибо за активность! 🚀"
            await context.bot.send_message(chat_id=winner_id, text=pm)
        except Exception:
            pass
        
        # Show result to owner
        result_msg = "✅ РОЗЫГРЫШ ПРОВЕДЁН!\n\n"
        result_msg += f"🎉 Победитель: @{winner_username}\n"
        result_msg += f"💎 Награда: {format_number(gift_amount)} Пульсов\n"
        result_msg += f"👥 Участвовало: {len(qualified)} чел.\n"
        result_msg += f"✉️ Сообщений: {winner['messages']}"
        
        keyboard = [[InlineKeyboardButton("🔙 К управлению", callback_data="menu_monthly_gift")]]
        
        await query.edit_message_text(result_msg, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ──────────────────────────────────────
    # OWNER: Toggle / History
    # ──────────────────────────────────────
    
    async def handle_monthly_gift_toggle(self, query, user, context):
        """Toggle monthly gift feature on/off"""
        if user.id != self.main_admin_id:
            await query.answer("У вас нет доступа к этой функции.", show_alert=True)
            return

        current = int(self.db.get_setting('monthly_gift_enabled', '1'))
        new_value = 0 if current == 1 else 1

        self.db.set_setting('monthly_gift_enabled', str(new_value))

        status = "✅ Включена" if new_value == 1 else "❌ Отключена"
        await query.answer(f"Функция {status}", show_alert=True)

        await self.show_monthly_gift_menu(query, user, context)
    
    async def show_monthly_gift_history(self, query, user):
        """Show monthly gift history — available to all"""
        self.db.cursor.execute('''
            SELECT mg.month, mg.prize_amount, mg.prize_type, mg.condition_type,
                   mg.awarded_at, mg.status, u.username, u.first_name
            FROM monthly_gifts mg
            LEFT JOIN users u ON mg.winner_id = u.user_id
            WHERE mg.workspace_id = ?
            ORDER BY mg.created_at DESC
            LIMIT 12
        ''', (self.ws_id,))
        
        history = self.db.cursor.fetchall()
        
        type_emojis = {'pulses': '💎', 'title': '👑', 'custom': '🎯'}
        
        if not history:
            message = "📊 ИСТОРИЯ РОЗЫГРЫШЕЙ\n\nПока розыгрышей не было"
        else:
            message = "📊 ИСТОРИЯ РОЗЫГРЫШЕЙ\n\n"
            for idx, record in enumerate(history, 1):
                month = record['month']
                amount = format_number(record['prize_amount'])
                emoji = type_emojis.get(record['prize_type'], '💎')
                
                if record['status'] == 'completed' and record['username']:
                    username = record['username'] or record['first_name']
                    message += f"{idx}. {month} — {emoji} {amount} Пульсов\n"
                    message += f"   🏆 @{username}\n\n"
                elif record['status'] == 'active':
                    message += f"{idx}. {month} — {emoji} {amount} Пульсов\n"
                    message += f"   ⏳ Ожидает розыгрыша\n\n"
                else:
                    message += f"{idx}. {month} — отменён\n\n"
        
        is_owner = user.id == self.main_admin_id
        back_cb = "menu_monthly_gift" if is_owner else "monthly_gift_user_view"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=back_cb)]]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ══════════════════════════════════════════════
    # 🎁 ПОДАРОК МЕСЯЦА — ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ
    # ══════════════════════════════════════════════
    
    async def show_monthly_gift_user(self, query, user):
        """Show monthly gift info card for regular user"""
        gift, current_month = self._get_current_gift()
        
        type_labels = {'pulses': '💎 Пульсы', 'title': '👑 VIP-титул + Пульсы', 'custom': '🎯 Особый приз + Пульсы'}
        cond_labels = {
            'random': '🎲 Равные шансы у всех',
            'weighted': '⚖️ Больше сообщений = больше шансов',
            'top_active': '🏆 Побеждает самый активный'
        }
        
        message = "🎁 ПОДАРОК МЕСЯЦА\n"
        message += f"📅 {current_month}\n\n"
        
        keyboard = []
        
        if not gift or gift['status'] != 'active':
            if gift and gift['status'] == 'completed' and gift['winner_id']:
                winner = self.db.get_user(gift['winner_id'])
                w_name = (winner['username'] or winner['first_name'] or str(gift['winner_id'])) if winner else str(gift['winner_id'])
                message += f"🏆 В этом месяце победил: @{w_name}\n"
                message += f"💎 Приз: {format_number(gift['prize_amount'])} Пульсов\n\n"
                
                if gift['winner_id'] == user.id:
                    message += "🎉 Это вы! Поздравляем!\n"
                
                message += "Следующий розыгрыш — в следующем месяце!"
            else:
                message += "📭 Подарок на этот месяц пока не объявлен.\n"
                message += "Следите за анонсами в чате!"
        else:
            # Active gift — show details
            participants = self._get_gift_participants_count(gift['id'])
            user_msgs = self._get_user_messages_this_month(user.id)
            min_msgs = gift['condition_min_messages']
            is_participating = self._is_user_participating(gift['id'], user.id)
            is_qualified = user_msgs >= min_msgs
            
            message += f"🏆 Приз: {type_labels.get(gift['prize_type'], '💎 Пульсы')}\n"
            message += f"💰 Сумма: {format_number(gift['prize_amount'])} Пульсов\n\n"
            message += f"📋 Режим: {cond_labels.get(gift['condition_type'], '')}\n"
            
            if min_msgs > 0:
                bar = self._make_progress_bar(user_msgs, min_msgs)
                message += f"\n✉️ Ваш прогресс: {user_msgs}/{min_msgs} сообщений\n"
                message += f"[{bar}] {'✅' if is_qualified else '⏳'}\n"
            
            message += f"\n👥 Участников: {participants}\n"
            
            if is_participating:
                message += "\n✅ Вы участвуете!"
                if not is_qualified and min_msgs > 0:
                    remaining = min_msgs - user_msgs
                    message += f"\n⏳ Осталось {remaining} сообщений для квалификации"
            else:
                message += "\n❓ Вы ещё не участвуете"
            
            # Buttons for users
            if not is_participating:
                keyboard.append([InlineKeyboardButton("✋ Участвовать!", callback_data="monthly_gift_participate")])
            
            keyboard.append([InlineKeyboardButton("📊 Мой прогресс", callback_data="monthly_gift_my_progress")])
        
        keyboard.append([InlineKeyboardButton("📜 История победителей", callback_data="monthly_gift_winners")])
        keyboard.append([InlineKeyboardButton("🔙 Активности", callback_data="menu_activities")])
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def monthly_gift_participate(self, query, user):
        """Register user as participant"""
        gift, current_month = self._get_current_gift()
        
        if not gift or gift['status'] != 'active':
            await query.answer("❌ Сейчас нет активного подарка", show_alert=True)
            return
        
        if self._is_user_participating(gift['id'], user.id):
            await query.answer("Вы уже участвуете! ✅", show_alert=True)
            return
        
        # Check user is not admin/owner
        user_data = self.db.get_user(user.id)
        if user_data and (user_data['is_admin'] or user_data['is_owner']):
            await query.answer("❌ Администраторы не могут участвовать", show_alert=True)
            return
        
        msgs = self._get_user_messages_this_month(user.id)
        
        try:
            self.db.cursor.execute('''
                INSERT INTO monthly_gift_participants (gift_id, user_id, messages_at_register, is_qualified)
                VALUES (?, ?, ?, ?)
            ''', (gift['id'], user.id, msgs, 1 if msgs >= gift['condition_min_messages'] else 0))
            self.db.conn.commit()
            
            await query.answer("🎉 Вы зарегистрированы! Удачи!", show_alert=True)
        except Exception:
            await query.answer("Вы уже участвуете! ✅", show_alert=True)
        
        # Refresh the user view
        await self.show_monthly_gift_user(query, user)
    
    async def monthly_gift_my_progress(self, query, user):
        """Show detailed progress for the user"""
        gift, current_month = self._get_current_gift()
        
        user_msgs = self._get_user_messages_this_month(user.id)
        
        message = "📊 МОЙ ПРОГРЕСС — ПОДАРОК МЕСЯЦА\n"
        message += f"📅 {current_month}\n\n"
        
        if gift and gift['status'] == 'active':
            min_msgs = gift['condition_min_messages']
            is_participating = self._is_user_participating(gift['id'], user.id)
            is_qualified = user_msgs >= min_msgs
            
            message += f"✉️ Сообщений за месяц: {user_msgs}\n"
            
            if min_msgs > 0:
                bar = self._make_progress_bar(user_msgs, min_msgs)
                pct = min(100, (user_msgs / max(1, min_msgs)) * 100)
                message += f"📊 Прогресс: [{bar}] {pct:.0f}%\n"
                message += f"🎯 Порог: {min_msgs} сообщений\n\n"
            
            if is_qualified:
                message += "✅ Вы квалифицированы!\n"
            else:
                remaining = max(0, min_msgs - user_msgs)
                message += f"⏳ До квалификации: ещё {remaining} сообщений\n"
            
            if is_participating:
                message += "\n🎫 Статус: Участвуете"
            else:
                message += "\n❌ Статус: Не участвуете (нажмите «Участвовать»)"
            
            # Show chances for weighted mode
            if gift['condition_type'] == 'weighted' and is_participating:
                self.db.cursor.execute('''
                    SELECT p.user_id FROM monthly_gift_participants p WHERE p.gift_id = ?
                ''', (gift['id'],))
                all_p = self.db.cursor.fetchall()
                total_msgs = sum(self._get_user_messages_this_month(p['user_id']) for p in all_p)
                if total_msgs > 0:
                    chance = (user_msgs / total_msgs) * 100
                    message += f"\n🎲 Ваши шансы: ~{chance:.1f}%"
        else:
            message += f"✉️ Сообщений за месяц: {user_msgs}\n\n"
            message += "📭 Сейчас нет активного подарка"
        
        keyboard = [
            [InlineKeyboardButton("🔙 К подарку", callback_data="monthly_gift_user_view")],
            [InlineKeyboardButton("🔙 Активности", callback_data="menu_activities")]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ══════════════════════════════════════════════
    # РОУТЕР
    # ══════════════════════════════════════════════

    async def handle_callback(self, query, data, user, context):
        """Единая точка входа для всех monthly_gift_* и mgift_* колбэков."""
        is_owner = (user.id == self.main_admin_id)

        if data == "menu_monthly_gift":
            if is_owner:
                await self.show_monthly_gift_menu(query, user, context)
            else:
                await self.show_monthly_gift_user(query, user)
        elif data == "monthly_gift_create":
            await self.monthly_gift_create_start(query, user, context)
        elif data.startswith("mgift_set_amount_"):
            await self.monthly_gift_set_amount(query, data, user, context)
        elif data.startswith("mgift_set_type_"):
            await self.monthly_gift_set_type(query, data, user, context)
        elif data.startswith("mgift_set_cond_"):
            await self.monthly_gift_set_condition(query, data, user, context)
        elif data.startswith("mgift_set_minmsg_"):
            await self.monthly_gift_set_min_messages(query, data, user, context)
        elif data == "monthly_gift_toggle":
            await self.handle_monthly_gift_toggle(query, user, context)
        elif data == "monthly_gift_history":
            await self.show_monthly_gift_history(query, user)
        elif data == "monthly_gift_participants":
            await self.show_monthly_gift_participants(query, user)
        elif data == "monthly_gift_announce":
            await self.monthly_gift_announce(query, user, context)
        elif data == "monthly_gift_confirm_draw":
            await self.monthly_gift_confirm_draw(query, user, context)
        elif data == "monthly_gift_draw":
            await self.handle_monthly_gift_draw(query, user, context)
        elif data == "monthly_gift_user_view":
            await self.show_monthly_gift_user(query, user)
        elif data == "monthly_gift_participate":
            await self.monthly_gift_participate(query, user)
        elif data == "monthly_gift_my_progress":
            await self.monthly_gift_my_progress(query, user)
        elif data == "monthly_gift_winners":
            await self.show_monthly_gift_winners(query, user)

    async def show_monthly_gift_winners(self, query, user):
        """Show past winners — public view"""
        self.db.cursor.execute('''
            SELECT mg.month, mg.prize_amount, mg.prize_type, u.username, u.first_name
            FROM monthly_gifts mg
            JOIN users u ON mg.winner_id = u.user_id
            WHERE mg.status = 'completed' AND mg.workspace_id = ?
            ORDER BY mg.awarded_at DESC
            LIMIT 12
        ''', (self.ws_id,))
        
        history = self.db.cursor.fetchall()
        type_emojis = {'pulses': '💎', 'title': '👑', 'custom': '🎯'}
        
        if not history:
            message = "🏆 ПОБЕДИТЕЛИ ПОДАРКА МЕСЯЦА\n\nПока победителей нет. Будьте первым!"
        else:
            message = "🏆 ПОБЕДИТЕЛИ ПОДАРКА МЕСЯЦА\n\n"
            for idx, record in enumerate(history, 1):
                username = record['username'] or record['first_name']
                emoji = type_emojis.get(record['prize_type'], '💎')
                message += f"{idx}. {record['month']} — @{username}\n"
                message += f"   {emoji} {format_number(record['prize_amount'])} Пульсов\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🔙 К подарку", callback_data="monthly_gift_user_view")],
            [InlineKeyboardButton("🔙 Активности", callback_data="menu_activities")]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
