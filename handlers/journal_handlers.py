#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Журнал событий — логирование в Telegram-канал.

Путь: handlers/journal_handlers.py

Функционал:
  - Подключение/отключение канала-журнала через владельца
  - Автоматическое логирование событий:
    • Вход/выход из чата
    • Мут/бан/размут
    • Срабатывание триггеров
    • Ответы exit-опросов
    • Действия админов (эмиссия, вайп, блэклист)
  - Хештеги для фильтрации
  - Кнопка «Написать в ЛС» под записями

Использование:
  from handlers.journal_handlers import log_event, show_journal_menu
"""

import logging
from typing import Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  ТАБЛИЦА
# ═══════════════════════════════════════════════════════════════

def ensure_journal_tables(db) -> None:
    """Создаёт таблицу journal_messages."""
    try:
        db.cursor.execute('''
            CREATE TABLE IF NOT EXISTS journal_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                channel_id INTEGER,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                text_preview TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_journal_event ON journal_messages(event_type)'
        )
        db.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_journal_user ON journal_messages(user_id)'
        )
        db.conn.commit()
    except Exception as e:
        logger.error(f"ensure_journal_tables error: {e}")


# ═══════════════════════════════════════════════════════════════
#  ХЕЛПЕРЫ
# ═══════════════════════════════════════════════════════════════

def _get_journal_channel(db) -> Optional[int]:
    """Получает ID канала-журнала из settings."""
    val = db.get_setting('journal_channel_id')
    if val:
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
    return None


def _dm_button(user_id: int) -> InlineKeyboardMarkup:
    """Кнопка 'Написать в ЛС' под записью журнала."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Написать в ЛС", url=f"tg://user?id={user_id}")]
    ])


def _user_tag(db, user_id: int) -> str:
    """Формирует тег пользователя для журнала."""
    u = db.get_user(user_id)
    if u:
        name = u['username'] or u['first_name'] or str(user_id)
        return f'<a href="tg://user?id={user_id}">@{name}</a>'
    return f'<code>{user_id}</code>'


# ═══════════════════════════════════════════════════════════════
#  ГЛАВНАЯ ФУНКЦИЯ ЛОГИРОВАНИЯ
# ═══════════════════════════════════════════════════════════════

async def log_event(
    bot: Bot,
    db,
    event_type: str,
    text: str,
    user_id: int = None,
    hashtag: str = None,
) -> None:
    """
    Отправляет запись в канал-журнал.

    Args:
        bot: объект Bot
        db: объект Database
        event_type: тип события (join, leave, mute, ban, trigger, etc.)
        text: HTML-текст сообщения
        user_id: ID пользователя (для кнопки ЛС)
        hashtag: хештег, например #Вход
    """
    channel_id = _get_journal_channel(db)
    if not channel_id:
        return

    full_text = text
    if hashtag:
        full_text = f"{hashtag}\n\n{text}"

    markup = _dm_button(user_id) if user_id else None

    try:
        msg = await bot.send_message(
            chat_id=channel_id,
            text=full_text,
            parse_mode='HTML',
            reply_markup=markup,
            disable_web_page_preview=True,
        )

        # Сохраняем запись в БД
        try:
            ensure_journal_tables(db)
            preview = text[:200] if text else ''
            db.cursor.execute(
                'INSERT INTO journal_messages (message_id, channel_id, event_type, user_id, text_preview) '
                'VALUES (?, ?, ?, ?, ?)',
                (msg.message_id, channel_id, event_type, user_id, preview)
            )
            db.conn.commit()
        except Exception as e:
            logger.error(f"Journal DB save error: {e}")

    except Exception as e:
        logger.error(f"Journal send error ({event_type}): {e}")


# ═══════════════════════════════════════════════════════════════
#  ГОТОВЫЕ ЛОГГЕРЫ (вызываются из других модулей)
# ═══════════════════════════════════════════════════════════════

async def log_join(bot, db, user_id: int) -> None:
    """Логирует вход пользователя в чат."""
    tag = _user_tag(db, user_id)
    await log_event(
        bot, db, 'join',
        f"👋 {tag} вступил(а) в чат\n🆔 <code>{user_id}</code>",
        user_id=user_id, hashtag="#Вход"
    )


async def log_leave(bot, db, user_id: int, reason: str = None) -> None:
    """Логирует выход пользователя из чата."""
    tag = _user_tag(db, user_id)
    text = f"🚪 {tag} покинул(а) чат\n🆔 <code>{user_id}</code>"
    if reason:
        text += f"\n📝 Причина: {reason}"
    await log_event(bot, db, 'leave', text, user_id=user_id, hashtag="#Выход")


async def log_mute(bot, db, target_id: int, admin_id: int, duration: str) -> None:
    """Логирует мут."""
    target_tag = _user_tag(db, target_id)
    admin_tag = _user_tag(db, admin_id)
    await log_event(
        bot, db, 'mute',
        f"🔇 {target_tag} замучен на {duration}\n👮 Админ: {admin_tag}",
        user_id=target_id, hashtag="#Мут"
    )


async def log_unmute(bot, db, target_id: int, admin_id: int) -> None:
    """Логирует размут."""
    target_tag = _user_tag(db, target_id)
    admin_tag = _user_tag(db, admin_id)
    await log_event(
        bot, db, 'unmute',
        f"🔊 {target_tag} размучен\n👮 Админ: {admin_tag}",
        user_id=target_id, hashtag="#Размут"
    )


async def log_ban(bot, db, target_id: int, admin_id: int) -> None:
    """Логирует бан."""
    target_tag = _user_tag(db, target_id)
    admin_tag = _user_tag(db, admin_id)
    await log_event(
        bot, db, 'ban',
        f"🚫 {target_tag} забанен\n👮 Админ: {admin_tag}",
        user_id=target_id, hashtag="#Бан"
    )


async def log_trigger(bot, db, user_id: int, trigger_name: str, action: str) -> None:
    """Логирует срабатывание триггера."""
    tag = _user_tag(db, user_id)
    await log_event(
        bot, db, 'trigger',
        f"⚡ Триггер <b>{trigger_name}</b>\n👤 {tag}\n⚙️ Действие: {action}",
        user_id=user_id, hashtag="#Триггер"
    )


async def log_blacklist(bot, db, target_id: int, admin_id: int, added: bool) -> None:
    """Логирует добавление/удаление из блэклиста."""
    target_tag = _user_tag(db, target_id)
    admin_tag = _user_tag(db, admin_id)
    if added:
        text = f"🚫 {target_tag} добавлен в блэклист\n👮 {admin_tag}"
        hashtag = "#Блокировка"
    else:
        text = f"✅ {target_tag} убран из блэклиста\n👮 {admin_tag}"
        hashtag = "#Разблокировка"
    await log_event(bot, db, 'blacklist', text, user_id=target_id, hashtag=hashtag)


async def log_admin_action(bot, db, admin_id: int, action_text: str) -> None:
    """Логирует административное действие (эмиссия, вайп и т.д.)."""
    admin_tag = _user_tag(db, admin_id)
    await log_event(
        bot, db, 'admin',
        f"🔧 {admin_tag}\n{action_text}",
        hashtag="#Админ"
    )


async def log_exit_survey(bot, db, user_id: int, reason: str) -> None:
    """Логирует ответ exit-опроса."""
    tag = _user_tag(db, user_id)
    await log_event(
        bot, db, 'exit_survey',
        f"📋 {tag} ответил(а) на опрос\n📝 Причина: {reason}",
        user_id=user_id, hashtag="#Опрос"
    )


async def log_profile_change(bot, db, user_id: int, changes: str) -> None:
    """Логирует изменения профиля."""
    tag = _user_tag(db, user_id)
    await log_event(
        bot, db, 'profile',
        f"👤 {tag} обновил(а) профиль\n{changes}",
        user_id=user_id, hashtag="#Профиль"
    )


# ═══════════════════════════════════════════════════════════════
#  МЕНЮ ЖУРНАЛА (для владельца)
# ═══════════════════════════════════════════════════════════════

async def show_journal_menu(query, db, admin_id: int) -> None:
    """Показывает меню управления журналом."""
    channel_id = _get_journal_channel(db)

    if channel_id:
        status = f"✅ Подключён: <code>{channel_id}</code>"
        btn_connect = InlineKeyboardButton("🔄 Сменить канал", callback_data="journal_connect")
        btn_disconnect = InlineKeyboardButton("❌ Отключить", callback_data="journal_disconnect")
        btn_test = InlineKeyboardButton("📝 Тест", callback_data="journal_test")
        extra_row = [btn_disconnect, btn_test]
    else:
        status = "❌ Не подключён"
        btn_connect = InlineKeyboardButton("🔗 Подключить канал", callback_data="journal_connect")
        extra_row = []

    # Статистика
    ensure_journal_tables(db)
    db.cursor.execute('SELECT COUNT(*) as cnt FROM journal_messages')
    total = db.cursor.fetchone()['cnt']

    db.cursor.execute(
        "SELECT COUNT(*) as cnt FROM journal_messages WHERE created_at >= datetime('now', '-24 hours')"
    )
    today = db.cursor.fetchone()['cnt']

    text = (
        f"📢 <b>ЖУРНАЛ СОБЫТИЙ</b>\n"
        f"{'━' * 24}\n\n"
        f"📡 Статус: {status}\n"
        f"📊 Всего записей: <b>{total}</b>\n"
        f"📅 За 24 часа: <b>{today}</b>\n\n"
        f"<b>Хештеги для поиска в канале:</b>\n"
        f"<code>#Вход #Выход #Мут #Бан</code>\n"
        f"<code>#Триггер #Опрос #Профиль #Админ</code>"
    )

    keyboard = [[btn_connect]]
    if extra_row:
        keyboard.append(extra_row)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="panel_main")])

    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"show_journal_menu error: {e}")


async def journal_connect_start(query, context, db, admin_id: int) -> None:
    """Ожидание пересланного сообщения из канала."""
    context.user_data['owner_awaiting'] = 'journal_connect'
    text = (
        "🔗 <b>Подключение канала-журнала</b>\n\n"
        "1. Добавьте бота как <b>админа</b> в канал\n"
        "2. Перешлите сюда <b>любое сообщение</b> из этого канала\n\n"
        "<i>Или отправьте ID канала (например: -1001234567890)</i>"
    )
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="owner_journal")]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def journal_disconnect(query, db, admin_id: int) -> None:
    """Отключение канала."""
    db.set_setting('journal_channel_id', '')
    await query.answer("✅ Канал-журнал отключён.", show_alert=True)
    await show_journal_menu(query, db, admin_id)


async def journal_test(query, context, db, admin_id: int) -> None:
    """Отправка тестового сообщения в журнал."""
    channel_id = _get_journal_channel(db)
    if not channel_id:
        await query.answer("❌ Канал не подключён.", show_alert=True)
        return

    try:
        await context.bot.send_message(
            chat_id=channel_id,
            text="✅ <b>Тест журнала</b>\n\nЕсли вы видите это сообщение — журнал работает!",
            parse_mode='HTML',
        )
        await query.answer("✅ Тестовое сообщение отправлено!", show_alert=True)
    except Exception as e:
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
#  FSM: ОБРАБОТКА ВВОДА (ID канала или пересланное сообщение)
# ═══════════════════════════════════════════════════════════════

async def handle_journal_text_input(update, context, db) -> bool:
    """
    Обработчик ввода ID канала / пересланного сообщения.
    Вызывается из message_handler.
    Возвращает True если обработано.
    """
    if context.user_data.get('owner_awaiting') != 'journal_connect':
        return False

    context.user_data.pop('owner_awaiting', None)
    message = update.effective_message

    channel_id = None

    # Пересланное сообщение из канала
    if message.forward_from_chat:
        channel_id = message.forward_from_chat.id
    elif message.text:
        # Ручной ввод ID
        text = message.text.strip()
        try:
            channel_id = int(text)
        except (ValueError, TypeError):
            await message.reply_text(
                "❌ Некорректный ID.\nПерешлите сообщение из канала или введите ID.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 К журналу", callback_data="owner_journal")]
                ])
            )
            return True

    if not channel_id:
        await message.reply_text("❌ Не удалось определить канал.")
        return True

    # Проверяем, что бот — админ канала
    try:
        member = await context.bot.get_chat_member(channel_id, (await context.bot.get_me()).id)
        if member.status not in ('administrator', 'creator'):
            await message.reply_text(
                "❌ Бот не является админом этого канала.\n"
                "Добавьте бота как администратора и попробуйте снова.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Попробовать снова", callback_data="journal_connect")]
                ])
            )
            return True
    except Exception as e:
        await message.reply_text(
            f"❌ Не удалось проверить канал: {e}\n"
            f"Убедитесь, что бот добавлен как админ.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Попробовать снова", callback_data="journal_connect")]
            ])
        )
        return True

    # Сохраняем
    db.set_setting('journal_channel_id', str(channel_id))

    # Тестовое сообщение
    try:
        await context.bot.send_message(
            chat_id=channel_id,
            text="✅ <b>Канал-журнал подключён!</b>\n\nСюда будут приходить логи событий бота.",
            parse_mode='HTML',
        )
    except Exception:
        pass

    await message.reply_text(
        f"✅ Канал <code>{channel_id}</code> подключён как журнал!",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 К журналу", callback_data="owner_journal")]
        ])
    )
    logger.info(f"Journal channel connected: {channel_id}")
    return True
