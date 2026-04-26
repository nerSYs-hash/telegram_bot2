#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модерация в чате — команды для админов.

Путь: handlers/moderation.py

Команды (только через reply_to_message, только для is_admin/is_owner):
  /mute [время]   — мут пользователя (5m, 10m, 1h, 12h, 1d)
  /unmute          — снятие мута
  /ban             — бан пользователя
  /restrict        — инлайн-панель тонкой настройки прав
"""

import logging
import re
import time
from typing import Optional, Tuple

from telegram import (
    Update, ChatPermissions,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  ХЕЛПЕРЫ
# ═══════════════════════════════════════════════════════════════

# Допустимые форматы: 5m, 10m, 30m, 1h, 12h, 1d, 7d
_TIME_RE = re.compile(r'^(\d+)\s*([mhdMHD])$')

_TIME_MULTIPLIERS = {
    'm': 60,
    'h': 3600,
    'd': 86400,
}


def parse_duration(text: str) -> Optional[Tuple[int, str]]:
    """
    Парсит строку вроде '5m', '1h', '1d'.
    Возвращает (секунды, человекочитаемое) или None.
    """
    text = text.strip().lower()
    m = _TIME_RE.match(text)
    if not m:
        return None

    value = int(m.group(1))
    unit = m.group(2)

    if value <= 0:
        return None

    seconds = value * _TIME_MULTIPLIERS[unit]

    # Telegram не разрешает мут менее 30 секунд и более 366 дней
    if seconds < 30 or seconds > 366 * 86400:
        return None

    labels = {'m': 'мин.', 'h': 'ч.', 'd': 'д.'}
    human = f"{value} {labels[unit]}"
    return seconds, human


def _user_link(user) -> str:
    """HTML-ссылка на пользователя."""
    name = user.first_name or "Пользователь"
    return f'<a href="tg://user?id={user.id}">{name}</a>'


async def _is_admin_or_owner(db, user_id: int, main_admin_id: int) -> bool:
    """
    Проверяет, может ли user_id модерировать чат.

    Переходный период (V1.12.10f): обе системы работают параллельно.
    1) main_admin_id — всегда True
    2) TG-админство (bot_database.db.users.is_admin/is_owner) — старая модель
    3) Permissions: moderation.delete (pulse_bot.db.role_permissions) — новая модель
    Со временем TG-админство уйдёт, останется только permissions.
    """
    if user_id == main_admin_id:
        return True
    user_data = db.get_user(user_id)
    if user_data and (user_data['is_admin'] or user_data['is_owner']):
        return True

    try:
        from bot_permissions import user_has
        if await user_has(user_id, "moderation.delete"):
            return True
    except Exception:
        pass

    return False


async def _is_target_protected(db, target_id: int, main_admin_id: int) -> bool:
    """Защита: нельзя мутить/банить других админов/владельца."""
    if target_id == main_admin_id:
        return True
    target_data = db.get_user(target_id)
    if target_data and (target_data['is_admin'] or target_data['is_owner']):
        return True
    return False


async def _delete_silently(message) -> None:
    """Пытается удалить сообщение, молча игнорирует ошибку."""
    try:
        await message.delete()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
#  /mute [время]
# ═══════════════════════════════════════════════════════════════

async def mute_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    main_admin_id: int,
    target_chat_id: int,
) -> None:
    """Мут пользователя по реплаю. Использование: /mute 5m|10m|1h|12h|1d"""
    message = update.effective_message
    user = update.effective_user

    if not await _is_admin_or_owner(db, user.id, main_admin_id):
        return

    if not message.reply_to_message:
        await message.reply_text("↩️ Ответьте на сообщение пользователя, которого хотите замутить.")
        return

    target = message.reply_to_message.from_user
    if not target:
        return

    if await _is_target_protected(db, target.id, main_admin_id):
        await message.reply_text("⛔ Нельзя замутить админа или владельца.")
        return

    # Парсим время; без аргумента — навсегда
    permanent = not context.args
    if permanent:
        seconds, human = 0, "навсегда"
    else:
        parsed = parse_duration(context.args[0])
        if not parsed:
            await message.reply_text(
                "❌ Неверный формат.\nИспользуйте: <code>/mute 5m</code>, "
                "<code>/mute 1h</code>, <code>/mute 1d</code>\n"
                "Без времени — навсегда: <code>/mute</code>",
                parse_mode='HTML',
            )
            return
        seconds, human = parsed

    restrict_kwargs = dict(
        chat_id=target_chat_id,
        user_id=target.id,
        permissions=ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        ),
    )
    if not permanent:
        restrict_kwargs['until_date'] = int(time.time()) + seconds

    try:
        await context.bot.restrict_chat_member(**restrict_kwargs)

        duration_text = f"на <b>{human}</b>" if not permanent else "<b>навсегда</b>"
        await message.reply_text(
            f"🔇 {_user_link(target)} замучен {duration_text}",
            parse_mode='HTML',
        )
        await _delete_silently(message)
        logger.info(f"MUTE: {target.id} by {user.id} for {human} ({seconds}s, until_ts={until_date})")

        # Журнал
        try:
            from handlers.journal_handlers import log_mute
            from datetime import datetime, timezone
            await log_mute(
                context.bot, db, target.id, user.id,
                duration_human=human,
                chat=message.chat,
                target_user=target,
                admin_user=user,
                trigger_message=message.reply_to_message,
                muted_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"Journal log_mute error: {e}")

    except Exception as e:
        logger.error(f"mute_command error: {e}")
        await message.reply_text(f"❌ Не удалось замутить: {e}")


# ═══════════════════════════════════════════════════════════════
#  /unmute
# ═══════════════════════════════════════════════════════════════

async def unmute_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    main_admin_id: int,
    target_chat_id: int,
) -> None:
    """Снятие мута по реплаю."""
    message = update.effective_message
    user = update.effective_user

    if not await _is_admin_or_owner(db, user.id, main_admin_id):
        return

    if not message.reply_to_message:
        await message.reply_text("↩️ Ответьте на сообщение пользователя для снятия мута.")
        return

    target = message.reply_to_message.from_user
    if not target:
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=target_chat_id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )

        await message.reply_text(
            f"🔊 {_user_link(target)} размучен",
            parse_mode='HTML',
        )
        await _delete_silently(message)
        logger.info(f"UNMUTE: {target.id} by {user.id}")

        # Журнал
        try:
            from handlers.journal_handlers import log_unmute
            from datetime import datetime, timezone
            await log_unmute(
                context.bot, db, target.id, user.id,
                chat=message.chat,
                target_user=target,
                admin_user=user,
                unmuted_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"Journal log_unmute error: {e}")

    except Exception as e:
        logger.error(f"unmute_command error: {e}")
        await message.reply_text(f"❌ Не удалось размутить: {e}")


# ═══════════════════════════════════════════════════════════════
#  /ban
# ═══════════════════════════════════════════════════════════════

async def ban_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    main_admin_id: int,
    target_chat_id: int,
) -> None:
    """Бан пользователя по реплаю."""
    message = update.effective_message
    user = update.effective_user

    if not await _is_admin_or_owner(db, user.id, main_admin_id):
        return

    if not message.reply_to_message:
        await message.reply_text("↩️ Ответьте на сообщение пользователя для бана.")
        return

    target = message.reply_to_message.from_user
    if not target:
        return

    if await _is_target_protected(db, target.id, main_admin_id):
        await message.reply_text("⛔ Нельзя забанить админа или владельца.")
        return

    try:
        await context.bot.ban_chat_member(
            chat_id=target_chat_id,
            user_id=target.id,
        )

        await message.reply_text(
            f"🚫 {_user_link(target)} забанен",
            parse_mode='HTML',
        )
        await _delete_silently(message)
        logger.info(f"BAN: {target.id} by {user.id}")

        # Журнал
        try:
            from handlers.journal_handlers import log_ban
            from datetime import datetime, timezone
            await log_ban(
                context.bot, db, target.id, user.id,
                chat=message.chat,
                target_user=target,
                admin_user=user,
                banned_at=datetime.now(timezone.utc),
                trigger_message=message.reply_to_message,
            )
        except Exception as e:
            logger.error(f"Journal log_ban error: {e}")

    except Exception as e:
        logger.error(f"ban_command error: {e}")
        await message.reply_text(f"❌ Не удалось забанить: {e}")


# ═══════════════════════════════════════════════════════════════
#  /unban
# ═══════════════════════════════════════════════════════════════

async def unban_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    main_admin_id: int,
    target_chat_id: int,
) -> None:
    """Разбан пользователя по реплаю."""
    message = update.effective_message
    user = update.effective_user

    if not await _is_admin_or_owner(db, user.id, main_admin_id):
        return

    if not message.reply_to_message:
        await message.reply_text("↩️ Ответьте на сообщение пользователя для разбана.")
        return

    target = message.reply_to_message.from_user
    if not target:
        return

    try:
        await context.bot.unban_chat_member(
            chat_id=target_chat_id,
            user_id=target.id,
            only_if_banned=True,
        )

        await message.reply_text(
            f"✅ {_user_link(target)} разбанен",
            parse_mode='HTML',
        )
        await _delete_silently(message)
        logger.info(f"UNBAN: {target.id} by {user.id}")

        # Журнал
        try:
            from handlers.journal_handlers import log_unban
            from datetime import datetime, timezone
            await log_unban(
                context.bot, db, target.id, user.id,
                chat=message.chat,
                target_user=target,
                admin_user=user,
                unbanned_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"Journal log_unban error: {e}")

    except Exception as e:
        logger.error(f"unban_command error: {e}")
        await message.reply_text(f"❌ Не удалось разбанить: {e}")


# ═══════════════════════════════════════════════════════════════
#  /restrict — инлайн-панель настройки прав
# ═══════════════════════════════════════════════════════════════

# Маппинг: ключ → (отображение, атрибуты ChatPermissions)
RESTRICT_PERMS = {
    'text':    ('💬 Текст',              ['can_send_messages']),
    'media':   ('📷 Фото/Видео',         ['can_send_photos', 'can_send_videos']),
    'voice':   ('🎤 Голосовые/Кружки',    ['can_send_voice_notes', 'can_send_video_notes']),
    'sticker': ('🎭 Гиф/Стикеры',        ['can_send_other_messages']),
}


def _build_restrict_keyboard(
    target_user_id: int,
    perms_state: dict,
) -> InlineKeyboardMarkup:
    """Строит клавиатуру с галочками для текущего состояния прав."""
    keyboard = []
    for key, (label, _attrs) in RESTRICT_PERMS.items():
        enabled = perms_state.get(key, True)
        icon = "✅" if enabled else "❌"
        keyboard.append([
            InlineKeyboardButton(
                f"{icon} {label}",
                callback_data=f"restrict_toggle_{key}_{target_user_id}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "💾 Применить",
            callback_data=f"restrict_apply_{target_user_id}",
        )
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="restrict_cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)


async def restrict_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    main_admin_id: int,
    target_chat_id: int,
) -> None:
    """Показывает инлайн-панель настройки прав по реплаю."""
    message = update.effective_message
    user = update.effective_user

    if not await _is_admin_or_owner(db, user.id, main_admin_id):
        return

    if not message.reply_to_message:
        await message.reply_text("↩️ Ответьте на сообщение пользователя для настройки прав.")
        return

    target = message.reply_to_message.from_user
    if not target:
        return

    if await _is_target_protected(db, target.id, main_admin_id):
        await message.reply_text("⛔ Нельзя ограничить админа или владельца.")
        return

    # Получаем текущие права пользователя в чате
    try:
        member = await context.bot.get_chat_member(target_chat_id, target.id)
        current = getattr(member, 'can_send_messages', True)

        # Определяем начальное состояние
        perms_state = {
            'text':    getattr(member, 'can_send_messages', True) if hasattr(member, 'can_send_messages') else True,
            'media':   getattr(member, 'can_send_photos', True) if hasattr(member, 'can_send_photos') else True,
            'voice':   getattr(member, 'can_send_voice_notes', True) if hasattr(member, 'can_send_voice_notes') else True,
            'sticker': getattr(member, 'can_send_other_messages', True) if hasattr(member, 'can_send_other_messages') else True,
        }
    except Exception:
        # Если не получилось — все права включены по умолчанию
        perms_state = {k: True for k in RESTRICT_PERMS}

    # Сохраняем в context для переключения кнопок
    ctx_key = f"restrict_{target.id}"
    context.chat_data[ctx_key] = perms_state

    text = (
        f"🛡 <b>Настройка прав</b>\n"
        f"Пользователь: {_user_link(target)}\n\n"
        f"Нажимайте для переключения, затем «💾 Применить»."
    )

    await message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=_build_restrict_keyboard(target.id, perms_state),
    )
    await _delete_silently(message)


async def handle_restrict_callback(
    query,
    data: str,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    main_admin_id: int,
    target_chat_id: int,
) -> None:
    """
    Обработчик callback_data для restrict-панели.
    Вызывается из callback_handler.py для data, начинающихся с 'restrict_'.
    """
    user = query.from_user

    if not await _is_admin_or_owner(db, user.id, main_admin_id):
        await query.answer("⛔ Нет доступа.", show_alert=True)
        return

    # ── Отмена ──
    if data == "restrict_cancel":
        try:
            await query.edit_message_text("❌ Настройка прав отменена.")
        except Exception:
            pass
        return

    # ── Переключение права ──
    if data.startswith("restrict_toggle_"):
        # restrict_toggle_{key}_{user_id}
        parts = data.replace("restrict_toggle_", "").rsplit("_", 1)
        if len(parts) != 2:
            await query.answer("❌ Ошибка.", show_alert=True)
            return

        perm_key, target_uid = parts[0], int(parts[1])
        ctx_key = f"restrict_{target_uid}"

        perms_state = context.chat_data.get(ctx_key)
        if not perms_state:
            perms_state = {k: True for k in RESTRICT_PERMS}
            context.chat_data[ctx_key] = perms_state

        # Переключаем
        perms_state[perm_key] = not perms_state.get(perm_key, True)

        try:
            await query.edit_message_reply_markup(
                reply_markup=_build_restrict_keyboard(target_uid, perms_state),
            )
        except Exception:
            pass
        await query.answer()
        return

    # ── Применение ──
    if data.startswith("restrict_apply_"):
        target_uid = int(data.replace("restrict_apply_", ""))
        ctx_key = f"restrict_{target_uid}"

        perms_state = context.chat_data.get(ctx_key, {k: True for k in RESTRICT_PERMS})

        # Собираем ChatPermissions
        perms_kwargs = {
            'can_send_messages':          perms_state.get('text', True),
            'can_send_photos':            perms_state.get('media', True),
            'can_send_videos':            perms_state.get('media', True),
            'can_send_voice_notes':       perms_state.get('voice', True),
            'can_send_video_notes':       perms_state.get('voice', True),
            'can_send_other_messages':    perms_state.get('sticker', True),
            # Остальные — разрешаем
            'can_send_audios':            True,
            'can_send_documents':         True,
            'can_send_polls':             True,
            'can_add_web_page_previews':  True,
        }

        try:
            await context.bot.restrict_chat_member(
                chat_id=target_chat_id,
                user_id=target_uid,
                permissions=ChatPermissions(**perms_kwargs),
            )

            # Формируем результат
            lines = []
            for key, (label, _) in RESTRICT_PERMS.items():
                icon = "✅" if perms_state.get(key, True) else "❌"
                lines.append(f"  {icon} {label}")

            result_text = (
                f"🛡 <b>Права обновлены</b>\n"
                f"👤 ID: <code>{target_uid}</code>\n\n"
                + "\n".join(lines)
            )
            await query.edit_message_text(result_text, parse_mode='HTML')
            logger.info(f"RESTRICT applied to {target_uid} by {user.id}: {perms_state}")

        except Exception as e:
            logger.error(f"restrict_apply error: {e}")
            await query.edit_message_text(f"❌ Ошибка: {e}")

        # Очистка
        context.chat_data.pop(ctx_key, None)
