#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Трекер багов для веток администраторского чата.
Когда владелец пишет в ветку багов — бот создаёт карточку с кнопками:
  ✏️ Редактировать (добавить/изменить комментарий)
  🟡 В работе      (статус)
  ✅ Отработано    (статус)
"""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_CHAT_ID, BUG_THREAD_BOT, BUG_THREAD_SITE, OWNER_ID
from config.emojis import ICON_GREEN_CIRCLE, ICON_YELLOW_CIRCLE

logger = logging.getLogger(__name__)

BUG_THREADS = {BUG_THREAD_BOT, BUG_THREAD_SITE}

STATUS_NEW         = 'new'
STATUS_IN_PROGRESS = 'in_progress'
STATUS_DONE        = 'done'

_STATUS_ICON = {
    STATUS_NEW:         '',
    STATUS_IN_PROGRESS: f'{ICON_YELLOW_CIRCLE} В работе\n\n',
    STATUS_DONE:        f'{ICON_GREEN_CIRCLE} Отработано\n\n',
}


# ─────────────────────────────────────────────
#  БД
# ─────────────────────────────────────────────

def ensure_bug_tables(db) -> None:
    db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS bug_cards (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id       INTEGER NOT NULL,
            original_msg_id INTEGER NOT NULL,
            card_msg_id     INTEGER,
            status          TEXT DEFAULT 'new',
            comment         TEXT,
            original_text   TEXT,
            is_photo        INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Миграция для старых таблиц без новых колонок
    for col, definition in [
        ('original_text', 'TEXT'),
        ('is_photo',      'INTEGER DEFAULT 0'),
    ]:
        try:
            db.cursor.execute(f'ALTER TABLE bug_cards ADD COLUMN {col} {definition}')
        except Exception:
            pass
    db.conn.commit()


def get_bug_card_by_original(db, original_msg_id: int) -> dict | None:
    try:
        db.cursor.execute('SELECT * FROM bug_cards WHERE original_msg_id = ?', (original_msg_id,))
        row = db.cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def get_bug_card_by_card_msg(db, card_msg_id: int) -> dict | None:
    try:
        db.cursor.execute('SELECT * FROM bug_cards WHERE card_msg_id = ?', (card_msg_id,))
        row = db.cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def upsert_bug_card(db, original_msg_id: int, **kwargs) -> None:
    row = get_bug_card_by_original(db, original_msg_id)
    if row is None:
        cols = ['original_msg_id'] + list(kwargs.keys())
        vals = [original_msg_id] + list(kwargs.values())
        ph = ','.join('?' * len(cols))
        db.cursor.execute(
            f'INSERT INTO bug_cards ({",".join(cols)}) VALUES ({ph})', vals
        )
    else:
        sets = ', '.join(f'{k}=?' for k in kwargs)
        vals = list(kwargs.values()) + [original_msg_id]
        db.cursor.execute(
            f'UPDATE bug_cards SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE original_msg_id=?',
            vals
        )
    db.conn.commit()


# ─────────────────────────────────────────────
#  Построение карточки
# ─────────────────────────────────────────────

def _build_card_text(original_text: str, status: str, comment: str | None) -> str:
    status_line = _STATUS_ICON.get(status, '')
    text = f"{status_line}🐛 <b>Баг:</b>\n{original_text}"
    if comment:
        import html
        text += f"\n\n💬 <b>Комментарий:</b> {html.escape(comment)}"
    return text


def _build_keyboard(original_msg_id: int, status: str) -> InlineKeyboardMarkup:
    in_prog_mark = '✅ ' if status == STATUS_IN_PROGRESS else ''
    done_mark    = '✅ ' if status == STATUS_DONE else ''
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"bug_edit_{original_msg_id}")],
        [
            InlineKeyboardButton(f"{in_prog_mark}🟡 В работе",  callback_data=f"bug_status_ip_{original_msg_id}"),
            InlineKeyboardButton(f"{done_mark}✅ Отработано", callback_data=f"bug_status_done_{original_msg_id}"),
        ],
    ])


# ─────────────────────────────────────────────
#  Создание карточки при новом сообщении
# ─────────────────────────────────────────────

async def handle_bug_message(message, bot, db) -> None:
    """Вызывается когда OWNER_ID/DEVELOPER_ID пишет в ветку багов."""
    ensure_bug_tables(db)

    original_text = message.text or message.caption or ''
    original_msg_id = message.message_id
    thread_id = message.message_thread_id
    chat_id = message.chat.id

    card_text = _build_card_text(original_text or '(без текста)', STATUS_NEW, None)
    kb = _build_keyboard(original_msg_id, STATUS_NEW)

    # Определяем тип медиа
    photo_id = None
    video_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id  # лучшее качество
    elif message.video:
        video_id = message.video.file_id

    if photo_id:
        sent = await bot.send_photo(
            chat_id=chat_id,
            message_thread_id=thread_id,
            photo=photo_id,
            caption=card_text,
            parse_mode='HTML',
            reply_markup=kb,
        )
        is_photo = 1  # caption-based
    elif video_id:
        sent = await bot.send_video(
            chat_id=chat_id,
            message_thread_id=thread_id,
            video=video_id,
            caption=card_text,
            parse_mode='HTML',
            reply_markup=kb,
        )
        is_photo = 1  # видео тоже caption-based
    else:
        sent = await bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=card_text,
            parse_mode='HTML',
            reply_markup=kb,
        )
        is_photo = 0

    # Удаляем исходное сообщение — карточка его заменяет
    try:
        await bot.delete_message(chat_id=chat_id, message_id=original_msg_id)
    except Exception:
        pass

    upsert_bug_card(db, original_msg_id,
                    thread_id=thread_id,
                    card_msg_id=sent.message_id,
                    status=STATUS_NEW,
                    comment=None,
                    original_text=original_text or '(без текста)',
                    is_photo=is_photo)
    logger.info(f"Bug card created: orig={original_msg_id} card={sent.message_id} thread={thread_id}")


# ─────────────────────────────────────────────
#  Callback-обработчик
# ─────────────────────────────────────────────

async def handle_bug_callback(query, context, db) -> bool:
    """Возвращает True если callback обработан."""
    data = query.data
    if not data.startswith('bug_'):
        return False

    ensure_bug_tables(db)

    # ── Статус: В работе ──
    if data.startswith('bug_status_ip_'):
        orig_id = int(data[len('bug_status_ip_'):])
        await _set_status(query, db, orig_id, STATUS_IN_PROGRESS)
        return True

    # ── Статус: Отработано ──
    if data.startswith('bug_status_done_'):
        orig_id = int(data[len('bug_status_done_'):])
        await _set_status(query, db, orig_id, STATUS_DONE)
        return True

    # ── Редактировать (открыть FSM) ──
    if data.startswith('bug_edit_'):
        from telegram import ForceReply
        orig_id = int(data[len('bug_edit_'):])
        thread_id = query.message.message_thread_id
        chat_id = query.message.chat.id
        context.user_data['bug_edit_orig_id'] = orig_id
        context.user_data['bug_edit_card_msg_id'] = query.message.message_id
        context.user_data['bug_edit_chat_id'] = chat_id
        context.user_data['bug_awaiting_comment'] = True
        await query.answer()
        # Спрашиваем прямо в треде (ForceReply — бот ждёт ответа именно от этого юзера)
        prompt = await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text="✏️ Ответь на это сообщение с комментарием к баг-репорту:",
            reply_markup=ForceReply(selective=True),
        )
        context.user_data['bug_edit_prompt_msg_id'] = prompt.message_id
        return True

    return False


async def _set_status(query, db, original_msg_id: int, new_status: str) -> None:
    row = get_bug_card_by_original(db, original_msg_id)
    if not row:
        await query.answer("❌ Карточка не найдена.", show_alert=True)
        return

    comment       = row.get('comment')
    original_text = row.get('original_text') or '(без текста)'

    new_text = _build_card_text(original_text, new_status, comment)
    kb = _build_keyboard(original_msg_id, new_status)

    try:
        if query.message.photo or query.message.video:
            await query.edit_message_caption(new_text, parse_mode='HTML', reply_markup=kb)
        else:
            await query.edit_message_text(new_text, parse_mode='HTML', reply_markup=kb)
        upsert_bug_card(db, original_msg_id, status=new_status)
        await query.answer()
    except Exception as e:
        logger.error(f"_set_status error: {e}")
        await query.answer("❌ Ошибка обновления карточки.", show_alert=True)


async def handle_bug_comment_input(message, context, db) -> bool:
    """Вызывается когда ожидаем комментарий к баг-карточке (в треде или в ЛС)."""
    if not context.user_data.get('bug_awaiting_comment'):
        return False

    orig_id    = context.user_data.pop('bug_edit_orig_id', None)
    card_msg   = context.user_data.pop('bug_edit_card_msg_id', None)
    chat_id    = context.user_data.pop('bug_edit_chat_id', None)
    prompt_msg = context.user_data.pop('bug_edit_prompt_msg_id', None)
    context.user_data.pop('bug_awaiting_comment', None)

    if not orig_id or not card_msg or not chat_id:
        return False

    ensure_bug_tables(db)
    row = get_bug_card_by_original(db, orig_id)
    if not row:
        return True

    comment = (message.text or '').strip()
    if not comment:
        return True

    status        = row.get('status', STATUS_NEW)
    original_text = row.get('original_text') or '(без текста)'
    is_photo      = bool(row.get('is_photo'))

    new_text = _build_card_text(original_text, status, comment)
    kb = _build_keyboard(orig_id, status)

    updated = False
    try:
        if is_photo:
            await context.bot.edit_message_caption(
                chat_id=chat_id, message_id=card_msg,
                caption=new_text, parse_mode='HTML', reply_markup=kb
            )
        else:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=card_msg,
                text=new_text, parse_mode='HTML', reply_markup=kb
            )
        updated = True
    except Exception as e:
        logger.error(f"handle_bug_comment_input edit error: {e}")

    if updated:
        upsert_bug_card(db, orig_id, comment=comment)

    # Удаляем: промпт, сообщение с комментарием — через 2 сек
    import asyncio

    async def _cleanup():
        await asyncio.sleep(2)
        for msg_id in filter(None, [prompt_msg, message.message_id]):
            try:
                await context.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            except Exception:
                pass

    asyncio.create_task(_cleanup())
    return True
