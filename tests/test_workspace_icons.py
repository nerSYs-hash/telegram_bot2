"""V1.17.0j: тесты флага WORKSPACE_ICONS и cache_dir."""
from bot_core.workspace_icons import workspace_icons_enabled, cache_dir


def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("WORKSPACE_ICONS", raising=False)
    assert workspace_icons_enabled() is False


def test_flag_on_truthy(monkeypatch):
    for v in ("1", "true", "YES", "on"):
        monkeypatch.setenv("WORKSPACE_ICONS", v)
        assert workspace_icons_enabled() is True


def test_flag_off_falsy(monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS", "0")
    assert workspace_icons_enabled() is False


def test_cache_dir_env_override(monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", "/tmp/custom")
    assert cache_dir() == "/tmp/custom"


def test_cache_dir_default_is_non_empty(monkeypatch):
    monkeypatch.delenv("WORKSPACE_ICONS_CACHE_DIR", raising=False)
    # дефолт зависит от ОС, главное — непустая строка с разделителями
    val = cache_dir()
    assert isinstance(val, str) and 'ws_icons' in val
