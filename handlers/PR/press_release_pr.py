#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Пресс-релизы — создание, публикация, планирование, редактирование.

Путь: handlers/PR/press_release_pr.py

Все функции — модульного уровня (без класса).
db, admin_id, target_chat_id передаются явно.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import InputMediaPhoto, InputMediaVideo
from utils.helpers import get_moscow_time


# ═══════════════════════════════════════════════════════════════
# КОНСТАНТЫ И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════

MSG_LIMIT = 4096
CAPTION_LIMIT = 1024
MAX_MEDIA = 5


async def _is_pr_privileged(user_id: int, admin_id: int) -> bool:
    """Владелец или зам владельца."""
    if user_id == admin_id:
        return True
    from database.db_friend import is_deputy
    return await is_deputy(user_id)


async def _send_long_text(bot, chat_id, text, parse_mode='HTML', thread_id=None):
    """Отправляет длинный текст, разбивая на части по MSG_LIMIT (4096)."""
    base_kw = {'chat_id': chat_id, 'parse_mode': parse_mode}
    if thread_id:
        base_kw['message_thread_id'] = thread_id
    while text:
        if len(text) <= MSG_LIMIT:
            await bot.send_message(**base_kw, text=text)
            break
        cut = text.rfind('\n', 0, MSG_LIMIT)
        if cut == -1:
            cut = MSG_LIMIT
        await bot.send_message(**base_kw, text=text[:cut])
        text = text[cut:].lstrip('\n')


def _parse_media(photo_file_id: str) -> list:
    """
    Разбирает поле photo_file_id в список (kind, file_id).
    Форматы: 'photo:fid', 'video:fid', 'photo:f1|video:f2|...', 'bare_fid' (legacy).
    """
    if not photo_file_id:
        return []
    items = []
    for part in photo_file_id.split('|'):
        part = part.strip()
        if not part:
            continue
        if part.startswith('video:'):
            items.append(('video', part[6:]))
        elif part.startswith('photo:'):
            items.append(('photo', part[6:]))
        else:
            items.append(('photo', part))
    return items


def _pack_media(media_list: list) -> str:
    """Собирает список (kind, file_id) обратно в строку для БД."""
    return '|'.join(f"{k}:{f}" for k, f in media_list)


def _media_icon_summary(media_list: list) -> str:
    """Возвращает строку вроде '📷×2 🎥×1' или '📷' для 1 фото."""
    photos = sum(1 for k, _ in media_list if k == 'photo')
    videos = sum(1 for k, _ in media_list if k == 'video')
    parts = []
    if photos:
        parts.append(f"📷×{photos}" if photos > 1 else "📷")
    if videos:
        parts.append(f"🎥×{videos}" if videos > 1 else "🎥")
    return " ".join(parts)


async def _send_pr_media(bot, chat_id, thread_id, media_list: list, text: str):
    """
    Отправляет пресс-релиз с учётом количества медиафайлов:
      0 медиа  → send_message (разбивает по MSG_LIMIT)
      1 медиа  → send_photo/video (caption ≤1024 или медиа+текст отдельно)
      2–5 медиа → send_media_group (caption на первом ≤1024, иначе медиа+текст отдельно)
    """
    kw = {'chat_id': chat_id}
    if thread_id:
        kw['message_thread_id'] = thread_id

    if not media_list:
        await _send_long_text(bot, chat_id, text, thread_id=thread_id)
        return

    if len(media_list) == 1:
        kind, file_id = media_list[0]
        if len(text) <= CAPTION_LIMIT:
            send_kw = {**kw, 'parse_mode': 'HTML', 'caption': text}
            if kind == 'video':
                await bot.send_video(video=file_id, **send_kw)
            else:
                await bot.send_photo(photo=file_id, **send_kw)
        else:
            if kind == 'video':
                await bot.send_video(video=file_id, **kw)
            else:
                await bot.send_photo(photo=file_id, **kw)
            await _send_long_text(bot, chat_id, text, thread_id=thread_id)
        return

    # 2–5 медиа: send_media_group
    group = []
    for i, (kind, file_id) in enumerate(media_list):
        caption = text if i == 0 and len(text) <= CAPTION_LIMIT else None
        parse_mode = 'HTML' if caption else None
        if kind == 'video':
            group.append(InputMediaVideo(media=file_id, caption=caption, parse_mode=parse_mode))
        else:
            group.append(InputMediaPhoto(media=file_id, caption=caption, parse_mode=parse_mode))

    await bot.send_media_group(media=group, **kw)

    if len(text) > CAPTION_LIMIT:
        await _send_long_text(bot, chat_id, text, thread_id=thread_id)


def _resolve_thread_name(db, target_chat_id, thread_id):
    """Получить человекочитаемое имя ветки из БД по thread_id."""
    if not thread_id:
        return "💬 Основной чат"

    topics = db.get_all_topics(target_chat_id)
    for t in topics:
        if t['thread_id'] == thread_id:
            name = (t['thread_name'] if t['thread_name'] else '')
            is_generic = (
                not name or
                name.startswith('Ветка #') or
                name == f'Ветка #{thread_id}'
            )
            if not is_generic:
                return f"🧵 {name}"
            break

    return f"🧵 Ветка #{thread_id}"


def _build_pr_action_keyboard(media_list: list, include_preview=True) -> list:
    """Строит клавиатуру действий пресс-релиза (публикация/медиа/отмена)."""
    n = len(media_list)
    keyboard = []
    if include_preview:
        keyboard.append([InlineKeyboardButton("👁 Полный предпросмотр", callback_data="pr_full_preview")])
    keyboard.append([InlineKeyboardButton("🚀 Опубликовать сейчас", callback_data="pr_publish_now")])
    keyboard.append([InlineKeyboardButton("⏰ Запланировать", callback_data="pr_schedule")])

    if n < MAX_MEDIA:
        label = "📷 Добавить медиа" if n == 0 else f"📷 Добавить медиа ({n}/{MAX_MEDIA})"
        keyboard.append([InlineKeyboardButton(label, callback_data="pr_add_photo")])
    if n > 0:
        keyboard.append([InlineKeyboardButton("🗑 Очистить медиа", callback_data="pr_remove_photo")])

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="pr_cancel")])
    return keyboard


# ═══════════════════════════════════════════════════════════════
# СОЗДАНИЕ ПРЕСС-РЕЛИЗА
# ═══════════════════════════════════════════════════════════════

async def start_press_release(query, user, context, db, admin_id):
    """Start press release creation (owner only)"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return

    context.user_data['awaiting_press_release'] = True
    context.user_data.pop('pr_data', None)

    await query.edit_message_text(
        "📰 СОЗДАНИЕ ПРЕСС-РЕЛИЗА\n\n"
        "Отправьте текст пресс-релиза.\n"
        "Можно сразу с фото или видео — или добавить до 5 медиафайлов позже.\n\n"
        "✍️ После отправки текста вы сможете:\n"
        "• Добавить до 5 фото/видео\n"
        "• Выбрать куда публиковать (чат / ветка)\n"
        "• Опубликовать сразу или запланировать\n\n"
        "Для отмены: /cancel",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Запланированные", callback_data="pr_scheduled_list")],
            [InlineKeyboardButton("❌ Отмена", callback_data="back_to_menu")],
            [InlineKeyboardButton("🔙 Назад в настройки", callback_data="back_to_menu")]
        ])
    )


async def handle_pr_target_selection(query, data, user, context, db, admin_id, target_chat_id):
    """Handle press release target (chat/thread) selection"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    pr_data = context.user_data.get('pr_data', {})
    if not pr_data:
        await query.edit_message_text("❌ Данные пресс-релиза потеряны. Начните заново.")
        return

    if data == "pr_target_main":
        pr_data['thread_id'] = None
        thread_name = "💬 Основной чат"
    elif data == "pr_target_manual":
        context.user_data['awaiting_thread_id'] = True
        await query.edit_message_text(
            "✏️ ВВЕДИТЕ ID ВЕТКИ\n\n"
            "Пришлите числовой ID темы/ветки чата.\n"
            "Например: 12345\n\n"
            "Для отмены: /cancel"
        )
        return
    elif data.startswith("pr_target_thread_"):
        try:
            thread_id = int(data.replace("pr_target_thread_", ""))
            pr_data['thread_id'] = thread_id
            thread_name = _resolve_thread_name(db, target_chat_id, thread_id)
        except ValueError:
            await query.answer("Ошибка: неверный ID ветки", show_alert=True)
            return
    else:
        await query.answer("Неизвестный выбор", show_alert=True)
        return

    context.user_data['pr_data'] = pr_data

    media_list = _parse_media(pr_data.get('photo_file_id'))
    n = len(media_list)
    summary = _media_icon_summary(media_list)
    media_line = f"{summary}\n" if summary else ""

    preview = pr_data.get('text', '')[:150]
    if len(pr_data.get('text', '')) > 150:
        preview += "..."

    preview_lines = preview.split('\n', 1)
    if len(preview_lines) > 1:
        preview_formatted = f"<b>{preview_lines[0]}</b>\n{preview_lines[1]}"
    else:
        preview_formatted = f"<b>{preview_lines[0]}</b>"

    keyboard = _build_pr_action_keyboard(media_list)

    await query.edit_message_text(
        f"👁 Предпросмотр:\n\n"
        f"{preview_formatted}\n\n"
        f"<i>© Сообщество Pulse 2026</i>\n\n"
        f"{media_line}"
        f"🎯 Куда: {thread_name}\n\n"
        f"⏰ Когда опубликовать?",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ═══════════════════════════════════════════════════════════════
# ДОБАВИТЬ / УБРАТЬ МЕДИА (при создании)
# ═══════════════════════════════════════════════════════════════

async def handle_pr_add_photo(query, user, context, db, admin_id):
    """Кнопка '📷 Добавить медиа' — во время создания пресс-релиза"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    pr_data = context.user_data.get('pr_data', {})
    if not pr_data:
        await query.edit_message_text("❌ Данные пресс-релиза потеряны. Начните заново.")
        return

    media_list = _parse_media(pr_data.get('photo_file_id'))
    n = len(media_list)

    if n >= MAX_MEDIA:
        await query.answer(f"⚠️ Уже {MAX_MEDIA}/{MAX_MEDIA} медиафайлов. Сначала очистите.", show_alert=True)
        return

    context.user_data['awaiting_pr_photo'] = True

    summary = _media_icon_summary(media_list)
    current_info = f"\n📎 Уже прикреплено: {summary} ({n}/{MAX_MEDIA})\n" if n > 0 else ""

    await query.edit_message_text(
        f"📷 ДОБАВИТЬ МЕДИА\n"
        f"{current_info}\n"
        f"Отправьте фото или видео (до {MAX_MEDIA} файлов всего).\n\n"
        "Для отмены: /cancel",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="pr_cancel")]
        ])
    )


async def handle_pr_remove_photo(query, user, context, db, admin_id):
    """Кнопка '🗑 Очистить медиа' — убрать все прикреплённые медиафайлы"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    pr_data = context.user_data.get('pr_data', {})
    if not pr_data:
        await query.edit_message_text("❌ Данные пресс-релиза потеряны. Начните заново.")
        return

    pr_data['photo_file_id'] = None
    context.user_data['pr_data'] = pr_data

    await query.answer("🗑 Все медиа удалены!", show_alert=False)

    from handlers.messages.admin_logic import build_topic_keyboard
    keyboard = await build_topic_keyboard(context, db, query.message.chat_id)

    preview = pr_data.get('text', '')[:200]
    if len(pr_data.get('text', '')) > 200:
        preview += "..."

    preview_msg = f"📰 ПРЕДПРОСМОТР ПРЕСС-РЕЛИЗА\n\n{preview}\n"
    preview_msg += "\n🎯 Выберите куда опубликовать:"

    await query.edit_message_text(preview_msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_pr_media_done(query, user, context, db, admin_id, target_chat_id):
    """Кнопка '✅ Готово' — завершить добавление медиа и вернуться к выбору публикации"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    context.user_data.pop('awaiting_pr_photo', None)
    pr_data = context.user_data.get('pr_data', {})
    media_list = _parse_media(pr_data.get('photo_file_id'))
    n = len(media_list)
    summary = _media_icon_summary(media_list)

    thread_id = pr_data.get('thread_id')

    if thread_id is not None:
        thread_name = _resolve_thread_name(db, target_chat_id, thread_id)
        preview = pr_data.get('text', '')[:150]
        if len(pr_data.get('text', '')) > 150:
            preview += '...'

        media_line = f"{summary}\n" if summary else ""
        preview_lines = preview.split('\n', 1)
        if len(preview_lines) > 1:
            preview_formatted = f"<b>{preview_lines[0]}</b>\n{preview_lines[1]}"
        else:
            preview_formatted = f"<b>{preview_lines[0]}</b>"

        keyboard = _build_pr_action_keyboard(media_list)

        await query.edit_message_text(
            f"👁 Предпросмотр:\n\n"
            f"{preview_formatted}\n\n"
            f"<i>© Сообщество Pulse 2026</i>\n\n"
            f"{media_line}"
            f"🎯 Куда: {thread_name}\n\n"
            f"⏰ Когда опубликовать?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        from handlers.messages.admin_logic import build_topic_keyboard
        keyboard = await build_topic_keyboard(context, db, target_chat_id)
        text_preview = pr_data.get('text', '')[:200]
        if len(pr_data.get('text', '')) > 200:
            text_preview += '...'

        msg = f"📰 ПРЕДПРОСМОТР ПРЕСС-РЕЛИЗА\n\n{text_preview}\n"
        if summary:
            msg += f"\n{summary} прикреплено\n"
        msg += "\n🎯 Выберите куда опубликовать:"

        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ═══════════════════════════════════════════════════════════════
# ПОЛНЫЙ ПРЕДПРОСМОТР (медиа + весь текст)
# ═══════════════════════════════════════════════════════════════

async def handle_pr_full_preview(query, user, context, db, admin_id):
    """Отправляет полный предпросмотр: медиа + весь текст, как будет в чате."""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    pr_data = context.user_data.get('pr_data', {})
    if not pr_data:
        await query.answer("❌ Данные потеряны. Начните заново.", show_alert=True)
        return

    text = pr_data.get('text', '')
    media_list = _parse_media(pr_data.get('photo_file_id'))
    chat_id = query.message.chat.id

    lines = text.split('\n', 1)
    if len(lines) > 1:
        formatted_text = f"<b>{lines[0]}</b>\n{lines[1]}"
    else:
        formatted_text = f"<b>{lines[0]}</b>"

    press_release = (
        f"👁 <b>ПОЛНЫЙ ПРЕДПРОСМОТР</b>\n"
        f"{'━' * 20}\n\n"
        f"{formatted_text}\n\n"
        f"<i>© Сообщество Pulse 2026</i>"
    )

    try:
        await _send_pr_media(context.bot, chat_id, None, media_list, press_release)
        await query.answer("👆 Полный предпросмотр отправлен выше")
    except Exception as e:
        await query.answer(f"❌ Ошибка предпросмотра: {e}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
# ПУБЛИКАЦИЯ
# ═══════════════════════════════════════════════════════════════

async def handle_pr_publish_now(query, user, context, db, admin_id, target_chat_id):
    """Publish press release immediately"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    pr_data = context.user_data.get('pr_data', {})
    if not pr_data:
        await query.edit_message_text("❌ Данные пресс-релиза потеряны. Начните заново.")
        return

    text = pr_data.get('text', '')
    media_list = _parse_media(pr_data.get('photo_file_id'))
    thread_id = pr_data.get('thread_id')

    lines = text.split('\n', 1)
    if len(lines) > 1:
        formatted_text = f"<b>{lines[0]}</b>\n{lines[1]}"
    else:
        formatted_text = f"<b>{lines[0]}</b>"

    press_release = (
        f"{formatted_text}\n\n"
        f"<i>© Сообщество Pulse 2026</i>"
    )

    try:
        await _send_pr_media(context.bot, target_chat_id, thread_id, media_list, press_release)
        context.user_data.pop('pr_data', None)

        await query.edit_message_text(
            "✅ Пресс-релиз опубликован!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
            ]])
        )
    except Exception as e:
        err_lower = str(e).lower()
        if 'thread not found' in err_lower or 'topic_closed' in err_lower or 'topic closed' in err_lower or 'forum topic' in err_lower:
            try:
                await _send_pr_media(context.bot, target_chat_id, None, media_list, press_release)
                context.user_data.pop('pr_data', None)
                await query.edit_message_text(
                    "✅ Пресс-релиз опубликован! (тред не найден — отправлено в основной чат)",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
                    ]])
                )
                return
            except Exception as e2:
                e = e2
        try:
            await query.edit_message_text(
                f"❌ Ошибка при публикации: {e}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔁 Попробовать снова", callback_data="pr_publish_now"),
                    InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
                ]])
            )
        except Exception:
            pass


async def handle_pr_schedule(query, user, context, db, admin_id):
    """Start scheduling flow - ask for date/time"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    pr_data = context.user_data.get('pr_data', {})
    if not pr_data:
        await query.edit_message_text("❌ Данные пресс-релиза потеряны. Начните заново.")
        return

    context.user_data['awaiting_schedule_time'] = True

    now = get_moscow_time()

    await query.edit_message_text(
        "⏰ ОТЛОЖЕННАЯ ПУБЛИКАЦИЯ\n\n"
        f"🕐 Текущее время (МСК): {now.strftime('%d.%m.%Y %H:%M')}\n\n"
        "Отправьте дату и время публикации.\n"
        "💡 *Вы можете использовать любые разделители* (точки, запятые, пробелы, двоеточия).\n\n"
        "Например:\n"
        "📅 `25.03.2026 14:30`\n"
        "📅 `25,03,26 14,30`\n"
        "📅 `25 03 14 30` *(текущий год подставится сам)*\n\n"
        "Для отмены: /cancel",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="pr_cancel")
        ]])
    )


# ═══════════════════════════════════════════════════════════════
# СПИСОК ЗАПЛАНИРОВАННЫХ + УДАЛЕНИЕ
# ═══════════════════════════════════════════════════════════════

async def show_scheduled_posts(query, user, context, db, admin_id, target_chat_id=None):
    """Show list of scheduled posts with real thread names"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    posts = db.get_scheduled_posts_list('pending')

    if not posts:
        await query.edit_message_text(
            "📋 ЗАПЛАНИРОВАННЫЕ ПОСТЫ\n\n"
            "Нет запланированных постов.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📰 Создать пресс-релиз", callback_data="press_release_start")],
                [InlineKeyboardButton("🔙 В настройки", callback_data="back_to_menu")]
            ])
        )
        return

    if not target_chat_id and posts:
        target_chat_id = posts[0]['target_chat_id']

    message = "📋 ЗАПЛАНИРОВАННЫЕ ПОСТЫ\n\n"
    keyboard = []

    for post in posts:
        text_preview = (post['text'] or '')[:50]
        if len(post['text'] or '') > 50:
            text_preview += "..."
        text_preview = text_preview.replace("━", "").replace("📰", "").replace("<b>", "").replace("</b>", "").strip()

        publish_at = post['publish_at']
        chat_id_for_topic = (post['target_chat_id'] or target_chat_id)
        thread_name = _resolve_thread_name(db, chat_id_for_topic, post['thread_id'])

        media_list = _parse_media(post['photo_file_id'])
        summary = _media_icon_summary(media_list)
        photo_icon = f" {summary}" if summary else ""

        message += f"🆔 #{post['id']} | 📅 {publish_at}\n"
        message += f"   🎯 {thread_name}{photo_icon}\n"
        message += f"   📝 {text_preview}\n\n"

        keyboard.append([
            InlineKeyboardButton(f"✏️ Ред. #{post['id']}", callback_data=f"pr_edit_{post['id']}"),
            InlineKeyboardButton(f"🗑 Удал. #{post['id']}", callback_data=f"pr_delete_{post['id']}")
        ])

    keyboard.append([InlineKeyboardButton("📰 Создать новый", callback_data="press_release_start")])
    keyboard.append([InlineKeyboardButton("🔙 В настройки", callback_data="back_to_menu")])

    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_pr_delete(query, data, user, context, db, admin_id, target_chat_id=None):
    """Delete a scheduled post"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_delete_", ""))
    deleted = db.delete_scheduled_post(post_id)

    if deleted:
        await query.answer(f"✅ Пост #{post_id} удалён!", show_alert=True)
    else:
        await query.answer(f"❌ Пост #{post_id} не найден или уже опубликован.", show_alert=True)

    await show_scheduled_posts(query, user, context, db, admin_id, target_chat_id)


# ═══════════════════════════════════════════════════════════════
# РЕДАКТИРОВАНИЕ ЗАПЛАНИРОВАННЫХ ПОСТОВ
# ═══════════════════════════════════════════════════════════════

async def handle_pr_edit(query, data, user, context, db, admin_id, target_chat_id=None):
    """Show edit menu for a scheduled post"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_", ""))
    post = db.get_scheduled_post(post_id)

    if not post or post['status'] != 'pending':
        await query.answer("❌ Пост не найден или уже опубликован.", show_alert=True)
        return

    text_preview = (post['text'] or '')[:200]
    if len(post['text'] or '') > 200:
        text_preview += "..."
    for tag in ['<b>', '</b>', '<i>', '</i>']:
        text_preview = text_preview.replace(tag, '')

    chat_id_for_topic = (post['target_chat_id'] or target_chat_id)
    thread_name = _resolve_thread_name(db, chat_id_for_topic, post['thread_id'])

    media_list = _parse_media(post['photo_file_id'])
    n = len(media_list)
    if n > 0:
        summary = _media_icon_summary(media_list)
        photo_status = f"📎 Прикреплено: {summary} ({n} файл(ов))"
    else:
        photo_status = "📄 Без медиа"

    message = (
        f"✏️ РЕДАКТИРОВАНИЕ ПОСТА #{post_id}\n\n"
        f"📝 Текст:\n{text_preview}\n\n"
        f"📅 Публикация: {post['publish_at']}\n"
        f"🎯 Куда: {thread_name}\n"
        f"{photo_status}\n\n"
        f"Что изменить?"
    )

    keyboard = [
        [InlineKeyboardButton("📝 Изменить текст", callback_data=f"pr_edit_text_{post_id}")],
        [InlineKeyboardButton("📅 Изменить время", callback_data=f"pr_edit_time_{post_id}")],
        [InlineKeyboardButton("🎯 Изменить ветку", callback_data=f"pr_edit_target_{post_id}")],
        [InlineKeyboardButton("🚀 Опубликовать сейчас", callback_data=f"pr_edit_publishnow_{post_id}")]
    ]

    if n > 0:
        keyboard.append([
            InlineKeyboardButton("🔄 Заменить медиа", callback_data=f"pr_edit_photo_{post_id}"),
            InlineKeyboardButton("🗑 Очистить медиа", callback_data=f"pr_edit_remove_photo_{post_id}"),
        ])
    else:
        keyboard.append([InlineKeyboardButton("📷 Добавить медиа", callback_data=f"pr_edit_photo_{post_id}")])

    keyboard.append([InlineKeyboardButton("🔙 К списку", callback_data="pr_scheduled_list")])

    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_pr_edit_text(query, data, user, context, db, admin_id):
    """Start editing text of a scheduled post"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_text_", ""))
    post = db.get_scheduled_post(post_id)

    if not post or post['status'] != 'pending':
        await query.answer("❌ Пост не найден.", show_alert=True)
        return

    context.user_data['awaiting_edit_text'] = post_id

    await query.edit_message_text(
        f"📝 РЕДАКТИРОВАНИЕ ТЕКСТА (пост #{post_id})\n\n"
        "Отправьте новый текст пресс-релиза.\n\n"
        "Для отмены: /cancel",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data=f"pr_edit_{post_id}")]
        ])
    )


async def handle_pr_edit_photo(query, data, user, context, db, admin_id):
    """Start adding/replacing media of a scheduled post (accumulative mode)"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_photo_", ""))
    post = db.get_scheduled_post(post_id)

    if not post or post['status'] != 'pending':
        await query.answer("❌ Пост не найден.", show_alert=True)
        return

    context.user_data['awaiting_edit_photo'] = post_id
    context.user_data['edit_photo_buffer'] = []

    await query.edit_message_text(
        f"📷 ДОБАВИТЬ/ЗАМЕНИТЬ МЕДИА (пост #{post_id})\n\n"
        f"Отправьте до {MAX_MEDIA} фото/видео.\n"
        "Они ЗАМЕНЯТ текущее медиа поста.\n"
        "Нажмите ✅ Готово когда закончите.\n\n"
        "Для отмены: /cancel",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data=f"pr_edit_{post_id}")]
        ])
    )


async def handle_pr_edit_remove_photo(query, data, user, context, db, admin_id, target_chat_id=None):
    """Remove all media from a scheduled post"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_remove_photo_", ""))
    updated = db.update_scheduled_post(post_id, photo_file_id=None)

    if updated:
        await query.answer("🗑 Медиа удалено!", show_alert=True)
    else:
        await query.answer("❌ Не удалось обновить пост.", show_alert=True)

    await handle_pr_edit(query, f"pr_edit_{post_id}", user, context, db, admin_id, target_chat_id)


async def handle_pr_edit_media_done(query, data, user, context, db, admin_id, target_chat_id=None):
    """Кнопка '✅ Готово' при редактировании медиа запланированного поста"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_media_done_", ""))

    buffer = context.user_data.pop('edit_photo_buffer', [])
    context.user_data.pop('awaiting_edit_photo', None)

    if buffer:
        photo_file_id = _pack_media(buffer)
        updated = db.update_scheduled_post(post_id, photo_file_id=photo_file_id)
        n = len(buffer)
        summary = _media_icon_summary(buffer)
        if updated:
            await query.answer(f"✅ Медиа обновлено: {summary} ({n} файл(ов))", show_alert=True)
        else:
            await query.answer("❌ Не удалось обновить.", show_alert=True)
    else:
        await query.answer("⚠️ Медиа не добавлено — пост не изменён.", show_alert=True)

    await handle_pr_edit(query, f"pr_edit_{post_id}", user, context, db, admin_id, target_chat_id)


async def handle_pr_edit_time(query, data, user, context, db, admin_id):
    """Start editing publish time of a scheduled post"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_time_", ""))
    post = db.get_scheduled_post(post_id)

    if not post or post['status'] != 'pending':
        await query.answer("❌ Пост не найден.", show_alert=True)
        return

    context.user_data['awaiting_edit_time'] = post_id

    now = get_moscow_time()

    await query.edit_message_text(
        f"📅 ИЗМЕНИТЬ ВРЕМЯ (пост #{post_id})\n\n"
        f"Текущее время: {post['publish_at']}\n"
        f"🕐 Сейчас (МСК): {now.strftime('%d.%m.%Y %H:%M')}\n\n"
        "Отправьте новую дату и время.\n"
        "💡 *Разделители могут быть любыми* (точки, запятые, пробелы).\n\n"
        "Например:\n"
        "📅 `25.03.2026 14:30`\n"
        "📅 `25,03 14,30`\n\n"
        "Для отмены: /cancel",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data=f"pr_edit_{post_id}")]
        ])
    )


async def handle_pr_edit_target(query, data, user, context, db, admin_id, target_chat_id):
    """Start changing target thread of a scheduled post"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_target_", ""))
    post = db.get_scheduled_post(post_id)

    if not post or post['status'] != 'pending':
        await query.answer("❌ Пост не найден.", show_alert=True)
        return

    context.user_data['editing_post_target'] = post_id

    from handlers.messages.admin_logic import build_topic_keyboard
    raw_keyboard = await build_topic_keyboard(context, db, target_chat_id)

    keyboard = []
    for row in raw_keyboard:
        new_row = []
        for btn in row:
            cb = btn.callback_data or ''
            if cb.startswith("pr_target_"):
                new_cb = cb.replace("pr_target_", "pr_retarget_")
                new_row.append(InlineKeyboardButton(btn.text, callback_data=new_cb))
            elif cb == "pr_cancel":
                new_row.append(InlineKeyboardButton("🔙 Назад", callback_data=f"pr_edit_{post_id}"))
            elif cb == "pr_refresh_topics":
                new_row.append(btn)
            else:
                new_row.append(btn)
        keyboard.append(new_row)

    current_thread = _resolve_thread_name(db, target_chat_id, post['thread_id'])

    await query.edit_message_text(
        f"🎯 ИЗМЕНИТЬ ВЕТКУ (пост #{post_id})\n\n"
        f"Текущая: {current_thread}\n\n"
        f"Выберите новую ветку:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_pr_edit_publish_now(query, data, user, context, db, admin_id, target_chat_id):
    """Publish a scheduled post immediately from the edit menu"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_publishnow_", ""))
    post = db.get_scheduled_post(post_id)

    if not post or post['status'] != 'pending':
        await query.answer("❌ Пост не найден или уже опубликован.", show_alert=True)
        return

    text = post['text'] or ''
    media_list = _parse_media(post['photo_file_id'])
    chat_id_for_topic = post['target_chat_id'] or target_chat_id
    thread_id = post['thread_id']

    lines = text.split('\n', 1)
    if len(lines) > 1:
        formatted_text = f"<b>{lines[0]}</b>\n{lines[1]}"
    else:
        formatted_text = f"<b>{lines[0]}</b>"

    press_release = (
        f"{formatted_text}\n\n"
        f"<i>© Сообщество Pulse 2026</i>"
    )

    try:
        await _send_pr_media(context.bot, chat_id_for_topic, thread_id, media_list, press_release)
        db.delete_scheduled_post(post_id)
        await query.answer("✅ Пресс-релиз успешно опубликован!", show_alert=True)
        await show_scheduled_posts(query, user, context, db, admin_id, target_chat_id)

    except Exception as e:
        import logging
        err_lower = str(e).lower()
        if 'thread not found' in err_lower or 'topic_closed' in err_lower or 'topic closed' in err_lower or 'forum topic' in err_lower:
            try:
                await _send_pr_media(context.bot, chat_id_for_topic, None, media_list, press_release)
                db.delete_scheduled_post(post_id)
                await query.answer("✅ Опубликовано в основной чат (тред закрыт/не найден)", show_alert=True)
                await show_scheduled_posts(query, user, context, db, admin_id, target_chat_id)
                return
            except Exception as e2:
                e = e2
        logging.error(f"Error publishing scheduled post now: {e}")
        await query.answer(f"❌ Ошибка при публикации: {e}", show_alert=True)


async def handle_pr_retarget(query, data, user, context, db, admin_id, target_chat_id):
    """Handle new target selection for an existing scheduled post"""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = context.user_data.get('editing_post_target')
    if not post_id:
        await query.answer("❌ Ошибка: не найден ID поста.", show_alert=True)
        return

    if data == "pr_retarget_main":
        new_thread_id = None
    elif data.startswith("pr_retarget_thread_"):
        try:
            new_thread_id = int(data.replace("pr_retarget_thread_", ""))
        except ValueError:
            await query.answer("Ошибка: неверный ID ветки", show_alert=True)
            return
    elif data == "pr_retarget_manual":
        context.user_data['awaiting_edit_target_manual'] = post_id
        await query.edit_message_text(
            f"✏️ ВВЕДИТЕ ID ВЕТКИ (для поста #{post_id})\n\n"
            "Пришлите числовой ID темы/ветки.\n\n"
            "Для отмены: /cancel"
        )
        return
    else:
        await query.answer("Неизвестный выбор", show_alert=True)
        return

    updated = db.update_scheduled_post(post_id, thread_id=new_thread_id)
    context.user_data.pop('editing_post_target', None)

    thread_name = _resolve_thread_name(db, target_chat_id, new_thread_id)

    if updated:
        await query.answer(f"✅ Ветка изменена → {thread_name}", show_alert=True)
    else:
        await query.answer("❌ Не удалось обновить.", show_alert=True)

    await handle_pr_edit(query, f"pr_edit_{post_id}", user, context, db, admin_id, target_chat_id)


# ═══════════════════════════════════════════════════════════════
# ОБНОВИТЬ СПИСОК ВЕТОК
# ═══════════════════════════════════════════════════════════════

async def handle_pr_refresh_topics(query, user, context, db, admin_id, target_chat_id):
    """Refresh topic list: purge generic names, probe alive threads, rebuild keyboard."""
    if not await _is_pr_privileged(user.id, admin_id):
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    deleted = db.purge_unnamed_topics(target_chat_id)

    topics = db.get_all_topics(target_chat_id)
    alive_count = 0
    dead_ids = []

    for topic in topics:
        if topic['is_main_thread'] or not topic['thread_id']:
            continue
        try:
            test_msg = await context.bot.send_message(
                chat_id=target_chat_id,
                message_thread_id=topic['thread_id'],
                text="🔍"
            )
            await context.bot.delete_message(
                chat_id=target_chat_id,
                message_id=test_msg.message_id
            )
            alive_count += 1
        except Exception:
            dead_ids.append(topic['thread_id'])

    for tid in dead_ids:
        db.cursor.execute(
            'DELETE FROM topics WHERE chat_id = ? AND thread_id = ?',
            (target_chat_id, tid)
        )
    db.conn.commit()

    from handlers.messages.admin_logic import build_topic_keyboard
    keyboard = await build_topic_keyboard(context, db, target_chat_id)

    fresh_topics = db.get_all_topics(target_chat_id)
    named = sum(1 for t in fresh_topics
                if t['thread_name']
                and not t['thread_name'].startswith('Ветка #')
                and not t['thread_name'].startswith('Ветка ')
                and not t['is_main_thread'])
    total = sum(1 for t in fresh_topics
                if not t['is_main_thread'] and t['thread_id'])

    msg = (
        f"🔄 СПИСОК ОБНОВЛЁН\n\n"
        f"🗑 Удалено неактивных: {deleted + len(dead_ids)}\n"
        f"✅ Активных веток: {alive_count}\n"
        f"🏷️ С именами: {named} из {total}\n\n"
    )

    if named < total:
        msg += (
            "💡 Чтобы бот узнал имена веток:\n"
            "Переименуйте ветку в Telegram (можно сразу обратно) — "
            "бот запомнит новое имя автоматически.\n\n"
        )

    pr_data = context.user_data.get('pr_data')
    if pr_data:
        msg += "🎯 Выберите куда опубликовать:"

    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ═══════════════════════════════════════════════════════════════
# ОТМЕНА
# ═══════════════════════════════════════════════════════════════

async def handle_pr_cancel(query, user, context, db, admin_id):
    """Cancel press release creation"""
    context.user_data.pop('awaiting_press_release', None)
    context.user_data.pop('awaiting_schedule_time', None)
    context.user_data.pop('awaiting_pr_photo', None)
    context.user_data.pop('awaiting_edit_text', None)
    context.user_data.pop('awaiting_edit_photo', None)
    context.user_data.pop('awaiting_edit_time', None)
    context.user_data.pop('awaiting_edit_target_manual', None)
    context.user_data.pop('editing_post_target', None)
    context.user_data.pop('edit_photo_buffer', None)
    context.user_data.pop('pr_data', None)

    await query.edit_message_text(
        "❌ Создание пресс-релиза отменено.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
        ]])
    )
