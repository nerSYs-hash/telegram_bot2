#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Пресс-релизы — создание, публикация, планирование, редактирование.

Путь: handlers/PR/press_release_pr.py

Все функции — модульного уровня (без класса).
db, admin_id, target_chat_id передаются явно.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import get_moscow_time


# ═══════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════

MSG_LIMIT = 4096


async def _send_long_text(bot, chat_id, text, parse_mode='HTML', thread_id=None):
    """Отправляет длинный текст, разбивая на части по MSG_LIMIT (4096)."""
    base_kw = {'chat_id': chat_id, 'parse_mode': parse_mode}
    if thread_id:
        base_kw['message_thread_id'] = thread_id
    # Разбиваем по \n чтобы не резать посреди строки
    while text:
        if len(text) <= MSG_LIMIT:
            await bot.send_message(**base_kw, text=text)
            break
        # Ищем последний перенос строки в пределах лимита
        cut = text.rfind('\n', 0, MSG_LIMIT)
        if cut == -1:
            cut = MSG_LIMIT
        await bot.send_message(**base_kw, text=text[:cut])
        text = text[cut:].lstrip('\n')

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


# ═══════════════════════════════════════════════════════════════
# СОЗДАНИЕ ПРЕСС-РЕЛИЗА
# ═══════════════════════════════════════════════════════════════

async def start_press_release(query, user, context, db, admin_id):
    """Start press release creation (owner only)"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа к этой функции.", show_alert=True)
        return

    context.user_data['awaiting_press_release'] = True
    context.user_data.pop('pr_data', None)

    await query.edit_message_text(
        "📰 СОЗДАНИЕ ПРЕСС-РЕЛИЗА\n\n"
        "Отправьте текст пресс-релиза.\n"
        "Можно сразу с фото, видео, картинкой — или добавить его позже кнопкой.\n\n"
        "✍️ После отправки текста вы сможете:\n"
        "• Добавить/заменить фото\n"
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
    if user.id != admin_id:
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

    # Предпросмотр + выбор времени
    preview = pr_data.get('text', '')[:150]
    if len(pr_data.get('text', '')) > 150:
        preview += "..."

    photo_line = ""
    saved_file_id = pr_data.get('photo_file_id')
    if saved_file_id:
        if str(saved_file_id).startswith('video:'):
            photo_line = "🎥 С видео\n"
        else:
            photo_line = "📷 С фото\n"

    keyboard = [
        [InlineKeyboardButton("� Полный предпросмотр", callback_data="pr_full_preview")],
        [InlineKeyboardButton("�🚀 Опубликовать сейчас", callback_data="pr_publish_now")],
        [InlineKeyboardButton("⏰ Запланировать", callback_data="pr_schedule")],
    ]
    if pr_data.get('photo_file_id'):
        keyboard.append([InlineKeyboardButton("🗑 Убрать фото", callback_data="pr_remove_photo")])
    else:
        keyboard.append([InlineKeyboardButton("📷 Добавить фото", callback_data="pr_add_photo")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="pr_cancel")])

    preview_lines = preview.split('\n', 1)
    if len(preview_lines) > 1:
        preview_formatted = f"<b>{preview_lines[0]}</b>\n{preview_lines[1]}"
    else:
        preview_formatted = f"<b>{preview_lines[0]}</b>"

    await query.edit_message_text(
        f"👁 Предпросмотр:\n\n"
        f"{preview_formatted}\n\n"
        f"<i>© Pulse Chat Community 2026</i>\n\n"
        f"{photo_line}"
        f"🎯 Куда: {thread_name}\n\n"
        f"⏰ Когда опубликовать?",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ═══════════════════════════════════════════════════════════════
# ДОБАВИТЬ / УБРАТЬ ФОТО (при создании)
# ═══════════════════════════════════════════════════════════════

async def handle_pr_add_photo(query, user, context, db, admin_id):
    """Кнопка '📷 Добавить фото' — во время создания пресс-релиза"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    pr_data = context.user_data.get('pr_data', {})
    if not pr_data:
        await query.edit_message_text("❌ Данные пресс-релиза потеряны. Начните заново.")
        return

    context.user_data['awaiting_pr_photo'] = True

    await query.edit_message_text(
        "📷 ДОБАВИТЬ ФОТО\n\n"
        "Отправьте фото для пресс-релиза.\n\n"
        "Для отмены: /cancel",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="pr_cancel")]
        ])
    )


async def handle_pr_remove_photo(query, user, context, db, admin_id):
    """Кнопка '🗑 Убрать фото' — убрать прикреплённое фото"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    pr_data = context.user_data.get('pr_data', {})
    if not pr_data:
        await query.edit_message_text("❌ Данные пресс-релиза потеряны. Начните заново.")
        return

    pr_data['photo_file_id'] = None
    context.user_data['pr_data'] = pr_data

    await query.answer("🗑 Фото убрано!", show_alert=False)

    from handlers.messages.admin_logic import build_topic_keyboard
    keyboard = await build_topic_keyboard(context, db, query.message.chat_id)

    preview = pr_data.get('text', '')[:200]
    if len(pr_data.get('text', '')) > 200:
        preview += "..."

    preview_msg = f"📰 ПРЕДПРОСМОТР ПРЕСС-РЕЛИЗА\n\n{preview}\n"
    preview_msg += "\n🎯 Выберите куда опубликовать:"

    await query.edit_message_text(preview_msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ═══════════════════════════════════════════════════════════════
# ПОЛНЫЙ ПРЕДПРОСМОТР (медиа + весь текст)
# ═══════════════════════════════════════════════════════════════

async def handle_pr_full_preview(query, user, context, db, admin_id):
    """Отправляет полный предпросмотр: медиа + весь текст, как будет в чате."""
    if user.id != admin_id:
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    pr_data = context.user_data.get('pr_data', {})
    if not pr_data:
        await query.answer("❌ Данные потеряны. Начните заново.", show_alert=True)
        return

    text = pr_data.get('text', '')
    photo_file_id = pr_data.get('photo_file_id')
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
        f"<i>© Сообщество Pulse</i>"
    )

    try:
        if photo_file_id:
            is_video = False
            raw_file_id = photo_file_id

            if str(photo_file_id).startswith('video:'):
                is_video = True
                raw_file_id = photo_file_id.split(':', 1)[1]
            elif str(photo_file_id).startswith('photo:'):
                raw_file_id = photo_file_id.split(':', 1)[1]

            if len(press_release) > 1024:
                if is_video:
                    await context.bot.send_video(chat_id=chat_id, video=raw_file_id)
                else:
                    await context.bot.send_photo(chat_id=chat_id, photo=raw_file_id)
                await _send_long_text(context.bot, chat_id, press_release)
            else:
                if is_video:
                    await context.bot.send_video(
                        chat_id=chat_id, video=raw_file_id,
                        caption=press_release, parse_mode='HTML',
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=chat_id, photo=raw_file_id,
                        caption=press_release, parse_mode='HTML',
                    )
        else:
            await _send_long_text(context.bot, chat_id, press_release)

        await query.answer("👆 Полный предпросмотр отправлен выше")
    except Exception as e:
        await query.answer(f"❌ Ошибка предпросмотра: {e}", show_alert=True)


# ═══════════════════════════════════════════════════════════════
# ПУБЛИКАЦИЯ
# ═══════════════════════════════════════════════════════════════

async def handle_pr_publish_now(query, user, context, db, admin_id, target_chat_id):
    """Publish press release immediately"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    pr_data = context.user_data.get('pr_data', {})
    if not pr_data:
        await query.edit_message_text("❌ Данные пресс-релиза потеряны. Начните заново.")
        return

    text = pr_data.get('text', '')
    photo_file_id = pr_data.get('photo_file_id')
    thread_id = pr_data.get('thread_id')

    lines = text.split('\n', 1)
    if len(lines) > 1:
        formatted_text = f"<b>{lines[0]}</b>\n{lines[1]}"
    else:
        formatted_text = f"<b>{lines[0]}</b>"

    press_release = (
        f"{formatted_text}\n\n"
        f"<i>© Сообщество Pulse</i>"
    )

    try:
        kwargs = {
            'chat_id': target_chat_id,
            'parse_mode': 'HTML',
        }
        if thread_id:
            kwargs['message_thread_id'] = thread_id

        if photo_file_id:
            is_video = False
            raw_file_id = photo_file_id

            if str(photo_file_id).startswith('video:'):
                is_video = True
                raw_file_id = photo_file_id.split(':', 1)[1]
            elif str(photo_file_id).startswith('photo:'):
                raw_file_id = photo_file_id.split(':', 1)[1]

            if len(press_release) > 1024:
                # Caption > 1024: медиа без подписи + текст отдельно
                if is_video:
                    kwargs['video'] = raw_file_id
                    await context.bot.send_video(**kwargs)
                else:
                    kwargs['photo'] = raw_file_id
                    await context.bot.send_photo(**kwargs)
                await _send_long_text(context.bot, target_chat_id, press_release, thread_id=thread_id)
            else:
                if is_video:
                    kwargs['video'] = raw_file_id
                    kwargs['caption'] = press_release
                    await context.bot.send_video(**kwargs)
                else:
                    kwargs['photo'] = raw_file_id
                    kwargs['caption'] = press_release
                    await context.bot.send_photo(**kwargs)
        else:
            await _send_long_text(context.bot, target_chat_id, press_release, thread_id=thread_id)

        context.user_data.pop('pr_data', None)

        await query.edit_message_text(
            "✅ Пресс-релиз опубликован!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
            ]])
        )
    except Exception as e:
        # Если тред не найден — пробуем без треда
        err_lower = str(e).lower()
        if 'thread not found' in err_lower or 'topic_closed' in err_lower or 'topic closed' in err_lower or 'forum topic' in err_lower:
            try:
                kwargs.pop('message_thread_id', None)
                if photo_file_id:
                    if len(press_release) > 1024:
                        if 'video' in kwargs:
                            await context.bot.send_video(**kwargs)
                        elif 'photo' in kwargs:
                            await context.bot.send_photo(**kwargs)
                        await _send_long_text(context.bot, target_chat_id, press_release)
                    else:
                        kwargs['caption'] = press_release
                        if 'video' in kwargs:
                            await context.bot.send_video(**kwargs)
                        else:
                            await context.bot.send_photo(**kwargs)
                else:
                    await _send_long_text(context.bot, target_chat_id, press_release)
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
    if user.id != admin_id:
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
    if user.id != admin_id:
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

        photo_icon = ""
        if post['photo_file_id']:
            if str(post['photo_file_id']).startswith('video:'):
                photo_icon = " 🎥"
            else:
                photo_icon = " 📷"

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
    if user.id != admin_id:
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
    if user.id != admin_id:
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

    photo_status = "📄 Без медиа"
    if post['photo_file_id']:
        if str(post['photo_file_id']).startswith('video:'):
            photo_status = "🎥 Прикреплено видео"
        else:
            photo_status = "📷 Прикреплено фото"

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

    if post['photo_file_id']:
        keyboard.append([
            InlineKeyboardButton("🔄 Заменить фото", callback_data=f"pr_edit_photo_{post_id}"),
            InlineKeyboardButton("🗑 Убрать фото", callback_data=f"pr_edit_remove_photo_{post_id}"),
        ])
    else:
        keyboard.append([InlineKeyboardButton("📷 Добавить фото", callback_data=f"pr_edit_photo_{post_id}")])

    keyboard.append([InlineKeyboardButton("🔙 К списку", callback_data="pr_scheduled_list")])

    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_pr_edit_text(query, data, user, context, db, admin_id):
    """Start editing text of a scheduled post"""
    if user.id != admin_id:
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
    """Start adding/replacing photo of a scheduled post"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_photo_", ""))
    post = db.get_scheduled_post(post_id)

    if not post or post['status'] != 'pending':
        await query.answer("❌ Пост не найден.", show_alert=True)
        return

    context.user_data['awaiting_edit_photo'] = post_id

    await query.edit_message_text(
        f"📷 ДОБАВИТЬ/ЗАМЕНИТЬ ФОТО (пост #{post_id})\n\n"
        "Отправьте фото.\n\n"
        "Для отмены: /cancel",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data=f"pr_edit_{post_id}")]
        ])
    )


async def handle_pr_edit_remove_photo(query, data, user, context, db, admin_id, target_chat_id=None):
    """Remove photo from a scheduled post"""
    if user.id != admin_id:
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_remove_photo_", ""))
    updated = db.update_scheduled_post(post_id, photo_file_id=None)

    if updated:
        await query.answer("🗑 Фото убрано!", show_alert=True)
    else:
        await query.answer("❌ Не удалось обновить пост.", show_alert=True)

    await handle_pr_edit(query, f"pr_edit_{post_id}", user, context, db, admin_id, target_chat_id)


async def handle_pr_edit_time(query, data, user, context, db, admin_id):
    """Start editing publish time of a scheduled post"""
    if user.id != admin_id:
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
    if user.id != admin_id:
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
    if user.id != admin_id:
        await query.answer("У вас нет доступа.", show_alert=True)
        return

    post_id = int(data.replace("pr_edit_publishnow_", ""))
    post = db.get_scheduled_post(post_id)

    if not post or post['status'] != 'pending':
        await query.answer("❌ Пост не найден или уже опубликован.", show_alert=True)
        return

    text = post['text'] or ''
    photo_file_id = post['photo_file_id']
    chat_id_for_topic = post['target_chat_id'] or target_chat_id
    thread_id = post['thread_id']

    # Форматирование: жирная первая строка
    lines = text.split('\n', 1)
    if len(lines) > 1:
        formatted_text = f"<b>{lines[0]}</b>\n{lines[1]}"
    else:
        formatted_text = f"<b>{lines[0]}</b>"

    press_release = (
        f"{formatted_text}\n\n"
        f"<i>© Сообщество Pulse</i>"
    )

    try:
        kwargs = {
            'chat_id': chat_id_for_topic,
            'parse_mode': 'HTML',
        }
        if thread_id:
            kwargs['message_thread_id'] = thread_id

        if photo_file_id:
            is_video = False
            raw_file_id = photo_file_id

            if str(photo_file_id).startswith('video:'):
                is_video = True
                raw_file_id = photo_file_id.split(':', 1)[1]
            elif str(photo_file_id).startswith('photo:'):
                raw_file_id = photo_file_id.split(':', 1)[1]

            if len(press_release) > 1024:
                if is_video:
                    kwargs['video'] = raw_file_id
                    await context.bot.send_video(**kwargs)
                else:
                    kwargs['photo'] = raw_file_id
                    await context.bot.send_photo(**kwargs)
                await _send_long_text(context.bot, chat_id_for_topic, press_release, thread_id=thread_id)
            else:
                if is_video:
                    kwargs['video'] = raw_file_id
                    kwargs['caption'] = press_release
                    await context.bot.send_video(**kwargs)
                else:
                    kwargs['photo'] = raw_file_id
                    kwargs['caption'] = press_release
                    await context.bot.send_photo(**kwargs)
        else:
            await _send_long_text(context.bot, chat_id_for_topic, press_release, thread_id=thread_id)

        db.delete_scheduled_post(post_id)
        await query.answer("✅ Пресс-релиз успешно опубликован!", show_alert=True)
        await show_scheduled_posts(query, user, context, db, admin_id, target_chat_id)

    except Exception as e:
        import logging
        err_lower = str(e).lower()
        if 'thread not found' in err_lower or 'topic_closed' in err_lower or 'topic closed' in err_lower or 'forum topic' in err_lower:
            try:
                kwargs.pop('message_thread_id', None)
                if photo_file_id:
                    if len(press_release) > 1024:
                        if 'video' in kwargs:
                            await context.bot.send_video(**kwargs)
                        elif 'photo' in kwargs:
                            await context.bot.send_photo(**kwargs)
                        await _send_long_text(context.bot, chat_id_for_topic, press_release)
                    else:
                        kwargs['caption'] = press_release
                        if 'video' in kwargs:
                            await context.bot.send_video(**kwargs)
                        else:
                            await context.bot.send_photo(**kwargs)
                else:
                    await _send_long_text(context.bot, chat_id_for_topic, press_release)
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
    if user.id != admin_id:
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
    if user.id != admin_id:
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
    context.user_data.pop('pr_data', None)

    await query.edit_message_text(
        "❌ Создание пресс-релиза отменено.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
        ]])
    )
