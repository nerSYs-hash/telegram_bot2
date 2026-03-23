#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль Меню, Старт, Поддержка — вынесен из CommandHandler.
Все функции принимают db, admin_id, target_chat_id как аргументы.
"""

import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from utils.helpers import format_number


# ═══════════════════════════════════════════════════════════
# УМНАЯ ПОСТОЯННАЯ КЛАВИАТУРА (ReplyKeyboard)
# ═══════════════════════════════════════════════════════════

def get_main_reply_keyboard(db):
    """
    Нижняя клавиатура — только базовые кнопки.
    Всё остальное — через inline-меню (📋 Меню).
    """
    # Логика: если профиль включен — показываем его, иначе показываем баланс
    profile_enabled = db.is_feature_enabled('profile')
    balance_or_profile = KeyboardButton("👤 Профиль") if profile_enabled else KeyboardButton("💰 Баланс")
    
    keyboard = [
        [balance_or_profile, KeyboardButton("📊 Курс")],
        [KeyboardButton("❓ FAQ"), KeyboardButton("📋 Меню")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db, target_chat_id):
    """Handle /start command — only in private chat for regular users"""
    user = update.effective_user
    admin_id = int(os.getenv('MAIN_ADMIN_ID', 0))

    # Обычные пользователи — /start только в ЛС
    if update.effective_chat.type != 'private':
        user_data = db.get_user(user.id)
        is_privileged = user.id == admin_id or (user_data and (user_data['is_owner'] or user_data['is_admin']))
        if not is_privileged:
            return  # молча игнорируем

    existing_user = db.get_user(user.id)
    is_new_user = existing_user is None

    db.add_user(user.id, user.username, user.first_name, user.last_name)

    join_method = 'direct' 
    referrer_id = None
    referral_token = None
    came_from_referral = False

    if context.args and len(context.args) > 0:
        arg = context.args[0]

        # ── Deep link: BBS ──
        if arg == 'bbs':
            from handlers.bbs_handlers import show_bbs_menu
            db.add_user(user.id, user.username, user.first_name, user.last_name)
            if not db.is_feature_enabled('bbs'):
                await update.message.reply_text("📋 Pulse BBS временно отключена.")
                return
            await show_bbs_menu(update, context, db)
            return

        # ── Deep link: ЖАЛОБА на анкету BBS ──
        if arg.startswith('report_'):
            try:
                reported_user_id = int(arg.replace('report_', ''))
            except (ValueError, TypeError):
                await update.message.reply_text("❌ Некорректная ссылка для жалобы.")
                return

            context.user_data['reporting_user_id'] = reported_user_id

            # Проверяем что нарушитель существует
            reported_user = db.get_user(reported_user_id)
            if reported_user:
                try:
                    reported_name = reported_user['username'] or reported_user['first_name'] or str(reported_user_id)
                except (KeyError, IndexError):
                    reported_name = str(reported_user_id)
                header = f"🚨 <b>Жалоба на пользователя</b>\n\n👤 Нарушитель: @{reported_name}\n\n"
            else:
                header = f"🚨 <b>Жалоба на пользователя</b>\n\n👤 ID: <code>{reported_user_id}</code>\n\n"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔞 Спам / Реклама", callback_data="report_reason_spam")],
                [InlineKeyboardButton("🤡 Фейк / Мошенник", callback_data="report_reason_fake")],
                [InlineKeyboardButton("🤬 Оскорбления / Токсичность", callback_data="report_reason_toxic")],
                [InlineKeyboardButton("🔞 Откровенный контент", callback_data="report_reason_nsfw")],
                [InlineKeyboardButton("❌ Отмена", callback_data="report_cancel")],
            ])
            await update.message.reply_text(
                header + "Выберите причину жалобы:",
                parse_mode='HTML',
                reply_markup=keyboard,
            )
            return

        # New referral link format
        if arg.startswith('ref1_'):
            referral_token = arg
            came_from_referral = True
            if is_new_user:
                referrer_id = db.use_referral_link(referral_token, user.id)
                if referrer_id:
                    db.cursor.execute('UPDATE users SET referrer_id = ? WHERE user_id = ?', (referrer_id, user.id))
                    db.conn.commit()
                    join_method = 'referral_link'
                else:
                    join_method = 'expired_referral_link'
            else:
                join_method = 'referral_link_existing_user'

        # Legacy referral link format
        elif arg.startswith('ref_'):
            ref_code = arg
            came_from_referral = True
            db.cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (ref_code,))
            result = db.cursor.fetchone()

            if result and is_new_user:
                referrer_id = result['user_id']
                if referrer_id != user.id:
                    db.cursor.execute('UPDATE users SET referrer_id = ? WHERE user_id = ?', (referrer_id, user.id))
                    db.conn.commit()
                    join_method = 'referral_link_legacy'

    if is_new_user:
        db.record_user_join(
            user_id=user.id, username=user.username, first_name=user.first_name,
            join_method=join_method, referrer_id=referrer_id, referral_token=referral_token
        )

    if came_from_referral:
        chat_invite_link = await _get_chat_invite_link(context, db, target_chat_id)

        if chat_invite_link:
            keyboard = [[InlineKeyboardButton("💬 Вступить в чат", url=chat_invite_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if referrer_id:
                referrer_data = db.get_user(referrer_id)
                referrer_name = referrer_data['first_name'] if referrer_data else 'друг'
                text = (f"Привет, {user.first_name}! 👋\n\nТебя пригласил(а) {referrer_name}!\n\nНажми кнопку ниже, чтобы вступить в наш чат 👇")
            elif join_method == 'expired_referral_link':
                text = (f"Привет, {user.first_name}! 👋\n\n⚠️ К сожалению, эта ссылка уже была использована.\nПопроси друга отправить тебе новую!\n\nИли вступи в чат по кнопке ниже 👇")
            else:
                text = (f"Привет, {user.first_name}! 👋\n\nНажми кнопку ниже, чтобы вступить в наш чат 👇")

            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                f"Привет, {user.first_name}! 👋\n\nЯ бот для управления чатом с системой геймификации и экономикой.\n\nИспользуй кнопки внизу для навигации 👇",
                reply_markup=get_main_reply_keyboard(db)
            )
    else:
        await update.message.reply_text(
            f"Привет, {user.first_name}! 👋\n\nЯ бот для управления чатом с системой геймификации и экономикой.\n\nИспользуй кнопки внизу для навигации 👇",
            reply_markup=get_main_reply_keyboard(db)
        )


async def _get_chat_invite_link(context, db, target_chat_id):
    """Get or generate chat invite link"""
    env_link = os.getenv('CHAT_INVITE_LINK', '')
    if env_link: return env_link

    saved_link = db.get_setting('chat_invite_link')
    if saved_link: return saved_link

    try:
        link_obj = await context.bot.create_chat_invite_link(chat_id=target_chat_id, name="Referral invite", creates_join_request=False)
        invite_link = link_obj.invite_link
        db.set_setting('chat_invite_link', invite_link)
        return invite_link
    except Exception as e:
        logging.error(f"Error creating invite link: {e}")
    return None


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db, admin_id):
    """Handle /menu command — single window mode"""
    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await update.message.reply_text("Сначала используй /start")
        return

    is_owner = user.id == admin_id
    try:
        is_owner = is_owner or user_data['is_owner']
    except (KeyError, IndexError):
        pass

    # Обычные пользователи — только в ЛС
    if not is_owner and update.effective_chat.type != 'private':
        bot_me = await context.bot.get_me()
        await update.message.reply_text(
            f"📋 Меню доступно только в ЛС.\n👉 @{bot_me.username}",
        )
        return

    chat_id = update.effective_chat.id

    # ── Удаляем старое меню ──
    old_msg = context.user_data.get('menu_msg_id')
    if old_msg:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=old_msg)
        except Exception:
            pass

    # ── Удаляем сообщение пользователя (кнопку "📋 Меню") ──
    try:
        await update.message.delete()
    except Exception:
        pass

    balance = user_data['balance']
    message = f"📱 ГЛАВНОЕ МЕНЮ\n\n👤 {user.first_name}\n💰 Баланс: {format_number(balance)} 💎 Пульсов"

    keyboard = []

    if db.is_feature_enabled('profile'):
        keyboard.append([InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")])
    if db.is_feature_enabled('top') or db.is_feature_enabled('top_commands'):
        keyboard.append([InlineKeyboardButton("🏆 ТОП-5", callback_data="menu_top5")])
    if db.is_feature_enabled('activities'):
        keyboard.append([InlineKeyboardButton("🎯 Активности", callback_data="menu_activities")])
    if db.is_feature_enabled('bank'):
        keyboard.append([InlineKeyboardButton("🏦 Центробанк", callback_data="menu_bank")])
    if db.is_feature_enabled('detalization'):
        keyboard.append([InlineKeyboardButton("📋 Детализация", callback_data="my_detalization")])
    if db.is_feature_enabled('bbs'):
        keyboard.append([InlineKeyboardButton("❣️ Pulse BBS", callback_data="menu_bbs")])
    keyboard.append([InlineKeyboardButton("📋 Правила", url="https://t.me/c/3153855971/13")])

    # ── Статистика: для админов И владельца ──
    is_admin_user = user_data and (user_data['is_admin'] or user_data['is_owner'])
    if (is_owner or is_admin_user) and db.is_feature_enabled('statistics'):
        keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="menu_stats")])

    # ── Владелец ──
    if is_owner:
        keyboard.append([InlineKeyboardButton("🎛 Пульт Владельца", callback_data="owner_dashboard")])
        keyboard.append([InlineKeyboardButton("🔧 Управление функциями", callback_data="manage_features")])
        keyboard.append([InlineKeyboardButton("📰 Пресс-релиз", callback_data="press_release_start")])
        if db.is_feature_enabled('horoscope'):
            keyboard.append([InlineKeyboardButton("🔮 Гороскоп", callback_data="horoscope_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    sent = await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)
    context.user_data['menu_msg_id'] = sent.message_id


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command — shows FAQ menu"""
    await _show_faq_menu(update.message)


async def _show_faq_menu(message):
    text = "❓ FAQ / ПОМОЩЬ\n\nВыберите раздел:"
    keyboard = [[InlineKeyboardButton("📚 Команды и их описание", callback_data="faq_commands")],[InlineKeyboardButton("📖 Описание функций", callback_data="faq_functions")],
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ═══════════════════════════════════════════════════════════
# FAQ — ТЕКСТЫ РАЗДЕЛОВ
# ═══════════════════════════════════════════════════════════

FAQ_COMMANDS_USER = (
    "📚 <b>Справка по командам бота Pulse</b>\n\n"
    "📱 <b>Основные команды</b>\n"
    "• /start — Запустить/перезапустить бота.\n"
    "• /menu — Открыть главное меню.\n"
    "• /help — Вызвать эту справку.\n"
    "• /cancel — Отменить действие.\n\n"
    "💎 <b>Экономика и кошелёк</b>\n"
    "• /balance — Проверить свой баланс Пульсов.\n"
    "• /курс (или /course) — Узнать текущий биржевой курс.\n"
    "• /pay @username[сумма] — Перевод Пульсов другому участнику.\n"
    "• /donate — Открыть меню донатов.\n\n"
    "🪄 <b>Слова-триггеры</b> (писать в чат без /)\n"
    "• <b>богач</b> — ТОП-5 самых богатых участников.\n"
    "• <b>активист</b> — ТОП-5 самых активных по Индексу.\n"
    "• <b>курс</b> — Текущий курс Пульса."
)

FAQ_COMMANDS_ADMIN = (
    "\n\n"
    "⚙️ <b>Команды управления (Владелец)</b>\n"
    "• /give_pulse [ID_юзера] [сумма] — Выдать Пульсы из Центробанка.\n"
    "• /recalc — Принудительно пересчитать курс валюты.\n"
    "• /mute [15m/1h/1d] — Выдать мут нарушителю.\n"
    "• /restrict — Инлайн-панель для отключения гифок/фото/текста."
)

FAQ_FUNCTIONS = (
    "📖 <b>Описание функций</b>\n\n"
    "🚧 Раздел в разработке.\n\n"
    "Здесь скоро появится подробное описание всех функций бота.\n\n"
    "Следите за обновлениями!"
)