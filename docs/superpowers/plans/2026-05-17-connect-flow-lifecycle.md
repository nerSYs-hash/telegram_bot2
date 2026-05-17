# Connect-flow Lifecycle Implementation Plan (P1–P3 backend)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Починить lifecycle подключённого чата: бот удалён → мягкая пометка (роль/ws сохранены, сайт видит «отключён»), повторное добавление → роль восстановлена; connect-flow не плодит лишние workspace; удаление ws чистит арендные данные; одноразовая безопасная консолидация ws5/ws6→ws1.

**Architecture:** Всё за флагом `CONNECT_FLOW_V2` (default OFF = строго байт-в-байт). Переиспользуем уже существующую soft-disconnect инфру (`removed_at`, `mark_bot_chat_removed`, `upsert_bot_chat`), которая сейчас мертва из-за затенения MY_CHAT_MEMBER-хендлеров. Регистрацию хендлеров НЕ трогаем — меняем поведение только внутри `on_bot_added_to_chat` по флагу. Миграция `removed_at` — идемпотентная, по образцу существующих в `db_migrations.py`.

**Tech Stack:** Python 3, python-telegram-bot, sqlite3, pytest/pytest-asyncio. Спека: `docs/superpowers/specs/2026-05-17-connect-flow-lifecycle-design.md`.

**Scope:** Этот план = P1 (backend lifecycle C1–C3,C5,C9) + P2 (prevention C4) + P3 (консолидация-скрипт C7). **P4 (сайт-UI C6,C8) — отдельный план** (`docs/superpowers/plans/2026-05-17-connect-flow-site-ui.md`, пишется при старте P4): отдельный деплой-юнит, React, свой CHANGELOG_SITE. P3 `--apply` на живом проде и любой деплой сайта — **гейт-шаги с явным «go» Ильи**.

---

## File Structure

- **Create** `bot_core/connect_flow.py` — флаг-хелпер `connect_flow_v2_enabled()` (зеркало `bot_core/login_button.py`).
- **Modify** `database/db_migrations.py` — `+add_removed_at_to_bot_chats(db)` (идемпотентная миграция, образец существующих).
- **Modify** `database/db_manager.py:~598` — вызвать миграцию рядом с `_create_stat_events_log(self)`.
- **Modify** `database/db_workspaces.py` — `+soft_remove_bot_chat`, `+get_disconnected_bot_chat`, `+TENANT_TABLES`, флаг-ветки в `get_workspace_by_chat`/`delete_workspace`.
- **Modify** `handlers/bot_membership.py` — C1 (left/kicked), C3 (restore), C4 (role-picker).
- **Create** `scripts/consolidate_workspaces.py` — одноразовая консолидация (dry-run/backup/apply).
- **Tests** `tests/test_connect_flow_lifecycle.py`, `tests/test_connect_flow_migration.py`, `tests/test_consolidate_workspaces.py`.
- **NOT touched:** `bot.py` регистрация хендлеров; `database/db_press_release.py` (реюзаем как есть).

---

# PHASE P1 — Backend lifecycle (safe, flag OFF = byte-for-byte)

### Task 1: Флаг-хелпер `CONNECT_FLOW_V2`

**Files:**
- Create: `bot_core/connect_flow.py`
- Test: `tests/test_connect_flow_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_connect_flow_lifecycle.py
import os
from bot_core.connect_flow import connect_flow_v2_enabled


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot_core.connect_flow'`

- [ ] **Step 3: Write minimal implementation**

```python
# bot_core/connect_flow.py
"""V1.17.0h: флаг connect-flow lifecycle (зеркало bot_core/login_button.py).

OFF по умолчанию = строго байт-в-байт: hard-delete bot_chats,
старый connect-flow, get_workspace_by_chat/delete_workspace без изменений.
"""
import os

_TRUTHY = {"1", "true", "yes", "on"}


def connect_flow_v2_enabled() -> bool:
    return os.getenv("CONNECT_FLOW_V2", "").strip().lower() in _TRUTHY
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add bot_core/connect_flow.py tests/test_connect_flow_lifecycle.py
git commit -m "feat(V1.17.0h1): flag-helper CONNECT_FLOW_V2 (default OFF)"
```

---

### Task 2: Идемпотентная миграция `removed_at`

**Files:**
- Modify: `database/db_migrations.py` (добавить функцию в конец)
- Modify: `database/db_manager.py` (вызвать рядом с `_create_stat_events_log`)
- Test: `tests/test_connect_flow_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_connect_flow_migration.py
import sqlite3
from database.db_migrations import add_removed_at_to_bot_chats


class _DB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _cols(conn):
    return {r[1] for r in conn.execute("PRAGMA table_info(bot_chats)").fetchall()}


def test_adds_removed_at_when_missing():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, workspace_id INTEGER)")
    db = _DB(conn)
    assert "removed_at" not in _cols(conn)
    add_removed_at_to_bot_chats(db)
    assert "removed_at" in _cols(conn)


def test_idempotent_when_already_present():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, removed_at TIMESTAMP)")
    db = _DB(conn)
    add_removed_at_to_bot_chats(db)  # must not raise
    add_removed_at_to_bot_chats(db)  # second call also no-op
    assert "removed_at" in _cols(conn)


def test_no_bot_chats_table_is_safe():
    conn = sqlite3.connect(":memory:")
    db = _DB(conn)
    add_removed_at_to_bot_chats(db)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_migration.py -q`
Expected: FAIL — `ImportError: cannot import name 'add_removed_at_to_bot_chats'`

- [ ] **Step 3: Write minimal implementation**

Append to `database/db_migrations.py`:

```python
def add_removed_at_to_bot_chats(db):
    """V1.17.0h: добавить bot_chats.removed_at если колонки нет.

    Идемпотентно (PRAGMA-проверка), безопасно при флаге OFF — колонка
    аддитивна и не меняет поведения сама по себе.
    """
    try:
        db.cursor.execute("PRAGMA table_info(bot_chats)")
        cols = [row[1] for row in db.cursor.fetchall()]
        if not cols:
            logging.info("bot_chats table absent, skip removed_at migration")
            return
        if 'removed_at' not in cols:
            db.cursor.execute("ALTER TABLE bot_chats ADD COLUMN removed_at TIMESTAMP")
            db.conn.commit()
            logging.info("✅ bot_chats.removed_at column added")
        else:
            logging.info("bot_chats.removed_at already present")
    except Exception as e:
        logging.error(f"add_removed_at_to_bot_chats error: {e}")
        db.conn.rollback()
```

In `database/db_manager.py`, find the line `_create_stat_events_log(self)` (~598) and the import block (~line 116 `create_stat_events_log as _create_stat_events_log`). Add import alias and call:

```python
# in the migrations import block near line 116:
from database.db_migrations import (
    add_removed_at_to_bot_chats as _add_removed_at_to_bot_chats,
)
```

```python
# right after the existing `_create_stat_events_log(self)` call (~line 598):
        _add_removed_at_to_bot_chats(self)
```

- [ ] **Step 3a: Verify exact insertion points**

Run: `.venv\Scripts\python.exe -c "import database.db_manager"`
Expected: no ImportError (alias resolves). If the import block uses a single `from database.db_migrations import (...)` group, add the alias inside that group instead of a new statement.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_migration.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add database/db_migrations.py database/db_manager.py tests/test_connect_flow_migration.py
git commit -m "feat(V1.17.0h2): idempotent bot_chats.removed_at migration + db_manager hook"
```

---

### Task 3: conn-уровневые soft-disconnect примитивы в `db_workspaces.py`

`bot_membership` работает через `db.conn`/`remove_bot_chat(db.conn, ...)`. `mark_bot_chat_removed` в `db_press_release` принимает `db` (с `.cursor`). Чтобы не смешивать вью, добавляем conn-уровневые хелперы рядом с `remove_bot_chat`.

**Files:**
- Modify: `database/db_workspaces.py` (после `remove_bot_chat`, ~line 217)
- Test: `tests/test_connect_flow_lifecycle.py` (дополнить)

- [ ] **Step 1: Write the failing test** (append to `tests/test_connect_flow_lifecycle.py`)

```python
import sqlite3
import pytest
from database.db_workspaces import (
    soft_remove_bot_chat, get_disconnected_bot_chat, get_workspace_by_chat,
)


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
    assert get_disconnected_bot_chat(conn, -100) is None  # active → None
    soft_remove_bot_chat(conn, -100)
    d = get_disconnected_bot_chat(conn, -100)
    assert d == {'workspace_id': 7, 'role': 'main'}


def test_get_workspace_by_chat_flag_off_unchanged(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    conn = _conn_with_chat()
    soft_remove_bot_chat(conn, -100)
    # OFF: removed chat still resolves (byte-for-byte legacy behavior)
    assert get_workspace_by_chat(conn, -100) == 7


def test_get_workspace_by_chat_flag_on_excludes_removed(monkeypatch):
    monkeypatch.setenv("CONNECT_FLOW_V2", "1")
    conn = _conn_with_chat()
    assert get_workspace_by_chat(conn, -100) == 7   # active
    soft_remove_bot_chat(conn, -100)
    assert get_workspace_by_chat(conn, -100) is None  # removed → not active
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -q`
Expected: FAIL — `ImportError: cannot import name 'soft_remove_bot_chat'`

- [ ] **Step 3: Write minimal implementation** (in `database/db_workspaces.py`, after `remove_bot_chat`)

```python
from bot_core.connect_flow import connect_flow_v2_enabled


def _bot_chats_has_removed_at(conn: sqlite3.Connection) -> bool:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chats)").fetchall()]
    return 'removed_at' in cols


def soft_remove_bot_chat(conn: sqlite3.Connection, chat_id: int) -> None:
    """V1.17.0h: мягкое отключение — removed_at=now, workspace_id/role сохраняются.
    Если колонки removed_at нет (старая схема) — фолбэк на hard delete."""
    if _bot_chats_has_removed_at(conn):
        conn.execute(
            "UPDATE bot_chats SET removed_at=CURRENT_TIMESTAMP WHERE chat_id=?",
            (chat_id,))
    else:
        conn.execute("DELETE FROM bot_chats WHERE chat_id=?", (chat_id,))
    conn.commit()


def get_disconnected_bot_chat(conn: sqlite3.Connection, chat_id: int):
    """Вернёт {'workspace_id','role'} если чат soft-removed, иначе None."""
    if not _bot_chats_has_removed_at(conn):
        return None
    row = conn.execute(
        "SELECT workspace_id, role FROM bot_chats "
        "WHERE chat_id=? AND removed_at IS NOT NULL", (chat_id,)
    ).fetchone()
    return {'workspace_id': row[0], 'role': row[1]} if row else None
```

Modify existing `get_workspace_by_chat` — add flag-gated active filter:

```python
def get_workspace_by_chat(conn: sqlite3.Connection, chat_id: int) -> Optional[int]:
    """Возвращает workspace_id если chat привязан, иначе None.
    При CONNECT_FLOW_V2 ON: soft-removed чат (removed_at IS NOT NULL) → None."""
    if connect_flow_v2_enabled() and _bot_chats_has_removed_at(conn):
        row = conn.execute(
            'SELECT workspace_id FROM bot_chats '
            'WHERE chat_id=? AND removed_at IS NULL', (chat_id,)
        ).fetchone()
    else:
        row = conn.execute(
            'SELECT workspace_id FROM bot_chats WHERE chat_id=?', (chat_id,)
        ).fetchone()
    return row[0] if row else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -q`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add database/db_workspaces.py tests/test_connect_flow_lifecycle.py
git commit -m "feat(V1.17.0h3): soft_remove/get_disconnected + flag-gated get_workspace_by_chat"
```

---

### Task 4: C1 — `on_bot_added_to_chat` left/kicked ветка за флагом

**Files:**
- Modify: `handlers/bot_membership.py:57-64`
- Test: `tests/test_connect_flow_lifecycle.py` (дополнить)

- [ ] **Step 1: Write the failing test** (append)

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -k kicked -q`
Expected: FAIL on `test_kicked_flag_on_soft_removes` (currently always hard delete → row count 0, removed_at branch missing)

- [ ] **Step 3: Write minimal implementation**

In `handlers/bot_membership.py` add import near top imports:

```python
from database.db_workspaces import (
    create_workspace, add_bot_chat, get_workspaces_for_user,
    remove_bot_chat, soft_remove_bot_chat,
)
from bot_core.connect_flow import connect_flow_v2_enabled
```

Replace the `left/kicked` block (currently lines ~57-64):

```python
    # G1 / V1.17.0h C1: bot kicked/left → отвязать чат от ws (workspace остаётся).
    if new.status in ('left', 'kicked'):
        existing_ws = db.get_workspace_by_chat(chat_id)
        if existing_ws is not None:
            if connect_flow_v2_enabled():
                soft_remove_bot_chat(db.conn, chat_id)
                logger.info(f"Bot left chat={chat_id}; soft-removed (ws={existing_ws})")
            else:
                remove_bot_chat(db.conn, chat_id)
                logger.info(f"Bot left chat={chat_id}; removed from bot_chats (ws={existing_ws})")
            invalidate_cache(chat_id)
        return
```

Note: `db.get_workspace_by_chat` at ON excludes already-soft-removed; first kick still has `removed_at IS NULL` so resolves correctly. Idempotent: second kick → `existing_ws` None at ON (already removed) → no-op.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -k kicked -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add handlers/bot_membership.py tests/test_connect_flow_lifecycle.py
git commit -m "feat(V1.17.0h4): C1 left/kicked soft-remove za flagom (OFF=hard delete bayt-v-bayt)"
```

---

### Task 5: C3 — restore роли при повторном добавлении

**Files:**
- Modify: `handlers/bot_membership.py` (add-ветка, перед блоком «3+4 Already bound?» ~line 69)
- Test: `tests/test_connect_flow_lifecycle.py` (дополнить)

- [ ] **Step 1: Write the failing test** (append)

```python
def _added_update(chat_id):
    u = MagicMock()
    u.my_chat_member.new_chat_member.user.id = 999
    u.my_chat_member.new_chat_member.status = 'administrator'
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
    # no "куда подключить" menu was sent
    sent = " ".join(str(c) for c in ctx.bot.send_message.call_args_list)
    assert "Куда подключить" not in sent


@pytest.mark.asyncio
async def test_reconnect_flag_off_unchanged(monkeypatch):
    monkeypatch.delenv("CONNECT_FLOW_V2", raising=False)
    from handlers.bot_membership import on_bot_added_to_chat
    db = _lifecycle_db()
    # OFF: legacy — chat row absent (was hard-deleted on leave); add → normal flow
    db.conn.execute("INSERT INTO users (user_id,username) VALUES (42,'a')")
    db.conn.commit()
    ctx = _ctx()
    await on_bot_added_to_chat(_added_update(-100), ctx, db)
    # legacy path created a workspace (no regression)
    assert get_workspace_by_chat(db.conn, -100) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -k reconnect -q`
Expected: FAIL on `test_reconnect_restores_role_no_menu` (no restore branch → falls into "already bound elsewhere"/menu)

- [ ] **Step 3: Write minimal implementation**

In `handlers/bot_membership.py`, add import: `from database.db_workspaces import get_disconnected_bot_chat`. Insert restore block right after `if new.status not in ('member', 'administrator'): return` and **before** `# 3+4. Already bound?`:

```python
    # V1.17.0h C3: повторное добавление soft-removed чата → восстановить роль.
    if connect_flow_v2_enabled():
        disc = get_disconnected_bot_chat(db.conn, chat_id)
        if disc is not None:
            db.conn.execute(
                "UPDATE bot_chats SET removed_at=NULL, added_by_user_id=?, "
                "title=?, chat_type=? WHERE chat_id=?",
                (from_user.id, chat_title, chat.type, chat_id))
            db.conn.commit()
            invalidate_cache(chat_id)
            role_txt = disc['role'] or 'без роли'
            logger.info(f"Reconnect chat={chat_id} restored ws={disc['workspace_id']} role={disc['role']}")
            try:
                await context.bot.send_message(
                    chat_id,
                    f"♻️ С возвращением! Чат переподключён к Pulse SaaS, "
                    f"роль «{role_txt}» восстановлена.\n"
                    f"Управление — на сайте: {SITE_URL}",
                    reply_markup=_login_kb(),
                )
            except Exception as e:
                logger.warning(f"send_message (reconnect) failed: {e}")
            return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -k reconnect -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add handlers/bot_membership.py tests/test_connect_flow_lifecycle.py
git commit -m "feat(V1.17.0h5): C3 restore roli pri reconnect (flag ON; OFF=legacy)"
```

---

### Task 6: C9 — каскад-очистка tenant-таблиц в `delete_workspace`

**Files:**
- Modify: `database/db_workspaces.py` (`delete_workspace` + `TENANT_TABLES`)
- Test: `tests/test_connect_flow_lifecycle.py` (дополнить)

- [ ] **Step 1: Write the failing test** (append)

```python
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
    assert conn.execute("SELECT COUNT(*) FROM economy_settings WHERE workspace_id=9").fetchone()[0] == 1  # legacy: orphaned


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -k delete_workspace -q`
Expected: FAIL on `test_delete_workspace_flag_on_cascades` (economy_settings row still there — no cascade)

- [ ] **Step 3: Write minimal implementation**

In `database/db_workspaces.py`, add module-level constant (shared with consolidation script):

```python
# V1.17.0h: единый список tenant-таблиц с колонкой workspace_id.
# Реюз: C9 (delete cascade) и scripts/consolidate_workspaces.py (safety).
TENANT_TABLES = (
    'economy_settings', 'economy_section_toggles', 'branding_settings',
    'user_stats', 'user_stats_hourly', 'chat_stats', 'topics', 'triggers',
)
```

Modify `delete_workspace` — add cascade before the 3 structural deletes:

```python
def delete_workspace(conn: sqlite3.Connection, workspace_id: int) -> None:
    """Удаляет workspace: members + bot_chats + сам workspace.
    При CONNECT_FLOW_V2 ON — дополнительно чистит tenant-данные (C9).
    Запрещает удаление is_pulse_themed=1."""
    row = conn.execute(
        'SELECT is_pulse_themed FROM workspaces WHERE id=?', (workspace_id,)
    ).fetchone()
    if not row:
        return
    if row[0]:
        raise ValueError('Нельзя удалить Pulse-themed сообщество')
    if connect_flow_v2_enabled():
        for t in TENANT_TABLES:
            try:
                conn.execute(f'DELETE FROM {t} WHERE workspace_id=?', (workspace_id,))
            except sqlite3.OperationalError:
                pass  # таблицы может не быть в этой БД — ок
    conn.execute('DELETE FROM bot_chats WHERE workspace_id=?', (workspace_id,))
    conn.execute('DELETE FROM workspace_members WHERE workspace_id=?', (workspace_id,))
    conn.execute('DELETE FROM workspaces WHERE id=?', (workspace_id,))
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -k delete_workspace -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add database/db_workspaces.py tests/test_connect_flow_lifecycle.py
git commit -m "feat(V1.17.0h6): C9 cascade tenant-cleanup v delete_workspace za flagom + TENANT_TABLES"
```

---

### Task 7: P1 регрессия — весь сьют

- [ ] **Step 1: Run full suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q --no-header`
Expected: `>= 219 + новые` passed, 0 failed. Если что-то красное — чинить причину (флаг OFF обязан быть байт-в-байт; смотреть тесты, ожидающие старое поведение `get_workspace_by_chat`/`remove_bot_chat`).

- [ ] **Step 2: Commit (если были правки фиксов регрессий)**

```bash
git add -A -- tests/ handlers/ database/ bot_core/
git commit -m "test(V1.17.0h7): P1 regress green (baza+novye, flag OFF bayt-v-bayt)"
```

---

# PHASE P2 — Connect-flow prevention (C4)

### Task 8: Привязка к существующему ws через выбор роли

Сейчас (`bot_membership.py` шаг 6) кнопки `connect_chat:<ws_id>:<uid>` и `connect_chat:new:<uid>`; callback `on_connect_chat_callback` привязывает с `role=None`. C4: при ON для существующего ws предлагать выбор роли, привязывать с выбранной ролью; «создать новое» остаётся.

**Files:**
- Modify: `handlers/bot_membership.py` (шаг 6 кнопки + `on_connect_chat_callback`)
- Test: `tests/test_connect_flow_lifecycle.py` (дополнить)

- [ ] **Step 1: Write the failing test** (append)

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -k connect_ -q`
Expected: FAIL on `test_connect_existing_ws_binds_with_role` (4-part callback not parsed; role not set)

- [ ] **Step 3: Write minimal implementation**

In `on_connect_chat_callback`, make the parser accept optional 4th `role` segment, flag-gated. Replace the parse block:

```python
    parts = q.data.split(':')
    if len(parts) < 3 or parts[0] != 'connect_chat':
        return
    target = parts[1]
    try:
        from_user_id = int(parts[2])
    except ValueError:
        return
    chosen_role = parts[3] if (len(parts) >= 4 and connect_flow_v2_enabled()) else None
    if chosen_role is not None and chosen_role not in ('main', 'admin', 'journal'):
        chosen_role = None
```

In the existing-ws bind path, replace `role=None` with `role=chosen_role`:

```python
    add_bot_chat(db.conn, chat_id, ws_id, added_by=from_user_id,
                 title=chat_title, chat_type=chat.type, role=chosen_role)
```

In step-6 button construction (the `owned_wss` loop), at ON emit role-choice buttons; at OFF keep current 3-part callbacks (byte-for-byte):

```python
    if owned_wss:
        buttons = []
        for w in owned_wss:
            if connect_flow_v2_enabled():
                for rcode, rlabel in (('main', 'Главный'), ('admin', 'Админ'), ('journal', 'Журнал')):
                    buttons.append([InlineKeyboardButton(
                        f"📂 «{w['name']}» — {rlabel}",
                        callback_data=f"connect_chat:{w['id']}:{from_user.id}:{rcode}")])
            else:
                buttons.append([InlineKeyboardButton(
                    f"📂 К «{w['name']}»",
                    callback_data=f"connect_chat:{w['id']}:{from_user.id}")])
        buttons.append([InlineKeyboardButton(
            "🆕 Создать новое сообщество",
            callback_data=f"connect_chat:new:{from_user.id}")])
        # ... existing send_message(chat_id, "👋 ... Куда подключить ...", reply_markup=InlineKeyboardMarkup(buttons))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_connect_flow_lifecycle.py -k connect_ -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add handlers/bot_membership.py tests/test_connect_flow_lifecycle.py
git commit -m "feat(V1.17.0h8): C4 privyazka k sushestvuyushemu ws s vyborom roli (OFF=3-part legacy)"
```

---

### Task 9: P2 регрессия

- [ ] **Step 1:** Run: `.venv\Scripts\python.exe -m pytest tests/ -q --no-header` → all green.
- [ ] **Step 2:** Commit fixes if any: `git commit -m "test(V1.17.0h9): P2 regress green"`

---

# PHASE P3 — Консолидация-скрипт (C7) — `--apply` ГЕЙТ с Ильёй

### Task 10: `scripts/consolidate_workspaces.py`

**Files:**
- Create: `scripts/consolidate_workspaces.py`
- Test: `tests/test_consolidate_workspaces.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_consolidate_workspaces.py
import sqlite3, pytest
from scripts.consolidate_workspaces import consolidate, ConsolidateBlocked


def _db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT, owner_user_id INTEGER, is_pulse_themed INTEGER, plan TEXT)")
    conn.execute("CREATE TABLE workspace_members (workspace_id INTEGER, user_id INTEGER, role TEXT)")
    conn.execute("CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, workspace_id INTEGER, role TEXT, removed_at TIMESTAMP)")
    conn.execute("CREATE TABLE economy_settings (workspace_id INTEGER, key TEXT)")
    for wid, themed in ((1,1),(5,0),(6,0)):
        conn.execute("INSERT INTO workspaces VALUES (?,?,?,?,?)", (wid,f"W{wid}",42,themed,'free'))
        conn.execute("INSERT INTO workspace_members VALUES (?,?,?)", (wid,42,'owner'))
    conn.execute("INSERT INTO bot_chats VALUES (-1,1,'main',NULL)")
    conn.execute("INSERT INTO bot_chats VALUES (-5,5,'journal',NULL)")
    conn.execute("INSERT INTO bot_chats VALUES (-6,6,'admin',NULL)")
    conn.commit()
    return conn


def test_dry_run_changes_nothing():
    conn = _db()
    consolidate(conn, from_ids=[5,6], into_id=1, apply=False)
    assert conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0] == 3
    assert conn.execute("SELECT workspace_id FROM bot_chats WHERE chat_id=-5").fetchone()[0] == 5


def test_apply_repoints_and_deletes_empty():
    conn = _db()
    consolidate(conn, from_ids=[5,6], into_id=1, apply=True)
    assert conn.execute("SELECT workspace_id FROM bot_chats WHERE chat_id=-5").fetchone()[0] == 1
    assert conn.execute("SELECT role FROM bot_chats WHERE chat_id=-5").fetchone()[0] == 'journal'
    assert conn.execute("SELECT COUNT(*) FROM workspaces WHERE id IN (5,6)").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM workspace_members WHERE workspace_id IN (5,6)").fetchone()[0] == 0


def test_apply_idempotent():
    conn = _db()
    consolidate(conn, from_ids=[5,6], into_id=1, apply=True)
    consolidate(conn, from_ids=[5,6], into_id=1, apply=True)  # no error, no-op
    assert conn.execute("SELECT workspace_id FROM bot_chats WHERE chat_id=-5").fetchone()[0] == 1


def test_blocks_if_source_has_tenant_data():
    conn = _db()
    conn.execute("INSERT INTO economy_settings VALUES (5,'k')")
    conn.commit()
    with pytest.raises(ConsolidateBlocked):
        consolidate(conn, from_ids=[5,6], into_id=1, apply=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_consolidate_workspaces.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/consolidate_workspaces.py
"""V1.17.0h C7: одноразовая безопасная консолидация workspace.

Перепривязывает bot_chats из пустых source-ws в целевой ws (роли
сохраняются), удаляет опустевшие source-ws + их workspace_members.
Защита: source с непустыми tenant-данными → ConsolidateBlocked.

Usage:
  python -m scripts.consolidate_workspaces --db database/bot_database.db --from 5,6 --into 1            # dry-run
  python -m scripts.consolidate_workspaces --db database/bot_database.db --from 5,6 --into 1 --apply     # выполнить
Бэкап БД делается автоматически перед --apply.
"""
import argparse, os, shutil, sqlite3, sys
from datetime import datetime

from database.db_workspaces import TENANT_TABLES


class ConsolidateBlocked(Exception):
    pass


def _tenant_rows(conn, ws_id):
    total = 0
    for t in TENANT_TABLES:
        try:
            total += conn.execute(
                f"SELECT COUNT(*) FROM {t} WHERE workspace_id=?", (ws_id,)
            ).fetchone()[0]
        except sqlite3.OperationalError:
            pass
    return total


def consolidate(conn, from_ids, into_id, apply=False):
    plan = []
    for src in from_ids:
        n = _tenant_rows(conn, src)
        if n > 0:
            raise ConsolidateBlocked(
                f"ws={src} имеет {n} tenant-строк — авто-консолидация запрещена, нужно ручное решение")
        chats = conn.execute(
            "SELECT chat_id, role FROM bot_chats WHERE workspace_id=?", (src,)).fetchall()
        plan.append((src, chats))
        for cid, role in chats:
            print(f"[plan] bot_chats chat_id={cid} role={role}: ws {src} -> {into_id}")
        print(f"[plan] DELETE workspace_members ws={src}; DELETE workspaces id={src}")
    if not apply:
        print("[dry-run] изменения НЕ применены (--apply чтобы выполнить)")
        return
    try:
        conn.execute("BEGIN")
        for src, _ in plan:
            conn.execute("UPDATE bot_chats SET workspace_id=? WHERE workspace_id=?", (into_id, src))
            conn.execute("DELETE FROM workspace_members WHERE workspace_id=?", (src,))
            conn.execute("DELETE FROM workspaces WHERE id=?", (src,))
        conn.execute("COMMIT")
        print(f"[done] консолидация выполнена: {from_ids} -> {into_id}")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _backup(db_path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = f"{db_path}.pre_consolidate_{ts}"
    shutil.copy2(db_path, dest)
    print(f"[backup] {dest}")
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--from", dest="from_ids", required=True, help="напр. 5,6")
    ap.add_argument("--into", dest="into_id", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    from_ids = [int(x) for x in a.from_ids.split(",") if x.strip()]
    if a.apply:
        _backup(a.db)
    conn = sqlite3.connect(a.db)
    try:
        consolidate(conn, from_ids, a.into_id, apply=a.apply)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_consolidate_workspaces.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/consolidate_workspaces.py tests/test_consolidate_workspaces.py
git commit -m "feat(V1.17.0h10): skript konsolidacii ws (dry-run/backup/apply/guard/idempotent)"
```

---

### Task 11: Финальная регрессия + spec self-review

- [ ] **Step 1:** Run: `.venv\Scripts\python.exe -m pytest tests/ -q --no-header` → all green (база + все новые).
- [ ] **Step 2:** Сверить план со спекой: C1✓T4 C2✓T2 C3✓T5 C4✓T8 C5✓T3 C7✓T10 C9✓T6. C6/C8 → P4 отдельный план. Зафиксировать в memory `dev_backlog_index` статус P1-P3 done.
- [ ] **Step 3:** Commit: `git commit -m "test(V1.17.0h11): final regress green, P1-P3 gotovy k merge+aktivacii"`

---

## Activation (после merge, путь A как H/I/g) — ГЕЙТ с Ильёй

1. merge `feat/V1.17.0h-connect-flow-lifecycle` → `main` → push → авто-деплой (флаг OFF = байт-в-байт, миграция `removed_at` аддитивна).
2. Проверить прод чист (pulsbot+pulsapi active, 0 ошибок), `removed_at` колонка появилась.
3. `/root/PulsBot/.env` `CONNECT_FLOW_V2=1` (бэкап `.env` перед).
4. `systemctl restart pulsbot` → smoke Ильёй: удалить бота из тест-чата (Кирилл ws7) → ws помечен «отключён», бот молчит → добавить обратно → роль восстановлена, бот ожил.
5. **C7 консолидация — отдельный явный шаг:** dry-run на проде → показать Илье план → `--apply` ТОЛЬКО с его «go» (бэкап авто).
6. Откат: убрать флаг + рестарт; БД — `removed_at` безвреден при OFF; консолидация — restore из `.pre_consolidate_*`.

## P4 (отдельный план — сайт-UI C6/C8)

`docs/superpowers/plans/2026-05-17-connect-flow-site-ui.md` — пишется при старте P4. Бейдж «🔴 бот не в чате» (из `chats_count`/`removed_at`) + ярлык «⭐ Главное / доп. №N» (из `is_pulse_themed`+порядок) в `Admin_SITE` (`WorkspaceList.jsx`, `WorkspacePage.jsx`, `AdminDashboard.jsx`). Отдельный деплой сайта (`[Site]`, локальный билд → деплой), CHANGELOG_SITE. Гейт с Ильёй.
