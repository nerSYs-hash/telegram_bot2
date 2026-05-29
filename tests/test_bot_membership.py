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


# ── V1.17.0c (G): бот покинул чат → авто-отвязка ──

@pytest.mark.asyncio
async def test_bot_kicked_removes_chat_from_bot_chats(db):
    """G1: бот kicked → запись в bot_chats удаляется, workspace остаётся."""
    from handlers.bot_membership import on_bot_added_to_chat
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42, 'alice')")
    db.conn.commit()
    ws_id = create_workspace(db.conn, 'Mine', owner_user_id=42)
    add_bot_chat(db.conn, chat_id=-700, workspace_id=ws_id, added_by=42,
                 title='Gone', chat_type='supergroup')

    update = _make_update(999, 'kicked', -700, 'Gone', 'supergroup', 42)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)

    assert db.get_workspace_by_chat(-700) is None
    ws_row = db.conn.execute(
        "SELECT id FROM workspaces WHERE id=?", (ws_id,)
    ).fetchone()
    assert ws_row is not None  # workspace остаётся


@pytest.mark.asyncio
async def test_bot_left_removes_chat_from_bot_chats(db):
    from handlers.bot_membership import on_bot_added_to_chat
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42, 'alice')")
    db.conn.commit()
    ws_id = create_workspace(db.conn, 'Mine', owner_user_id=42)
    add_bot_chat(db.conn, chat_id=-800, workspace_id=ws_id, added_by=42,
                 title='Gone2', chat_type='supergroup')

    update = _make_update(999, 'left', -800, 'Gone2', 'supergroup', 42)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)

    assert db.get_workspace_by_chat(-800) is None


# ── E1 (V1.17.0R): упрощённый онбординг ──

@pytest.mark.asyncio
async def test_schedule_greeting_delete_calls_run_once():
    from handlers.bot_membership import _schedule_greeting_delete
    ctx = MagicMock()
    ctx.job_queue.run_once = MagicMock()
    _schedule_greeting_delete(ctx, chat_id=-100, message_id=7, delay=120)
    ctx.job_queue.run_once.assert_called_once()
    _args, kwargs = ctx.job_queue.run_once.call_args
    assert kwargs['data'] == {'chat_id': -100, 'message_id': 7}


@pytest.mark.asyncio
async def test_schedule_greeting_delete_no_jobqueue_is_safe():
    from handlers.bot_membership import _schedule_greeting_delete
    ctx = MagicMock()
    ctx.job_queue = None
    _schedule_greeting_delete(ctx, chat_id=-100, message_id=7, delay=120)


@pytest.mark.asyncio
async def test_delete_greeting_job_calls_delete_message():
    from handlers.bot_membership import _delete_greeting_job
    ctx = MagicMock()
    ctx.bot.delete_message = AsyncMock()
    ctx.job.data = {'chat_id': -100, 'message_id': 7}
    await _delete_greeting_job(ctx)
    ctx.bot.delete_message.assert_awaited_once_with(-100, 7)


def test_owner_dm_text_contains_title_and_site():
    from handlers.bot_membership import _owner_dm_text, SITE_URL
    txt = _owner_dm_text('Моя Группа')
    assert 'Моя Группа' in txt
    assert SITE_URL in txt


@pytest.mark.asyncio
async def test_e1_owner_with_existing_ws_autoconnects(db, monkeypatch):
    """Флаг ON: владелец с сообществом добавляет бота → авто-создан НОВЫЙ ws
    role=main, БЕЗ inline-кнопок выбора, бот не уходит."""
    monkeypatch.setenv('CONNECT_FLOW_V2', '1')
    from handlers.bot_membership import on_bot_added_to_chat
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42,'alice')")
    db.conn.commit()
    create_workspace(db.conn, 'Existing', owner_user_id=42)  # ws=1

    update = _make_update(999, 'administrator', -200, 'New Chat', 'supergroup', 42)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)

    ws_id = db.get_workspace_by_chat(-200)
    assert ws_id is not None and ws_id != 1  # отдельный новый ws
    role = db.conn.execute(
        "SELECT role FROM bot_chats WHERE chat_id=?", (-200,)).fetchone()[0]
    assert role == 'main'
    ctx.bot.leave_chat.assert_not_called()
    for _a, kwargs in ctx.bot.send_message.call_args_list:
        mk = kwargs.get('reply_markup')
        if mk is not None and hasattr(mk, 'inline_keyboard'):
            data = [b.callback_data for row in mk.inline_keyboard for b in row]
            assert not any((d or '').startswith('connect_chat') for d in data)


@pytest.mark.asyncio
async def test_e1_unregistered_connects_without_leave(db, monkeypatch):
    """Флаг ON: гейт регистрации убран — незарегистрированный подключает чат,
    бот НЕ уходит, ws создаётся с ним как owner."""
    monkeypatch.setenv('CONNECT_FLOW_V2', '1')
    from handlers.bot_membership import on_bot_added_to_chat
    update = _make_update(999, 'administrator', -210, 'Fresh', 'supergroup', 666)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)

    ws_id = db.get_workspace_by_chat(-210)
    assert ws_id is not None
    owner = db.conn.execute(
        "SELECT owner_user_id FROM workspaces WHERE id=?", (ws_id,)).fetchone()[0]
    assert owner == 666
    ctx.bot.leave_chat.assert_not_called()


@pytest.mark.asyncio
async def test_e1_sends_group_greeting_and_owner_dm(db, monkeypatch):
    """Флаг ON: бот шлёт приветствие в группу И отдельный DM владельцу."""
    monkeypatch.setenv('CONNECT_FLOW_V2', '1')
    from handlers.bot_membership import on_bot_added_to_chat
    update = _make_update(999, 'administrator', -220, 'Greet Chat', 'supergroup', 77)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)

    sent_chat_ids = [a[0] for a, _ in ctx.bot.send_message.call_args_list]
    assert -220 in sent_chat_ids
    assert 77 in sent_chat_ids


@pytest.mark.asyncio
async def test_e1_schedules_greeting_self_delete(db, monkeypatch):
    """Флаг ON: самоудаление приветствия запланировано через job_queue."""
    monkeypatch.setenv('CONNECT_FLOW_V2', '1')
    from handlers.bot_membership import on_bot_added_to_chat
    update = _make_update(999, 'administrator', -230, 'Del Chat', 'supergroup', 88)
    ctx = _make_context(999)
    ctx.job_queue.run_once = MagicMock()
    await on_bot_added_to_chat(update, ctx, db)
    ctx.job_queue.run_once.assert_called_once()
