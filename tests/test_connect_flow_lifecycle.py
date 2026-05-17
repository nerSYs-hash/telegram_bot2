import os
from bot_core.connect_flow import connect_flow_v2_enabled


def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    assert connect_flow_v2_enabled() is False


def test_flag_on_truthy(monkeypatch):
    for v in ("1", "true", "YES", "on"):
        monkeypatch.setenv("CONNECT_FLOW_V2", v)
        assert connect_flow_v2_enabled() is True


def test_flag_off_falsy(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "0")
    assert connect_flow_v2_enabled() is False
