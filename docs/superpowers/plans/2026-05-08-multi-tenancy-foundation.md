# Multi-tenancy Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Превратить single-tenant Pulse-бота в мультитенантную SaaS-платформу: добавить `workspace_id` ко всем тенантизируемым таблицам, перенести существующие Pulse-данные в `workspace_id=1`, обеспечить изоляцию данных в коде.

**Architecture:** Big-bang миграция БД с обратимым downgrade. Все тенантизируемые DB-функции обязаны принимать `workspace_id` первым аргументом. `WorkspaceContext` создаётся в начале каждого update-обработчика и прокидывается через handlers. Pulse-only фичи защищены декоратором `@pulse_only`.

**Tech Stack:** Python 3.13, sqlite3, python-telegram-bot v20+, FastAPI (api.py), pytest (asyncio).

**Spec:** `docs/superpowers/specs/2026-05-08-multi-tenancy-foundation-design.md`

**Branch:** `Интеграция-множетсвенные-пользователи` (не сливать в main до полного теста).

---

## Phase 1: Schema foundation

### Task 1: Создать миграционный скрипт — новые таблицы

**Files:**
- Create: `database/migrations/multi_tenancy.py`
- Create: `database/migrations/__init__.py` (пустой)

- [ ] **Step 1: Создать `database/migrations/__init__.py`**

```python
# Marker для пакета миграций.
```

- [ ] **Step 2: Создать `database/migrations/multi_tenancy.py` с функцией `up_create_workspaces_tables`**

```python
"""
Миграция: добавление мультитенантности.
ID: 2026-05-08-multi-tenancy
Spec: docs/superpowers/specs/2026-05-08-multi-tenancy-foundation-design.md
"""
import os
import shutil
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'bot_database.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')


def backup_db(db_path: str = DB_PATH) -> str:
    """Делает копию БД перед миграцией. Возвращает путь к бэкапу."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(BACKUP_DIR, f'pre_multitenancy_{ts}.db')
    shutil.copy2(db_path, dest)
    return dest


def up_create_workspaces_tables(conn: sqlite3.Connection) -> None:
    """Создаёт workspaces и workspace_members таблицы."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS workspaces (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            owner_user_id   INTEGER NOT NULL,
            is_pulse_themed INTEGER NOT NULL DEFAULT 0,
            plan            TEXT    NOT NULL DEFAULT 'free',
            settings_json   TEXT,
            created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workspace_members (
            workspace_id INTEGER NOT NULL,
            user_id      INTEGER NOT NULL,
            role         TEXT    NOT NULL CHECK (role IN ('owner','admin','moderator')),
            joined_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, user_id),
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id);
    ''')
    conn.commit()


def up_seed_pulse_workspace(conn: sqlite3.Connection, owner_user_id: int) -> int:
    """Создаёт workspace_id=1 (Pulse Москва) с Витей-владельцем."""
    cur = conn.execute(
        'INSERT INTO workspaces (id, name, owner_user_id, is_pulse_themed, plan) '
        'VALUES (1, ?, ?, 1, ?)',
        ('Pulse Москва', owner_user_id, 'free')
    )
    conn.execute(
        'INSERT INTO workspace_members (workspace_id, user_id, role) '
        'VALUES (1, ?, ?)',
        (owner_user_id, 'owner')
    )
    conn.commit()
    return cur.lastrowid


def down_drop_workspaces_tables(conn: sqlite3.Connection) -> None:
    """Откат: удаляет workspaces и workspace_members."""
    conn.executescript('''
        DROP TABLE IF EXISTS workspace_members;
        DROP TABLE IF EXISTS workspaces;
    ''')
    conn.commit()
```

- [ ] **Step 3: Запустить интерактивно, проверить создание таблиц на копии БД**

```bash
cp database/bot_database.db /tmp/test_db.db
python -c "
import sqlite3
from database.migrations.multi_tenancy import up_create_workspaces_tables, up_seed_pulse_workspace
conn = sqlite3.connect('/tmp/test_db.db')
up_create_workspaces_tables(conn)
up_seed_pulse_workspace(conn, owner_user_id=int(__import__('os').getenv('MAIN_ADMIN_ID','0')))
print(conn.execute('SELECT * FROM workspaces').fetchone())
print(conn.execute('SELECT * FROM workspace_members').fetchone())
"
```
Expected: row workspaces (1, 'Pulse Москва', <Витя_id>, 1, 'free', None, ts, ts) и row workspace_members (1, <Витя_id>, 'owner', ts).

- [ ] **Step 4: Commit**

```bash
git add database/migrations/__init__.py database/migrations/multi_tenancy.py
git commit -m "feat(V1.17.0a1): миграция multi-tenancy — workspaces+members tables"
```

---

### Task 2: Миграционный скрипт — ALTER существующих таблиц

**Files:**
- Modify: `database/migrations/multi_tenancy.py` (добавить функции)

- [ ] **Step 1: Добавить список тенантизируемых таблиц в `multi_tenancy.py`**

Дописать после `down_drop_workspaces_tables`:

```python
TENANTED_TABLES = [
    'anketa_edits', 'bbs_other_posts', 'bbs_profiles', 'bbs_reactions',
    'bingo_cards', 'bingo_games', 'bot_chats', 'bot_chat_topics',
    'branding_settings', 'bug_cards', 'challenges', 'chat_stats',
    'combo_claims', 'daily_stats_summary', 'economy_cancellations',
    'economy_history', 'economy_section_toggles', 'economy_settings',
    'exit_interviews', 'hall_of_fame', 'journal_messages', 'lotteries',
    'lottery_tickets', 'marketplace_services', 'messages',
    'monthly_gift_participants', 'monthly_gifts',
    'press_release_targets', 'press_release_templates', 'press_release_versions',
    'reactor', 'referral_links', 'referral_seasons', 'referral_stats',
    'scheduled_posts', 'shipper_matches', 'shipper_resonance_stats',
    'sprint_claims', 'stat_events_log', 'title_packages', 'title_rub_requests',
    'titles', 'top_activists_history', 'top_activists_percent', 'topics',
    'transactions', 'trigger_violations', 'triggers',
    'user_joins', 'user_stats', 'user_stats_hourly',
]

GLOBAL_TABLES = [
    'users', 'exchange_rate_history', 'shipper_phrases',
    'settings', 'sqlite_sequence',
]
```

- [ ] **Step 2: Добавить функцию `up_tenantize_existing_tables`**

```python
def up_tenantize_existing_tables(conn: sqlite3.Connection) -> None:
    """ALTER каждую тенантизируемую таблицу: добавить workspace_id NOT NULL DEFAULT 1.
    Создать индекс idx_<table>_workspace.
    Существующие строки получают workspace_id=1 автоматически (DEFAULT 1)."""
    for tbl in TENANTED_TABLES:
        # Проверяем существование таблицы (на случай если БД отстаёт)
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (tbl,)
        ).fetchone()
        if not exists:
            print(f'[skip] table {tbl} does not exist')
            continue
        # Проверяем что колонки workspace_id ещё нет
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if 'workspace_id' in cols:
            print(f'[skip] {tbl}.workspace_id already exists')
            continue
        conn.execute(
            f'ALTER TABLE {tbl} ADD COLUMN workspace_id INTEGER NOT NULL DEFAULT 1'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{tbl}_workspace ON {tbl}(workspace_id)'
        )
        print(f'[ok] tenantized {tbl}')
    conn.commit()
```

- [ ] **Step 3: Добавить функцию `down_remove_workspace_id`**

SQLite не поддерживает `DROP COLUMN` напрямую. Используем pragma rebuild:

```python
def down_remove_workspace_id(conn: sqlite3.Connection) -> None:
    """Откат: удаляет workspace_id из всех тенантизированных таблиц.
    Использует SQLite-обходной путь через временную таблицу."""
    for tbl in TENANTED_TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if 'workspace_id' not in cols:
            continue
        # Drop index
        conn.execute(f'DROP INDEX IF EXISTS idx_{tbl}_workspace')
        # SQLite >=3.35 поддерживает ALTER TABLE DROP COLUMN. Проверяем версию.
        sqlite_ver = sqlite3.sqlite_version_info
        if sqlite_ver >= (3, 35, 0):
            conn.execute(f'ALTER TABLE {tbl} DROP COLUMN workspace_id')
        else:
            # Fallback: воссоздать таблицу без колонки
            kept_cols = [c for c in cols if c != 'workspace_id']
            cols_csv = ', '.join(kept_cols)
            conn.execute(f'CREATE TABLE {tbl}__new AS SELECT {cols_csv} FROM {tbl}')
            conn.execute(f'DROP TABLE {tbl}')
            conn.execute(f'ALTER TABLE {tbl}__new RENAME TO {tbl}')
        print(f'[ok] removed workspace_id from {tbl}')
    conn.commit()
```

- [ ] **Step 4: Добавить top-level `migrate_up` и `migrate_down`**

```python
def migrate_up(db_path: str = DB_PATH, owner_user_id: int | None = None) -> str:
    """Полная миграция up. Делает backup, создаёт таблицы, тенантизирует,
    создаёт workspace=1 (Pulse). Возвращает путь к backup."""
    if owner_user_id is None:
        owner_user_id = int(os.getenv('MAIN_ADMIN_ID', '0'))
        if not owner_user_id:
            raise ValueError('MAIN_ADMIN_ID not set in env and owner_user_id not passed')

    backup_path = backup_db(db_path)
    print(f'[backup] {backup_path}')

    conn = sqlite3.connect(db_path)
    try:
        up_create_workspaces_tables(conn)
        up_seed_pulse_workspace(conn, owner_user_id)
        up_tenantize_existing_tables(conn)
    finally:
        conn.close()
    print('[done] migrate_up complete')
    return backup_path


def migrate_down(db_path: str = DB_PATH) -> None:
    """Полный откат. Бэкап делать ОТДЕЛЬНО руками если нужен."""
    conn = sqlite3.connect(db_path)
    try:
        down_remove_workspace_id(conn)
        down_drop_workspaces_tables(conn)
    finally:
        conn.close()
    print('[done] migrate_down complete')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'down':
        migrate_down()
    else:
        migrate_up()
```

- [ ] **Step 5: Commit**

```bash
git add database/migrations/multi_tenancy.py
git commit -m "feat(V1.17.0a2): миграция multi-tenancy — ALTER+backfill всех таблиц"
```

---

### Task 3: Тест миграции (round-trip up→down→up)

**Files:**
- Create: `tests/test_multi_tenancy_migration.py`

- [ ] **Step 1: Создать тест round-trip**

```python
"""Тест полной миграции: up → down → up восстанавливает рабочее состояние."""
import os
import shutil
import sqlite3
import tempfile
import pytest

from database.migrations.multi_tenancy import (
    migrate_up, migrate_down, TENANTED_TABLES,
)


@pytest.fixture
def real_db_copy(tmp_path):
    """Копия настоящей БД во временной директории."""
    src = os.path.join(os.path.dirname(__file__), '..', 'database', 'bot_database.db')
    dst = tmp_path / 'test.db'
    shutil.copy2(src, dst)
    return str(dst)


def test_migrate_up_creates_workspaces_table(real_db_copy):
    migrate_up(real_db_copy, owner_user_id=12345)
    conn = sqlite3.connect(real_db_copy)
    rows = conn.execute('SELECT id, name, owner_user_id, is_pulse_themed FROM workspaces').fetchall()
    assert len(rows) == 1
    assert rows[0] == (1, 'Pulse Москва', 12345, 1)
    conn.close()


def test_migrate_up_creates_owner_member(real_db_copy):
    migrate_up(real_db_copy, owner_user_id=12345)
    conn = sqlite3.connect(real_db_copy)
    rows = conn.execute('SELECT user_id, role FROM workspace_members WHERE workspace_id=1').fetchall()
    assert (12345, 'owner') in rows
    conn.close()


def test_migrate_up_tenantizes_all_tables(real_db_copy):
    migrate_up(real_db_copy, owner_user_id=12345)
    conn = sqlite3.connect(real_db_copy)
    for tbl in TENANTED_TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not exists:
            continue  # таблица не существует в этой БД, ок
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info({tbl})').fetchall()]
        assert 'workspace_id' in cols, f'workspace_id missing in {tbl}'
    conn.close()


def test_migrate_up_backfills_existing_data(real_db_copy):
    """Существующие строки получают workspace_id=1."""
    migrate_up(real_db_copy, owner_user_id=12345)
    conn = sqlite3.connect(real_db_copy)
    # Проверяем на нескольких таблицах что данные сохранились и получили ws_id=1
    for tbl in ['user_stats', 'economy_history', 'press_release_templates']:
        try:
            rows = conn.execute(f'SELECT COUNT(*) FROM {tbl} WHERE workspace_id=1').fetchone()
            total = conn.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()
            assert rows[0] == total[0], f'{tbl}: {rows[0]}/{total[0]} rows have workspace_id=1'
        except sqlite3.OperationalError:
            pass  # таблица не существует, ок
    conn.close()


def test_migrate_round_trip_down_up(real_db_copy):
    """down после up удаляет колонки. Затем up создаёт заново."""
    migrate_up(real_db_copy, owner_user_id=12345)
    migrate_down(real_db_copy)

    conn = sqlite3.connect(real_db_copy)
    # workspaces table удалена
    res = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workspaces'"
    ).fetchone()
    assert res is None
    # workspace_id колонка удалена
    cols = [r[1] for r in conn.execute('PRAGMA table_info(user_stats)').fetchall()]
    assert 'workspace_id' not in cols
    conn.close()

    # Повторный up должен пройти без ошибок
    migrate_up(real_db_copy, owner_user_id=12345)
```

- [ ] **Step 2: Запустить тесты**

```bash
python -m pytest tests/test_multi_tenancy_migration.py -v
```
Expected: 5 passed (или skipped если каких-то таблиц нет в текущей БД).

- [ ] **Step 3: Commit**

```bash
git add tests/test_multi_tenancy_migration.py
git commit -m "test(V1.17.0a3): тесты миграции multi-tenancy round-trip"
```

---

## Phase 2: Workspace data layer

### Task 4: db_workspaces.py — CRUD для workspaces

**Files:**
- Create: `database/db_workspaces.py`

- [ ] **Step 1: Создать модуль с базовыми CRUD функциями**

```python
"""CRUD для workspaces и workspace_members. Используется в bot.py и api.py."""
import sqlite3
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class Workspace:
    id: int
    name: str
    owner_user_id: int
    is_pulse_themed: bool
    plan: str
    settings_json: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row[0], name=row[1], owner_user_id=row[2],
            is_pulse_themed=bool(row[3]), plan=row[4],
            settings_json=row[5], created_at=row[6], updated_at=row[7],
        )


@dataclass
class WorkspaceMember:
    workspace_id: int
    user_id: int
    role: str  # 'owner' | 'admin' | 'moderator'
    joined_at: str


def create_workspace(
    conn: sqlite3.Connection, name: str, owner_user_id: int,
    is_pulse_themed: bool = False, plan: str = 'free',
) -> int:
    """Создаёт workspace, возвращает его id. Owner автоматически добавляется в members."""
    cur = conn.execute(
        'INSERT INTO workspaces (name, owner_user_id, is_pulse_themed, plan) '
        'VALUES (?, ?, ?, ?)',
        (name, owner_user_id, 1 if is_pulse_themed else 0, plan)
    )
    ws_id = cur.lastrowid
    conn.execute(
        'INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)',
        (ws_id, owner_user_id, 'owner')
    )
    conn.commit()
    return ws_id


def get_workspace(conn: sqlite3.Connection, ws_id: int) -> Optional[Workspace]:
    row = conn.execute(
        'SELECT id, name, owner_user_id, is_pulse_themed, plan, settings_json, '
        'created_at, updated_at FROM workspaces WHERE id=?', (ws_id,)
    ).fetchone()
    return Workspace.from_row(row) if row else None


def list_workspaces_for_user(conn: sqlite3.Connection, user_id: int) -> List[Workspace]:
    """Все workspaces где user является членом."""
    rows = conn.execute(
        'SELECT w.id, w.name, w.owner_user_id, w.is_pulse_themed, w.plan, '
        '       w.settings_json, w.created_at, w.updated_at '
        'FROM workspaces w '
        'JOIN workspace_members m ON m.workspace_id = w.id '
        'WHERE m.user_id=? '
        'ORDER BY w.created_at',
        (user_id,)
    ).fetchall()
    return [Workspace.from_row(r) for r in rows]


def add_member(
    conn: sqlite3.Connection, ws_id: int, user_id: int, role: str
) -> None:
    if role not in ('owner', 'admin', 'moderator'):
        raise ValueError(f'Invalid role: {role}')
    conn.execute(
        'INSERT OR REPLACE INTO workspace_members (workspace_id, user_id, role) '
        'VALUES (?, ?, ?)',
        (ws_id, user_id, role)
    )
    conn.commit()


def remove_member(conn: sqlite3.Connection, ws_id: int, user_id: int) -> None:
    """Owner-а удалять нельзя — отдельный transfer_ownership."""
    role = get_member_role(conn, ws_id, user_id)
    if role == 'owner':
        raise ValueError('Cannot remove owner. Transfer ownership first.')
    conn.execute(
        'DELETE FROM workspace_members WHERE workspace_id=? AND user_id=?',
        (ws_id, user_id)
    )
    conn.commit()


def get_member_role(
    conn: sqlite3.Connection, ws_id: int, user_id: int
) -> Optional[str]:
    row = conn.execute(
        'SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?',
        (ws_id, user_id)
    ).fetchone()
    return row[0] if row else None
```

- [ ] **Step 2: Commit**

```bash
git add database/db_workspaces.py
git commit -m "feat(V1.17.0a4): db_workspaces — CRUD workspaces+members"
```

---

### Task 5: Тесты для db_workspaces

**Files:**
- Create: `tests/test_db_workspaces.py`

- [ ] **Step 1: Создать тесты**

```python
"""Тесты CRUD для workspaces."""
import sqlite3
import pytest

from database.migrations.multi_tenancy import (
    up_create_workspaces_tables,
)
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
    ws_id = create_workspace(conn, 'Test WS', owner_user_id=42, is_pulse_themed=True)
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
    user_ws = list_workspaces_for_user(conn, 42)
    ids = [w.id for w in user_ws]
    assert ws1 in ids and ws2 in ids
    other = list_workspaces_for_user(conn, 99)
    assert other == [w for w in other if w.id == ws2]


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
```

- [ ] **Step 2: Запустить тесты**

```bash
python -m pytest tests/test_db_workspaces.py -v
```
Expected: 7 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_db_workspaces.py
git commit -m "test(V1.17.0a5): тесты db_workspaces CRUD"
```

---

## Phase 3: Runtime workspace context

### Task 6: WorkspaceContext + chat→workspace resolver

**Files:**
- Create: `bot_core/workspace_context.py`

- [ ] **Step 1: Создать модуль**

```python
"""WorkspaceContext — рантайм-объект, описывающий контекст текущего workspace.
Создаётся при входе в каждый handler (резолв через chat_id → workspace_id).
"""
import sqlite3
from dataclasses import dataclass
from typing import Optional


@dataclass
class WorkspaceContext:
    workspace_id: int
    is_pulse_themed: bool
    plan: str
    member_role: Optional[str] = None  # роль текущего юзера в WS


# Кеш chat_id → workspace_id (избегаем JOIN на каждое сообщение)
_chat_to_ws_cache: dict[int, int] = {}


def resolve_workspace_for_chat(
    conn: sqlite3.Connection, chat_id: int
) -> Optional[int]:
    """По telegram chat_id находит workspace_id из bot_chats. Кеширует."""
    cached = _chat_to_ws_cache.get(chat_id)
    if cached is not None:
        return cached
    row = conn.execute(
        'SELECT workspace_id FROM bot_chats WHERE chat_id=?', (chat_id,)
    ).fetchone()
    if row:
        _chat_to_ws_cache[chat_id] = row[0]
        return row[0]
    return None


def build_context(
    conn: sqlite3.Connection, chat_id: int, user_id: Optional[int] = None
) -> Optional[WorkspaceContext]:
    """Собирает WorkspaceContext для входящего update-а.
    Возвращает None если chat не привязан к workspace (бот в новом чате)."""
    ws_id = resolve_workspace_for_chat(conn, chat_id)
    if ws_id is None:
        return None
    ws_row = conn.execute(
        'SELECT is_pulse_themed, plan FROM workspaces WHERE id=?', (ws_id,)
    ).fetchone()
    if not ws_row:
        return None
    member_role = None
    if user_id is not None:
        m_row = conn.execute(
            'SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?',
            (ws_id, user_id)
        ).fetchone()
        if m_row:
            member_role = m_row[0]
    return WorkspaceContext(
        workspace_id=ws_id,
        is_pulse_themed=bool(ws_row[0]),
        plan=ws_row[1],
        member_role=member_role,
    )


def invalidate_cache(chat_id: Optional[int] = None) -> None:
    """Сброс кеша при изменении привязки чата к workspace."""
    if chat_id is None:
        _chat_to_ws_cache.clear()
    else:
        _chat_to_ws_cache.pop(chat_id, None)
```

- [ ] **Step 2: Commit**

```bash
mkdir -p bot_core
touch bot_core/__init__.py
git add bot_core/__init__.py bot_core/workspace_context.py
git commit -m "feat(V1.17.0a6): WorkspaceContext + chat→workspace resolver с кешем"
```

---

### Task 7: Тесты для WorkspaceContext

**Files:**
- Create: `tests/test_workspace_context.py`

- [ ] **Step 1: Создать тесты**

```python
"""Тесты WorkspaceContext и резолвера."""
import sqlite3
import pytest

from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import create_workspace, add_member
from bot_core.workspace_context import (
    resolve_workspace_for_chat, build_context, invalidate_cache,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    up_create_workspaces_tables(c)
    # Минимальная bot_chats таблица для теста
    c.execute('''CREATE TABLE bot_chats (
        chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL DEFAULT 1
    )''')
    c.commit()
    yield c
    c.close()
    invalidate_cache()  # чистим глобальный кеш между тестами


def test_resolve_returns_workspace_id(conn):
    create_workspace(conn, 'WS1', owner_user_id=1)
    conn.execute('INSERT INTO bot_chats (chat_id, workspace_id) VALUES (?, ?)', (-100, 1))
    conn.commit()
    assert resolve_workspace_for_chat(conn, -100) == 1


def test_resolve_unknown_chat_returns_none(conn):
    assert resolve_workspace_for_chat(conn, -999) is None


def test_resolve_caches_result(conn):
    create_workspace(conn, 'WS1', owner_user_id=1)
    conn.execute('INSERT INTO bot_chats (chat_id, workspace_id) VALUES (?, ?)', (-100, 1))
    conn.commit()
    resolve_workspace_for_chat(conn, -100)
    # Удаляем строку — должно всё ещё вернуть из кеша
    conn.execute('DELETE FROM bot_chats WHERE chat_id=?', (-100,))
    conn.commit()
    assert resolve_workspace_for_chat(conn, -100) == 1
    invalidate_cache(-100)
    assert resolve_workspace_for_chat(conn, -100) is None


def test_build_context_full(conn):
    create_workspace(conn, 'WS1', owner_user_id=1, is_pulse_themed=True)
    add_member(conn, 1, 42, 'admin')
    conn.execute('INSERT INTO bot_chats (chat_id, workspace_id) VALUES (?, ?)', (-100, 1))
    conn.commit()
    ctx = build_context(conn, chat_id=-100, user_id=42)
    assert ctx.workspace_id == 1
    assert ctx.is_pulse_themed is True
    assert ctx.member_role == 'admin'


def test_build_context_unknown_chat_returns_none(conn):
    ctx = build_context(conn, chat_id=-999, user_id=42)
    assert ctx is None
```

- [ ] **Step 2: Запустить тесты**

```bash
python -m pytest tests/test_workspace_context.py -v
```
Expected: 5 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_workspace_context.py
git commit -m "test(V1.17.0a7): тесты WorkspaceContext+resolver"
```

---

### Task 8: @pulse_only декоратор для Pulse-фич

**Files:**
- Modify: `bot_core/workspace_context.py` (добавить декоратор)
- Create: `tests/test_pulse_only.py`

- [ ] **Step 1: Добавить декоратор в `bot_core/workspace_context.py`**

Дописать в конец файла:

```python
import functools
import logging

logger = logging.getLogger(__name__)


def pulse_only(handler):
    """Декоратор: handler выполняется только если ws_ctx.is_pulse_themed.
    Иначе silent skip с логом.

    Применять к Pulse-специфичным handlers (BBS, реактор, anketa, shipper).

    Сигнатура handler-а: (update, ctx, ws_ctx, ...) — ws_ctx должен быть
    в kwargs или 3-м позиционным.
    """
    @functools.wraps(handler)
    async def wrapper(*args, **kwargs):
        ws_ctx = kwargs.get('ws_ctx')
        if ws_ctx is None and len(args) >= 3:
            ws_ctx = args[2]
        if ws_ctx is None or not ws_ctx.is_pulse_themed:
            logger.debug(
                'pulse_only skip: handler=%s ws=%s',
                handler.__name__,
                ws_ctx.workspace_id if ws_ctx else 'None'
            )
            return None
        return await handler(*args, **kwargs)
    return wrapper
```

- [ ] **Step 2: Создать тесты декоратора**

```python
"""Тесты @pulse_only декоратора."""
import pytest
from bot_core.workspace_context import WorkspaceContext, pulse_only


@pulse_only
async def pulse_handler(update, ctx, ws_ctx):
    return 'ran'


@pytest.mark.asyncio
async def test_pulse_only_runs_when_themed():
    ws = WorkspaceContext(workspace_id=1, is_pulse_themed=True, plan='free')
    result = await pulse_handler(None, None, ws)
    assert result == 'ran'


@pytest.mark.asyncio
async def test_pulse_only_skips_when_not_themed():
    ws = WorkspaceContext(workspace_id=2, is_pulse_themed=False, plan='free')
    result = await pulse_handler(None, None, ws)
    assert result is None


@pytest.mark.asyncio
async def test_pulse_only_skips_when_no_context():
    result = await pulse_handler(None, None, None)
    assert result is None
```

- [ ] **Step 3: Запустить тесты**

```bash
python -m pytest tests/test_pulse_only.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add bot_core/workspace_context.py tests/test_pulse_only.py
git commit -m "feat(V1.17.0a8): @pulse_only декоратор для Pulse-only handlers"
```

---

## Phase 4: Pilot module migration — economy

### Task 9: Аудит db_economy.py — какие функции мигрировать

**Files:**
- Read-only: `database/db_economy.py`, `database/db_economy_history.py`

- [ ] **Step 1: Получить список всех публичных функций db_economy.py и db_economy_history.py**

```bash
grep -n "^def \|^async def " database/db_economy.py database/db_economy_history.py | head -50
```

- [ ] **Step 2: Записать список функций которые читают/пишут таблицы economy_*, transactions, economy_settings, economy_history**

Создать чек-лист в этом файле как комментарий или временный TODO.txt. Каждая функция должна получить `workspace_id` первым аргументом.

---

### Task 10: Мигрировать db_economy.py — паттерн

**Files:**
- Modify: `database/db_economy.py`

- [ ] **Step 1: Добавить workspace_id первым параметром в каждую функцию**

Паттерн на примере одной функции (применить ко всем):

**Было:**
```python
def get_user_balance(conn, user_id: int) -> int:
    row = conn.execute(
        'SELECT balance FROM economy_history WHERE user_id=? ORDER BY ts DESC LIMIT 1',
        (user_id,)
    ).fetchone()
    return row[0] if row else 0
```

**Стало:**
```python
def get_user_balance(conn, workspace_id: int, user_id: int) -> int:
    row = conn.execute(
        'SELECT balance FROM economy_history WHERE workspace_id=? AND user_id=? '
        'ORDER BY ts DESC LIMIT 1',
        (workspace_id, user_id)
    ).fetchone()
    return row[0] if row else 0
```

Применить к каждой функции в db_economy.py:
- Добавить `workspace_id: int` сразу после `conn`/`db` (или первый если их нет).
- В каждом SQL: добавить `workspace_id = ?` в WHERE.
- В каждом INSERT: явно вставлять `workspace_id`.
- В каждом UPDATE: добавить `workspace_id = ?` в WHERE.

- [ ] **Step 2: Запустить существующие тесты которые могут что-то покрывать**

```bash
python -m pytest tests/ -v
```
Expected: некоторые тесты могут упасть из-за изменения сигнатур — это покажет вам где надо обновить вызовы.

- [ ] **Step 3: Commit**

```bash
git add database/db_economy.py
git commit -m "refactor(V1.17.0a9): db_economy — workspace_id во всех функциях"
```

---

### Task 11: Мигрировать db_economy_history.py

**Files:**
- Modify: `database/db_economy_history.py`

- [ ] **Step 1: Применить тот же паттерн что в Task 10 ко всем функциям**

- [ ] **Step 2: Commit**

```bash
git add database/db_economy_history.py
git commit -m "refactor(V1.17.0a10): db_economy_history — workspace_id во всех функциях"
```

---

### Task 12: Обновить вызовы db_economy в handlers

**Files:**
- Modify: каждый файл в `handlers/` который импортирует из `db_economy`

- [ ] **Step 1: Найти все вызовы**

```bash
grep -rn "from database.db_economy\|from .db_economy\|db_economy\." handlers/ message_handler.py mining_logic.py | head -40
```

- [ ] **Step 2: В каждом call-site добавить `workspace_id` аргумент**

Шаблон. Где было:
```python
balance = db_economy.get_user_balance(conn, user_id)
```
Стало:
```python
balance = db_economy.get_user_balance(conn, ws_ctx.workspace_id, user_id)
```

`ws_ctx` должен быть в scope handler-а. Для MVP, если ещё нет ws_ctx в scope — захардкодить `workspace_id=1` с TODO-комментарием:
```python
balance = db_economy.get_user_balance(conn, 1, user_id)  # TODO: пробросить ws_ctx
```

Это позволит коду компилироваться. Полная интеграция WorkspaceContext в handlers — Task 14.

- [ ] **Step 3: Запустить smoke test**

```bash
python -c "
import sys
sys.path.insert(0, '.')
import database.db_economy as e
# Проверка что импорт не сломан
print(dir(e))
"
```

- [ ] **Step 4: Commit**

```bash
git add handlers/ message_handler.py mining_logic.py
git commit -m "refactor(V1.17.0a11): обновлены вызовы db_economy с workspace_id (placeholder=1)"
```

---

### Task 13: Тест изоляции экономики

**Files:**
- Create: `tests/test_economy_isolation.py`

- [ ] **Step 1: Тест что данные двух workspace-ов не смешиваются**

```python
"""Тест изоляции экономических данных между workspaces."""
import sqlite3
import pytest

from database.migrations.multi_tenancy import (
    up_create_workspaces_tables, up_tenantize_existing_tables,
)
from database.db_workspaces import create_workspace
from database import db_economy


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    # Создаём минимально необходимые таблицы для теста
    c.executescript('''
        CREATE TABLE economy_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            balance INTEGER NOT NULL,
            ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    up_create_workspaces_tables(c)
    up_tenantize_existing_tables(c)
    yield c
    c.close()


def test_balance_isolated_per_workspace(conn):
    ws1 = create_workspace(conn, 'WS1', owner_user_id=1)
    ws2 = create_workspace(conn, 'WS2', owner_user_id=2)
    conn.execute(
        'INSERT INTO economy_history (workspace_id, user_id, balance) VALUES (?, ?, ?)',
        (ws1, 100, 1000)
    )
    conn.execute(
        'INSERT INTO economy_history (workspace_id, user_id, balance) VALUES (?, ?, ?)',
        (ws2, 100, 5000)
    )
    conn.commit()

    bal_ws1 = db_economy.get_user_balance(conn, ws1, 100)
    bal_ws2 = db_economy.get_user_balance(conn, ws2, 100)
    assert bal_ws1 == 1000
    assert bal_ws2 == 5000
    # Юзер 100 в WS1 не видит данные из WS2 и наоборот
```

- [ ] **Step 2: Запустить**

```bash
python -m pytest tests/test_economy_isolation.py -v
```
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_economy_isolation.py
git commit -m "test(V1.17.0a12): тест изоляции экономики между workspaces"
```

---

## Phase 5: Sweep остальных модулей

### Task 14: Применить паттерн ко всем оставшимся db_*.py + handlers

**Files (по чек-листу):**

- [ ] **Module: `database/db_friend.py`**
  - Добавить workspace_id во все функции
  - Обновить вызовы в `handlers/friend_*.py`
  - Commit `feat(V1.17.0a13): db_friend — workspace_id`

- [ ] **Module: `database/db_press_release.py`**
  - Добавить workspace_id
  - Обновить `api.py` (роуты press-release уже частично через workspace=1)
  - Commit `feat(V1.17.0a14): db_press_release — workspace_id`

- [ ] **Module: `database/db_exchange.py`**
  - Курсы валют — глобальные, НЕ тенантизируем `exchange_rate_history`
  - Но если есть user-specific логика — добавить workspace_id для них
  - Commit `feat(V1.17.0a15): db_exchange — workspace_id где надо`

- [ ] **Module: `database/db_manager.py`** — base методы
  - user_stats, chat_stats, messages, daily_stats_summary, user_joins
  - Это центральный модуль, особенно тщательно
  - Commit `feat(V1.17.0a16): db_manager base — workspace_id`

- [ ] **BBS module: handlers/bbs_*.py + соответствующие DB-функции**
  - BBS таблицы тенантизированы, но фича Pulse-only
  - Применить @pulse_only к роутам/handlers
  - Commit `feat(V1.17.0a17): BBS — workspace_id + @pulse_only`

- [ ] **Журнал: handlers/journal_*.py**
  - Применить паттерн
  - Commit `feat(V1.17.0a18): journal — workspace_id`

- [ ] **Триггеры: handlers/triggers_*.py + db**
  - Применить паттерн
  - Commit `feat(V1.17.0a19): triggers — workspace_id`

- [ ] **Реактор/Активности/Бинго/Лотереи/Рейтинги/Титулы**
  - Pulse-only через @pulse_only где относится
  - Commit `feat(V1.17.0a20): остальные модули — workspace_id`

- [ ] **Шипер**
  - Pulse-only
  - shipper_phrases остаётся глобальной
  - Commit `feat(V1.17.0a21): shipper — workspace_id + @pulse_only`

После каждого модуля — запустить `python -m pytest tests/ -v` и убедиться что ничего не сломалось.

---

### Task 15: Интегрировать WorkspaceContext в bot.py middleware

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: В bot.py перед routing-ом сообщений резолвить ws_ctx**

```python
from bot_core.workspace_context import build_context

# В каждом обработчике (или middleware-style — group=-1 priority handler):
async def resolve_workspace_middleware(update, context):
    chat_id = update.effective_chat.id if update.effective_chat else None
    user_id = update.effective_user.id if update.effective_user else None
    if chat_id:
        ws_ctx = build_context(self.db.conn, chat_id, user_id)
        context.user_data['ws_ctx'] = ws_ctx
        # Если ws_ctx is None (бот в новом чате) — переход к onboarding flow
        # (это будет в Подпроекте #2). Пока — логируем.
        if ws_ctx is None:
            logger.warning('Unknown chat %s for user %s — no workspace context', chat_id, user_id)
```

- [ ] **Step 2: Заменить TODO-placeholder вызовы (`workspace_id=1`) на `ws_ctx.workspace_id`**

```bash
grep -rn "TODO: пробросить ws_ctx" handlers/ message_handler.py mining_logic.py
```

В каждой такой строке заменить `1` на `context.user_data['ws_ctx'].workspace_id`.

- [ ] **Step 3: Smoke test — verify импорты и инстанциация**

```bash
python -c "
import sys; sys.path.insert(0, '.')
from bot_core.workspace_context import build_context
import bot
print('Imports OK')
"
```
Expected: `Imports OK` без exception. Это не полный run, но проверяет что синтаксис и импорты валидны после правок.

- [ ] **Step 4: Commit**

```bash
git add bot.py handlers/ message_handler.py mining_logic.py
git commit -m "feat(V1.17.0a22): WorkspaceContext middleware в bot.py"
```

---

## Phase 6: API layer

### Task 16: Резолв workspace_id в FastAPI

**Files:**
- Modify: `api.py`

- [ ] **Step 1: Добавить dependency для извлечения workspace_id из header**

```python
from fastapi import Header, HTTPException

async def get_workspace_id(
    x_workspace_id: int | None = Header(default=None, alias='X-Workspace-Id'),
) -> int:
    """Извлекает workspace_id из header X-Workspace-Id.
    Если не передан — fallback на 1 (для backward compat — пока сайт работает только с Pulse).
    После Подпроекта #3 (web auth) — будет извлекаться из JWT."""
    return x_workspace_id if x_workspace_id is not None else 1
```

- [ ] **Step 2: Добавить `workspace_id: int = Depends(get_workspace_id)` во все DB-зависимые эндпоинты**

Пример:
```python
@app.get('/api/economy/balance/{user_id}')
async def api_get_balance(user_id: int, workspace_id: int = Depends(get_workspace_id)):
    return {'balance': db_economy.get_user_balance(db.conn, workspace_id, user_id)}
```

- [ ] **Step 3: Frontend — пока добавить заглушечный header X-Workspace-Id: 1 во все API-вызовы**

```js
// Admin_SITE/components/press_release/useApi.js (и аналоги)
const headers = {
  'Authorization': `Bearer ${token}`,
  'X-Workspace-Id': '1',  // TODO: workspace switcher (Подпроект #3)
};
```

- [ ] **Step 4: Commit**

```bash
git add api.py Admin_SITE/
git commit -m "feat(V1.17.0a23): API — workspace_id из header X-Workspace-Id"
```

---

## Phase 7: Smoke + rollback

### Task 17: Запуск миграции на staging snapshot

- [ ] **Step 1: Сделать актуальный backup продакшен БД**

```bash
cp database/bot_database.db database/backups/manual_pre_v1.17.0_$(date +%Y%m%d).db
```

- [ ] **Step 2: Запустить миграцию на копии**

```bash
cp database/bot_database.db /tmp/staging.db
python -c "
from database.migrations.multi_tenancy import migrate_up
migrate_up('/tmp/staging.db')
"
```

- [ ] **Step 3: Прогнать smoke-тесты с новой БД**

```bash
PULSE_DB=/tmp/staging.db python -m pytest tests/ -v
```
Expected: все green.

- [ ] **Step 4: Запустить бота против /tmp/staging.db в DRY_RUN**

Verify: основные команды работают, экономика отвечает, /balance показывает старые данные.

---

### Task 18: Тест rollback

- [ ] **Step 1: На /tmp/staging.db запустить migrate_down**

```bash
python -c "
from database.migrations.multi_tenancy import migrate_down
migrate_down('/tmp/staging.db')
"
```

- [ ] **Step 2: Проверить что workspaces table удалена и workspace_id колонок нет**

```bash
python -c "
import sqlite3
c = sqlite3.connect('/tmp/staging.db')
print('workspaces exists:', bool(c.execute(\"SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspaces'\").fetchone()))
print('user_stats cols:', [r[1] for r in c.execute('PRAGMA table_info(user_stats)')])
"
```

Expected: workspaces=False, user_stats без workspace_id.

- [ ] **Step 3: Запустить старый код против roll-backed БД — должен работать**

(только если ещё есть old-style ветка, например main).

---

### Task 19: Документировать процедуру деплоя в main

**Files:**
- Create: `docs/superpowers/runbooks/multi-tenancy-deploy.md`

- [ ] **Step 1: Написать runbook**

```markdown
# Деплой multi-tenancy foundation в продакшен

## Перед деплоем
1. Убедиться все тесты пройдены: `python -m pytest tests/ -v`
2. Сделать backup: `cp database/bot_database.db database/backups/pre_v1.17.0_<DATE>.db`

## Деплой
1. Остановить бота: `systemctl stop pulse-bot`
2. Pull merge:  `git checkout main && git merge Интеграция-множетсвенные-пользователи`
3. Запустить миграцию: `python -m database.migrations.multi_tenancy`
4. Проверить: workspaces table создана, workspace_id=1 = Pulse Москва.
5. Запустить бота: `systemctl start pulse-bot`
6. Smoke-test через Telegram: /balance, /journal, и т.д.

## Rollback (если что-то пошло не так)
1. `systemctl stop pulse-bot`
2. `cp database/backups/pre_v1.17.0_<DATE>.db database/bot_database.db`
3. `git revert <merge_commit>`
4. `systemctl start pulse-bot`
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/runbooks/
git commit -m "docs: runbook для деплоя multi-tenancy foundation"
```

---

## Conclusion

После всех 19 задач:
- БД мультитенантизирована, существующие Pulse-данные в workspace=1.
- Все DB-функции принимают workspace_id первым аргументом.
- WorkspaceContext резолвится в начале каждого handler-а.
- @pulse_only декоратор защищает Pulse-only фичи.
- API эндпоинты получают workspace_id из header (заглушка 1, до подпроекта #3).
- Тесты покрывают: миграция, изоляция, резолвер, декоратор.

**Следующие подпроекты** (отдельные spec+plan):
- #2: Bot connection flow — как новый чат создаёт workspace.
- #3: Web auth + workspace switcher.
- #5: Per-workspace stats.

Не сливать в main до полного теста. Деплой по runbook.
