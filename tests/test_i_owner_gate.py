# tests/test_i_owner_gate.py
import asyncio
import pytest
import handlers.admin_moderation as am


class _Ctx:
    def __init__(self): self.chat_data = {}; self.user_data = {}


def _run(coro): return asyncio.get_event_loop().run_until_complete(coro)


async def _aw(v): return v


def test_off_context_none_old_path(monkeypatch):
    # context=None → ветка I пропущена, идём по старой логике.
    monkeypatch.setattr(am, 'OWNER_ID', 111, raising=False)
    monkeypatch.setattr('bot_permissions.user_has', lambda *a, **k: _aw(False))
    monkeypatch.setattr('database.db_friend.is_deputy', lambda *a, **k: _aw(False))
    assert _run(am._is_owner_or_deputy(222, context=None)) is False


def test_owner_id_shortcut_still_first(monkeypatch):
    from config import OWNER_ID
    assert _run(am._is_owner_or_deputy(OWNER_ID, context=None)) is True


def test_flag_on_ws_owner_true(monkeypatch):
    # context задан, is_ws_owner True → _is_owner_or_deputy True (per-WS).
    monkeypatch.setattr('bot_core.ws_role.is_ws_owner', lambda *a, **k: True)
    assert _run(am._is_owner_or_deputy(8376708692, context=_Ctx())) is True


def test_flag_on_ws_not_owner_falls_through(monkeypatch):
    # is_ws_owner False → не теряем старый путь (fallback).
    monkeypatch.setattr('bot_core.ws_role.is_ws_owner', lambda *a, **k: False)
    monkeypatch.setattr('bot_permissions.user_has', lambda *a, **k: _aw(False))
    monkeypatch.setattr('database.db_friend.is_deputy', lambda *a, **k: _aw(False))
    assert _run(am._is_owner_or_deputy(424242, context=_Ctx())) is False
