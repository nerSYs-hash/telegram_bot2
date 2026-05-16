#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Обработчики донатов — вынесены из callback_handler.py

Все функции — модульного уровня (без класса).
Параметр db передаётся явно вместо self.db.

Использование в callback_handler.py:
    from handlers.donate_handlers import (
        safe_name, show_donate_menu, donate_to_user_start, donate_pick_user,
        donate_user_amount, donate_user_custom, donate_user_confirm,
        donate_to_bank_start, donate_bank_custom, donate_bank_amount,
        donate_bank_confirm, donate_show_history,
    )
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import format_number, get_today_date_msk
from bot_core.workspace_context import pulse_only  # V1.17.0a21 multi-tenancy gating


def safe_name(user_data):
    """Безопасное имя — никогда не None"""
    if not user_data:
        return "Unknown"
    name = user_data.get('username') if hasattr(user_data, 'get') else (user_data['username'] if user_data['username'] else None)
    if not name:
        name = user_data.get('first_name') if hasattr(user_data, 'get') else (user_data['first_name'] if user_data['first_name'] else None)
    if not name or str(name).strip() == '' or str(name) == 'None':
        uid = user_data.get('user_id') if hasattr(user_data, 'get') else user_data['user_id']
        return f"ID:{uid}"
    return str(name)

# ═══════════════════════════════════════════
# СИСТЕМА ДОНАТОВ
# ═══════════════════════════════════════════

async def show_donate_menu(query, user, db):
    """Главное меню донатов"""
    user_data = db.get_user(user.id)
    if not user_data:
        await query.edit_message_text("Сначала используй /start")
        return
    if not db.is_feature_enabled('donate'):
        await query.answer("⛔ Донаты отключены.", show_alert=True)
        return
    
    message = (
        f"🎁 СИСТЕМА ДОНАТОВ\n\n"
        f"💰 Ваш баланс: {format_number(user_data['balance'])} 💎\n\n"
        f"Выберите действие:"
    )
    keyboard = [
        [InlineKeyboardButton("🎁 Пользователю", callback_data="donate_to_user_start")],
        [InlineKeyboardButton("🏦 В Центробанк", callback_data="donate_to_bank_start")],
        [InlineKeyboardButton("📜 Мои донаты", callback_data="donate_history")],
        [InlineKeyboardButton("🔙 Меню", callback_data="back_to_menu")]
    ]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

# ─── Донат пользователю ───

@pulse_only
async def donate_to_user_start(query, user, context, db):
    """Умное меню переводов — выбор категории получателя"""
    user_data = db.get_user(user.id)
    if not user_data:
        await query.edit_message_text("Сначала используй /start")
        return

    # Сбрасываем возможный «висящий» FSM ручного ввода
    context.user_data.pop('awaiting_donate_manual_user', None)

    message = (
        f"💸 КОМУ ОТПРАВИТЬ ДОНАТ?\n\n"
        f"💰 Ваш баланс: {format_number(user_data['balance'])} 💎\n\n"
        f"Выберите, как найти получателя:"
    )
    keyboard = [
        [InlineKeyboardButton("🔄 Недавние переводы", callback_data="donate_cat_recent")],
        [InlineKeyboardButton("🌟 Топ Активистов (сегодня)", callback_data="donate_cat_activists")],
        [InlineKeyboardButton("🆘 Помощь малоимущим", callback_data="donate_cat_poor")],
        [InlineKeyboardButton("✍️ Ввести ник/ID вручную", callback_data="donate_cat_manual")],
        [InlineKeyboardButton("🔙 Назад", callback_data="donate_menu")],
    ]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


@pulse_only
async def donate_cat_recent(query, user, context, db):
    """Категория: последние 5 уникальных получателей моих донатов."""
    user_data = db.get_user(user.id)
    if not user_data:
        await query.edit_message_text("Сначала используй /start")
        return

    db.cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, u.is_admin, u.is_owner,
               MAX(t.timestamp) AS last_ts
        FROM transactions t
        JOIN users u ON u.user_id = t.to_user_id
        WHERE t.from_user_id = ?
          AND t.transaction_type = 'donate_to_user'
          AND t.to_user_id IS NOT NULL
          AND t.to_user_id != ?
        GROUP BY u.user_id
        ORDER BY last_ts DESC
        LIMIT 5
    ''', (user.id, user.id))
    rows = db.cursor.fetchall()

    keyboard = []
    if not rows:
        message = (
            f"🔄 НЕДАВНИЕ ПЕРЕВОДЫ\n\n"
            f"Вы ещё никому не отправляли донаты.\n"
            f"Выберите другую категорию или введите ник вручную."
        )
    else:
        message = (
            f"🔄 НЕДАВНИЕ ПЕРЕВОДЫ\n\n"
            f"💰 Баланс: {format_number(user_data['balance'])} 💎\n\n"
            f"Кому вы отправляли последний раз:"
        )
        for u in rows:
            name = safe_name(u)
            label = f"@{name}"
            if u['is_owner']:
                label += " 👑"
            elif u['is_admin']:
                label += " ⭐"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"donate_pick_user_{u['user_id']}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="donate_to_user_start")])
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


@pulse_only
async def donate_cat_activists(query, user, context, db):
    """Категория: Топ-5 активистов сегодня."""
    user_data = db.get_user(user.id)
    if not user_data:
        await query.edit_message_text("Сначала используй /start")
        return

    today = get_today_date_msk()
    db.cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, u.is_admin, u.is_owner,
               us.total_messages, us.activity_score
        FROM user_stats us
        JOIN users u ON u.user_id = us.user_id
        WHERE us.date = ?
          AND us.total_messages > 0
          AND u.is_left = 0
          AND u.user_id != ?
        ORDER BY us.activity_score DESC, us.total_messages DESC
        LIMIT 5
    ''', (today, user.id))
    rows = db.cursor.fetchall()

    keyboard = []
    if not rows:
        message = (
            f"🌟 ТОП АКТИВИСТОВ (сегодня)\n\n"
            f"Сегодня ещё никто активно не писал в чат."
        )
    else:
        message = (
            f"🌟 ТОП АКТИВИСТОВ ЗА СЕГОДНЯ\n\n"
            f"💰 Баланс: {format_number(user_data['balance'])} 💎\n\n"
            f"Поощри тех, кто двигает чат:"
        )
        for u in rows:
            name = safe_name(u)
            msgs = int(u['total_messages']) if u['total_messages'] else 0
            label = f"🌟 @{name} · {msgs} 💬"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"donate_pick_user_{u['user_id']}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="donate_to_user_start")])
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


@pulse_only
async def donate_cat_poor(query, user, context, db):
    """Категория: Топ-5 малоимущих (без админов, активные за 7 дней)."""
    user_data = db.get_user(user.id)
    if not user_data:
        await query.edit_message_text("Сначала используй /start")
        return

    db.cursor.execute('''
        SELECT user_id, username, first_name, balance
        FROM users
        WHERE is_admin = 0
          AND is_owner = 0
          AND is_left = 0
          AND user_id != ?
          AND last_active >= datetime('now', '-7 days')
        ORDER BY balance ASC
        LIMIT 5
    ''', (user.id,))
    rows = db.cursor.fetchall()

    keyboard = []
    if not rows:
        message = (
            f"🆘 ПОМОЩЬ МАЛОИМУЩИМ\n\n"
            f"Не нашлось подходящих получателей (нужны активные за 7 дней)."
        )
    else:
        message = (
            f"🆘 ПОМОЩЬ МАЛОИМУЩИМ\n\n"
            f"💰 Ваш баланс: {format_number(user_data['balance'])} 💎\n\n"
            f"Поделись пульсами с теми, у кого их меньше всего:"
        )
        for u in rows:
            name = safe_name(u)
            bal = float(u['balance']) if u['balance'] is not None else 0.0
            label = f"🆘 @{name} · {format_number(bal)} 💎"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"donate_pick_user_{u['user_id']}")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="donate_to_user_start")])
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


@pulse_only
async def donate_cat_manual(query, user, context, db):
    """Категория: ручной ввод @username или ID."""
    user_data = db.get_user(user.id)
    if not user_data:
        await query.edit_message_text("Сначала используй /start")
        return

    context.user_data['awaiting_donate_manual_user'] = True
    # На всякий случай чистим возможный остаток FSM суммы
    context.user_data.pop('awaiting_donate_amount', None)
    context.user_data.pop('donate_custom_target_id', None)

    message = (
        f"✍️ ВВЕДИТЕ ПОЛУЧАТЕЛЯ\n\n"
        f"Отправьте сообщением:\n"
        f"  • @username  (например: @ivan)\n"
        f"  • или ID пользователя (только цифры)\n\n"
        f"Для отмены — /cancel."
    )
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="donate_to_user_start")]]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


@pulse_only
async def handle_manual_donate_user(message, context, db):
    """Обработка ручного ввода @username или ID для доната.

    Возвращает True, если ввод обработан (успешно или с понятной ошибкой),
    и False, если FSM-флаг уже не активен (на всякий случай).
    """
    if not context.user_data.get('awaiting_donate_manual_user'):
        return False

    text = (message.text or '').strip()

    if text == '/cancel':
        context.user_data.pop('awaiting_donate_manual_user', None)
        await message.reply_text("Поиск получателя отменён.")
        return True

    if not text:
        await message.reply_text("Пусто. Введите @username или ID, либо /cancel.")
        return True

    target = None
    if text.startswith('@') or not text.lstrip('-').isdigit():
        # Поиск по username (без @, без учёта регистра)
        clean = text.lstrip('@').lower()
        db.cursor.execute('SELECT * FROM users WHERE LOWER(username) = ?', (clean,))
        target = db.cursor.fetchone()
    else:
        try:
            uid = int(text)
            target = db.get_user(uid)
        except ValueError:
            target = None

    if not target:
        await message.reply_text(
            "❌ Пользователь не найден.\n"
            "Попробуйте ещё раз или нажмите /cancel."
        )
        return True

    # tg-объект Row → dict-подобный; user_id и username доступны как [..]
    target_user_id = target['user_id'] if hasattr(target, '__getitem__') else target.get('user_id')
    if target_user_id == message.from_user.id:
        await message.reply_text("Нельзя донатить самому себе. Введите другого получателя или /cancel.")
        return True

    context.user_data.pop('awaiting_donate_manual_user', None)

    user_data = db.get_user(message.from_user.id)
    target_name = safe_name(target)
    balance = float(user_data['balance']) if user_data else 0.0

    text_msg = (
        f"🎁 ДОНАТ ДЛЯ @{target_name}\n\n"
        f"💰 Баланс: {format_number(balance)} 💎\n\n"
        f"Выберите сумму:"
    )
    amounts = [10, 25, 50, 100, 250, 500, 1000]
    keyboard = []
    row = []
    for amt in amounts:
        if balance >= amt:
            row.append(InlineKeyboardButton(
                f"{format_number(amt)} 💎",
                callback_data=f"donate_user_amount_{target_user_id}_{amt}"
            ))
            if len(row) == 3:
                keyboard.append(row)
                row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("✏️ Своя сумма", callback_data=f"donate_user_custom_{target_user_id}")])
    keyboard.append([InlineKeyboardButton("🔙 К меню донатов", callback_data="donate_to_user_start")])

    await message.reply_text(text_msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return True

@pulse_only
async def donate_pick_user(query, data, user, context, db):
    """Выбор суммы для доната пользователю"""
    target_user_id = int(data.replace("donate_pick_user_", ""))
    target_user = db.get_user(target_user_id)
    user_data = db.get_user(user.id)
    if not target_user or not user_data:
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    
    target_name = safe_name(target_user)
    balance = float(user_data['balance'])
    
    message = f"🎁 ДОНАТ ДЛЯ @{target_name}\n\n💰 Баланс: {format_number(balance)} 💎\n\nВыберите сумму:"
    
    amounts = [10, 25, 50, 100, 250, 500, 1000]
    keyboard = []
    row = []
    for amt in amounts:
        if balance >= amt:
            row.append(InlineKeyboardButton(f"{format_number(amt)} 💎", callback_data=f"donate_user_amount_{target_user_id}_{amt}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("✏️ Своя сумма", callback_data=f"donate_user_custom_{target_user_id}")])
    keyboard.append([InlineKeyboardButton("🔙 К списку", callback_data="donate_to_user_start")])
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

@pulse_only
async def donate_user_amount(query, data, user, context, db):
    """Подтверждение суммы доната пользователю"""
    parts = data.replace("donate_user_amount_", "").split("_")
    target_user_id = int(parts[0])
    amount = float(parts[1])
    
    target_user = db.get_user(target_user_id)
    user_data = db.get_user(user.id)
    if not target_user or not user_data:
        await query.answer("Ошибка.", show_alert=True)
        return
    if float(user_data['balance']) < amount:
        await query.answer("Недостаточно средств!", show_alert=True)
        return
    
    target_name = safe_name(target_user)
    message = (
        f"🎁 ПОДТВЕРЖДЕНИЕ\n\n"
        f"👤 Кому: @{target_name}\n"
        f"💎 Сумма: {format_number(amount)} Пульсов\n"
        f"💰 После: {format_number(float(user_data['balance']) - amount)} 💎\n\n"
        f"Подтвердить?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data=f"donate_user_confirm_{target_user_id}_{amount}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"donate_pick_user_{target_user_id}")]
    ]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

@pulse_only
async def donate_user_custom(query, data, user, context, db):
    """Ввод своей суммы для доната пользователю"""
    target_user_id = int(data.replace("donate_user_custom_", ""))
    target_user = db.get_user(target_user_id)
    if not target_user:
        await query.answer("Пользователь не найден.", show_alert=True)
        return
    
    target_name = safe_name(target_user)
    context.user_data['donate_custom_target_id'] = target_user_id
    context.user_data['awaiting_donate_amount'] = 'user'
    
    message = f"✏️ СВОЯ СУММА ДЛЯ @{target_name}\n\nОтправьте сумму числом (например: 12.50):"
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"donate_pick_user_{target_user_id}")]]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

@pulse_only
async def donate_user_confirm(query, data, user, context, db):
    """Выполнение доната пользователю"""
    parts = data.replace("donate_user_confirm_", "").split("_")
    target_user_id = int(parts[0])
    amount = round(float(parts[1]), 2)
    
    target_user = db.get_user(target_user_id)
    user_data = db.get_user(user.id)
    if not target_user or not user_data:
        await query.answer("Ошибка.", show_alert=True)
        return
    if float(user_data['balance']) < amount:
        await query.answer("Недостаточно средств!", show_alert=True)
        return
    
    db.update_user_balance(user.id, amount, 'subtract')
    db.update_user_balance(target_user_id, amount, 'add')
    
    target_name = safe_name(target_user)
    sender_name = safe_name(user_data)
    db.add_transaction(user.id, target_user_id, amount, 'donate_to_user', f'Донат для @{target_name}')
    
    new_balance = float(user_data['balance']) - amount
    message = (
        f"✅ ДОНАТ ОТПРАВЛЕН!\n\n"
        f"🎁 @{sender_name} → @{target_name}\n"
        f"💎 Сумма: {format_number(amount)} Пульсов\n"
        f"💰 Ваш баланс: {format_number(new_balance)} 💎"
    )
    keyboard = [
        [InlineKeyboardButton("🎁 Ещё донат", callback_data="donate_to_user_start")],
        [InlineKeyboardButton("🔙 Меню донатов", callback_data="donate_menu")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")]
    ]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🎁 Вам пришёл донат!\n\n👤 От: @{sender_name}\n💎 Сумма: {format_number(amount)} Пульсов"
        )
    except:
        pass

# ─── Донат в Центробанк ───

@pulse_only
async def donate_to_bank_start(query, user, context, db):
    """Выбор суммы для доната в банк"""
    user_data = db.get_user(user.id)
    if not user_data:
        await query.edit_message_text("Сначала используй /start")
        return
    
    balance = float(user_data['balance'])
    bank_balance = db.get_bank_balance()
    
    message = (
        f"🏦 ДОНАТ В ЦЕНТРОБАНК\n\n"
        f"💰 Ваш баланс: {format_number(balance)} 💎\n"
        f"🏦 Баланс банка: {format_number(bank_balance)} 💎\n\n"
        f"Выберите сумму:"
    )
    
    amounts = [10, 25, 50, 100, 250, 500, 1000]
    keyboard = []
    row = []
    for amt in amounts:
        if balance >= amt:
            row.append(InlineKeyboardButton(f"{format_number(amt)} 💎", callback_data=f"donate_bank_amount_{amt}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
    if row:
        keyboard.append(row)
    # ВСЕГДА показываем кнопку «Своя сумма»
    keyboard.append([InlineKeyboardButton("✏️ Своя сумма", callback_data="donate_bank_custom")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="donate_menu")])
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

@pulse_only
async def donate_bank_custom(query, user, context, db):
    """Ввод своей суммы для банка"""
    context.user_data['awaiting_donate_amount'] = 'bank'
    message = "✏️ СВОЯ СУММА В ЦЕНТРОБАНК\n\nОтправьте сумму числом (например: 12.50):"
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="donate_to_bank_start")]]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

@pulse_only
async def donate_bank_amount(query, data, user, context, db):
    """Подтверждение суммы доната в банк"""
    amount = float(data.replace("donate_bank_amount_", ""))
    user_data = db.get_user(user.id)
    if not user_data or float(user_data['balance']) < amount:
        await query.answer("Недостаточно средств!", show_alert=True)
        return
    
    message = (
        f"🏦 ПОДТВЕРЖДЕНИЕ\n\n"
        f"💎 Сумма: {format_number(amount)} Пульсов\n"
        f"💰 После: {format_number(float(user_data['balance']) - amount)} 💎\n\nПодтвердить?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data=f"donate_bank_confirm_{amount}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="donate_to_bank_start")]
    ]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

@pulse_only
async def donate_bank_confirm(query, data, user, context, db):
    """Выполнение доната в банк"""
    amount = round(float(data.replace("donate_bank_confirm_", "")), 2)
    user_data = db.get_user(user.id)
    if not user_data or float(user_data['balance']) < amount:
        await query.answer("Недостаточно средств!", show_alert=True)
        return
    
    db.update_user_balance(user.id, amount, 'subtract')
    db.update_bank_balance(amount, 'add')
    db.add_transaction(user.id, None, amount, 'donate_to_bank', 'Донат в Центробанк')
    
    sender_name = safe_name(user_data)
    message = (
        f"✅ ДОНАТ В БАНК!\n\n"
        f"👤 От: @{sender_name}\n"
        f"💎 Сумма: {format_number(amount)} Пульсов\n"
        f"🏦 Банк: {format_number(db.get_bank_balance())} 💎\n"
        f"💰 Баланс: {format_number(float(user_data['balance']) - amount)} 💎"
    )
    keyboard = [
        [InlineKeyboardButton("🏦 Ещё в банк", callback_data="donate_to_bank_start")],
        [InlineKeyboardButton("🔙 Меню донатов", callback_data="donate_menu")]
    ]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

# ─── История донатов ───

async def donate_show_history(query, user, db):
    """История донатов пользователя"""
    # Итоги отправленных
    db.cursor.execute('''
        SELECT
            COALESCE(SUM(CASE WHEN transaction_type = 'donate_to_user' THEN amount ELSE 0 END), 0) as sent_users,
            COALESCE(SUM(CASE WHEN transaction_type = 'donate_to_bank' THEN amount ELSE 0 END), 0) as sent_bank
        FROM transactions
        WHERE from_user_id = ?
          AND transaction_type IN ('donate_to_user', 'donate_to_bank')
    ''', (user.id,))
    sent = db.cursor.fetchone()
    
    # Итого получено
    db.cursor.execute('''
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE to_user_id = ? AND transaction_type = 'donate_to_user'
    ''', (user.id,))
    received_total = db.cursor.fetchone()['total']
    
    # Последние отправленные
    db.cursor.execute('''
        SELECT t.amount, t.transaction_type, t.timestamp,
               u_to.username as to_username, u_to.first_name as to_first_name, u_to.user_id as to_uid
        FROM transactions t
        LEFT JOIN users u_to ON t.to_user_id = u_to.user_id
        WHERE t.from_user_id = ?
          AND t.transaction_type IN ('donate_to_user', 'donate_to_bank')
        ORDER BY t.timestamp DESC LIMIT 10
    ''', (user.id,))
    sent_list = db.cursor.fetchall()
    
    # Последние полученные
    db.cursor.execute('''
        SELECT t.amount, t.timestamp,
               u_from.username as from_username, u_from.first_name as from_first_name, u_from.user_id as from_uid
        FROM transactions t
        LEFT JOIN users u_from ON t.from_user_id = u_from.user_id
        WHERE t.to_user_id = ? AND t.transaction_type = 'donate_to_user'
        ORDER BY t.timestamp DESC LIMIT 10
    ''', (user.id,))
    recv_list = db.cursor.fetchall()
    
    total_sent = sent['sent_users'] + sent['sent_bank']

    message = "📜 ИСТОРИЯ ДОНАТОВ\n\n"
    message += "📊 ИТОГИ:\n"
    message += f"   🎁 Пользователям: {format_number(sent['sent_users'])} 💎\n"
    message += f"   🏦 В Центробанк: {format_number(sent['sent_bank'])} 💎\n"
    message += f"   ▸ Всего отправлено: {format_number(total_sent)} 💎\n"
    message += f"   📥 Получено: {format_number(received_total)} 💎\n\n"
    
    if sent_list:
        message += "📤 Отправленные:\n"
        for d in sent_list[:7]:
            ts = str(d['timestamp'])[:10] if d['timestamp'] else ''
            if d['transaction_type'] == 'donate_to_user':
                to_name = d['to_username'] or d['to_first_name'] or f"ID:{d['to_uid']}"
                message += f"   🎁 @{to_name}: {format_number(d['amount'])} 💎 ({ts})\n"
            else:
                message += f"   🏦 Банк: {format_number(d['amount'])} 💎 ({ts})\n"
        message += "\n"
    
    if recv_list:
        message += "📥 Полученные:\n"
        for d in recv_list[:7]:
            ts = str(d['timestamp'])[:10] if d['timestamp'] else ''
            from_name = d['from_username'] or d['from_first_name'] or f"ID:{d['from_uid']}"
            message += f"   🎁 от @{from_name}: {format_number(d['amount'])} 💎 ({ts})\n"
    
    if not sent_list and not recv_list:
        message += "Пока нет донатов."
    
    if len(message) > 4000:
        message = message[:3950] + "\n..."
    
    keyboard = [
        [InlineKeyboardButton("🔙 Меню донатов", callback_data="donate_menu")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")]
    ]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
