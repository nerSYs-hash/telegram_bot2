"""V1.17.0h fix: connect_chat CallbackQueryHandler не должен затеняться
беспаттерновым catch-all `handle_callback`.

Баг (подпроект F, V1.17.0c): catch-all `CallbackQueryHandler(handle_callback)`
зарегистрирован в группе 0 БЕЗ паттерна → ловит любой callback и срабатывает
первым; профильный `^connect_chat:` хендлер в той же группе зарегистрирован
позже и до него очередь не доходит. Кнопки подключения чата мертвы на проде.

Регрессия-гард: в группе 0 хендлер с паттерном `^connect_chat:` обязан стоять
РАНЬШЕ первого беспаттернового CallbackQueryHandler.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from telegram.ext import Application, CallbackQueryHandler

import bot as bot_module


def _fake_bot_with_real_app():
    app = (
        Application.builder()
        .token("123456:dummy")
        .updater(None)
        .job_queue(None)
        .build()
    )
    fake = SimpleNamespace(
        application=app,
        db=MagicMock(),
        callback_handler=MagicMock(),
        message_handler=MagicMock(),
        command_handler=MagicMock(),
        target_chat_id=0,
        main_admin_id=0,
        bot_username="testbot",
        handle_join_request=lambda *a, **k: None,
        error_handler=lambda *a, **k: None,
        resolve_workspace_middleware=lambda *a, **k: None,
    )
    bot_module.TelegramBot.setup_handlers(fake)
    return app


def test_connect_chat_handler_precedes_catchall_in_group0():
    app = _fake_bot_with_real_app()
    group0 = app.handlers[0]

    idx_connect = None
    idx_catchall = None
    for i, h in enumerate(group0):
        if not isinstance(h, CallbackQueryHandler):
            continue
        pat = getattr(h, "pattern", None)
        if pat is None and idx_catchall is None:
            idx_catchall = i
        elif pat is not None and pat.search("connect_chat:7:1") and idx_connect is None:
            idx_connect = i

    assert idx_connect is not None, "connect_chat CallbackQueryHandler не зарегистрирован в группе 0"
    assert idx_catchall is not None, "беспаттерновый catch-all CallbackQueryHandler не найден (тест устарел?)"
    assert idx_connect < idx_catchall, (
        f"connect_chat (idx={idx_connect}) затеняется беспаттерновым "
        f"catch-all (idx={idx_catchall}) — кнопки подключения чата мертвы"
    )
