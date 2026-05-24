"""V1.17.0j3: тесты сервиса workspace_icon — pick / should_refresh / refresh."""
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.workspace_icon import (
    pick_chat_for_icon, should_refresh, refresh_workspace_icon,
)


def _conn():
    c = sqlite3.connect(":memory:")
    c.execute(
        "CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT, "
        "icon_file_id TEXT, icon_cached_at TIMESTAMP, "
        "icon_source TEXT DEFAULT 'tg', icon_local_path TEXT)"
    )
    c.execute(
        "CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, "
        "workspace_id INTEGER, role TEXT, removed_at TIMESTAMP, added_at TEXT)"
    )
    c.execute("INSERT INTO workspaces (id, name) VALUES (1, 'WS')")
    c.commit()
    return c


# ── pick_chat_for_icon ──

def test_pick_chat_prefers_main():
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-3, 1, 'journal', NULL, '2025-01-01')")
    c.execute("INSERT INTO bot_chats VALUES (-2, 1, 'admin',   NULL, '2025-01-02')")
    c.execute("INSERT INTO bot_chats VALUES (-1, 1, 'main',    NULL, '2025-01-03')")
    c.commit()
    assert pick_chat_for_icon(c, 1) == -1


def test_pick_chat_prefers_admin_over_journal_when_no_main():
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-3, 1, 'journal', NULL, '2025-01-01')")
    c.execute("INSERT INTO bot_chats VALUES (-2, 1, 'admin',   NULL, '2025-01-02')")
    c.commit()
    assert pick_chat_for_icon(c, 1) == -2


def test_pick_chat_skips_soft_removed():
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-1, 1, 'main',  CURRENT_TIMESTAMP, '2025-01-01')")
    c.execute("INSERT INTO bot_chats VALUES (-2, 1, 'admin', NULL, '2025-01-02')")
    c.commit()
    assert pick_chat_for_icon(c, 1) == -2


def test_pick_chat_empty_returns_none():
    c = _conn()
    assert pick_chat_for_icon(c, 1) is None


def test_pick_chat_falls_back_to_no_role():
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-1, 1, NULL, NULL, '2025-01-01')")
    c.commit()
    assert pick_chat_for_icon(c, 1) == -1


# ── should_refresh ──

def test_should_refresh_when_cached_at_null():
    assert should_refresh({'icon_cached_at': None}) is True


def test_should_refresh_when_missing_key():
    assert should_refresh({}) is True


def test_should_refresh_false_within_ttl():
    recent = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    assert should_refresh({'icon_cached_at': recent}, ttl_s=86400) is False


def test_should_refresh_true_when_stale():
    old = (datetime.utcnow() - timedelta(days=30)).isoformat()
    assert should_refresh({'icon_cached_at': old}, ttl_s=86400) is True


def test_should_refresh_garbage_value_is_true():
    """Неконвертируемая строка — считаем устаревшей (safer to refresh)."""
    assert should_refresh({'icon_cached_at': 'not-a-date'}) is True


# ── refresh_workspace_icon ──

@pytest.mark.asyncio
async def test_refresh_no_chats_writes_null_path(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    c = _conn()  # bot_chats пуст
    bot = MagicMock()
    bot.get_chat = AsyncMock()
    result = await refresh_workspace_icon(bot, c, 1)
    assert result is None
    row = c.execute(
        "SELECT icon_local_path, icon_cached_at FROM workspaces WHERE id=1"
    ).fetchone()
    assert row[0] is None and row[1] is not None
    bot.get_chat.assert_not_called()  # без чата — TG не зовём


@pytest.mark.asyncio
async def test_refresh_chat_without_photo_writes_null(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-1, 1, 'main', NULL, '2025-01-01')")
    c.commit()
    bot = MagicMock()
    chat = MagicMock()
    chat.photo = None
    bot.get_chat = AsyncMock(return_value=chat)
    result = await refresh_workspace_icon(bot, c, 1)
    assert result is None
    row = c.execute(
        "SELECT icon_local_path, icon_cached_at FROM workspaces WHERE id=1"
    ).fetchone()
    assert row[0] is None and row[1] is not None


@pytest.mark.asyncio
async def test_refresh_downloads_and_saves(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-1, 1, 'main', NULL, '2025-01-01')")
    c.commit()
    bot = MagicMock()
    chat = MagicMock()
    chat.photo = MagicMock()
    chat.photo.small_file_id = "abc123"
    bot.get_chat = AsyncMock(return_value=chat)
    file_obj = MagicMock()

    async def _fake_download(path):
        # имитируем реальное поведение PTB: записывает файл по пути
        with open(path, 'wb') as fh:
            fh.write(b"\xff\xd8\xff\xe0FAKE")

    file_obj.download_to_drive = AsyncMock(side_effect=_fake_download)
    bot.get_file = AsyncMock(return_value=file_obj)
    result = await refresh_workspace_icon(bot, c, 1)
    assert result is not None
    assert result.endswith("1.jpg")
    row = c.execute(
        "SELECT icon_file_id, icon_local_path, icon_source FROM workspaces WHERE id=1"
    ).fetchone()
    assert row[0] == "abc123"
    assert row[1] == result
    assert row[2] == 'tg'
    bot.get_chat.assert_awaited_once_with(-1)
    bot.get_file.assert_awaited_once_with("abc123")


@pytest.mark.asyncio
async def test_prewarm_iterates_only_stale(tmp_path, monkeypatch):
    """prewarm_all_workspaces: вызывает refresh только для устаревших ws."""
    from services.workspace_icon import prewarm_all_workspaces
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    c = _conn()
    # 3 ws: 1 свежий, 2 устаревший (старая дата), 3 без cached_at
    c.execute("INSERT INTO workspaces (id, name, icon_cached_at) VALUES (2, 'W2', ?)",
              ((datetime.utcnow() - timedelta(days=30)).isoformat(),))
    c.execute("INSERT INTO workspaces (id, name) VALUES (3, 'W3')")
    # ws=1 уже есть из _conn(), сделаем его свежим
    c.execute("UPDATE workspaces SET icon_cached_at=? WHERE id=1",
              ((datetime.utcnow() - timedelta(hours=1)).isoformat(),))
    # все имеют main-чат
    c.execute("INSERT INTO bot_chats VALUES (-1, 1, 'main', NULL, '2025-01-01')")
    c.execute("INSERT INTO bot_chats VALUES (-2, 2, 'main', NULL, '2025-01-01')")
    c.execute("INSERT INTO bot_chats VALUES (-3, 3, 'main', NULL, '2025-01-01')")
    c.commit()

    bot = MagicMock()
    chat = MagicMock(); chat.photo = None
    bot.get_chat = AsyncMock(return_value=chat)

    refreshed = await prewarm_all_workspaces(bot, c, ttl_s=86400)
    # обновили 2 (устаревший) и 3 (NULL), пропустили 1 (свежий)
    assert refreshed == 2
    assert bot.get_chat.await_count == 2


@pytest.mark.asyncio
async def test_prewarm_continues_on_per_ws_error(tmp_path, monkeypatch):
    """Ошибка одного ws не ломает обход остальных."""
    from services.workspace_icon import prewarm_all_workspaces
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    c = _conn()
    c.execute("INSERT INTO workspaces (id, name) VALUES (2, 'W2')")
    c.execute("INSERT INTO bot_chats VALUES (-1, 1, 'main', NULL, '2025-01-01')")
    c.execute("INSERT INTO bot_chats VALUES (-2, 2, 'main', NULL, '2025-01-01')")
    c.commit()

    call_count = {'n': 0}

    async def _get_chat(cid):
        call_count['n'] += 1
        if cid == -1:
            raise RuntimeError("TG flaky")
        chat = MagicMock(); chat.photo = None
        return chat

    bot = MagicMock()
    bot.get_chat = AsyncMock(side_effect=_get_chat)
    refreshed = await prewarm_all_workspaces(bot, c)
    # ws=1 упал, ws=2 норм → один успешный refresh
    assert refreshed == 1
    assert call_count['n'] == 2


@pytest.mark.asyncio
async def test_refresh_tg_error_does_not_crash_and_keeps_prev(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-1, 1, 'main', NULL, '2025-01-01')")
    # имитируем что когда-то уже была иконка
    c.execute(
        "UPDATE workspaces SET icon_local_path=?, icon_file_id=?, "
        "icon_cached_at=? WHERE id=1",
        (str(tmp_path / "1.jpg"), "old", "2025-01-01T00:00:00")
    )
    c.commit()
    bot = MagicMock()
    bot.get_chat = AsyncMock(side_effect=RuntimeError("TG 403"))
    result = await refresh_workspace_icon(bot, c, 1)
    assert result is None
    # запись о предыдущей иконке НЕ затёрта (хотим попробовать снова)
    row = c.execute(
        "SELECT icon_file_id, icon_local_path FROM workspaces WHERE id=1"
    ).fetchone()
    assert row[0] == "old"
    assert row[1] == str(tmp_path / "1.jpg")
