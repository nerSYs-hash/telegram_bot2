"""Декоратор @requires_module + cached is_module_enabled.

Кеш: {(ws_id, module_id): (is_enabled, version_seen_at_read, read_at_monotonic)}.
Инвалидация: если БД cache_version > version_seen — перечитываем.
TTL: дополнительно 30 c, чтобы избыточных lookups не было даже без bump.

На шаге 7.0 декоратор существует, но НЕ применяется ни к одному хэндлеру.
Применение — поштучно на шагах 7.1–7.4.
"""
import functools
import time
from typing import Callable

from database.db_module_toggles import is_module_enabled, get_cache_version

_CACHE: dict = {}
_TTL = 30.0


def _invalidate_cache_for_ws(workspace_id: int) -> None:
    """Очистить весь кеш для workspace (тестовый/админский хелпер)."""
    for k in list(_CACHE.keys()):
        if k[0] == workspace_id:
            _CACHE.pop(k, None)


def is_module_enabled_cached(conn, workspace_id: int, module_id: str) -> bool:
    """Чтение состояния модуля с кешем.

    Сначала смотрит cache_version в БД (дешёвый SELECT) — если совпадает
    с тем, что было при последнем чтении и TTL не истёк — отдаёт кеш.
    Иначе перечитывает is_module_enabled.
    """
    key = (workspace_id, module_id)
    now = time.monotonic()
    cur_version = get_cache_version(conn, workspace_id)
    cached = _CACHE.get(key)
    if cached is not None:
        value, seen_version, seen_at = cached
        if seen_version == cur_version and (now - seen_at) < _TTL:
            return value
    value = is_module_enabled(conn, workspace_id, module_id)
    _CACHE[key] = (value, cur_version, now)
    return value


def requires_module(module_id: str, *,
                    conn_provider: Callable,
                    ws_resolver: Callable):
    """Guard для PTB-хэндлера.

    Аргументы:
      module_id      — id модуля из shared/modules_catalog.json.
      conn_provider  — func(update, context) -> sqlite3.Connection.
      ws_resolver    — func(update, context) -> workspace_id (int).

    Поведение:
      Если модуль OFF — silent return (None). Иначе вызывает обёрнутый
      handler.
    """
    def deco(handler):
        @functools.wraps(handler)
        async def wrapped(update, context, *a, **kw):
            conn = conn_provider(update, context)
            ws_id = ws_resolver(update, context)
            if not is_module_enabled_cached(conn, ws_id, module_id):
                return None
            return await handler(update, context, *a, **kw)
        return wrapped
    return deco
