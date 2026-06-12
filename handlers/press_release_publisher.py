#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Публикация пресс-релизов из планировщика (V1.16.14).

Поддерживает:
  • Multi-target (один пост → много чатов/топиков)
  • bold_header (первая строка <b>)
  • signature (добавление кастомной подписи)
  • inline_keyboard (URL и callback кнопки)
  • settings: pin, disable_preview, disable_notify, content_protection
  • delete_after_publish (отложенное удаление через JobQueue)
  • pre_publish_reminder (за N минут — DM автору)
  • Сохранение published_message_ids для последующего удаления
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputMediaVideo,
)

logger = logging.getLogger(__name__)

MSG_LIMIT = 4096
CAPTION_LIMIT = 1024


# ────────────────────────────────────────────────────────────────────
# Парсинг и сборка контента
# ────────────────────────────────────────────────────────────────────

def _parse_media(photo_file_id: str) -> list:
    """Формат: 'photo:VAL|video:VAL|animation:VAL|...'
       VAL — file_id, либо локальный путь (/media/...), либо HTTP URL."""
    if not photo_file_id:
        return []
    items = []
    for part in photo_file_id.split('|'):
        part = part.strip()
        if not part:
            continue
        if part.startswith('video:'):
            items.append(('video', part[6:]))
        elif part.startswith('animation:'):
            items.append(('animation', part[10:]))
        elif part.startswith('photo:'):
            items.append(('photo', part[6:]))
        else:
            items.append(('photo', part))
    return items


def _resolve_media_input(value: str):
    """Возвращает file_id-строку или открытый файл для отправки в Telegram.
       Для /media/... ищем файл в Admin_SITE/media_uploads/."""
    import os
    if not value:
        return value
    # HTTP URL — Telegram его сам скачает
    if value.startswith('http://') or value.startswith('https://'):
        return value
    # Локальный URL /media/<filename>
    if value.startswith('/media/'):
        fname = value[len('/media/'):]
        # Корень проекта
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, 'Admin_SITE', 'media_uploads', fname)
        if os.path.exists(path):
            return open(path, 'rb')
        logger.warning(f"media file not found: {path}")
        raise ValueError(f"Локальный медиа-файл не найден: {fname}")
    # Абсолютный путь
    if value.startswith('/') or (len(value) > 1 and value[1] == ':'):
        if os.path.exists(value):
            return open(value, 'rb')
        raise ValueError(f"Файл не найден по пути: {value}")
    # Иначе — file_id
    return value


def _sanitize_html_for_telegram(html: str) -> str:
    """Чистит HTML из WYSIWYG-редактора браузера под parse_mode=HTML Telegram.

    Telegram поддерживает только: b/strong i/em u/ins s/strike/del code pre
    a tg-spoiler blockquote tg-emoji span(class=tg-spoiler).
    Все остальные теги (br, div, p, span без class, font, h1..) — конвертируем в \\n или удаляем.
    """
    import re
    if not html:
        return ''
    s = html
    # HTML-комментарии (например наш HEADER-заглушка) — выкидываем
    s = re.sub(r'<!--.*?-->', '', s, flags=re.DOTALL)
    # <br> и <br/> → перенос строки
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.IGNORECASE)
    # </p>, </div> → перенос. Открывающие <p>, <div> вырезаем.
    s = re.sub(r'</(p|div)\s*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<(p|div)(\s[^>]*)?>', '', s, flags=re.IGNORECASE)
    # <span> и font без полезных атрибутов — снимаем теги, оставляем содержимое
    s = re.sub(r'</?(span|font|h\d|ul|ol|li)(\s[^>]*)?>', '', s, flags=re.IGNORECASE)
    # &nbsp; → пробел
    s = s.replace('&nbsp;', ' ')
    # Лишние пустые строки (3+) → 2
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def _build_text(post: dict, signature_default: str = '') -> str:
    """Применяет bold_header, добавляет signature, санитизирует HTML."""
    text = _sanitize_html_for_telegram(post.get('text') or '')
    bold_header = post.get('bold_header', 1)
    if bold_header and text:
        lines = text.split('\n', 1)
        if len(lines) > 1 and lines[0].strip():
            # Не оборачиваем дважды если уже <b>
            if not lines[0].lstrip().lower().startswith('<b>'):
                text = f"<b>{lines[0]}</b>\n{lines[1]}"
        else:
            if not text.lstrip().lower().startswith('<b>'):
                text = f"<b>{text}</b>"
    if post.get('add_signature', 1):
        sig = _sanitize_html_for_telegram(post.get('signature') or signature_default or '')
        if sig:
            text = f"{text}\n\n{sig}" if text else sig
    return text


def _build_keyboard(post: dict) -> Optional[InlineKeyboardMarkup]:
    """Inline-keyboard из поля inline_keyboard (JSON list of rows of buttons)."""
    raw = post.get('inline_keyboard')
    if not raw:
        return None
    try:
        rows = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return None
    if not rows:
        return None
    kb = []
    for row in rows:
        kb_row = []
        for btn in row:
            label = btn.get('text', '').strip()
            if not label:
                continue
            btype = btn.get('type', 'url')
            value = btn.get('value', '').strip()
            if btype == 'url' and value:
                kb_row.append(InlineKeyboardButton(label, url=value))
            elif btype == 'callback' and value:
                kb_row.append(InlineKeyboardButton(label, callback_data=f"pr_act_{value}"))
        if kb_row:
            kb.append(kb_row)
    return InlineKeyboardMarkup(kb) if kb else None


def _settings(post: dict) -> dict:
    raw = post.get('settings_json')
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) or {}
    except (ValueError, TypeError):
        return {}


# ────────────────────────────────────────────────────────────────────
# Отправка длинного текста с разбиением
# ────────────────────────────────────────────────────────────────────

async def _send_long(bot, chat_id: int, text: str, thread_id: int = None,
                     reply_markup=None, **kwargs) -> list:
    """Возвращает list message_id всех отправленных частей."""
    base = {'chat_id': chat_id, 'parse_mode': 'HTML'}
    if thread_id:
        base['message_thread_id'] = thread_id
    base.update(kwargs)
    msg_ids = []
    remaining = text or ''
    while remaining:
        if len(remaining) <= MSG_LIMIT:
            m = await bot.send_message(text=remaining, reply_markup=reply_markup, **base)
            msg_ids.append(m.message_id)
            break
        cut = remaining.rfind('\n', 0, MSG_LIMIT)
        if cut == -1:
            cut = MSG_LIMIT
        m = await bot.send_message(text=remaining[:cut], **base)
        msg_ids.append(m.message_id)
        remaining = remaining[cut:].lstrip('\n')
    return msg_ids


async def _send_to_target(bot, chat_id: int, thread_id: Optional[int],
                          text: str, media_list: list, reply_markup,
                          settings: dict) -> list:
    """Возвращает список message_id всех частей."""
    extra = {}
    if settings.get('disable_notify'):
        extra['disable_notification'] = True
    if settings.get('content_protection'):
        extra['protect_content'] = True

    msg_ids = []

    # Без медиа — обычный текст (с разбиением)
    if not media_list:
        text_extra = dict(extra)
        if settings.get('disable_preview'):
            text_extra['disable_web_page_preview'] = True
        msg_ids = await _send_long(bot, chat_id, text, thread_id=thread_id,
                                   reply_markup=reply_markup, **text_extra)

    elif len(media_list) == 1:
        kind, fid = media_list[0]
        media_input = _resolve_media_input(fid)
        send_kw = {'chat_id': chat_id, 'parse_mode': 'HTML', **extra}
        if thread_id:
            send_kw['message_thread_id'] = thread_id
        if len(text) <= CAPTION_LIMIT:
            send_kw['caption'] = text
            send_kw['reply_markup'] = reply_markup
            if kind == 'video':
                m = await bot.send_video(video=media_input, **send_kw)
            elif kind == 'animation':
                m = await bot.send_animation(animation=media_input, **send_kw)
            else:
                m = await bot.send_photo(photo=media_input, **send_kw)
            msg_ids.append(m.message_id)
        else:
            kw_no_caption = {'chat_id': chat_id, **extra}
            if thread_id:
                kw_no_caption['message_thread_id'] = thread_id
            if kind == 'video':
                m = await bot.send_video(video=media_input, **kw_no_caption)
            elif kind == 'animation':
                m = await bot.send_animation(animation=media_input, **kw_no_caption)
            else:
                m = await bot.send_photo(photo=media_input, **kw_no_caption)
            msg_ids.append(m.message_id)
            text_ids = await _send_long(bot, chat_id, text, thread_id=thread_id,
                                        reply_markup=reply_markup, **extra)
            msg_ids.extend(text_ids)

    else:
        # 2-5 медиа: media_group (animation в группе нельзя — пропускаем)
        group = []
        for i, (kind, fid) in enumerate(media_list):
            cap = text if i == 0 and len(text) <= CAPTION_LIMIT else None
            pm = 'HTML' if cap else None
            media_input = _resolve_media_input(fid)
            if kind == 'video':
                group.append(InputMediaVideo(media=media_input, caption=cap, parse_mode=pm))
            else:
                # animation внутри группы Telegram не поддерживает — отправляем как photo
                group.append(InputMediaPhoto(media=media_input, caption=cap, parse_mode=pm))
        send_kw = {'chat_id': chat_id, 'media': group}
        if thread_id:
            send_kw['message_thread_id'] = thread_id
        if extra.get('disable_notification'):
            send_kw['disable_notification'] = True
        if extra.get('protect_content'):
            send_kw['protect_content'] = True
        msgs = await bot.send_media_group(**send_kw)
        msg_ids.extend([m.message_id for m in msgs])
        if len(text) > CAPTION_LIMIT:
            text_ids = await _send_long(bot, chat_id, text, thread_id=thread_id,
                                        reply_markup=reply_markup, **extra)
            msg_ids.extend(text_ids)

    # Закрепление (только для первого сообщения)
    if settings.get('pin') and msg_ids:
        try:
            await bot.pin_chat_message(
                chat_id=chat_id, message_id=msg_ids[0],
                disable_notification=bool(settings.get('disable_notify')),
            )
        except Exception as e:
            logger.warning(f"pin failed chat={chat_id} msg={msg_ids[0]}: {e}")

    return msg_ids


# ────────────────────────────────────────────────────────────────────
# Главная функция: публикация одного поста
# ────────────────────────────────────────────────────────────────────

async def publish_press_release(application, db, post: dict) -> tuple[bool, list]:
    """
    Публикует пресс-релиз во все его targets.
    Обновляет targets (message_ids/error) и статус поста.
    Возвращает (overall_ok, errors_list).

    V1.17.0a14: workspace_id берётся из `post['workspace_id']` (приходит из
    scheduled_posts.workspace_id, добавленного миграцией multi-tenancy).
    """
    from database.db_press_release import (
        get_targets, mark_target_published, mark_target_error,
        mark_published, mark_failed, get_branding,
    )

    bot = application.bot
    post_id = post['id']
    ws_id = post.get('workspace_id') or 1
    settings = _settings(post)
    media_list = _parse_media(post.get('photo_file_id'))
    keyboard = _build_keyboard(post)

    # Подпись из брендинга (default fallback)
    sig_default = get_branding(db, ws_id, 'signature', '') or ''
    text = _build_text(post, signature_default=sig_default)

    # Если targets пустой — fallback на legacy target_chat_id/thread_id
    targets = get_targets(db, ws_id, post_id)
    if not targets and post.get('target_chat_id'):
        targets = [{
            'id': None,
            'chat_id': post['target_chat_id'],
            'thread_id': post.get('thread_id'),
            'message_ids': [],
        }]

    if not targets:
        mark_failed(db, ws_id, post_id, "Нет ни одного target для публикации")
        return False, ["no targets"]

    overall_ok = True
    errors = []

    for tgt in targets:
        try:
            msg_ids = await _send_to_target(
                bot,
                chat_id=tgt['chat_id'],
                thread_id=tgt.get('thread_id'),
                text=text,
                media_list=media_list,
                reply_markup=keyboard,
                settings=settings,
            )
            if tgt.get('id'):
                mark_target_published(db, ws_id, tgt['id'], msg_ids)

            # Отложенное удаление через JobQueue
            dap = settings.get('delete_after_publish') or {}
            if dap.get('enabled') and msg_ids:
                _schedule_delete(application, tgt['chat_id'], msg_ids, dap)

        except Exception as e:
            overall_ok = False
            err = str(e)
            errors.append(f"chat={tgt['chat_id']}: {err}")
            if tgt.get('id'):
                mark_target_error(db, ws_id, tgt['id'], err)
            logger.error(f"publish post={post_id} target={tgt['chat_id']}: {e}", exc_info=True)

    if overall_ok:
        mark_published(db, ws_id, post_id)
    else:
        # Если все таргеты упали — фейл; иначе оставляем published как partial
        all_failed = all(
            t.get('error') or False for t in get_targets(db, ws_id, post_id)
        )
        if all_failed:
            mark_failed(db, ws_id, post_id, "; ".join(errors)[:500])
        else:
            mark_published(db, ws_id, post_id)  # частичный успех — всё равно published

    # Уведомление автору в ЛС
    try:
        author_id = post.get('author_id')
        if author_id:
            title = post.get('title') or '(без имени)'
            if overall_ok:
                msg = f"✅ Пресс-релиз «{title}» опубликован."
            else:
                msg = f"⚠️ Пресс-релиз «{title}» опубликован частично. Ошибки:\n" + "\n".join(errors[:5])
            await bot.send_message(chat_id=author_id, text=msg)
    except Exception as e:
        logger.debug(f"notify author: {e}")

    return overall_ok, errors


# ────────────────────────────────────────────────────────────────────
# Отложенное удаление и pre-publish reminder через JobQueue
# ────────────────────────────────────────────────────────────────────

def _schedule_delete(application, chat_id: int, msg_ids: list, dap: dict) -> None:
    """Планирует удаление сообщений через delete_after_publish.value [unit]."""
    value = int(dap.get('value', 0) or 0)
    unit = dap.get('unit', 'minutes')
    seconds = {'minutes': 60, 'hours': 3600, 'days': 86400}.get(unit, 60) * value
    if seconds <= 0:
        return

    async def _job(context):
        for mid in msg_ids:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception as e:
                logger.debug(f"auto-delete chat={chat_id} msg={mid}: {e}")

    application.job_queue.run_once(_job, when=seconds, name=f"pr_del_{chat_id}_{msg_ids[0]}")


async def check_pre_publish_reminders(application, db) -> None:
    """
    Проверяет посты со status=scheduled, у которых publish_at - reminder_min <= now < publish_at.
    Шлёт DM автору один раз (помечает в settings.reminder_sent=true).
    """
    from utils.helpers import get_moscow_time
    from database.db_press_release import update_press_release
    now = get_moscow_time()
    db.cursor.execute('''
        SELECT id, workspace_id, author_id, title, publish_at, pre_publish_reminder, settings_json
        FROM scheduled_posts
        WHERE status = 'scheduled' AND pre_publish_reminder > 0
    ''')
    rows = [dict(r) for r in db.cursor.fetchall()]
    for row in rows:
        try:
            settings = json.loads(row.get('settings_json') or '{}')
        except (ValueError, TypeError):
            settings = {}
        if settings.get('reminder_sent'):
            continue
        try:
            pa = datetime.fromisoformat(row['publish_at'])
        except (ValueError, TypeError):
            continue
        rem_min = int(row['pre_publish_reminder'] or 0)
        window_start = pa - timedelta(minutes=rem_min)
        if window_start <= now < pa:
            try:
                title = row.get('title') or '(без имени)'
                await application.bot.send_message(
                    chat_id=row['author_id'],
                    text=(
                        f"⏰ <b>Напоминание:</b> через {rem_min} мин публикуется "
                        f"пресс-релиз «{title}». Проверьте всё в админке.\n\n"
                        f"Опубликуется: {pa.strftime('%d.%m.%Y %H:%M')}"
                    ),
                    parse_mode='HTML',
                )
                settings['reminder_sent'] = True
                update_press_release(
                    db, row.get('workspace_id') or 1, row['id'],
                    settings_json=json.dumps(settings, ensure_ascii=False),
                )
            except Exception as e:
                logger.warning(f"pre-publish reminder post={row['id']}: {e}")


# ────────────────────────────────────────────────────────────────────
# Главный тик планировщика
# ────────────────────────────────────────────────────────────────────

async def tick_scheduler(application, db) -> None:
    """Вызывается из bot.py check_scheduled_posts. Публикует подошедшие пресс-релизы.

    V1.17.0a14: cross-workspace — берём из всех тенантов через
    `get_all_pending_press_releases`. Каждый post тащит свой workspace_id
    из строки scheduled_posts, дальнейшие вызовы получают его внутри
    publish_press_release.
    """
    from utils.helpers import get_moscow_time
    from database.db_press_release import get_all_pending_press_releases

    # 1) Pre-publish reminders
    try:
        await check_pre_publish_reminders(application, db)
    except Exception as e:
        logger.error(f"check_pre_publish_reminders: {e}")

    # 2) Сами публикации
    now_str = get_moscow_time().strftime('%Y-%m-%d %H:%M:%S')
    pending = get_all_pending_press_releases(db, now_str)
    for post in pending:
        try:
            await publish_press_release(application, db, post)
        except Exception as e:
            logger.error(f"publish post={post['id']}: {e}", exc_info=True)
