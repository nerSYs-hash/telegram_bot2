#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Опрос при выходе из чата — полная реализация по ТЗ п.6.3.

5 вопросов:
  Q1  — Почему вышел? (15 кнопок с ветвлениями)
  Q1b — Уточнение для спецкейсов (текст или подкнопки)
  Q2  — Что можно улучшить?
  Q3  — Конкретное событие?
  Q4  — Какие были ожидания? (текст или пропуск)
  Q5  — «Ты уверен?» + кнопка возврата

Колбэки:
  exit_{key}_{user_id}        — Q1 причина
  exit_skip_reason_{user_id}  — пропуск текстового ввода Q1
  exitlove_{key}_{user_id}    — подвопрос «Нашёл любовь»
  exitimp_{key}_{user_id}     — Q2 улучшение
  exitev_{key}_{user_id}      — Q3 событие
  exitq4_skip_{user_id}       — пропуск Q4
  exitfinal_done_{user_id}    — завершить опрос (Q5)

Сохраняется в exit_interviews.
"""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import format_number

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
#  МИГРАЦИЯ
# ════════════════════════════════════════════════════════════════

def ensure_survey_columns(db) -> None:
    """Добавляет недостающие колонки в exit_interviews."""
    try:
        db.cursor.execute("PRAGMA table_info(exit_interviews)")
        cols = {row[1] for row in db.cursor.fetchall()}
        for col, typ in [
            ('improvement',    'TEXT'),
            ('would_return',   'TEXT'),
            ('q3_event',       'TEXT'),
            ('q4_expectations','TEXT'),
        ]:
            if col not in cols:
                db.cursor.execute(f'ALTER TABLE exit_interviews ADD COLUMN {col} {typ}')
        db.conn.commit()
    except Exception as e:
        logger.error(f"ensure_survey_columns error: {e}")


# ════════════════════════════════════════════════════════════════
#  СЛОВАРИ
# ════════════════════════════════════════════════════════════════

REASON_MAP = {
    'boring':       'Скучно',
    'same_faces':   'Одни и те же лица',
    'few_people':   'Мало народа',
    'other_expect': 'Другие ожидания',
    'flood':        'Много флуда',
    'threats':      'Угрозы/Шантаж',
    'ignored':      'Меня игнорят',
    'tired':        'Надоело',
    'love':         'Нашел любовь',
    'no_info':      'Нет нужной инфы',
    'not_fit':      'Не зашло',
    'toxic':        'Токсичность',
    'no_time':      'Нет времени',
    'notifs':       'Много уведомлений',
    'other':        'Другое',
}

IMPROVEMENT_MAP = {
    'admins': '👮 Работу админов',
    'users':  '👥 Количество пользователей',
    'events': '🎉 Конкурсы',
    'topics': '💬 Темы/Ветки',
    'dunno':  '🤷 Не знаю',
    'bot':    '🤖 Работу бота',
    'other':  '📝 Другое',
}

LOVE_PLACE_MAP = {
    'our_chat':    '💚 В нашем чате',
    'other_chat':  '💬 В другом чате',
    'dating_site': '🌐 На сайте знакомств',
    'friends':     '👫 Познакомили друзья',
    'other':       '📝 Другое',
}

EVENT_MAP = {
    'none':       '🙅 Нет',
    'conflict':   '⚔️ Конфликт',
    'love':       '💕 Нашел любовь',
    'detox':      '📵 Цифровой детокс',
    'other_chat': '💬 Ушел в другой чат',
    'other':      '📝 Другое',
}


# ════════════════════════════════════════════════════════════════
#  ВНУТРЕННИЕ ХЕЛПЕРЫ
# ════════════════════════════════════════════════════════════════

def _save_reason(db, user_id: int, reason_text: str, context) -> None:
    """Сохраняет причину ухода и запоминает interview_id в user_data."""
    try:
        db.cursor.execute(
            'INSERT INTO exit_interviews (user_id, reason_category) VALUES (?, ?)',
            (user_id, reason_text)
        )
        db.conn.commit()
        context.user_data['exit_interview_id'] = db.cursor.lastrowid
    except Exception as e:
        logger.error(f"_save_reason error: {e}")


def _parse_key_and_uid(data: str, prefix: str):
    """Вытаскивает (key, user_id) из строки вида prefix_key_uid.
    key сам может содержать '_', user_id — всегда последняя часть."""
    rest = data[len(prefix):]
    idx = rest.rfind('_')
    if idx == -1:
        return None, None
    try:
        return rest[:idx], int(rest[idx + 1:])
    except ValueError:
        return None, None


def _make_improvement_kb(user_id: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(label, callback_data=f"exitimp_{k}_{user_id}")]
            for k, label in IMPROVEMENT_MAP.items()]
    rows.append([InlineKeyboardButton("⏭ Пропустить", callback_data=f"exitimp_skip_{user_id}")])
    return InlineKeyboardMarkup(rows)


def _make_event_kb(user_id: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(label, callback_data=f"exitev_{k}_{user_id}")]
            for k, label in EVENT_MAP.items()]
    rows.append([InlineKeyboardButton("⏭ Пропустить", callback_data=f"exitev_skip_{user_id}")])
    return InlineKeyboardMarkup(rows)


def _make_love_place_kb(user_id: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(label, callback_data=f"exitlove_{k}_{user_id}")]
            for k, label in LOVE_PLACE_MAP.items()]
    return InlineKeyboardMarkup(rows)


async def _generate_invite_link(context, user_id: int) -> str | None:
    """Генерирует одноразовую ссылку возврата из сохранённого chat_id."""
    chat_id = context.user_data.get('exit_survey_chat_id')
    if not chat_id:
        return None
    try:
        link_obj = await context.bot.create_chat_invite_link(
            chat_id=int(chat_id),
            member_limit=1,
            name=f"return_{user_id}"[:32],
        )
        return link_obj.invite_link
    except Exception as e:
        logger.error(f"_generate_invite_link error: {e}")
        return None


# ════════════════════════════════════════════════════════════════
#  ШАГ 1: ПРИЧИНА УХОДА  (exit_{key}_{user_id})
# ════════════════════════════════════════════════════════════════

async def handle_exit_reason(query, data: str, context, db, admin_id: int) -> None:
    ensure_survey_columns(db)

    reason_key, user_id = _parse_key_and_uid(data, "exit_")
    if reason_key is None:
        await query.answer("❌ Ошибка.", show_alert=True)
        return

    reason_text = REASON_MAP.get(reason_key, 'Другое')
    await query.answer()

    # ── Спецкейсы: требуют текстового ввода ─────────────────────

    if reason_key == 'other_expect':
        context.user_data.update({
            'exit_survey_awaiting': 'expectations',
            'exit_survey_user_id':  user_id,
            'exit_survey_reason':   reason_text,
        })
        await query.edit_message_text(
            "💭 <b>Какие ожидания у тебя были от чата?</b>\n\nНапиши свободным текстом:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⏭ Пропустить", callback_data=f"exit_skip_reason_{user_id}")
            ]])
        )
        return

    if reason_key == 'threats':
        context.user_data.update({
            'exit_survey_awaiting': 'threat_details',
            'exit_survey_user_id':  user_id,
            'exit_survey_reason':   reason_text,
        })
        await query.edit_message_text(
            "⚠️ <b>Это серьёзно, и мы хотим помочь.</b>\n\n"
            "Укажи обстоятельства: эти люди из нашего чата? Напиши ник. "
            "Чем подробнее — тем лучше мы сможем защитить других.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⏭ Пропустить", callback_data=f"exit_skip_reason_{user_id}")
            ]])
        )
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"⚠️ <b>Угрозы/Шантаж</b>\n\nПользователь ID {user_id} указал эту причину ухода. Ожидайте детали.",
                parse_mode='HTML',
            )
        except Exception:
            pass
        return

    if reason_key == 'no_info':
        context.user_data.update({
            'exit_survey_awaiting': 'info_request',
            'exit_survey_user_id':  user_id,
            'exit_survey_reason':   reason_text,
        })
        await query.edit_message_text(
            "📚 <b>Какую информацию ты искал?</b>\n\nНапиши подробнее — мы постараемся добавить нужный контент:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⏭ Пропустить", callback_data=f"exit_skip_reason_{user_id}")
            ]])
        )
        return

    if reason_key == 'not_fit':
        context.user_data.update({
            'exit_survey_awaiting': 'dislike_details',
            'exit_survey_user_id':  user_id,
            'exit_survey_reason':   reason_text,
        })
        await query.edit_message_text(
            "💬 <b>Что именно тебе не понравилось?</b>\n\nЭто поможет нам стать лучше:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⏭ Пропустить", callback_data=f"exit_skip_reason_{user_id}")
            ]])
        )
        return

    if reason_key == 'other':
        context.user_data.update({
            'exit_survey_awaiting': 'other_details',
            'exit_survey_user_id':  user_id,
            'exit_survey_reason':   reason_text,
        })
        await query.edit_message_text(
            "💬 <b>Расскажи нам подробности!</b>\n\nНам очень интересно твоё мнение:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⏭ Пропустить", callback_data=f"exit_skip_reason_{user_id}")
            ]])
        )
        return

    # ── Спецкейсы: особый ответ + кнопка возврата / продолжения ─

    if reason_key == 'ignored':
        _save_reason(db, user_id, reason_text, context)
        await query.edit_message_text(
            "💙 <b>Это очень прискорбно слышать.</b>\n\n"
            "Иногда сложно влиться в новое сообщество — это нормально. "
            "Давай попробуем ещё раз? В Pulse точно найдутся люди, которым будет интересно с тобой!",
            parse_mode='HTML',
            reply_markup=await _make_q5_kb(user_id, context),
        )
        return

    if reason_key == 'tired':
        _save_reason(db, user_id, reason_text, context)
        await query.edit_message_text(
            "💡 <b>Знаешь ли ты, что в Telegram есть Архив?</b>\n\n"
            "Не обязательно уходить — можно временно смахнуть чат в архив. "
            "Когда захочешь вернуться, он будет тебя ждать 😊",
            parse_mode='HTML',
            reply_markup=await _make_q5_kb(user_id, context),
        )
        return

    if reason_key == 'notifs':
        _save_reason(db, user_id, reason_text, context)
        await query.edit_message_text(
            "🔔 <b>Уведомления можно просто отключить!</b>\n\n"
            "1. Открой чат → нажми на его название вверху\n"
            "2. Найди «Уведомления» или значок 🔔\n"
            "3. Выбери «Отключить» — на 1 час, 8 часов или навсегда\n\n"
            "Так ты останешься с нами, но тебя не будут беспокоить 😊",
            parse_mode='HTML',
            reply_markup=await _make_q5_kb(user_id, context),
        )
        return

    # ── Подвопрос: «Нашёл любовь» ────────────────────────────────

    if reason_key == 'love':
        _save_reason(db, user_id, reason_text, context)
        context.user_data['exit_survey_user_id'] = user_id
        await query.edit_message_text(
            "💕 <b>Поздравляем!</b>\n\nГде ты встретил свою вторую половинку?",
            parse_mode='HTML',
            reply_markup=_make_love_place_kb(user_id),
        )
        return

    # ── Уведомление владельца при токсичности ────────────────────

    if reason_key == 'toxic':
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"⚠️ Пользователь ID {user_id} ушёл из-за <b>токсичности</b>. Рекомендуется проверить ситуацию.",
                parse_mode='HTML',
            )
        except Exception:
            pass

    # ── Обычный кейс → Q2 ────────────────────────────────────────

    _save_reason(db, user_id, reason_text, context)
    await query.edit_message_text(
        "2️⃣ <b>Что можно улучшить в первую очередь?</b>",
        parse_mode='HTML',
        reply_markup=_make_improvement_kb(user_id),
    )


async def handle_exit_skip_reason(query, data: str, context, db) -> None:
    """Пропуск текстового ввода Q1."""
    parts = data.split('_')
    try:
        user_id = int(parts[-1])
    except (ValueError, IndexError):
        await query.answer("❌ Ошибка.", show_alert=True)
        return

    context.user_data.pop('exit_survey_awaiting', None)
    reason_text = context.user_data.pop('exit_survey_reason', 'Не указана')
    _save_reason(db, user_id, reason_text, context)

    await query.answer()
    await query.edit_message_text(
        "2️⃣ <b>Что можно улучшить в первую очередь?</b>",
        parse_mode='HTML',
        reply_markup=_make_improvement_kb(user_id),
    )


# ════════════════════════════════════════════════════════════════
#  ПОДВОПРОС: НАШЁЛ ЛЮБОВЬ  (exitlove_{key}_{user_id})
# ════════════════════════════════════════════════════════════════

async def handle_exit_love_place(query, data: str, context, db) -> None:
    place_key, user_id = _parse_key_and_uid(data, "exitlove_")
    if place_key is None:
        await query.answer("❌ Ошибка.", show_alert=True)
        return

    place_text = LOVE_PLACE_MAP.get(place_key, place_key)
    interview_id = context.user_data.get('exit_interview_id')
    if interview_id:
        try:
            db.cursor.execute(
                'UPDATE exit_interviews SET reason_text = ? WHERE id = ?',
                (f'Место знакомства: {place_text}', interview_id)
            )
            db.conn.commit()
        except Exception as e:
            logger.error(f"handle_exit_love_place save error: {e}")

    await query.answer()
    await query.edit_message_text(
        "2️⃣ <b>Что можно улучшить в первую очередь?</b>",
        parse_mode='HTML',
        reply_markup=_make_improvement_kb(user_id),
    )


# ════════════════════════════════════════════════════════════════
#  Q2: ЧТО УЛУЧШИТЬ  (exitimp_{key}_{user_id})
# ════════════════════════════════════════════════════════════════

async def handle_exit_improvement(query, data: str, context, db) -> None:
    imp_key, user_id = _parse_key_and_uid(data, "exitimp_")
    if imp_key is None:
        await query.answer("❌ Ошибка.", show_alert=True)
        return

    if imp_key != 'skip':
        interview_id = context.user_data.get('exit_interview_id')
        if interview_id:
            imp_text = IMPROVEMENT_MAP.get(imp_key, imp_key)
            try:
                db.cursor.execute(
                    'UPDATE exit_interviews SET improvement = ? WHERE id = ?',
                    (imp_text, interview_id)
                )
                db.conn.commit()
            except Exception as e:
                logger.error(f"handle_exit_improvement save error: {e}")

    await query.answer()
    await query.edit_message_text(
        "3️⃣ <b>Было ли конкретное событие, после которого ты решил выйти?</b>",
        parse_mode='HTML',
        reply_markup=_make_event_kb(user_id),
    )


# ════════════════════════════════════════════════════════════════
#  Q3: СОБЫТИЕ  (exitev_{key}_{user_id})
# ════════════════════════════════════════════════════════════════

async def handle_exit_event(query, data: str, context, db) -> None:
    ev_key, user_id = _parse_key_and_uid(data, "exitev_")
    if ev_key is None:
        await query.answer("❌ Ошибка.", show_alert=True)
        return

    if ev_key != 'skip':
        interview_id = context.user_data.get('exit_interview_id')
        if interview_id:
            ev_text = EVENT_MAP.get(ev_key, ev_key)
            try:
                db.cursor.execute(
                    'UPDATE exit_interviews SET q3_event = ? WHERE id = ?',
                    (ev_text, interview_id)
                )
                db.conn.commit()
            except Exception as e:
                logger.error(f"handle_exit_event save error: {e}")

    # → Q4: текстовый ввод ожиданий
    context.user_data['exit_survey_awaiting'] = 'q4_expectations'
    context.user_data['exit_survey_user_id'] = user_id

    await query.answer()
    await query.edit_message_text(
        "4️⃣ <b>Какие были ожидания при вступлении в чат?</b>\n\n"
        "Напиши свободным текстом (или пропусти):",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭ Пропустить", callback_data=f"exitq4_skip_{user_id}")
        ]])
    )


# ════════════════════════════════════════════════════════════════
#  Q4 ПРОПУСК  (exitq4_skip_{user_id})
# ════════════════════════════════════════════════════════════════

async def handle_exitq4_skip(query, data: str, context, db) -> None:
    parts = data.split('_')
    try:
        user_id = int(parts[-1])
    except (ValueError, IndexError):
        await query.answer("❌ Ошибка.", show_alert=True)
        return

    context.user_data.pop('exit_survey_awaiting', None)
    await query.answer()
    await query.edit_message_text(
        "5️⃣ <b>Ты уверен, что хочешь лишить себя:</b>\n\n"
        "• Дополнительного инструмента для поиска друзей и пары?\n"
        "• Офлайн-встреч с чатланами?\n"
        "• Консультаций равного консультанта по теме здоровья?\n"
        "• Живого общения?",
        parse_mode='HTML',
        reply_markup=await _make_q5_kb(user_id, context),
    )


# ════════════════════════════════════════════════════════════════
#  Q5: ФИНАЛ  (exitfinal_done_{user_id})
# ════════════════════════════════════════════════════════════════

async def handle_exit_final(query, data: str, context, db) -> None:
    """Завершение опроса — показываем благодарность."""
    parts = data.split('_')
    try:
        user_id = int(parts[-1])
    except (ValueError, IndexError):
        await query.answer("❌ Ошибка.", show_alert=True)
        return

    await query.answer()
    await _show_thanks(query.message, user_id, db)


async def _make_q5_kb(user_id: int, context) -> InlineKeyboardMarkup:
    """Клавиатура Q5: кнопка возврата + завершить."""
    invite_link = context.user_data.get('exit_survey_invite_link')
    if not invite_link:
        invite_link = await _generate_invite_link(context, user_id)
        if invite_link:
            context.user_data['exit_survey_invite_link'] = invite_link

    rows = []
    if invite_link:
        rows.append([InlineKeyboardButton("🔄 Вернуться в чат", url=invite_link)])
    rows.append([InlineKeyboardButton("✅ Завершить опрос", callback_data=f"exitfinal_done_{user_id}")])
    return InlineKeyboardMarkup(rows)


async def _show_thanks(message, user_id: int, db) -> None:
    try:
        user_data = db.get_user(user_id)
        frozen = 0
        if user_data:
            try:
                frozen = float(user_data['frozen_balance'] or 0)
            except (KeyError, TypeError):
                frozen = 0
    except Exception:
        frozen = 0

    frozen_text = ""
    if frozen > 0:
        frozen_text = (
            f"\n\n❄️ Напоминаем: твои <b>{format_number(frozen)}</b> Пульсов заморожены на 30 дней. "
            f"Вернись — и они вернутся к тебе!"
        )

    await message.edit_text(
        "🙏 <b>Спасибо за обратную связь!</b>\n\n"
        "Мы ценим каждое мнение и обязательно учтём твои слова "
        "при улучшении нашего сообщества."
        f"{frozen_text}\n\n"
        "Двери всегда открыты 💙",
        parse_mode='HTML',
    )


# ════════════════════════════════════════════════════════════════
#  ОБРАБОТЧИК ТЕКСТОВОГО ВВОДА  (вызывается из message_handler)
# ════════════════════════════════════════════════════════════════

async def handle_exit_survey_text(update, context, db) -> bool:
    """
    Перехватывает текстовые ответы в рамках exit survey.
    Возвращает True если сообщение обработано.
    Вызывается из handle_private_message ДО проверки членства.
    """
    awaiting = context.user_data.get('exit_survey_awaiting')
    if not awaiting:
        return False

    message = update.effective_message
    text = (message.text or '').strip()[:500]
    user_id = context.user_data.get('exit_survey_user_id')
    if not user_id:
        return False

    interview_id = context.user_data.get('exit_interview_id')

    # ── Q1 текстовые ответы ──────────────────────────────────────
    if awaiting in ('expectations', 'threat_details', 'info_request', 'dislike_details', 'other_details'):
        reason_text = context.user_data.pop('exit_survey_reason', awaiting)
        context.user_data.pop('exit_survey_awaiting', None)

        try:
            if interview_id:
                db.cursor.execute(
                    'UPDATE exit_interviews SET reason_text = ? WHERE id = ?',
                    (text, interview_id)
                )
            else:
                db.cursor.execute(
                    'INSERT INTO exit_interviews (user_id, reason_category, reason_text) VALUES (?, ?, ?)',
                    (user_id, reason_text, text)
                )
                context.user_data['exit_interview_id'] = db.cursor.lastrowid
            db.conn.commit()
        except Exception as e:
            logger.error(f"handle_exit_survey_text Q1 save error: {e}")

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        rows = [[InlineKeyboardButton(label, callback_data=f"exitimp_{k}_{user_id}")]
                for k, label in IMPROVEMENT_MAP.items()]
        rows.append([InlineKeyboardButton("⏭ Пропустить", callback_data=f"exitimp_skip_{user_id}")])
        await message.reply_text(
            "2️⃣ <b>Что можно улучшить в первую очередь?</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return True

    # ── Q4 ожидания ──────────────────────────────────────────────
    if awaiting == 'q4_expectations':
        context.user_data.pop('exit_survey_awaiting', None)

        if interview_id and text:
            try:
                db.cursor.execute(
                    'UPDATE exit_interviews SET q4_expectations = ? WHERE id = ?',
                    (text, interview_id)
                )
                db.conn.commit()
            except Exception as e:
                logger.error(f"handle_exit_survey_text Q4 save error: {e}")

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        invite_link = context.user_data.get('exit_survey_invite_link')
        rows = []
        if invite_link:
            rows.append([InlineKeyboardButton("🔄 Вернуться в чат", url=invite_link)])
        rows.append([InlineKeyboardButton("✅ Завершить опрос", callback_data=f"exitfinal_done_{user_id}")])

        await message.reply_text(
            "5️⃣ <b>Ты уверен, что хочешь лишить себя:</b>\n\n"
            "• Дополнительного инструмента для поиска друзей и пары?\n"
            "• Офлайн-встреч с чатланами?\n"
            "• Консультаций равного консультанта по теме здоровья?\n"
            "• Живого общения?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return True

    return False


# ════════════════════════════════════════════════════════════════
#  ДАШБОРД РЕЗУЛЬТАТОВ  (для владельца)
# ════════════════════════════════════════════════════════════════

async def show_survey_results(query, db, admin_id: int) -> None:
    ensure_survey_columns(db)

    db.cursor.execute('SELECT COUNT(*) as cnt FROM exit_interviews')
    total = db.cursor.fetchone()['cnt']

    db.cursor.execute('''
        SELECT reason_category, COUNT(*) as cnt
        FROM exit_interviews
        GROUP BY reason_category
        ORDER BY cnt DESC LIMIT 15
    ''')
    reasons = db.cursor.fetchall()

    db.cursor.execute('''
        SELECT improvement, COUNT(*) as cnt
        FROM exit_interviews
        WHERE improvement IS NOT NULL
        GROUP BY improvement
        ORDER BY cnt DESC LIMIT 7
    ''')
    improvements = db.cursor.fetchall()

    db.cursor.execute('''
        SELECT q3_event, COUNT(*) as cnt
        FROM exit_interviews
        WHERE q3_event IS NOT NULL
        GROUP BY q3_event
        ORDER BY cnt DESC LIMIT 6
    ''')
    events = db.cursor.fetchall()

    db.cursor.execute('''
        SELECT ei.*, u.username, u.first_name
        FROM exit_interviews ei
        LEFT JOIN users u ON ei.user_id = u.user_id
        ORDER BY ei.left_at DESC LIMIT 5
    ''')
    recent = db.cursor.fetchall()

    text = f"📊 <b>ОПРОСЫ ПРИ ВЫХОДЕ</b>\n\n📋 Всего ответов: <b>{total}</b>\n\n"

    if reasons:
        text += "<b>Причины ухода:</b>\n"
        for r in reasons:
            text += f"  {r['reason_category']}: <b>{r['cnt']}</b>\n"
        text += "\n"

    if improvements:
        text += "<b>Что улучшить:</b>\n"
        for i in improvements:
            text += f"  {i['improvement']}: <b>{i['cnt']}</b>\n"
        text += "\n"

    if events:
        text += "<b>Конкретное событие:</b>\n"
        for e in events:
            text += f"  {e['q3_event']}: <b>{e['cnt']}</b>\n"
        text += "\n"

    if recent:
        text += "<b>Последние 5:</b>\n"
        for r in recent:
            name = r['username'] or r['first_name'] or f"ID:{r['user_id']}"
            reason = r['reason_category'] or '—'
            date = str(r['left_at'])[:10] if r['left_at'] else '—'
            text += f"  @{name} ({date}): {reason}\n"

    if len(text) > 4000:
        text = text[:3950] + "\n\n<i>...обрезано</i>"

    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="owner_dashboard")
        ]])
    )
