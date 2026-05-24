"""Тесты module_guard (is_module_enabled / гарды модулей в боте)."""

import asyncio
import sqlite3
import pytest
from database.migrations.module_toggles import up
from database.db_module_toggles import set_module_state
from bot_core.module_guard import (
    is_module_enabled_cached, requires_module, _invalidate_cache_for_ws,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    up(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _clear_cache():
    # перед каждым тестом сбрасываем глобальный кеш guard'а
    from bot_core import module_guard as _mg
    _mg._CACHE.clear()
    yield


def test_disabled_by_default(conn):
    assert is_module_enabled_cached(conn, 1, "triggers") is False


def test_enabled_after_set(conn):
    set_module_state(conn, 1, "triggers", True, reason=None, user_id=42)
    _invalidate_cache_for_ws(1)
    assert is_module_enabled_cached(conn, 1, "triggers") is True


def test_cache_invalidates_on_version_bump(conn):
    assert is_module_enabled_cached(conn, 1, "triggers") is False
    set_module_state(conn, 1, "triggers", True, reason=None, user_id=42)
    # Version bumped inside set_module_state; cached helper must notice.
    assert is_module_enabled_cached(conn, 1, "triggers") is True


def test_requires_module_silent_when_off(conn):
    calls = []

    @requires_module("triggers", conn_provider=lambda *_: conn,
                     ws_resolver=lambda *_: 1)
    async def handler(update, ctx):
        calls.append("ran")

    asyncio.run(handler({"x": 1}, {}))
    assert calls == []


def test_requires_module_runs_when_on(conn):
    set_module_state(conn, 1, "triggers", True, reason=None, user_id=42)
    calls = []

    @requires_module("triggers", conn_provider=lambda *_: conn,
                     ws_resolver=lambda *_: 1)
    async def handler(update, ctx):
        calls.append("ran")

    asyncio.run(handler({"x": 1}, {}))
    assert calls == ["ran"]
