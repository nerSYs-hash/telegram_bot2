"""/get_thread_id — узнать chat_id и thread_id текущего топика.

V1.17.0c6 (F follow-up): пока UI настройки топиков не выпилен, владельцу
нужен способ узнать thread_id внутри supergroup-форума, чтобы прописать
APPLICATIONS_THREAD_ID/BUG_THREAD_BOT/BUG_THREAD_SITE/DOSSIER_THREAD_ID
в `.env`.

Использование: зайди в топик, напиши `/get_thread_id`. Бот ответит:
  📍 chat_id: -1001234567890
  🧵 thread_id: 42 (или «нет, не в топике»)
"""
import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def get_thread_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat = msg.chat
    thread_id = msg.message_thread_id  # None если не в топике / не forum

    if thread_id is None:
        text = (
            f"📍 <b>chat_id</b>: <code>{chat.id}</code>\n"
            f"🧵 <b>thread_id</b>: <i>—</i>  (сообщение НЕ внутри топика)\n\n"
            f"Чтобы узнать ID топика — отправь эту команду <b>внутри</b> нужного топика."
        )
    else:
        text = (
            f"📍 <b>chat_id</b>: <code>{chat.id}</code>\n"
            f"🧵 <b>thread_id</b>: <code>{thread_id}</code>\n\n"
            f"Скопируй число и пропиши в <code>.env</code> на сервере, например:\n"
            f"<code>APPLICATIONS_THREAD_ID={thread_id}</code>\n\n"
            f"После правки .env: <code>systemctl restart pulsbot</code>"
        )
    try:
        await msg.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"/get_thread_id reply failed: {e}")
