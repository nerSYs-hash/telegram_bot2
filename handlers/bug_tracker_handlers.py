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
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
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

async def handle_bug_message(message, db) -> None:
    """Вызывается когда OWNER_ID пишет в ветку багов."""
    ensure_bug_tables(db)

    original_text = message.text or message.caption or '(медиа без текста)'
    original_msg_id = message.message_id
    thread_id = message.message_thread_id

    card_text = _build_card_text(original_text, STATUS_NEW, None)
    kb = _build_keyboard(original_msg_id, STATUS_NEW)

    try:
        sent = await message.reply_text(
            card_text,
            parse_mode='HTML',
            reply_markup=kb,
        )
        upsert_bug_card(db, original_msg_id,
                        thread_id=thread_id,
                        card_msg_id=sent.message_id,
                        status=STATUS_NEW,
                        comment=None)
        logger.info(f"Bug card created: orig={original_msg_id} card={sent.message_id} thread={thread_id}")
    except Exception as e:
        logger.error(f"handle_bug_message error: {e}")


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
        orig_id = int(data[len('bug_edit_'):])
        context.user_data['bug_edit_orig_id'] = orig_id
        context.user_data['bug_edit_card_msg_id'] = query.message.message_id
        context.user_data['bug_edit_chat_id'] = query.message.chat.id
        context.user_data['bug_awaiting_comment'] = True
        await query.answer()
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="✏️ Напиши комментарий — он будет добавлен в карточку баг-репорта:"
        )
        return True

    return False


async def _set_status(query, db, original_msg_id: int, new_status: str) -> None:
    row = get_bug_card_by_original(db, original_msg_id)
    if not row:
        await query.answer("❌ Карточка не найдена.", show_alert=True)
        return

    comment = row.get('comment')
    # Восстанавливаем оригинальный текст из сообщения на которое отвечала карточка
    try:
        orig_msg = query.message.reply_to_message
        original_text = (orig_msg.text or orig_msg.caption or '(медиа)') if orig_msg else '—'
    except Exception:
        original_text = '—'

    new_text = _build_card_text(original_text, new_status, comment)
    kb = _build_keyboard(original_msg_id, new_status)

    try:
        await query.edit_message_text(new_text, parse_mode='HTML', reply_markup=kb)
        upsert_bug_card(db, original_msg_id, status=new_status)
        await query.answer()
    except Exception as e:
        logger.error(f"_set_status error: {e}")
        await query.answer("❌ Ошибка обновления карточки.", show_alert=True)


async def handle_bug_comment_input(message, context, db) -> bool:
    """Вызывается из message_handler при личном сообщении если ожидаем комментарий."""
    if not context.user_data.get('bug_awaiting_comment'):
        return False

    orig_id   = context.user_data.pop('bug_edit_orig_id', None)
    card_msg  = context.user_data.pop('bug_edit_card_msg_id', None)
    chat_id   = context.user_data.pop('bug_edit_chat_id', None)
    context.user_data.pop('bug_awaiting_comment', None)

    if not orig_id or not card_msg or not chat_id:
        return False

    ensure_bug_tables(db)
    row = get_bug_card_by_original(db, orig_id)
    if not row:
        await message.reply_text("❌ Карточка не найдена.")
        return True

    comment = message.text.strip()
    status  = row.get('status', STATUS_NEW)

    # Получаем оригинальный текст через stored текст карточки или восстанавливаем
    # Сохраняем оригинальный текст в карточке при первом комментарии
    stored_orig = row.get('comment')  # это старый комментарий

    # Получаем оригинальный текст из карточки (из базы нет, придётся из API)
    try:
        orig_chat_msg = await context.bot.forward_message(
            chat_id=message.chat.id, from_chat_id=chat_id, message_id=orig_id
        )
        original_text = orig_chat_msg.text or orig_chat_msg.caption or '—'
        await context.bot.delete_message(chat_id=message.chat.id, message_id=orig_chat_msg.message_id)
    except Exception:
        original_text = '—'

    new_text = _build_card_text(original_text, status, comment)
    kb = _build_keyboard(orig_id, status)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=card_msg,
            text=new_text, parse_mode='HTML', reply_markup=kb
        )
        upsert_bug_card(db, orig_id, comment=comment)
        await message.reply_text("✅ Комментарий добавлен в карточку.")
    except Exception as e:
        logger.error(f"handle_bug_comment_input error: {e}")
        await message.reply_text("❌ Не удалось обновить карточку.")

    return True
