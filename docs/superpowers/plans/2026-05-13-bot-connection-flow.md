# Bot Connection Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подключение нового сообщества: владелец логинится на сайте, добавляет бота в чат, бот автоматически создаёт workspace и привязывает чат, владелец управляет помощниками.

**Architecture:** ChatMemberHandler в боте ловит `my_chat_member` event при добавлении бота, проверяет регистрацию `from_user` (= зарегистрирован ли он на сайте через существующий JWT-flow), создаёт workspace + bot_chats + workspace_members. Composite PK debt закрывается миграцией rebuild-pattern. /start в DM маршрутизируется через `join_<ws_id>` deep-link. Сайт получает 4 новых endpoint-а (`/api/workspaces` list/details, `/members` add/delete, rename).

**Tech Stack:** Python 3.11, python-telegram-bot 20.x, FastAPI, SQLite, React+Vite, Tailwind, lucide-react.

**Поправка к спеке:** `site_users`/`site_sessions` таблицы НЕ создаём — JWT auth + `users` таблица (которая GLOBAL после миграции #1) уже покрывают это. `POST /api/auth/telegram` уже работает (`api.py:140-162`). Считаем что user "зарегистрирован на сайте" если есть запись в `users.user_id`.

---

## Файловая структура

| Файл | Действие | Назначение |
|---|---|---|
| `database/migrations/composite_pk_fix.py` | Create | Rebuild 7 таблиц с `(workspace_id, …)` PK |
| `database/migrations/bot_chats_extend.py` | Create | ALTER bot_chats добавить added_by/title/type/added_at |
| `database/db_workspaces.py` | Modify | + `get_workspaces_for_user`, `get_workspace_details`, `update_workspace_name` |
| `handlers/bot_membership.py` | Create | `on_bot_added_to_chat`, `on_bot_removed_from_chat` |
| `bot.py` | Modify | Регистрация ChatMemberHandler, убрать fallback ws=1 в middleware |
| `bot_core/workspace_context.py` | Modify | Resolve без fallback (ws_ctx=None для unknown chat) |
| `handlers/commands/system_commands.py` | Modify | `/start` routing: `join_<ws>`, default → site link |
| `api/workspaces_routes.py` | Create | `/api/workspaces` (list/details/rename), `/members` (add/delete) |
| `api.py` | Modify | `include_router(workspaces_router)` |
| `Admin_SITE/components/shared/api.js` | Modify | + `fetchWorkspaces`, `inviteMember`, `removeMember`, `renameWorkspace` |
| `Admin_SITE/components/workspaces/WorkspaceList.jsx` | Create | Список сообществ юзера |
| `Admin_SITE/components/workspaces/WorkspacePage.jsx` | Create | Детали workspace + список чатов + помощники |
| `Admin_SITE/components/workspaces/InviteMemberModal.jsx` | Create | Модалка приглашения помощника |
| `Admin_SITE/AdminDashboard.jsx` | Modify | Использовать WorkspaceList вместо хардкод-блока "Без чата" |
| `tests/test_composite_pk_fix.py` | Create | Round-trip миграции на копии БД |
| `tests/test_bot_membership.py` | Create | 4 кейса my_chat_member handler |
| `tests/test_start_command_routing.py` | Create | join_<ws> / default routing |
| `tests/test_workspaces_api.py` | Create | list/details/members/rename + permission checks |

---

## Phase 1 — Database foundation

### Task 1: Миграция composite_pk_fix

**Files:**
- Create: `database/migrations/composite_pk_fix.py`
- Test: `tests/test_composite_pk_fix.py`

- [ ] **Step 1: Написать failing-тест round-trip миграции**

```python
# tests/test_composite_pk_fix.py
import os
import shutil
import sqlite3
import pytest

from database.migrations.composite_pk_fix import migrate_up, migrate_down, REBUILT_TABLES


@pytest.fixture
def db_with_v17_state(tmp_path):
    """Копия live-БД (уже мигрирована до multi-tenancy V1.17.0a22)."""
    src = os.path.join(os.path.dirname(__file__), '..', 'database', 'bot_database.db')
    dst = tmp_path / 'test.db'
    shutil.copy2(src, dst)
    return str(dst)


def test_migrate_up_recreates_economy_settings_pk(db_with_v17_state):
    migrate_up(db_with_v17_state)
    conn = sqlite3.connect(db_with_v17_state)
    pk_cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(economy_settings)"
    ).fetchall() if r[5] > 0]  # pk > 0
    assert set(pk_cols) == {'workspace_id', 'key'}
    conn.close()


def test_migrate_up_preserves_data(db_with_v17_state):
    conn = sqlite3.connect(db_with_v17_state)
    before = conn.execute("SELECT COUNT(*) FROM economy_settings").fetchone()[0]
    conn.close()
    migrate_up(db_with_v17_state)
    conn = sqlite3.connect(db_with_v17_state)
    after = conn.execute("SELECT COUNT(*) FROM economy_settings").fetchone()[0]
    assert after == before
    conn.close()


def test_migrate_up_allows_two_workspaces_same_key(db_with_v17_state):
    """После фикса можно иметь одинаковый key в разных workspace."""
    migrate_up(db_with_v17_state)
    conn = sqlite3.connect(db_with_v17_state)
    conn.execute(
        "INSERT INTO economy_settings (workspace_id, key, value) VALUES (?, ?, ?)",
        (99, 'test_key', '100')
    )
    conn.execute(
        "INSERT INTO economy_settings (workspace_id, key, value) VALUES (?, ?, ?)",
        (100, 'test_key', '200')
    )
    conn.commit()
    rows = conn.execute(
        "SELECT workspace_id, value FROM economy_settings WHERE key='test_key' ORDER BY workspace_id"
    ).fetchall()
    assert rows == [(99, '100'), (100, '200')]
    conn.close()


def test_migrate_down_reverts(db_with_v17_state):
    migrate_up(db_with_v17_state)
    migrate_down(db_with_v17_state)
    conn = sqlite3.connect(db_with_v17_state)
    pk_cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(economy_settings)"
    ).fetchall() if r[5] > 0]
    assert pk_cols == ['key']  # back to single PK
    conn.close()


def test_all_rebuilt_tables_have_composite_pk(db_with_v17_state):
    migrate_up(db_with_v17_state)
    conn = sqlite3.connect(db_with_v17_state)
    for tbl, expected_pk in REBUILT_TABLES.items():
        pk_cols = [r[1] for r in conn.execute(
            f"PRAGMA table_info({tbl})"
        ).fetchall() if r[5] > 0]
        assert set(pk_cols) == set(expected_pk), f'{tbl}: PK={pk_cols} expected={expected_pk}'
    conn.close()
```

- [ ] **Step 2: Запустить тест — должен упасть**

Run: `pytest tests/test_composite_pk_fix.py -v`
Expected: 5 ошибок `ModuleNotFoundError: composite_pk_fix`

- [ ] **Step 3: Написать миграцию**

```python
# database/migrations/composite_pk_fix.py
"""
Миграция: исправление composite PK для 7 таблиц.
ID: 2026-05-13-composite-pk-fix
Spec: docs/superpowers/specs/2026-05-13-bot-connection-flow-design.md

После multi-tenancy миграции (V1.17.0a22) в этих таблицах PK/UNIQUE НЕ включают
workspace_id, поэтому два workspace не могут иметь одинаковые ключи. Фиксим
через rebuild-pattern (CREATE...AS SELECT, DROP, RENAME).
"""
import os
import shutil
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'bot_database.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')

# table → новый composite PK (или composite UNIQUE через индекс если так удобнее)
REBUILT_TABLES = {
    'economy_settings':         ['workspace_id', 'key'],
    'economy_section_toggles':  ['workspace_id', 'category'],
    'branding_settings':        ['workspace_id', 'key'],
    'user_stats':               ['workspace_id', 'user_id', 'date'],
    'user_stats_hourly':        ['workspace_id', 'user_id', 'date', 'hour'],
    'chat_stats':               ['workspace_id', 'date'],
    'topics':                   ['workspace_id', 'chat_id', 'thread_id'],
}


def backup_db(db_path: str = DB_PATH) -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(BACKUP_DIR, f'pre_composite_pk_{ts}.db')
    shutil.copy2(db_path, dest)
    return dest


def _rebuild_table(conn: sqlite3.Connection, tbl: str, pk_cols: list[str]) -> None:
    """Пересоздаёт таблицу с composite PK через CREATE AS SELECT."""
    # Get full column list with types
    cols_info = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
    if not cols_info:
        print(f'[skip] {tbl}: table does not exist')
        return
    col_defs = []
    col_names = []
    for cid, name, ctype, notnull, dflt, pk in cols_info:
        d = f"{name} {ctype}"
        if notnull:
            d += " NOT NULL"
        if dflt is not None:
            d += f" DEFAULT {dflt}"
        col_defs.append(d)
        col_names.append(name)
    col_defs.append(f"PRIMARY KEY ({', '.join(pk_cols)})")
    cols_csv = ', '.join(col_names)
    create_sql = f"CREATE TABLE {tbl}__new ({', '.join(col_defs)})"

    conn.execute(create_sql)
    conn.execute(f"INSERT INTO {tbl}__new ({cols_csv}) SELECT {cols_csv} FROM {tbl}")
    conn.execute(f"DROP TABLE {tbl}")
    conn.execute(f"ALTER TABLE {tbl}__new RENAME TO {tbl}")
    # Восстановить idx_<tbl>_workspace
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_workspace ON {tbl}(workspace_id)")
    print(f'[ok] rebuilt {tbl} with PK {pk_cols}')


def migrate_up(db_path: str = DB_PATH) -> str:
    backup = backup_db(db_path)
    print(f'[backup] {backup}')
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        for tbl, pk_cols in REBUILT_TABLES.items():
            _rebuild_table(conn, tbl, pk_cols)
        conn.commit()
    finally:
        conn.close()
    print('[done] composite_pk_fix migrate_up complete')
    return backup


def _restore_single_pk(conn: sqlite3.Connection, tbl: str, single_pk: str) -> None:
    """Откат: пересоздать таблицу с одиночным PK (как было до)."""
    cols_info = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
    if not cols_info:
        return
    col_defs = []
    col_names = []
    for cid, name, ctype, notnull, dflt, pk in cols_info:
        d = f"{name} {ctype}"
        if name == single_pk:
            d += " PRIMARY KEY"
        elif notnull:
            d += " NOT NULL"
        if dflt is not None and name != single_pk:
            d += f" DEFAULT {dflt}"
        col_defs.append(d)
        col_names.append(name)
    cols_csv = ', '.join(col_names)
    conn.execute(f"CREATE TABLE {tbl}__old ({', '.join(col_defs)})")
    conn.execute(f"INSERT INTO {tbl}__old ({cols_csv}) SELECT {cols_csv} FROM {tbl}")
    conn.execute(f"DROP TABLE {tbl}")
    conn.execute(f"ALTER TABLE {tbl}__old RENAME TO {tbl}")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_workspace ON {tbl}(workspace_id)")


_ORIGINAL_PK = {
    'economy_settings':        'key',
    'economy_section_toggles': 'category',
    'branding_settings':       'key',
}


def migrate_down(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        for tbl, single_pk in _ORIGINAL_PK.items():
            _restore_single_pk(conn, tbl, single_pk)
        # user_stats/chat_stats/topics/user_stats_hourly — оригинально без PK, только UNIQUE.
        # Восстановить через DROP PRIMARY KEY невозможно — пересоздать без PK clause.
        for tbl in ('user_stats', 'user_stats_hourly', 'chat_stats', 'topics'):
            cols_info = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
            if not cols_info:
                continue
            col_defs = []
            col_names = []
            for cid, name, ctype, notnull, dflt, pk in cols_info:
                d = f"{name} {ctype}"
                if notnull and name != 'workspace_id':
                    d += " NOT NULL"
                if dflt is not None:
                    d += f" DEFAULT {dflt}"
                col_defs.append(d)
                col_names.append(name)
            cols_csv = ', '.join(col_names)
            conn.execute(f"CREATE TABLE {tbl}__old ({', '.join(col_defs)})")
            conn.execute(f"INSERT INTO {tbl}__old ({cols_csv}) SELECT {cols_csv} FROM {tbl}")
            conn.execute(f"DROP TABLE {tbl}")
            conn.execute(f"ALTER TABLE {tbl}__old RENAME TO {tbl}")
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_workspace ON {tbl}(workspace_id)")
        conn.commit()
    finally:
        conn.close()
    print('[done] composite_pk_fix migrate_down complete')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'down':
        migrate_down()
    else:
        migrate_up()
```

- [ ] **Step 4: Запустить тесты — все должны пройти**

Run: `pytest tests/test_composite_pk_fix.py -v`
Expected: 5 passed

- [ ] **Step 5: Применить миграцию к dev-БД**

Run: `python -m database.migrations.composite_pk_fix`
Expected: `[backup] ...` + `[ok] rebuilt ...` ×7 + `[done]`

- [ ] **Step 6: Прогнать ВСЕ multi-tenancy тесты чтобы убедиться что ничего не сломалось**

Run: `pytest tests/test_multi_tenancy_migration.py tests/test_db_workspaces.py tests/test_workspace_context.py tests/test_economy_isolation.py -v`
Expected: 28 passed

- [ ] **Step 7: Commit**

```bash
git add database/migrations/composite_pk_fix.py tests/test_composite_pk_fix.py
git commit -m "feat(V1.17.0b1): composite PK fix — 7 таблиц rebuild с (workspace_id, ...) PK"
```

---

### Task 2: Расширить bot_chats (added_by/title/type/added_at)

**Files:**
- Create: `database/migrations/bot_chats_extend.py`
- Test: `tests/test_bot_chats_extend.py`

- [ ] **Step 1: Failing-тест**

```python
# tests/test_bot_chats_extend.py
import os, shutil, sqlite3, pytest
from database.migrations.bot_chats_extend import migrate_up, NEW_COLUMNS


@pytest.fixture
def db_copy(tmp_path):
    src = os.path.join(os.path.dirname(__file__), '..', 'database', 'bot_database.db')
    dst = tmp_path / 'test.db'
    shutil.copy2(src, dst)
    return str(dst)


def test_adds_all_new_columns(db_copy):
    migrate_up(db_copy)
    conn = sqlite3.connect(db_copy)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chats)").fetchall()]
    for new_col in NEW_COLUMNS:
        assert new_col in cols, f'{new_col} missing'
    conn.close()


def test_idempotent(db_copy):
    migrate_up(db_copy)
    migrate_up(db_copy)  # second call should not error
    conn = sqlite3.connect(db_copy)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chats)").fetchall()]
    # No duplicates
    assert len(cols) == len(set(cols))
    conn.close()
```

- [ ] **Step 2: Verify fails**

Run: `pytest tests/test_bot_chats_extend.py -v`
Expected: ModuleNotFoundError

- [ ] **Step 3: Implement**

```python
# database/migrations/bot_chats_extend.py
"""Миграция: расширение bot_chats для self-onboarding.
ID: 2026-05-13-bot-chats-extend
"""
import os, sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'bot_database.db')

NEW_COLUMNS = {
    'added_by_user_id': 'INTEGER',
    'title':            'TEXT',
    'chat_type':        'TEXT',
    'added_at':         'TEXT',
}


def migrate_up(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chats)").fetchall()]
        for name, typ in NEW_COLUMNS.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE bot_chats ADD COLUMN {name} {typ}")
                print(f"[ok] added bot_chats.{name}")
            else:
                print(f"[skip] bot_chats.{name} already exists")
        conn.commit()
    finally:
        conn.close()
    print('[done] bot_chats_extend complete')


if __name__ == '__main__':
    migrate_up()
```

- [ ] **Step 4: Test passes**

Run: `pytest tests/test_bot_chats_extend.py -v`
Expected: 2 passed

- [ ] **Step 5: Apply to dev DB**

Run: `python -m database.migrations.bot_chats_extend`

- [ ] **Step 6: Commit**

```bash
git add database/migrations/bot_chats_extend.py tests/test_bot_chats_extend.py
git commit -m "feat(V1.17.0b2): bot_chats — добавлены added_by_user_id/title/chat_type/added_at"
```

---

### Task 3: Расширить db_workspaces.py — функции для UI

**Files:**
- Modify: `database/db_workspaces.py`
- Modify: `tests/test_db_workspaces.py`

- [ ] **Step 1: Failing-тесты в существующий файл**

Прочитать `tests/test_db_workspaces.py` и в конец добавить:

```python
def test_get_workspaces_for_user_returns_only_membered(conn):
    from database.db_workspaces import create_workspace, add_member, get_workspaces_for_user
    create_workspace(conn, 'WS A', owner_user_id=1)
    create_workspace(conn, 'WS B', owner_user_id=2)
    add_member(conn, 1, 99, 'admin')   # user 99 в WS A
    rows = get_workspaces_for_user(conn, user_id=99)
    assert len(rows) == 1
    assert rows[0]['name'] == 'WS A'
    assert rows[0]['role'] == 'admin'


def test_get_workspaces_includes_owned(conn):
    from database.db_workspaces import create_workspace, get_workspaces_for_user
    create_workspace(conn, 'Mine', owner_user_id=42)
    rows = get_workspaces_for_user(conn, user_id=42)
    assert len(rows) == 1
    assert rows[0]['role'] == 'owner'


def test_get_workspace_details_returns_members_and_chats(conn):
    from database.db_workspaces import create_workspace, add_member, add_bot_chat, get_workspace_details
    create_workspace(conn, 'X', owner_user_id=1)
    add_member(conn, 1, 99, 'admin')
    add_bot_chat(conn, chat_id=-100, workspace_id=1, added_by=1,
                 title='Main', chat_type='supergroup')
    details = get_workspace_details(conn, workspace_id=1)
    assert details['workspace']['name'] == 'X'
    assert len(details['members']) == 2  # owner + admin
    assert len(details['chats']) == 1
    assert details['chats'][0]['title'] == 'Main'


def test_update_workspace_name(conn):
    from database.db_workspaces import create_workspace, update_workspace_name, get_workspace
    create_workspace(conn, 'OLD', owner_user_id=1)
    update_workspace_name(conn, workspace_id=1, new_name='NEW')
    ws = get_workspace(conn, 1)
    assert ws['name'] == 'NEW'
```

И обновить fixture в `test_db_workspaces.py` чтобы создавал `bot_chats` table:

```python
# в fixture conn():
c.execute('''CREATE TABLE bot_chats (
    chat_id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL DEFAULT 1,
    added_by_user_id INTEGER,
    title TEXT,
    chat_type TEXT,
    added_at TEXT
)''')
```

- [ ] **Step 2: Verify fails**

Run: `pytest tests/test_db_workspaces.py::test_get_workspaces_for_user_returns_only_membered -v`
Expected: AttributeError

- [ ] **Step 3: Implement**

Добавить в `database/db_workspaces.py`:

```python
def get_workspaces_for_user(conn, user_id: int) -> list[dict]:
    """Возвращает все workspace где user — member (owner/admin/moderator).
    Включает счётчики members_count и chats_count."""
    rows = conn.execute('''
        SELECT
            w.id, w.name, w.owner_user_id, w.is_pulse_themed, w.plan,
            m.role,
            (SELECT COUNT(*) FROM workspace_members WHERE workspace_id=w.id) AS members_count,
            (SELECT COUNT(*) FROM bot_chats WHERE workspace_id=w.id) AS chats_count
        FROM workspaces w
        JOIN workspace_members m ON m.workspace_id = w.id
        WHERE m.user_id = ?
        ORDER BY w.created_at DESC
    ''', (user_id,)).fetchall()
    keys = ('id', 'name', 'owner_user_id', 'is_pulse_themed', 'plan',
            'role', 'members_count', 'chats_count')
    return [dict(zip(keys, r)) for r in rows]


def get_workspace_details(conn, workspace_id: int) -> dict | None:
    """Workspace + список членов + список чатов."""
    ws_row = conn.execute(
        'SELECT id, name, owner_user_id, is_pulse_themed, plan, created_at '
        'FROM workspaces WHERE id=?', (workspace_id,)
    ).fetchone()
    if not ws_row:
        return None

    members = conn.execute('''
        SELECT user_id, role, joined_at
        FROM workspace_members WHERE workspace_id=?
        ORDER BY CASE role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,
                 joined_at
    ''', (workspace_id,)).fetchall()

    chats = conn.execute('''
        SELECT chat_id, title, chat_type, added_by_user_id, added_at
        FROM bot_chats WHERE workspace_id=?
        ORDER BY added_at DESC
    ''', (workspace_id,)).fetchall()

    return {
        'workspace': {
            'id': ws_row[0], 'name': ws_row[1], 'owner_user_id': ws_row[2],
            'is_pulse_themed': bool(ws_row[3]), 'plan': ws_row[4],
            'created_at': ws_row[5],
        },
        'members': [{'user_id': m[0], 'role': m[1], 'joined_at': m[2]} for m in members],
        'chats': [{'chat_id': c[0], 'title': c[1], 'chat_type': c[2],
                   'added_by': c[3], 'added_at': c[4]} for c in chats],
    }


def update_workspace_name(conn, workspace_id: int, new_name: str) -> None:
    conn.execute(
        "UPDATE workspaces SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (new_name, workspace_id)
    )
    conn.commit()


def add_bot_chat(conn, chat_id: int, workspace_id: int, added_by: int,
                 title: str | None, chat_type: str | None) -> None:
    conn.execute('''
        INSERT INTO bot_chats (chat_id, workspace_id, added_by_user_id, title, chat_type, added_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id) DO UPDATE SET
          workspace_id=excluded.workspace_id,
          added_by_user_id=excluded.added_by_user_id,
          title=excluded.title,
          chat_type=excluded.chat_type
    ''', (chat_id, workspace_id, added_by, title, chat_type))
    conn.commit()


def get_workspace_by_chat(conn, chat_id: int) -> int | None:
    """Возвращает workspace_id если chat привязан, иначе None."""
    row = conn.execute(
        'SELECT workspace_id FROM bot_chats WHERE chat_id=?', (chat_id,)
    ).fetchone()
    return row[0] if row else None
```

- [ ] **Step 4: Tests pass**

Run: `pytest tests/test_db_workspaces.py -v`
Expected: All passed (existing 7 + new 4)

- [ ] **Step 5: Commit**

```bash
git add database/db_workspaces.py tests/test_db_workspaces.py
git commit -m "feat(V1.17.0b3): db_workspaces — get_workspaces_for_user/get_workspace_details/add_bot_chat/update_name"
```

---

## Phase 2 — Bot core

### Task 4: handlers/bot_membership.py — on_bot_added_to_chat

**Files:**
- Create: `handlers/bot_membership.py`
- Test: `tests/test_bot_membership.py`

- [ ] **Step 1: Failing-тесты (4 кейса)**

```python
# tests/test_bot_membership.py
"""Тесты ChatMemberHandler для само-онбординга."""
import pytest
import sqlite3
from unittest.mock import AsyncMock, MagicMock

from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import (
    create_workspace, add_member, add_bot_chat,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(':memory:')
    up_create_workspaces_tables(conn)
    conn.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL DEFAULT 1,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT, added_at TEXT
    )''')
    conn.execute('''CREATE TABLE users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT
    )''')

    class _DB:
        def __init__(self, c): self.conn = c
        def get_site_user(self, uid):
            row = c.execute("SELECT user_id, username FROM users WHERE user_id=?", (uid,)).fetchone()
            return {'user_id': row[0], 'username': row[1]} if row else None
        def get_workspace_by_chat(self, chat_id):
            from database.db_workspaces import get_workspace_by_chat
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
    ws = db.conn.execute("SELECT name, owner_user_id FROM workspaces WHERE id=?", (ws_id,)).fetchone()
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
    # Не пересоздаём workspace для занятого чата
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
```

- [ ] **Step 2: Verify fails**

Run: `pytest tests/test_bot_membership.py -v`
Expected: ModuleNotFoundError для `handlers.bot_membership`

- [ ] **Step 3: Implement**

```python
# handlers/bot_membership.py
"""ChatMemberHandler: само-онбординг при добавлении бота в чат."""
import logging
import os

from database.db_workspaces import (
    create_workspace, add_member, add_bot_chat,
)
from bot_core.workspace_context import invalidate_cache

logger = logging.getLogger(__name__)

SITE_URL = os.getenv('SITE_URL', 'https://puls-chat.ru')


async def on_bot_added_to_chat(update, context, db):
    """Обработчик ChatMemberHandler.MY_CHAT_MEMBER.

    Срабатывает когда меняется membership самого бота. Если бот добавлен
    как member/administrator в новый чат:
      - проверяем что from_user зарегистрирован на сайте (есть в users)
      - проверяем что chat не привязан к другому workspace
      - создаём workspace + members + bot_chats
      - сообщения в чат и владельцу в DM
    Если from_user не зарегистрирован или чат занят — leave_chat.
    """
    new = update.my_chat_member.new_chat_member
    if new.user.id != context.bot.id:
        return  # не про нас

    if new.status not in ('member', 'administrator'):
        return  # left/kicked/restricted — отдельные обработчики, не сейчас

    chat = update.my_chat_member.chat
    from_user = update.my_chat_member.from_user
    chat_id = chat.id
    chat_title = chat.title or f"Чат {chat_id}"

    # Check 1: chat already bound to another workspace?
    existing_ws = db.get_workspace_by_chat(chat_id)
    if existing_ws is not None:
        try:
            await context.bot.send_message(
                chat_id,
                "❌ Этот чат уже привязан к другому сообществу на Pulse SaaS."
            )
        except Exception as e:
            logger.warning(f"send_message in already-bound chat failed: {e}")
        try:
            await context.bot.leave_chat(chat_id)
        except Exception as e:
            logger.warning(f"leave_chat failed: {e}")
        return

    # Check 2: from_user registered on site?
    site_user = db.get_site_user(from_user.id)
    if not site_user:
        try:
            await context.bot.send_message(
                chat_id,
                f"❌ Тот, кто меня добавил, не зарегистрирован на сайте.\n"
                f"Зайди сюда: {SITE_URL}/login и попробуй снова."
            )
        except Exception as e:
            logger.warning(f"send_message to unregistered chat failed: {e}")
        try:
            await context.bot.leave_chat(chat_id)
        except Exception as e:
            logger.warning(f"leave_chat (unregistered) failed: {e}")
        return

    # Create workspace + member + chat binding
    ws_id = create_workspace(db.conn, chat_title, owner_user_id=from_user.id)
    add_member(db.conn, ws_id, from_user.id, 'owner')
    add_bot_chat(db.conn, chat_id, ws_id, added_by=from_user.id,
                 title=chat_title, chat_type=chat.type)
    invalidate_cache(chat_id)
    logger.info(f"Created workspace_id={ws_id} for chat {chat_id} owner={from_user.id}")

    # Notify in-chat + DM
    try:
        await context.bot.send_message(
            chat_id,
            f"✅ Сообщество «{chat_title}» подключено к Pulse SaaS.\n"
            f"Управление — на сайте: {SITE_URL}"
        )
    except Exception as e:
        logger.warning(f"send_message after workspace creation failed: {e}")
    try:
        await context.bot.send_message(
            from_user.id,
            f"✅ Чат «{chat_title}» добавлен в твой кабинет.\n"
            f"Зайди на сайт чтобы настроить: {SITE_URL}"
        )
    except Exception as e:
        logger.warning(f"DM to owner failed: {e}")
```

- [ ] **Step 4: Tests pass**

Run: `pytest tests/test_bot_membership.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add handlers/bot_membership.py tests/test_bot_membership.py
git commit -m "feat(V1.17.0b4): handlers/bot_membership — само-онбординг чата при add"
```

---

### Task 5: Регистрация ChatMemberHandler в bot.py + добавить get_site_user в Database

**Files:**
- Modify: `bot.py`
- Modify: `database/db_manager.py`

- [ ] **Step 1: Failing-тест**

Добавить в `tests/test_db_workspaces.py`:

```python
def test_get_site_user_via_db_manager(tmp_path):
    """Database.get_site_user возвращает запись из users или None."""
    import os
    db_path = tmp_path / 'test.db'
    # Минимальная инициализация
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT)")
    conn.execute("INSERT INTO users (user_id, username, first_name) VALUES (42, 'alice', 'Alice')")
    conn.commit()
    conn.close()

    from database.db_manager import Database
    db = Database(db_path=str(db_path))
    assert db.get_site_user(42) == {'user_id': 42, 'username': 'alice', 'first_name': 'Alice'}
    assert db.get_site_user(999) is None
```

- [ ] **Step 2: Verify fails**

Run: `pytest tests/test_db_workspaces.py::test_get_site_user_via_db_manager -v`
Expected: AttributeError get_site_user

- [ ] **Step 3: Implement в db_manager.py**

Добавить метод в класс `Database`:

```python
def get_site_user(self, user_id: int) -> dict | None:
    """Возвращает {user_id, username, first_name} если юзер логинился (есть в users), иначе None.
    Используется bot_membership handler для проверки.
    """
    self.cursor.execute(
        "SELECT user_id, username, first_name FROM users WHERE user_id=?", (user_id,)
    )
    row = self.cursor.fetchone()
    if not row:
        return None
    return {
        'user_id':    row['user_id']    if hasattr(row, 'keys') else row[0],
        'username':   row['username']   if hasattr(row, 'keys') else row[1],
        'first_name': row['first_name'] if hasattr(row, 'keys') else row[2],
    }


def get_workspace_by_chat(self, chat_id: int) -> int | None:
    from database.db_workspaces import get_workspace_by_chat as _impl
    return _impl(self.conn, chat_id)
```

- [ ] **Step 4: Test passes**

Run: `pytest tests/test_db_workspaces.py::test_get_site_user_via_db_manager -v`
Expected: PASS

- [ ] **Step 5: Регистрация в bot.py**

В `bot.py.setup_handlers()` после регистрации TypeHandler (middleware) добавить:

```python
from telegram.ext import ChatMemberHandler
from handlers.bot_membership import on_bot_added_to_chat

self.application.add_handler(
    ChatMemberHandler(
        lambda u, c: on_bot_added_to_chat(u, c, self.db),
        ChatMemberHandler.MY_CHAT_MEMBER
    )
)
```

- [ ] **Step 6: Smoke import**

Run: `python -c "from dotenv import load_dotenv; load_dotenv(); import bot; print('OK')"`
Expected: `bot import OK` без traceback

- [ ] **Step 7: Commit**

```bash
git add bot.py database/db_manager.py tests/test_db_workspaces.py
git commit -m "feat(V1.17.0b5): ChatMemberHandler регистрация + Database.get_site_user/get_workspace_by_chat"
```

---

### Task 6: /start command routing — join_<ws> + default site link

**Files:**
- Modify: `handlers/commands/system_commands.py`
- Test: `tests/test_start_command_routing.py`

- [ ] **Step 1: Изучить текущий /start**

Run: `grep -n "start_command\|def start\b" handlers/commands/system_commands.py | head`

Прочитать обработчик чтобы знать как он сейчас сопоставлен с registration_conversation.

- [ ] **Step 2: Failing-тест**

```python
# tests/test_start_command_routing.py
"""Тесты роутинга /start по deep-link параметрам."""
import pytest
from unittest.mock import AsyncMock, MagicMock


def _make_update_message(text):
    upd = MagicMock()
    upd.message.text = text
    upd.message.reply_text = AsyncMock()
    upd.effective_user.id = 100
    upd.effective_chat.type = 'private'
    return upd


def _make_context(args):
    ctx = MagicMock()
    ctx.args = args
    return ctx


@pytest.mark.asyncio
async def test_start_no_args_shows_site_link():
    from handlers.commands.system_commands import start_command
    db = MagicMock()
    upd = _make_update_message('/start')
    ctx = _make_context(args=[])
    await start_command(upd, ctx, db)
    call_text = upd.message.reply_text.call_args[0][0]
    assert 'сайт' in call_text.lower() or 'site' in call_text.lower()


@pytest.mark.asyncio
async def test_start_join_unknown_ws_shows_not_found():
    from handlers.commands.system_commands import start_command
    db = MagicMock()
    db.get_workspace = MagicMock(return_value=None)
    upd = _make_update_message('/start')
    ctx = _make_context(args=['join_999'])
    await start_command(upd, ctx, db)
    call_text = upd.message.reply_text.call_args[0][0]
    assert 'не найден' in call_text.lower()


@pytest.mark.asyncio
async def test_start_join_pulse_triggers_pulse_anketa(monkeypatch):
    from handlers.commands import system_commands
    db = MagicMock()
    db.get_workspace = MagicMock(return_value={'id': 1, 'is_pulse_themed': True, 'name': 'Pulse'})
    called = {'pulse_flow': False}
    async def fake_pulse(u, c, d):
        called['pulse_flow'] = True
    monkeypatch.setattr(system_commands, 'start_pulse_registration', fake_pulse)
    upd = _make_update_message('/start')
    ctx = _make_context(args=['join_1'])
    await system_commands.start_command(upd, ctx, db)
    assert called['pulse_flow'] is True


@pytest.mark.asyncio
async def test_start_join_nonpulse_shows_welcome():
    from handlers.commands.system_commands import start_command
    db = MagicMock()
    db.get_workspace = MagicMock(return_value={
        'id': 42, 'is_pulse_themed': False, 'name': 'TestWS'
    })
    upd = _make_update_message('/start')
    ctx = _make_context(args=['join_42'])
    await start_command(upd, ctx, db)
    call_text = upd.message.reply_text.call_args[0][0]
    assert 'TestWS' in call_text
    assert 'добро пожаловать' in call_text.lower()
```

- [ ] **Step 3: Verify fails**

Run: `pytest tests/test_start_command_routing.py -v`
Expected: fail (текущий start_command не имеет такой логики)

- [ ] **Step 4: Implement**

В `handlers/commands/system_commands.py` найти текущий `start_command` и заменить (или дополнить) логикой:

```python
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

SITE_URL = os.getenv('SITE_URL', 'https://puls-chat.ru')


async def start_pulse_registration(update, context, db):
    """Запускает старую Pulse-анкету (registration_conversation).
    Делегирует в существующий handler. Реализация-обёртка для testability."""
    from handlers.registration_conversation import start_registration as _impl
    return await _impl(update, context)


async def start_command(update, context, db):
    """Маршрутизатор /start:
      /start             → DM welcome + кнопка «Открыть сайт»
      /start join_<ws>   → welcome выбранного workspace (или Pulse-анкета для ws=1)
      /start own         → синоним default
    """
    args = getattr(context, 'args', []) or []
    user_id = update.effective_user.id

    # join_<ws_id>
    if args and args[0].startswith('join_'):
        try:
            ws_id = int(args[0][5:])
        except ValueError:
            await update.message.reply_text("❌ Некорректная ссылка.")
            return
        ws = db.get_workspace(ws_id)
        if not ws:
            await update.message.reply_text("❌ Сообщество не найдено.")
            return
        if ws['is_pulse_themed']:
            return await start_pulse_registration(update, context, db)
        # generic non-Pulse welcome
        await update.message.reply_text(
            f"👋 Добро пожаловать в «{ws['name']}»!\n"
            f"Скоро здесь будет регистрационная анкета этого сообщества. "
            f"Пока — просто подожди приглашение от админов."
        )
        return

    # default + /start own
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🌐 Открыть сайт", url=SITE_URL)
    ]])
    await update.message.reply_text(
        "Привет 👋 Я Pulse Bot.\n\n"
        "Чтобы подключить свой чат к платформе — открой сайт и войди через Telegram.",
        reply_markup=keyboard
    )
```

И в `bot.py.setup_handlers()` убедиться что `start_command` зарегистрирован как CommandHandler('start', ...) ПОСЛЕ или вместо текущей registration-conversation. Если registration_conv был ConversationHandler с entry_points=[CommandHandler('start', ...)] — поменять entry_points на новый `start_command` (внутри которого Pulse-anketa триггерится только из `join_1`).

В bot.py найти строку регистрации registration_conv и обернуть так:

```python
# OLD: self.application.add_handler(registration_conv)
# NEW: start_command сам решает запускать ли registration_conv

from handlers.commands.system_commands import start_command
self.application.add_handler(
    CommandHandler('start', lambda u, c: start_command(u, c, self.db))
)
# registration_conv остаётся зарегистрированным для completion FSM steps,
# но entry_point /start теперь идёт через start_command. Для этого
# нужно убрать /start entry_point из registration_conv (либо понизить group):
# self.application.add_handler(registration_conv, group=1)
```

- [ ] **Step 5: Tests pass**

Run: `pytest tests/test_start_command_routing.py -v`
Expected: 4 passed

- [ ] **Step 6: Smoke import + manual ручная проверка**

Run:
```bash
python -c "from dotenv import load_dotenv; load_dotenv(); import bot; print('OK')"
```

Затем локально запустить бот, проверить:
- `/start` в DM → "Открыть сайт"
- `/start join_1` в DM (Pulse) → запускается анкета
- `/start join_999` → "не найдено"

- [ ] **Step 7: Commit**

```bash
git add handlers/commands/system_commands.py bot.py tests/test_start_command_routing.py
git commit -m "feat(V1.17.0b6): /start routing — join_<ws> deep-link, Pulse-анкета только для ws=1"
```

---

### Task 7: Убрать middleware fallback ws=1 для unknown chats

**Files:**
- Modify: `bot.py` (resolve_workspace_middleware)
- Modify: `tests/test_workspace_context.py`

- [ ] **Step 1: Failing-тест**

Добавить в `tests/test_workspace_context.py`:

```python
def test_build_context_no_fallback_for_unknown_chat(conn):
    """Для chat не зарегистрированного в bot_chats build_context возвращает None
    (а не Pulse fallback)."""
    ctx = build_context(conn, chat_id=-99999, user_id=1)
    assert ctx is None
```

- [ ] **Step 2: Verify passes (это уже текущее поведение build_context)**

Run: `pytest tests/test_workspace_context.py::test_build_context_no_fallback_for_unknown_chat -v`
Expected: PASS (build_context уже возвращает None для unknown — fallback стоит в middleware, не в build_context)

- [ ] **Step 3: Изменить middleware**

В `bot.py.resolve_workspace_middleware` заменить:

```python
if ws_ctx is None:
    # Fallback на Pulse (ws=1) до Bot connection flow (#2)
    ws_ctx = WorkspaceContext(
        workspace_id=1,
        is_pulse_themed=True,
        plan='free',
        member_role=None,
    )
```

На:

```python
if ws_ctx is None:
    # V1.17.0b7: для unknown chat ws_ctx остаётся None.
    # Декораторы @pulse_only безопасно скипают handlers (allow для DM-команд
    # которые не нуждаются в workspace context).
    pass

context.user_data['ws_ctx'] = ws_ctx  # may be None
context.chat_data['ws_ctx'] = ws_ctx
```

Также убрать дефолтный Pulse fallback в except-блоке — поставить `ws_ctx=None` чтобы handlers ничего не пускали без явного workspace.

- [ ] **Step 4: Smoke прогон всех тестов**

Run: `pytest tests/ -q --ignore=tests/test_shop_mechanics.py`
Expected: 32+ passed (28 multi-tenancy + 5 composite + новые)

- [ ] **Step 5: Smoke import**

Run: `python -c "from dotenv import load_dotenv; load_dotenv(); import bot; print('OK')"`

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_workspace_context.py
git commit -m "feat(V1.17.0b7): убрать middleware fallback ws=1 — после #2 unknown chats честно None"
```

---

## Phase 3 — API endpoints

### Task 8: GET /api/workspaces — список моих сообществ

**Files:**
- Create: `api/workspaces_routes.py`
- Modify: `api.py` (include_router)
- Test: `tests/test_workspaces_api.py`

- [ ] **Step 1: Failing-тест**

```python
# tests/test_workspaces_api.py
"""Тесты API /api/workspaces/*."""
import sqlite3
import pytest
from fastapi.testclient import TestClient

from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import create_workspace, add_member, add_bot_chat


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / 'test.db'
    conn = sqlite3.connect(str(db_path))
    up_create_workspaces_tables(conn)
    conn.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL DEFAULT 1,
        added_by_user_id INTEGER, title TEXT, chat_type TEXT, added_at TEXT
    )''')
    conn.execute('''CREATE TABLE users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT
    )''')

    create_workspace(conn, 'My WS', owner_user_id=42)
    create_workspace(conn, 'Other WS', owner_user_id=99)
    add_member(conn, 1, 42, 'owner')
    add_member(conn, 1, 100, 'admin')   # 100 — member чужого
    add_bot_chat(conn, -100, 1, 42, 'My Main', 'supergroup')
    conn.commit()

    # Mock JWT-auth
    from api.workspaces_routes import router, _setup
    class _DB:
        def __init__(self, c):
            self.conn = c
            self.cursor = c.cursor()
        def get_workspace_by_chat(self, chat_id):
            from database.db_workspaces import get_workspace_by_chat
            return get_workspace_by_chat(self.conn, chat_id)
    fake_db = _DB(conn)

    def fake_require_auth(authorization):
        # In tests, parse "Bearer fake-<user_id>"
        token = authorization.replace('Bearer ', '')
        if not token.startswith('fake-'):
            from fastapi import HTTPException
            raise HTTPException(401)
        return {'user_id': int(token[5:])}

    _setup(fake_db, fake_require_auth)

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_get_workspaces_returns_only_user_membered(client):
    r = client.get('/api/workspaces', headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    data = r.json()
    assert len(data['workspaces']) == 1
    assert data['workspaces'][0]['name'] == 'My WS'
    assert data['workspaces'][0]['role'] == 'owner'


def test_get_workspaces_admin_role(client):
    r = client.get('/api/workspaces', headers={'Authorization': 'Bearer fake-100'})
    assert r.status_code == 200
    data = r.json()
    assert data['workspaces'][0]['role'] == 'admin'


def test_get_workspaces_no_auth(client):
    r = client.get('/api/workspaces')
    assert r.status_code == 401


def test_get_workspaces_empty_for_new_user(client):
    r = client.get('/api/workspaces', headers={'Authorization': 'Bearer fake-555'})
    assert r.status_code == 200
    assert r.json()['workspaces'] == []
```

- [ ] **Step 2: Verify fails**

Run: `pytest tests/test_workspaces_api.py -v`
Expected: ModuleNotFoundError api.workspaces_routes

- [ ] **Step 3: Implement**

```python
# api/workspaces_routes.py
"""Endpoints: /api/workspaces, /api/workspaces/{id}, /workspaces/{id}/members."""
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from database.db_workspaces import (
    get_workspaces_for_user, get_workspace_details, update_workspace_name,
    add_member, remove_member,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

_db = None
_require_auth_fn = None


def _setup(db, require_auth):
    global _db, _require_auth_fn
    _db = db
    _require_auth_fn = require_auth


def _auth(authorization: str) -> dict:
    return _require_auth_fn(authorization)


def _check_role(workspace_id: int, user_id: int, required_role: str = 'moderator') -> str:
    """Возвращает роль юзера в WS или 403/404."""
    row = _db.conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (workspace_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Сообщество не найдено или вы не член")
    role = row[0]
    rank = {'owner': 3, 'admin': 2, 'moderator': 1}
    if rank.get(role, 0) < rank.get(required_role, 0):
        raise HTTPException(status_code=403, detail=f"Нужна роль {required_role} или выше")
    return role


@router.get("")
async def list_workspaces(authorization: str = Header(default=None)):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    rows = get_workspaces_for_user(_db.conn, user_id)
    return {"workspaces": rows}
```

В `api.py` после остальных `include_router`:

```python
try:
    from api.workspaces_routes import router as workspaces_router, _setup as _ws_setup
    _ws_setup(db, lambda auth: _require_auth(auth))
    app.include_router(workspaces_router)
    logger.info("✅ /api/workspaces подключён")
except Exception as e:
    logger.error(f"Workspaces router setup failed: {e}")
```

- [ ] **Step 4: Tests pass**

Run: `pytest tests/test_workspaces_api.py -v`
Expected: 4 passed (test_get_workspaces_*)

- [ ] **Step 5: Commit**

```bash
git add api/workspaces_routes.py api.py tests/test_workspaces_api.py
git commit -m "feat(V1.17.0b8): GET /api/workspaces — список моих сообществ"
```

---

### Task 9: GET /api/workspaces/{id} — детали + members + chats

**Files:**
- Modify: `api/workspaces_routes.py`
- Modify: `tests/test_workspaces_api.py`

- [ ] **Step 1: Failing-тест**

```python
def test_get_workspace_details(client):
    r = client.get('/api/workspaces/1', headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    data = r.json()
    assert data['workspace']['name'] == 'My WS'
    assert len(data['members']) == 2
    assert len(data['chats']) == 1
    assert data['chats'][0]['title'] == 'My Main'


def test_get_workspace_details_non_member_forbidden(client):
    r = client.get('/api/workspaces/1', headers={'Authorization': 'Bearer fake-555'})
    assert r.status_code == 404  # не член
```

- [ ] **Step 2: Verify fails**

Run: `pytest tests/test_workspaces_api.py::test_get_workspace_details -v`
Expected: 404 (endpoint не существует)

- [ ] **Step 3: Implement**

В `api/workspaces_routes.py` добавить:

```python
@router.get("/{ws_id}")
async def workspace_details(ws_id: int, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'moderator')
    details = get_workspace_details(_db.conn, ws_id)
    if not details:
        raise HTTPException(status_code=404, detail="Сообщество не найдено")
    return details
```

- [ ] **Step 4: Tests pass**

Run: `pytest tests/test_workspaces_api.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add api/workspaces_routes.py tests/test_workspaces_api.py
git commit -m "feat(V1.17.0b9): GET /api/workspaces/{id} — детали + members + chats"
```

---

### Task 10: POST /api/workspaces/{id}/members + DELETE — управление помощниками

**Files:**
- Modify: `api/workspaces_routes.py`
- Modify: `database/db_workspaces.py` (+ `remove_member`)
- Modify: `tests/test_workspaces_api.py`

- [ ] **Step 1: Failing-тесты**

```python
def test_owner_can_add_admin(client):
    r = client.post(
        '/api/workspaces/1/members',
        json={'user_id': 200, 'role': 'admin'},
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 200


def test_non_owner_cannot_add_member(client):
    r = client.post(
        '/api/workspaces/1/members',
        json={'user_id': 300, 'role': 'admin'},
        headers={'Authorization': 'Bearer fake-100'}  # admin, not owner
    )
    assert r.status_code == 403


def test_add_member_invalid_role(client):
    r = client.post(
        '/api/workspaces/1/members',
        json={'user_id': 200, 'role': 'superadmin'},
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 400


def test_owner_can_remove_admin(client):
    client.post(
        '/api/workspaces/1/members',
        json={'user_id': 200, 'role': 'admin'},
        headers={'Authorization': 'Bearer fake-42'}
    )
    r = client.delete(
        '/api/workspaces/1/members/200',
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 200


def test_owner_cannot_remove_self(client):
    r = client.delete(
        '/api/workspaces/1/members/42',
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 400
```

- [ ] **Step 2: Verify fails**

Run: `pytest tests/test_workspaces_api.py -v`
Expected: 5 failing новых

- [ ] **Step 3: Implement remove_member в db_workspaces**

```python
# database/db_workspaces.py добавить
def remove_member(conn, workspace_id: int, user_id: int) -> None:
    conn.execute(
        "DELETE FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (workspace_id, user_id)
    )
    conn.commit()
```

- [ ] **Step 4: Implement endpoints**

В `api/workspaces_routes.py`:

```python
class MemberAdd(BaseModel):
    user_id: int
    role: str  # 'admin' | 'moderator'


@router.post("/{ws_id}/members")
async def add_workspace_member(
    ws_id: int, body: MemberAdd, authorization: str = Header(default=None)
):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    if body.role not in ('admin', 'moderator'):
        raise HTTPException(status_code=400, detail="Роль должна быть admin или moderator")

    # Lookup: target юзер логинился на сайте?
    target = _db.get_site_user(body.user_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail="Этот юзер ещё не логинился на сайте. Попроси его войти через Telegram."
        )

    # Already member?
    exists = _db.conn.execute(
        "SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (ws_id, body.user_id)
    ).fetchone()
    if exists:
        raise HTTPException(status_code=409, detail="Юзер уже член этого сообщества")

    add_member(_db.conn, ws_id, body.user_id, body.role)
    return {"ok": True, "user_id": body.user_id, "role": body.role}


@router.delete("/{ws_id}/members/{member_user_id}")
async def remove_workspace_member(
    ws_id: int, member_user_id: int,
    authorization: str = Header(default=None)
):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    if member_user_id == user_id:
        raise HTTPException(status_code=400, detail="Owner не может удалить себя")

    target_role = _db.conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (ws_id, member_user_id)
    ).fetchone()
    if not target_role:
        raise HTTPException(status_code=404, detail="Член сообщества не найден")
    if target_role[0] == 'owner':
        raise HTTPException(status_code=400, detail="Owner нельзя удалить (нужен transfer ownership)")

    remove_member(_db.conn, ws_id, member_user_id)
    return {"ok": True}
```

- [ ] **Step 5: Tests pass**

Run: `pytest tests/test_workspaces_api.py -v`
Expected: 11 passed total

- [ ] **Step 6: Commit**

```bash
git add api/workspaces_routes.py database/db_workspaces.py tests/test_workspaces_api.py
git commit -m "feat(V1.17.0b10): /api/workspaces/{id}/members add/delete — owner-only"
```

---

### Task 11: PATCH /api/workspaces/{id} — переименование

**Files:**
- Modify: `api/workspaces_routes.py`
- Modify: `tests/test_workspaces_api.py`

- [ ] **Step 1: Failing-тест**

```python
def test_owner_can_rename(client):
    r = client.patch(
        '/api/workspaces/1',
        json={'name': 'Renamed'},
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 200
    r2 = client.get('/api/workspaces/1', headers={'Authorization': 'Bearer fake-42'})
    assert r2.json()['workspace']['name'] == 'Renamed'


def test_admin_cannot_rename(client):
    r = client.patch(
        '/api/workspaces/1',
        json={'name': 'X'},
        headers={'Authorization': 'Bearer fake-100'}
    )
    assert r.status_code == 403


def test_rename_empty_name_400(client):
    r = client.patch(
        '/api/workspaces/1',
        json={'name': ''},
        headers={'Authorization': 'Bearer fake-42'}
    )
    assert r.status_code == 400
```

- [ ] **Step 2: Verify fails**

Run: `pytest tests/test_workspaces_api.py -v`

- [ ] **Step 3: Implement**

```python
# в api/workspaces_routes.py
class WorkspacePatch(BaseModel):
    name: Optional[str] = None


@router.patch("/{ws_id}")
async def patch_workspace(
    ws_id: int, body: WorkspacePatch, authorization: str = Header(default=None)
):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'owner')

    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=400, detail="Имя не может быть пустым")
        if len(body.name) > 100:
            raise HTTPException(status_code=400, detail="Имя слишком длинное")
        update_workspace_name(_db.conn, ws_id, body.name.strip())

    return {"ok": True}
```

- [ ] **Step 4: Tests pass**

Run: `pytest tests/test_workspaces_api.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add api/workspaces_routes.py tests/test_workspaces_api.py
git commit -m "feat(V1.17.0b11): PATCH /api/workspaces/{id} — переименование owner-only"
```

---

## Phase 4 — UI на сайте

### Task 12: API клиент + хук useWorkspaces

**Files:**
- Modify: `Admin_SITE/components/shared/api.js`
- Create: `Admin_SITE/components/workspaces/useWorkspaces.js`

- [ ] **Step 1: Найти текущий API-клиент**

Run: `grep -rn "fetch.*api\|BASE_URL\|API_URL" Admin_SITE/components/shared/ Admin_SITE/*.jsx | head -10`

Понять каким образом сейчас идут запросы. Если есть существующий wrapper (`api.js`) — расширить, иначе создать.

- [ ] **Step 2: Расширить api.js**

В `Admin_SITE/components/shared/api.js` добавить:

```javascript
export async function fetchWorkspaces(token) {
  const r = await fetch('/api/workspaces', {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!r.ok) throw new Error(`fetchWorkspaces ${r.status}`);
  return r.json();
}

export async function fetchWorkspaceDetails(token, wsId) {
  const r = await fetch(`/api/workspaces/${wsId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!r.ok) throw new Error(`fetchWorkspaceDetails ${r.status}`);
  return r.json();
}

export async function inviteMember(token, wsId, userId, role) {
  const r = await fetch(`/api/workspaces/${wsId}/members`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ user_id: userId, role })
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `inviteMember ${r.status}`);
  }
  return r.json();
}

export async function removeMember(token, wsId, userId) {
  const r = await fetch(`/api/workspaces/${wsId}/members/${userId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!r.ok) throw new Error(`removeMember ${r.status}`);
  return r.json();
}

export async function renameWorkspace(token, wsId, newName) {
  const r = await fetch(`/api/workspaces/${wsId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ name: newName })
  });
  if (!r.ok) throw new Error(`renameWorkspace ${r.status}`);
  return r.json();
}
```

- [ ] **Step 3: Создать useWorkspaces hook**

```javascript
// Admin_SITE/components/workspaces/useWorkspaces.js
import { useEffect, useState, useCallback } from 'react';
import { fetchWorkspaces } from '../shared/api';

export function useWorkspaces(token) {
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError(null);
    try {
      const data = await fetchWorkspaces(token);
      setWorkspaces(data.workspaces || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { reload(); }, [reload]);

  // Polling каждые 30 сек на случай добавления нового чата через бота
  useEffect(() => {
    if (!token) return;
    const id = setInterval(reload, 30000);
    return () => clearInterval(id);
  }, [token, reload]);

  return { workspaces, loading, error, reload };
}
```

- [ ] **Step 4: Build проверка**

Run: `cd Admin_SITE && npm run build`
Expected: build success без ошибок

- [ ] **Step 5: Commit**

```bash
git add Admin_SITE/components/shared/api.js Admin_SITE/components/workspaces/useWorkspaces.js
git commit -m "feat(V1.17.0b12): [Site] api wrapper + useWorkspaces hook"
```

---

### Task 13: WorkspaceList — карточка списка сообществ на дашборде

**Files:**
- Create: `Admin_SITE/components/workspaces/WorkspaceList.jsx`
- Modify: `Admin_SITE/AdminDashboard.jsx` (заменить блок "Без чата" + "Чат")

- [ ] **Step 1: Создать WorkspaceList компонент**

```jsx
// Admin_SITE/components/workspaces/WorkspaceList.jsx
import { Users, MessageCircle, ChevronRight, Plus, Plug } from 'lucide-react';
import { useWorkspaces } from './useWorkspaces';

export default function WorkspaceList({ token, onSelectWorkspace, onConnectClick, botUsername }) {
  const { workspaces, loading, error } = useWorkspaces(token);

  // Состояние "Без чата" — старый блок
  if (!loading && workspaces.length === 0) {
    return (
      <div className="bg-gradient-to-br from-blue-500 to-blue-700 rounded-[2rem] p-5 text-white">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-white/15 backdrop-blur
                          flex items-center justify-center border border-white/30 flex-shrink-0">
            <Plug size={18} className="text-white"/>
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-black uppercase tracking-wide">Без чата</h3>
            <p className="text-xs font-medium text-blue-100 mt-1 leading-snug">
              Pulse Bot ещё не работает в вашем чате
            </p>
          </div>
        </div>
        <button
          onClick={onConnectClick}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                     bg-white text-blue-700 font-black text-xs uppercase tracking-wide
                     hover:bg-blue-50 active:scale-[0.98] transition-all shadow">
          <Plug size={14}/> Подключить чат
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-[2rem] p-5 border border-gray-100 space-y-2">
      <h3 className="font-black text-gray-900 text-xs uppercase flex items-center mb-3">
        <Users className="mr-2 text-blue-500" size={14}/> Мои сообщества
      </h3>
      {error && <div className="text-xs text-red-600 font-medium">{error}</div>}
      {loading && <div className="text-xs text-gray-400 font-medium">Загрузка…</div>}
      <div className="space-y-2">
        {workspaces.map(ws => (
          <button
            key={ws.id}
            onClick={() => onSelectWorkspace(ws.id)}
            className="w-full flex items-center justify-between p-3 bg-gray-50 rounded-2xl
                       hover:bg-blue-50 hover:border-blue-200 border border-transparent
                       transition-all">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center flex-shrink-0">
                <MessageCircle size={16} className="text-blue-600"/>
              </div>
              <div className="text-left min-w-0">
                <div className="font-black text-sm text-gray-900 truncate">{ws.name}</div>
                <div className="text-[10px] uppercase tracking-widest font-bold text-gray-400 mt-0.5">
                  {ws.role} · {ws.members_count} участн. · {ws.chats_count} чат.
                </div>
              </div>
            </div>
            <ChevronRight size={16} className="text-gray-400 flex-shrink-0"/>
          </button>
        ))}
      </div>
      <button
        onClick={onConnectClick}
        className="mt-3 w-full flex items-center justify-center gap-2 py-2.5
                   border-2 border-dashed border-blue-200 rounded-2xl
                   text-blue-600 font-black text-xs uppercase tracking-wide
                   hover:bg-blue-50 transition-all">
        <Plus size={14}/> Подключить ещё чат
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Заменить блок в AdminDashboard.jsx**

Найти в `AdminDashboard.jsx` строки 5070-5122 (текущий "Без чата" + "Чат" блоки) и заменить на:

```jsx
<WorkspaceList
  token={authUser?.token}
  botUsername={profileData?.bot_username}
  onConnectClick={() => setShowConnectChat(true)}
  onSelectWorkspace={(id) => setSelectedWorkspaceId(id)}
/>
```

Импорт сверху:
```jsx
import WorkspaceList from './components/workspaces/WorkspaceList';
```

State для selected ws:
```jsx
const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(null);
```

- [ ] **Step 3: Build**

Run: `cd Admin_SITE && npm run build`
Expected: success

- [ ] **Step 4: Manual test**

Открыть `Admin_SITE/dist/index.html` или dev-сервер. Залогиниться через TG. Убедиться что:
- Если у юзера 0 workspace → старый "Без чата" блок
- Если ≥1 → список карточек

- [ ] **Step 5: Commit**

```bash
git add Admin_SITE/components/workspaces/WorkspaceList.jsx Admin_SITE/AdminDashboard.jsx
git commit -m "feat(V1.17.0b13): [Site] WorkspaceList — список сообществ на дашборде"
```

---

### Task 14: WorkspacePage — детали сообщества + помощники

**Files:**
- Create: `Admin_SITE/components/workspaces/WorkspacePage.jsx`
- Modify: `Admin_SITE/AdminDashboard.jsx`

- [ ] **Step 1: Создать WorkspacePage**

```jsx
// Admin_SITE/components/workspaces/WorkspacePage.jsx
import { useEffect, useState } from 'react';
import { ArrowLeft, Edit2, Save, X, MessageCircle, Users, UserPlus, Trash2 } from 'lucide-react';
import { fetchWorkspaceDetails, renameWorkspace, removeMember } from '../shared/api';

const ROLE_LABEL = { owner: '👑 Владелец', admin: '🛡 Админ', moderator: '🔧 Модератор' };
const ROLE_COLOR = {
  owner:     'bg-amber-100 text-amber-700',
  admin:     'bg-blue-100 text-blue-700',
  moderator: 'bg-gray-100 text-gray-700',
};

export default function WorkspacePage({ token, wsId, currentUserId, onBack, onInviteClick }) {
  const [details, setDetails] = useState(null);
  const [editing, setEditing] = useState(false);
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);

  const reload = async () => {
    try {
      setErr(null);
      const d = await fetchWorkspaceDetails(token, wsId);
      setDetails(d);
      setNewName(d.workspace.name);
    } catch (e) { setErr(e.message); }
  };

  useEffect(() => { reload(); }, [wsId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await renameWorkspace(token, wsId, newName);
      await reload();
      setEditing(false);
    } catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  };

  const handleRemove = async (memberUserId) => {
    if (!confirm('Удалить помощника?')) return;
    try {
      await removeMember(token, wsId, memberUserId);
      await reload();
    } catch (e) { setErr(e.message); }
  };

  if (!details) return <div className="p-5 text-gray-400">Загрузка…</div>;

  const ws = details.workspace;
  const isOwner = details.members.find(m => m.user_id === currentUserId)?.role === 'owner';

  return (
    <div className="space-y-4">
      <button onClick={onBack}
              className="flex items-center gap-2 text-blue-600 font-black text-xs uppercase tracking-wide hover:bg-blue-50 rounded-xl px-3 py-2">
        <ArrowLeft size={14}/> Назад
      </button>

      {err && <div className="bg-red-50 text-red-700 rounded-2xl p-3 text-xs font-medium">{err}</div>}

      {/* General */}
      <div className="bg-white rounded-[2rem] p-5 border border-gray-100">
        <h3 className="font-black text-gray-900 text-xs uppercase mb-3">Общее</h3>
        {editing ? (
          <div className="flex items-center gap-2">
            <input value={newName} onChange={e => setNewName(e.target.value)}
                   className="flex-1 px-3 py-2 border border-gray-200 rounded-xl text-sm font-medium"/>
            <button onClick={handleSave} disabled={saving}
                    className="p-2 rounded-xl bg-blue-600 text-white"><Save size={14}/></button>
            <button onClick={() => { setEditing(false); setNewName(ws.name); }}
                    className="p-2 rounded-xl bg-gray-100 text-gray-700"><X size={14}/></button>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-black text-gray-900">{ws.name}</h2>
            {isOwner && (
              <button onClick={() => setEditing(true)} className="p-2 rounded-xl hover:bg-gray-100">
                <Edit2 size={14} className="text-gray-400"/>
              </button>
            )}
          </div>
        )}
        <div className="mt-2 text-[10px] uppercase tracking-widest font-bold text-gray-400">
          Тариф: {ws.plan}{ws.is_pulse_themed ? ' · Pulse-themed' : ''}
        </div>
      </div>

      {/* Chats */}
      <div className="bg-white rounded-[2rem] p-5 border border-gray-100">
        <h3 className="font-black text-gray-900 text-xs uppercase mb-3 flex items-center">
          <MessageCircle className="mr-2 text-emerald-500" size={14}/> Чаты ({details.chats.length})
        </h3>
        {details.chats.length === 0 && (
          <div className="text-xs text-gray-400 font-medium">Нет подключённых чатов.</div>
        )}
        <div className="space-y-2">
          {details.chats.map(c => (
            <div key={c.chat_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-2xl">
              <div className="min-w-0">
                <div className="font-black text-sm text-gray-900 truncate">{c.title || `Чат ${c.chat_id}`}</div>
                <div className="text-[10px] uppercase tracking-widest font-bold text-gray-400 mt-0.5">
                  {c.chat_type} · добавлен {c.added_at?.slice(0, 10) || '—'}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Members */}
      <div className="bg-white rounded-[2rem] p-5 border border-gray-100">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-black text-gray-900 text-xs uppercase flex items-center">
            <Users className="mr-2 text-violet-500" size={14}/> Помощники ({details.members.length})
          </h3>
          {isOwner && (
            <button onClick={onInviteClick}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 text-white
                               text-xs font-black uppercase tracking-wide hover:bg-blue-700">
              <UserPlus size={12}/> Пригласить
            </button>
          )}
        </div>
        <div className="space-y-2">
          {details.members.map(m => (
            <div key={m.user_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-2xl">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-gray-200 flex items-center justify-center text-xs font-black text-gray-500">
                  {String(m.user_id).slice(-2)}
                </div>
                <div>
                  <div className="font-black text-sm text-gray-900">ID {m.user_id}</div>
                  <span className={`px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wide ${ROLE_COLOR[m.role]}`}>
                    {ROLE_LABEL[m.role]}
                  </span>
                </div>
              </div>
              {isOwner && m.role !== 'owner' && (
                <button onClick={() => handleRemove(m.user_id)}
                        className="p-2 rounded-xl hover:bg-red-50 text-red-500">
                  <Trash2 size={14}/>
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Подключить к AdminDashboard.jsx**

```jsx
{selectedWorkspaceId ? (
  <WorkspacePage
    token={authUser?.token}
    wsId={selectedWorkspaceId}
    currentUserId={authUser?.user_id}
    onBack={() => setSelectedWorkspaceId(null)}
    onInviteClick={() => setShowInviteModal(true)}
  />
) : (
  // ... existing profile view + WorkspaceList
)}
```

Импорты + state:
```jsx
import WorkspacePage from './components/workspaces/WorkspacePage';
const [showInviteModal, setShowInviteModal] = useState(false);
```

- [ ] **Step 3: Build**

Run: `cd Admin_SITE && npm run build`

- [ ] **Step 4: Commit**

```bash
git add Admin_SITE/components/workspaces/WorkspacePage.jsx Admin_SITE/AdminDashboard.jsx
git commit -m "feat(V1.17.0b14): [Site] WorkspacePage — детали сообщества с чатами и помощниками"
```

---

### Task 15: InviteMemberModal — приглашение помощника

**Files:**
- Create: `Admin_SITE/components/workspaces/InviteMemberModal.jsx`
- Modify: `Admin_SITE/AdminDashboard.jsx`

- [ ] **Step 1: Создать модалку**

```jsx
// Admin_SITE/components/workspaces/InviteMemberModal.jsx
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { X, UserPlus } from 'lucide-react';
import { inviteMember } from '../shared/api';

export default function InviteMemberModal({ token, wsId, onClose, onSuccess }) {
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState('admin');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErr(null); setLoading(true);
    try {
      const uid = parseInt(userId.replace('@', ''), 10);
      if (!uid || isNaN(uid)) throw new Error('Введи Telegram user_id (число)');
      await inviteMember(token, wsId, uid, role);
      onSuccess();
      onClose();
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  };

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-0 sm:p-4
                    bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <form
        onSubmit={handleSubmit}
        onClick={e => e.stopPropagation()}
        className="bg-white w-full max-w-md rounded-t-[2.5rem] sm:rounded-[2.5rem] p-6 shadow-2xl">
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-violet-100 flex items-center justify-center">
              <UserPlus size={22} className="text-violet-600"/>
            </div>
            <div>
              <h3 className="font-black text-gray-900 text-base">Пригласить помощника</h3>
              <p className="text-xs text-gray-500 font-medium">user_id из Telegram</p>
            </div>
          </div>
          <button type="button" onClick={onClose}
                  className="p-2 rounded-xl hover:bg-gray-100"><X size={18} className="text-gray-400"/></button>
        </div>

        <label className="text-[10px] uppercase tracking-widest font-bold text-gray-400 mb-1.5 block">
          Telegram user_id
        </label>
        <input value={userId} onChange={e => setUserId(e.target.value)} placeholder="например 123456789"
               className="w-full px-3 py-3 border border-gray-200 rounded-2xl text-sm font-medium mb-4
                          focus:border-blue-500 focus:outline-none"/>

        <label className="text-[10px] uppercase tracking-widest font-bold text-gray-400 mb-1.5 block">
          Роль
        </label>
        <div className="grid grid-cols-2 gap-2 mb-5">
          {['admin', 'moderator'].map(r => (
            <button key={r} type="button" onClick={() => setRole(r)}
                    className={`py-3 rounded-2xl font-black text-xs uppercase tracking-wide transition-all
                                ${role === r
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              {r === 'admin' ? '🛡 Админ' : '🔧 Модератор'}
            </button>
          ))}
        </div>

        {err && <div className="bg-red-50 text-red-700 rounded-2xl p-3 text-xs font-medium mb-4">{err}</div>}

        <button type="submit" disabled={loading || !userId}
                className="w-full py-4 rounded-2xl bg-blue-600 text-white font-black text-sm uppercase
                           tracking-wide hover:bg-blue-700 disabled:opacity-50">
          {loading ? 'Добавляю…' : 'Пригласить'}
        </button>
      </form>
    </div>,
    document.body
  );
}
```

- [ ] **Step 2: Подключить в AdminDashboard.jsx**

```jsx
{showInviteModal && (
  <InviteMemberModal
    token={authUser?.token}
    wsId={selectedWorkspaceId}
    onClose={() => setShowInviteModal(false)}
    onSuccess={() => {/* WorkspacePage reload по next render */}}
  />
)}
```

- [ ] **Step 3: Build**

Run: `cd Admin_SITE && npm run build`

- [ ] **Step 4: Commit**

```bash
git add Admin_SITE/components/workspaces/InviteMemberModal.jsx Admin_SITE/AdminDashboard.jsx
git commit -m "feat(V1.17.0b15): [Site] InviteMemberModal — приглашение помощника owner-only"
```

---

## Phase 5 — Deploy

### Task 16: Smoke checklist + обновить RUNBOOK

**Files:**
- Modify: `docs/RUNBOOK_multi_tenancy_deploy.md` (или новый RUNBOOK для b1-b15)

- [ ] **Step 1: Полный pytest**

Run: `pytest tests/ -q --ignore=tests/test_shop_mechanics.py`
Expected: 40+ passed (28 base + 5 composite + 4 bot_membership + 4 start + 11 workspaces API)

- [ ] **Step 2: Smoke import**

Run: `python -c "from dotenv import load_dotenv; load_dotenv(); import bot; print('OK')"`

- [ ] **Step 3: Manual флоу локально** (если есть тестовый чат и второй TG-аккаунт)

1. Залогиниться на сайт с **новым** TG-аккаунтом (не Витя)
2. Дашборд показывает "БЕЗ ЧАТА"
3. Создать тестовую группу в Telegram
4. Добавить `@Pulse_On_bot` в группу, дать админа
5. В чате: "✅ Сообщество подключено..."
6. В DM боту от твоего нового аккаунта: "✅ Чат добавлен в кабинет..."
7. Refresh сайт → видишь карточку "<title>"
8. Открой её → "Помощники" → "Пригласить" → user_id Вити → admin
9. Logout, login как Витя → видишь чужой workspace с role=admin
10. Pulse-чат: убедись что всё работает как раньше (открыть BBS, Реактор, /top)

- [ ] **Step 4: Обновить runbook**

В `docs/RUNBOOK_multi_tenancy_deploy.md` добавить новую секцию:

```markdown
## V1.17.0b — Bot connection flow + composite PK fix

После применения V1.17.0a и smoke прохождения:

1. `python -m database.migrations.composite_pk_fix` — rebuild 7 таблиц
2. `python -m database.migrations.bot_chats_extend` — расширение bot_chats
3. `python scripts/check_migration_state.py` — должна показать те же workspace
4. `sudo systemctl restart pulsbot`
5. На сайте — UI обновится автоматически (новый билд `cd Admin_SITE && npm run build`)
6. Acceptance:
   - Залогиниться **новым** аккаунтом → "БЕЗ ЧАТА" → подключить → workspace создан
   - Pulse-чат и его старые юзеры работают как раньше

Rollback composite_pk_fix: `python -m database.migrations.composite_pk_fix down`
Rollback bot_chats_extend: восстановить из backup (нет автоматического down).
```

- [ ] **Step 5: Commit**

```bash
git add docs/RUNBOOK_multi_tenancy_deploy.md
git commit -m "docs(V1.17.0b16): runbook — деплой Bot Connection Flow"
```

---

### Task 17: Welcome-сообщение Pulse-чата с deep-link на /start join_1

**Files:**
- Modify: `handlers/commands/system_commands.py` (новая команда `/setup_welcome`)
- Manual: запустить команду в Pulse-чате

- [ ] **Step 1: Failing-тест (опционально, manual flow)**

Тест:

```python
# tests/test_setup_welcome.py
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_setup_welcome_owner_only():
    from handlers.commands.system_commands import setup_welcome_command
    upd = MagicMock()
    upd.effective_user.id = 999  # not owner
    upd.message.reply_text = AsyncMock()
    ctx = MagicMock(); ctx.bot.send_message = AsyncMock()
    db = MagicMock()
    await setup_welcome_command(upd, ctx, db, main_admin_id=1283941769)
    upd.message.reply_text.assert_called_with(
        "❌ Команда доступна только владельцу.", parse_mode='HTML'
    )
```

- [ ] **Step 2: Implement**

```python
# handlers/commands/system_commands.py
async def setup_welcome_command(update, context, db, main_admin_id: int = None):
    """Команда владельца Pulse: выкладывает welcome-сообщение в основной чат
    с inline-кнопкой "Регистрация" ведущей на /start join_1."""
    import os
    main_admin_id = main_admin_id or int(os.getenv('MAIN_ADMIN_ID', 0))
    if update.effective_user.id != main_admin_id:
        await update.message.reply_text(
            "❌ Команда доступна только владельцу.", parse_mode='HTML'
        )
        return

    target_chat_id = int(os.getenv('TARGET_CHAT_ID', 0))
    if not target_chat_id:
        await update.message.reply_text("❌ TARGET_CHAT_ID не настроен в .env")
        return

    bot_username = os.getenv('BOT_USERNAME', 'Pulse_On_bot')
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🎫 Регистрация",
            url=f"https://t.me/{bot_username}?start=join_1"
        )
    ]])
    msg = await context.bot.send_message(
        target_chat_id,
        "👋 <b>Добро пожаловать в Pulse Москва!</b>\n\n"
        "Чтобы получить полный доступ — пройди регистрацию.",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    try:
        await context.bot.pin_chat_message(target_chat_id, msg.message_id, disable_notification=True)
    except Exception:
        pass
    await update.message.reply_text(f"✅ Welcome выложен в чат, message_id={msg.message_id}")
```

В `bot.py` зарегистрировать:

```python
self.application.add_handler(
    CommandHandler('setup_welcome', lambda u, c: setup_welcome_command(u, c, self.db))
)
```

- [ ] **Step 3: Manual — Витя запускает `/setup_welcome` в Pulse-чате**

В чате `@Pulse_On_bot /setup_welcome` от Вити → бот пишет welcome + пинит.

- [ ] **Step 4: Commit**

```bash
git add handlers/commands/system_commands.py bot.py tests/test_setup_welcome.py
git commit -m "feat(V1.17.0b17): /setup_welcome — welcome-сообщение Pulse-чата с deep-link join_1"
```

---

## Финальный merge в main

После завершения всех 17 задач:

- [ ] Все тесты проходят: `pytest tests/ -q --ignore=tests/test_shop_mechanics.py` → 40+ PASS
- [ ] Бот импортируется: `python -c "import bot"` → OK
- [ ] Сайт билдится: `cd Admin_SITE && npm run build` → success
- [ ] Manual smoke второго владельца сделан
- [ ] Push в `origin/main`: `git push origin main`
- [ ] На сервере по обновлённому runbook:
  - `git pull`
  - `python -m database.migrations.composite_pk_fix`
  - `python -m database.migrations.bot_chats_extend`
  - `python scripts/check_migration_state.py`
  - `sudo systemctl restart pulsbot`
- [ ] Сообщить Вите что Подпроект #2 задеплоен. Следующий — #3 (Web auth advanced) или #4 (Module system).
