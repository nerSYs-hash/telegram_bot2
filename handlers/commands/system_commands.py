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

def get_main_reply_keyboard(db, user_id=None, main_admin_id=None):
    """
    Нижняя клавиатура — только базовые кнопки.
    Владелец видит [👑 Панель Владельца], Админ — [📋 Новые заявки], остальные — [❓ FAQ].
    """
    profile_enabled = db.is_feature_enabled('profile')
    balance_or_profile = KeyboardButton("👤 Профиль") if profile_enabled else KeyboardButton("💰 Баланс")

    is_owner = user_id and main_admin_id and user_id == main_admin_id
    is_deputy = False
    is_admin = False
    if user_id and not is_owner:
        u = db.get_user(user_id)
        if u and u.get('is_owner'):
            is_deputy = True  # зам владельца — видит полную панель
        elif u and u.get('is_admin'):
            is_admin = True

    if is_owner or is_deputy:
        special_btn = KeyboardButton("👑 Панель Владельца")
    elif is_admin:
        special_btn = KeyboardButton("📋 Новые заявки")
    else:
        special_btn = KeyboardButton("❓ FAQ")

    keyboard = [
        [balance_or_profile, KeyboardButton("📊 Курс")],
        [special_btn, KeyboardButton("📋 Меню")],
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
            from handlers.BBS.navigation_bbs import show_bbs_menu
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
                reply_markup=get_main_reply_keyboard(db, user.id, admin_id)
            )
    else:
        await update.message.reply_text(
            f"Привет, {user.first_name}! 👋\n\nЯ бот для управления чатом с системой геймификации и экономикой.\n\nИспользуй кнопки внизу для навигации 👇",
            reply_markup=get_main_reply_keyboard(db, user.id, admin_id)
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
    keyboard.append([InlineKeyboardButton("❓ FAQ / Помощь", callback_data="faq_menu")])
    keyboard.append([InlineKeyboardButton("📋 Правила", url="https://t.me/c/3153855971/13")])

    # ── Статистика: для админов И владельца ──
    is_admin_user = user_data and (user_data['is_admin'] or user_data['is_owner'])
    if (is_owner or is_admin_user) and db.is_feature_enabled('statistics'):
        keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="menu_stats")])

    # ── Владелец/Зам ──
    if is_owner:
        keyboard.append([InlineKeyboardButton("💘 Шиппер", callback_data="owner_shipper_menu")])
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
    "• /restrict — Инлайн-панель для отключения гифок/фото/текста.\n"
    "• /restore_news — Восстановление ветки НьюзON (форум новостей).\n"
    "• /restore_bbs — Восстановление ветки BBS (анкеты).\n"
    "• /restore_last_bbs — Восстановление ПОСЛЕДНЕЙ удаленной анкеты BBS.\n"
    "• /resend_dossier [user_id] — Принудительно опубликовать досье участника из БД в ветку Досье. Используй когда досье не улетело автоматически после одобрения заявки.\n"
    "\n🎁 <b>Кнопка «Компенсация BBS»</b> — позволяет вручную выдать компенсацию пострадавшим пользователям после восстановления ветки BBS. Доступна в меню восстановления веток для владельца."
)

FAQ_FEATURES = {
    'profile': {
        'icon': '👤',
        'name': 'Личный кабинет',
        'text': (
            "👤 <b>Личный кабинет (Профиль)</b>\n\n"
            "Твоя персональная карточка в сообществе.\n\n"
            "• 💎 Баланс Пульсов и текущий титул\n"
            "• 📊 Статистика активности за всё время\n"
            "• 🎖 Индекс активности и ранг\n"
            "• ⚙️ Настройки уведомлений\n\n"
            "📍 Доступ: кнопка <b>«Профиль»</b> в главном меню"
        ),
    },
    'top': {
        'icon': '🏆',
        'name': 'ТОП-5',
        'text': (
            "🏆 <b>ТОП-5</b>\n\n"
            "Рейтинги участников сообщества.\n\n"
            "💰 <b>Богачи</b>\n"
            "Топ по размеру баланса Пульсов.\n"
            "Чем больше Пульсов на счету — тем выше место.\n"
            "Пополняй баланс через майнинг, лотерею и активности.\n\n"
            "🏅 <b>Активисты</b>\n"
            "Топ по Индексу Активности за последние 7 дней.\n"
            "Индекс учитывает: количество сообщений, реакции,"
            " Пульсы намайненные за неделю.\n"
            "Обновляется раз в 30 минут.\n\n"
            "ℹ️ Администраторы и владелец в топы не входят.\n\n"
            "Слова-триггеры в чате:\n"
            "• <b>богач, богачи</b> — ТОП-5 богачей\n"
            "• <b>активист, активисты</b> — ТОП-5 активистов\n\n"
            "📍 Доступ: кнопка <b>«ТОП-5»</b> в меню"
        ),
    },
    'bank': {
        'icon': '🏦',
        'name': 'Центробанк',
        'text': (
            "🏦 <b>Центробанк</b>\n\n"
            "Центральный банк экономики Pulse.\n\n"
            "• 💱 Текущий курс Пульса к рублю\n"
            "• 💰 Конвертация баланса в рубли\n"
            "• 📊 Курс обновляется каждые 30 минут\n\n"
            "Все Пульсы в обращении выпущены из Центробанка.\n"
            "Общая эмиссия: 10 000 000 💎\n\n"
            "📍 Доступ: кнопка <b>«Центробанк»</b> в меню"
        ),
    },
    'activities': {
        'icon': '🎯',
        'name': 'Активности',
        'text': (
            "🎯 <b>Активности</b>\n\n"
            "Развлечения и события сообщества.\n\n"
            "• 🎰 Лотерея — покупай билеты, выигрывай призы\n"
            "• 🎱 Бинго — заполняй карточку, лови удачу\n"
            "• 🎁 Подарок Месяца — ежемесячный розыгрыш\n"
            "• 🛒 Чёрный Рынок — титулы, бустеры, лутбоксы\n\n"
            "📍 Доступ: кнопка <b>«Активности»</b> в меню"
        ),
    },
    'detalization': {
        'icon': '📋',
        'name': 'Детализация',
        'text': (
            "📋 <b>Детализация</b>\n\n"
            "Полная история твоих операций с Пульсами.\n\n"
            "• 💎 Все начисления и списания\n"
            "• ⛏ Награды за майнинг по дням\n"
            "• 🎁 Донаты, покупки, переводы\n"
            "• 📗 Выгрузка в Excel-файл\n\n"
            "📍 Доступ: кнопка <b>«Детализация»</b> в меню"
        ),
    },
    'lottery': {
        'icon': '🎰',
        'name': 'Лотерея',
        'text': (
            "🎰 <b>Лотерея</b>\n\n"
            "Испытай удачу и сорви куш!\n\n"
            "• 🎟 Покупай билеты за Пульсы (до 10 шт.)\n"
            "• 🏆 1 или 3 победителя (60%/25%/15%)\n"
            "• 💸 Комиссия 20% → в Центробанк\n"
            "• 🌟 Джекпот «Пульсар» — 5% с каждого билета копится, шанс 1%\n"
            "• ⚠️ Минимум 5 участников, иначе — полный возврат\n\n"
            "📍 Доступ: <b>Активности → Лотерея</b>"
        ),
    },
    'bingo': {
        'icon': '🎱',
        'name': 'Бинго',
        'text': (
            "🎱 <b>Бинго</b>\n\n"
            "Классическая игра — собери линию первым!\n\n"
            "• 🎫 Покупай карточку с уникальными числами\n"
            "• 🔢 Шары выпадают автоматически\n"
            "• ✅ Отмечай числа на своей карточке\n"
            "• 🔥 Собрал линию? Жми БИНГО и забирай банк!\n"
            "• ⚠️ <b>Анти-чит:</b> нажал БИНГО без линии — штраф! "
            "Бот проверяет карточку автоматически, "
            "фейковые заявки наказываются списанием Пульсов 💸\n\n"
            "📍 Доступ: <b>Активности → Бинго</b>"
        ),
    },
    'referral': {
        'icon': '👥',
        'name': 'Рефералы',
        'text': (
            "👥 <b>Реферальная система</b>\n\n"
            "Приглашай друзей — получай бонусы!\n\n"
            "• 🔗 Уникальная реферальная ссылка\n"
            "• 💎 Бонус за каждого приглашённого\n"
            "• 📊 Счётчик приглашённых друзей\n\n"
            "📍 Доступ: <b>Профиль → Рефералы</b>"
        ),
    },
    'donate': {
        'icon': '🎁',
        'name': 'Донаты',
        'text': (
            "🎁 <b>Система донатов</b>\n\n"
            "Поддержи сообщество или друга Пульсами!\n\n"
            "• 👤 Донат другому участнику\n"
            "• 🏦 Донат в Центробанк\n"
            "• 🔋 Донат в Реактор\n\n"
            "Также доступно командой: /donate\n\n"
            "📍 Доступ: команда <b>/donate</b> или меню"
        ),
    },
    'monthly_gift': {
        'icon': '🎁',
        'name': 'Подарок Месяца',
        'text': (
            "🎁 <b>Подарок Месяца</b>\n\n"
            "Ежемесячный розыгрыш призов!\n\n"
            "• 🎲 Случайный, взвешенный или по активности\n"
            "• 💎 Приз — Пульсы, VIP-титул или кастомный подарок\n"
            "• ✉️ Порог участия — минимум сообщений за месяц\n"
            "• 📢 Анонс и результаты в чате\n\n"
            "📍 Доступ: <b>Активности → Подарок Месяца</b>"
        ),
    },
    'bbs': {
        'icon': '❣️',
        'name': 'Pulse BBS',
        'text': (
            "❣️ <b>Pulse BBS</b>\n\n"
            "Внутренняя доска знакомств и объявлений сообщества!\n\n"
            "• 📝 Создай анкету с фото и описанием\n"
            "• 👀 Просматривай анкеты других участников\n"
            "• ❤️ Ставь реакции — взаимный лайк = мэтч!\n"
            "• 📦 Раздел <b>«Другое»</b> — аренда, услуги, барахолка и объявления о помощи\n"
            "• 🏆 Бонус популярности за реакции на анкету\n\n"
            "📍 Доступ: кнопка <b>«Pulse BBS»</b> в меню"
        ),
    },
}


async def show_faq_functions(query, db):
    """Показать описание функций — только включённые фичи."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    text = "📖 <b>Описание Событий</b>\n\nВыберите функцию для подробного описания:"

    keyboard = []
    for feat_id, feat in FAQ_FEATURES.items():
        if db.is_feature_enabled(feat_id):
            keyboard.append([InlineKeyboardButton(
                f"{feat['icon']} {feat['name']}",
                callback_data=f"faq_feat_{feat_id}"
            )])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="faq_back")])

    await query.edit_message_text(text, parse_mode='HTML',
                                  reply_markup=InlineKeyboardMarkup(keyboard))