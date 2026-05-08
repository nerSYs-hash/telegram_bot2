"""Тесты CRUD для workspaces."""
import sqlite3
import pytest

from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import (
    create_workspace, get_workspace, list_workspaces_for_user,
    add_member, remove_member, get_member_role,
)


@pytest.fixture
def conn():
    """Чистая in-memory БД с workspaces схемой."""
    c = sqlite3.connect(':memory:')
    up_create_workspaces_tables(c)
    yield c
    c.close()


def test_create_workspace_inserts_owner_member(conn):
    ws_id = create_workspace(conn, 'Test WS', owner_user_id=42)
    assert ws_id == 1
    role = get_member_role(conn, ws_id, 42)
    assert role == 'owner'


def test_get_workspace_returns_data(conn):
    ws_id = create_workspace(
        conn, 'Test WS', owner_user_id=42, is_pulse_themed=True
    )
    ws = get_workspace(conn, ws_id)
    assert ws is not None
    assert ws.name == 'Test WS'
    assert ws.is_pulse_themed is True


def test_get_workspace_missing_returns_none(conn):
    assert get_workspace(conn, 999) is None


def test_list_workspaces_for_user_returns_only_member_of(conn):
    ws1 = create_workspace(conn, 'WS1', owner_user_id=42)
    ws2 = create_workspace(conn, 'WS2', owner_user_id=99)
    add_member(conn, ws2, 42, 'admin')

    user_ws_ids = {w.id for w in list_workspaces_for_user(conn, 42)}
    assert user_ws_ids == {ws1, ws2}

    other_ws_ids = {w.id for w in list_workspaces_for_user(conn, 99)}
    assert other_ws_ids == {ws2}


def test_add_member_invalid_role_raises(conn):
    ws_id = create_workspace(conn, 'WS', owner_user_id=1)
    with pytest.raises(ValueError):
        add_member(conn, ws_id, 2, 'superadmin')


def test_remove_owner_raises(conn):
    ws_id = create_workspace(conn, 'WS', owner_user_id=1)
    with pytest.raises(ValueError):
        remove_member(conn, ws_id, 1)


def test_remove_admin_works(conn):
    ws_id = create_workspace(conn, 'WS', owner_user_id=1)
    add_member(conn, ws_id, 2, 'admin')
    remove_member(conn, ws_id, 2)
    assert get_member_role(conn, ws_id, 2) is None
