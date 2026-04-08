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


def _get_journal_channel_2(db) -> tuple:
    """Возвращает (chat_id, thread_id) для второго канала журнала."""
    val = db.get_setting('journal_channel_id_2')
    thread = db.get_setting('journal_thread_id_2')
    if val:
        try:
            return int(val), (int(thread) if thread else None)
        except (ValueError, TypeError):
            pass
    return None, None


def _get_journal_channel_3(db) -> tuple:
    """Возвращает (chat_id, thread_id) для третьего канала журнала."""
    val = db.get_setting('journal_channel_id_3')
    thread = db.get_setting('journal_thread_id_3')
    if val:
        try:
            return int(val), (int(thread) if thread else None)
        except (ValueError, TypeError):
            pass
    return None, None


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
    channel_num: int = 1,
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
        channel_num: номер канала журнала (1, 2 или 3)
    """
    thread_id = None
    if channel_num == 2:
        channel_id, thread_id = _get_journal_channel_2(db)
    elif channel_num == 3:
        channel_id, thread_id = _get_journal_channel_3(db)
    else:
        channel_id = _get_journal_channel(db)

    if not channel_id:
        return

    full_text = text
    if hashtag:
        full_text = f"{hashtag}\n\n{text}"

    markup = _dm_button(user_id) if user_id else None

    send_kwargs = dict(
        chat_id=channel_id,
        text=full_text,
        parse_mode='HTML',
        reply_markup=markup,
        disable_web_page_preview=True,
    )
    if thread_id:
        send_kwargs['message_thread_id'] = thread_id

    try:
        msg = await bot.send_message(**send_kwargs)

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
    """Логирует вход пользователя в чат → второй канал."""
    tag = _user_tag(db, user_id)
    await log_event(
        bot, db, 'join',
        f"👋 {tag} вступил(а) в чат",
        user_id=user_id, hashtag="#Вход", channel_num=2
    )


async def log_leave(bot, db, user_id: int, reason: str = None) -> None:
    """Логирует выход пользователя из чата → второй канал."""
    tag = _user_tag(db, user_id)
    text = f"🚪 {tag} покинул(а) чат"
    if reason:
        text += f"\n📝 Причина: {reason}"
    await log_event(bot, db, 'leave', text, user_id=user_id, hashtag="#Выход", channel_num=2)


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
    """Логирует ответ exit-опроса → второй канал."""
    tag = _user_tag(db, user_id)
    await log_event(
        bot, db, 'exit_survey',
        f"📋 {tag} ответил(а) на опрос\n📝 Причина: {reason}",
        user_id=user_id, hashtag="#Опрос", channel_num=2
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

def _channel_status_line(db, num: int) -> str:
    """Возвращает строку статуса канала по номеру (1, 2, 3)."""
    if num == 1:
        cid = _get_journal_channel(db)
        return f"✅ <code>{cid}</code>" if cid else "❌ не задан"
    elif num == 2:
        cid, tid = _get_journal_channel_2(db)
        if cid:
            return f"✅ <code>{cid}</code>" + (f" тред <code>{tid}</code>" if tid else "")
        return "❌ не задан"
    elif num == 3:
        cid, tid = _get_journal_channel_3(db)
        if cid:
            return f"✅ <code>{cid}</code>" + (f" тред <code>{tid}</code>" if tid else "")
        return "❌ не задан"
    return "❌"


async def show_journal_menu(query, db, admin_id: int) -> None:
    """Показывает меню управления журналом (3 канала)."""
    ensure_journal_tables(db)
    db.cursor.execute('SELECT COUNT(*) as cnt FROM journal_messages')
    total = db.cursor.fetchone()['cnt']
    db.cursor.execute(
        "SELECT COUNT(*) as cnt FROM journal_messages WHERE created_at >= datetime('now', '-24 hours')"
    )
    today = db.cursor.fetchone()['cnt']

    s1 = _channel_status_line(db, 1)
    s2 = _channel_status_line(db, 2)
    s3 = _channel_status_line(db, 3)

    text = (
        f"📢 <b>ЖУРНАЛ СОБЫТИЙ</b>\n\n"
        f"📡 Канал 1 (общий): {s1}\n"
        f"📡 Канал 2 (вход/выход/опросы): {s2}\n"
        f"📡 Канал 3 (доп. канал): {s3}\n\n"
        f"📊 Всего записей: <b>{total}</b>\n"
        f"📅 За 24 часа: <b>{today}</b>\n\n"
        f"<b>Хештеги:</b> <code>#Вход #Выход #Мут #Бан #Триггер #Опрос #Профиль #Админ</code>"
    )

    keyboard = [
        [InlineKeyboardButton("⚙️ Канал 1", callback_data="journal_ch1_menu")],
        [InlineKeyboardButton("⚙️ Канал 2", callback_data="journal_ch2_menu")],
        [InlineKeyboardButton("⚙️ Канал 3", callback_data="journal_ch3_menu")],
        [InlineKeyboardButton("🔙 Назад", callback_data="panel_main")],
    ]

    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"show_journal_menu error: {e}")


async def show_journal_channel_menu(query, db, admin_id: int, num: int) -> None:
    """Sub-меню для конкретного канала (1, 2 или 3)."""
    labels = {
        1: "Канал 1 — общий журнал",
        2: "Канал 2 — входы/выходы/опросы",
        3: "Канал 3 — дополнительный",
    }
    title = labels.get(num, f"Канал {num}")
    status = _channel_status_line(db, num)

    text = (
        f"📢 <b>{title}</b>\n\n"
        f"Статус: {status}\n\n"
        f"Для канала 2/3 поддерживается тред (топик).\n"
        f"Введите ID чата или перешлите сообщение из канала/группы."
    )

    cb_connect = f"journal_ch{num}_connect"
    cb_thread = f"journal_ch{num}_thread"
    cb_disconnect = f"journal_ch{num}_disconnect"
    cb_test = f"journal_ch{num}_test"

    # Проверяем, подключён ли канал
    if num == 1:
        connected = bool(_get_journal_channel(db))
    else:
        cid, _ = (_get_journal_channel_2 if num == 2 else _get_journal_channel_3)(db)
        connected = bool(cid)

    keyboard = []
    if connected:
        keyboard.append([InlineKeyboardButton("🔄 Сменить ID", callback_data=cb_connect)])
        if num in (2, 3):
            keyboard.append([InlineKeyboardButton("🧵 Задать тред", callback_data=cb_thread)])
        keyboard.append([
            InlineKeyboardButton("❌ Отключить", callback_data=cb_disconnect),
            InlineKeyboardButton("📝 Тест", callback_data=cb_test),
        ])
    else:
        keyboard.append([InlineKeyboardButton("🔗 Подключить", callback_data=cb_connect)])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="owner_journal")])

    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        if 'not modified' not in str(e).lower():
            logger.error(f"show_journal_channel_menu error: {e}")


async def journal_connect_start(query, context, db, admin_id: int, num: int = 1) -> None:
    """Ожидание ввода ID канала (или пересылки) для канала num."""
    context.user_data['owner_awaiting'] = f'journal_connect_{num}'
    context.user_data['journal_connect_num'] = num
    text = (
        f"🔗 <b>Подключение канала {num}</b>\n\n"
        "1. Добавьте бота как <b>админа</b> в канал/группу\n"
        "2. Перешлите сюда <b>любое сообщение</b> из этого канала\n\n"
        "<i>Или отправьте ID чата (например: -1001234567890)</i>"
    )
    back_cb = f"journal_ch{num}_menu"
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=back_cb)]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def journal_thread_start(query, context, db, admin_id: int, num: int) -> None:
    """Ожидание ввода thread_id для канала num (только 2 или 3)."""
    context.user_data['owner_awaiting'] = f'journal_thread_{num}'
    context.user_data['journal_connect_num'] = num
    text = (
        f"🧵 <b>Тред для канала {num}</b>\n\n"
        "Отправьте ID топика (thread_id).\n"
        "Найдите его в ссылке: <code>t.me/c/CHATID/<b>THREADID</b>/...</code>\n\n"
        "<i>Отправьте 0 чтобы убрать тред.</i>"
    )
    back_cb = f"journal_ch{num}_menu"
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=back_cb)]]
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


async def journal_disconnect(query, db, admin_id: int, num: int = 1) -> None:
    """Отключение канала num."""
    if num == 1:
        db.set_setting('journal_channel_id', '')
    elif num == 2:
        db.set_setting('journal_channel_id_2', '')
        db.set_setting('journal_thread_id_2', '')
    elif num == 3:
        db.set_setting('journal_channel_id_3', '')
        db.set_setting('journal_thread_id_3', '')
    await query.answer(f"✅ Канал {num} отключён.", show_alert=True)
    await show_journal_channel_menu(query, db, admin_id, num)


async def journal_test(query, context, db, admin_id: int, num: int = 1) -> None:
    """Отправка тестового сообщения в канал num."""
    if num == 1:
        channel_id = _get_journal_channel(db)
        thread_id = None
    elif num == 2:
        channel_id, thread_id = _get_journal_channel_2(db)
    else:
        channel_id, thread_id = _get_journal_channel_3(db)

    if not channel_id:
        await query.answer("❌ Канал не подключён.", show_alert=True)
        return

    try:
        send_kwargs = dict(
            chat_id=channel_id,
            text=f"✅ <b>Тест журнала (канал {num})</b>\n\nЕсли вы видите это — канал работает!",
            parse_mode='HTML',
        )
        if thread_id:
            send_kwargs['message_thread_id'] = thread_id
        await context.bot.send_message(**send_kwargs)
        await query.answer("✅ Тестовое сообщение отправлено!", show_alert=True)
    except Exception as e:
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
#  FSM: ОБРАБОТКА ВВОДА (ID канала или пересланное сообщение)
# ═══════════════════════════════════════════════════════════════

async def handle_journal_text_input(update, context, db) -> bool:
    """
    Обработчик ввода ID канала / пересланного сообщения / thread_id.
    """
    awaiting = context.user_data.get('owner_awaiting', '')

    # Обработка ввода thread_id для канала 2 или 3
    if awaiting.startswith('journal_thread_'):
        num = int(awaiting.split('_')[-1])
        message = update.effective_message
        text = (message.text or '').strip()
        try:
            tid = int(text)
        except (ValueError, TypeError):
            await message.reply_text("❌ Некорректный thread_id. Отправьте число (или 0 чтобы убрать).")
            return True
        key = f'journal_thread_id_{num}'
        db.set_setting(key, '' if tid == 0 else str(tid))
        context.user_data.pop('owner_awaiting', None)
        context.user_data.pop('journal_connect_num', None)
        await message.reply_text(
            f"✅ Тред для канала {num} {'убран' if tid == 0 else f'задан: <code>{tid}</code>'}.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"⚙️ Канал {num}", callback_data=f"journal_ch{num}_menu")]
            ])
        )
        return True

    # Обработка ввода ID канала
    if not awaiting.startswith('journal_connect_'):
        return False

    num = int(awaiting.split('_')[-1])
    message = update.effective_message
    channel_id = None

    # ПРОВЕРКА ПЕРЕСЫЛКИ (v20+)
    if message.forward_origin:
        if hasattr(message.forward_origin, 'chat'):
            channel_id = message.forward_origin.chat.id
        elif hasattr(message.forward_origin, 'sender_chat'):
            channel_id = message.forward_origin.sender_chat.id

    elif message.text:
        text = message.text.strip()
        try:
            channel_id = int(text)
        except (ValueError, TypeError):
            back_cb = f"journal_ch{num}_menu"
            await message.reply_text(
                "❌ Некорректный ID.\nПерешлите сообщение из канала или введите ID.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data=back_cb)]
                ])
            )
            return True

    if not channel_id:
        await message.reply_text("❌ Не удалось определить канал.")
        return True

    # Проверяем, что бот — админ (только для каналов, где это нужно)
    retry_cb = f"journal_ch{num}_connect"
    try:
        member = await context.bot.get_chat_member(channel_id, (await context.bot.get_me()).id)
        if member.status not in ('administrator', 'creator'):
            await message.reply_text(
                "❌ Бот не является админом этого канала/группы.\n"
                "Добавьте бота как администратора и попробуйте снова.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Попробовать снова", callback_data=retry_cb)]
                ])
            )
            return True
    except Exception as e:
        await message.reply_text(
            f"❌ Не удалось проверить канал: {e}\n"
            f"Убедитесь, что бот добавлен как админ.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Попробовать снова", callback_data=retry_cb)]
            ])
        )
        return True

    # Сохраняем
    context.user_data.pop('owner_awaiting', None)
    context.user_data.pop('journal_connect_num', None)

    if num == 1:
        db.set_setting('journal_channel_id', str(channel_id))
    elif num == 2:
        db.set_setting('journal_channel_id_2', str(channel_id))
    elif num == 3:
        db.set_setting('journal_channel_id_3', str(channel_id))

    # Тестовое сообщение
    try:
        await context.bot.send_message(
            chat_id=channel_id,
            text=f"✅ <b>Канал {num} журнала подключён!</b>\n\nСюда будут приходить логи событий.",
            parse_mode='HTML',
        )
    except Exception:
        pass

    await message.reply_text(
        f"✅ Канал <code>{channel_id}</code> подключён как журнал {num}!",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚙️ Канал {num}", callback_data=f"journal_ch{num}_menu")]
        ])
    )
    logger.info(f"Journal channel {num} connected: {channel_id}")
    return True
