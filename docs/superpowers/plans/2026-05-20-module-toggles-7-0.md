# Module Toggles 7.0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Построить механизм единых тумблеров модулей: БД, API, bot-guard, React-компоненты, отдельная вкладка «Тумблеры» (2 колонки) и поиск в каталоге. На этом шаге механизм существует, но **не вешается** ни на один реальный хэндлер бота — это сделают шаги 7.1–7.4.

**Architecture:** Истина в БД (`module_toggles` + история + version), сайт пишет/читает через FastAPI-роутер `/api/workspaces/<id>/modules/...`, бот читает через `db_module_toggles` с локальным кешем 30 с + bump-version. Единый источник списка `module_id` — `shared/modules_catalog.json` (читают и Vite, и Python).

**Tech Stack:** Python 3.11, sqlite3, FastAPI, pytest, React 18, Vite, Tailwind (классы `bg-ok`/`bg-bd2`/`bg-sff` уже используются в Toggle.jsx), Lucide icons.

**Spec:** `docs/superpowers/specs/2026-05-20-module-toggles-design.md`

---

## File Structure (создаются/правятся)

**Создаются:**
- `shared/modules_catalog.json` — единый источник списка модулей.
- `database/migrations/module_toggles.py` — миграция 3 таблиц.
- `database/db_module_toggles.py` — CRUD + кеш + bump_version.
- `bot_core/module_guard.py` — `is_module_enabled` + декоратор `@requires_module`.
- `api/modules_routes.py` — 4 эндпоинта.
- `Admin_SITE/hooks/useModules.js` — fetch + mutate.
- `Admin_SITE/components/modules/ModuleToggle.jsx`
- `Admin_SITE/components/modules/ModuleHeader.jsx`
- `Admin_SITE/components/modules/DisableReasonModal.jsx`
- `Admin_SITE/components/modules/ModulesTogglesTab.jsx` — вкладка 2 колонки.
- `tests/test_db_module_toggles.py`
- `tests/test_api_module_toggles.py`
- `tests/test_module_guard.py`

**Правятся:**
- `api.py` — регистрация роутера.
- `Admin_SITE/components/modules/ModulesHub.jsx` — поиск + замена кнопки на `<ModuleToggle>`.
- `Admin_SITE/AdminDashboard.jsx` — удаление `localStorage`, регистрация вкладки «Тумблеры» в Системе.

---

## Task 1 · Каталог модулей в JSON

**Files:**
- Create: `shared/modules_catalog.json`

- [ ] **Step 1: Создать JSON со списком модулей**

```json
{
  "modules": [
    {"id": "statistics",    "name": "Статистика",     "section": "analytics",  "description": "11 виджетов-графиков активности чата."},
    {"id": "top5",          "name": "Топ-5",          "section": "analytics",  "description": "Рейтинги участников по периодам."},
    {"id": "economy",       "name": "Экономика",      "section": "economy",    "description": "Награды, штрафы, валюта чата."},
    {"id": "sprints",       "name": "Спринты",        "section": "economy",    "description": "Соревнования участников за период."},
    {"id": "combos",        "name": "Комбо",          "section": "economy",    "description": "Серии действий за бонусы."},
    {"id": "shipper",       "name": "Шиппер",         "section": "engagement", "description": "Шипперинг участников + награды."},
    {"id": "donations",     "name": "Донаты",         "section": "engagement", "description": "Сбор донатов через бота."},
    {"id": "bbs_pulse",     "name": "Пульс ББС",      "section": "engagement", "description": "ББС-механика для активных."},
    {"id": "bbs_other",     "name": "ББС Другое",     "section": "engagement", "description": "Прочие ББС-функции."},
    {"id": "bbs_anketa",    "name": "Ред.анкет ББС",  "section": "engagement", "description": "Редактирование анкет ББС."},
    {"id": "bbs_vip",       "name": "VIP BBS",        "section": "engagement", "description": "Платная ББС-метка VIP."},
    {"id": "titles",        "name": "Титулы",         "section": "engagement", "description": "Платные титулы."},
    {"id": "press_release", "name": "Пресс-релизы",   "section": "content",    "description": "Публикация постов в чат."},
    {"id": "triggers",      "name": "Триггеры",       "section": "content",    "description": "Авто-реакции на слова/фразы."},
    {"id": "horoscope",     "name": "Гороскоп",       "section": "content",    "description": "Авто-гороскоп для участников."},
    {"id": "journal",       "name": "Журнал",         "section": "journal",    "description": "Лог событий чата (15 суб-журналов)."}
  ]
}
```

- [ ] **Step 2: Закоммитить**

```
git add shared/modules_catalog.json
git commit -m "feat(V1.17.0h0a): каталог модулей в shared/modules_catalog.json"
```

---

## Task 2 · Миграция БД

**Files:**
- Create: `database/migrations/module_toggles.py`
- Test: `tests/test_db_module_toggles.py` (только smoke на этом шаге)

- [ ] **Step 1: Написать smoke-тест миграции**

```python
# tests/test_db_module_toggles.py
import sqlite3
from database.migrations.module_toggles import up

def test_migration_creates_three_tables():
    conn = sqlite3.connect(":memory:")
    up(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "module_toggles" in tables
    assert "module_toggle_history" in tables
    assert "module_toggle_cache_version" in tables

def test_migration_is_idempotent():
    conn = sqlite3.connect(":memory:")
    up(conn)
    up(conn)  # should not raise
```

- [ ] **Step 2: Запустить — упадёт**

```
pytest tests/test_db_module_toggles.py -v
```
Ожидаем: ImportError (нет модуля).

- [ ] **Step 3: Написать миграцию**

```python
# database/migrations/module_toggles.py
"""Module toggles migration — 3 tables + index.
ID: 2026-05-20-module-toggles
Spec: docs/superpowers/specs/2026-05-20-module-toggles-design.md
"""
import sqlite3


def up(conn: sqlite3.Connection) -> None:
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS module_toggles (
            workspace_id INTEGER NOT NULL,
            module_id    TEXT    NOT NULL,
            is_enabled   INTEGER NOT NULL DEFAULT 0,
            updated_by   INTEGER,
            updated_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, module_id)
        );

        CREATE TABLE IF NOT EXISTS module_toggle_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            module_id    TEXT    NOT NULL,
            action       TEXT    NOT NULL CHECK (action IN ('enable','disable')),
            reason       TEXT,
            changed_by   INTEGER NOT NULL,
            changed_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_mth_ws_mod
            ON module_toggle_history(workspace_id, module_id, changed_at DESC);

        CREATE TABLE IF NOT EXISTS module_toggle_cache_version (
            workspace_id INTEGER PRIMARY KEY,
            version      INTEGER NOT NULL DEFAULT 0
        );
    ''')
    conn.commit()
```

- [ ] **Step 4: Запустить — пройдёт**

```
pytest tests/test_db_module_toggles.py -v
```

- [ ] **Step 5: Подключить миграцию к startup**

Найти, где регистрируются миграции (вероятно `database/db_manager.py` или `bot.py`). Добавить вызов `module_toggles.up(conn)` рядом с другими миграциями (`composite_pk_fix` и т.п.).

Команда поиска:
```
grep -n "multi_tenancy\|composite_pk_fix" --include='*.py' -r .
```

- [ ] **Step 6: Коммит**

```
git add database/migrations/module_toggles.py tests/test_db_module_toggles.py <файл-с-регистрацией>
git commit -m "feat(V1.17.0h0b): миграция module_toggles + smoke-тест"
```

---

## Task 3 · CRUD `db_module_toggles.py`

**Files:**
- Create: `database/db_module_toggles.py`
- Modify: `tests/test_db_module_toggles.py` (добавляем CRUD-тесты)

- [ ] **Step 1: Добавить тесты CRUD (failing)**

Дописать в `tests/test_db_module_toggles.py`:

```python
import json
from pathlib import Path
from database.db_module_toggles import (
    is_module_enabled, set_module_state, get_modules,
    list_history, get_cache_version, bump_cache_version,
    VALID_MODULE_IDS,
)
from database.migrations.module_toggles import up as _up

def _fresh():
    conn = sqlite3.connect(":memory:")
    _up(conn)
    return conn

def test_default_module_is_disabled():
    conn = _fresh()
    assert is_module_enabled(conn, 1, "triggers") is False

def test_set_module_state_enable_then_disable():
    conn = _fresh()
    set_module_state(conn, 1, "triggers", True,  reason=None,           user_id=42)
    assert is_module_enabled(conn, 1, "triggers") is True
    set_module_state(conn, 1, "triggers", False, reason="не нужен", user_id=42)
    assert is_module_enabled(conn, 1, "triggers") is False

def test_workspace_isolation():
    conn = _fresh()
    set_module_state(conn, 1, "triggers", True, reason=None, user_id=42)
    assert is_module_enabled(conn, 1, "triggers") is True
    assert is_module_enabled(conn, 2, "triggers") is False

def test_disable_requires_reason():
    conn = _fresh()
    try:
        set_module_state(conn, 1, "triggers", False, reason=None, user_id=42)
        assert False, "должен был кинуть ValueError"
    except ValueError:
        pass

def test_invalid_module_id_rejected():
    conn = _fresh()
    try:
        set_module_state(conn, 1, "unknown_xxx", True, reason=None, user_id=42)
        assert False
    except ValueError:
        pass

def test_history_records_action_and_reason():
    conn = _fresh()
    set_module_state(conn, 1, "triggers", True,  reason=None, user_id=42)
    set_module_state(conn, 1, "triggers", False, reason="тест", user_id=42)
    h = list_history(conn, 1, "triggers", limit=10)
    assert [r["action"] for r in h] == ["disable", "enable"]  # DESC
    assert h[0]["reason"] == "тест"

def test_bump_cache_version_increments():
    conn = _fresh()
    v0 = get_cache_version(conn, 1)
    bump_cache_version(conn, 1)
    assert get_cache_version(conn, 1) == v0 + 1

def test_set_module_state_bumps_version():
    conn = _fresh()
    v0 = get_cache_version(conn, 1)
    set_module_state(conn, 1, "triggers", True, reason=None, user_id=42)
    assert get_cache_version(conn, 1) == v0 + 1

def test_valid_module_ids_loaded_from_json():
    cat = json.loads(Path("shared/modules_catalog.json").read_text(encoding="utf-8"))
    expected = {m["id"] for m in cat["modules"]}
    assert VALID_MODULE_IDS == expected

def test_get_modules_returns_all_with_defaults():
    conn = _fresh()
    items = get_modules(conn, 1)
    ids = {i["id"] for i in items}
    assert "triggers" in ids
    assert all(i["is_enabled"] is False for i in items)
```

- [ ] **Step 2: Запустить — упадёт**

```
pytest tests/test_db_module_toggles.py -v
```

- [ ] **Step 3: Реализовать CRUD**

```python
# database/db_module_toggles.py
"""CRUD для module_toggles + history + cache_version.
Используется и api/modules_routes.py, и bot_core/module_guard.py.
"""
import json
import sqlite3
from pathlib import Path
from typing import List, Optional

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "shared" / "modules_catalog.json"
_CATALOG = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
VALID_MODULE_IDS = {m["id"] for m in _CATALOG["modules"]}
_MODULE_META = {m["id"]: m for m in _CATALOG["modules"]}


def _validate_module_id(module_id: str) -> None:
    if module_id not in VALID_MODULE_IDS:
        raise ValueError(f"Unknown module_id: {module_id}")


def is_module_enabled(conn: sqlite3.Connection, workspace_id: int, module_id: str) -> bool:
    _validate_module_id(module_id)
    row = conn.execute(
        "SELECT is_enabled FROM module_toggles WHERE workspace_id=? AND module_id=?",
        (workspace_id, module_id),
    ).fetchone()
    return bool(row and row[0])


def set_module_state(
    conn: sqlite3.Connection,
    workspace_id: int,
    module_id: str,
    is_enabled: bool,
    reason: Optional[str],
    user_id: int,
) -> None:
    _validate_module_id(module_id)
    if not is_enabled and not (reason and reason.strip()):
        raise ValueError("reason required when disabling a module")
    conn.execute(
        '''INSERT INTO module_toggles (workspace_id, module_id, is_enabled, updated_by, updated_at)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(workspace_id, module_id) DO UPDATE SET
               is_enabled=excluded.is_enabled,
               updated_by=excluded.updated_by,
               updated_at=CURRENT_TIMESTAMP''',
        (workspace_id, module_id, 1 if is_enabled else 0, user_id),
    )
    conn.execute(
        '''INSERT INTO module_toggle_history (workspace_id, module_id, action, reason, changed_by)
           VALUES (?, ?, ?, ?, ?)''',
        (workspace_id, module_id, "enable" if is_enabled else "disable", reason, user_id),
    )
    bump_cache_version(conn, workspace_id)
    conn.commit()


def get_modules(conn: sqlite3.Connection, workspace_id: int) -> List[dict]:
    rows = conn.execute(
        "SELECT module_id, is_enabled, updated_at, updated_by "
        "FROM module_toggles WHERE workspace_id=?",
        (workspace_id,),
    ).fetchall()
    state = {r[0]: {"is_enabled": bool(r[1]), "updated_at": r[2], "updated_by": r[3]} for r in rows}
    result = []
    for m in _CATALOG["modules"]:
        s = state.get(m["id"], {"is_enabled": False, "updated_at": None, "updated_by": None})
        result.append({
            "id": m["id"], "name": m["name"], "section": m["section"],
            "description": m["description"], **s,
        })
    return result


def list_history(conn: sqlite3.Connection, workspace_id: int, module_id: str, limit: int = 20) -> List[dict]:
    _validate_module_id(module_id)
    rows = conn.execute(
        '''SELECT action, reason, changed_by, changed_at
           FROM module_toggle_history
           WHERE workspace_id=? AND module_id=?
           ORDER BY changed_at DESC LIMIT ?''',
        (workspace_id, module_id, limit),
    ).fetchall()
    return [
        {"action": r[0], "reason": r[1], "changed_by": r[2], "changed_at": r[3]}
        for r in rows
    ]


def get_cache_version(conn: sqlite3.Connection, workspace_id: int) -> int:
    row = conn.execute(
        "SELECT version FROM module_toggle_cache_version WHERE workspace_id=?",
        (workspace_id,),
    ).fetchone()
    return row[0] if row else 0


def bump_cache_version(conn: sqlite3.Connection, workspace_id: int) -> None:
    conn.execute(
        '''INSERT INTO module_toggle_cache_version (workspace_id, version)
           VALUES (?, 1)
           ON CONFLICT(workspace_id) DO UPDATE SET version = version + 1''',
        (workspace_id,),
    )
```

- [ ] **Step 4: Запустить — пройдёт**

```
pytest tests/test_db_module_toggles.py -v
```

- [ ] **Step 5: Коммит**

```
git add database/db_module_toggles.py tests/test_db_module_toggles.py
git commit -m "feat(V1.17.0h0c): CRUD module_toggles + 10 тестов (изоляция WS, history, version)"
```

---

## Task 4 · Bot-guard

**Files:**
- Create: `bot_core/module_guard.py`
- Create: `tests/test_module_guard.py`

- [ ] **Step 1: Тесты guard'а (failing)**

```python
# tests/test_module_guard.py
import asyncio
import sqlite3
import pytest
from database.migrations.module_toggles import up
from database.db_module_toggles import set_module_state
from bot_core.module_guard import (
    is_module_enabled_cached, requires_module, _invalidate_cache_for_ws,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    up(c)
    return c


def test_disabled_by_default(conn):
    assert is_module_enabled_cached(conn, 1, "triggers") is False


def test_enabled_after_set(conn):
    set_module_state(conn, 1, "triggers", True, reason=None, user_id=42)
    _invalidate_cache_for_ws(1)
    assert is_module_enabled_cached(conn, 1, "triggers") is True


def test_cache_invalidates_on_version_bump(conn):
    assert is_module_enabled_cached(conn, 1, "triggers") is False
    set_module_state(conn, 1, "triggers", True, reason=None, user_id=42)
    # Version bumped inside set_module_state; cached helper must notice.
    assert is_module_enabled_cached(conn, 1, "triggers") is True


def test_requires_module_silent_when_off(conn):
    calls = []

    @requires_module("triggers", conn_provider=lambda *_: conn,
                     ws_resolver=lambda *_: 1)
    async def handler(update, ctx):
        calls.append("ran")

    asyncio.run(handler({"x": 1}, {}))
    assert calls == []


def test_requires_module_runs_when_on(conn):
    set_module_state(conn, 1, "triggers", True, reason=None, user_id=42)
    calls = []

    @requires_module("triggers", conn_provider=lambda *_: conn,
                     ws_resolver=lambda *_: 1)
    async def handler(update, ctx):
        calls.append("ran")

    asyncio.run(handler({"x": 1}, {}))
    assert calls == ["ran"]
```

- [ ] **Step 2: Запустить — упадёт**

```
pytest tests/test_module_guard.py -v
```

- [ ] **Step 3: Реализовать guard**

```python
# bot_core/module_guard.py
"""Декоратор @requires_module + cached is_module_enabled.

Кеш: {(ws_id, module_id): (is_enabled, version_seen_at_read)}.
Инвалидация: если БД version > version_seen — перечитываем.
TTL: дополнительно 30 c, чтобы redundant lookups были редкими.
"""
import functools
import time
from typing import Callable

from database.db_module_toggles import is_module_enabled, get_cache_version

_CACHE: dict = {}
_TTL = 30.0


def _invalidate_cache_for_ws(workspace_id: int) -> None:
    """Очистить весь кеш для workspace (тестовый хелпер)."""
    for k in list(_CACHE.keys()):
        if k[0] == workspace_id:
            _CACHE.pop(k, None)


def is_module_enabled_cached(conn, workspace_id: int, module_id: str) -> bool:
    key = (workspace_id, module_id)
    now = time.monotonic()
    cur_version = get_cache_version(conn, workspace_id)
    cached = _CACHE.get(key)
    if cached is not None:
        value, seen_version, seen_at = cached
        if seen_version == cur_version and (now - seen_at) < _TTL:
            return value
    value = is_module_enabled(conn, workspace_id, module_id)
    _CACHE[key] = (value, cur_version, now)
    return value


def requires_module(module_id: str, *,
                    conn_provider: Callable,
                    ws_resolver: Callable):
    """Guard для PTB-хэндлера.

    conn_provider(update, context) -> sqlite3.Connection
    ws_resolver(update, context)  -> workspace_id

    Если модуль OFF — silent return (None). Иначе вызывает обёрнутый handler.
    """
    def deco(handler):
        @functools.wraps(handler)
        async def wrapped(update, context, *a, **kw):
            conn = conn_provider(update, context)
            ws_id = ws_resolver(update, context)
            if not is_module_enabled_cached(conn, ws_id, module_id):
                return None
            return await handler(update, context, *a, **kw)
        return wrapped
    return deco
```

- [ ] **Step 4: Запустить — пройдёт**

```
pytest tests/test_module_guard.py -v
```

- [ ] **Step 5: Коммит**

```
git add bot_core/module_guard.py tests/test_module_guard.py
git commit -m "feat(V1.17.0h0d): bot module_guard — @requires_module + кешированный is_module_enabled"
```

---

## Task 5 · API роутер (FastAPI)

**Files:**
- Create: `api/modules_routes.py`
- Create: `tests/test_api_module_toggles.py`

- [ ] **Step 1: Тесты API (failing)**

```python
# tests/test_api_module_toggles.py
import sqlite3
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.migrations.module_toggles import up as up_modules
from api.modules_routes import router as modules_router, _setup as modules_setup


class _DB:
    def __init__(self, conn):
        self.conn = conn


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    up_modules(conn)
    # workspace_members нужен для _check_role — создаём минимально:
    conn.execute("CREATE TABLE workspace_members (workspace_id INTEGER, user_id INTEGER, role TEXT)")
    conn.execute("INSERT INTO workspace_members VALUES (1, 100, 'owner')")
    conn.execute("INSERT INTO workspace_members VALUES (1, 200, 'admin')")
    conn.execute("INSERT INTO workspace_members VALUES (1, 300, 'moderator')")
    conn.commit()

    app = FastAPI()

    # Тестовый require_auth: токен = user_id строкой.
    def require_auth(authorization: str) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            from fastapi import HTTPException
            raise HTTPException(401, "no auth")
        return {"user_id": int(authorization.split(" ", 1)[1])}

    modules_setup(_DB(conn), require_auth)
    app.include_router(modules_router)
    return TestClient(app)


def _h(uid): return {"Authorization": f"Bearer {uid}"}


def test_list_returns_all_modules_default_disabled(client):
    r = client.get("/api/workspaces/1/modules", headers=_h(100))
    assert r.status_code == 200
    items = r.json()
    assert any(m["id"] == "triggers" for m in items)
    assert all(m["is_enabled"] is False for m in items)


def test_owner_can_enable(client):
    r = client.post("/api/workspaces/1/modules/triggers/enable", headers=_h(100), json={})
    assert r.status_code == 200
    assert r.json()["is_enabled"] is True


def test_admin_can_enable(client):
    r = client.post("/api/workspaces/1/modules/triggers/enable", headers=_h(200), json={})
    assert r.status_code == 200


def test_moderator_cannot_enable(client):
    r = client.post("/api/workspaces/1/modules/triggers/enable", headers=_h(300), json={})
    assert r.status_code == 403


def test_disable_requires_reason(client):
    client.post("/api/workspaces/1/modules/triggers/enable", headers=_h(100), json={})
    r = client.post("/api/workspaces/1/modules/triggers/disable", headers=_h(100), json={"reason": ""})
    assert r.status_code == 400


def test_disable_with_reason_ok(client):
    client.post("/api/workspaces/1/modules/triggers/enable", headers=_h(100), json={})
    r = client.post("/api/workspaces/1/modules/triggers/disable", headers=_h(100), json={"reason": "не нужен"})
    assert r.status_code == 200
    assert r.json()["is_enabled"] is False


def test_unknown_module_returns_404(client):
    r = client.post("/api/workspaces/1/modules/xxx_nope/enable", headers=_h(100), json={})
    assert r.status_code == 404


def test_history_returns_records(client):
    client.post("/api/workspaces/1/modules/triggers/enable", headers=_h(100), json={})
    client.post("/api/workspaces/1/modules/triggers/disable", headers=_h(100), json={"reason": "test"})
    r = client.get("/api/workspaces/1/modules/triggers/history", headers=_h(100))
    assert r.status_code == 200
    h = r.json()
    assert [x["action"] for x in h] == ["disable", "enable"]
```

- [ ] **Step 2: Запустить — упадёт**

```
pytest tests/test_api_module_toggles.py -v
```

- [ ] **Step 3: Реализовать роутер**

```python
# api/modules_routes.py
"""FastAPI endpoints: /api/workspaces/{ws_id}/modules/..."""
import logging
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from database.db_module_toggles import (
    VALID_MODULE_IDS, get_modules, set_module_state, list_history,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workspaces", tags=["modules"])

_db = None
_require_auth_fn = None


def _setup(db, require_auth):
    global _db, _require_auth_fn
    _db = db
    _require_auth_fn = require_auth


def _auth(authorization: str) -> dict:
    return _require_auth_fn(authorization)


def _check_write_role(ws_id: int, user_id: int) -> str:
    row = _db.conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
        (ws_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "workspace not found or no membership")
    role = row[0]
    if role not in ("owner", "admin"):
        raise HTTPException(403, "owner or admin required")
    return role


class DisableBody(BaseModel):
    reason: str


@router.get("/{ws_id}/modules")
def list_modules(ws_id: int, authorization: str = Header(default="")):
    _auth(authorization)
    return get_modules(_db.conn, ws_id)


@router.post("/{ws_id}/modules/{module_id}/enable")
def enable_module(ws_id: int, module_id: str, authorization: str = Header(default="")):
    user = _auth(authorization)
    if module_id not in VALID_MODULE_IDS:
        raise HTTPException(404, "unknown module")
    _check_write_role(ws_id, user["user_id"])
    set_module_state(_db.conn, ws_id, module_id, True, reason=None, user_id=user["user_id"])
    return {"is_enabled": True}


@router.post("/{ws_id}/modules/{module_id}/disable")
def disable_module(
    ws_id: int, module_id: str, body: DisableBody,
    authorization: str = Header(default=""),
):
    user = _auth(authorization)
    if module_id not in VALID_MODULE_IDS:
        raise HTTPException(404, "unknown module")
    if not body.reason or not body.reason.strip():
        raise HTTPException(400, "reason required")
    _check_write_role(ws_id, user["user_id"])
    set_module_state(_db.conn, ws_id, module_id, False, reason=body.reason.strip(),
                     user_id=user["user_id"])
    return {"is_enabled": False}


@router.get("/{ws_id}/modules/{module_id}/history")
def module_history(ws_id: int, module_id: str, limit: int = 20,
                   authorization: str = Header(default="")):
    _auth(authorization)
    if module_id not in VALID_MODULE_IDS:
        raise HTTPException(404, "unknown module")
    return list_history(_db.conn, ws_id, module_id, limit=limit)
```

- [ ] **Step 4: Запустить — пройдёт**

```
pytest tests/test_api_module_toggles.py -v
```

- [ ] **Step 5: Коммит**

```
git add api/modules_routes.py tests/test_api_module_toggles.py
git commit -m "feat(V1.17.0h0e): API /api/workspaces/<id>/modules — 4 эндпоинта + 8 тестов"
```

---

## Task 6 · Регистрация роутера в `api.py`

**Files:**
- Modify: `api.py` (рядом с `workspaces_router`)

- [ ] **Step 1: Найти блок регистрации workspaces_router**

```
grep -n "workspaces_router\|workspaces_routes" api.py
```

- [ ] **Step 2: Добавить регистрацию modules_routes**

Сразу после блока `workspaces_router` вставить:

```python
try:
    from api.modules_routes import router as modules_router, _setup as _modules_setup
    _modules_setup(db, require_auth)
    app.include_router(modules_router)
    logger.info("✅ modules: роутер подключён")
except Exception as e:
    logger.warning(f"⚠️ Ошибка подключения modules router: {e}")
```

(Используем те же `db` и `require_auth`, что и для workspaces — посмотреть строку выше и взять имена один-в-один.)

- [ ] **Step 3: Запустить smoke**

```
python -c "from api import app; print([r.path for r in app.routes if '/modules' in r.path])"
```

Ожидаем 4 пути `/api/workspaces/{ws_id}/modules...`.

- [ ] **Step 4: Коммит**

```
git add api.py
git commit -m "feat(V1.17.0h0f): подключить modules_router в api.py"
```

---

## Task 7 · Backfill для workspace=1

**Files:**
- Create: `scripts/backfill_module_toggles_ws1.py`

- [ ] **Step 1: Скрипт backfill**

```python
# scripts/backfill_module_toggles_ws1.py
"""Одноразово: включить module_toggles для workspace=1 (Витя)
для модулей, чьи фичи сейчас реально работают в проде.
Идемпотентно: повторный запуск ничего не меняет (ON CONFLICT DO NOTHING).
"""
import sqlite3
import sys
from pathlib import Path

# Подключить тот же путь к БД, что использует bot.py.
# Здесь — пример; уточнить путь под прод/dev перед запуском.
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "pulse_bot.db"

ENABLED_FOR_WS1 = [
    "triggers", "press_release", "shipper", "horoscope",
    "economy", "statistics", "top5", "donations",
    "bbs_pulse", "bbs_other", "bbs_anketa", "bbs_vip", "titles",
    "journal",
    # sprints, combos — НЕ включаем (не работают по факту, см. контракт).
]

WS_ID = 1
SYSTEM_USER = 0  # 0 = system/migration

def main():
    conn = sqlite3.connect(DB_PATH)
    inserted = 0
    for mid in ENABLED_FOR_WS1:
        cur = conn.execute(
            '''INSERT INTO module_toggles (workspace_id, module_id, is_enabled, updated_by)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(workspace_id, module_id) DO NOTHING''',
            (WS_ID, mid, SYSTEM_USER),
        )
        if cur.rowcount:
            inserted += 1
            conn.execute(
                '''INSERT INTO module_toggle_history (workspace_id, module_id, action, reason, changed_by)
                   VALUES (?, ?, 'enable', 'backfill V1.17.0h0', ?)''',
                (WS_ID, mid, SYSTEM_USER),
            )
    # bump version once
    conn.execute(
        '''INSERT INTO module_toggle_cache_version (workspace_id, version) VALUES (?, 1)
           ON CONFLICT(workspace_id) DO UPDATE SET version = version + 1''',
        (WS_ID,),
    )
    conn.commit()
    print(f"backfill: inserted={inserted}, total_targets={len(ENABLED_FOR_WS1)}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Тестовый прогон на in-memory**

Создать `tests/test_backfill_module_toggles.py`:
```python
import sqlite3, runpy, sys
from database.migrations.module_toggles import up

def test_backfill_inserts_expected_modules(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    up(conn); conn.close()
    sys.argv = ["backfill", str(db)]
    runpy.run_path("scripts/backfill_module_toggles_ws1.py", run_name="__main__")
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT module_id FROM module_toggles WHERE workspace_id=1 AND is_enabled=1"
    ).fetchall()
    ids = {r[0] for r in rows}
    assert "triggers" in ids and "horoscope" in ids and "sprints" not in ids
```

- [ ] **Step 3: Запустить**

```
pytest tests/test_backfill_module_toggles.py -v
```

- [ ] **Step 4: Коммит**

```
git add scripts/backfill_module_toggles_ws1.py tests/test_backfill_module_toggles.py
git commit -m "feat(V1.17.0h0g): backfill module_toggles для workspace=1 + тест"
```

---

## Task 8 · React-хук `useModules`

**Files:**
- Create: `Admin_SITE/hooks/useModules.js`

- [ ] **Step 1: Написать хук**

```javascript
// Admin_SITE/hooks/useModules.js
import { useCallback, useEffect, useState } from 'react';

const TOKEN_KEY = 'pulse_token'; // как в AdminDashboard.jsx
const WS_KEY    = 'pulse_active_ws_id';

function authHeader() {
  const t = localStorage.getItem(TOKEN_KEY);
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export function useModules(wsId) {
  const [modules, setModules]   = useState([]);
  const [loading, setLoading]   = useState(false);
  const [error,   setError]     = useState(null);

  const load = useCallback(async () => {
    if (!wsId) return;
    setLoading(true); setError(null);
    try {
      const r = await fetch(`/api/workspaces/${wsId}/modules`, { headers: authHeader() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setModules(await r.json());
    } catch (e) { setError(e); }
    finally    { setLoading(false); }
  }, [wsId]);

  useEffect(() => { load(); }, [load]);

  const enable = useCallback(async (moduleId) => {
    const r = await fetch(`/api/workspaces/${wsId}/modules/${moduleId}/enable`,
      { method: 'POST', headers: { ...authHeader(), 'Content-Type': 'application/json' }, body: '{}' });
    if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
    await load();
  }, [wsId, load]);

  const disable = useCallback(async (moduleId, reason) => {
    const r = await fetch(`/api/workspaces/${wsId}/modules/${moduleId}/disable`,
      { method: 'POST', headers: { ...authHeader(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }) });
    if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
    await load();
  }, [wsId, load]);

  const history = useCallback(async (moduleId, limit = 20) => {
    const r = await fetch(
      `/api/workspaces/${wsId}/modules/${moduleId}/history?limit=${limit}`,
      { headers: authHeader() });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  }, [wsId]);

  return { modules, loading, error, enable, disable, history, reload: load };
}
```

(Если `pulse_token` / `pulse_active_ws_id` имеют другие имена в `AdminDashboard.jsx` — заменить на правильные. Команда поиска: `grep -n "localStorage.*pulse" Admin_SITE/AdminDashboard.jsx | head -5`.)

- [ ] **Step 2: Коммит**

```
git add Admin_SITE/hooks/useModules.js
git commit -m "feat(V1.17.0h0h) [Site]: hook useModules — fetch/enable/disable/history через API"
```

---

## Task 9 · `DisableReasonModal` + `ModuleToggle`

**Files:**
- Create: `Admin_SITE/components/modules/DisableReasonModal.jsx`
- Create: `Admin_SITE/components/modules/ModuleToggle.jsx`

- [ ] **Step 1: Модалка причины**

```jsx
// Admin_SITE/components/modules/DisableReasonModal.jsx
import { useState } from 'react';

export default function DisableReasonModal({ moduleName, onCancel, onConfirm }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const tooShort = reason.trim().length < 3;
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
         onClick={onCancel}>
      <div className="bg-sff rounded-2xl border border-bd max-w-md w-full p-5"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-bold mb-1">Отключить модуль «{moduleName}»</h3>
        <p className="text-sm text-txm mb-3">
          Расскажите коротко, зачем — это попадёт в журнал.
        </p>
        <textarea
          autoFocus
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Например: не нужен в моём чате"
          className="w-full min-h-[88px] rounded-xl border border-bd px-3 py-2 text-sm bg-sff"
        />
        <div className="flex gap-2 mt-4 justify-end">
          <button onClick={onCancel}
            className="px-4 py-2 rounded-xl bg-sff border border-bd text-txd text-sm">
            Отмена
          </button>
          <button
            disabled={tooShort || busy}
            onClick={async () => {
              setBusy(true);
              try { await onConfirm(reason.trim()); }
              finally { setBusy(false); }
            }}
            className="px-4 py-2 rounded-xl bg-cta text-white font-semibold text-sm disabled:opacity-50">
            {busy ? 'Отключаю…' : 'Подтвердить отключение'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: ModuleToggle**

```jsx
// Admin_SITE/components/modules/ModuleToggle.jsx
import { useState } from 'react';
import Toggle from '../shared/Toggle';
import DisableReasonModal from './DisableReasonModal';

export default function ModuleToggle({ moduleId, moduleName, modulesApi, disabled = false }) {
  const m = (modulesApi.modules || []).find(x => x.id === moduleId);
  const [showReason, setShowReason] = useState(false);
  const [busy, setBusy] = useState(false);

  const handleChange = async (next) => {
    if (next) {
      setBusy(true);
      try { await modulesApi.enable(moduleId); }
      finally { setBusy(false); }
    } else {
      setShowReason(true);
    }
  };

  return (
    <>
      <Toggle
        checked={!!m?.is_enabled}
        onChange={handleChange}
        className={busy || disabled ? 'opacity-50 pointer-events-none' : ''}
      />
      {showReason && (
        <DisableReasonModal
          moduleName={moduleName || moduleId}
          onCancel={() => setShowReason(false)}
          onConfirm={async (reason) => {
            await modulesApi.disable(moduleId, reason);
            setShowReason(false);
          }}
        />
      )}
    </>
  );
}
```

- [ ] **Step 3: Коммит**

```
git add Admin_SITE/components/modules/DisableReasonModal.jsx Admin_SITE/components/modules/ModuleToggle.jsx
git commit -m "feat(V1.17.0h0i) [Site]: ModuleToggle + DisableReasonModal"
```

---

## Task 10 · `ModuleHeader` (паспорт)

**Files:**
- Create: `Admin_SITE/components/modules/ModuleHeader.jsx`

- [ ] **Step 1: Компонент-паспорт**

```jsx
// Admin_SITE/components/modules/ModuleHeader.jsx
import ModuleToggle from './ModuleToggle';

export default function ModuleHeader({
  moduleId, icon: Icon, name, description, modulesApi, canToggle = true,
}) {
  return (
    <div className="bg-sff border border-bd rounded-2xl p-4 flex items-center gap-4 mb-4">
      {Icon && (
        <div className="w-10 h-10 rounded-xl bg-bg2 flex items-center justify-center flex-shrink-0">
          <Icon size={20} className="text-txd" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="font-bold text-txd">{name}</div>
        {description && <div className="text-sm text-txm truncate">{description}</div>}
      </div>
      <ModuleToggle
        moduleId={moduleId}
        moduleName={name}
        modulesApi={modulesApi}
        disabled={!canToggle}
      />
    </div>
  );
}
```

- [ ] **Step 2: Коммит**

```
git add Admin_SITE/components/modules/ModuleHeader.jsx
git commit -m "feat(V1.17.0h0j) [Site]: ModuleHeader — единый паспорт модуля сверху экрана"
```

---

## Task 11 · Поиск в `ModulesHub` + замена localStorage-кнопки

**Files:**
- Modify: `Admin_SITE/components/modules/ModulesHub.jsx`

- [ ] **Step 1: Проверить текущую сигнатуру `ModulesHub`**

```
grep -n "export default\|function ModulesHub\|props" Admin_SITE/components/modules/ModulesHub.jsx | head -10
```

- [ ] **Step 2: Изменить ModulesHub**

Внести три изменения:

**(а) Принять `modulesApi` в props** (вместо `connected/onConnect/onDisconnect`):
```jsx
export default function ModulesHub({ onOpen, modulesApi }) {
```

**(б) Заменить кнопку «Подключить/Отключить» на `<ModuleToggle>`** в карточке модуля. Найти текущую кнопку (старая логика `connected.has(card.id)`) и заменить:
```jsx
import ModuleToggle from './ModuleToggle';
// ...внутри карточки, в углу с кнопками действий:
<ModuleToggle moduleId={card.id} moduleName={card.name} modulesApi={modulesApi} />
```
Источник правды о состоянии «подключён?» — `modulesApi.modules.find(m => m.id === card.id)?.is_enabled`. Если в карточке есть условный рендер «подключённый/нет» — использовать его.

**(в) Поиск в шапке хаба:**
```jsx
import { useMemo, useState } from 'react';
// ...
const [query, setQuery] = useState('');
const q = query.trim().toLowerCase();
const visibleCards = useMemo(
  () => allCards.filter(c =>
    !q || c.name.toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q)
  ),
  [allCards, q]
);
// ...в шапке хаба, над под-навигацией:
<div className="mb-4">
  <input
    type="text"
    value={query}
    onChange={(e) => setQuery(e.target.value)}
    onKeyDown={(e) => e.key === 'Escape' && setQuery('')}
    placeholder="Найти модуль…"
    className="w-full max-w-sm px-3 py-2 rounded-xl bg-sff border border-bd text-sm"
  />
</div>
// ...empty state, если visibleCards.length === 0:
{visibleCards.length === 0 && (
  <div className="text-center text-txm py-12">
    Ничего не найдено по запросу «{query}».{' '}
    <button onClick={() => setQuery('')} className="underline">сбросить</button>
  </div>
)}
```

(Подсветка `<mark>` — пропускаем на 7.0, если потребует UX-полировки — добавим отдельным мелким коммитом.)

- [ ] **Step 3: Локальная сборка**

```
node node_modules/vite/bin/vite.js build
```

Сборка должна пройти без ошибок (см. memory `build_npx_node_dir_trap`).

- [ ] **Step 4: Коммит**

```
git add Admin_SITE/components/modules/ModulesHub.jsx Admin_SITE/dist
git commit -m "feat(V1.17.0h0k) [Site]: ModulesHub — поиск + ModuleToggle вместо локального state"
```

---

## Task 12 · Вкладка «Тумблеры модулей» (grid в 2 колонки)

**Files:**
- Create: `Admin_SITE/components/modules/ModulesTogglesTab.jsx`

- [ ] **Step 1: Создать вкладку**

```jsx
// Admin_SITE/components/modules/ModulesTogglesTab.jsx
import { useMemo, useState } from 'react';
import ModuleToggle from './ModuleToggle';

export default function ModulesTogglesTab({ modulesApi }) {
  const [query, setQuery] = useState('');
  const q = query.trim().toLowerCase();
  const rows = useMemo(
    () => (modulesApi.modules || []).filter(m =>
      !q || m.name.toLowerCase().includes(q) || (m.description || '').toLowerCase().includes(q)
    ),
    [modulesApi.modules, q]
  );

  return (
    <div className="space-y-4 pb-24">
      <div>
        <h2 className="text-xl font-bold mb-1">Тумблеры модулей</h2>
        <p className="text-sm text-txm">
          Главный выключатель для каждого модуля. Тот же тумблер, что в карточке каталога
          и в верхнем «паспорте» модуля — три точки входа, одно состояние.
        </p>
      </div>

      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && setQuery('')}
        placeholder="Найти модуль…"
        className="w-full max-w-sm px-3 py-2 rounded-xl bg-sff border border-bd text-sm"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {rows.map(m => (
          <div key={m.id}
               className="bg-sff border border-bd rounded-2xl p-4 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="font-bold text-txd">{m.name}</div>
              <div className="text-sm text-txm truncate">{m.description}</div>
            </div>
            <ModuleToggle
              moduleId={m.id}
              moduleName={m.name}
              modulesApi={modulesApi}
            />
          </div>
        ))}
        {rows.length === 0 && (
          <div className="col-span-full text-center text-txm py-12">
            Ничего не найдено по запросу «{query}».{' '}
            <button onClick={() => setQuery('')} className="underline">сбросить</button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Коммит**

```
git add Admin_SITE/components/modules/ModulesTogglesTab.jsx
git commit -m "feat(V1.17.0h0l) [Site]: вкладка «Тумблеры модулей» — grid 2 колонки + поиск"
```

---

## Task 13 · Регистрация в `AdminDashboard` + удаление localStorage

**Files:**
- Modify: `Admin_SITE/AdminDashboard.jsx`

- [ ] **Step 1: Использовать `useModules` вместо локального state**

В `AdminDashboard.jsx` (район строк 985–1013, по памяти ModulesHub.connected) заменить:

```jsx
// УДАЛИТЬ блок:
// const [connectedModules, setConnectedModules] = useState(() => {...localStorage...});
// const _persistModules = (s) => localStorage.setItem('pulse_connected_modules', ...);
// const connectModule = ...
// const disconnectModule = ...
// const activeModuleNavs = new Set([...connectedModules].map(...));

// ВСТАВИТЬ:
import { useModules } from './hooks/useModules';
// ...
const modulesApi = useModules(activeWsId); // имя переменной WS взять из соседнего кода
const activeModuleNavs = useMemo(
  () => new Set(
    (modulesApi.modules || [])
      .filter(m => m.is_enabled)
      .map(m => MODULE_NAV[m.id])
      .filter(Boolean)
  ),
  [modulesApi.modules]
);
```

- [ ] **Step 2: Передать `modulesApi` в `ModulesHub`**

Найти место рендера `<ModulesHub …/>` и заменить:
```jsx
case 'modules':
  return <ModulesHub onOpen={navigateTo} modulesApi={modulesApi} />;
```

- [ ] **Step 3: Зарегистрировать вкладку «Тумблеры модулей»**

В массиве `navigation` (там, где `'system'`, `'permissions'` и т.п.) добавить:
```jsx
{ id: 'module_toggles', name: 'Тумблеры модулей', icon: ToggleRight, group: 'system' },
```

В `renderContent()` добавить case:
```jsx
case 'module_toggles':
  return <ModulesTogglesTab modulesApi={modulesApi} />;
```

Импорт: `import ModulesTogglesTab from './components/modules/ModulesTogglesTab';`
Импорт иконки: `ToggleRight` из `lucide-react`.

- [ ] **Step 4: Одноразовая чистка старого localStorage**

В корне `AdminDashboard` (внутри `useEffect(() => {...}, [])`) добавить:
```jsx
useEffect(() => {
  if (!localStorage.getItem('pulse_modules_migrated_v1')) {
    localStorage.removeItem('pulse_connected_modules');
    localStorage.setItem('pulse_modules_migrated_v1', '1');
  }
}, []);
```

- [ ] **Step 5: Локальная сборка**

```
node node_modules/vite/bin/vite.js build
```

- [ ] **Step 6: Smoke в браузере**

Открыть `Admin_SITE/dist/index.html` или dev-сервер, проверить:
1. В сайдбаре «Система» появилась вкладка «Тумблеры модулей».
2. В ней — grid 2 колонки.
3. Включение/выключение работает (для disable — открывается модалка причины).
4. В каталоге модулей поиск фильтрует карточки.

(Если backend не поднят локально — fetch упадёт; это ок, проверка только UI-рендера и наличия вкладки.)

- [ ] **Step 7: Коммит**

```
git add Admin_SITE/AdminDashboard.jsx Admin_SITE/dist
git commit -m "feat(V1.17.0h0m) [Site]: AdminDashboard — useModules + вкладка «Тумблеры» + чистка localStorage"
```

---

## Self-Review

Прошёлся по спеке секция-за-секцией:
- §3 архитектура → задачи 2 (БД), 3 (CRUD), 4 (guard), 5 (API), 6 (регистрация), 8–13 (UI).
- §4 БД → задача 2.
- §5 API → задача 5.
- §6 UI: useModules (8), ModuleToggle/DisableReasonModal (9), ModuleHeader (10), поиск+ModulesHub (11), вкладка 2 колонки (12), AdminDashboard+localStorage (13).
- §7 бот → задача 4.
- §8 план выката → этот документ.
- §9 тесты → разбросаны по задачам 2, 3, 4, 5, 7.
- §10 открытые вопросы → не реализуются на 7.0 (явно зафиксировано).
- §11 риски → backfill (7), кеш (4), localStorage (13).

Type consistency:
- `set_module_state(conn, ws, mid, is_enabled, reason, user_id)` — одна сигнатура везде.
- `VALID_MODULE_IDS` (set) — экспорт из `db_module_toggles`, импорт в `modules_routes`.
- `modulesApi` (объект `{modules, enable, disable, history, reload}`) — пропс везде одинаков.
- Имена эндпоинтов и порядок: GET list / POST enable / POST disable / GET history — совпадают между спекой, тестами и роутером.

Placeholder scan: нет TBD/TODO/"add appropriate". Все шаги с кодом — содержат код.

Без правок.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-20-module-toggles-7-0.md`. Two execution options:

**1. Subagent-Driven (recommended)** — я диспатчу свежий субагент на каждую задачу, ревьюю между, быстрая итерация.

**2. Inline Execution** — задачи в этой сессии через `executing-plans`, батч с чекпоинтами.

Which approach?
