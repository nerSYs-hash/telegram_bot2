#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Трекер багов для веток администраторского чата.
FSM-мастер создания карточек: Баг / Фича / Доработка / Удаление.
Управление статусами, приоритетами, автоудаление через 72 часа.
"""

import logging
import html
import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
from config import ADMIN_CHAT_ID, BUG_THREAD_BOT, BUG_THREAD_SITE, OWNER_ID
# Если DEVELOPER_ID нет в config, можно убрать или заменить на OWNER_ID
try:
    from config import DEVELOPER_ID
except ImportError:
    DEVELOPER_ID = OWNER_ID

logger = logging.getLogger(__name__)

BUG_THREADS = {BUG_THREAD_BOT, BUG_THREAD_SITE}

# ─────────────────────────────────────────────
#  МАТРИЦА СТАТУСОВ, ТЕГОВ И ПРЕФИКСОВ
# ─────────────────────────────────────────────

STATUS_DRAFT       = 'draft'
STATUS_NEW         = 'new'
STATUS_IN_PROGRESS = 'in_progress'
STATUS_DONE        = 'done'

# Темы обращений
TOPIC_BUG = "bug"
TOPIC_NEW_FEAT = "new_feat"
TOPIC_EDIT_FEAT = "edit_feat"
TOPIC_DEL_FEAT = "del_feat"

TOPIC_LABELS = {
    TOPIC_BUG: "🐛 Баг",
    TOPIC_NEW_FEAT: "💡 Новая ФИЧА",
    TOPIC_EDIT_FEAT: "🛠 Доработка ФИЧИ",
    TOPIC_DEL_FEAT: "🗑 Удаление ФИЧИ"
}

# Префиксы для ID карточки
ID_PREFIXES = {
    TOPIC_BUG: "ID_Бага",
    TOPIC_NEW_FEAT: "ID_Новая_ФИЧА",
    TOPIC_EDIT_FEAT: "ID_Доработка_ФИЧИ",
    TOPIC_DEL_FEAT: "ID_Удаление_ФИЧИ"
}

# Матрица хештегов: {Тема: {Статус: Хештег}}
TAGS_MATRIX = {
    TOPIC_BUG: {
        STATUS_NEW: "#Баг_в_Ожидании",
        STATUS_IN_PROGRESS: "#Баг_в_Работе",
        STATUS_DONE: "#Баг_Решен"
    },
    TOPIC_NEW_FEAT: {
        STATUS_NEW: "#Новая_ФИЧА_в_Ожидании",
        STATUS_IN_PROGRESS: "#ФИЧА_в_Работе",
        STATUS_DONE: "#Новая_ФИЧА_Разработана"
    },
    TOPIC_EDIT_FEAT: {
        STATUS_NEW: "#Доработка_ФИЧИ_в_Ожидании",
        STATUS_IN_PROGRESS: "#Доработка_ФИЧИ_в_Работе",
        STATUS_DONE: "#ФИЧА_Доработана"
    },
    TOPIC_DEL_FEAT: {
        STATUS_NEW: "#Удаление_ФИЧИ_в_Ожидании",
        STATUS_IN_PROGRESS: "#Удаление_ФИЧИ_в_Работе",
        STATUS_DONE: "#ФИЧА_Удалена"
    }
}

# Приоритеты
PRIORITY_LOW = "low"
PRIORITY_HIGH = "high"
PRIORITY_CRITICAL = "critical"

PRIORITY_LABELS = {
    PRIORITY_LOW: "❗️ Не срочно",
    PRIORITY_HIGH: "⚡️ Срочно",
    PRIORITY_CRITICAL: "☄️ Критическая Ошибка"
}


# ─────────────────────────────────────────────
#  БД (С НОВЫМИ КОЛОНКАМИ)
# ─────────────────────────────────────────────

def ensure_bug_tables(db) -> None:
    db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS bug_cards (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id       INTEGER NOT NULL,
            original_msg_id INTEGER NOT NULL,
            card_msg_id     INTEGER,
            status          TEXT DEFAULT 'draft',
            topic_type      TEXT,
            priority        TEXT,
            reporter_id     INTEGER,
            reporter_uname  TEXT,
            comment         TEXT,
            original_text   TEXT,
            is_photo        INTEGER DEFAULT 0,
            resolved_at     TIMESTAMP,
            last_comment_at TIMESTAMP,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Авто-миграция для старых таблиц (если колонки не было - она добавится)
    new_columns =[
        ('topic_type', 'TEXT'),
        ('priority', 'TEXT'),
        ('reporter_id', 'INTEGER'),
        ('reporter_uname', 'TEXT'),
        ('resolved_at', 'TIMESTAMP'),
        ('last_comment_at', 'TIMESTAMP'),
        ('original_text', 'TEXT'),
        ('is_photo', 'INTEGER DEFAULT 0'),
    ]
    for col, definition in new_columns:
        try:
            db.cursor.execute(f'ALTER TABLE bug_cards ADD COLUMN {col} {definition}')
        except Exception:
            pass # Колонка уже существует
    db.conn.commit()


def get_bug_card_by_original(db, original_msg_id: int) -> dict | None:
    try:
        db.cursor.execute('SELECT * FROM bug_cards WHERE original_msg_id = ?', (original_msg_id,))
        row = db.cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    
    # ─────────────────────────────────────────────
#  БД (Хелперы - Продолжение)
# ─────────────────────────────────────────────

def get_bug_card_by_card_msg(db, card_msg_id: int) -> dict | None:
    try:
        db.cursor.execute('SELECT * FROM bug_cards WHERE card_msg_id = ?', (card_msg_id,))
        row = db.cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        return None

def upsert_bug_card(db, original_msg_id: int, **kwargs) -> None:
    # Авто-миграция для сохранения медиа (т.к. исходное сообщение удаляется)
    try:
        db.cursor.execute('ALTER TABLE bug_cards ADD COLUMN media_file_id TEXT')
        db.conn.commit()
    except Exception:
        pass # Если колонка уже есть - пропускаем

    row = get_bug_card_by_original(db, original_msg_id)
    if row is None:
        cols = ['original_msg_id'] + list(kwargs.keys())
        vals = [original_msg_id] + list(kwargs.values())
        ph = ','.join('?' * len(cols))
        db.cursor.execute(
            f'INSERT INTO bug_cards ({",".join(cols)}) VALUES ({ph})', vals
        )
    else:
        sets = ', '.join(f'{k}=?' for k in kwargs.keys())
        vals = list(kwargs.values()) + [original_msg_id]
        db.cursor.execute(
            f'UPDATE bug_cards SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE original_msg_id=?',
            vals
        )
    db.conn.commit()


# ─────────────────────────────────────────────
#  ШАГ 1: Перехват сообщения и выбор ТЕМЫ
# ─────────────────────────────────────────────

async def handle_bug_message(message, context, db) -> None:
    """Перехватывает сообщение в ветке багов, удаляет его и запускает Мастер."""
    ensure_bug_tables(db)

    original_text = message.text or message.caption or ''
    original_msg_id = message.message_id
    thread_id = message.message_thread_id
    chat_id = message.chat.id
    
    reporter_id = message.from_user.id
    reporter_uname = message.from_user.username or message.from_user.first_name

    # Сохраняем ID медиа, так как само сообщение мы удалим!
    is_photo = 0
    media_file_id = None
    if message.photo:
        media_file_id = message.photo[-1].file_id # берем в лучшем качестве
        is_photo = 1
    elif message.video:
        media_file_id = message.video.file_id
        is_photo = 1

    # Инлайн-меню выбора Темы
    keyboard =[
        [InlineKeyboardButton(TOPIC_LABELS[TOPIC_BUG], callback_data=f"bug_topic_{TOPIC_BUG}_{original_msg_id}")],
        [InlineKeyboardButton(TOPIC_LABELS[TOPIC_NEW_FEAT], callback_data=f"bug_topic_{TOPIC_NEW_FEAT}_{original_msg_id}")],
        [InlineKeyboardButton(TOPIC_LABELS[TOPIC_EDIT_FEAT], callback_data=f"bug_topic_{TOPIC_EDIT_FEAT}_{original_msg_id}")],
        [InlineKeyboardButton(TOPIC_LABELS[TOPIC_DEL_FEAT], callback_data=f"bug_topic_{TOPIC_DEL_FEAT}_{original_msg_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"bug_cancel_{original_msg_id}")]
    ]
    
    # Отправляем меню Мастера создания
    sent = await context.bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text="🗂 <b>К какой категории относится ваше обращение?</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Удаляем исходное сообщение юзера, чтобы не мусорить в ветке!
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить исходное сообщение бага: {e}")

    # Сохраняем черновик
    upsert_bug_card(db, original_msg_id,
                    thread_id=thread_id,
                    card_msg_id=sent.message_id,
                    status=STATUS_DRAFT,
                    reporter_id=reporter_id,
                    reporter_uname=reporter_uname,
                    original_text=original_text or '(без текста)',
                    media_file_id=media_file_id,
                    is_photo=is_photo)
    
    logger.info(f"Bug DRAFT created: orig={original_msg_id}")


# ─────────────────────────────────────────────
#  ШАГ 2: Выбор ПРИОРИТЕТА
# ─────────────────────────────────────────────

async def handle_topic_selection(query, data: str, db) -> bool:
    """Обрабатывает нажатие на кнопку Темы и выдает кнопки Приоритета"""
    # Парсим data (например: bug_topic_new_feat_12345)
    prefix = "bug_topic_"
    remainder = data[len(prefix):]
    
    # Отрезаем ID с конца (так как тема может содержать подчеркивания, типа new_feat)
    *topic_parts, orig_id_str = remainder.split('_')
    topic_type = '_'.join(topic_parts)
    orig_id = int(orig_id_str)

    # Сохраняем выбранную тему в БД
    upsert_bug_card(db, orig_id, topic_type=topic_type)

    # Меню Приоритета
    keyboard = [
        [InlineKeyboardButton(PRIORITY_LABELS[PRIORITY_CRITICAL], callback_data=f"bug_pri_{PRIORITY_CRITICAL}_{orig_id}")],
        [InlineKeyboardButton(PRIORITY_LABELS[PRIORITY_HIGH], callback_data=f"bug_pri_{PRIORITY_HIGH}_{orig_id}")],[InlineKeyboardButton(PRIORITY_LABELS[PRIORITY_LOW], callback_data=f"bug_pri_{PRIORITY_LOW}_{orig_id}")],[InlineKeyboardButton("🔙 Назад (Изменить тему)", callback_data=f"bug_cancel_{orig_id}")] # Отменяет и сносит черновик
    ]

    await query.edit_message_text(
        f"✅ Тема: <b>{TOPIC_LABELS.get(topic_type, 'Неизвестно')}</b>\n\n"
        f"⚡️ <b>Оцените срочность:</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return True

# ─────────────────────────────────────────────
#  ШАГ 3: ПРЕДПРОСМОТР КАРТОЧКИ
# ─────────────────────────────────────────────
def _parse_comments(comment_data: str) -> list:
    """Безопасно распаковывает JSON со списком комментариев из БД."""
    if not comment_data:
        return []
    try:
        return json.loads(comment_data)
    except Exception:
        return []

def _build_preview_text(row: dict) -> str:
    """Формирует красивый текст карточки на основе данных из БД"""
    import html
    
    topic = row.get('topic_type', TOPIC_BUG)
    priority = row.get('priority', PRIORITY_LOW)
    status = row.get('status', STATUS_NEW)
    reporter = row.get('reporter_uname', 'Unknown')
    text = row.get('original_text', '(без текста)')
    
    # 1. Получаем хештег
    tag = TAGS_MATRIX.get(topic, {}).get(status, "#В_Ожидании")
    
    # 2. Получаем префикс ID
    id_prefix = ID_PREFIXES.get(topic, "ID")
    card_id = row['id'] # Берем ID из базы данных!
    
    # 3. Приоритет и тег Nersys
    priority_str = PRIORITY_LABELS.get(priority, "Неизвестно")
    if priority == PRIORITY_CRITICAL:
        # Пинг разработчика (берем из конфига)
        try:
            from config import DEVELOPER_ID
            priority_str += f" (<a href='tg://user?id={DEVELOPER_ID}'>Разработчик</a>, обрати внимание!)"
        except ImportError:
            priority_str += " (Разработчик, обрати внимание!)"
            
    # Собираем всё вместе
    preview = (
        f"<b>{id_prefix}: #{card_id}</b>\n"
        f"{tag}\n"
        f"<b>Приоритет:</b> {priority_str}\n"
        f"<b>От кого:</b> @{html.escape(reporter)}\n\n"
        f"<b>Текст:</b>\n{html.escape(text)}"
    )
    
    # Если есть комментарии (понадобится на этапе "В работе")
    comments = _parse_comments(row.get('comment', ''))
    if comments:
        preview += "\n\n💬 <b>Комментарии:</b>"
        for i, c in enumerate(comments, 1):
            preview += f"\n{i}. {c}"
            
    # Если карточка была возвращена в работу
    resolved_at = row.get('resolved_at')
    if status == STATUS_IN_PROGRESS and resolved_at:
        try:
            # Форматируем дату, если она есть
            date_obj = datetime.strptime(resolved_at[:19], '%Y-%m-%d %H:%M:%S')
            date_str = date_obj.strftime('%d.%m.%Y %H:%M')
            preview += f"\n\n⚠️ <i>Возвращено в работу. Прошлое решение: {date_str}</i>"
        except Exception:
            pass

    return preview

async def show_card_preview(context, db, orig_id: int, query_to_delete=None) -> None:
    """Удаляет старое сообщение (меню) и присылает полноценный предпросмотр (с фото, если есть)"""
    row = get_bug_card_by_original(db, orig_id)
    if not row:
        return

    chat_id = context.bot_data.get('target_chat_id') or ADMIN_CHAT_ID # или берем из query
    thread_id = row['thread_id']
    old_card_msg_id = row['card_msg_id']
    
    # 1. Если передали query, берем chat_id оттуда
    if query_to_delete:
        chat_id = query_to_delete.message.chat.id
        # Пытаемся удалить старое меню
        try:
            await query_to_delete.message.delete()
        except Exception:
            pass
    else:
        # Если query нет (вызов после редактирования текста)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=old_card_msg_id)
        except Exception:
            pass

    # 2. Собираем текст и кнопки предпросмотра
    text = _build_preview_text(row)
    
    keyboard = [[InlineKeyboardButton("✅ Отправить разработчикам", callback_data=f"bug_publish_{orig_id}")],[InlineKeyboardButton("✏️ Редактировать", callback_data=f"bug_edit_{orig_id}"),
         InlineKeyboardButton("❌ Отмена", callback_data=f"bug_cancel_{orig_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 3. Отправляем НОВОЕ сообщение с медиа или без
    media_file_id = row.get('media_file_id')
    is_photo = row.get('is_photo', 0)
    
    try:
        if media_file_id and is_photo:
            # Пытаемся отправить как фото
            sent = await context.bot.send_photo(
                chat_id=chat_id, message_thread_id=thread_id,
                photo=media_file_id, caption=text, parse_mode='HTML', reply_markup=reply_markup
            )
        else:
            # Отправляем как текст
            sent = await context.bot.send_message(
                chat_id=chat_id, message_thread_id=thread_id,
                text=text, parse_mode='HTML', reply_markup=reply_markup
            )
            
        # 4. Обновляем card_msg_id в БД!
        upsert_bug_card(db, orig_id, card_msg_id=sent.message_id)
        
    except Exception as e:
        logger.error(f"Error showing preview: {e}")


async def handle_priority_selection(query, data: str, context, db) -> bool:
    """Обрабатывает нажатие на Приоритет и запускает Предпросмотр"""
    prefix = "bug_pri_"
    remainder = data[len(prefix):]
    
    *pri_parts, orig_id_str = remainder.split('_')
    priority = '_'.join(pri_parts)
    orig_id = int(orig_id_str)

    # Сохраняем приоритет
    upsert_bug_card(db, orig_id, priority=priority)

    # Запускаем сборку и отправку предпросмотра
    await show_card_preview(context, db, orig_id, query_to_delete=query)
    return True

# ─────────────────────────────────────────────
#  ШАГ 4: ОТМЕНА И УДАЛЕНИЕ (Черновики и готовые)
# ─────────────────────────────────────────────

async def handle_cancel_card(query, data: str, context, db) -> bool:
    """Кнопка 'Отмена' или 'Удалить'. Сносит карточку из БД и удаляет сообщение."""
    orig_id = int(data.replace("bug_cancel_", ""))
    
    # 1. Проверяем, можно ли удалять (Защита от удаления Критикалов)
    row = get_bug_card_by_original(db, orig_id)
    if row:
        # Запрещаем удаление, если это Критикал (независимо от статуса)
        if row.get('priority') == PRIORITY_CRITICAL:
            await query.answer("☄️ Критические ошибки удалять нельзя вообще!", show_alert=True)
            return True

    try:
        await query.message.delete()
    except Exception:
        pass
        
    try:
        # Удаляем из БД (каскадное удаление черновика или бага)
        db.cursor.execute('DELETE FROM bug_cards WHERE original_msg_id = ?', (orig_id,))
        db.conn.commit()
    except Exception as e:
        logger.error(f"Failed to delete bug card from DB: {e}")
        
    await query.answer("🗑 Карточка удалена", show_alert=False)
    return True

# ─────────────────────────────────────────────
#  ШАГ 5: ПУБЛИКАЦИЯ (Перевод из Draft в New)
# ─────────────────────────────────────────────

def _build_published_keyboard(orig_id: int, original_text: str, status: str) -> InlineKeyboardMarkup:
    """Клавиатура для УЖЕ ОПУБЛИКОВАННОЙ карточки (9 кнопок)"""
    # 1 ряд: Редактировать | (Удалить) | Комментировать
    top_row =[InlineKeyboardButton("✏️ Редактировать", callback_data=f"bug_edit_{orig_id}")]
    
    # Кнопка УДАЛИТЬ появляется только если текст < 15 символов
    if len(original_text) < 15:
        top_row.append(InlineKeyboardButton("🗑 Удалить", callback_data=f"bug_cancel_{orig_id}"))
        
    top_row.append(InlineKeyboardButton("💬 Комментировать", callback_data=f"bug_comment_{orig_id}"))
    
    # 2 ряд: Статусы
    bottom_row =[]
    if status == STATUS_NEW:
        bottom_row =[
            InlineKeyboardButton("🟡 В работе", callback_data=f"bug_status_ip_{orig_id}"),
            InlineKeyboardButton("✅ Отработано", callback_data=f"bug_status_done_{orig_id}")
        ]
    elif status == STATUS_IN_PROGRESS:
        bottom_row =[
            InlineKeyboardButton("✏️ В работе", callback_data="bug_noop"), # Заглушка
            InlineKeyboardButton("✅ Отработано", callback_data=f"bug_status_done_{orig_id}")
        ]
    elif status == STATUS_DONE:
        bottom_row =[
            InlineKeyboardButton("♻️ Вернуть в работу", callback_data=f"bug_status_ip_{orig_id}"),
            InlineKeyboardButton("✅ Отработано", callback_data="bug_noop") # Заглушка
        ]
        
    return InlineKeyboardMarkup([top_row, bottom_row])

async def handle_publish_card(query, data: str, db) -> bool:
    """Переводит карточку из 'draft' в 'new' и меняет клавиатуру на рабочую"""
    orig_id = int(data.replace("bug_publish_", ""))
    
    upsert_bug_card(db, orig_id, status=STATUS_NEW)
    
    row = get_bug_card_by_original(db, orig_id)
    if not row:
        return True
        
    text = _build_preview_text(row)
    kb = _build_published_keyboard(orig_id, row.get('original_text', ''), STATUS_NEW)
    
    try:
        # Пытаемся отредактировать предпросмотр (если медиа не менялось, это сработает)
        if query.message.photo or query.message.video:
            await query.edit_message_caption(caption=text, parse_mode='HTML', reply_markup=kb)
        else:
            await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=kb)
        await query.answer("🚀 Опубликовано!")
    except Exception as e:
        logger.error(f"Error publishing card: {e}")
        await query.answer("❌ Ошибка при публикации", show_alert=True)
        
    return True

# ─────────────────────────────────────────────
#  ШАГ 4: ЦЕНТРАЛЬНЫЙ ОБРАБОТЧИК КНОПОК
# ─────────────────────────────────────────────

async def handle_bug_callback(query, context, db) -> bool:
    """Центральный перехватчик всех кнопок баг-трекера."""
    data = query.data
    if not data.startswith('bug_'):
        return False

    ensure_bug_tables(db)

    # Заглушка для пустых кнопок (когда они выполняют роль индикатора, например "✏️ В работе")
    if data == "bug_noop":
        await query.answer()
        return True

    # 1. Выбор ТЕМЫ (Draft)
    if data.startswith("bug_topic_"):
        return await handle_topic_selection(query, data, db)

    # 2. Выбор ПРИОРИТЕТА (Draft)
    if data.startswith("bug_pri_"):
        return await handle_priority_selection(query, data, context, db)

    # 3. ОТМЕНА или УДАЛЕНИЕ
    if data.startswith("bug_cancel_"):
        return await handle_cancel_card(query, data, context, db)

    # 4. ПУБЛИКАЦИЯ
    if data.startswith("bug_publish_"):
        return await handle_publish_card(query, data, db)

    # 5. СТАТУС: В РАБОТЕ
    if data.startswith('bug_status_ip_'):
        orig_id = int(data.replace("bug_status_ip_", ""))
        await _set_status(query, context, db, orig_id, STATUS_IN_PROGRESS)
        return True

    # 6. СТАТУС: ОТРАБОТАНО
    if data.startswith('bug_status_done_'):
        orig_id = int(data.replace("bug_status_done_", ""))
        await _set_status(query, context, db, orig_id, STATUS_DONE)
        return True

    # 7. РЕДАКТИРОВАТЬ ТЕКСТ (Запрос реплая)
    if data.startswith('bug_edit_'):
        from telegram import ForceReply
        orig_id = int(data.replace("bug_edit_", ""))
        thread_id = query.message.message_thread_id
        chat_id = query.message.chat.id
        
        # Сохраняем в кэш, что мы ждем именно РЕДАКТИРОВАНИЕ
        context.user_data['bug_edit_orig_id'] = orig_id
        context.user_data['bug_action_type'] = 'edit_text' # 'edit_text' или 'comment'
        
        await query.answer()
        prompt = await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text="✏️ <b>Отправьте новый текст или медиафайл ответом (Reply) на это сообщение:</b>\n"
                 "<i>(Старое тело карточки будет полностью заменено)</i>",
            parse_mode='HTML',
            reply_markup=ForceReply(selective=True),
        )
        context.user_data['bug_edit_prompt_msg_id'] = prompt.message_id
        return True

    # 8. КОММЕНТИРОВАТЬ (Запрос реплая)
    if data.startswith('bug_comment_'):
        from telegram import ForceReply
        orig_id = int(data.replace("bug_comment_", ""))
        thread_id = query.message.message_thread_id
        chat_id = query.message.chat.id
        
        context.user_data['bug_edit_orig_id'] = orig_id
        context.user_data['bug_action_type'] = 'comment'
        
        await query.answer()
        prompt = await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text="💬 <b>Напишите ваш комментарий ответом (Reply) на это сообщение:</b>\n"
                 "<i>(Он добавится в самый конец карточки)</i>",
            parse_mode='HTML',
            reply_markup=ForceReply(selective=True),
        )
        context.user_data['bug_edit_prompt_msg_id'] = prompt.message_id
        return True

    return False


# ─────────────────────────────────────────────
#  ШАГ 5: ЛОГИКА СТАТУСОВ И ТАЙМЕРОВ УДАЛЕНИЯ
# ─────────────────────────────────────────────

async def _set_status(query, context, db, original_msg_id: int, new_status: str) -> None:
    row = get_bug_card_by_original(db, original_msg_id)
    if not row:
        await query.answer("❌ Карточка не найдена.", show_alert=True)
        return

    # Если возвращают в работу, запоминаем дату прошлого закрытия
    if new_status == STATUS_IN_PROGRESS and row['status'] == STATUS_DONE:
        import datetime as dt
        resolved_at = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        upsert_bug_card(db, original_msg_id, resolved_at=resolved_at)

    upsert_bug_card(db, original_msg_id, status=new_status)
    row = get_bug_card_by_original(db, original_msg_id) # обновляем данные

    text = _build_preview_text(row)
    kb = _build_published_keyboard(original_msg_id, row.get('original_text', ''), new_status)

    try:
        if query.message.photo or query.message.video:
            await query.edit_message_caption(caption=text, parse_mode='HTML', reply_markup=kb)
        else:
            await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=kb)
        await query.answer()
    except Exception as e:
        logger.error(f"_set_status error: {e}")
        await query.answer("❌ Ошибка обновления.", show_alert=True)

    # Управление таймером автоудаления (72 часа)
    job_name = f"delete_bug_{original_msg_id}"
    
    # 1. Если статус стал "Отработано" и это НЕ Критикал -> запускаем таймер
    if new_status == STATUS_DONE and row.get('priority') != PRIORITY_CRITICAL:
        # Проверяем, нет ли уже такого таймера
        existing_jobs = context.job_queue.get_jobs_by_name(job_name)
        if not existing_jobs:
            context.job_queue.run_once(
                _auto_delete_bug_job,
                when=72 * 3600, # 72 часа в секундах
                data={'orig_id': original_msg_id, 'chat_id': query.message.chat.id},
                name=job_name
            )
            logger.info(f"Timer set for 72h auto-delete bug #{original_msg_id}")
            
    # 2. Если статус вернули "В работу" -> отменяем таймер (если он был)
    elif new_status == STATUS_IN_PROGRESS:
        existing_jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in existing_jobs:
            job.schedule_removal()
            logger.info(f"Timer for auto-delete bug #{original_msg_id} cancelled.")


async def _auto_delete_bug_job(context):
    """Фоновая задача. Удаляет карточку через 72 часа."""
    job_data = context.job.data
    orig_id = job_data['orig_id']
    chat_id = job_data['chat_id']
    
    db = context.application.bot_data.get('db')
    if not db:
        return
        
    row = get_bug_card_by_original(db, orig_id)
    if not row or row.get('status') != STATUS_DONE:
        return # Если кто-то успел поменять статус, пока таймер тикал, не удаляем
        
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=row['card_msg_id'])
        db.cursor.execute('DELETE FROM bug_cards WHERE original_msg_id = ?', (orig_id,))
        db.conn.commit()
        logger.info(f"Bug #{orig_id} auto-deleted after 72h.")
    except Exception as e:
        logger.error(f"Failed auto-delete bug #{orig_id}: {e}")


# ─────────────────────────────────────────────
#  ШАГ 6: ОБРАБОТКА ВВОДА ОТ АДМИНА (ForceReply)
# ─────────────────────────────────────────────

async def handle_bug_comment_input(message, context, db) -> bool:
    """Вызывается из message_handler.py, если это ответ на ForceReply бота."""
    if not context.user_data.get('bug_action_type'):
        return False

    orig_id = context.user_data.pop('bug_edit_orig_id', None)
    action_type = context.user_data.pop('bug_action_type', None)
    prompt_msg = context.user_data.pop('bug_edit_prompt_msg_id', None)

    ensure_bug_tables(db)
    row = get_bug_card_by_original(db, orig_id)
    
    # 0. ЗАЩИТА ОТ СТАРЫХ КАРТОЧЕК (Которых нет в новой БД)
    if not row:
        sent = await context.bot.send_message(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            text="❌ <b>Ошибка:</b> Эта карточка создана ДО обновления системы.\nЕё нет в базе данных, поэтому изменить её нельзя.",
            parse_mode="HTML"
        )
        # Удаляем это уведомление через 5 секунд, чтобы не мусорить в чате
        import asyncio
        async def _del_warning():
            await asyncio.sleep(5)
            try: await context.bot.delete_message(chat_id=message.chat.id, message_id=sent.message_id)
            except: pass
        asyncio.create_task(_del_warning())
        
    else:
        text = message.text or message.caption or ''
        author = message.from_user.username or message.from_user.first_name

        # 1. ОБРАБОТКА РЕДАКТИРОВАНИЯ (Заменяем текст/медиа и обновляем)
        if action_type == 'edit_text':
            is_photo = 0
            media_file_id = None
            if message.photo:
                media_file_id = message.photo[-1].file_id
                is_photo = 1
            elif message.video:
                media_file_id = message.video.file_id
                is_photo = 1
                
            upsert_bug_card(db, orig_id, original_text=text, media_file_id=media_file_id, is_photo=is_photo)
            updated_row = get_bug_card_by_original(db, orig_id)
            
            # Если это только черновик - пересобираем превью
            if updated_row['status'] == STATUS_DRAFT:
                await show_card_preview(context, db, orig_id)
            # Если карточка уже в работе - просто аккуратно меняем текст
            else:
                new_text = _build_preview_text(updated_row)
                kb = _build_published_keyboard(orig_id, updated_row.get('original_text', ''), updated_row['status'])
                try:
                    if updated_row.get('is_photo') and updated_row.get('media_file_id'):
                        await context.bot.edit_message_caption(
                            chat_id=message.chat.id, message_id=updated_row['card_msg_id'],
                            caption=new_text, parse_mode='HTML', reply_markup=kb
                        )
                    else:
                        await context.bot.edit_message_text(
                            chat_id=message.chat.id, message_id=updated_row['card_msg_id'],
                            text=new_text, parse_mode='HTML', reply_markup=kb
                        )
                except Exception as e:
                    logger.error(f"Error updating edited text: {e}")

        # 2. ОБРАБОТКА КОММЕНТАРИЯ (Добавляем в конец)
        elif action_type == 'comment':
            if text:
                import json as _json
                existing = row.get('comment') or ''
                existing_comments = _parse_comments(existing) if existing else []
                
                new_comment = f"@{author}: \"{text}\""
                existing_comments.append(new_comment)
                
                from datetime import datetime
                comment_data = _json.dumps(existing_comments, ensure_ascii=False)
                upsert_bug_card(db, orig_id, comment=comment_data, last_comment_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                
                existing_jobs = context.job_queue.get_jobs_by_name(f"delete_bug_{orig_id}")
                for job in existing_jobs:
                    job.schedule_removal()
                
                updated_row = get_bug_card_by_original(db, orig_id)
                new_text = _build_preview_text(updated_row)
                kb = _build_published_keyboard(orig_id, updated_row.get('original_text', ''), updated_row['status'])
                
                try:
                    if row.get('is_photo') and row.get('media_file_id'):
                        await context.bot.edit_message_caption(
                            chat_id=message.chat.id, message_id=row['card_msg_id'],
                            caption=new_text, parse_mode='HTML', reply_markup=kb
                        )
                    else:
                        await context.bot.edit_message_text(
                            chat_id=message.chat.id, message_id=row['card_msg_id'],
                            text=new_text, parse_mode='HTML', reply_markup=kb
                        )
                except Exception as e:
                    logger.error(f"Error updating comment: {e}")

    # 3. УБОРКА (Удаляем prompt от бота и сообщение админа с текстом)
    import asyncio
    async def _cleanup():
        await asyncio.sleep(1)
        for msg_id in filter(None, [prompt_msg, message.message_id]):
            try:
                await context.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            except Exception:
                pass

    asyncio.create_task(_cleanup())
    return True