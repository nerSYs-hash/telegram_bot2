"""Срез D (V1.17.0g): команда /login — вызвать LoginUrl-кнопку в любой момент.

Точка-возврата если юзер закрыл коннект-DM + готовый крючок для хаба C.
За флагом LOGIN_URL_BUTTON: OFF → команда молчит (байт-в-байт, как будто
её нет).
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot_core.login_button import login_keyboard, login_url_enabled

logger = logging.getLogger(__name__)


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not login_url_enabled():
        return  # флаг OFF → неактивна
    msg = update.effective_message
    if msg is None:
        return
    try:
        await msg.reply_text(
            "🔓 <b>Твой кабинет Pulse SaaS</b>\n"
            "Один тап — и ты внутри, без пароля.",
            parse_mode="HTML",
            reply_markup=login_keyboard(),
        )
    except Exception as e:
        logger.warning(f"/login reply failed: {e}")
