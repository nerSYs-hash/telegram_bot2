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
    """Чистая in-memory БД с workspaces + bot_chats схемой."""
    c = sqlite3.connect(':memory:')
    up_create_workspaces_tables(c)
    c.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL DEFAULT 1,
        added_by_user_id INTEGER,
        title TEXT,
        chat_type TEXT,
        added_at TEXT
    )''')
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


# ── V1.17.0b3: helpers для onboarding flow ──

def test_get_workspaces_for_user_includes_owned(conn):
    from database.db_workspaces import get_workspaces_for_user
    create_workspace(conn, 'Mine', owner_user_id=42)
    rows = get_workspaces_for_user(conn, user_id=42)
    assert len(rows) == 1
    assert rows[0]['role'] == 'owner'
    assert rows[0]['members_count'] == 1
    assert rows[0]['chats_count'] == 0


def test_get_workspaces_for_user_filters_by_membership(conn):
    from database.db_workspaces import get_workspaces_for_user
    create_workspace(conn, 'WS A', owner_user_id=1)
    create_workspace(conn, 'WS B', owner_user_id=2)
    add_member(conn, 1, 99, 'admin')
    rows = get_workspaces_for_user(conn, user_id=99)
    assert len(rows) == 1
    assert rows[0]['name'] == 'WS A'
    assert rows[0]['role'] == 'admin'


def test_get_workspace_details_returns_members_and_chats(conn):
    from database.db_workspaces import get_workspace_details, add_bot_chat
    ws_id = create_workspace(conn, 'X', owner_user_id=1)
    add_member(conn, ws_id, 99, 'admin')
    add_bot_chat(conn, chat_id=-100, workspace_id=ws_id, added_by=1,
                 title='Main', chat_type='supergroup')
    details = get_workspace_details(conn, workspace_id=ws_id)
    assert details['workspace']['name'] == 'X'
    assert len(details['members']) == 2  # owner + admin
    assert len(details['chats']) == 1
    assert details['chats'][0]['title'] == 'Main'


def test_update_workspace_name(conn):
    from database.db_workspaces import update_workspace_name
    ws_id = create_workspace(conn, 'OLD', owner_user_id=1)
    update_workspace_name(conn, workspace_id=ws_id, new_name='NEW')
    ws = get_workspace(conn, ws_id)
    assert ws.name == 'NEW'


def test_get_workspace_by_chat_returns_id_or_none(conn):
    from database.db_workspaces import add_bot_chat, get_workspace_by_chat
    ws_id = create_workspace(conn, 'WS', owner_user_id=1)
    add_bot_chat(conn, chat_id=-200, workspace_id=ws_id, added_by=1,
                 title='C', chat_type='group')
    assert get_workspace_by_chat(conn, -200) == ws_id
    assert get_workspace_by_chat(conn, -99999) is None


# Note: Database.get_site_user и Database.get_workspace_by_chat — тонкие
# обёртки над SQL/db_workspaces, тестируются интеграционно через
# test_bot_membership.py (fake _DB class) и live smoke.
