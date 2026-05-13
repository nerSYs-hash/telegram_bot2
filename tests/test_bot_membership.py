"""Тесты ChatMemberHandler для само-онбординга нового чата."""
import sqlite3
import pytest
from unittest.mock import AsyncMock, MagicMock

from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import create_workspace, add_bot_chat, get_workspace_by_chat


@pytest.fixture
def db():
    conn = sqlite3.connect(':memory:')
    up_create_workspaces_tables(conn)
    conn.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL DEFAULT 1,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT,
        role TEXT CHECK (role IS NULL OR role IN ('main','admin','journal')),
        added_at TEXT
    )''')
    conn.execute('''CREATE TABLE users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT
    )''')

    class _DB:
        def __init__(self, c):
            self.conn = c

        def get_site_user(self, uid):
            row = self.conn.execute(
                "SELECT user_id, username FROM users WHERE user_id=?", (uid,)
            ).fetchone()
            return {'user_id': row[0], 'username': row[1]} if row else None

        def get_workspace_by_chat(self, chat_id):
            return get_workspace_by_chat(self.conn, chat_id)
    return _DB(conn)


def _make_update(bot_id, new_status, chat_id, chat_title, chat_type, from_user_id):
    update = MagicMock()
    update.my_chat_member.new_chat_member.user.id = bot_id
    update.my_chat_member.new_chat_member.status = new_status
    update.my_chat_member.chat.id = chat_id
    update.my_chat_member.chat.title = chat_title
    update.my_chat_member.chat.type = chat_type
    update.my_chat_member.from_user.id = from_user_id
    return update


def _make_context(bot_id=999):
    ctx = MagicMock()
    ctx.bot.id = bot_id
    ctx.bot.send_message = AsyncMock()
    ctx.bot.leave_chat = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_creates_workspace_when_owner_registered(db):
    from handlers.bot_membership import on_bot_added_to_chat
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42, 'alice')")
    db.conn.commit()
    update = _make_update(999, 'administrator', -100, 'Alice Chat', 'supergroup', 42)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)
    ws_id = db.get_workspace_by_chat(-100)
    assert ws_id is not None
    ws = db.conn.execute(
        "SELECT name, owner_user_id FROM workspaces WHERE id=?", (ws_id,)
    ).fetchone()
    assert ws == ('Alice Chat', 42)
    members = db.conn.execute(
        "SELECT user_id, role FROM workspace_members WHERE workspace_id=?", (ws_id,)
    ).fetchall()
    assert (42, 'owner') in members
    ctx.bot.send_message.assert_called()


@pytest.mark.asyncio
async def test_leaves_when_owner_not_registered(db):
    from handlers.bot_membership import on_bot_added_to_chat
    update = _make_update(999, 'administrator', -100, 'X', 'supergroup', 666)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)
    assert db.get_workspace_by_chat(-100) is None
    ctx.bot.leave_chat.assert_called_once_with(-100)


@pytest.mark.asyncio
async def test_leaves_when_chat_already_bound(db):
    from handlers.bot_membership import on_bot_added_to_chat
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42, 'alice')")
    db.conn.commit()
    create_workspace(db.conn, 'Other WS', owner_user_id=1)
    add_bot_chat(db.conn, chat_id=-100, workspace_id=1, added_by=1,
                 title='Other', chat_type='supergroup')
    update = _make_update(999, 'administrator', -100, 'Try Steal', 'supergroup', 42)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)
    ws_id = db.get_workspace_by_chat(-100)
    assert ws_id == 1  # original Other WS
    ctx.bot.leave_chat.assert_called_once_with(-100)


@pytest.mark.asyncio
async def test_ignores_non_self_membership_change(db):
    from handlers.bot_membership import on_bot_added_to_chat
    update = _make_update(123, 'member', -100, 'X', 'group', 42)  # bot_id != self.id
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)
    assert db.get_workspace_by_chat(-100) is None
    ctx.bot.send_message.assert_not_called()
    ctx.bot.leave_chat.assert_not_called()


# ── V1.17.0c (F): кнопки выбора + текст «уже подключён к моему» ──

@pytest.mark.asyncio
async def test_already_bound_to_own_ws_does_not_leave(db):
    """Если чат привязан к МОЕМУ ws — бот говорит «уже подключён» и не уходит."""
    from handlers.bot_membership import on_bot_added_to_chat
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42, 'alice')")
    db.conn.commit()
    ws_id = create_workspace(db.conn, 'Mine', owner_user_id=42)
    add_bot_chat(db.conn, chat_id=-100, workspace_id=ws_id, added_by=42,
                 title='Mine', chat_type='supergroup')
    update = _make_update(999, 'administrator', -100, 'Mine', 'supergroup', 42)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)
    ctx.bot.send_message.assert_called()
    ctx.bot.leave_chat.assert_not_called()


@pytest.mark.asyncio
async def test_shows_buttons_when_user_owns_workspace(db):
    """Если у владельца уже есть ws — бот показывает кнопки, не создаёт новый автоматом."""
    from handlers.bot_membership import on_bot_added_to_chat
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42, 'alice')")
    db.conn.commit()
    create_workspace(db.conn, 'Existing', owner_user_id=42)

    update = _make_update(999, 'administrator', -200, 'New Chat', 'group', 42)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)

    # workspace не создаётся автоматически — ждём callback
    assert db.get_workspace_by_chat(-200) is None
    # отправили сообщение с кнопками
    ctx.bot.send_message.assert_called_once()
    _, kwargs = ctx.bot.send_message.call_args
    markup = kwargs.get('reply_markup')
    assert markup is not None
    btn_data = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert any(d.startswith('connect_chat:1:42') for d in btn_data)
    assert any(d.startswith('connect_chat:new:42') for d in btn_data)


@pytest.mark.asyncio
async def test_callback_binds_to_existing_ws(db):
    """Callback connect_chat:<ws_id>:<user_id> привязывает чат к существующему ws."""
    from handlers.bot_membership import on_connect_chat_callback
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42, 'alice')")
    db.conn.commit()
    ws_id = create_workspace(db.conn, 'Existing', owner_user_id=42)

    q = MagicMock()
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    q.data = f"connect_chat:{ws_id}:42"
    q.from_user.id = 42
    q.message.chat.id = -200
    q.message.chat.title = 'New Chat'
    q.message.chat.type = 'group'
    update = MagicMock()
    update.callback_query = q

    await on_connect_chat_callback(update, MagicMock(), db)
    assert db.get_workspace_by_chat(-200) == ws_id


@pytest.mark.asyncio
async def test_callback_new_creates_workspace(db):
    """Callback connect_chat:new:<user_id> создаёт новый ws с ролью main у чата."""
    from handlers.bot_membership import on_connect_chat_callback
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42, 'alice')")
    db.conn.commit()

    q = MagicMock()
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    q.data = "connect_chat:new:42"
    q.from_user.id = 42
    q.message.chat.id = -300
    q.message.chat.title = 'Fresh'
    q.message.chat.type = 'supergroup'
    update = MagicMock()
    update.callback_query = q

    await on_connect_chat_callback(update, MagicMock(), db)
    ws_id = db.get_workspace_by_chat(-300)
    assert ws_id is not None
    row = db.conn.execute(
        "SELECT role FROM bot_chats WHERE chat_id=?", (-300,)
    ).fetchone()
    assert row[0] == 'main'


@pytest.mark.asyncio
async def test_callback_rejects_foreign_user(db):
    """Другой юзер не может выбрать ws за владельца."""
    from handlers.bot_membership import on_connect_chat_callback
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42, 'alice')")
    db.conn.commit()
    ws_id = create_workspace(db.conn, 'Existing', owner_user_id=42)

    q = MagicMock()
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    q.data = f"connect_chat:{ws_id}:42"
    q.from_user.id = 666  # не тот, кто добавил
    q.message.chat.id = -400
    q.message.chat.title = 'X'
    q.message.chat.type = 'group'
    update = MagicMock()
    update.callback_query = q

    await on_connect_chat_callback(update, MagicMock(), db)
    assert db.get_workspace_by_chat(-400) is None
