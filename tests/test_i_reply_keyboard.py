# tests/test_i_reply_keyboard.py
import pytest
from handlers.commands.system_commands import get_main_reply_keyboard


class _DB:
    def is_feature_enabled(self, _): return True
    def get_user(self, _): return {'is_owner': 0, 'is_admin': 0}


class _Ctx:
    def __init__(self): self.chat_data = {}; self.user_data = {}


def _btn_texts(markup):
    return [b.text for row in markup.keyboard for b in row]


def test_owner_button_for_pulse_owner_unchanged():
    m = get_main_reply_keyboard(_DB(), user_id=111, main_admin_id=111)
    assert "👑 Панель Владельца" in _btn_texts(m)


def test_member_no_context_is_faq():
    m = get_main_reply_keyboard(_DB(), user_id=222, main_admin_id=111)
    assert "❓ FAQ" in _btn_texts(m)
    assert "👑 Панель Владельца" not in _btn_texts(m)


def test_ws_owner_with_context_gets_owner_button(monkeypatch):
    monkeypatch.setattr('bot_core.ws_role.is_ws_owner', lambda *a, **k: True)
    m = get_main_reply_keyboard(_DB(), user_id=8376708692,
                                main_admin_id=111, context=_Ctx())
    assert "👑 Панель Владельца" in _btn_texts(m)


def test_context_none_unchanged():
    # context=None → ветка I пропущена, обычный участник = FAQ.
    m = get_main_reply_keyboard(_DB(), user_id=8376708692,
                                main_admin_id=111, context=None)
    assert "❓ FAQ" in _btn_texts(m)
