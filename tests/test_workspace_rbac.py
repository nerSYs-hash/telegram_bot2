# tests/test_workspace_rbac.py
import sqlite3
import pytest
from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import create_workspace, add_member
from api.workspace_rbac import resolve_ws_role


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    up_create_workspaces_tables(c)
    create_workspace(c, 'WS1', owner_user_id=42)          # ws id 1, owner=42
    create_workspace(c, 'WS2', owner_user_id=99)          # ws id 2, owner=99
    add_member(c, 1, 100, 'admin')                        # 100 admin in ws1
    add_member(c, 1, 101, 'moderator')                    # 101 moderator in ws1
    c.commit()
    yield c
    c.close()


def test_owner_maps_to_owner(conn):
    assert resolve_ws_role(conn, 42, 1, developer_id=0) == 'owner'

def test_admin_maps_to_deputy(conn):
    assert resolve_ws_role(conn, 100, 1, developer_id=0) == 'deputy'

def test_moderator_maps_to_admin(conn):
    assert resolve_ws_role(conn, 101, 1, developer_id=0) == 'admin'

def test_non_member_maps_to_user(conn):
    assert resolve_ws_role(conn, 100, 2, developer_id=0) == 'user'

def test_unknown_user_maps_to_user(conn):
    assert resolve_ws_role(conn, 777, 1, developer_id=0) == 'user'

def test_developer_is_godmode_everywhere(conn):
    # ws2 where 555 is not a member at all
    assert resolve_ws_role(conn, 555, 2, developer_id=555) == 'developer'

def test_developer_beats_membership(conn):
    # even if developer is a moderator somewhere, still 'developer'
    assert resolve_ws_role(conn, 555, 1, developer_id=555) == 'developer'
