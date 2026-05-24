"""V1.17.0h3: миграция economy_module_backfill + мостик is_econ_section_enabled.

Проверяем, что после разбивки каталога economy → гранулы:
  - 9 эконом-модулей включаются для ws=1;
  - устаревшая строка `economy` убирается;
  - явное OFF от владельца не перетирается;
  - миграция идемпотентна;
  - db_manager.is_econ_section_enabled читает именно module_toggles.
"""
import sqlite3

from database.migrations.module_toggles import up as up_modules
from database.migrations.economy_module_backfill import up as up_econ, ECONOMY_MODULES
from database.db_module_toggles import set_module_state, is_module_enabled


def _fresh():
    conn = sqlite3.connect(":memory:")
    up_modules(conn)
    return conn


def test_backfill_enables_all_nine_economy_modules():
    conn = _fresh()
    up_econ(conn)
    for mid in ECONOMY_MODULES:
        assert is_module_enabled(conn, 1, mid) is True, mid
    assert len(ECONOMY_MODULES) == 9


def test_backfill_removes_stale_economy_row():
    conn = _fresh()
    # старый backfill (h0g) вставлял единый `economy`
    conn.execute(
        "INSERT INTO module_toggles (workspace_id, module_id, is_enabled) VALUES (1, 'economy', 1)"
    )
    conn.commit()
    up_econ(conn)
    row = conn.execute(
        "SELECT 1 FROM module_toggles WHERE workspace_id=1 AND module_id='economy'"
    ).fetchone()
    assert row is None


def test_backfill_respects_explicit_owner_off():
    """Если владелец явно выключил модуль — backfill его НЕ включает обратно."""
    conn = _fresh()
    set_module_state(conn, 1, "mining", False, reason="не нужен", user_id=42)
    up_econ(conn)
    assert is_module_enabled(conn, 1, "mining") is False
    # остальные при этом всё равно включились
    assert is_module_enabled(conn, 1, "lottery") is True


def test_backfill_is_idempotent():
    conn = _fresh()
    up_econ(conn)
    up_econ(conn)
    rows = conn.execute(
        "SELECT COUNT(*) FROM module_toggle_history "
        "WHERE workspace_id=1 AND reason LIKE 'backfill V1.17.0h3%'"
    ).fetchone()
    assert rows[0] == 9  # ровно по одному enable на модуль


def test_backfill_only_touches_workspace_1():
    conn = _fresh()
    up_econ(conn)
    for mid in ECONOMY_MODULES:
        assert is_module_enabled(conn, 2, mid) is False, mid


def test_is_econ_section_enabled_reads_module_toggles():
    """Мостик: db_manager.is_econ_section_enabled берёт состояние из module_toggles."""
    from database.db_manager import Database

    conn = _fresh()
    up_econ(conn)

    class _FakeDB:
        _DEFAULT_WS_ID = 1

        def __init__(self, c):
            self.conn = c

    fake = _FakeDB(conn)
    # mining включён миграцией
    assert Database.is_econ_section_enabled(fake, "mining") is True

    # владелец выключает combos → мостик это видит
    from bot_core import module_guard as _mg
    _mg._CACHE.clear()
    set_module_state(conn, 1, "combos", False, reason="тест", user_id=1)
    _mg._CACHE.clear()
    assert Database.is_econ_section_enabled(fake, "combos") is False
    assert Database.is_econ_section_enabled(fake, "mining") is True
