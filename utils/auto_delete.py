#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils/auto_delete.py — автоматическое удаление сообщений бота в главном чате.

Реализует три поведения:
1. Удаление команд пользователей (/balance, /top …) из главного чата сразу
   после получения — через обработчик группы -1 (delete_user_command_in_main_chat).
2. Chain-delete бот-ответов: когда приходит следующий бот-ответ — предыдущий
   удаляется немедленно; если нового нет — удаляется через AUTODEL_DELAY сек.
3. Исключение для триггеров: устанавливаем контекстную переменную _IN_TRIGGER
   перед вызовом триггерного кода — патч проверяет её и не регистрирует сообщение.
"""

from __future__ import annotations

import contextvars
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram.ext import Application

logger = logging.getLogger(__name__)

# ── Сколько секунд ждать перед удалением последнего бот-сообщения ────────────
AUTODEL_DELAY = 60

# ── Команды с отложенным удалением: команда → задержка в секундах ─────────────
_DELAYED_CMDS: dict[str, int] = {
    '/tip': 5,
}

# ── Ключ в bot_data для хранения текущего отслеживаемого сообщения ───────────
_CHAIN_KEY = '_autodel_chain_bot'

# ── ContextVar: True, когда выполняется триггерный код ───────────────────────
_IN_TRIGGER: contextvars.ContextVar[bool] = contextvars.ContextVar(
    'autodel_in_trigger', default=False
)


# ═══════════════════════════════════════════════════════════════════════════════
#  ПУБЛИЧНЫЙ API
# ═══════════════════════════════════════════════════════════════════════════════

class trigger_scope:  # noqa: N801
    """
    Контекстный менеджер: любые send_message/send_photo внутри блока
    НЕ будут зарегистрированы в цепочке автоудаления.

    Использование:
        async with trigger_scope():
            await process_triggers(...)
    """

    def __init__(self):
        self._token = None

    async def __aenter__(self):
        self._token = _IN_TRIGGER.set(True)
        return self

    async def __aexit__(self, *_):
        if self._token is not None:
            _IN_TRIGGER.reset(self._token)


async def delete_user_command_in_main_chat(update, context) -> None:
    """
    Обработчик группы -1.
    Удаляет сообщение-команду пользователя (/balance, /top …) из главного чата.
    Команды из _DELAYED_CMDS удаляются с заданной задержкой, остальные — мгновенно.
    """
    msg = update.message
    if not msg:
        return

    text = (msg.text or '').split()[0].split('@')[0].lower()
    delay = _DELAYED_CMDS.get(text)

    if delay:
        try:
            context.application.job_queue.run_once(
                _do_delete_job,
                when=delay,
                data={'chat_id': msg.chat_id, 'msg_id': msg.message_id},
                name=f'cmd_del_{msg.message_id}',
            )
            logger.debug(f'auto_delete: scheduled command {text} deletion in {delay}s')
        except Exception as e:
            logger.debug(f'auto_delete: delayed command delete schedule failed: {e}')
        return

    try:
        await msg.delete()
        logger.debug(
            f'auto_delete: deleted command {text} '
            f'from user {update.effective_user.id}'
        )
    except Exception as e:
        logger.debug(f'auto_delete: command delete failed: {e}')


def patch_bot_for_autodelete(bot, application: 'Application', target_chat_id: int) -> None:
    """
    Monkey-patch методов бота для chain-delete.

    Патчит send_message / send_photo / send_video / send_animation / send_audio /
    send_document. При каждом вызове:
      - если чат == target_chat_id AND не внутри trigger_scope → регистрируем.
      - иначе — пропускаем, не трогаем.

    Вызывать ПОСЛЕ application.build() (в post_init).
    """
    _METHODS = (
        'send_message',
        'send_photo',
        'send_video',
        'send_animation',
        'send_audio',
        'send_document',
        'send_sticker',
        'send_voice',
    )

    for method_name in _METHODS:
        original = getattr(bot.__class__, method_name, None)
        if original is None:
            continue

        # Захватываем переменные в замыкание через аргументы функции
        def _make_wrapper(orig_method, meth_name):
            async def wrapper(self_bot, *args, **kwargs):
                # Потребляем наш кастомный флаг, не передавая его в Telegram API
                no_chain = kwargs.pop('_no_chain', False)
                msg = await orig_method(self_bot, *args, **kwargs)
                if not no_chain and not _IN_TRIGGER.get():
                    _chain_register(application, msg, target_chat_id)
                return msg
            wrapper.__name__ = meth_name
            return wrapper

        setattr(bot.__class__, method_name, _make_wrapper(original, method_name))
        logger.debug(f'auto_delete: patched Bot.{method_name}')

    logger.info(f'auto_delete: bot patched for chain-delete (chat {target_chat_id})')


# ═══════════════════════════════════════════════════════════════════════════════
#  ВНУТРЕННИЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════════════════════

def _chain_register(application: 'Application', message, target_chat_id: int) -> None:
    """
    Синхронно регистрирует сообщение в цепочке:
      1. Предыдущее сообщение: отменяем таймер, ставим немедленное удаление.
      2. Новое сообщение: ставим удаление через AUTODEL_DELAY.
    """
    if message is None:
        return
    # Определяем chat_id из объекта Message
    chat_id = getattr(message, 'chat_id', None)
    if chat_id is None and hasattr(message, 'chat'):
        chat_id = message.chat.id
    if chat_id != target_chat_id:
        return

    msg_id = message.message_id

    prev = application.bot_data.pop(_CHAIN_KEY, None)
    if prev:
        # Отменяем таймер предыдущего сообщения
        try:
            prev['job'].schedule_removal()
        except Exception:
            pass
        # Немедленное удаление предыдущего
        try:
            application.job_queue.run_once(
                _do_delete_job,
                when=0,
                data={'chat_id': prev['chat_id'], 'msg_id': prev['msg_id']},
                name=f'chain_del_prev_{prev["msg_id"]}',
            )
        except Exception as e:
            logger.debug(f'auto_delete: prev-delete schedule failed: {e}')

    # Таймер на текущее сообщение
    try:
        job = application.job_queue.run_once(
            _do_delete_job,
            when=AUTODEL_DELAY,
            data={'chat_id': chat_id, 'msg_id': msg_id},
            name=f'chain_del_{msg_id}',
        )
        application.bot_data[_CHAIN_KEY] = {
            'chat_id': chat_id,
            'msg_id': msg_id,
            'job': job,
        }
        logger.debug(f'auto_delete: registered msg {msg_id} for deletion in {AUTODEL_DELAY}s')
    except Exception as e:
        logger.debug(f'auto_delete: new-delete schedule failed: {e}')


async def _do_delete_job(context) -> None:
    """Job: удаляет сообщение и очищает запись в bot_data."""
    d = context.job.data
    try:
        await context.bot.delete_message(chat_id=d['chat_id'], message_id=d['msg_id'])
        logger.debug(f'auto_delete: deleted msg {d["msg_id"]} from chat {d["chat_id"]}')
    except Exception:
        pass
    # Убираем из bot_data если это последнее отслеживаемое сообщение
    cur = context.bot_data.get(_CHAIN_KEY)
    if cur and cur.get('msg_id') == d['msg_id']:
        context.bot_data.pop(_CHAIN_KEY, None)
