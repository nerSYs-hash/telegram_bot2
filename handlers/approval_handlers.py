#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание: Логика одобрения заявок — регистрация пользователя, отправка ссылки,
          формирование Досье с аватарками и отправка в админский чат.
"""

import html
import asyncio
import logging
import re

from telegram import InputMediaPhoto

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
#  Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────────

def _build_city_tag(city: str) -> str:
    """Формирует хэштег города."""
    if not city:
        return "#Город_не_указан"
    normalized = city.strip().lower()
    if normalized in ("санкт-петербург", "спб", "питер", "saint-petersburg", "saint petersburg"):
        return "#СПБ"
    if normalized in ("москва", "мск", "moscow"):
        return "#МСК"
    # Любой другой город: заменить пробелы и дефисы на _
    tag = re.sub(r"[\s\-]+", "_", city.strip())
    return f"#{tag}"


def _build_dossier_text(reg_data: dict, target_user_id: int, admin_username: str) -> str:
    """Формирует HTML-текст Досье."""
    q_name    = html.escape(reg_data.get("q_name")    or "—")
    q_age     = html.escape(str(reg_data.get("q_age") or "—"))
    q_city    = html.escape(reg_data.get("q_city")    or "—")
    q_therapy = html.escape(reg_data.get("q_therapy") or "—")
    username  = reg_data.get("username")

    username_tag  = f"@{username}" if username else q_name
    city_tag      = _build_city_tag(reg_data.get("q_city") or "")
    id_tag        = f"#user{target_user_id}"
    tags_line     = f"{city_tag} {username_tag} {id_tag}"

    username_display = f"@{username}" if username else "—"

    text = (
        f"✅ <b>АНКЕТА ОДОБРЕНА</b>\n\n"
        f"👤 Имя: {q_name}\n"
        f"🎂 Возраст: {q_age}\n"
        f"🏙 Город: {q_city}\n"
        f"🔗 Username: {username_display}\n"
        f"🆔 ID: <code>{id_tag}</code>\n"
        f"💊 Терапия: {q_therapy}\n"
        f"👮‍♂️ Одобрил: {admin_username}\n\n"
        f"<code>{tags_line}</code>"
    )
    return text


async def _send_dossier(context, target_user_id: int, reg_data: dict, admin_user) -> None:
    """
    Формирует Досье и отправляет в admin_chat_id из context.bot_data.
    Если есть аватарки — альбом (до 3 фото), иначе — текст.
    Весь блок в try-except: ошибка досье не роняет основную логику.
    """
    admin_chat_id = context.bot_data.get("admin_chat_id")
    if not admin_chat_id:
        logger.warning("_send_dossier: admin_chat_id не задан в bot_data, пропускаем досье")
        return

    admin_username = (
        f"@{admin_user.username}" if admin_user.username else str(admin_user.id)
    )
    dossier_text = _build_dossier_text(reg_data, target_user_id, admin_username)

    try:
        # Получаем до 3 аватарок пользователя
        photos_result = await context.bot.get_user_profile_photos(
            user_id=target_user_id, limit=3
        )

        if photos_result and photos_result.total_count > 0:
            # Берём наибольший размер каждого фото
            media = []
            for i, photo_sizes in enumerate(photos_result.photos):
                best = photo_sizes[-1]  # последний элемент — наибольшее разрешение
                if i == 0:
                    media.append(InputMediaPhoto(
                        media=best.file_id,
                        caption=dossier_text,
                        parse_mode="HTML",
                    ))
                else:
                    media.append(InputMediaPhoto(media=best.file_id))

            await context.bot.send_media_group(
                chat_id=admin_chat_id,
                media=media,
            )
            logger.info(f"📸 Досье с {len(media)} фото отправлено в {admin_chat_id} для {target_user_id}")
        else:
            # Фото скрыты или отсутствуют
            no_photo_note = "\n\n<i>(❌ Аватарки скрыты настройками приватности пользователя)</i>"
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=dossier_text + no_photo_note,
                parse_mode="HTML",
            )
            logger.info(f"📄 Досье (без фото) отправлено в {admin_chat_id} для {target_user_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка отправки досье для {target_user_id}: {e}")


# ──────────────────────────────────────────────────────────────────────────────
#  Главная функция одобрения
# ──────────────────────────────────────────────────────────────────────────────

async def approve_application(
    query,
    context,
    app_id: int,
    target_user_id: int,
    app_data: dict,
    reg_data: dict,
    applied_at: str,
    main_db,
) -> None:
    """
    Полный цикл одобрения заявки:
      1. Обновляет БД регистрации и основную БД
      2. Уведомляет пользователя + отправляет одноразовую ссылку
      3. Отправляет Досье с аватарками в admin_chat
      4. Обновляет сообщение в чате администраторов (карточка 3.3.3)
    """
    from handlers.admin_moderation import _send_invite_link, _send_invite_friends_after_delay
    from database.db_friend import approve_application as db_approve_application, update_user
    from config import CHAT_ID
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    import html as _html

    joined_at = _msk_now()

    # 1. Одобряем в БД регистрации
    await db_approve_application(app_id, query.from_user.id)
    await update_user(target_user_id, status="approved")

    # 2. Регистрируем в основной БД (майнинг и т.д.)
    referrer_id = reg_data.get("referred_by") if reg_data else None
    if main_db:
        main_db.add_user(
            target_user_id,
            username=reg_data.get("username"),
            first_name=reg_data.get("first_name"),
            last_name=reg_data.get("last_name"),
        )
        if referrer_id:
            try:
                main_db.cursor.execute(
                    "UPDATE users SET referrer_id = ? WHERE user_id = ?",
                    (referrer_id, target_user_id),
                )
                main_db.conn.commit()
                logger.info(f"✅ Реферал {referrer_id} привязан к {target_user_id}")
            except Exception as e:
                logger.error(f"⚠️ Не удалось привязать реферала: {e}")

    # 3. Уведомляем пользователя
    user_name = reg_data.get("q_name") or reg_data.get("first_name") or "Друг"
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="🎉 Поздравляем! Твоя заявка одобрена.",
        )
    except Exception as e:
        logger.error(f"Не смог написать юзеру {target_user_id}: {e}")

    # Отправляем одноразовую ссылку
    await _send_invite_link(context.bot, target_user_id, user_name)

    # Через 1 минуту — сообщение «Приглашай друзей»
    asyncio.create_task(
        _send_invite_friends_after_delay(context.bot, target_user_id, user_name, delay=60)
    )

    # 4. Досье с аватарками → в admin_chat
    await _send_dossier(context, target_user_id, reg_data, query.from_user)

    # 5. Обновляем сообщение в чате администраторов (карточка 3.3.3)
    admin_name = (
        f"@{query.from_user.username}" if query.from_user.username else str(query.from_user.id)
    )
    is_returning = bool(reg_data.get("last_exit_at"))
    block_b = "#Возвращение" if is_returning else "#Новый"
    username_str = f"@{reg_data.get('username')}" if reg_data.get("username") else "нет"
    full_name = _html.escape(
        f"{reg_data.get('first_name') or ''} {reg_data.get('last_name') or ''}".strip()
        or reg_data.get("q_name") or "—"
    )
    user_link = f'<a href="tg://user?id={target_user_id}">{full_name}</a>'
    group_link = f'<a href="https://t.me/c/{str(CHAT_ID).replace("-100", "")}/1">PositivЭ</a>'

    card_text = (
        f"#Одобрено\n"
        f"{block_b}\n"
        f"Заявка одобрена {admin_name}\n\n"
        f"Группа: {group_link}\n"
        f"Пользователь: {user_link}\n"
        f"Никнейм: {username_str}\n"
        f"ID: <code>{target_user_id}</code>\n\n"
        f"<b>Анкета:</b>\n"
        f"Имя: {_html.escape(reg_data.get('q_name') or '—')}\n"
        f"Возраст: {reg_data.get('q_age') or '—'}\n"
        f"Город: {_html.escape(reg_data.get('q_city') or '—')}\n"
        f"Терапия: {_html.escape(reg_data.get('q_therapy') or '—')}\n\n"
        f"📅 Дата заявки: {applied_at}\n"
        f"✅ Дата вступления: {joined_at}"
    )
    card_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Написать в ЛС", url=f"tg://user?id={target_user_id}")]
    ])
    await query.edit_message_text(
        card_text, reply_markup=card_kb, parse_mode="HTML", disable_web_page_preview=True
    )


def _msk_now() -> str:
    """Текущее время МСК в читаемом формате."""
    import pytz
    from datetime import datetime
    tz = pytz.timezone("Europe/Moscow")
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M МСК")
