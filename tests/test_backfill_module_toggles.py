"""Тесты миграции бэкфилла module_toggles (V1.17.0h0b/h3)."""

import runpy
import sqlite3
import sys
from database.migrations.module_toggles import up


def test_backfill_inserts_expected_modules(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    up(conn)
    conn.close()

    sys.argv = ["backfill", str(db)]
    runpy.run_path("scripts/backfill_module_toggles_ws1.py", run_name="__main__")

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT module_id FROM module_toggles WHERE workspace_id=1 AND is_enabled=1"
    ).fetchall()
    ids = {r[0] for r in rows}
    assert "triggers" in ids
    assert "horoscope" in ids
    assert "sprints" not in ids
    assert "combos" not in ids


def test_backfill_is_idempotent(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    up(conn)
    conn.close()

    sys.argv = ["backfill", str(db)]
    runpy.run_path("scripts/backfill_module_toggles_ws1.py", run_name="__main__")
    runpy.run_path("scripts/backfill_module_toggles_ws1.py", run_name="__main__")

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT COUNT(*) FROM module_toggle_history WHERE workspace_id=1"
    ).fetchone()
    # V1.17.0k3: список переехал в DEFAULT_PULSE_ENABLED (общий для backfill +
    # seed нового Pulse-ws). Сверяем по живому источнику, а не по магическому числу.
    from database.db_module_toggles import DEFAULT_PULSE_ENABLED
    assert rows[0] == len(DEFAULT_PULSE_ENABLED)
