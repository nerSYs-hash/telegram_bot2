"""
Модуль для работы с журналом событий
Реализует п.5 ТЗ - логирование событий согласно форматам блоков А-Ж
"""
import logging
from aiogram import Bot
from datetime import datetime, timezone, timedelta
from typing import Optional

from database import (
    get_setting,
    add_journal_message,
    get_last_profile_message,
    delete_journal_message,
    get_user
)
from constants import Hashtags
from utils.keyboards import create_dm_keyboard

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))


# ═══════════════════════════════════════════════════════════
#  БЛОКИ — вспомогательные функции
# ═══════════════════════════════════════════════════════════

def _block_b(user: dict, admin_id: int = None, change_line: str = None) -> str:
    """
    Блок В — идентификация пользователя (динамический).
    change_line — строка вида «Никнейм: @old → @new» или «Пользователь: Иван → Пётр»,
    заменяет соответствующее поле в блоке.
    """
    parts = []

    # Пользователь: имя
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if change_line and change_line.startswith("Пользователь:"):
        parts.append(change_line)
    elif full_name:
        parts.append(f"Пользователь: {full_name}")

    # Никнейм: @username
    if change_line and change_line.startswith("Никнейм:"):
        parts.append(change_line)
    elif user.get('username'):
        parts.append(f"Никнейм: @{user['username']}")

    # ID
    parts.append(f"#user{user['tg_id']}")

    # Администратор (для исключения / блокировки / разблокировки)
    if admin_id:
        admin = None
        try:
            import asyncio
            # get_user async — получим синхронно через кэш если доступен
            # Используем ID как fallback
            pass
        except Exception:
            pass
        parts.append(f"Администратор: ID {admin_id}")

    return "\n".join(parts)


def _block_b_with_admin_name(user: dict, admin_user: Optional[dict], change_line: str = None) -> str:
    """Блок В с полным именем администратора."""
    parts = []

    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if change_line and change_line.startswith("Пользователь:"):
        parts.append(change_line)
    elif full_name:
        parts.append(f"Пользователь: {full_name}")

    if change_line and change_line.startswith("Никнейм:"):
        parts.append(change_line)
    elif user.get('username'):
        parts.append(f"Никнейм: @{user['username']}")

    parts.append(f"#user{user['tg_id']}")

    if admin_user:
        if admin_user.get('username'):
            parts.append(f"Администратор: @{admin_user['username']}")
        else:
            admin_name = f"{admin_user.get('first_name', '')} {admin_user.get('last_name', '')}".strip()
            parts.append(f"Администратор: {admin_name or admin_user['tg_id']}")

    return "\n".join(parts)


def _block_g(user: dict) -> str:
    """Блок Г — анкетные данные (динамический, только заполненные поля)."""
    parts = []
    if user.get('q_name'):
        parts.append(f"Имя: {user['q_name']}")
    if user.get('q_age'):
        parts.append(f"Возраст: {user['q_age']}")
    if user.get('q_city'):
        parts.append(f"Город: {user['q_city']}")
    if user.get('q_therapy'):
        parts.append(f"Терапия: {user['q_therapy']}")
    return "\n".join(parts)


def _block_e(label: str, dt: Optional[datetime] = None) -> str:
    """Блок Е — дата события."""
    if dt is None:
        dt = datetime.now(MSK)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    return f"📅 {label}: {dt.strftime('%d.%m.%Y %H:%M')} МСК"


def _now_e(label: str = "Дата") -> str:
    return _block_e(label, datetime.now(MSK))


# ═══════════════════════════════════════════════════════════
#  ОТПРАВКА В КАНАЛ
# ═══════════════════════════════════════════════════════════

async def get_journal_channel_id() -> Optional[int]:
    """Получение ID канала журнала из БД."""
    channel_id = await get_setting("journal_channel_id")
    if channel_id:
        try:
            return int(channel_id)
        except (ValueError, TypeError):
            pass
    return None


async def check_bot_is_admin(bot: Bot, channel_id: int) -> bool:
    """Проверка, является ли бот администратором канала."""
    try:
        bot_member = await bot.get_chat_member(channel_id, bot.id)
        return bot_member.status in ['administrator', 'creator']
    except Exception:
        return False


async def send_to_journal(
    bot: Bot,
    text: str,
    msg_type: str = "info",
    user_id: Optional[int] = None,
    add_dm_button: bool = False
) -> Optional[int]:
    """Отправка сообщения в канал-журнал."""
    journal_channel_id = await get_journal_channel_id()
    if not journal_channel_id:
        logger.warning("JOURNAL_CHANNEL_ID not set, skipping journal entry")
        return None

    reply_markup = None
    if add_dm_button and user_id:
        reply_markup = create_dm_keyboard(user_id)

    try:
        msg = await bot.send_message(
            journal_channel_id,
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        await add_journal_message(msg.message_id, journal_channel_id, msg_type, user_id)
        logger.info(f"Sent {msg_type} message to journal (ID: {msg.message_id})")
        return msg.message_id
    except Exception as e:
        logger.error(f"Failed to send message to journal: {e}")
        return None


async def send_photo_to_journal(
    bot: Bot,
    photo_id: str,
    caption: str = "",
    user_id: Optional[int] = None,
    add_dm_button: bool = False
) -> Optional[int]:
    """Отправка фото в канал-журнал."""
    journal_channel_id = await get_journal_channel_id()
    if not journal_channel_id:
        return None

    reply_markup = None
    if add_dm_button and user_id:
        reply_markup = create_dm_keyboard(user_id)

    try:
        msg = await bot.send_photo(
            journal_channel_id,
            photo_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        await add_journal_message(msg.message_id, journal_channel_id, "photo", user_id)
        return msg.message_id
    except Exception as e:
        logger.error(f"Failed to send photo to journal: {e}")
        return None


async def update_profile_message(
    bot: Bot,
    user_id: int,
    new_text: str,
) -> Optional[int]:
    """
    Обновление #Профиль-сообщения: удаляет предыдущее, отправляет новое.
    П.5.3.1 — в канале всегда только актуальная информация.
    """
    journal_channel_id = await get_journal_channel_id()
    if not journal_channel_id:
        return None

    last_msg_id = await get_last_profile_message(user_id, journal_channel_id)
    if last_msg_id:
        try:
            await bot.delete_message(journal_channel_id, last_msg_id)
            await delete_journal_message(last_msg_id)
            logger.info(f"Deleted old #Профиль message {last_msg_id} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete old profile message: {e}")

    return await send_to_journal(
        bot, new_text, msg_type="profile",
        user_id=user_id, add_dm_button=True
    )


# ═══════════════════════════════════════════════════════════
#  СОБЫТИЯ ЖУРНАЛА (п.5.2)
# ═══════════════════════════════════════════════════════════

async def log_join(bot: Bot, user_id: int, chat_name: str = ""):
    """
    5.2.1 — Вход пользователя в чат.
    Формат: Блок А + Блок В + Блок Г (если заполнена анкета) + Блок Е + Блок Ж
    """
    user = await get_user(user_id)
    if not user:
        return

    b = _block_b(user)
    g = _block_g(user)

    lines = [Hashtags.JOIN, "", b]
    if g:
        lines += ["", g]
    lines += ["", _now_e("Дата вступления")]

    text = "\n".join(lines)
    return await send_to_journal(bot, text, "join", user_id, add_dm_button=True)


async def log_exit(bot: Bot, user_id: int, chat_name: str = "", kicked_by: Optional[int] = None):
    """
    5.2.2 — Выход (самостоятельный).
    5.2.3 — Исключение администратором.
    """
    user = await get_user(user_id)
    if not user:
        return

    admin_user = None
    if kicked_by:
        admin_user = await get_user(kicked_by)

    hashtag = Hashtags.KICK if kicked_by else Hashtags.EXIT
    b = _block_b_with_admin_name(user, admin_user)
    date_label = "Дата исключения" if kicked_by else "Дата выхода"

    lines = [hashtag, "", b, "", _now_e(date_label)]
    text = "\n".join(lines)
    return await send_to_journal(bot, text, "kick" if kicked_by else "exit", user_id, add_dm_button=True)


async def log_profile_username_change(bot: Bot, user_id: int, old_username: Optional[str], new_username: Optional[str]):
    """
    5.2.4 — Смена @Username (было → стало).
    5.2.5 — Удаление @Username (было → null).
    5.2.6 — Присвоение @Username (null → стало).
    """
    user = await get_user(user_id)
    if not user:
        return

    old_str = f"@{old_username}" if old_username else "null"
    new_str = f"@{new_username}" if new_username else "null"
    change_line = f"Никнейм: {old_str} → {new_str}"

    b = _block_b(user, change_line=change_line)

    # Блок Г только при смене (оба значения не null) — п.5.2.4
    g = _block_g(user) if (old_username and new_username) else ""

    joined_at = None
    if user.get('created_at'):
        try:
            joined_at = datetime.fromisoformat(user['created_at'])
        except (ValueError, TypeError):
            pass

    lines = [Hashtags.PROFILE, "", b]
    if g:
        lines += ["", g]
    lines += ["", _block_e("Дата вступления", joined_at)]

    text = "\n".join(lines)
    return await update_profile_message(bot, user_id, text)


async def log_profile_name_change(bot: Bot, user_id: int, old_name: str, new_name: str):
    """
    5.2.7 — Смена имени (first name / last name).
    Формат: Блок А + Блок В (изменение) + Блок Г + Блок Е (дата заявки) + Блок Ж
    """
    user = await get_user(user_id)
    if not user:
        return

    change_line = f"Пользователь: {old_name} → {new_name}"
    b = _block_b(user, change_line=change_line)
    g = _block_g(user)

    joined_at = None
    if user.get('created_at'):
        try:
            joined_at = datetime.fromisoformat(user['created_at'])
        except (ValueError, TypeError):
            pass

    lines = [Hashtags.PROFILE, "", b]
    if g:
        lines += ["", g]
    lines += ["", _block_e("Дата заявки", joined_at)]

    text = "\n".join(lines)
    return await update_profile_message(bot, user_id, text)


async def log_photo_change(bot: Bot, user_id: int, photo_id: str = None):
    """
    5.2.8 — Смена аватара / открытие аватара.
    Формат: Блок А + Блок В (без анкетных данных) + Блок Ж
    """
    user = await get_user(user_id)
    if not user:
        return

    b = _block_b(user)
    text = f"{Hashtags.PHOTO}\n\n{b}"

    if photo_id:
        return await send_photo_to_journal(bot, photo_id, text, user_id, add_dm_button=True)
    return await send_to_journal(bot, text, "photo", user_id, add_dm_button=True)


async def log_inactivity(bot: Bot, user_id: int):
    """
    5.2.9 — Неактивность пользователя (60+ дней офлайн).
    Формат: Блок А + Блок В (без анкетных данных) + текст активности + Блок Ж
    """
    user = await get_user(user_id)
    if not user:
        return

    b = _block_b(user)
    activity_text = "Активность: Пользователь не был онлайн более 60 дней."

    lines = [Hashtags.ACTIVITY, "", b, "", activity_text]
    text = "\n".join(lines)
    return await send_to_journal(bot, text, "activity", user_id, add_dm_button=True)


async def log_block(bot: Bot, user_id: int, admin_id: int, reason: str):
    """
    5.2.10 — Блокировка пользователя (добавление в ЧС).
    Формат: Блок А + Блок В (с Администратором) + Причина + Блок Е
    Кнопка Ж не предусмотрена спецификацией для этого события.
    """
    user = await get_user(user_id)
    admin_user = await get_user(admin_id) if admin_id else None
    if not user:
        return

    b = _block_b_with_admin_name(user, admin_user)

    lines = [
        Hashtags.BLOCKED, "",
        b, "",
        f"Причина: {reason}", "",
        _now_e("Дата блокировки")
    ]
    text = "\n".join(lines)
    return await send_to_journal(bot, text, "block", user_id, add_dm_button=False)


async def log_unblock(bot: Bot, user_id: int, admin_id: int):
    """
    5.2.11 — Разблокировка пользователя (удаление из ЧС).
    Формат: Блок А + Блок В (с Администратором) + Блок Е
    """
    user = await get_user(user_id)
    admin_user = await get_user(admin_id) if admin_id else None
    if not user:
        return

    b = _block_b_with_admin_name(user, admin_user)

    lines = [Hashtags.UNBLOCKED, "", b, "", _now_e("Дата разблокировки")]
    text = "\n".join(lines)
    return await send_to_journal(bot, text, "unblock", user_id, add_dm_button=False)


# Обратная совместимость — вызывается из admin.py при одобрении/отказе
async def log_approval(bot: Bot, user_id: int, admin_id: int, chat_name: str = ""):
    """Логирование одобрения (при необходимости добавить в канал)."""
    pass  # Одобрение отображается в уведомлении, не в канале-журнале


async def log_rejection(bot: Bot, user_id: int, admin_id: int, reason: str, chat_name: str = ""):
    """Логирование отказа (при необходимости добавить в канал)."""
    pass  # Отказ отображается в уведомлении, не в канале-журнале


async def log_profile_change(bot: Bot, user_id: int, changes: list):
    """
    Устаревший API — оставлен для обратной совместимости.
    Новый код должен вызывать log_profile_username_change / log_profile_name_change.
    """
    user = await get_user(user_id)
    if not user:
        return

    b = _block_b(user)
    changes_text = "\n".join(changes) if changes else ""
    g = _block_g(user)

    lines = [Hashtags.PROFILE, "", b]
    if changes_text:
        lines += ["", changes_text]
    if g:
        lines += ["", g]
    lines += ["", _now_e("Дата")]

    text = "\n".join(lines)
    return await update_profile_message(bot, user_id, text)


async def log_event(bot: Bot, event_type: str, user_id: int, **kwargs):
    """Общая функция логирования для нестандартных событий."""
    user = await get_user(user_id)
    if not user:
        return

    b = _block_b(user)
    extra = "\n".join(f"{k}: {v}" for k, v in kwargs.items() if v is not None)

    lines = [f"#{event_type}", "", b]
    if extra:
        lines += ["", extra]
    lines += ["", _now_e("Дата")]

    text = "\n".join(lines)
    return await send_to_journal(bot, text, event_type.lower(), user_id, add_dm_button=True)
