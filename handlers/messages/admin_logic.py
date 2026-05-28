#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль админ-панели и рассылок — вынесен из message_handler.py

Обрабатывает все ожидания ввода от админа (awaiting_*),
а также пресс-релизы и клавиатуру тем.

Все функции — модульного уровня (без класса).
db, admin_id, target_chat_id передаются явно.

Использование в message_handler.py:
    from handlers.messages.admin_logic import (
        process_admin_input,
        build_topic_keyboard,
        publish_press_release,
        publish_press_release_to_target,
    )
"""

import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import format_number
from handlers.pr_handlers import _resolve_thread_name
from telegram import Update
from telegram.ext import ContextTypes
from utils.helpers import format_number

# Импортируйте вашу логику пересчета (если она есть в другом файле)
# Например: from utils.math_logic import calculate_dynamic_rate

async def force_update_bot_state(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """
    Принудительный пересчет курса и статистики (Ручной запуск)
    """
    user_id = update.effective_user.id
    
    # 1. Проверяем админа (на всякий случай)
    # (Хотя вы будете вызывать это из админки, лишняя проверка не помешает)
    user_data = db.get_user(user_id)
    if not user_data or not (user_data.get('is_owner') or user_data.get('is_admin')):
        return

    status_msg = await update.message.reply_text("⏳ Начинаю принудительный пересчет...")

    # 2. Собираем статистику за ПОСЛЕДНИЕ 24 ЧАСА (а не просто "сегодня")
    # Это решает проблему "пустого дня" после перезапуска
    db.cursor.execute('''
        SELECT COUNT(*) as msgs, COUNT(DISTINCT user_id) as users 
        FROM messages 
        WHERE timestamp >= datetime('now', '-1 day')
    ''')
    stats = db.cursor.fetchone()
    
    msgs_24h = stats['msgs']
    active_users_24h = stats['users']

    # 3. Пример вашей формулы курса (замените на свою!)
    # Допустим: 100 сообщений = +0.1 к курсу. База = 1.0
    # Вставьте сюда ту логику, которая была у вас "умной"
    
    # ПРИМЕР ФОРМУЛЫ:
    base_rate = 1.0
    activity_bonus = (msgs_24h / 1000)  # Каждая 1000 сообщений дает +1 рубль
    new_rate = round(base_rate + activity_bonus, 2)

    # Защита от слишком низкого курса
    if new_rate < 1.0: new_rate = 1.0

    # 4. Применяем изменения
    db.set_exchange_rate(new_rate)
    
    # 5. Отчет
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=status_msg.message_id,
        text=(
            f"✅ **Система обновлена вручную!**\n\n"
            f"📊 Активность за 24ч:\n"
            f"• Сообщений: {msgs_24h}\n"
            f"• Активных: {active_users_24h}\n\n"
            f"💱 **Новый курс:** 1 💎 = {new_rate} ₽"
        ),
        parse_mode='Markdown'
    )

def make_first_line_bold(text):
    """Make the first line of text bold (HTML). Rest stays as-is."""
    if not text:
        return text
    lines = text.split('\n', 1)
    first_line = f"<b>{lines[0]}</b>"
    if len(lines) > 1:
        return first_line + '\n' + lines[1]
    return first_line


# ═══════════════════════════════════════════════════════════════
# КЛАВИАТУРА ТЕМ (ВЕТОК)
# ═══════════════════════════════════════════════════════════════

async def build_topic_keyboard(context, db, target_chat_id):
    """Build keyboard with available topics/threads from DB + auto-refresh via Telegram API."""
    keyboard = []

    # Main chat / General option always present
    keyboard.append([InlineKeyboardButton(
        "💬 General (основной чат)",
        callback_data="pr_target_main"
    )])

    # Get topics from DB
    topics = db.get_all_topics(target_chat_id)

    named_topics = []
    unnamed_topics = []

    for topic in topics:
        if topic['is_main_thread']:
            continue  # Skip main — already added above
        if not topic['thread_id']:
            continue

        name = topic['thread_name'] or ''
        tid = topic['thread_id']

        # Generic only when empty or exactly default auto-name for this ID.
        # Do not hide real names that happen to start with "Ветка".
        normalized = name.strip()
        is_generic = (
            not normalized or
            normalized == f'Ветка #{tid}' or
            normalized == f'Ветка {tid}'
        )

        if is_generic:
            unnamed_topics.append(topic)
        else:
            named_topics.append(topic)

    # Show topics with real names first
    for topic in named_topics:
        keyboard.append([InlineKeyboardButton(
            f"🧵 {topic['thread_name']}",
            callback_data=f"pr_target_thread_{topic['thread_id']}"
        )])

    # Show unnamed topics (if any exist) in a compact way
    if unnamed_topics:
        for topic in unnamed_topics:
            keyboard.append([InlineKeyboardButton(
                f"❓ Ветка #{topic['thread_id']} (имя неизвестно)",
                callback_data=f"pr_target_thread_{topic['thread_id']}"
            )])

    # Manual entry always available
    keyboard.append([InlineKeyboardButton(
        "✏️ Ввести ID ветки вручную",
        callback_data="pr_target_manual"
    )])

    # Refresh / scan button
    keyboard.append([InlineKeyboardButton(
        "🔄 Обновить список веток",
        callback_data="pr_refresh_topics"
    )])

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="pr_cancel")])

    return keyboard


# ═══════════════════════════════════════════════════════════════
# ПУБЛИКАЦИЯ ПРЕСС-РЕЛИЗОВ
# ═══════════════════════════════════════════════════════════════

async def publish_press_release(message, context, target_chat_id):
    """Publish press release to chat with optional image (legacy — from group chat)"""
    try:
        text = message.text or message.caption

        # Format press release text
        press_release = (
            f"{make_first_line_bold(text)}\n\n"
            "<i>© PositivЭ</i>"
        )

        # Check if message has photo
        if message.photo:
            photo = message.photo[-1]  # Get highest quality
            if len(press_release) <= 1024:
                await context.bot.send_photo(
                    chat_id=target_chat_id,
                    photo=photo.file_id,
                    caption=press_release,
                    parse_mode='HTML',
                    _no_chain=True,
                )
            else:
                await context.bot.send_photo(
                    chat_id=target_chat_id,
                    photo=photo.file_id,
                    _no_chain=True,
                )
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text=press_release,
                    parse_mode='HTML',
                    _no_chain=True,
                )
        else:
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=press_release,
                parse_mode='HTML',
                _no_chain=True,
            )

        # Confirm to owner
        await message.reply_text("✅ Пресс-релиз опубликован в чате!")

    except Exception as e:
        logging.error(f"Error publishing press release: {e}")
        await message.reply_text(f"❌ Ошибка при публикации: {e}")


async def publish_press_release_to_target(bot, text, photo_file_id, chat_id, thread_id=None):
    """Publish formatted press release to specific chat/thread (used by scheduler)"""
    from handlers.PR.press_release_pr import _parse_media, _send_pr_media
    try:
        media_list = _parse_media(photo_file_id)
        await _send_pr_media(bot, chat_id, thread_id, media_list, text)
        return True
    except Exception as e:
        logging.error(f"Error publishing press release to target: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# ДИСПЕТЧЕР ОЖИДАЮЩЕГО ВВОДА АДМИНА
# ═══════════════════════════════════════════════════════════════

async def process_admin_input(message, user, context, db, admin_id, target_chat_id, update=None):
    """
    Обрабатывает все awaiting_* блоки ввода.

    Возвращает True если сообщение было обработано (caller должен сделать return).
    Возвращает False если ни один awaiting-блок не сработал.
    """
    if message.chat.type != 'private':
        return False

    # Проверяем права: владелец или зам
    from database.db_friend import is_deputy as _is_deputy_fn
    _is_privileged = user.id == admin_id or await _is_deputy_fn(user.id)

    # === РЕДАКТИРОВАНИЕ АНКЕТЫ (фото / примечание) ===
    if context.user_data.get('anketa_edit') and _is_privileged:
        from handlers.anketa_edit_handlers import handle_anketa_edit_input
        if await handle_anketa_edit_input(message, context, db):
            return True

    # === ОБРАБОТКА ВРЕМЕНИ РАСПИСАНИЯ ГОРОСКОПА ===
    if context.user_data.get('awaiting_horoscope_sched_time') and _is_privileged:
        await _handle_awaiting_horoscope_sched_time(message, context, db)
        return True

    # === ОБРАБОТКА ВВОДА ID ВЕТКИ (для пресс-релиза) ===
    if context.user_data.get('awaiting_thread_id') and _is_privileged:
        await _handle_awaiting_thread_id(message, user, context, db, target_chat_id)
        return True

    # === ОБРАБОТКА ФОТО ДЛЯ ПРЕСС-РЕЛИЗА (кнопка «📷 Добавить фото») ===
    if context.user_data.get('awaiting_pr_photo') and _is_privileged:
        await _handle_awaiting_pr_photo(message, context, db, target_chat_id)
        return True

    # === ОБРАБОТКА ИЗМЕНЕНИЯ ТЕКСТА ТЕКУЩЕГО ПРЕСС-РЕЛИЗА ===
    if context.user_data.get('awaiting_pr_current_text_edit') and _is_privileged:
        await _handle_awaiting_pr_current_text_edit(message, context, db, target_chat_id)
        return True

    # === ОБРАБОТКА РЕДАКТИРОВАНИЯ ТЕКСТА ===
    if context.user_data.get('awaiting_edit_text') and _is_privileged:
        await _handle_awaiting_edit_text(message, context, db)
        return True

    # === ОБРАБОТКА РЕДАКТИРОВАНИЯ ФОТО ===
    if context.user_data.get('awaiting_edit_photo') and _is_privileged:
        await _handle_awaiting_edit_photo(message, context, db)
        return True

    # === ОБРАБОТКА РЕДАКТИРОВАНИЯ ВРЕМЕНИ ===
    if context.user_data.get('awaiting_edit_time') and _is_privileged:
        await _handle_awaiting_edit_time(message, context, db, target_chat_id)
        return True

    # === ОБРАБОТКА РУЧНОГО ВВОДА ВЕТКИ ПРИ РЕДАКТИРОВАНИИ ===
    if context.user_data.get('awaiting_edit_target_manual') and _is_privileged:
        await _handle_awaiting_edit_target_manual(message, context, db, target_chat_id)
        return True

    # === ОБРАБОТКА ВВОДА ВРЕМЕНИ (для отложенного пресс-релиза) ===
    if context.user_data.get('awaiting_schedule_time') and _is_privileged:
        await _handle_awaiting_schedule_time(message, user, context, db, target_chat_id)
        return True

    # === ОБРАБОТКА ПРЕСС-РЕЛИЗА ===
    if context.user_data.get('awaiting_press_release') and _is_privileged:
        await _handle_awaiting_press_release(message, context, db, target_chat_id)
        return True

    # === ОБРАБОТКА УСТАНОВКИ КУРСА ===
    if context.user_data.get('awaiting_exchange_rate') and _is_privileged:
        await _handle_awaiting_exchange_rate(message, context, db)
        return True

    # === ОБРАБОТКА ВВОДА @USERNAME ДЛЯ БАНКОВОГО ПЕРЕВОДА ===
    if context.user_data.get('awaiting_bt_username') and _is_privileged:
        await _handle_awaiting_bt_username(message, user, context, db)
        return True

    # === ОБРАБОТКА ПЕРЕВОДА ИЗ БАНКА ===
    if context.user_data.get('awaiting_bank_transfer') and _is_privileged:
        await _handle_awaiting_bank_transfer(message, user, context, db)
        return True

    # === ОБРАБОТКА РУЧНОГО ВВОДА ПОЛУЧАТЕЛЯ ДОНАТА (@username / ID) ===
    if context.user_data.get('awaiting_donate_manual_user'):
        from handlers.donate_handlers import handle_manual_donate_user
        if await handle_manual_donate_user(message, context, db):
            return True

    # === ОБРАБОТКА ВВОДА СУММЫ ДОНАТА ===
    donate_type = context.user_data.get('awaiting_donate_amount')
    if donate_type:
        await _handle_awaiting_donate_amount(message, user, context, db, donate_type)
        return True

    # === OWNER PANEL FSM (Персонал, Эмиссия, Блэклист, Журнал) ===
    if context.user_data.get('owner_awaiting') and _is_privileged:
        _upd = update  # may be None if caller didn't pass it
        awaiting_val = context.user_data['owner_awaiting']
        if (
            awaiting_val == 'journal_connect'
            or awaiting_val.startswith('journal_connect_')
            or awaiting_val.startswith('journal_thread_')
        ):
            from handlers.journal_handlers import handle_journal_text_input
            if _upd is not None:
                return await handle_journal_text_input(_upd, context, db)
            # fallback: construct minimal proxy
            class _FakeUpdate:
                effective_message = message
                effective_user = user
            return await handle_journal_text_input(_FakeUpdate(), context, db)
        from handlers.owner_handlers import handle_owner_text_input
        if _upd is not None:
            return await handle_owner_text_input(_upd, context, db, admin_id, target_chat_id)
        class _FakeUpdate2:
            effective_message = message
            effective_user = user
        return await handle_owner_text_input(_FakeUpdate2(), context, db, admin_id, target_chat_id)

    return False


# ═══════════════════════════════════════════════════════════════
# ОБРАБОТЧИКИ ОТДЕЛЬНЫХ AWAITING-БЛОКОВ
# ═══════════════════════════════════════════════════════════════

async def _handle_awaiting_thread_id(message, user, context, db, target_chat_id):
    """Обработка ввода ID ветки для пресс-релиза."""
    if message.text == '/cancel':
        context.user_data['awaiting_thread_id'] = False
        context.user_data.pop('pr_data', None)
        await message.reply_text("❌ Действие отменено.")
        return

    text = (message.text or "").strip()
    try:
        thread_id_input = int(text)
        context.user_data['awaiting_thread_id'] = False

        pr_data = context.user_data.get('pr_data', {})
        pr_data['thread_id'] = thread_id_input
        context.user_data['pr_data'] = pr_data

        # Register this topic in DB for future use
        db.register_topic(target_chat_id, thread_id_input, f"Ветка #{thread_id_input}")

        preview = pr_data.get('text', '')[:150]
        if len(pr_data.get('text', '')) > 150:
            preview += "..."

        await message.reply_text(
            f"📰 ПРЕСС-РЕЛИЗ\n\n"
            f"📝 {preview}\n"
            f"🎯 Куда: {_resolve_thread_name(db, target_chat_id, thread_id_input)}\n\n"
            f"⏰ Когда опубликовать?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Опубликовать сейчас", callback_data="pr_publish_now")],
                [InlineKeyboardButton("⏰ Запланировать", callback_data="pr_schedule")],
                [InlineKeyboardButton("❌ Отмена", callback_data="pr_cancel")]
            ])
        )
    except ValueError:
        await message.reply_text(
            "❌ Введите числовой ID ветки.\n"
            "Например: `123`\n\n"
            "Для отмены: /cancel",
            parse_mode='Markdown'
        )


async def _handle_awaiting_schedule_time(message, user, context, db, target_chat_id):
    """Обработка ввода времени для отложенной публикации."""
    if message.text == '/cancel':
        context.user_data['awaiting_schedule_time'] = False
        context.user_data.pop('pr_data', None)
        await message.reply_text("❌ Планирование отменено.")
        return

    text = (message.text or "").strip()

    import pytz
    moscow_tz = pytz.timezone('Europe/Moscow')

    from utils.helpers import parse_flexible_datetime
    formatted_time_str = parse_flexible_datetime(text)

    if not formatted_time_str:
        await message.reply_text(
            "❌ Не удалось распознать дату/время.\n\n"
            "Пожалуйста, введите 4 или 5 чисел (день, месяц, [год], часы, минуты).\n"
            "Например: `25.03 14:30` или `25,03,26 14,30`\n\n"
            "Для отмены: /cancel",
            parse_mode='Markdown'
        )
        return

    # Превращаем нашу красивую строку обратно в объект времени для бота
    parsed_time = datetime.strptime(formatted_time_str, '%d.%m.%Y %H:%M')
    
    publish_at = moscow_tz.localize(parsed_time)
    now = datetime.now(moscow_tz)

    if publish_at <= now:
        await message.reply_text("❌ Дата должна быть в будущем! Попробуйте снова.")
        return

    context.user_data['awaiting_schedule_time'] = False
    pr_data = context.user_data.get('pr_data', {})
    thread_id_val = pr_data.get('thread_id')

    pr_text = pr_data.get('text', '')
    press_release_text = (
        f"{make_first_line_bold(pr_text)}\n\n"
        "<i>© PositivЭ</i>"
    )

    post_id = db.add_scheduled_post(
        author_id=user.id,
        text=press_release_text,
        photo_file_id=pr_data.get('photo_file_id'),
        target_chat_id=target_chat_id,
        thread_id=thread_id_val,
        publish_at=publish_at.strftime('%Y-%m-%d %H:%M:%S')
    )

    thread_name = _resolve_thread_name(db, target_chat_id, thread_id_val)

    context.user_data.pop('pr_data', None)

    await message.reply_text(
        f"✅ ПРЕСС-РЕЛИЗ ЗАПЛАНИРОВАН\n\n"
        f"🆔 ID: #{post_id}\n"
        f"📅 Публикация: {publish_at.strftime('%d.%m.%Y %H:%M')} МСК\n"
        f"🎯 Куда: {thread_name}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Запланированные", callback_data="pr_scheduled_list")
        ]])
    )


async def _pr_show_topic_keyboard(message, context, db, target_chat_id):
    """Показывает клавиатуру выбора ветки после сбора pr_data."""
    from handlers.PR.press_release_pr import _parse_media, _media_icon_summary
    pr_data = context.user_data.get('pr_data', {})
    keyboard = await build_topic_keyboard(context, db, target_chat_id)
    text = pr_data.get('text', '')
    preview = text[:200] + "..." if len(text) > 200 else text
    media_list = _parse_media(pr_data.get('photo_file_id'))
    summary = _media_icon_summary(media_list)
    preview_msg = "📰 ПРЕДПРОСМОТР ПРЕСС-РЕЛИЗА\n\n"
    if preview:
        preview_msg += f"{preview}\n"
    if summary:
        preview_msg += f"\n{summary}\n"
    preview_msg += "\n🎯 Выберите куда опубликовать:"
    await message.reply_text(preview_msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def _handle_awaiting_press_release(message, context, db, target_chat_id):
    """Обработка ввода текста пресс-релиза. Поддерживает одиночное сообщение и альбомы (media_group)."""
    import asyncio
    from handlers.PR.press_release_pr import MAX_MEDIA, _parse_media, _pack_media

    if message.text == '/cancel':
        context.user_data['awaiting_press_release'] = False
        context.user_data.pop('pr_initial_mg_id', None)
        old_task = context.user_data.pop('pr_mg_task', None)
        if old_task:
            old_task.cancel()
        await message.reply_text("Создание пресс-релиза отменено.")
        return

    text = message.text or message.caption or ""
    mg_id = getattr(message, 'media_group_id', None)

    # ── Альбом (media_group) — накапливаем все файлы, финализируем с задержкой ──
    if mg_id:
        existing_mg = context.user_data.get('pr_initial_mg_id')

        # Новая группа — сбрасываем предыдущие данные
        if existing_mg != mg_id:
            context.user_data['pr_initial_mg_id'] = mg_id
            context.user_data['pr_data'] = {'text': '', 'photo_file_id': None}

        pr_data = context.user_data['pr_data']

        # Текст берём только с первого элемента (у остальных caption пустой)
        if text and not pr_data.get('text'):
            pr_data['text'] = text

        # Добавляем медиа (до MAX_MEDIA)
        media_list = _parse_media(pr_data.get('photo_file_id'))
        if len(media_list) < MAX_MEDIA:
            if message.video:
                media_list.append(('video', message.video.file_id))
            elif message.photo:
                media_list.append(('photo', message.photo[-1].file_id))
            pr_data['photo_file_id'] = _pack_media(media_list) if media_list else None

        context.user_data['pr_data'] = pr_data

        # Отменяем предыдущую задачу финализации, создаём новую с задержкой 1.5с
        old_task = context.user_data.pop('pr_mg_task', None)
        if old_task:
            old_task.cancel()

        async def _finalize_mg():
            await asyncio.sleep(1.5)
            if not context.user_data.get('awaiting_press_release'):
                return
            context.user_data['awaiting_press_release'] = False
            context.user_data.pop('pr_initial_mg_id', None)
            context.user_data.pop('pr_mg_task', None)
            final_data = context.user_data.get('pr_data', {})
            if not final_data.get('text') and not final_data.get('photo_file_id'):
                context.user_data['awaiting_press_release'] = True
                await message.reply_text("❌ Не удалось получить медиафайлы. Попробуйте снова.")
                return
            await _pr_show_topic_keyboard(message, context, db, target_chat_id)

        context.user_data['pr_mg_task'] = asyncio.create_task(_finalize_mg())
        return

    # ── Одиночное сообщение ──
    media_file_id = None
    if message.video:
        media_file_id = f"video:{message.video.file_id}"
    elif message.photo:
        media_file_id = f"photo:{message.photo[-1].file_id}"

    if not text and not media_file_id:
        await message.reply_text("❌ Отправьте текст, фото или видео для пресс-релиза.")
        return

    context.user_data['awaiting_press_release'] = False
    context.user_data.pop('pr_initial_mg_id', None)
    context.user_data['pr_data'] = {
        'text': text,
        'photo_file_id': media_file_id,
    }

    await _pr_show_topic_keyboard(message, context, db, target_chat_id)


async def _handle_awaiting_pr_current_text_edit(message, context, db, target_chat_id):
    """Обновление текста текущего (несохранённого) пресс-релиза после предупреждения о длине."""
    if message.text == '/cancel':
        context.user_data.pop('awaiting_pr_current_text_edit', None)
        await message.reply_text("❌ Редактирование отменено.")
        return

    new_text = message.text or message.caption or ""
    if not new_text:
        await message.reply_text("❌ Отправьте новый текст. Для отмены: /cancel")
        return

    pr_data = context.user_data.get('pr_data', {})
    pr_data['text'] = new_text
    context.user_data['pr_data'] = pr_data
    context.user_data.pop('awaiting_pr_current_text_edit', None)

    keyboard = await build_topic_keyboard(context, db, target_chat_id)
    photo_file_id = pr_data.get('photo_file_id')
    preview = new_text[:200] + "..." if len(new_text) > 200 else new_text
    preview_msg = f"📰 ПРЕДПРОСМОТР ПРЕСС-РЕЛИЗА\n\n{preview}\n"
    if photo_file_id:
        preview_msg += "\n🎥 С видео\n" if str(photo_file_id).startswith('video:') else "\n📷 С фото\n"
    preview_msg += "\n🎯 Выберите куда опубликовать:"

    await message.reply_text(preview_msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def _handle_awaiting_exchange_rate(message, context, db):
    """Обработка ввода нового курса обмена."""
    if message.text == '/cancel':
        context.user_data['awaiting_exchange_rate'] = False
        await message.reply_text("Установка курса отменена.")
        return

    try:
        new_rate = float(message.text.strip())
        if new_rate <= 0:
            await message.reply_text("❌ Курс должен быть положительным числом.")
            return

        db.set_exchange_rate(new_rate, changed_by=message.from_user.id)
        context.user_data['awaiting_exchange_rate'] = False

        await message.reply_text(
            f"✅ Курс установлен!\n\n"
            f"💱 Новый курс: 1 💎 = {new_rate} ₽"
        )

    except ValueError:
        await message.reply_text("❌ Неверный формат. Введите число (например: 0.5)")


async def _handle_awaiting_bt_username(message, user, context, db):
    """Обработка ввода @username получателя банкового перевода."""
    context.user_data.pop('awaiting_bt_username', None)

    if message.text == '/cancel':
        await message.reply_text("Ввод отменён.")
        return

    username = message.text.strip().lstrip('@')
    target_user = db.get_user_by_username(username)

    if not target_user:
        await message.reply_text(f"❌ Пользователь @{username} не найден в базе.\nПопробуйте ещё раз или выберите из списка: /bank")
        return

    from handlers.bank_handlers import select_transfer_amount
    # Перенаправляем на выбор суммы через фейковый query — проще отправить сообщение
    target_id = target_user['user_id']
    display = target_user['username'] or target_user['first_name'] or str(target_id)
    bank_balance = db.get_bank_balance()

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from utils.helpers import format_number
    keyboard = [
        [
            InlineKeyboardButton("50 💎", callback_data=f"bt_amount_{target_id}_50"),
            InlineKeyboardButton("100 💎", callback_data=f"bt_amount_{target_id}_100")
        ],
        [
            InlineKeyboardButton("500 💎", callback_data=f"bt_amount_{target_id}_500"),
            InlineKeyboardButton("1000 💎", callback_data=f"bt_amount_{target_id}_1000")
        ],
        [InlineKeyboardButton("✏️ Своя сумма", callback_data=f"bt_custom_{target_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="bank_transfer_start")],
    ]
    await message.reply_text(
        f"💸 ПЕРЕВОД ДЛЯ @{display}\n\n"
        f"💰 Баланс банка: {format_number(bank_balance)} 💎\n\n"
        f"Выберите сумму:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _handle_awaiting_bank_transfer(message, user, context, db):
    """Обработка ввода перевода из банка."""
    if message.text == '/cancel':
        context.user_data['awaiting_bank_transfer'] = False
        context.user_data.pop('bt_custom_user_id', None)
        await message.reply_text("Перевод из банка отменён.")
        return

    try:
        # Check if this is custom amount from inline buttons
        if 'bt_custom_user_id' in context.user_data:
            target_user_id = context.user_data['bt_custom_user_id']
            amount = float(message.text.strip())
        else:
            # Old format: user_id amount
            parts = message.text.strip().split()
            if len(parts) != 2:
                await message.reply_text(
                    "❌ Неверный формат.\n\n"
                    "Используйте: user_id сумма\n"
                    "Пример: 123456789 100.50"
                )
                return

            target_user_id = int(parts[0])
            amount = float(parts[1])

        if amount <= 0:
            await message.reply_text("❌ Сумма должна быть положительной.")
            return

        # Check bank balance
        bank_balance = db.get_bank_balance()
        if amount > bank_balance:
            await message.reply_text(
                f"❌ Недостаточно средств в банке!\n\n"
                f"💰 В банке: {format_number(bank_balance)} 💎\n"
                f"📤 Запрошено: {format_number(amount)} 💎"
            )
            return

        # Check if user exists
        target_user = db.get_user(target_user_id)
        if not target_user:
            await message.reply_text(f"❌ Пользователь {target_user_id} не найден в базе.")
            return

        # Subtract from bank
        db.update_bank_balance(amount, 'subtract')

        # Add to user
        db.update_user_balance(target_user_id, amount, 'add')

        # Record transaction
        db.add_transaction(
            None,  # from_user (bank)
            target_user_id,
            amount,
            'bank_transfer',
            'Перевод из банка владельцем'
        )

        context.user_data['awaiting_bank_transfer'] = False
        context.user_data.pop('bt_custom_user_id', None)

        target_username = target_user['username'] or target_user['first_name'] or str(target_user_id)

        await message.reply_text(
            f"✅ Перевод выполнен!\n\n"
            f"👤 Получатель: @{target_username}\n"
            f"💎 Сумма: {format_number(amount)} Пульсов\n\n"
            f"💰 Остаток в банке: {format_number(db.get_bank_balance())} 💎"
        )

        # Notify recipient
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"💸 Вам зачислены Пульсы из банка!\n\n"
                     f"💎 Сумма: {format_number(amount)} Пульсов\n"
                     f"💰 Ваш баланс: {format_number(target_user['balance'] + amount)} 💎"
            )
        except Exception as e:
            logging.warning(f"Could not notify user {target_user_id}: {e}")

    except ValueError:
        await message.reply_text("❌ Неверный формат. Введите число (например: 250.50)")
    except Exception as e:
        logging.error(f"Error in bank transfer: {e}")
        await message.reply_text(f"❌ Ошибка при переводе: {str(e)}")


async def _handle_awaiting_horoscope_sched_time(message, context, db):
    """FSM: обработка ввода времени для расписания гороскопа (HH:MM)."""
    import re as _re
    context.user_data.pop('awaiting_horoscope_sched_time', None)

    raw = (message.text or '').strip()
    if not _re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', raw):
        await message.reply_text(
            "❌ Неверный формат. Введи время в виде <code>ЧЧ:ММ</code>, "
            "например <code>09:00</code> или <code>21:30</code>.",
            parse_mode='HTML',
        )
        return

    db.set_setting('horoscope_schedule_time', raw)
    await message.reply_text(
        f"✅ Время публикации гороскопа установлено: <b>{raw} МСК</b>.\n"
        f"Вернись в меню расписания чтобы проверить настройки.",
        parse_mode='HTML',
    )


async def _handle_awaiting_donate_amount(message, user, context, db, donate_type):
    """Обработка ввода своей суммы доната."""
    if message.text and message.text.strip() == '/cancel':
        context.user_data.pop('awaiting_donate_amount', None)
        context.user_data.pop('donate_custom_target_id', None)
        await message.reply_text("Донат отменён.")
        return

    try:
        amount = round(float(message.text.strip()), 2)
        if amount <= 0:
            await message.reply_text("❌ Сумма должна быть положительной.")
            return

        user_data = db.get_user(user.id)
        if not user_data or float(user_data['balance']) < amount:
            await message.reply_text(
                f"❌ Недостаточно средств!\n"
                f"💰 Баланс: {format_number(float(user_data['balance']) if user_data else 0)} 💎"
            )
            return

        sender_name = user_data['username'] or user_data['first_name'] or f"ID:{user.id}"

        # ── Донат пользователю ──
        if donate_type == 'user':
            target_user_id = context.user_data.get('donate_custom_target_id')
            if not target_user_id:
                context.user_data.pop('awaiting_donate_amount', None)
                await message.reply_text("❌ Получатель не найден. /donate для начала")
                return

            target_user = db.get_user(target_user_id)
            if not target_user:
                context.user_data.pop('awaiting_donate_amount', None)
                context.user_data.pop('donate_custom_target_id', None)
                await message.reply_text("❌ Получатель не найден.")
                return

            db.update_user_balance(user.id, amount, 'subtract')
            db.update_user_balance(target_user_id, amount, 'add')

            target_name = target_user['username'] or target_user['first_name'] or f"ID:{target_user_id}"
            db.add_transaction(user.id, target_user_id, amount, 'donate_to_user', f'Донат для @{target_name}')

            context.user_data.pop('awaiting_donate_amount', None)
            context.user_data.pop('donate_custom_target_id', None)

            await message.reply_text(
                f"✅ ДОНАТ ОТПРАВЛЕН!\n\n"
                f"🎁 @{sender_name} → @{target_name}\n"
                f"💎 Сумма: {format_number(amount)} Пульсов\n"
                f"💰 Ваш баланс: {format_number(float(user_data['balance']) - amount)} 💎"
            )
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🎁 Вам пришёл донат!\n\n"
                         f"👤 От: @{sender_name}\n"
                         f"💎 Сумма: {format_number(amount)} Пульсов"
                )
            except:
                pass

        # ── Донат в банк ──
        elif donate_type == 'bank':
            db.update_user_balance(user.id, amount, 'subtract')
            db.update_bank_balance(amount, 'add')
            db.add_transaction(user.id, None, amount, 'donate_to_bank', 'Донат в Центробанк')

            context.user_data.pop('awaiting_donate_amount', None)

            await message.reply_text(
                f"✅ ДОНАТ В БАНК!\n\n"
                f"👤 От: @{sender_name}\n"
                f"💎 Сумма: {format_number(amount)} Пульсов\n"
                f"🏦 Банк: {format_number(db.get_bank_balance())} 💎\n"
                f"💰 Баланс: {format_number(float(user_data['balance']) - amount)} 💎"
            )

        # ── Донат в реактор ──
        elif donate_type == 'reactor':
            db.update_user_balance(user.id, amount, 'subtract')
            db.update_bank_balance(amount, 'add')
            db.cursor.execute('INSERT INTO reactor (user_id, amount) VALUES (?, ?)', (user.id, amount))
            current_reactor = float(db.get_setting('reactor_balance', 0))
            db.set_setting('reactor_balance', current_reactor + amount)
            db.add_transaction(user.id, None, amount, 'reactor_donation', 'Донат в Реактор')
            db.conn.commit()

            context.user_data.pop('awaiting_donate_amount', None)

            reactor_balance = float(db.get_setting('reactor_balance', 0))
            reactor_goal = float(db.get_setting('reactor_goal', 10000))
            progress = (reactor_balance / reactor_goal) * 100 if reactor_goal > 0 else 0

            await message.reply_text(
                f"✅ ДОНАТ В РЕАКТОР!\n\n"
                f"💎 Сумма: {format_number(amount)} Пульсов\n"
                f"🔋 Реактор: {format_number(reactor_balance)} / {format_number(reactor_goal)}\n"
                f"📊 Прогресс: {progress:.1f}%"
            )

    except ValueError:
        await message.reply_text("❌ Неверный формат. Введите число (например: 12.50)")
    except Exception as e:
        logging.error(f"Error in donate custom: {e}")
        await message.reply_text(f"❌ Ошибка: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ ЗАПЛАНИРОВАННЫХ ПОСТОВ
# ═══════════════════════════════════════════════════════════════

async def _pr_photo_reply(message, context):
    """Отправляет одну реплику с текущим счётчиком медиа + кнопками."""
    from handlers.PR.press_release_pr import MAX_MEDIA, _parse_media, _media_icon_summary
    pr_data = context.user_data.get('pr_data', {})
    media_list = _parse_media(pr_data.get('photo_file_id'))
    n = len(media_list)
    summary = _media_icon_summary(media_list)
    hint = f"Отправьте ещё или нажмите ✅ Готово." if n < MAX_MEDIA else f"Достигнут лимит {MAX_MEDIA} файлов."
    keyboard_rows = [
        [InlineKeyboardButton("✅ Готово", callback_data="pr_media_done")],
        [InlineKeyboardButton("🗑 Очистить медиа", callback_data="pr_remove_photo")],
        [InlineKeyboardButton("❌ Отмена", callback_data="pr_cancel")],
    ]
    await message.reply_text(
        f"✅ Медиа добавлено!\n\n"
        f"📎 Прикреплено: {summary} ({n}/{MAX_MEDIA})\n\n"
        f"{hint}",
        reply_markup=InlineKeyboardMarkup(keyboard_rows)
    )


async def _handle_awaiting_pr_photo(message, context, db, target_chat_id):
    """Обработка отправки медиа для пресс-релиза (накопительный режим, до 5 файлов).
    Поддерживает одиночные файлы и альбомы (media_group) — одна реплика на весь альбом.
    """
    import asyncio
    from handlers.PR.press_release_pr import MAX_MEDIA, _parse_media, _pack_media, _media_icon_summary

    if message.text == '/cancel':
        context.user_data.pop('awaiting_pr_photo', None)
        context.user_data.pop('pr_add_mg_id', None)
        old_task = context.user_data.pop('pr_add_mg_task', None)
        if old_task:
            old_task.cancel()
        await message.reply_text("❌ Добавление медиа отменено.")
        return

    if not message.photo and not message.video:
        await message.reply_text(
            "❌ Это не медиафайл. Отправьте фото или видео.\n\n"
            "Для отмены: /cancel"
        )
        return

    pr_data = context.user_data.get('pr_data', {})
    media_list = _parse_media(pr_data.get('photo_file_id'))

    if len(media_list) >= MAX_MEDIA:
        await message.reply_text(
            f"⚠️ Уже {MAX_MEDIA}/{MAX_MEDIA} медиафайлов. Нажмите ✅ Готово или 🗑 Очистить.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Готово", callback_data="pr_media_done")],
                [InlineKeyboardButton("🗑 Очистить медиа", callback_data="pr_remove_photo")],
            ])
        )
        return

    if message.video:
        kind, file_id = 'video', message.video.file_id
    else:
        kind, file_id = 'photo', message.photo[-1].file_id

    media_list.append((kind, file_id))
    pr_data['photo_file_id'] = _pack_media(media_list)
    context.user_data['pr_data'] = pr_data

    mg_id = getattr(message, 'media_group_id', None)

    if mg_id:
        # Альбом: накапливаем тихо, финализируем одной репликой через 1.5с
        context.user_data['pr_add_mg_id'] = mg_id
        old_task = context.user_data.pop('pr_add_mg_task', None)
        if old_task:
            old_task.cancel()

        async def _finalize_add():
            await asyncio.sleep(1.5)
            context.user_data.pop('pr_add_mg_id', None)
            context.user_data.pop('pr_add_mg_task', None)
            await _pr_photo_reply(message, context)

        context.user_data['pr_add_mg_task'] = asyncio.create_task(_finalize_add())
    else:
        # Одиночный файл: отвечаем сразу
        await _pr_photo_reply(message, context)


async def _handle_awaiting_edit_text(message, context, db):
    """Обработка нового текста для редактирования запланированного поста."""
    post_id = context.user_data.get('awaiting_edit_text')

    if message.text == '/cancel':
        context.user_data.pop('awaiting_edit_text', None)
        await message.reply_text(
            "❌ Редактирование отменено.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 К посту", callback_data=f"pr_edit_{post_id}")
            ]])
        )
        return

    new_text = message.text or message.caption or ""
    if not new_text:
        await message.reply_text("❌ Отправьте текст. Для отмены: /cancel")
        return

    # Форматируем как пресс-релиз
    formatted_text = (
        f"{make_first_line_bold(new_text)}\n\n"
        "<i>© PositivЭ</i>"
    )

    updated = db.update_scheduled_post(post_id, text=formatted_text)
    context.user_data.pop('awaiting_edit_text', None)

    if updated:
        await message.reply_text(
            f"✅ Текст поста #{post_id} обновлён!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ К посту", callback_data=f"pr_edit_{post_id}")],
                [InlineKeyboardButton("📋 К списку", callback_data="pr_scheduled_list")]
            ])
        )
    else:
        await message.reply_text(
            f"❌ Не удалось обновить пост #{post_id}. Возможно, он уже опубликован.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 К списку", callback_data="pr_scheduled_list")
            ]])
        )


async def _handle_awaiting_edit_photo(message, context, db):
    """Обработка медиа для запланированного поста (накопительный режим, до 5 файлов)."""
    post_id = context.user_data.get('awaiting_edit_photo')

    if message.text == '/cancel':
        context.user_data.pop('awaiting_edit_photo', None)
        context.user_data.pop('edit_photo_buffer', None)
        await message.reply_text(
            "❌ Редактирование медиа отменено.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 К посту", callback_data=f"pr_edit_{post_id}")
            ]])
        )
        return

    if not message.photo and not message.video:
        await message.reply_text(
            "❌ Это не медиафайл. Отправьте фото или видео.\n\n"
            "Для отмены: /cancel"
        )
        return

    from handlers.PR.press_release_pr import MAX_MEDIA, _pack_media, _media_icon_summary

    buffer = context.user_data.get('edit_photo_buffer', [])

    if len(buffer) >= MAX_MEDIA:
        await message.reply_text(
            f"⚠️ Уже {MAX_MEDIA}/{MAX_MEDIA} файлов. Нажмите ✅ Готово.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Готово", callback_data=f"pr_edit_media_done_{post_id}")
            ]])
        )
        return

    if message.video:
        kind, file_id = 'video', message.video.file_id
    else:
        kind, file_id = 'photo', message.photo[-1].file_id

    buffer.append((kind, file_id))
    context.user_data['edit_photo_buffer'] = buffer

    n = len(buffer)
    summary = _media_icon_summary(buffer)
    hint = f"Отправьте ещё или нажмите ✅ Готово." if n < MAX_MEDIA else f"Достигнут лимит {MAX_MEDIA} файлов."

    await message.reply_text(
        f"✅ Медиа добавлено!\n\n"
        f"📎 В буфере: {summary} ({n}/{MAX_MEDIA})\n\n"
        f"{hint}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Готово", callback_data=f"pr_edit_media_done_{post_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"pr_edit_{post_id}")],
        ])
    )



async def _handle_awaiting_edit_time(message, context, db, target_chat_id):
    """Обработка нового времени публикации для запланированного поста."""
    post_id = context.user_data.get('awaiting_edit_time')

    if message.text == '/cancel':
        context.user_data.pop('awaiting_edit_time', None)
        await message.reply_text(
            "❌ Редактирование отменено.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 К посту", callback_data=f"pr_edit_{post_id}")
            ]])
        )
        return

    text = (message.text or "").strip()

    import pytz
    moscow_tz = pytz.timezone('Europe/Moscow')

    from utils.helpers import parse_flexible_datetime
    formatted_time_str = parse_flexible_datetime(text)

    if not formatted_time_str:
        await message.reply_text(
            "❌ Не удалось распознать дату/время.\n\n"
            "Пожалуйста, введите 4 или 5 чисел (день, месяц, [год], часы, минуты).\n"
            "Например: `25.03 14:30` или `25,03,26 14,30`\n\n"
            "Для отмены: /cancel",
            parse_mode='Markdown'
        )
        return

    parsed_time = datetime.strptime(formatted_time_str, '%d.%m.%Y %H:%M')

    publish_at = moscow_tz.localize(parsed_time)
    now = datetime.now(moscow_tz)

    if publish_at <= now:
        await message.reply_text("❌ Дата должна быть в будущем! Попробуйте снова.")
        return

    publish_at_str = publish_at.strftime('%Y-%m-%d %H:%M:%S')
    updated = db.update_scheduled_post(post_id, publish_at=publish_at_str)
    context.user_data.pop('awaiting_edit_time', None)

    if updated:
        await message.reply_text(
            f"✅ Время поста #{post_id} изменено!\n"
            f"📅 Новое время: {publish_at.strftime('%d.%m.%Y %H:%M')} МСК",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ К посту", callback_data=f"pr_edit_{post_id}")],
                [InlineKeyboardButton("📋 К списку", callback_data="pr_scheduled_list")]
            ])
        )
    else:
        await message.reply_text(
            f"❌ Не удалось обновить пост #{post_id}.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 К списку", callback_data="pr_scheduled_list")
            ]])
        )


async def _handle_awaiting_edit_target_manual(message, context, db, target_chat_id):
    """Обработка ручного ввода ID ветки при редактировании поста."""
    post_id = context.user_data.get('awaiting_edit_target_manual')

    if message.text == '/cancel':
        context.user_data.pop('awaiting_edit_target_manual', None)
        await message.reply_text(
            "❌ Редактирование отменено.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 К посту", callback_data=f"pr_edit_{post_id}")
            ]])
        )
        return

    text = (message.text or "").strip()
    try:
        new_thread_id = int(text)
    except ValueError:
        await message.reply_text(
            "❌ Введите числовой ID ветки.\n"
            "Например: `123`\n\n"
            "Для отмены: /cancel",
            parse_mode='Markdown'
        )
        return

    # Регистрируем тему в БД
    db.register_topic(target_chat_id, new_thread_id, f"Ветка #{new_thread_id}")

    updated = db.update_scheduled_post(post_id, thread_id=new_thread_id)
    context.user_data.pop('awaiting_edit_target_manual', None)
    context.user_data.pop('editing_post_target', None)

    thread_name = _resolve_thread_name(db, target_chat_id, new_thread_id)

    if updated:
        await message.reply_text(
            f"✅ Ветка поста #{post_id} изменена → {thread_name}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ К посту", callback_data=f"pr_edit_{post_id}")],
                [InlineKeyboardButton("📋 К списку", callback_data="pr_scheduled_list")]
            ])
        )
    else:
        await message.reply_text(
            f"❌ Не удалось обновить пост #{post_id}.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 К списку", callback_data="pr_scheduled_list")
            ]])
        )
