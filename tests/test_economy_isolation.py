"""Тест изоляции экономических данных между workspaces.

Проверяет что:
1. economy_history фильтруется по workspace_id
2. economy_cancellations изолирована по workspace_id
3. get_econ читает значение только из своего workspace
4. economy_section_toggles изолирован

Note: economy_settings.key — PK глобально, поэтому для одинаковых ключей в
разных workspace тест использует разные ключи (см. multi_tenancy_pk_debt.md
для долга по composite PK).

V1.17.0a18.
"""
import os
import shutil
import sqlite3
import pytest

from database.migrations.multi_tenancy import (
    up_create_workspaces_tables, up_tenantize_existing_tables,
    up_seed_pulse_workspace,
)
from database.db_workspaces import create_workspace
from database import db_economy
from database import db_economy_history


@pytest.fixture
def db_pair(tmp_path):
    """Чистая БД с двумя workspace: ws=1 (Pulse-seed) и ws=2 (тестовый)."""
    src = os.path.join(os.path.dirname(__file__), '..', 'database', 'bot_database.db')
    dst = str(tmp_path / 'test.db')
    shutil.copy2(src, dst)
    conn = sqlite3.connect(dst)
    conn.row_factory = sqlite3.Row

    # Применяем миграцию если ещё не применена
    has_ws_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspaces'"
    ).fetchone()
    if not has_ws_table:
        up_create_workspaces_tables(conn)
        up_tenantize_existing_tables(conn)

    # Seed Pulse workspace (id=1) если не было
    ws1_exists = conn.execute('SELECT 1 FROM workspaces WHERE id=1').fetchone()
    if not ws1_exists:
        up_seed_pulse_workspace(conn, owner_user_id=12345)

    # Создаём 2-й workspace
    ws2 = create_workspace(conn, 'WS2 Test', owner_user_id=99999, is_pulse_themed=False)
    assert ws2 != 1, f"ws2 должен быть != 1, получили {ws2}"

    yield conn, 1, ws2
    conn.close()


class _DbWrap:
    """Минимальная обёртка под интерфейс db.cursor/db.conn что использует db_economy."""
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _seed_setting(conn, workspace_id, key, value):
    """Прямой INSERT setting'а для workspace."""
    conn.execute(
        "INSERT INTO economy_settings "
        "(workspace_id, key, category, label, value, value_type, is_enabled) "
        "VALUES (?, ?, 'test', 'Test Label', ?, 'float', 1)",
        (workspace_id, key, str(value))
    )
    conn.commit()


def test_get_econ_isolated_by_workspace(db_pair):
    """ws1 и ws2 имеют разные ключи — каждый читает только свои данные."""
    conn, ws1, ws2 = db_pair

    # Уникальные ключи для теста (PK debt — использовать одинаковые ключи нельзя)
    _seed_setting(conn, ws1, 'test.ws1_only', 100.0)
    _seed_setting(conn, ws2, 'test.ws2_only', 200.0)

    db = _DbWrap(conn)

    # ws1 видит свой ключ
    v = db_economy.get_econ(db, ws1, 'test.ws1_only', default=-1, value_type='float')
    assert v == 100.0

    # ws1 НЕ видит ключ ws2 (даже несмотря на PK key — фильтр workspace_id отсекает)
    v = db_economy.get_econ(db, ws1, 'test.ws2_only', default=-1, value_type='float')
    assert v == -1, f"ws1 не должен видеть данные ws2, получили {v}"

    # ws2 видит свой ключ
    v = db_economy.get_econ(db, ws2, 'test.ws2_only', default=-1, value_type='float')
    assert v == 200.0

    # ws2 НЕ видит ключ ws1
    v = db_economy.get_econ(db, ws2, 'test.ws1_only', default=-1, value_type='float')
    assert v == -1, f"ws2 не должен видеть данные ws1, получили {v}"


def test_section_toggles_isolated(db_pair):
    """is_section_enabled для категории независим между workspace.

    Note: PK у economy_section_toggles — `category`. Для теста используем
    разные категории-ключи (см. multi_tenancy_pk_debt.md).
    """
    conn, ws1, ws2 = db_pair

    conn.execute(
        "INSERT INTO economy_section_toggles (workspace_id, category, is_enabled) "
        "VALUES (?, ?, 0)",
        (ws1, 'mining_ws1')
    )
    conn.execute(
        "INSERT INTO economy_section_toggles (workspace_id, category, is_enabled) "
        "VALUES (?, ?, 1)",
        (ws2, 'mining_ws2')
    )
    conn.commit()

    db = _DbWrap(conn)
    # ws1 видит свою категорию выключенной
    assert db_economy.is_section_enabled(db, ws1, 'mining_ws1') is False
    # ws2 НЕ видит ws1.mining_ws1 — для ws2 эта категория не существует → default True
    assert db_economy.is_section_enabled(db, ws2, 'mining_ws1') is True


def test_history_isolated_by_workspace(db_pair):
    """economy_history фильтруется по workspace_id (одинаковый setting_key, разные WS)."""
    conn, ws1, ws2 = db_pair

    # Один и тот же setting_key, но workspace_id разные
    conn.execute(
        "INSERT INTO economy_history "
        "(workspace_id, setting_key, action, new_value, comment, changed_by, changed_by_role) "
        "VALUES (?, ?, 'edit', ?, 'ws1-edit', 1, 'owner')",
        (ws1, 'mining.rate', '50')
    )
    conn.execute(
        "INSERT INTO economy_history "
        "(workspace_id, setting_key, action, new_value, comment, changed_by, changed_by_role) "
        "VALUES (?, ?, 'edit', ?, 'ws2-edit', 99997, 'owner')",
        (ws2, 'mining.rate', '999')
    )
    conn.commit()

    db = _DbWrap(conn)
    # get_history_for_key возвращает dict {"entries": [...], "chart_data": [...]}
    rows_ws1 = db_economy_history.get_history_for_key(db, ws1, 'mining.rate', limit=10)
    comments_ws1 = [e['comment'] for e in rows_ws1['entries']]
    assert 'ws1-edit' in comments_ws1
    assert 'ws2-edit' not in comments_ws1, "ws1 не должен видеть history ws2"

    rows_ws2 = db_economy_history.get_history_for_key(db, ws2, 'mining.rate', limit=10)
    comments_ws2 = [e['comment'] for e in rows_ws2['entries']]
    assert 'ws2-edit' in comments_ws2
    assert 'ws1-edit' not in comments_ws2, "ws2 не должен видеть history ws1"


def test_cancellations_isolated(db_pair):
    """economy_cancellations фильтруется по workspace_id."""
    conn, ws1, ws2 = db_pair

    conn.execute(
        "INSERT INTO economy_cancellations "
        "(workspace_id, cancellation_type, target_user_id, source_tx_id, "
        " amount, mode, actually_deducted, comment, executed_by, executed_by_role) "
        "VALUES (?, 'pointwise', 555, 1, 100, 'deduct', 100, 'ws1-cancel', 1, 'owner')",
        (ws1,)
    )
    conn.execute(
        "INSERT INTO economy_cancellations "
        "(workspace_id, cancellation_type, target_user_id, source_tx_id, "
        " amount, mode, actually_deducted, comment, executed_by, executed_by_role) "
        "VALUES (?, 'pointwise', 666, 2, 200, 'deduct', 200, 'ws2-cancel', 99999, 'owner')",
        (ws2,)
    )
    conn.commit()

    db = _DbWrap(conn)
    cancels_ws1 = db_economy_history.get_cancellations(db, ws1, limit=50)
    comments_ws1 = [c['comment'] for c in cancels_ws1]
    assert 'ws1-cancel' in comments_ws1
    assert 'ws2-cancel' not in comments_ws1

    cancels_ws2 = db_economy_history.get_cancellations(db, ws2, limit=50)
    comments_ws2 = [c['comment'] for c in cancels_ws2]
    assert 'ws2-cancel' in comments_ws2
    assert 'ws1-cancel' not in comments_ws2


def test_metrics_isolated_by_workspace(db_pair):
    """get_economy_metrics возвращает данные только своего workspace (smoke)."""
    conn, ws1, ws2 = db_pair
    db = _DbWrap(conn)
    m1 = db_economy.get_economy_metrics(db, ws1)
    m2 = db_economy.get_economy_metrics(db, ws2)
    assert isinstance(m1, dict)
    assert isinstance(m2, dict)
