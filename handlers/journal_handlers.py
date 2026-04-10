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
import pytz
from datetime import datetime, timezone
from typing import Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
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


def _chat_id_clean(chat_id: int) -> str:
    """Возвращает числовую часть ID суперчата (без -100 префикса)."""
    s = str(abs(chat_id))
    return s[3:] if s.startswith('100') else s


def _fmt_user_block(user_obj, user_id: int, db) -> str:
    """
    Формирует строку блока В для пользователя/инициатора.
    Формат: <a href>First Last</a> [@user][id] #userID
    """
    if user_obj:
        first = getattr(user_obj, 'first_name', '') or ''
        last = getattr(user_obj, 'last_name', '') or ''
        full = f"{first} {last}".strip() or str(user_id)
        uname = getattr(user_obj, 'username', None)
    else:
        u = db.get_user(user_id)
        if u:
            full = u['first_name'] or str(user_id)
            uname = u['username']
        else:
            full = str(user_id)
            uname = None
    if uname:
        uname_part = f' <a href="https://t.me/{uname}">@{uname}</a>'
    else:
        uname_part = ''
    return (
        f'<a href="tg://user?id={user_id}">{full}</a>'
        f'{uname_part} [<a href="tg://user?id={user_id}">{user_id}</a>] #user{user_id}'
    )


def _fmt_time_msk(dt=None) -> str:
    """Единый формат времени для журнала: '09 мая 2026, 14:48:34 МСК'."""
    if dt is None:
        dt = datetime.now(_MSK)
    else:
        tz = getattr(dt, 'tzinfo', None)
        if tz is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(_MSK)
        else:
            dt = dt.astimezone(_MSK)
    return f"{dt.day:02d} {_MONTHS[dt.month - 1]} {dt.year}, {dt.strftime('%H:%M:%S')} МСК"


def _fmt_chat_block(chat) -> str:
    """Формат строки 'Группа: Title [chat_id] #cN' с кликабельными ссылками."""
    if not chat:
        return "Группа: —"
    chat_id = chat.id
    clean = _chat_id_clean(chat_id)
    title = chat.title or "Pulse 4ever"
    link = f"https://t.me/c/{clean}/2147483647"
    return f'Группа: <a href="{link}">{title}</a> [<a href="{link}">{chat_id}</a>] #c{clean}'


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
    markup: Optional[InlineKeyboardMarkup] = None,
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

    if markup is None:
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

_MSK = pytz.timezone('Europe/Moscow')
_MONTHS = ['января','февраля','марта','апреля','мая','июня',
           'июля','августа','сентября','октября','ноября','декабря']


async def log_join(
    bot: Bot,
    db,
    user_id: int,
    chat=None,
    tg_user=None,
    from_user=None,
    invite_link=None,
    joined_at=None,
    is_returning: bool = False,
) -> None:
    """
    Логирует вход пользователя в чат → канал 3.

    Args:
        chat: telegram.Chat объект чата
        tg_user: telegram.User — вступивший пользователь
        from_user: telegram.User — кто инициировал (admin/bot)
        invite_link: telegram.ChatInviteLink — ссылка-приглашение
        joined_at: datetime — время вступления
        is_returning: True если пользователь возвращается
    """
    lines = ["🆔 #Вход", ""]

    # ─ Блок Б: пригласительная ссылка (если есть) ─
    invite_display = None
    if invite_link:
        link_name = getattr(invite_link, 'name', None)
        link_url = getattr(invite_link, 'invite_link', None)
        invite_display = link_name or link_url
    if invite_display:
        lines.append(f"Пригласительная ссылка: {invite_display}")
        lines.append("")

    # ─ Блок В: группа ─
    if chat:
        chat_id = chat.id
        clean = _chat_id_clean(chat_id)
        title = chat.title or "Pulse 4ever"
        link = f"https://t.me/c/{clean}/2147483647"
        lines.append(f'Группа: <a href="{link}">{title}</a> [<a href="{link}">{chat_id}</a>] #c{clean}')
        lines.append("")

    # ─ Блок В: инициатор ─
    initiator = None
    if from_user and from_user.id != user_id:
        initiator = from_user
    elif invite_link:
        creator = getattr(invite_link, 'creator', None)
        if creator and creator.id != user_id:
            initiator = creator
    if initiator:
        lines.append(f"Инициатор: {_fmt_user_block(initiator, initiator.id, db)}")
        lines.append("")

    # ─ Блок В: пользователь ─
    lines.append(f"Пользователь: {_fmt_user_block(tg_user, user_id, db)}")
    lines.append("")

    # ─ Одобрено (кто принял заявку/добавил) ─
    if initiator:
        lines.append(f"Одобрено: {_fmt_user_block(initiator, initiator.id, db)}")
        lines.append("")

    # ─ Блок Е: время ─
    lines.append(f"🕐 {_fmt_time_msk(joined_at)}")

    # Дата первой регистрации при возврате
    u_db = db.get_user(user_id)
    if is_returning and u_db:
        try:
            first_seen = u_db['created_at']
            if first_seen:
                lines.append(f"📅 Первая регистрация: {first_seen}")
        except (KeyError, IndexError):
            pass

    text = "\n".join(lines)

    # ─ Блок Ж: кнопки действий ─
    action_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚫 Забанить", callback_data=f"jban_{user_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"jkick_{user_id}"),
        ],
        [
            InlineKeyboardButton("🔇 Заглушить навсегда", callback_data=f"jmute_{user_id}"),
        ],
    ])

    await log_event(
        bot, db, 'join', text,
        user_id=user_id,
        channel_num=3,
        markup=action_markup,
    )


async def log_leave(
    bot: Bot,
    db,
    user_id: int,
    chat=None,
    tg_user=None,
    left_at=None,
) -> None:
    """
    Логирует выход пользователя из чата → канал 3.

    Args:
        chat: telegram.Chat объект чата
        tg_user: telegram.User — покинувший пользователь
        left_at: datetime — время выхода
    """
    lines = ["⚠️ #Выход", ""]

    # ─ Блок В: группа ─
    if chat:
        chat_id = chat.id
        clean = _chat_id_clean(chat_id)
        title = chat.title or "Pulse 4ever"
        link = f"https://t.me/c/{clean}/2147483647"
        lines.append(f'Группа: <a href="{link}">{title}</a> [<a href="{link}">{chat_id}</a>] #c{clean}')
        lines.append("")

    # ─ Блок В: пользователь ─
    lines.append(f"Пользователь: {_fmt_user_block(tg_user, user_id, db)}")
    lines.append("")

    # ─ Блок Е: время ─
    lines.append(f"🕐 {_fmt_time_msk(left_at)}")

    text = "\n".join(lines)

    # ─ Блок Ж: кнопка «Написать в ЛС» ─
    await log_event(
        bot, db, 'leave', text,
        user_id=user_id,
        channel_num=3,
    )


async def log_kick(
    bot: Bot,
    db,
    target_id: int,
    admin_id: int,
    chat_id: int = None,
    chat_title: str = None,
    kicked_at=None,
    target_user=None,
    admin_user=None,
) -> None:
    """
    Логирует удаление пользователя из чата (#Исключен) → канал 3.

    Args:
        target_id: ID удалённого пользователя
        admin_id: ID администратора
        chat_id: ID чата (опционально)
        chat_title: название чата (опционально)
        kicked_at: datetime — время исключения
        target_user: telegram.User объект (опционально)
        admin_user: telegram.User объект (опционально)
    """
    admin_block = _fmt_user_block(admin_user, admin_id, db)
    target_block = _fmt_user_block(target_user, target_id, db)

    lines = ["🆘 #Исключен", ""]

    # ─ Блок В: группа ─
    if chat_id:
        clean = _chat_id_clean(chat_id)
        title = chat_title or "Pulse 4ever"
        link = f"https://t.me/c/{clean}/2147483647"
        lines.append(f'Группа: <a href="{link}">{title}</a> [<a href="{link}">{chat_id}</a>] #c{clean}')
        lines.append("")

    lines.append(f"Инициатор: {admin_block}")
    lines.append("")
    lines.append(f"Пользователь: {target_block}")
    lines.append("")

    # ─ Блок Е: время ─
    lines.append(f"🕐 {_fmt_time_msk(kicked_at)}")

    text = "\n".join(lines)

    # Без кнопок (user_id=None чтобы не добавлялась авто-кнопка ЛС)
    await log_event(bot, db, 'kick', text, user_id=None, channel_num=3)


async def log_ban(
    bot: Bot,
    db,
    target_id: int,
    admin_id: int,
    chat=None,
    target_user=None,
    admin_user=None,
    banned_at=None,
    trigger_message=None,
) -> None:
    """
    Логирует бан (#Бан) → канал 3. Без Блока Ж (кнопки действий).

    Args:
        chat: telegram.Chat
        target_user: telegram.User — кого банят
        admin_user: telegram.User — кто банит
        banned_at: datetime — время бана
        trigger_message: telegram.Message — сообщение-триггер (опционально)
    """
    lines = ["⚠️ #Бан", ""]

    # ─ Блок В: группа ─
    target_chat = chat or (trigger_message.chat if trigger_message else None)
    if target_chat:
        lines.append(_fmt_chat_block(target_chat))
        lines.append("")

    lines.append(f"Инициатор: {_fmt_user_block(admin_user, admin_id, db)}")
    lines.append("")
    lines.append(f"Пользователь: {_fmt_user_block(target_user, target_id, db)}")
    lines.append("")

    # ─ Сообщение-триггер (если есть) ─
    if trigger_message:
        cid = trigger_message.chat.id
        clean = _chat_id_clean(cid)
        msg_id = trigger_message.message_id
        msg_link = f"https://t.me/c/{clean}/{msg_id}"

        msg_date = trigger_message.date
        if msg_date:
            tz = getattr(msg_date, 'tzinfo', None)
            msg_dt = msg_date.replace(tzinfo=timezone.utc).astimezone(_MSK) if tz is None else msg_date.astimezone(_MSK)
            msg_ts = f"[{msg_dt.strftime('%Y-%m-%d %H:%M:%S')}]"
        else:
            msg_ts = ""

        lines.append(f'Сообщение пользователя: {msg_ts} <a href="{msg_link}">ветка</a>')
        lines.append(f'<a href="{msg_link}">Перейти к сообщению</a>')

        msg_text = trigger_message.text or trigger_message.caption or ''
        if msg_text:
            lines.append("")
            lines.append(msg_text)
        lines.append("")

    # ─ Блок Е: время ─
    lines.append(f"🕐 {_fmt_time_msk(banned_at)}")

    text = "\n".join(lines)

    # ─ Кнопки действий ─
    action_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔊 Размьютить", callback_data=f"jremute_{target_id}")],
        [
            InlineKeyboardButton("🚫 Забанить", callback_data=f"jban_{target_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"jkick_{target_id}"),
        ],
        [InlineKeyboardButton("🔇 Заглушить навсегда", callback_data=f"jmute_{target_id}")],
    ])

    await log_event(bot, db, 'ban', text, user_id=target_id, channel_num=3, markup=action_markup)


async def log_mute(
    bot: Bot,
    db,
    target_id: int,
    admin_id: int,
    duration_human: str = 'Навсегда',
    chat=None,
    target_user=None,
    admin_user=None,
    trigger_message=None,
    muted_at=None,
) -> None:
    """Логирует мут пользователя (#Мут) → канал 3."""
    target_block = _fmt_user_block(target_user, target_id, db)
    admin_block = _fmt_user_block(admin_user, admin_id, db)

    is_forever = duration_human.lower() in ('навсегда', 'forever', '∞', '♾️')
    duration_display = "♾️" if is_forever else f"на {duration_human}"

    lines = ["🔇 #Мут", ""]

    if chat:
        lines.append(_fmt_chat_block(chat))
        lines.append("")

    lines.append(f"Инициатор: {admin_block}")
    lines.append("")
    lines.append(f"Пользователь: {target_block}")
    lines.append("")
    lines.append(f"Действие: Запрещено писать {duration_display}")
    lines.append("")

    # ─ Сообщение-причина (реплай) ─
    if trigger_message:
        cid = trigger_message.chat.id if trigger_message.chat else (chat.id if chat else None)
        clean = _chat_id_clean(cid) if cid else ""
        msg_id = trigger_message.message_id
        thread_id = getattr(trigger_message, 'message_thread_id', None)
        if clean:
            if thread_id and thread_id != msg_id:
                msg_link = f"https://t.me/c/{clean}/{thread_id}/{msg_id}"
            else:
                msg_link = f"https://t.me/c/{clean}/{msg_id}"
        else:
            msg_link = ""

        msg_date = trigger_message.date
        if msg_date:
            tz = getattr(msg_date, 'tzinfo', None)
            msg_dt = msg_date.replace(tzinfo=timezone.utc).astimezone(_MSK) if tz is None else msg_date.astimezone(_MSK)
            msg_ts = f"[{msg_dt.strftime('%Y-%m-%d %H:%M:%S')}]"
        else:
            msg_ts = ""

        if msg_link:
            lines.append(f'Сообщение пользователя: {msg_ts} <a href="{msg_link}">ветка</a>')
            lines.append(f'<a href="{msg_link}">Перейти к сообщению</a>')
        else:
            lines.append(f"Сообщение пользователя: {msg_ts}")

        msg_text = trigger_message.text or trigger_message.caption or ''
        if msg_text:
            lines.append("")
            lines.append(msg_text)
        lines.append("")

    lines.append(f"🕐 {_fmt_time_msk(muted_at)}")

    text = "\n".join(lines)

    # ─ Кнопки: Размьютить / Забанить / Удалить ─
    action_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔊 Размьютить", callback_data=f"jremute_{target_id}")],
        [
            InlineKeyboardButton("🚫 Забанить", callback_data=f"jban_{target_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"jkick_{target_id}"),
        ],
    ])

    await log_event(bot, db, 'mute', text, user_id=target_id, channel_num=3, markup=action_markup)


async def log_unmute(
    bot: Bot,
    db,
    target_id: int,
    admin_id: int,
    chat=None,
    target_user=None,
    admin_user=None,
    unmuted_at=None,
) -> None:
    """Логирует снятие мута (#Размут) → канал 3."""
    target_block = _fmt_user_block(target_user, target_id, db)
    admin_block = _fmt_user_block(admin_user, admin_id, db)

    lines = ["✅ #Размут", ""]

    if chat:
        lines.append(_fmt_chat_block(chat))
        lines.append("")

    lines.append(f"Инициатор: {admin_block}")
    lines.append("")
    lines.append(f"Пользователь: {target_block}")
    lines.append("")

    # ─ Предыдущий мут ─
    try:
        db.cursor.execute(
            "SELECT created_at FROM journal_messages "
            "WHERE event_type='mute' AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (target_id,),
        )
        prev_mute = db.cursor.fetchone()
        if prev_mute:
            lines.append(f"Предыдущий мут: {prev_mute['created_at']}")
            lines.append("")
    except Exception:
        pass

    lines.append(f"🕐 {_fmt_time_msk(unmuted_at)}")
    text = "\n".join(lines)

    await log_event(bot, db, 'unmute', text, user_id=target_id, channel_num=3)


async def log_unban(
    bot: Bot,
    db,
    target_id: int,
    admin_id: int,
    chat=None,
    target_user=None,
    admin_user=None,
    unbanned_at=None,
) -> None:
    """Логирует разбан пользователя (#Разбан) → канал 3."""
    target_block = _fmt_user_block(target_user, target_id, db)
    admin_block = _fmt_user_block(admin_user, admin_id, db)

    lines = ["✅ #Разбан", ""]

    if chat:
        lines.append(_fmt_chat_block(chat))
        lines.append("")

    lines.append(f"Инициатор: {admin_block}")
    lines.append("")
    lines.append(f"Пользователь: {target_block}")
    lines.append("")

    # ─ Предыдущий бан ─
    try:
        db.cursor.execute(
            "SELECT text_preview, created_at FROM journal_messages "
            "WHERE event_type='ban' AND user_id=? ORDER BY created_at DESC LIMIT 1",
            (target_id,),
        )
        prev_ban = db.cursor.fetchone()
        if prev_ban:
            ban_dt_raw = prev_ban['created_at']
            lines.append(f"Предыдущий бан: {ban_dt_raw}")
            lines.append("")
    except Exception:
        pass

    lines.append(f"🕐 {_fmt_time_msk(unbanned_at)}")
    text = "\n".join(lines)

    await log_event(bot, db, 'unban', text, user_id=target_id, channel_num=3)


_TRIGGER_ACTION_LABELS = {
    'msg_chat': 'сообщение в чат',
    'msg_pm': 'сообщение в ЛС',
    'warn': 'предупреждение',
    'mute': 'мут',
    'ban': 'бан',
    'kick': 'удаление',
    'delete': 'удалить сообщение',
    'emoji': 'реакция эмодзи',
    'reply': 'ответ в чат',
}


def _localize_trigger_actions(action: str) -> str:
    """Переводит сырые ключи действий триггера на русский."""
    if not action:
        return "—"
    parts = [p.strip() for p in str(action).replace(';', ',').split(',') if p.strip()]
    out = []
    for p in parts:
        out.append(_TRIGGER_ACTION_LABELS.get(p.lower(), p))
    return ", ".join(out) if out else action


async def log_trigger(bot, db, user_id: int, trigger_name: str, action: str,
                      chat=None, tg_user=None, triggered_at=None,
                      trigger_message=None) -> None:
    """Логирует срабатывание триггера (#Триггер) → канал 3."""
    # Тег триггера: пробелы → подчёркивания, чтобы получился валидный хештег
    name_tag = (trigger_name or 'unknown').strip().replace(' ', '_')

    lines = ["⚡️ #Триггер", f"#{name_tag}", ""]

    if chat:
        lines.append(_fmt_chat_block(chat))
        lines.append("")

    lines.append(f"Пользователь: {_fmt_user_block(tg_user, user_id, db)}")
    lines.append("")

    action_ru = _localize_trigger_actions(action)
    lines.append(f"⚙️ Действие: {action_ru}")
    lines.append("")

    # ─ Сообщение, на которое сработал триггер ─
    if trigger_message:
        cid = trigger_message.chat.id if trigger_message.chat else (chat.id if chat else None)
        clean = _chat_id_clean(cid) if cid else ""
        msg_id = trigger_message.message_id
        thread_id = getattr(trigger_message, 'message_thread_id', None)
        if clean:
            if thread_id and thread_id != msg_id:
                msg_link = f"https://t.me/c/{clean}/{thread_id}/{msg_id}"
            else:
                msg_link = f"https://t.me/c/{clean}/{msg_id}"
        else:
            msg_link = ""

        msg_date = trigger_message.date
        if msg_date:
            tz = getattr(msg_date, 'tzinfo', None)
            msg_dt = msg_date.replace(tzinfo=timezone.utc).astimezone(_MSK) if tz is None else msg_date.astimezone(_MSK)
            msg_ts = f"[{msg_dt.strftime('%Y-%m-%d %H:%M:%S')}]"
        else:
            msg_ts = ""

        if msg_link:
            lines.append(f'Сообщение пользователя: {msg_ts} <a href="{msg_link}">ветка</a>')
            lines.append(f'<a href="{msg_link}">Перейти к сообщению</a>')
        else:
            lines.append(f"Сообщение пользователя: {msg_ts}")

        msg_text = trigger_message.text or trigger_message.caption or ''
        if msg_text:
            lines.append("")
            lines.append(msg_text)
        lines.append("")

    lines.append(f"🕐 {_fmt_time_msk(triggered_at)}")

    await log_event(
        bot, db, 'trigger', "\n".join(lines),
        user_id=user_id, channel_num=3
    )


async def log_blacklist(bot, db, target_id: int, admin_id: int, added: bool) -> None:
    """Логирует добавление/удаление из блэклиста → канал 3."""
    target_tag = _user_tag(db, target_id)
    admin_tag = _user_tag(db, admin_id)
    if added:
        text = f"🚫 {target_tag} добавлен в блэклист\n👮 {admin_tag}"
        hashtag = "#Блокировка"
    else:
        text = f"✅ {target_tag} убран из блэклиста\n👮 {admin_tag}"
        hashtag = "#Разблокировка"
    await log_event(bot, db, 'blacklist', text, user_id=target_id, hashtag=hashtag, channel_num=3)


async def log_admin_action(bot, db, admin_id: int, action_text: str) -> None:
    """Логирует административное действие (эмиссия, вайп и т.д.) → канал 3."""
    admin_tag = _user_tag(db, admin_id)
    await log_event(
        bot, db, 'admin',
        f"🔧 {admin_tag}\n{action_text}",
        hashtag="#Админ", channel_num=3
    )


async def log_exit_survey(bot, db, user_id: int, reason: str = '', survey_row=None,
                          chat=None, tg_user=None, surveyed_at=None) -> None:
    """Логирует ответ exit-опроса → канал 3.

    Args:
        reason: строка причины (для обратной совместимости)
        survey_row: sqlite3.Row из exit_interviews с полями
                    reason_category, reason_text, improvement, q3_event, q4_expectations
    """
    user_block = _fmt_user_block(tg_user, user_id, db)

    # Извлечение полей опроса
    def _get(row, key, default='—'):
        if not row:
            return default
        try:
            val = row[key]
            return val if val else default
        except (KeyError, IndexError):
            return default

    reason_cat = _get(survey_row, 'reason_category', reason or '—')
    reason_txt = _get(survey_row, 'reason_text')
    improvement = _get(survey_row, 'improvement')
    q3_event = _get(survey_row, 'q3_event')
    q4_expectations = _get(survey_row, 'q4_expectations')

    lines = ["📋 #Опрос", ""]

    if chat:
        lines.append(_fmt_chat_block(chat))
        lines.append("")

    lines.append(f"Пользователь: {user_block}")
    lines.append("")
    lines.append(f"📝 Причина: {reason_cat}")
    lines.append(f"1b. Детали/уточнения: {reason_txt}")
    lines.append(f"2. Что можно улучшить: {improvement}")
    lines.append(f"3. Конкретное событие: {q3_event}")
    lines.append(f"4. Ожидания при вступлении: {q4_expectations}")
    lines.append("")
    lines.append(f"🕐 {_fmt_time_msk(surveyed_at)}")
    text = "\n".join(lines)

    await log_event(
        bot, db, 'exit_survey', text,
        user_id=user_id, channel_num=3
    )


async def log_profile_change(
    bot: Bot,
    db,
    user_id: int,
    changes: str = '',
    tg_user=None,
    old_user_data=None,
    chat=None,
    changed_at=None,
) -> None:
    """
    Логирует изменение профиля (#Профиль) → канал 3.

    Args:
        tg_user: telegram.User — новое состояние
        old_user_data: sqlite3.Row — старые данные из БД
        chat: telegram.Chat — чат где было сообщение
        changed_at: datetime — время изменения
    """
    # ─ Блок А ─
    lines = ["👥 #Профиль", ""]

    # ─ Блок В: группа ─
    if chat:
        lines.append(_fmt_chat_block(chat))
        lines.append("")

    # ─ Было / Стало ─
    if old_user_data and tg_user:
        try:
            old_first = old_user_data['first_name'] or ''
            old_last = old_user_data['last_name'] or ''
        except (KeyError, IndexError):
            old_first, old_last = '', ''
        try:
            old_uname = old_user_data['username']
        except (KeyError, IndexError):
            old_uname = None

        old_full = f"{old_first} {old_last}".strip() or str(user_id)
        if old_uname:
            old_uname_part = f' <a href="https://t.me/{old_uname}">@{old_uname}</a>'
        else:
            old_uname_part = ''
        was_line = (
            f'<a href="tg://user?id={user_id}">{old_full}</a>'
            f'{old_uname_part} [<a href="tg://user?id={user_id}">{user_id}</a>] #user{user_id}'
        )
        became_line = _fmt_user_block(tg_user, user_id, db)

        lines.append(f"Было {was_line}")
        lines.append(f"Стало {became_line}")
    elif changes:
        lines.append(changes)

    lines.append("")
    lines.append(f"🕐 {_fmt_time_msk(changed_at)}")

    text = "\n".join(lines)

    # Без кнопок (user_id=None чтобы не добавлялась авто-кнопка ЛС)
    await log_event(bot, db, 'profile', text, user_id=None, channel_num=3)


async def log_activity(
    bot: Bot,
    db,
    user_id: int,
    chat_id: int = None,
    chat_title: str = None,
    tg_user=None,
    days_inactive: int = 60,
) -> None:
    """
    Логирует неактивность пользователя 60+ дней (#Активность) → канал 3.
    """
    lines = ["🏋️ #Активность", ""]
    lines.append(f"Пользователь неактивен более {days_inactive} дней.")
    lines.append("")

    # ─ Блок В: группа ─
    if chat_id:
        clean = _chat_id_clean(chat_id)
        title = chat_title or "Pulse 4ever"
        link = f"https://t.me/c/{clean}/2147483647"
        lines.append(f'Группа: <a href="{link}">{title}</a> [<a href="{link}">{chat_id}</a>] #c{clean}')
        lines.append("")

    lines.append(f"Пользователь: {_fmt_user_block(tg_user, user_id, db)}")
    lines.append("")
    lines.append(f"🕐 {_fmt_time_msk()}")

    text = "\n".join(lines)

    # ─ Блок Ж: кнопка «Написать в ЛС» ─
    await log_event(bot, db, 'inactivity', text, user_id=user_id, channel_num=3)


async def log_photo(
    bot: Bot,
    db,
    user_id: int,
    chat=None,
    tg_user=None,
    action: str = 'changed',
) -> None:
    """
    Логирует смену/открытие/скрытие фото профиля (#Фото) → канал 3.
    Без Блока Г, без Блока Е, без кнопок.

    Args:
        action: 'changed' — сменил фото, 'opened' — открыл доступ для всех,
                'removed'/'hidden' — скрыл/удалил фото профиля
    """
    if action == 'opened':
        action_text = "открыл(а) доступ к фото профиля для всех"
    elif action in ('removed', 'hidden'):
        action_text = "скрыл(а) фото профиля"
    else:
        action_text = "сменил(а) фото профиля"

    lines = ["📸 #Фото", ""]
    lines.append(f"Пользователь из Вашей группы {action_text}.")
    lines.append("")

    if chat:
        lines.append(_fmt_chat_block(chat))
        lines.append("")

    lines.append(f"Пользователь: {_fmt_user_block(tg_user, user_id, db)}")
    lines.append("")
    lines.append(f"🕐 {_fmt_time_msk()}")

    text = "\n".join(lines)

    # Без кнопок (user_id=None чтобы не добавлялась авто-кнопка ЛС)
    await log_event(bot, db, 'photo', text, user_id=None, channel_num=3)


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
        f"📡 Канал 1 (резерв): {s1}\n"
        f"📡 Канал 2 (резерв): {s2}\n"
        f"📡 Канал 3 (основной — все события): {s3}\n\n"
        f"📊 Всего записей: <b>{total}</b>\n"
        f"📅 За 24 часа: <b>{today}</b>\n\n"
        f"<b>Хештеги:</b> <code>#Вход #Выход #Исключен #Бан #Разбан #Мут #Размут #Профиль #Фото #Активность</code>"
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
        1: "Канал 1 — резерв",
        2: "Канал 2 — резерв",
        3: "Канал 3 — основной (все события)",
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
        "<i>Или введите ID чата:</i>\n"
        "• <code>-1002756313911</code> — только чат\n"
        "• <code>2756313911/2</code> — чат + топик (тред)\n"
        "• <code>-1002756313911/2</code> — тоже работает"
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
        thread_from_slash = None

        # Поддержка формата CHATID/THREADID (из ссылки t.me/c/...)
        if '/' in text:
            parts = text.split('/')
            text = parts[0].strip()
            try:
                thread_from_slash = int(parts[1].strip())
            except (ValueError, IndexError):
                pass

        try:
            raw = int(text)
            # Если ID без минуса и больше 0 — добавляем -100 префикс
            if raw > 0:
                channel_id = int(f"-100{raw}")
            else:
                channel_id = raw
        except (ValueError, TypeError):
            back_cb = f"journal_ch{num}_menu"
            await message.reply_text(
                "❌ Некорректный ID.\nПерешлите сообщение из канала или введите ID.\n"
                "<i>Форматы: -1001234567890 или 1234567890/2 (с тредом)</i>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data=back_cb)]
                ])
            )
            return True

        # Если из формата CHATID/THREADID — сразу сохраняем тред
        if thread_from_slash is not None and num in (2, 3):
            db.set_setting(f'journal_thread_id_{num}', str(thread_from_slash))

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
