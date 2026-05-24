"""Тесты дефолт-сидинга module_toggles для новых workspace.

V1.17.0k3: при create_workspace вызывается seed_default_modules,
который в зависимости от is_pulse_themed включает либо утилитарный
набор (generic), либо расширенный (Pulse). Идемпотентен.
"""
import sqlite3
import pytest

from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.migrations.module_toggles import up as up_module_toggles
from database.db_workspaces import create_workspace
from database.db_module_toggles import (
    seed_default_modules, get_modules,
    DEFAULT_GENERIC_ENABLED, DEFAULT_PULSE_ENABLED, VALID_MODULE_IDS,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    up_create_workspaces_tables(c)
    up_module_toggles(c)
    yield c
    c.close()


def _enabled_set(conn, ws_id):
    """Множество module_id с is_enabled=1 для данного ws."""
    return {
        m['id'] for m in get_modules(conn, ws_id)
        if m['is_enabled']
    }


def test_seed_lists_valid_against_catalog():
    """Регрессия: оба seed-списка содержат только реальные module_id."""
    for mid in DEFAULT_GENERIC_ENABLED:
        assert mid in VALID_MODULE_IDS, f"generic seed: {mid} not in catalog"
    for mid in DEFAULT_PULSE_ENABLED:
        assert mid in VALID_MODULE_IDS, f"pulse seed: {mid} not in catalog"


def test_generic_seed_enables_utility_only(conn):
    """is_pulse_themed=False → только утилитарные модули."""
    ws_id = create_workspace(conn, 'Generic Test', owner_user_id=42, is_pulse_themed=False)
    enabled = _enabled_set(conn, ws_id)
    assert enabled == set(DEFAULT_GENERIC_ENABLED)
    # Pulse-фичи остались OFF
    assert 'mining'   not in enabled
    assert 'lottery'  not in enabled
    assert 'bbs_pulse' not in enabled


def test_pulse_seed_enables_extended(conn):
    """is_pulse_themed=True → расширенный набор с Pulse-фичами."""
    ws_id = create_workspace(conn, 'Pulse Test', owner_user_id=42, is_pulse_themed=True)
    enabled = _enabled_set(conn, ws_id)
    assert enabled == set(DEFAULT_PULSE_ENABLED)
    # Утилитарные тоже включены — pulse-набор включает generic-набор
    for mid in DEFAULT_GENERIC_ENABLED:
        assert mid in enabled, f"{mid} должен быть в Pulse-сиде"
    # Mining/lottery/bbs включены
    assert 'mining'   in enabled
    assert 'lottery'  in enabled
    assert 'bbs_pulse' in enabled


def test_seed_is_idempotent(conn):
    """Повторный seed не перезаписывает явный OFF владельца.

    Сценарий: владелец после создания ws выключил mining (с reason).
    Если seed вызвать повторно (например, во время миграции), он
    НЕ должен снова включить mining.
    """
    ws_id = create_workspace(conn, 'Test', owner_user_id=42, is_pulse_themed=True)
    assert 'mining' in _enabled_set(conn, ws_id)

    # Владелец выключает mining
    from database.db_module_toggles import set_module_state
    set_module_state(conn, ws_id, 'mining', is_enabled=False,
                     reason='не нужно для нашего чата', user_id=42)
    assert 'mining' not in _enabled_set(conn, ws_id)

    # Повторный сид
    inserted = seed_default_modules(conn, ws_id, is_pulse_themed=True, user_id=0)
    assert inserted == 0, 'повторный seed не должен создавать новых строк'
    assert 'mining' not in _enabled_set(conn, ws_id), \
        'явный OFF владельца должен пережить повторный seed'


def test_create_workspace_seeds_in_one_call(conn):
    """Дымовой: create_workspace без отдельного вызова seed — модули включены."""
    ws_id = create_workspace(conn, 'Smoke', owner_user_id=99, is_pulse_themed=False)
    enabled = _enabled_set(conn, ws_id)
    assert 'statistics' in enabled
    assert 'triggers'   in enabled
    assert 'journal'    in enabled
    # История seed-операций записана
    hist = conn.execute(
        "SELECT module_id, action, reason FROM module_toggle_history "
        "WHERE workspace_id=? ORDER BY module_id",
        (ws_id,)
    ).fetchall()
    assert len(hist) == len(DEFAULT_GENERIC_ENABLED)
    assert all(h[1] == 'enable' for h in hist)
    assert all('seed' in (h[2] or '') for h in hist)


def test_create_workspace_without_module_toggles_table_does_not_break(tmp_path):
    """Регрессия: если module_toggles ещё нет (старая схема), create_workspace
    всё равно работает — seed silently no-op."""
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    up_create_workspaces_tables(c)
    # module_toggles намеренно НЕ создаём
    ws_id = create_workspace(c, 'Legacy', owner_user_id=1)
    assert ws_id > 0
