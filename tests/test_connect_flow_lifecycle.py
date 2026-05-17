import os
import sqlite3
import pytest
from bot_core.connect_flow import connect_flow_v2_enabled
from database.db_workspaces import (
    soft_remove_bot_chat, get_disconnected_bot_chat, get_workspace_by_chat,
)


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


def _conn_with_chat():
    conn = sqlite3.connect(":memory:")
    conn.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT,
        role TEXT, added_at TEXT, removed_at TIMESTAMP
    )''')
    conn.execute("INSERT INTO bot_chats (chat_id, workspace_id, role, removed_at) "
                 "VALUES (-100, 7, 'main', NULL)")
    conn.commit()
    return conn


def test_soft_remove_sets_removed_at_keeps_ws_and_role():
    conn = _conn_with_chat()
    soft_remove_bot_chat(conn, -100)
    row = conn.execute(
        "SELECT workspace_id, role, removed_at FROM bot_chats WHERE chat_id=-100"
    ).fetchone()
    assert row[0] == 7 and row[1] == 'main' and row[2] is not None


def test_get_disconnected_returns_ws_role_only_when_removed():
    conn = _conn_with_chat()
    assert get_disconnected_bot_chat(conn, -100) is None
    soft_remove_bot_chat(conn, -100)
    d = get_disconnected_bot_chat(conn, -100)
    assert d == {'workspace_id': 7, 'role': 'main'}


def test_get_workspace_by_chat_flag_off_unchanged(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    conn = _conn_with_chat()
    soft_remove_bot_chat(conn, -100)
    assert get_workspace_by_chat(conn, -100) == 7


def test_get_workspace_by_chat_flag_on_excludes_removed(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "1")
    conn = _conn_with_chat()
    assert get_workspace_by_chat(conn, -100) == 7
    soft_remove_bot_chat(conn, -100)
    assert get_workspace_by_chat(conn, -100) is None


# --- Task 4: C1 left/kicked soft-remove за флагом ---
from unittest.mock import AsyncMock, MagicMock
from database.migrations.multi_tenancy import up_create_workspaces_tables


def _lifecycle_db():
    conn = sqlite3.connect(":memory:")
    up_create_workspaces_tables(conn)
    conn.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT,
        role TEXT, added_at TEXT, removed_at TIMESTAMP)''')
    conn.execute('''CREATE TABLE users (user_id INTEGER PRIMARY KEY,
        username TEXT, first_name TEXT)''')

    class _DB:
        def __init__(self, c): self.conn = c
        def get_site_user(self, uid):
            r = self.conn.execute("SELECT user_id,username FROM users WHERE user_id=?", (uid,)).fetchone()
            return {'user_id': r[0], 'username': r[1]} if r else None
        def get_workspace_by_chat(self, cid):
            return get_workspace_by_chat(self.conn, cid)
    return _DB(conn)


def _left_update(chat_id):
    u = MagicMock()
    u.my_chat_member.new_chat_member.user.id = 999
    u.my_chat_member.new_chat_member.status = 'kicked'
    u.my_chat_member.chat.id = chat_id
    u.my_chat_member.chat.title = 'X'
    u.my_chat_member.chat.type = 'supergroup'
    u.my_chat_member.from_user.id = 42
    return u


def _ctx():
    c = MagicMock(); c.bot.id = 999
    c.bot.send_message = AsyncMock(); c.bot.leave_chat = AsyncMock()
    return c


@pytest.mark.asyncio
async def test_kicked_flag_off_hard_deletes(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    from handlers.bot_membership import on_bot_added_to_chat
    db = _lifecycle_db()
    db.conn.execute("INSERT INTO bot_chats (chat_id,workspace_id,role) VALUES (-100,1,'main')")
    db.conn.commit()
    await on_bot_added_to_chat(_left_update(-100), _ctx(), db)
    assert db.conn.execute("SELECT COUNT(*) FROM bot_chats WHERE chat_id=-100").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_kicked_flag_on_soft_removes(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "1")
    from handlers.bot_membership import on_bot_added_to_chat
    db = _lifecycle_db()
    db.conn.execute("INSERT INTO bot_chats (chat_id,workspace_id,role) VALUES (-100,1,'main')")
    db.conn.commit()
    await on_bot_added_to_chat(_left_update(-100), _ctx(), db)
    row = db.conn.execute(
        "SELECT workspace_id,role,removed_at FROM bot_chats WHERE chat_id=-100").fetchone()
    assert row == (1, 'main', row[2]) and row[2] is not None


# --- Task 5: C3 restore роли при повторном добавлении ---
def _added_update(chat_id, old_status='left', new_status='administrator'):
    u = MagicMock()
    u.my_chat_member.new_chat_member.user.id = 999
    u.my_chat_member.new_chat_member.status = new_status
    u.my_chat_member.old_chat_member.status = old_status
    u.my_chat_member.chat.id = chat_id
    u.my_chat_member.chat.title = 'X'
    u.my_chat_member.chat.type = 'supergroup'
    u.my_chat_member.from_user.id = 42
    return u


@pytest.mark.asyncio
async def test_reconnect_restores_role_no_menu(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "1")
    from handlers.bot_membership import on_bot_added_to_chat
    db = _lifecycle_db()
    db.conn.execute("INSERT INTO bot_chats (chat_id,workspace_id,role,removed_at) "
                    "VALUES (-100,1,'main',CURRENT_TIMESTAMP)")
    db.conn.commit()
    ctx = _ctx()
    await on_bot_added_to_chat(_added_update(-100), ctx, db)
    row = db.conn.execute(
        "SELECT workspace_id,role,removed_at FROM bot_chats WHERE chat_id=-100").fetchone()
    assert row[0] == 1 and row[1] == 'main' and row[2] is None  # restored
    sent = " ".join(str(c) for c in ctx.bot.send_message.call_args_list)
    assert "Куда подключить" not in sent


@pytest.mark.asyncio
async def test_reconnect_flag_off_unchanged(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    from handlers.bot_membership import on_bot_added_to_chat
    db = _lifecycle_db()
    db.conn.execute("INSERT INTO users (user_id,username) VALUES (42,'a')")
    db.conn.commit()
    ctx = _ctx()
    await on_bot_added_to_chat(_added_update(-100), ctx, db)
    assert get_workspace_by_chat(db.conn, -100) is not None


# --- Task 6: C9 каскад-очистка tenant-таблиц в delete_workspace ---
def test_delete_workspace_flag_off_keeps_tenant_data(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    from database.db_workspaces import delete_workspace
    conn = sqlite3.connect(":memory:")
    up_create_workspaces_tables(conn)
    conn.execute("CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, workspace_id INTEGER, role TEXT, removed_at TIMESTAMP)")
    conn.execute("CREATE TABLE economy_settings (workspace_id INTEGER, key TEXT, value TEXT)")
    conn.execute("INSERT INTO workspaces (id,name,owner_user_id,is_pulse_themed,plan) VALUES (9,'X',42,0,'free')")
    conn.execute("INSERT INTO economy_settings VALUES (9,'k','v')")
    conn.commit()
    delete_workspace(conn, 9)
    assert conn.execute("SELECT COUNT(*) FROM economy_settings WHERE workspace_id=9").fetchone()[0] == 1


def test_delete_workspace_flag_on_cascades(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "1")
    from database.db_workspaces import delete_workspace
    conn = sqlite3.connect(":memory:")
    up_create_workspaces_tables(conn)
    conn.execute("CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, workspace_id INTEGER, role TEXT, removed_at TIMESTAMP)")
    conn.execute("CREATE TABLE economy_settings (workspace_id INTEGER, key TEXT, value TEXT)")
    conn.execute("INSERT INTO workspaces (id,name,owner_user_id,is_pulse_themed,plan) VALUES (9,'X',42,0,'free')")
    conn.execute("INSERT INTO economy_settings VALUES (9,'k','v')")
    conn.commit()
    delete_workspace(conn, 9)
    assert conn.execute("SELECT COUNT(*) FROM economy_settings WHERE workspace_id=9").fetchone()[0] == 0


def test_delete_workspace_pulse_themed_still_refused(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "1")
    from database.db_workspaces import delete_workspace
    conn = sqlite3.connect(":memory:")
    up_create_workspaces_tables(conn)
    conn.execute("CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, workspace_id INTEGER, role TEXT, removed_at TIMESTAMP)")
    conn.execute("INSERT INTO workspaces (id,name,owner_user_id,is_pulse_themed,plan) VALUES (1,'P',42,1,'free')")
    conn.commit()
    import pytest as _pt
    with _pt.raises(ValueError):
        delete_workspace(conn, 1)


# --- Task 8: C4 привязка к существующему ws с выбором роли ---
@pytest.mark.asyncio
async def test_connect_existing_ws_binds_with_role(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "1")
    from handlers.bot_membership import on_connect_chat_callback
    db = _lifecycle_db()
    db.conn.execute("INSERT INTO users (user_id,username) VALUES (42,'a')")
    db.conn.execute("INSERT INTO workspaces (id,name,owner_user_id,is_pulse_themed,plan) VALUES (3,'W',42,0,'free')")
    db.conn.execute("INSERT INTO workspace_members (workspace_id,user_id,role) VALUES (3,42,'owner')")
    db.conn.commit()
    q = MagicMock()
    q.data = "connect_chat:3:42:admin"
    q.from_user.id = 42
    q.message.chat.id = -100
    q.message.chat.title = "C"
    q.message.chat.type = "supergroup"
    q.answer = AsyncMock(); q.edit_message_text = AsyncMock()
    upd = MagicMock(); upd.callback_query = q
    await on_connect_chat_callback(upd, MagicMock(), db)
    row = db.conn.execute("SELECT workspace_id,role FROM bot_chats WHERE chat_id=-100").fetchone()
    assert row == (3, 'admin')


@pytest.mark.asyncio
async def test_connect_callback_legacy_3parts_still_works(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    from handlers.bot_membership import on_connect_chat_callback
    db = _lifecycle_db()
    db.conn.execute("INSERT INTO users (user_id,username) VALUES (42,'a')")
    db.conn.execute("INSERT INTO workspaces (id,name,owner_user_id,is_pulse_themed,plan) VALUES (3,'W',42,0,'free')")
    db.conn.execute("INSERT INTO workspace_members (workspace_id,user_id,role) VALUES (3,42,'owner')")
    db.conn.commit()
    q = MagicMock()
    q.data = "connect_chat:3:42"   # legacy 3-part
    q.from_user.id = 42
    q.message.chat.id = -100
    q.message.chat.title = "C"; q.message.chat.type = "supergroup"
    q.answer = AsyncMock(); q.edit_message_text = AsyncMock()
    upd = MagicMock(); upd.callback_query = q
    await on_connect_chat_callback(upd, MagicMock(), db)
    row = db.conn.execute("SELECT workspace_id,role FROM bot_chats WHERE chat_id=-100").fetchone()
    assert row == (3, None)  # legacy byte-for-byte: role None


# --- V1.17.0h12-fix: анти-двойное-срабатывание (член → админ = 2 события) ---
@pytest.mark.asyncio
async def test_promotion_event_does_not_double_onboard(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)  # флаг OFF
    from handlers.bot_membership import on_bot_added_to_chat
    db = _lifecycle_db()
    db.conn.execute("INSERT INTO users (user_id,username) VALUES (42,'kir')")
    db.conn.commit()
    ctx = _ctx()
    # Событие 1: бота добавили как участника (реальный вход) → онбординг 1 раз
    await on_bot_added_to_chat(
        _added_update(-200, old_status='left', new_status='member'), ctx, db)
    ws_after_1 = db.conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
    sends_after_1 = ctx.bot.send_message.await_count
    # Событие 2: бота повысили member→admin → онбординг НЕ должен повториться
    await on_bot_added_to_chat(
        _added_update(-200, old_status='member', new_status='administrator'), ctx, db)
    assert ws_after_1 == 1
    assert db.conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0] == 1, \
        "событие повышения создало дубль workspace"
    assert ctx.bot.send_message.await_count == sends_after_1, \
        "событие повышения отправило повторное онбординг-сообщение"


@pytest.mark.asyncio
async def test_channel_is_skipped_no_onboarding(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    from handlers.bot_membership import on_bot_added_to_chat
    db = _lifecycle_db()
    ctx = _ctx()
    upd = _added_update(-300, old_status='left', new_status='administrator')
    upd.my_chat_member.chat.type = 'channel'
    await on_bot_added_to_chat(upd, ctx, db)
    assert db.conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0] == 0
    assert ctx.bot.send_message.await_count == 0
    assert ctx.bot.leave_chat.await_count == 0
