#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Редактирование досье в ветке «Анкеты».

Позволяет администраторам:
  - Менять фото анкеты (кастомное)
  - Добавлять / редактировать примечание

Работает как для новых анкет (кнопка ✏️ сразу), так и для старых
(через кнопку в панели).

Колбэки: anketa_edit_{user_id}
         anketa_edit_photo_{user_id}
         anketa_edit_note_{user_id}
         anketa_edit_clrphoto_{user_id}
         anketa_edit_clrnote_{user_id}
         anketa_edit_done_{user_id}

FSM: context.user_data['anketa_edit'] = {'action': 'photo'|'note', 'user_id': int}
"""

import asyncio
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from config import ADMIN_CHAT_ID, DOSSIER_THREAD_ID

logger = logging.getLogger(__name__)

IKB = InlineKeyboardButton


# ─────────────────────────────────────────────
#  БД
# ─────────────────────────────────────────────

def ensure_anketa_edit_tables(db) -> None:
    db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS anketa_edits (
            user_id         INTEGER PRIMARY KEY,
            dossier_chat_id INTEGER,
            dossier_msg_id  INTEGER,
            dossier_is_photo INTEGER DEFAULT 0,
            custom_photo_id TEXT,
            note            TEXT,
            admin_username  TEXT,
            base_text       TEXT,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    for col, definition in [
        ('admin_username', 'TEXT'),
        ('base_text',      'TEXT'),
    ]:
        try:
            db.cursor.execute(f'ALTER TABLE anketa_edits ADD COLUMN {col} {definition}')
            db.conn.commit()
        except Exception:
            pass
    db.conn.commit()


def get_anketa_edit(db, user_id: int) -> dict | None:
    try:
        db.cursor.execute('SELECT * FROM anketa_edits WHERE user_id = ?', (user_id,))
        row = db.cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    except Exception:
        return None


def upsert_anketa_edit(db, user_id: int, **kwargs) -> None:
    row = get_anketa_edit(db, user_id)
    if row is None:
        cols = ['user_id'] + list(kwargs.keys())
        vals = [user_id] + list(kwargs.values())
        ph = ','.join('?' * len(cols))
        db.cursor.execute(
            f'INSERT INTO anketa_edits ({",".join(cols)}) VALUES ({ph})', vals
        )
    else:
        sets = ', '.join(f'{k}=?' for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        db.cursor.execute(
            f'UPDATE anketa_edits SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE user_id=?',
            vals,
        )
    db.conn.commit()


# ─────────────────────────────────────────────
#  Получение данных пользователя из reg DB
# ─────────────────────────────────────────────

async def _get_reg_data(user_id: int) -> dict | None:
    """Берёт данные анкеты из базы регистрации."""
    try:
        from database.db_friend import get_user as reg_get_user
        data = await reg_get_user(user_id)
        return dict(data) if data else None
    except Exception as e:
        logger.error(f"anketa_edit: reg_get_user({user_id}): {e}")
        return None


# ─────────────────────────────────────────────
#  Построение текста досье с примечанием
# ─────────────────────────────────────────────

def _build_dossier_text(reg_data: dict, target_user_id: int, admin_username: str,
                         note: str | None = None) -> str:
    """Формирует HTML текст досье (дублирует approval_handlers._build_dossier_text + примечание)."""
    import html, re

    def city_tag(city):
        if not city:
            return "#Город_не_указан"
        n = city.strip().lower()
        if n in ("санкт-петербург", "спб", "питер", "saint-petersburg", "saint petersburg"):
            return "#СПБ"
        if n in ("москва", "мск", "moscow"):
            return "#МСК"
        return '#' + re.sub(r'[\s\-]+', '_', city.strip())

    q_name    = html.escape(reg_data.get('q_name')    or '—')
    q_age     = html.escape(str(reg_data.get('q_age') or '—'))
    q_city    = html.escape(reg_data.get('q_city')    or '—')
    q_therapy = html.escape(reg_data.get('q_therapy') or '—')
    username  = reg_data.get('username')

    username_tag     = f"@{username}" if username else q_name
    id_tag           = f"#user{target_user_id}"
    tags_line        = f"{city_tag(reg_data.get('q_city') or '')} {username_tag} {id_tag}"
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
    if note:
        text += f"\n\n📝 <b>Примечание:</b> {html.escape(note)}"
    return text


# ─────────────────────────────────────────────
#  Обновление сообщения в треде
# ─────────────────────────────────────────────

async def _rebuild_and_update(bot, db, user_id: int, reg_data: dict) -> None:
    """Перестраивает досье и редактирует / пересылает сообщение в треде."""
    import html as _html
    row = get_anketa_edit(db, user_id) or {}

    note = row.get('note')
    custom_photo = row.get('custom_photo_id')
    chat_id = row.get('dossier_chat_id') or ADMIN_CHAT_ID
    msg_id  = row.get('dossier_msg_id')
    is_photo = bool(row.get('dossier_is_photo'))

    # Используем оригинальный текст досье (сохранённый при создании).
    # Если base_text не сохранён — fallback на _build_dossier_text.
    base_text = row.get('base_text') or ''
    if not base_text:
        admin_username = row.get('admin_username') or '—'
        base_text = _build_dossier_text(reg_data, user_id, admin_username)

    if note:
        text = base_text + f"\n\n📝 <b>Примечание:</b> {_html.escape(note)}"
    else:
        text = base_text
    kb = InlineKeyboardMarkup([
        [IKB("✉️ Написать в ЛС", url=f"tg://user?id={user_id}"),
         IKB("✏️ Редактировать", callback_data=f"anketa_edit_{user_id}")],
    ])

    if msg_id:
        try:
            if custom_photo:
                if is_photo:
                    # Досье уже фото — просто меняем медиа
                    from telegram import InputMediaPhoto
                    await bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=msg_id,
                        media=InputMediaPhoto(media=custom_photo, caption=text, parse_mode='HTML'),
                        reply_markup=kb,
                    )
                    upsert_anketa_edit(db, user_id, dossier_is_photo=1)
                else:
                    # Досье было текстом — удаляем старое, отправляем фото
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    except Exception:
                        pass
                    sent = await bot.send_photo(
                        chat_id=ADMIN_CHAT_ID,
                        message_thread_id=DOSSIER_THREAD_ID,
                        photo=custom_photo,
                        caption=text,
                        parse_mode='HTML',
                        reply_markup=kb,
                    )
                    upsert_anketa_edit(db, user_id,
                                       dossier_msg_id=sent.message_id,
                                       dossier_is_photo=1,
                                       dossier_chat_id=sent.chat.id)
                return
            elif is_photo and not custom_photo:
                # Была фото-версия, теперь убираем фото — удаляем старое, отправляем текст
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception:
                    pass
                sent = await bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=DOSSIER_THREAD_ID,
                    text=text,
                    parse_mode='HTML',
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
                upsert_anketa_edit(db, user_id,
                                   dossier_msg_id=sent.message_id,
                                   dossier_is_photo=0,
                                   dossier_chat_id=sent.chat.id)
            elif not is_photo:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text,
                    parse_mode='HTML',
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
            else:
                # Фото-сообщение, просто меняем подпись
                await bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=msg_id,
                    caption=text,
                    parse_mode='HTML',
                    reply_markup=kb,
                )
            return
        except Exception as e:
            if "Message is not modified" in str(e):
                return  # контент уже актуален — новое сообщение не нужно
            logger.warning(f"anketa_edit: edit_message failed ({e}), sending new")

    # Нет msg_id или редактирование не удалось — отправляем новое
    photo_id = custom_photo
    if photo_id:
        sent = await bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            message_thread_id=DOSSIER_THREAD_ID,
            photo=photo_id,
            caption=text,
            parse_mode='HTML',
            reply_markup=kb,
        )
        upsert_anketa_edit(db, user_id,
                           dossier_msg_id=sent.message_id,
                           dossier_is_photo=1,
                           dossier_chat_id=sent.chat.id)
    else:
        sent = await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            message_thread_id=DOSSIER_THREAD_ID,
            text=text,
            parse_mode='HTML',
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        upsert_anketa_edit(db, user_id,
                           dossier_msg_id=sent.message_id,
                           dossier_is_photo=0,
                           dossier_chat_id=sent.chat.id)


# ─────────────────────────────────────────────
#  Меню редактирования
# ─────────────────────────────────────────────

async def _show_edit_menu(query_or_msg, context, db, user_id: int,
                           reg_data: dict, is_edit: bool = True,
                           expanded_photo: bool = False) -> None:
    row = get_anketa_edit(db, user_id) or {}
    note = row.get('note')
    custom_photo = row.get('custom_photo_id')

    display_name = reg_data.get('q_name') or reg_data.get('first_name') or '—'
    username = reg_data.get('username')
    name_str = f"@{username}" if username else display_name

    photo_status = '📷 Кастомное' if custom_photo else '👤 Из профиля Telegram'
    note_str = f"<i>{note[:80]}{'…' if len(note) > 80 else ''}</i>" if note else '—'

    text = (
        f"✏️ <b>Редактирование анкеты</b>\n\n"
        f"👤 {name_str}\n"
        f"🆔 <code>#{user_id}</code>\n\n"
        f"📷 Фото: {photo_status}\n"
        f"📝 Примечание: {note_str}"
    )

    kb = []
    if expanded_photo:
        # Раскрытые кнопки медиа
        photo_row = [IKB("📸 Заменить фото", callback_data=f"anketa_edit_photo_{user_id}")]
        if custom_photo:
            photo_row.append(IKB("🗑 Убрать фото", callback_data=f"anketa_edit_clrphoto_{user_id}"))
        kb.append(photo_row)
    else:
        kb.append([IKB("📷 Медиа ▾", callback_data=f"anketa_edit_photomenu_{user_id}")])
    if note:
        kb.append([IKB("✏️ Изменить примечание", callback_data=f"anketa_edit_note_{user_id}"),
                   IKB("🗑",                      callback_data=f"anketa_edit_clrnote_{user_id}")])
    else:
        kb.append([IKB("📝 Добавить примечание", callback_data=f"anketa_edit_note_{user_id}")])
    kb.append([IKB("✅ Готово", callback_data=f"anketa_edit_done_{user_id}")])

    markup = InlineKeyboardMarkup(kb)
    if is_edit:
        try:
            await query_or_msg.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
            return
        except Exception:
            # Фото-сообщение — редактируем подпись
            try:
                await query_or_msg.edit_message_caption(text, parse_mode='HTML', reply_markup=markup)
                return
            except Exception:
                pass
    # Fallback: новое сообщение (сохраняем тред)
    msg = query_or_msg.message if hasattr(query_or_msg, 'message') else query_or_msg
    await context.bot.send_message(
        chat_id=msg.chat.id,
        message_thread_id=msg.message_thread_id,
        text=text, parse_mode='HTML', reply_markup=markup,
    )


# ─────────────────────────────────────────────
#  Обработчик колбэков
# ─────────────────────────────────────────────

async def handle_anketa_edit_callback(query, context, db, data: str) -> bool:
    """
    Обрабатывает все anketa_edit_* callback-ы.
    Возвращает True если обработал.
    """
    if not data.startswith('anketa_edit_'):
        return False

    sub = data[len('anketa_edit_'):]

    # Определяем action и user_id из sub-строки
    # Форматы: "{user_id}", "photo_{user_id}", "note_{user_id}",
    #          "clrphoto_{user_id}", "clrnote_{user_id}", "done_{user_id}"
    if sub.lstrip('-').isdigit():
        action, user_id_str = 'menu', sub
    elif '_' in sub:
        parts = sub.rsplit('_', 1)
        if len(parts) == 2 and parts[1].lstrip('-').isdigit():
            action, user_id_str = parts[0], parts[1]
        else:
            return False
    else:
        return False

    try:
        user_id = int(user_id_str)
    except ValueError:
        return False

    reg_data = await _get_reg_data(user_id)
    if reg_data is None:
        await query.answer("⚠️ Пользователь не найден в базе регистрации", show_alert=True)
        return True

    ensure_anketa_edit_tables(db)

    # ── меню ──
    if action == 'menu':
        # Сохраняем base_text при первом открытии (для старых досье без base_text)
        row = get_anketa_edit(db, user_id) or {}
        if not row.get('base_text'):
            current_text = query.message.caption or query.message.text or ''
            if current_text:
                upsert_anketa_edit(db, user_id, base_text=current_text)
        await _show_edit_menu(query, context, db, user_id, reg_data)
        return True

    # ── раскрытие кнопок медиа ──
    if action == 'photomenu':
        await query.answer()
        await _show_edit_menu(query, context, db, user_id, reg_data, expanded_photo=True)
        return True

    # ── начало ввода фото ──
    if action == 'photo':
        context.user_data['anketa_edit'] = {'action': 'photo', 'user_id': user_id}
        prompt_text = (
            f"📷 <b>Отправьте новое фото</b> для анкеты #{user_id}\n\n"
            "<i>Просто пришлите изображение в этот чат.</i>"
        )
        prompt_kb = InlineKeyboardMarkup([[IKB("❌ Отмена", callback_data=f"anketa_edit_{user_id}")]])
        try:
            await query.edit_message_text(prompt_text, parse_mode='HTML', reply_markup=prompt_kb)
        except Exception:
            # Фото-сообщение нельзя edit_message_text — редактируем подпись
            try:
                await query.edit_message_caption(prompt_text, parse_mode='HTML', reply_markup=prompt_kb)
            except Exception:
                await context.bot.send_message(
                    chat_id=query.message.chat.id,
                    message_thread_id=query.message.message_thread_id,
                    text=prompt_text, parse_mode='HTML', reply_markup=prompt_kb,
                )
        return True

    # ── начало ввода примечания ──
    if action == 'note':
        row = get_anketa_edit(db, user_id) or {}
        cur = row.get('note') or ''
        hint = f" (сейчас: {cur[:60]})" if cur else ''
        prompt = await context.bot.send_message(
            chat_id=query.message.chat.id,
            message_thread_id=query.message.message_thread_id,
            text=f"📝 Примечание к анкете #{user_id}{hint}:",
            reply_markup=ForceReply(selective=True, input_field_placeholder="Введите примечание…"),
        )
        await query.answer()
        context.user_data['anketa_edit'] = {
            'action': 'note',
            'user_id': user_id,
            'prompt_msg_id': prompt.message_id,
        }
        return True

    # ── убрать кастомное фото ──
    if action == 'clrphoto':
        upsert_anketa_edit(db, user_id, custom_photo_id=None)
        await query.answer("🗑 Кастомное фото убрано")
        await _rebuild_and_update(context.bot, db, user_id, reg_data)
        await _show_edit_menu(query, context, db, user_id, reg_data)
        return True

    # ── убрать примечание ──
    if action == 'clrnote':
        upsert_anketa_edit(db, user_id, note=None)
        await query.answer("🗑 Примечание убрано")
        await _rebuild_and_update(context.bot, db, user_id, reg_data)
        await _show_edit_menu(query, context, db, user_id, reg_data)
        return True

    # ── готово ──
    if action == 'done':
        context.user_data.pop('anketa_edit', None)
        await query.answer("✅ Сохранено")
        # Восстанавливаем досье вместо удаления — меню редактировало досье in-place,
        # и delete_message() убирало бы само досье навсегда.
        menu_msg_id = query.message.message_id
        if reg_data:
            await _rebuild_and_update(context.bot, db, user_id, reg_data)
            # Если rebuild создал НОВОЕ сообщение (msg_id изменился) — удаляем старое меню
            updated_row = get_anketa_edit(db, user_id) or {}
            if updated_row.get('dossier_msg_id') != menu_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=query.message.chat.id,
                        message_id=menu_msg_id,
                    )
                except Exception:
                    pass
        else:
            try:
                await query.delete_message()
            except Exception:
                pass
        return True

    return False


# ─────────────────────────────────────────────
#  FSM: обработка медиа и текста
# ─────────────────────────────────────────────

async def _autodelete(msg, delay: int = 4):
    """Удаляет сообщение через delay секунд."""
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def handle_anketa_edit_input(message, context, db) -> bool:
    """
    Вызывается из message_handler / admin_logic для обработки ввода в FSM.
    Возвращает True если обработал (нужно прекратить дальнейшую обработку).
    """
    state = context.user_data.get('anketa_edit')
    if not state:
        return False

    action  = state.get('action')
    user_id = state.get('user_id')
    if not action or not user_id:
        return False

    ensure_anketa_edit_tables(db)
    reg_data = await _get_reg_data(user_id)

    # ── фото ──
    if action == 'photo':
        photo = None
        if message.photo:
            photo = message.photo[-1].file_id
        elif message.document and message.document.mime_type and message.document.mime_type.startswith('image'):
            photo = message.document.file_id

        if not photo:
            await message.reply_text("⚠️ Нужно отправить фото.")
            return True

        context.user_data.pop('anketa_edit', None)
        upsert_anketa_edit(db, user_id, custom_photo_id=photo)

        if reg_data:
            await _rebuild_and_update(context.bot, db, user_id, reg_data)

        conf = await message.reply_text(f"✅ Фото анкеты #{user_id} обновлено.")
        asyncio.create_task(_autodelete(conf, delay=4))
        try:
            await message.delete()
        except Exception:
            pass
        return True

    # ── примечание ──
    if action == 'note':
        text = (message.text or '').strip()
        if not text:
            conf = await message.reply_text("⚠️ Пустое примечание не сохранено.")
            asyncio.create_task(_autodelete(conf, delay=3))
            return True

        prompt_msg_id = state.get('prompt_msg_id')
        context.user_data.pop('anketa_edit', None)
        upsert_anketa_edit(db, user_id, note=text)

        if reg_data:
            await _rebuild_and_update(context.bot, db, user_id, reg_data)

        # Удаляем ForceReply-промпт и ответ пользователя
        if prompt_msg_id:
            try:
                await context.bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
            except Exception:
                pass
        try:
            await message.delete()
        except Exception:
            pass
        return True

    return False
