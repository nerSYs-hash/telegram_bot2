#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Баннеры-онбординг для активностей.

Первый вход пользователя в раздел → полноэкранный баннер + кнопка "Участвовать!".
Повторный вход → сразу меню.

Баннеры: lottery | bingo | donate | gift
"""

import logging
import os

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# ─── Конфиг баннеров ─────────────────────────────────────────────────────────

_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'banners')

BANNERS = {
    'lottery': {'image': os.path.join(_BASE, 'lottery_banner.jpg'), 'enter_cb': 'banner_enter_lottery'},
    'bingo':   {'image': os.path.join(_BASE, 'bingo_banner.jpg'),   'enter_cb': 'banner_enter_bingo'},
    'donate':  {'image': os.path.join(_BASE, 'donate_banner.jpg'),  'enter_cb': 'banner_enter_donate'},
    'gift':    {'image': os.path.join(_BASE, 'gift_banner.jpg'),    'enter_cb': 'banner_enter_gift'},
}

# enter_cb → banner name
ENTER_CB_MAP = {v['enter_cb']: k for k, v in BANNERS.items()}


# ─── DB ──────────────────────────────────────────────────────────────────────

def _ensure_table(db):
    try:
        db.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_banners_seen (
                user_id INTEGER NOT NULL,
                banner  TEXT    NOT NULL,
                seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, banner)
            )
        ''')
        db.conn.commit()
    except Exception:
        pass


def has_seen(db, user_id: int, banner: str) -> bool:
    _ensure_table(db)
    try:
        db.cursor.execute(
            'SELECT 1 FROM user_banners_seen WHERE user_id=? AND banner=?',
            (user_id, banner))
        return db.cursor.fetchone() is not None
    except Exception:
        return True  # при ошибке — пропускаем баннер, не ломаем UX


def mark_seen(db, user_id: int, banner: str):
    _ensure_table(db)
    try:
        db.cursor.execute(
            'INSERT OR IGNORE INTO user_banners_seen (user_id, banner) VALUES (?,?)',
            (user_id, banner))
        db.conn.commit()
    except Exception:
        pass


# ─── Показ баннера ────────────────────────────────────────────────────────────

async def show_banner(query, context, db, banner: str) -> bool:
    """
    Показывает баннер если пользователь ещё не видел его.
    Возвращает True если баннер показан (дальнейшую обработку нужно прервать).
    """
    user_id = query.from_user.id
    if has_seen(db, user_id, banner):
        return False

    info = BANNERS[banner]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅  Участвовать!", callback_data=info['enter_cb'])
    ]])

    # Пробуем закешированный file_id (экономим трафик при повторных показах новым юзерам)
    file_id = db.get_setting(f'banner_fid_{banner}', '')
    try:
        if file_id:
            await context.bot.send_photo(
                chat_id=query.message.chat.id,
                photo=file_id,
                reply_markup=kb,
            )
        else:
            with open(info['image'], 'rb') as f:
                sent = await context.bot.send_photo(
                    chat_id=query.message.chat.id,
                    photo=f,
                    reply_markup=kb,
                )
            if sent.photo:
                db.set_setting(f'banner_fid_{banner}', sent.photo[-1].file_id)

        # Удаляем старое сообщение с меню-кнопками
        try:
            await query.message.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"show_banner({banner}): {e}")
        return False

    return True


# ─── Обработка "Участвовать!" ─────────────────────────────────────────────────

async def enter_banner(query, context, db, app_handler) -> bool:
    """
    Вызывается когда пользователь нажимает "Участвовать!" на баннере.
    Помечает баннер как просмотренный и открывает реальное меню.
    Возвращает True если обработано.
    """
    banner = ENTER_CB_MAP.get(query.data)
    if not banner:
        return False

    await query.answer()
    mark_seen(db, query.from_user.id, banner)

    # Удаляем фото-баннер
    try:
        await query.message.delete()
    except Exception:
        pass

    # Отправляем временный плейсхолдер и редактируем его под меню
    chat_id = query.message.chat.id
    placeholder = await context.bot.send_message(chat_id=chat_id, text="⌛")

    # FakeQuery: направляет edit_message_text в placeholder
    class _FQ:
        from_user = query.from_user
        message   = placeholder

        async def edit_message_text(self_, text, **kw):
            await placeholder.edit_text(text, **kw)

        async def edit_message_caption(self_, caption, **kw):
            await placeholder.edit_text(caption, **kw)

        async def answer(self_, *a, **kw):
            pass

    fq   = _FQ()
    user = query.from_user

    if banner == 'lottery':
        await app_handler.lottery_handler.show_lottery_menu(fq, user)
    elif banner == 'bingo':
        await app_handler.bingo_handler.show_bingo_menu(fq, user)
    elif banner == 'donate':
        from handlers.donate_handlers import show_donate_menu
        await show_donate_menu(fq, user, db)
    elif banner == 'gift':
        await app_handler.gift_handler.handle_callback(fq, 'menu_monthly_gift', user, context)

    return True
