"""ChatMemberHandler: само-онбординг при добавлении бота в чат.

Срабатывает на `my_chat_member` event. Если бот добавлен в новый чат
пользователем зарегистрированным на сайте — создаёт workspace и
привязывает чат. Если from_user не зарегистрирован или чат уже занят
другим workspace — пишет в чат причину и leave_chat.
"""
import logging
import os

from database.db_workspaces import create_workspace, add_bot_chat
from bot_core.workspace_context import invalidate_cache

logger = logging.getLogger(__name__)

SITE_URL = os.getenv('SITE_URL', 'https://puls-chat.ru')


async def on_bot_added_to_chat(update, context, db):
    """Обработчик ChatMemberHandler.MY_CHAT_MEMBER.

    1. Игнорировать события не про self (новый user != self.bot.id).
    2. Если status in (member/administrator):
       - Проверить что chat не привязан → иначе leave + сообщение.
       - Проверить что from_user зарегистрирован → иначе leave + сообщение.
       - Создать workspace, привязать chat, нотифай в чат + DM владельцу.
    """
    new = update.my_chat_member.new_chat_member
    if new.user.id != context.bot.id:
        return

    if new.status not in ('member', 'administrator'):
        # left/kicked/restricted — отдельный flow (не в этом подпроекте)
        return

    chat = update.my_chat_member.chat
    from_user = update.my_chat_member.from_user
    chat_id = chat.id
    chat_title = chat.title or f"Чат {chat_id}"

    # Check 1: chat already bound to another workspace?
    existing_ws = db.get_workspace_by_chat(chat_id)
    if existing_ws is not None:
        try:
            await context.bot.send_message(
                chat_id,
                "❌ Этот чат уже привязан к другому сообществу на Pulse SaaS."
            )
        except Exception as e:
            logger.warning(f"send_message (already bound) failed: {e}")
        try:
            await context.bot.leave_chat(chat_id)
        except Exception as e:
            logger.warning(f"leave_chat (already bound) failed: {e}")
        return

    # Check 2: from_user registered on site?
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

    # Create workspace + chat binding (create_workspace сам добавит owner в members)
    ws_id = create_workspace(db.conn, chat_title, owner_user_id=from_user.id)
    add_bot_chat(db.conn, chat_id, ws_id, added_by=from_user.id,
                 title=chat_title, chat_type=chat.type)
    invalidate_cache(chat_id)
    logger.info(
        f"Created workspace_id={ws_id} for chat={chat_id} owner={from_user.id}"
    )

    # Notify in-chat + DM
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
