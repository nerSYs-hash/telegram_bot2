"""ChatMemberHandler + callback flow для подключения чата к workspace.

V1.17.0c (подпроект F): вместо «один чат = одно сообщество» (b4) теперь:
- если from_user уже владеет одним или несколькими workspaces → бот спрашивает
  inline-кнопками: «Добавить к [имя]» или «Создать новое сообщество»;
- иначе — старое поведение (создать новый ws).

Тексты:
- если чат уже привязан к ТВОЕМУ ws → «уже подключён» (не leave);
- если к чужому → «привязан к другому сообществу» (leave).
"""
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db_workspaces import (
    create_workspace, add_bot_chat, get_workspaces_for_user,
)
from bot_core.workspace_context import invalidate_cache

logger = logging.getLogger(__name__)

SITE_URL = os.getenv('SITE_URL', 'https://puls-chat.ru')


async def on_bot_added_to_chat(update, context, db):
    """ChatMemberHandler.MY_CHAT_MEMBER — бот добавлен в чат.

    Сценарий:
    1. ignore если event не про self
    2. ignore если не member/administrator
    3. чат уже привязан к моему ws → «уже подключён»
    4. чат уже привязан к чужому ws → «привязан к другому» + leave
    5. from_user не зарегистрирован → reject + leave
    6. from_user уже owner ≥1 ws → inline-кнопки «к X» / «новое»
    7. иначе → создать новый ws (старое поведение)
    """
    new = update.my_chat_member.new_chat_member
    if new.user.id != context.bot.id:
        return

    if new.status not in ('member', 'administrator'):
        return

    chat = update.my_chat_member.chat
    from_user = update.my_chat_member.from_user
    chat_id = chat.id
    chat_title = chat.title or f"Чат {chat_id}"

    # 3+4. Already bound?
    existing_ws = db.get_workspace_by_chat(chat_id)
    if existing_ws is not None:
        user_wss = get_workspaces_for_user(db.conn, from_user.id)
        user_ws_ids = {w['id'] for w in user_wss}
        if existing_ws in user_ws_ids:
            try:
                await context.bot.send_message(
                    chat_id,
                    "ℹ️ Этот чат уже подключён к твоему сообществу на Pulse SaaS.\n"
                    f"Управление — на сайте: {SITE_URL}"
                )
            except Exception as e:
                logger.warning(f"send_message (already own) failed: {e}")
        else:
            try:
                await context.bot.send_message(
                    chat_id,
                    "❌ Этот чат уже привязан к другому сообществу на Pulse SaaS."
                )
            except Exception as e:
                logger.warning(f"send_message (already bound elsewhere) failed: {e}")
            try:
                await context.bot.leave_chat(chat_id)
            except Exception as e:
                logger.warning(f"leave_chat (already bound elsewhere) failed: {e}")
        return

    # 5. registered?
    site_user = db.get_site_user(from_user.id)
    if not site_user:
        try:
            await context.bot.send_message(
                chat_id,
                "❌ Тот, кто меня добавил, не зарегистрирован на сайте.\n"
                f"Зайди сюда: {SITE_URL}/login и попробуй снова."
            )
        except Exception as e:
            logger.warning(f"send_message (unregistered) failed: {e}")
        try:
            await context.bot.leave_chat(chat_id)
        except Exception as e:
            logger.warning(f"leave_chat (unregistered) failed: {e}")
        return

    # 6. user has existing workspaces? — ask via buttons
    user_wss = get_workspaces_for_user(db.conn, from_user.id)
    owned_wss = [w for w in user_wss if w.get('role') == 'owner']

    if owned_wss:
        buttons = []
        for w in owned_wss:
            buttons.append([InlineKeyboardButton(
                f"📂 К «{w['name']}»",
                callback_data=f"connect_chat:{w['id']}:{from_user.id}",
            )])
        buttons.append([InlineKeyboardButton(
            "🆕 Создать новое сообщество",
            callback_data=f"connect_chat:new:{from_user.id}",
        )])
        try:
            await context.bot.send_message(
                chat_id,
                f"👋 Привет! Я бот Pulse SaaS.\n\n"
                f"Куда подключить этот чат («{chat_title}»)?",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except Exception as e:
            logger.warning(f"send_message (choose ws) failed: {e}")
        return

    # 7. No existing workspaces → create new (legacy behavior)
    ws_id = create_workspace(db.conn, chat_title, owner_user_id=from_user.id)
    add_bot_chat(db.conn, chat_id, ws_id, added_by=from_user.id,
                 title=chat_title, chat_type=chat.type, role='main')
    invalidate_cache(chat_id)
    logger.info(
        f"Created workspace_id={ws_id} for chat={chat_id} owner={from_user.id}"
    )

    try:
        await context.bot.send_message(
            chat_id,
            f"✅ Сообщество «{chat_title}» подключено к Pulse SaaS.\n"
            f"Управление — на сайте: {SITE_URL}"
        )
    except Exception as e:
        logger.warning(f"send_message (success) failed: {e}")
    try:
        await context.bot.send_message(
            from_user.id,
            f"✅ Чат «{chat_title}» добавлен в твой кабинет.\n"
            f"Зайди на сайт чтобы настроить: {SITE_URL}"
        )
    except Exception as e:
        logger.warning(f"DM to owner failed: {e}")


async def on_connect_chat_callback(update, context: ContextTypes.DEFAULT_TYPE, db):
    """CallbackQueryHandler для кнопок «connect_chat:<ws_id|new>:<from_user_id>».

    Только тот юзер, кто добавил бота, может выбрать. Привязывает чат к
    выбранному ws или создаёт новый.
    """
    q = update.callback_query
    await q.answer()

    parts = q.data.split(':')
    if len(parts) != 3 or parts[0] != 'connect_chat':
        return
    target = parts[1]
    try:
        from_user_id = int(parts[2])
    except ValueError:
        return

    if q.from_user.id != from_user_id:
        await q.answer("Только тот, кто добавил бота, может выбрать.",
                       show_alert=True)
        return

    chat = q.message.chat
    chat_id = chat.id
    chat_title = chat.title or f"Чат {chat_id}"

    # Race: chat could have been bound by parallel event
    if db.get_workspace_by_chat(chat_id) is not None:
        try:
            await q.edit_message_text("ℹ️ Этот чат уже привязан.")
        except Exception:
            pass
        return

    if target == 'new':
        ws_id = create_workspace(db.conn, chat_title, owner_user_id=from_user_id)
        add_bot_chat(db.conn, chat_id, ws_id, added_by=from_user_id,
                     title=chat_title, chat_type=chat.type, role='main')
        invalidate_cache(chat_id)
        logger.info(f"Created NEW workspace_id={ws_id} for chat={chat_id}")
        try:
            await q.edit_message_text(
                f"✅ Создано новое сообщество «{chat_title}».\n"
                f"Настройка — на сайте: {SITE_URL}"
            )
        except Exception:
            pass
        return

    # Existing ws — validate ownership
    try:
        ws_id = int(target)
    except ValueError:
        return

    user_wss = get_workspaces_for_user(db.conn, from_user_id)
    ws = next((w for w in user_wss if w['id'] == ws_id and w.get('role') == 'owner'), None)
    if not ws:
        try:
            await q.edit_message_text(
                "❌ Сообщество не найдено или ты не его владелец."
            )
        except Exception:
            pass
        return

    add_bot_chat(db.conn, chat_id, ws_id, added_by=from_user_id,
                 title=chat_title, chat_type=chat.type, role=None)
    invalidate_cache(chat_id)
    logger.info(f"Bound chat={chat_id} to existing ws={ws_id} owner={from_user_id}")
    try:
        await q.edit_message_text(
            f"✅ Чат «{chat_title}» подключён к сообществу «{ws['name']}».\n"
            f"Назначь ему роль (Главный/Админ/Журнал) на сайте: {SITE_URL}"
        )
    except Exception:
        pass
