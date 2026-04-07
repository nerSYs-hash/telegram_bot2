#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Публикация, удаление и перепубликация анкет BBS в ветке чата.
"""

import json
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from handlers.BBS.database_bbs import get_profile
from handlers.BBS.helpers_bbs import (
    get_bbs_data, clear_bbs, build_profile_text, write_button,
)
from utils.helpers import get_moscow_time


# ═══════════════════════════════════════════════════════════════
# УТИЛИТА: безопасное редактирование/замена сообщения
# ═══════════════════════════════════════════════════════════════

async def safe_answer(query, text: str, keyboard: InlineKeyboardMarkup):
    """
    Отвечает на callback безопасно — работает и для текстовых,
    и для фото-сообщений (caption).
    Порядок попыток:
      1. edit_message_text   — обычное текстовое сообщение
      2. edit_message_caption — сообщение с фото/медиа
      3. delete + send_message — fallback (если ничего не помогло)
    """
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)
        return
    except Exception:
        pass

    try:
        await query.edit_message_caption(caption=text, parse_mode='HTML', reply_markup=keyboard)
        return
    except Exception:
        pass

    # Финальный fallback: удалить старое, отправить новое
    try:
        await query.message.delete()
    except Exception:
        pass
    try:
        await query.message.chat.send_message(text, parse_mode='HTML', reply_markup=keyboard)
    except Exception as e:
        logging.error(f"BBS safe_answer fallback failed: {e}")


# ═══════════════════════════════════════════════════════════════
# ПУБЛИКАЦИЯ
# ═══════════════════════════════════════════════════════════════

async def publish_profile(query, context, db, target_chat_id, bbs_thread_id):
    """Публикует анкету в ветку BBS и сохраняет в БД."""
    user = query.from_user
    data = get_bbs_data(context)
    photos = data.get('photos', [])
    profile_text = build_profile_text(data)
    bot_username = context.bot.username
    profile_text += f"\n\n"

    # Удалить старую анкету (полностью — и сообщения, и запись из БД)
    old_profile = get_profile(db, user.id)
    if old_profile:
        await delete_profile_messages(
            context.bot, db, old_profile, target_chat_id, bbs_thread_id
        )

    sent_message_ids = []
    try:
        if len(photos) == 1:
            msg = await context.bot.send_photo(
                chat_id=target_chat_id,
                message_thread_id=bbs_thread_id,
                photo=photos[0],
                caption=profile_text,
                parse_mode='HTML',
                reply_markup=write_button(user.id, bot_username),
            )
            sent_message_ids.append(msg.message_id)
        elif len(photos) > 1:
            media = [
                InputMediaPhoto(media=photos[0], caption=profile_text, parse_mode='HTML')
            ]
            media += [InputMediaPhoto(media=fid) for fid in photos[1:]]
            messages = await context.bot.send_media_group(
                chat_id=target_chat_id,
                message_thread_id=bbs_thread_id,
                media=media,
            )
            sent_message_ids.extend([m.message_id for m in messages])
            btn_msg = await context.bot.send_message(
                chat_id=target_chat_id,
                message_thread_id=bbs_thread_id,
                text=" 👆<b>Понравился ?</b>",
                parse_mode='HTML',
                reply_markup=write_button(user.id, bot_username),
            )
            sent_message_ids.append(btn_msg.message_id)
        else:
            # Без фото — текстовое сообщение
            msg = await context.bot.send_message(
                chat_id=target_chat_id,
                message_thread_id=bbs_thread_id,
                text=profile_text,
                parse_mode='HTML',
                reply_markup=write_button(user.id, bot_username),
            )
            sent_message_ids.append(msg.message_id)
    except Exception as e:
        logging.error(f"BBS: Error publishing profile: {e}")
        err_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 В меню", callback_data="menu_bbs")]
        ])
        await safe_answer(query, f"❌ Ошибка публикации: {e}", err_keyboard)
        clear_bbs(context)
        return

    # Сохранить в БД
    now_iso = get_moscow_time().strftime('%Y-%m-%d %H:%M:%S')
    save_sql = '''
            INSERT INTO bbs_profiles
                (user_id, username, photos, name, age, params, roles, city, goals, about,
                 message_ids, thread_id, published_at, edited_fields, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username, photos=excluded.photos, name=excluded.name,
                age=excluded.age, params=excluded.params, roles=excluded.roles,
                city=excluded.city, goals=excluded.goals, about=excluded.about,
                message_ids=excluded.message_ids, thread_id=excluded.thread_id,
                published_at=excluded.published_at, edited=0, edited_fields='{}',
                reaction_count=0, updated_at=excluded.updated_at
        '''
    save_args = (
            user.id, user.username,
            json.dumps(photos),
            data['name'], data['age'],
            json.dumps(data.get('params') or {}),
            json.dumps(data.get('roles', [])),
            json.dumps(data.get('city', [])),
            json.dumps(data.get('goals', [])),
            data.get('about'),
            json.dumps(sent_message_ids),
            bbs_thread_id,
            now_iso, now_iso, now_iso,
    )

    try:
        db.cursor.execute(save_sql, save_args)
        db.conn.commit()
    except Exception as e:
        logging.error(f"BBS: Error saving profile to DB (first try): {e}")
        try:
            from handlers.BBS.database_bbs import init_bbs_tables
            init_bbs_tables(db)
            db.cursor.execute(save_sql, save_args)
            db.conn.commit()
            logging.info("BBS: Profile saved after schema migration retry")
        except Exception as e2:
            logging.error(f"BBS: Error saving profile to DB (retry): {e2}")
            err_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В меню", callback_data="menu_bbs")]
            ])
            await safe_answer(
                query,
                "❌ Анкета не сохранена в БД из-за ошибки структуры данных. Попробуйте ещё раз.",
                err_keyboard,
            )
            clear_bbs(context)
            return

    clear_bbs(context)

    # Успешный ответ — safe_answer работает и с фото, и с текстом
    success_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
    ])
    await safe_answer(
        query,
        "✅ <b>Анкета опубликована!</b>\n\nОна появилась в ветке BBS. Удачи! 💘",
        success_keyboard,
    )


# ═══════════════════════════════════════════════════════════════
# УДАЛЕНИЕ
# ═══════════════════════════════════════════════════════════════

async def delete_profile_chat_messages(bot, profile, target_chat_id):
    """
    Удаляет ТОЛЬКО сообщения анкеты из чата. НЕ трогает БД.
    Используется при редактировании (перед перепубликацией).
    """
    msg_ids = profile.get('message_ids')
    if isinstance(msg_ids, str):
        try:
            msg_ids = json.loads(msg_ids)
        except Exception:
            msg_ids = []

    for mid in (msg_ids or []):
        try:
            await bot.delete_message(chat_id=target_chat_id, message_id=mid)
        except Exception as e:
            logging.warning(f"BBS: Could not delete msg {mid}: {e}")


async def delete_profile_messages(bot, db, profile, target_chat_id, bbs_thread_id=None):
    """
    Полное удаление: удаляет сообщения из чата И запись из БД.
    Используется при удалении анкеты пользователем или перепубликации с нуля.
    """
    await delete_profile_chat_messages(bot, profile, target_chat_id)

    try:
        db.cursor.execute(
            'DELETE FROM bbs_reactions WHERE profile_id = ?', (profile['id'],)
        )
        db.cursor.execute(
            'DELETE FROM bbs_profiles WHERE id = ?', (profile['id'],)
        )
        db.conn.commit()
    except Exception as e:
        logging.error(f"BBS: Error deleting profile from DB: {e}")


# ═══════════════════════════════════════════════════════════════
# ПЕРЕПУБЛИКАЦИЯ (после редактирования)
# ═══════════════════════════════════════════════════════════════

async def republish_profile(bot, db, user_id, target_chat_id, bbs_thread_id):
    profile = get_profile(db, user_id)
    if not profile:
        logging.warning(f"BBS republish: profile not found for user {user_id}")
        raise ValueError("Анкета не найдена в БД")

    # --- ИСПРАВЛЕНИЕ: Парсим JSON из БД, чтобы build_profile_text не падал ---
    parsed_profile = dict(profile)
    for field in ['photos', 'params', 'roles', 'city', 'goals', 'message_ids']:
        if field in parsed_profile and isinstance(parsed_profile[field], str):
            try:
                parsed_profile[field] = json.loads(parsed_profile[field])
            except Exception:
                # Fallback для битых данных
                if field in['photos', 'roles', 'city', 'goals', 'message_ids']:
                    parsed_profile[field] =[]
                elif field == 'params':
                    parsed_profile[field] = {}

    photos = parsed_profile.get('photos',[])
    
    # Теперь текст соберется без ошибок
    profile_text = build_profile_text(parsed_profile)
    sent_ids =[]

    try:
        if len(photos) == 1:
            msg = await bot.send_photo(
                chat_id=target_chat_id,
                message_thread_id=bbs_thread_id,
                photo=photos[0],
                caption=profile_text,
                parse_mode='HTML',
                reply_markup=write_button(user_id, bot.username),
            )
            sent_ids.append(msg.message_id)
        elif len(photos) > 1:
            # Фильтруем битые file_id (пустые строки, None)
            valid_photos = [p for p in photos if p]
            if not valid_photos:
                # Все фото битые — fallback на текст с кнопкой
                msg = await bot.send_message(
                    chat_id=target_chat_id,
                    message_thread_id=bbs_thread_id,
                    text=profile_text,
                    parse_mode='HTML',
                    reply_markup=write_button(user_id, bot.username),
                )
                sent_ids.append(msg.message_id)
            elif len(valid_photos) == 1:
                # Осталось 1 фото — отправляем как одиночное с кнопкой
                msg = await bot.send_photo(
                    chat_id=target_chat_id,
                    message_thread_id=bbs_thread_id,
                    photo=valid_photos[0],
                    caption=profile_text,
                    parse_mode='HTML',
                    reply_markup=write_button(user_id, bot.username),
                )
                sent_ids.append(msg.message_id)
            else:
                media = [
                    InputMediaPhoto(media=valid_photos[0], caption=profile_text, parse_mode='HTML')
                ]
                media += [InputMediaPhoto(media=fid) for fid in valid_photos[1:]]
                messages = await bot.send_media_group(
                    chat_id=target_chat_id,
                    message_thread_id=bbs_thread_id,
                    media=media,
                )
                sent_ids = [m.message_id for m in messages]
                # Кнопка — отдельным сообщением, отказ не должен ронять всю анкету
                try:
                    btn_msg = await bot.send_message(
                        chat_id=target_chat_id,
                        message_thread_id=bbs_thread_id,
                        text=" 👆<b>Понравился ?</b>",
                        parse_mode='HTML',
                        reply_markup=write_button(user_id, bot.username),
                    )
                    sent_ids.append(btn_msg.message_id)
                except Exception as btn_err:
                    logging.warning(f"BBS: Button send failed for {user_id}: {btn_err}")
        else:
            # Fallback на случай отсутствия фото (если БД повредилась)
            msg = await bot.send_message(
                chat_id=target_chat_id,
                message_thread_id=bbs_thread_id,
                text=profile_text,
                parse_mode='HTML',
                reply_markup=write_button(user_id, bot.username),
            )
            sent_ids.append(msg.message_id)
            
    except Exception as e:
        logging.error(f"BBS: Error republishing profile for {user_id}: {e}")
        # --- ИСПРАВЛЕНИЕ: Обязательно вызываем raise, чтобы родитель узнал об ошибке ---
        raise e

    # Обновляем message_ids в БД
    try:
        db.cursor.execute(
            'UPDATE bbs_profiles SET message_ids = ?, thread_id = ? WHERE user_id = ?',
            (json.dumps(sent_ids), bbs_thread_id, user_id),
        )
        db.conn.commit()
    except Exception as e:
        logging.error(f"BBS: Error updating message_ids: {e}")
        raise e


# ═══════════════════════════════════════════════════════════════
# РЕДАКТИРОВАНИЕ НА МЕСТЕ (без удаления и перемещения)
# ═══════════════════════════════════════════════════════════════

async def update_profile_in_place(bot, db, user_id, target_chat_id):
    """
    Обновляет анкету «на месте»: редактирует caption/text существующих
    сообщений через edit_message_caption / edit_message_text.
    Если редактирование невозможно — fallback на delete+republish.
    """
    profile = get_profile(db, user_id)
    if not profile:
        raise ValueError("Анкета не найдена в БД")

    parsed = dict(profile)
    for field in ['photos', 'params', 'roles', 'city', 'goals', 'message_ids']:
        if field in parsed and isinstance(parsed[field], str):
            try:
                parsed[field] = json.loads(parsed[field])
            except Exception:
                parsed[field] = [] if field != 'params' else {}

    msg_ids = parsed.get('message_ids') or []
    photos = parsed.get('photos') or []
    thread_id = profile.get('thread_id')

    profile_text = build_profile_text(parsed)

    if not msg_ids:
        # Нет сохранённых ID — fallback на republish
        logging.info(f"BBS update_in_place: no message_ids for user {user_id}, fallback republish")
        await republish_profile(bot, db, user_id, target_chat_id, thread_id)
        return

    first_msg_id = msg_ids[0]
    edited_in_place = False

    if photos:
        # Первое сообщение — фото с caption
        try:
            await bot.edit_message_caption(
                chat_id=target_chat_id,
                message_id=first_msg_id,
                caption=profile_text,
                parse_mode='HTML',
                reply_markup=write_button(user_id, bot.username),
            )
            edited_in_place = True
            logging.info(f"BBS update_in_place: caption edited for user {user_id}")
        except Exception as e:
            logging.warning(f"BBS update_in_place: edit_message_caption failed: {e}")
    else:
        # Текстовое сообщение
        try:
            await bot.edit_message_text(
                chat_id=target_chat_id,
                message_id=first_msg_id,
                text=profile_text,
                parse_mode='HTML',
                reply_markup=write_button(user_id, bot.username),
            )
            edited_in_place = True
            logging.info(f"BBS update_in_place: text edited for user {user_id}")
        except Exception as e:
            logging.warning(f"BBS update_in_place: edit_message_text failed: {e}")

    if not edited_in_place:
        # Fallback: удалить старые и перепубликовать
        logging.info(f"BBS update_in_place: fallback to republish for user {user_id}")
        await delete_profile_chat_messages(bot, profile, target_chat_id)
        await republish_profile(bot, db, user_id, target_chat_id, thread_id)