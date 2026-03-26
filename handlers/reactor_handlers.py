#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль «Реактор 2.0» — Общественный Battle Pass.

Путь: handlers/reactor_handlers.py

Чат скидывается Пульсами для разблокировки глобальных фич.
Пороги: 25% → Мега-Лотерея, 50% → Анонимные Валентинки, 100% → Чёрный Рынок.
При 100% — Last Hit: детонатор/спаситель тегается в чате.

v2: + админ-панель, + заглушки разблокируемых фич, + статистика вкладов.
"""

import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import format_number

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════

DEFAULT_TARGET = 100000.0       # Цель пула по умолчанию
ACCESS_KEY_THRESHOLD = 1000.0   # Порог «Ключа Доступа» (личный вклад за цикл)

THRESHOLDS = [
    (25,  "🎰 Мега-Лотерея"),
    (50,  "💌 Анонимные Валентинки"),
    (100, "🛍 Чёрный Рынок"),
]

# Символы прогресс-бара
BAR_FILLED = "▓"
BAR_EMPTY  = "░"
BAR_LENGTH = 10


# ═══════════════════════════════════════════════════════════════
#  ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ
# ═══════════════════════════════════════════════════════════════

def ensure_reactor_tables(db):
    """Создаёт таблицы reactor_state и reactor_contributions, если их нет."""
    try:
        db.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactor_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                current_pool REAL NOT NULL DEFAULT 0,
                target_pool REAL NOT NULL DEFAULT 100000,
                status TEXT NOT NULL DEFAULT 'charging',
                cycle_start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        db.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactor_contributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                contributed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Гарантируем, что есть хотя бы одна запись состояния
        db.cursor.execute('SELECT COUNT(*) as cnt FROM reactor_state')
        if db.cursor.fetchone()['cnt'] == 0:
            db.cursor.execute(
                'INSERT INTO reactor_state (current_pool, target_pool, status) VALUES (0, ?, "charging")',
                (DEFAULT_TARGET,)
            )

        db.conn.commit()
    except Exception as e:
        logger.error(f"ensure_reactor_tables error: {e}")


# ═══════════════════════════════════════════════════════════════
#  ХЕЛПЕРЫ РАБОТЫ С БД
# ═══════════════════════════════════════════════════════════════

def _get_reactor_state(db):
    """Возвращает текущее состояние реактора (dict-like Row)."""
    db.cursor.execute('SELECT * FROM reactor_state ORDER BY id DESC LIMIT 1')
    return db.cursor.fetchone()


def _get_user_contribution(db, user_id):
    """Суммарный вклад пользователя в ТЕКУЩЕМ цикле."""
    state = _get_reactor_state(db)
    if not state:
        return 0.0
    db.cursor.execute(
        'SELECT COALESCE(SUM(amount), 0) as total '
        'FROM reactor_contributions '
        'WHERE user_id = ? AND contributed_at >= ?',
        (user_id, state['cycle_start_time'])
    )
    row = db.cursor.fetchone()
    return float(row['total']) if row else 0.0


def _get_top_contributor(db):
    """Возвращает (user_id, total) топ-1 инвестора текущего цикла или None."""
    state = _get_reactor_state(db)
    if not state:
        return None
    db.cursor.execute('''
        SELECT user_id, SUM(amount) as total
        FROM reactor_contributions
        WHERE contributed_at >= ?
        GROUP BY user_id
        ORDER BY total DESC
        LIMIT 1
    ''', (state['cycle_start_time'],))
    return db.cursor.fetchone()


def _get_top_contributors(db, limit=10):
    """Возвращает список топ-инвесторов текущего цикла."""
    state = _get_reactor_state(db)
    if not state:
        return []
    db.cursor.execute('''
        SELECT user_id, SUM(amount) as total, COUNT(*) as donations_count
        FROM reactor_contributions
        WHERE contributed_at >= ?
        GROUP BY user_id
        ORDER BY total DESC
        LIMIT ?
    ''', (state['cycle_start_time'], limit))
    return db.cursor.fetchall()


def _get_contributors_count(db):
    """Число уникальных вкладчиков текущего цикла."""
    state = _get_reactor_state(db)
    if not state:
        return 0
    db.cursor.execute(
        'SELECT COUNT(DISTINCT user_id) as cnt '
        'FROM reactor_contributions WHERE contributed_at >= ?',
        (state['cycle_start_time'],)
    )
    row = db.cursor.fetchone()
    return row['cnt'] if row else 0


def _get_percent(state):
    """Процент заполненности (0–100+). Безопасно от деления на 0."""
    if not state or not state['target_pool'] or float(state['target_pool']) == 0:
        return 0.0
    return round(float(state['current_pool']) / float(state['target_pool']) * 100, 2)


def _build_progress_bar(percent):
    """Рисует прогресс-бар [▓▓▓▓░░░░░░] из 10 символов."""
    filled = min(BAR_LENGTH, int(percent / 100 * BAR_LENGTH))
    return f"[{BAR_FILLED * filled}{BAR_EMPTY * (BAR_LENGTH - filled)}]"


def _user_display_name(db, user_id):
    """Красивое имя пользователя для вывода."""
    u = db.get_user(user_id)
    if u and u['username']:
        return f"@{u['username']}"
    if u and u['first_name']:
        return u['first_name']
    return f"ID {user_id}"


def _has_access_key(db, user_id):
    """Проверяет, имеет ли юзер Ключ Доступа (вложил >= 1000 в текущем цикле)."""
    return _get_user_contribution(db, user_id) >= ACCESS_KEY_THRESHOLD


def _is_reward_unlocked(db, threshold_pct):
    """Проверяет, разблокирована ли награда на данном пороге."""
    state = _get_reactor_state(db)
    if not state:
        return False
    return _get_percent(state) >= threshold_pct


# ═══════════════════════════════════════════════════════════════
#  ГЛАВНОЕ МЕНЮ РЕАКТОРА (для пользователей)
# ═══════════════════════════════════════════════════════════════

async def show_reactor_menu(query, context, db, user_id, is_owner=False):
    """Генерирует красивое сообщение-меню Реактора."""
    ensure_reactor_tables(db)
    state = _get_reactor_state(db)

    if not state:
        await query.edit_message_text(
            "⚠️ Реактор не инициализирован. Обратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
            ])
        )
        return

    current = float(state['current_pool'])
    target = float(state['target_pool'])
    percent = _get_percent(state)
    status = state['status']
    bar = _build_progress_bar(percent)

    # ── Статус-заголовок ──
    if status == 'active':
        status_emoji = "⚡"
        status_text = "АКТИВЕН"
    elif status == 'cooldown':
        status_emoji = "❄️"
        status_text = "ПЕРЕЗАРЯДКА"
    else:
        status_emoji = "🔋"
        status_text = "ЗАРЯЖАЕТСЯ"

    # ── Награды ──
    rewards_lines = []
    for threshold_pct, reward_name in THRESHOLDS:
        unlocked = percent >= threshold_pct
        icon = "✅" if unlocked else "🔒"
        rewards_lines.append(f"  {threshold_pct}% — {reward_name} {icon}")
    rewards_block = "\n".join(rewards_lines)

    # ── Ключ доступа ──
    user_contrib = _get_user_contribution(db, user_id)
    if user_contrib >= ACCESS_KEY_THRESHOLD:
        key_line = "🔑 <b>[Ключ Доступа ПОЛУЧЕН]</b>"
    else:
        need = ACCESS_KEY_THRESHOLD - user_contrib
        key_line = f"🔑 [Нужно ещё {format_number(need)} 💎]"

    # ── Топ-1 инвестор ──
    top = _get_top_contributor(db)
    if top and top['total']:
        top_name = _user_display_name(db, top['user_id'])
        top_line = f"👑 Топ-инвестор: {top_name} — {format_number(top['total'])} 💎"
    else:
        top_line = "👑 Топ-инвестор: — пока никого —"

    # ── Личный вклад ──
    contrib_line = f"💎 Ваш вклад: {format_number(user_contrib)} 💎"

    # ── Собираем сообщение ──
    text = (
        f"{status_emoji} <b>РЕАКТОР 2.0</b> — {status_text}\n\n"
        f"{bar}  <b>{percent:.1f}%</b>\n"
        f"💰 {format_number(current)} / {format_number(target)} 💎\n\n"
        f"<b>Награды:</b>\n"
        f"{rewards_block}\n\n"
        f"{key_line}\n"
        f"{contrib_line}\n\n"
        f"{top_line}"
    )

    # ── Кнопки ──
    keyboard = []

    if status == 'charging':
        keyboard.append([
            InlineKeyboardButton("💎 100", callback_data="reactor_donate_100"),
            InlineKeyboardButton("💎 1000", callback_data="reactor_donate_1000"),
        ])
        keyboard.append([InlineKeyboardButton("✏️ Своя сумма", callback_data="reactor_donate_custom")])

    # Кнопки разблокированных наград (заглушки)
    if percent >= 25:
        keyboard.append([InlineKeyboardButton("🎰 Мега-Лотерея", callback_data="reactor_feat_lottery")])
    if percent >= 50:
        keyboard.append([InlineKeyboardButton("💌 Валентинки", callback_data="reactor_feat_valentines")])
    if percent >= 100:
        keyboard.append([InlineKeyboardButton("🛍 Чёрный Рынок", callback_data="reactor_feat_market")])

    # Админ-кнопка
    if is_owner:
        keyboard.append([InlineKeyboardButton("⚙️ Управление Реактором", callback_data="reactor_admin")])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"show_reactor_menu error: {e}")


# ═══════════════════════════════════════════════════════════════
#  ЗАГЛУШКИ РАЗБЛОКИРУЕМЫХ ФИЧ
# ═══════════════════════════════════════════════════════════════

async def handle_reactor_feature(query, data, db, user_id):
    """
    Обработчик кнопок разблокированных фич.
    Проверяет порог + Ключ Доступа, показывает заглушку.
    """
    feature_map = {
        "reactor_feat_lottery":    (25,  "🎰 Мега-Лотерея",
            "Масштабная лотерея с увеличенными призами!\n\n"
            "🔧 <i>Функция в разработке. Следите за обновлениями!</i>"),
        "reactor_feat_valentines": (50,  "💌 Анонимные Валентинки",
            "Отправляйте анонимные послания участникам чата!\n\n"
            "🔧 <i>Функция в разработке. Следите за обновлениями!</i>"),
        "reactor_feat_market":     (100, "🛍 Чёрный Рынок",
            "Эксклюзивный магазин с уникальными предметами, "
            "титулами и привилегиями!\n\n"
            "🔧 <i>Функция в разработке. Следите за обновлениями!</i>"),
    }

    if data not in feature_map:
        await query.answer("❌ Неизвестная функция.", show_alert=True)
        return

    threshold_pct, title, description = feature_map[data]

    # Проверка: порог разблокирован?
    if not _is_reward_unlocked(db, threshold_pct):
        await query.answer(
            f"🔒 Эта награда разблокируется на {threshold_pct}% Реактора.",
            show_alert=True
        )
        return

    # Проверка: есть ли Ключ Доступа?
    has_key = _has_access_key(db, user_id)
    if not has_key:
        need = ACCESS_KEY_THRESHOLD - _get_user_contribution(db, user_id)
        await query.answer(
            f"🔑 Нужен Ключ Доступа!\n"
            f"Вложите ещё {format_number(need)} 💎 в Реактор.",
            show_alert=True
        )
        return

    # Показываем заглушку
    text = (
        f"{title}\n\n"
        f"🔑 Ключ Доступа: ✅\n\n"
        f"{description}"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Назад к Реактору", callback_data="menu_reactor")],
    ]

    await query.edit_message_text(
        text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ═══════════════════════════════════════════════════════════════
#  ЛОГИКА ДОНАТА
# ═══════════════════════════════════════════════════════════════

async def _process_reactor_donation(query, context, db, user_id, amount, target_chat_id):
    """
    Центральная логика пополнения Реактора.
    Списывает у юзера, добавляет в пул, записывает транзакцию,
    проверяет пороги и Last Hit.
    """
    amount = round(float(amount), 2)

    if amount <= 0:
        await query.answer("❌ Сумма должна быть больше 0.", show_alert=True)
        return

    # Проверка: реактор в режиме charging?
    state = _get_reactor_state(db)
    if not state or state['status'] != 'charging':
        await query.answer("⚠️ Реактор сейчас не принимает Пульсы.", show_alert=True)
        return

    # Проверка баланса
    user_data = db.get_user(user_id)
    if not user_data:
        await query.answer("❌ Пользователь не найден.", show_alert=True)
        return

    balance = float(user_data['balance'])
    if balance < amount:
        await query.answer(
            f"❌ Недостаточно Пульсов!\nБаланс: {format_number(balance)} 💎",
            show_alert=True
        )
        return

    # ── Запоминаем процент ДО доната ──
    old_percent = _get_percent(state)

    # ── Списание и зачисление ──
    try:
        db.update_user_balance(user_id, amount, operation='subtract')

        new_pool = float(state['current_pool']) + amount
        db.cursor.execute(
            'UPDATE reactor_state SET current_pool = ? WHERE id = ?',
            (round(new_pool, 2), state['id'])
        )

        db.cursor.execute(
            'INSERT INTO reactor_contributions (user_id, amount) VALUES (?, ?)',
            (user_id, amount)
        )

        db.add_transaction(
            user_id, None, amount, 'reactor_donate',
            f"Вклад в Реактор 2.0 (цикл #{state['id']})"
        )

        db.conn.commit()
    except Exception as e:
        logger.error(f"Reactor donation DB error: {e}")
        try:
            db.conn.rollback()
        except Exception:
            pass
        await query.answer("❌ Ошибка при обработке. Попробуйте позже.", show_alert=True)
        return

    # ── Пересчёт процента ПОСЛЕ ──
    refreshed = _get_reactor_state(db)
    new_percent = _get_percent(refreshed)

    await query.answer(f"✅ Вы вложили {format_number(amount)} 💎 в Реактор!", show_alert=True)

    # ── ПРОВЕРКА ПОРОГОВ ──
    await _check_thresholds(context, db, user_id, old_percent, new_percent, target_chat_id)

    # ── Обновляем меню ──
    await show_reactor_menu(query, context, db, user_id)


async def _check_thresholds(context, db, user_id, old_pct, new_pct, target_chat_id):
    """
    Проверяет, пересёк ли донат порог 25/50/100%.
    Если да — отправляет анонс в главный чат.
    При 100%+ — Last Hit (эпичное сообщение + тег детонатора).
    """
    state = _get_reactor_state(db)
    if not state:
        return

    donor_name = _user_display_name(db, user_id)

    for threshold_pct, reward_name in THRESHOLDS:
        if old_pct < threshold_pct <= new_pct:
            if threshold_pct == 100:
                # ══════ LAST HIT — ДЕТОНАЦИЯ ══════
                try:
                    db.cursor.execute(
                        'UPDATE reactor_state SET status = "active" WHERE id = ?',
                        (state['id'],)
                    )
                    db.conn.commit()
                except Exception as e:
                    logger.error(f"Reactor status update error: {e}")

                epic_text = (
                    f"💥💥💥 <b>РЕАКТОР АКТИВИРОВАН!</b> 💥💥💥\n\n"
                    f"🔋 Цель {format_number(state['target_pool'])} 💎 — <b>ДОСТИГНУТА!</b>\n\n"
                    f"🏆 <b>Детонатор / Спаситель:</b>\n"
                    f"⚡ {donor_name}\n\n"
                    f"Разблокированы ВСЕ награды цикла:\n"
                    f"  🎰 Мега-Лотерея ✅\n"
                    f"  💌 Анонимные Валентинки ✅\n"
                    f"  🛍 Чёрный Рынок ✅\n\n"
                    f"Спасибо каждому, кто внёс Пульсы! 🫡"
                )
                try:
                    await context.bot.send_message(
                        chat_id=target_chat_id,
                        text=epic_text,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Reactor LAST HIT announce error: {e}")
            else:
                # ══════ ПРОМЕЖУТОЧНЫЙ ПОРОГ (25% / 50%) ══════
                # Пересчитываем остаток от обновлённого состояния
                refreshed = _get_reactor_state(db)
                remaining = float(refreshed['target_pool']) - float(refreshed['current_pool'])
                remaining = max(0, remaining)

                announce_text = (
                    f"🔋 <b>РЕАКТОР 2.0 — {threshold_pct}%!</b>\n\n"
                    f"{_build_progress_bar(new_pct)}  {new_pct:.1f}%\n\n"
                    f"🎁 Награда разблокирована:\n"
                    f"  {reward_name} ✅\n\n"
                    f"⚡ Последний вклад: {donor_name}\n"
                    f"💰 До 100%: ещё {format_number(remaining)} 💎"
                )
                try:
                    await context.bot.send_message(
                        chat_id=target_chat_id,
                        text=announce_text,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Reactor threshold {threshold_pct}% announce error: {e}")


# ═══════════════════════════════════════════════════════════════
#  ОБРАБОТЧИКИ КНОПОК ДОНАТА
# ═══════════════════════════════════════════════════════════════

async def handle_reactor_donate_fixed(query, data, user, context, db, target_chat_id):
    """
    Обработчик кнопок [💎 100] и [💎 1000].
    data формат: 'reactor_donate_100' или 'reactor_donate_1000'
    """
    try:
        amount = float(data.replace("reactor_donate_", ""))
    except (ValueError, TypeError):
        await query.answer("❌ Некорректная сумма.", show_alert=True)
        return

    await _process_reactor_donation(query, context, db, user.id, amount, target_chat_id)


async def handle_reactor_donate_custom_start(query, user, context, db):
    """
    Обработчик кнопки [✏️ Своя сумма].
    Ставит флаг ожидания ввода суммы.
    """
    user_data = db.get_user(user.id)
    balance = float(user_data['balance']) if user_data else 0

    context.user_data['awaiting_reactor_custom'] = True

    text = (
        f"✏️ <b>РЕАКТОР 2.0 — Своя сумма</b>\n\n"
        f"💰 Ваш баланс: {format_number(balance)} 💎\n\n"
        f"Введите сумму Пульсов для вклада в Реактор.\n"
        f"Минимум: 1 💎"
    )

    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="menu_reactor")],
    ]

    await query.edit_message_text(
        text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_reactor_custom_amount(update, context, db, target_chat_id):
    """
    Обработчик текстового сообщения с суммой (вызывается из message_handler).
    Возвращает True если сообщение обработано, False если нет.
    """
    if not context.user_data.get('awaiting_reactor_custom'):
        return False

    context.user_data['awaiting_reactor_custom'] = False

    text = update.message.text.strip().replace(',', '.')

    try:
        amount = round(float(text), 2)
    except (ValueError, TypeError):
        await update.message.reply_text(
            "❌ Некорректная сумма. Введите число.",
            parse_mode='HTML'
        )
        return True

    if amount < 1:
        await update.message.reply_text(
            "❌ Минимальная сумма: 1 💎",
            parse_mode='HTML'
        )
        return True

    user_id = update.effective_user.id
    ensure_reactor_tables(db)

    state = _get_reactor_state(db)
    if not state or state['status'] != 'charging':
        await update.message.reply_text("⚠️ Реактор сейчас не принимает Пульсы.")
        return True

    user_data = db.get_user(user_id)
    if not user_data:
        await update.message.reply_text("❌ Пользователь не найден.")
        return True

    balance = float(user_data['balance'])
    if balance < amount:
        await update.message.reply_text(
            f"❌ Недостаточно Пульсов!\nБаланс: {format_number(balance)} 💎"
        )
        return True

    # ── Запоминаем % ДО доната ──
    old_percent = _get_percent(state)

    # ── Списание и зачисление ──
    try:
        db.update_user_balance(user_id, amount, operation='subtract')

        new_pool = float(state['current_pool']) + amount
        db.cursor.execute(
            'UPDATE reactor_state SET current_pool = ? WHERE id = ?',
            (round(new_pool, 2), state['id'])
        )
        db.cursor.execute(
            'INSERT INTO reactor_contributions (user_id, amount) VALUES (?, ?)',
            (user_id, amount)
        )
        db.add_transaction(
            user_id, None, amount, 'reactor_donate',
            f"Вклад в Реактор 2.0 (цикл #{state['id']})"
        )
        db.conn.commit()
    except Exception as e:
        logger.error(f"Reactor custom donation error: {e}")
        try:
            db.conn.rollback()
        except Exception:
            pass
        await update.message.reply_text("❌ Ошибка при обработке. Попробуйте позже.")
        return True

    refreshed = _get_reactor_state(db)
    new_percent = _get_percent(refreshed)

    # ── Ответ пользователю ──
    text_reply = (
        f"✅ <b>Вклад принят!</b>\n\n"
        f"💎 Сумма: {format_number(amount)} 💎\n"
        f"🔋 Реактор: {new_percent:.1f}%\n\n"
        f"Используйте /menu чтобы открыть Реактор."
    )
    keyboard = [
        [InlineKeyboardButton("🔋 Открыть Реактор", callback_data="menu_reactor")],
    ]
    await update.message.reply_text(
        text_reply, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # ── Проверка порогов ──
    await _check_thresholds(context, db, user_id, old_percent, new_percent, target_chat_id)

    return True


# ═══════════════════════════════════════════════════════════════
#  АДМИН-ПАНЕЛЬ РЕАКТОРА
# ═══════════════════════════════════════════════════════════════

async def show_reactor_admin(query, context, db, user_id, admin_id):
    """Панель управления Реактором (только owner)."""
    if user_id != admin_id:
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    ensure_reactor_tables(db)
    state = _get_reactor_state(db)

    if not state:
        await query.answer("⚠️ Реактор не инициализирован.", show_alert=True)
        return

    current = float(state['current_pool'])
    target = float(state['target_pool'])
    percent = _get_percent(state)
    status = state['status']
    cycle_id = state['id']

    # Статистика вкладов
    contributors = _get_contributors_count(db)
    top_list = _get_top_contributors(db, limit=5)

    # Топ-5 строки
    top_lines = []
    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
    for i, row in enumerate(top_list):
        name = _user_display_name(db, row['user_id'])
        top_lines.append(
            f"  {medals[i]} {name} — {format_number(row['total'])} 💎 "
            f"({row['donations_count']} вкл.)"
        )
    top_block = "\n".join(top_lines) if top_lines else "  — пусто —"

    status_map = {'charging': '🔋 Заряжается', 'active': '⚡ Активен', 'cooldown': '❄️ Перезарядка'}

    text = (
        f"⚙️ <b>УПРАВЛЕНИЕ РЕАКТОРОМ</b>\n\n"
        f"📊 Цикл: <b>#{cycle_id}</b>\n"
        f"📡 Статус: {status_map.get(status, status)}\n"
        f"{_build_progress_bar(percent)}  <b>{percent:.1f}%</b>\n"
        f"💰 Пул: {format_number(current)} / {format_number(target)} 💎\n\n"
        f"👥 Вкладчиков: <b>{contributors}</b>\n\n"
        f"<b>Топ-5 инвесторов:</b>\n"
        f"{top_block}"
    )

    keyboard = [
        [InlineKeyboardButton("🔄 Новый цикл (сброс)", callback_data="reactor_admin_reset")],
        [
            InlineKeyboardButton("🎯 Цель 50к", callback_data="reactor_admin_target_50000"),
            InlineKeyboardButton("🎯 Цель 100к", callback_data="reactor_admin_target_100000"),
        ],
        [
            InlineKeyboardButton("🎯 Цель 250к", callback_data="reactor_admin_target_250000"),
            InlineKeyboardButton("🎯 Цель 500к", callback_data="reactor_admin_target_500000"),
        ],
        [InlineKeyboardButton("✏️ Своя цель", callback_data="reactor_admin_target_custom")],
        [
            InlineKeyboardButton("▶️ charging", callback_data="reactor_admin_status_charging"),
            InlineKeyboardButton("⚡ active", callback_data="reactor_admin_status_active"),
            InlineKeyboardButton("❄️ cooldown", callback_data="reactor_admin_status_cooldown"),
        ],
        [InlineKeyboardButton("🔙 Назад к Реактору", callback_data="menu_reactor")],
    ]

    try:
        await query.edit_message_text(
            text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"show_reactor_admin edit error: {e}")


async def reactor_admin_reset(query, context, db, user_id, admin_id):
    """Сброс Реактора — новый цикл. Только для owner."""
    if user_id != admin_id:
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    ensure_reactor_tables(db)

    try:
        state = _get_reactor_state(db)
        target = float(state['target_pool']) if state else DEFAULT_TARGET

        db.cursor.execute(
            'INSERT INTO reactor_state (current_pool, target_pool, status) VALUES (0, ?, "charging")',
            (target,)
        )
        db.conn.commit()

        await query.answer("✅ Реактор сброшен! Новый цикл запущен.", show_alert=True)
        await show_reactor_admin(query, context, db, user_id, admin_id)
    except Exception as e:
        logger.error(f"reactor_admin_reset error: {e}")
        await query.answer("❌ Ошибка сброса.", show_alert=True)


async def reactor_admin_set_target(query, context, db, user_id, admin_id, new_target):
    """Изменение цели Реактора. Только для owner."""
    if user_id != admin_id:
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    ensure_reactor_tables(db)

    try:
        new_target = float(new_target)
        if new_target <= 0:
            await query.answer("❌ Цель должна быть > 0.", show_alert=True)
            return

        state = _get_reactor_state(db)
        if state:
            db.cursor.execute(
                'UPDATE reactor_state SET target_pool = ? WHERE id = ?',
                (new_target, state['id'])
            )
            db.conn.commit()
            await query.answer(f"✅ Цель: {format_number(new_target)} 💎", show_alert=True)
        await show_reactor_admin(query, context, db, user_id, admin_id)
    except Exception as e:
        logger.error(f"reactor_admin_set_target error: {e}")
        await query.answer("❌ Ошибка.", show_alert=True)


async def reactor_admin_set_status(query, context, db, user_id, admin_id, new_status):
    """Ручная смена статуса Реактора. Только для owner."""
    if user_id != admin_id:
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    if new_status not in ('charging', 'active', 'cooldown'):
        await query.answer("❌ Неизвестный статус.", show_alert=True)
        return

    ensure_reactor_tables(db)

    try:
        state = _get_reactor_state(db)
        if state:
            db.cursor.execute(
                'UPDATE reactor_state SET status = ? WHERE id = ?',
                (new_status, state['id'])
            )
            db.conn.commit()
            status_names = {'charging': '🔋 Заряжается', 'active': '⚡ Активен', 'cooldown': '❄️ Перезарядка'}
            await query.answer(f"✅ Статус: {status_names[new_status]}", show_alert=True)
        await show_reactor_admin(query, context, db, user_id, admin_id)
    except Exception as e:
        logger.error(f"reactor_admin_set_status error: {e}")
        await query.answer("❌ Ошибка.", show_alert=True)


async def reactor_admin_custom_target_start(query, user, context, db, admin_id):
    """Ожидание текстового ввода цели. Только для owner."""
    if user.id != admin_id:
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    context.user_data['awaiting_reactor_target'] = True

    text = (
        f"✏️ <b>Установить цель Реактора</b>\n\n"
        f"Введите число (например: 150000)\n"
    )
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="reactor_admin")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_reactor_admin_custom_target(update, context, db, admin_id):
    """
    Обработчик текстового ввода новой цели (из message_handler).
    Возвращает True если обработано, False если нет.
    """
    if not context.user_data.get('awaiting_reactor_target'):
        return False

    context.user_data['awaiting_reactor_target'] = False

    if update.effective_user.id != admin_id:
        return True

    text = update.message.text.strip().replace(',', '.').replace(' ', '')

    try:
        new_target = float(text)
        if new_target <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("❌ Введите положительное число.")
        return True

    ensure_reactor_tables(db)
    state = _get_reactor_state(db)
    if state:
        db.cursor.execute(
            'UPDATE reactor_state SET target_pool = ? WHERE id = ?',
            (new_target, state['id'])
        )
        db.conn.commit()

    await update.message.reply_text(
        f"✅ Цель Реактора: <b>{format_number(new_target)} 💎</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Управление Реактором", callback_data="reactor_admin")]
        ])
    )
    return True
