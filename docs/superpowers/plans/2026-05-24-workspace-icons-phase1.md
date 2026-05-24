# Workspace Icons Phase 1 (auto из TG) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-05-24-workspace-icons-design.md`.
**Версия:** `V1.17.0j` · ветка `feat/V1.17.0j-workspace-icons`.
**Флаг:** `WORKSPACE_ICONS` (дефолт OFF). Бэкенд-часть `[backend]`, фронт-часть `[Site]`.

**Goal:** Бэкенд лениво тянет аватар main-чата из Telegram через `getChat` + `getFile`, кеширует на диск, отдаёт через защищённый эндпоинт `/api/workspaces/{ws}/icon.jpg`. Сайт показывает иконку поверх монограммы, при 404 / load-error — мягкий fallback на текущую монограмму.

**Architecture:** Всё за флагом `WORKSPACE_ICONS` (OFF = ни эндпоинт, ни поле `icon_url` в JSON, ни задача в боте; миграция аддитивна и безвредна при OFF). Прокси-эндпоинт обязателен — TG CDN URL содержит bot-токен, отдавать клиенту нельзя.

**Tech Stack:** Python 3, python-telegram-bot (PTB), FastAPI, sqlite3, pytest/pytest-asyncio. React 18 + Vite + Tailwind.

**Scope:** только фаза 1 (auto-from-TG). Фаза 2 (upload-override) — отдельной спекой + планом, когда будет запрос. Колонки задела (`icon_source`) включены уже сейчас, чтобы фаза 2 не требовала второй миграции.

---

## File Structure

- **Create** `bot_core/workspace_icons.py` — флаг-хелпер `workspace_icons_enabled()` (зеркало `bot_core/connect_flow.py`).
- **Modify** `database/db_migrations.py` — `+add_icon_columns_to_workspaces(db)` (идемпотентно, образец `add_removed_at_to_bot_chats`).
- **Modify** `database/db_manager.py` — вызвать миграцию рядом с уже встроенными.
- **Modify** `database/db_workspaces.py`
  - `get_workspaces_for_user` → добавить `icon_url` (под флагом, иначе None).
  - `get_workspace_details` → то же в `workspace.icon_url`.
  - +хелперы: `get_workspace_icon_meta(conn, ws_id)`, `set_workspace_icon(conn, ws_id, file_id, local_path)`, `clear_workspace_icon(conn, ws_id)`.
- **Create** `services/workspace_icon.py` — `pick_chat_for_icon`, `should_refresh`, `refresh_workspace_icon` (async).
- **Modify** `api/workspaces_routes.py` — `+GET /api/workspaces/{ws}/icon.jpg` (FileResponse, флаг-гейт).
- **Modify** `bot.py` (или scheduler-модуль, проверить при реализации) — регистрация ежедневной job-ы прогрева кеша.
- **Tests**
  - `tests/test_workspace_icon_migration.py` — миграция.
  - `tests/test_workspace_icon_service.py` — pick/should_refresh/refresh.
  - `tests/test_workspace_icon_route.py` — endpoint auth/флаг/200/404.
  - `tests/test_workspaces_api.py` — sanity `icon_url` в выдаче.
- **Create** `Admin_SITE/components/shared/useAuthImage.js` — fetch + blob hook.
- **Modify** `Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx`, `WorkspaceList.jsx`, `WorkspacePage.jsx` — `<img>` поверх монограммы с `onError` fallback.
- **NOT touched:** `bot_chats` (не меняем), legacy small-bot.

---

# PHASE J1 — Backend foundation (флаг + миграция + сервис)

### Task 1: Флаг-хелпер `WORKSPACE_ICONS`

**Files:**
- Create: `bot_core/workspace_icons.py`
- Test: `tests/test_workspace_icons.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workspace_icons.py
from bot_core.workspace_icons import workspace_icons_enabled


def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("WORKSPACE_ICONS", raising=False)
    assert workspace_icons_enabled() is False


def test_flag_on_truthy(monkeypatch):
    for v in ("1", "true", "YES", "on"):
        monkeypatch.setenv("WORKSPACE_ICONS", v)
        assert workspace_icons_enabled() is True


def test_flag_off_falsy(monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS", "0")
    assert workspace_icons_enabled() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_workspace_icons.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# bot_core/workspace_icons.py
"""V1.17.0j: флаг workspace-icons (зеркало bot_core/connect_flow.py)."""
import os

_TRUTHY = {"1", "true", "yes", "on"}


def workspace_icons_enabled() -> bool:
    return os.getenv("WORKSPACE_ICONS", "").strip().lower() in _TRUTHY


def cache_dir() -> str:
    """Путь к директории кеша. На проде дефолт /var/cache/pulsbot/ws_icons,
    локально — ./.cache/ws_icons."""
    default = "/var/cache/pulsbot/ws_icons" if os.name != "nt" else ".cache\\ws_icons"
    return os.getenv("WORKSPACE_ICONS_CACHE_DIR", default)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_workspace_icons.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add bot_core/workspace_icons.py tests/test_workspace_icons.py
git commit -m "feat(V1.17.0j1): flag-helper WORKSPACE_ICONS + cache_dir (default OFF)"
```

---

### Task 2: Идемпотентная миграция `workspaces` — 4 колонки

**Files:**
- Modify: `database/db_migrations.py`
- Modify: `database/db_manager.py`
- Test: `tests/test_workspace_icon_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workspace_icon_migration.py
import sqlite3
from database.db_migrations import add_icon_columns_to_workspaces


class _DB:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()


def _cols(conn):
    return {r[1] for r in conn.execute("PRAGMA table_info(workspaces)").fetchall()}


def test_adds_4_columns_when_missing():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT)")
    db = _DB(conn)
    add_icon_columns_to_workspaces(db)
    cols = _cols(conn)
    for c in ("icon_file_id", "icon_cached_at", "icon_source", "icon_local_path"):
        assert c in cols


def test_idempotent_when_already_present():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT, "
        "icon_file_id TEXT, icon_cached_at TIMESTAMP, "
        "icon_source TEXT, icon_local_path TEXT)"
    )
    db = _DB(conn)
    add_icon_columns_to_workspaces(db)  # no-op, no raise
    add_icon_columns_to_workspaces(db)  # повторный вызов тоже ок
    assert "icon_file_id" in _cols(conn)


def test_no_workspaces_table_is_safe():
    conn = sqlite3.connect(":memory:")
    add_icon_columns_to_workspaces(_DB(conn))  # без таблицы — лог + return
```

- [ ] **Step 2: Run test to verify it fails**

Expected: ImportError.

- [ ] **Step 3: Write minimal implementation**

Append to `database/db_migrations.py`:

```python
def add_icon_columns_to_workspaces(db):
    """V1.17.0j: добавить колонки иконок в workspaces. Идемпотентно."""
    try:
        db.cursor.execute("PRAGMA table_info(workspaces)")
        cols = [row[1] for row in db.cursor.fetchall()]
        if not cols:
            logging.info("workspaces table absent, skip icon migration")
            return
        adds = [
            ('icon_file_id',    'TEXT'),
            ('icon_cached_at',  'TIMESTAMP'),
            ('icon_source',     "TEXT DEFAULT 'tg'"),
            ('icon_local_path', 'TEXT'),
        ]
        for col, decl in adds:
            if col not in cols:
                db.cursor.execute(f"ALTER TABLE workspaces ADD COLUMN {col} {decl}")
        db.conn.commit()
        logging.info("✅ workspaces icon columns ensured")
    except Exception as e:
        logging.error(f"add_icon_columns_to_workspaces error: {e}")
        db.conn.rollback()
```

В `database/db_manager.py` рядом с `_add_removed_at_to_bot_chats(self)`:

```python
from database.db_migrations import (
    add_icon_columns_to_workspaces as _add_icon_columns_to_workspaces,
)
# ...
_add_icon_columns_to_workspaces(self)
```

- [ ] **Step 4: Run test to verify it passes** → 3 passed.
- [ ] **Step 5: Commit**

```bash
git add database/db_migrations.py database/db_manager.py tests/test_workspace_icon_migration.py
git commit -m "feat(V1.17.0j2): workspaces icon columns migration (idempotent)"
```

---

### Task 3: Сервис `services/workspace_icon.py`

**Files:**
- Create: `services/workspace_icon.py`
- Modify: `database/db_workspaces.py` (+ icon helpers)
- Test: `tests/test_workspace_icon_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workspace_icon_service.py
import os, sqlite3, asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from services.workspace_icon import (
    pick_chat_for_icon, should_refresh, refresh_workspace_icon,
)


def _conn():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT, "
              "icon_file_id TEXT, icon_cached_at TIMESTAMP, "
              "icon_source TEXT DEFAULT 'tg', icon_local_path TEXT)")
    c.execute("CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, "
              "workspace_id INTEGER, role TEXT, removed_at TIMESTAMP)")
    c.execute("INSERT INTO workspaces (id,name) VALUES (1,'WS')")
    c.commit()
    return c


def test_pick_chat_prefers_main_then_admin_then_journal():
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-3,1,'journal',NULL)")
    c.execute("INSERT INTO bot_chats VALUES (-2,1,'admin',NULL)")
    c.execute("INSERT INTO bot_chats VALUES (-1,1,'main',NULL)")
    c.commit()
    assert pick_chat_for_icon(c, 1) == -1


def test_pick_chat_skips_removed():
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-1,1,'main',CURRENT_TIMESTAMP)")
    c.execute("INSERT INTO bot_chats VALUES (-2,1,'admin',NULL)")
    c.commit()
    assert pick_chat_for_icon(c, 1) == -2


def test_pick_chat_empty_returns_none():
    c = _conn()
    assert pick_chat_for_icon(c, 1) is None


def test_should_refresh_null_cached_at():
    assert should_refresh({'icon_cached_at': None}) is True


def test_should_refresh_within_ttl():
    from datetime import datetime, timedelta
    recent = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    assert should_refresh({'icon_cached_at': recent}, ttl_s=86400) is False


def test_should_refresh_stale():
    from datetime import datetime, timedelta
    old = (datetime.utcnow() - timedelta(days=30)).isoformat()
    assert should_refresh({'icon_cached_at': old}, ttl_s=86400) is True


@pytest.mark.asyncio
async def test_refresh_no_photo_writes_null_path(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-1,1,'main',NULL)")
    c.commit()
    bot = MagicMock()
    chat = MagicMock(); chat.photo = None
    bot.get_chat = AsyncMock(return_value=chat)
    result = await refresh_workspace_icon(bot, c, 1)
    assert result is None
    row = c.execute("SELECT icon_local_path,icon_cached_at FROM workspaces WHERE id=1").fetchone()
    assert row[0] is None and row[1] is not None


@pytest.mark.asyncio
async def test_refresh_downloads_and_saves(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    c = _conn()
    c.execute("INSERT INTO bot_chats VALUES (-1,1,'main',NULL)")
    c.commit()
    bot = MagicMock()
    chat = MagicMock()
    chat.photo = MagicMock()
    chat.photo.small_file_id = "abc"
    bot.get_chat = AsyncMock(return_value=chat)
    file_obj = MagicMock()
    file_obj.download_to_drive = AsyncMock()
    bot.get_file = AsyncMock(return_value=file_obj)
    result = await refresh_workspace_icon(bot, c, 1)
    assert result is not None
    row = c.execute(
        "SELECT icon_file_id,icon_local_path FROM workspaces WHERE id=1"
    ).fetchone()
    assert row[0] == "abc" and row[1] is not None
    bot.get_chat.assert_awaited_once_with(-1)
    bot.get_file.assert_awaited_once_with("abc")
```

- [ ] **Step 2: Run test to verify it fails** → ModuleNotFoundError.

- [ ] **Step 3: Write minimal implementation**

```python
# services/workspace_icon.py
"""V1.17.0j: auto-иконка workspace из main-чата Telegram.

Кеширует small_file_id chat photo на диск, БД-метаданные. Все ошибки TG
ловятся локально — фронт всегда корректен (fallback на монограмму).
"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from bot_core.workspace_icons import cache_dir

logger = logging.getLogger(__name__)
_DEFAULT_TTL_S = 7 * 24 * 60 * 60  # 7 дней


def pick_chat_for_icon(conn, ws_id: int) -> Optional[int]:
    """main > admin > journal > любой не-removed > None."""
    row = conn.execute('''
        SELECT chat_id FROM bot_chats
        WHERE workspace_id=? AND removed_at IS NULL
        ORDER BY CASE role
            WHEN 'main' THEN 0
            WHEN 'admin' THEN 1
            WHEN 'journal' THEN 2
            ELSE 3 END,
          added_at ASC
        LIMIT 1
    ''', (ws_id,)).fetchone()
    return row[0] if row else None


def should_refresh(meta: dict, ttl_s: int = _DEFAULT_TTL_S) -> bool:
    cached_at = meta.get('icon_cached_at')
    if not cached_at:
        return True
    try:
        ts = datetime.fromisoformat(cached_at.replace('Z', ''))
    except (ValueError, AttributeError):
        return True
    return datetime.utcnow() - ts > timedelta(seconds=ttl_s)


def _ensure_cache_dir() -> Path:
    p = Path(cache_dir())
    p.mkdir(parents=True, exist_ok=True)
    return p


async def refresh_workspace_icon(bot, conn, ws_id: int) -> Optional[str]:
    """Подтянуть иконку main-чата ws_id из Telegram. Возвращает local_path
    или None если фото нет/ошибка. ВСЕГДА обновляет icon_cached_at."""
    chat_id = pick_chat_for_icon(conn, ws_id)
    if chat_id is None:
        conn.execute(
            "UPDATE workspaces SET icon_cached_at=CURRENT_TIMESTAMP, "
            "icon_local_path=NULL WHERE id=?", (ws_id,))
        conn.commit()
        return None
    try:
        chat = await bot.get_chat(chat_id)
        photo = getattr(chat, 'photo', None)
        if not photo or not getattr(photo, 'small_file_id', None):
            conn.execute(
                "UPDATE workspaces SET icon_cached_at=CURRENT_TIMESTAMP, "
                "icon_local_path=NULL, icon_file_id=NULL WHERE id=?", (ws_id,))
            conn.commit()
            return None
        file_id = photo.small_file_id
        cache = _ensure_cache_dir()
        tmp = cache / f"{ws_id}.jpg.tmp"
        final = cache / f"{ws_id}.jpg"
        f = await bot.get_file(file_id)
        await f.download_to_drive(str(tmp))
        os.replace(str(tmp), str(final))
        conn.execute(
            "UPDATE workspaces SET icon_file_id=?, icon_local_path=?, "
            "icon_cached_at=CURRENT_TIMESTAMP, icon_source='tg' WHERE id=?",
            (file_id, str(final), ws_id))
        conn.commit()
        return str(final)
    except Exception as e:
        logger.warning(f"refresh_workspace_icon ws={ws_id}: {e}")
        # cached_at не обновляем — попробуем снова при следующем запросе
        return None
```

- [ ] **Step 4: Run test to verify it passes** → 8 passed.

- [ ] **Step 5: Commit**

```bash
git add services/workspace_icon.py tests/test_workspace_icon_service.py
git commit -m "feat(V1.17.0j3): сервис workspace_icon — pick/should_refresh/refresh (TDD)"
```

---

### Task 4: API endpoint `GET /api/workspaces/{ws}/icon.jpg`

**Files:**
- Modify: `api/workspaces_routes.py`
- Test: `tests/test_workspace_icon_route.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workspace_icon_route.py
import sqlite3, os
import pytest
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from database.migrations.multi_tenancy import up_create_workspaces_tables
from database.db_workspaces import create_workspace, add_member


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS", "1")
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    up_create_workspaces_tables(conn)
    conn.execute("ALTER TABLE workspaces ADD COLUMN icon_file_id TEXT")
    conn.execute("ALTER TABLE workspaces ADD COLUMN icon_cached_at TIMESTAMP")
    conn.execute("ALTER TABLE workspaces ADD COLUMN icon_source TEXT DEFAULT 'tg'")
    conn.execute("ALTER TABLE workspaces ADD COLUMN icon_local_path TEXT")
    conn.execute('''CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY,
        workspace_id INTEGER, role TEXT, removed_at TIMESTAMP)''')
    ws = create_workspace(conn, 'W', owner_user_id=42)
    conn.commit()

    from api.workspaces_routes import router, _setup

    class _DB:
        def __init__(self, c): self.conn=c; self.cursor=c.cursor()
        def get_site_user(self, uid): return {'user_id': uid}

    def fake_auth(authorization):
        if not authorization: raise HTTPException(401)
        return {'user_id': int(authorization.replace('Bearer fake-', ''))}

    _setup(_DB(conn), fake_auth)
    app = FastAPI(); app.include_router(router)
    return TestClient(app), conn, ws, tmp_path


def test_icon_404_when_no_cached_file(client):
    c, conn, ws, _ = client
    r = c.get(f'/api/workspaces/{ws}/icon.jpg',
              headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 404


def test_icon_200_when_cached_file_exists(client):
    c, conn, ws, tmp = client
    p = Path(tmp) / f"{ws}.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0FAKEJPEG")
    conn.execute("UPDATE workspaces SET icon_local_path=?, icon_cached_at=CURRENT_TIMESTAMP WHERE id=?",
                 (str(p), ws))
    conn.commit()
    r = c.get(f'/api/workspaces/{ws}/icon.jpg',
              headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('image/')


def test_icon_401_no_auth(client):
    c, _, ws, _ = client
    assert c.get(f'/api/workspaces/{ws}/icon.jpg').status_code == 401


def test_icon_404_non_member(client):
    c, _, ws, _ = client
    r = c.get(f'/api/workspaces/{ws}/icon.jpg',
              headers={'Authorization': 'Bearer fake-999'})
    assert r.status_code == 404


def test_icon_404_when_flag_off(client, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS", "0")
    c, conn, ws, tmp = client
    p = Path(tmp) / f"{ws}.jpg"
    p.write_bytes(b"\xff\xd8FAKE")
    conn.execute("UPDATE workspaces SET icon_local_path=? WHERE id=?", (str(p), ws))
    conn.commit()
    r = c.get(f'/api/workspaces/{ws}/icon.jpg',
              headers={'Authorization': 'Bearer fake-42'})
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails** → endpoint not yet.

- [ ] **Step 3: Write minimal implementation** в `api/workspaces_routes.py`:

```python
from fastapi.responses import FileResponse
from bot_core.workspace_icons import workspace_icons_enabled
# ...

@router.get("/{ws_id}/icon.jpg")
async def workspace_icon(ws_id: int, authorization: str = Header(default=None)):
    payload = _auth(authorization)
    user_id = int(payload['user_id'])
    _check_role(ws_id, user_id, 'moderator')
    if not workspace_icons_enabled():
        raise HTTPException(status_code=404, detail="icons disabled")
    row = _db.conn.execute(
        "SELECT icon_local_path FROM workspaces WHERE id=?", (ws_id,)
    ).fetchone()
    if not row or not row[0] or not os.path.exists(row[0]):
        raise HTTPException(status_code=404, detail="no icon")
    return FileResponse(
        row[0], media_type='image/jpeg',
        headers={'Cache-Control': 'private, max-age=300'},
    )
```

- [ ] **Step 4: Run test to verify it passes** → 5 passed.

- [ ] **Step 5: Commit**

```bash
git add api/workspaces_routes.py tests/test_workspace_icon_route.py
git commit -m "feat(V1.17.0j4): endpoint /api/workspaces/{id}/icon.jpg (auth + flag-gated)"
```

---

### Task 5: API list/details — `icon_url`

**Files:**
- Modify: `database/db_workspaces.py`
- Test: `tests/test_workspaces_api.py` (дополнить)

- [ ] **Step 1: Write the failing test** (append к существующему файлу)

```python
def test_list_workspaces_exposes_icon_url_when_cached(client, monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ICONS", "1")
    monkeypatch.setenv("WORKSPACE_ICONS_CACHE_DIR", str(tmp_path))
    from api import workspaces_routes
    workspaces_routes._db.conn.execute(
        "ALTER TABLE workspaces ADD COLUMN icon_file_id TEXT"
    )
    workspaces_routes._db.conn.execute(
        "ALTER TABLE workspaces ADD COLUMN icon_cached_at TIMESTAMP"
    )
    workspaces_routes._db.conn.execute(
        "ALTER TABLE workspaces ADD COLUMN icon_source TEXT DEFAULT 'tg'"
    )
    workspaces_routes._db.conn.execute(
        "ALTER TABLE workspaces ADD COLUMN icon_local_path TEXT"
    )
    workspaces_routes._db.conn.execute(
        "UPDATE workspaces SET icon_local_path='/tmp/x.jpg' WHERE id=1"
    )
    workspaces_routes._db.conn.commit()
    r = client.get('/api/workspaces', headers={'Authorization': 'Bearer fake-42'})
    sample = r.json()['workspaces'][0]
    assert sample.get('icon_url') == '/api/workspaces/1/icon.jpg'


def test_list_workspaces_icon_url_null_when_no_path(client, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ICONS", "1")
    r = client.get('/api/workspaces', headers={'Authorization': 'Bearer fake-42'})
    sample = r.json()['workspaces'][0]
    # на конкретном workspace icon_local_path не задан → null
    assert sample.get('icon_url') is None
```

- [ ] **Step 2: Run test to verify it fails**.

- [ ] **Step 3: Write minimal implementation** в `get_workspaces_for_user` и `get_workspace_details`:

```python
from bot_core.workspace_icons import workspace_icons_enabled
# ...

# В get_workspaces_for_user после составления rows и has_removed:
icons_on = workspace_icons_enabled() and _workspaces_has_icon_columns(conn)
# в цикле rows:
d['icon_url'] = (f"/api/workspaces/{d['id']}/icon.jpg"
                 if icons_on and _has_icon_local_path(conn, d['id']) else None)
```

Хелперы:
```python
def _workspaces_has_icon_columns(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(workspaces)").fetchall()]
    return 'icon_local_path' in cols


def _has_icon_local_path(conn, ws_id: int) -> bool:
    row = conn.execute(
        "SELECT icon_local_path FROM workspaces WHERE id=?", (ws_id,)
    ).fetchone()
    return bool(row and row[0])
```

Аналогично в `get_workspace_details` для `workspace.icon_url`.

- [ ] **Step 4: Run test to verify it passes**.

- [ ] **Step 5: Commit**

```bash
git add database/db_workspaces.py tests/test_workspaces_api.py
git commit -m "feat(V1.17.0j5): API list/details — icon_url под флагом"
```

---

### Task 6: P1 регресс

- [ ] Run: `.venv\Scripts\python.exe -m pytest tests/ -q --no-header` → all green.
- [ ] Commit fixes if any.

---

# PHASE J2 — Бот: ежедневный прогрев кеша

### Task 7: Background job в боте

**Files:**
- Modify: `bot.py` (или scheduler-модуль если есть — проверить при реализации)
- Test: `tests/test_workspace_icon_service.py` (extend)

- [ ] **Step 1: Найти существующий планировщик** в `bot.py` (grep на `JobQueue`/`add_daily`). Если есть — добавить job; если нет — создать минимальный через `app.job_queue.run_repeating(..., interval=86400)`.

- [ ] **Step 2: Тест-обёртка** `prewarm_all_workspaces(bot, conn)`:
  - проходит все workspaces;
  - для `should_refresh(...)` → `await refresh_workspace_icon(...)`;
  - не падает на ошибке отдельного ws.

- [ ] **Step 3: Зарегистрировать** в `bot.py` при старте — только если `workspace_icons_enabled()`.

- [ ] **Step 4: Commit**

```bash
git add bot.py services/workspace_icon.py tests/test_workspace_icon_service.py
git commit -m "feat(V1.17.0j7): ежедневный прогрев кеша иконок workspaces (бот job)"
```

---

# PHASE J3 — Сайт `[Site]`

### Task 8: `useAuthImage` hook

**Files:**
- Create: `Admin_SITE/components/shared/useAuthImage.js`

```javascript
// Admin_SITE/components/shared/useAuthImage.js
// V1.17.0j: загрузка картинки с Bearer-auth, возвращает blob: URL.
// Используется для /api/workspaces/{id}/icon.jpg.
import { useEffect, useState } from 'react';

export function useAuthImage(url, token) {
  const [blob, setBlob] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!url || !token) {
      setBlob(null);
      setFailed(false);
      return;
    }
    let cancelled = false;
    let objectUrl = null;
    setFailed(false);
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.blob();
      })
      .then((b) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(b);
        setBlob(objectUrl);
      })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, token]);

  return { src: blob, failed };
}
```

- [ ] **Commit:** `feat(V1.17.0j8) [Site]: useAuthImage hook (fetch + blob)`

---

### Task 9: Интеграция в WorkspaceSwitcher / List / Page

**Files:**
- Modify: `Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx`
- Modify: `Admin_SITE/components/workspaces/WorkspaceList.jsx`
- Modify: `Admin_SITE/components/workspaces/WorkspacePage.jsx`

В каждом компоненте, где сейчас рендерится монограмма-тайл:

```jsx
const { src: iconSrc, failed } = useAuthImage(ws.icon_url, token);
// ...
<div className={`w-9 h-9 rounded-xl ... relative overflow-hidden ${tile}`}>
  {iconSrc && !failed && (
    <img src={iconSrc}
         className="absolute inset-0 w-full h-full object-cover"
         onError={() => {/* ignore — failed уже сработает */}}
         alt={ws.name}/>
  )}
  {(!iconSrc || failed) && <span>{mono}</span>}
</div>
```

- [ ] Прокинуть `token` пропом туда, где его ещё нет (`WorkspaceList`, `WorkspacePage`).
- [ ] Visual smoke через `Admin_SITE/preview.html`.

- [ ] **Commit:** `feat(V1.17.0j9) [Site]: иконки сообществ в Switcher/List/Page (auth-img + fallback)`

---

### Task 10: Локальный билд + dist commit

- [ ] Run: `cd Admin_SITE && node node_modules/vite/bin/vite.js build`.
- [ ] Sanity открыть `dist/index.html`.
- [ ] **Commit:** `chore [Site]: пересборка dist под V1.17.0j (иконки сообществ)`

---

### Task 11: Финальный regress + spec-sweep

- [ ] `.venv\Scripts\python.exe -m pytest tests/ -q --no-header` → green.
- [ ] Сверка с spec §4: D1✓T2 D2✓T1 D3✓T3 D4✓T4 D5✓T5 D6✓T7 D7✓T9. **Out-of-scope:** фаза 2 (upload-override).
- [ ] Commit fixes if any.

---

## Activation (ГЕЙТ с Ильёй)

1. merge `feat/V1.17.0j-workspace-icons` → `main` → авто-деплой (флаг OFF = байт-в-байт; миграция аддитивна).
2. На проде: `mkdir -p /var/cache/pulsbot/ws_icons && chmod 755 /var/cache/pulsbot/ws_icons`.
3. `/root/PulsBot/.env`: добавить `WORKSPACE_ICONS=1` (+ опционально `WORKSPACE_ICONS_CACHE_DIR`).
4. `systemctl restart pulsbot pulsapi`.
5. Подождать первый прогон job-ы (или дёрнуть вручную одну ws через python-shell) → проверить файл в кеше.
6. Открыть сайт → видны иконки main-чатов; смена фото в TG → через 7 дней (или ручной refresh) сменится на сайте.
7. **Сайт-деплой** — отдельный шаг, без него фронт всё равно красив (монограммы как сейчас).

Откат: убрать флаг + рестарт; `rm -rf /var/cache/pulsbot/ws_icons` если нужно; БД-колонки безвредны при OFF.

---

## Out of scope (явно)

- **Фаза 2 — upload-override.** POST endpoint, валидация, Pillow-ресайз — отдельная спека.
- `big_file_id` (большой формат) — пока хватает small.
- Иконки для каждой роли чата отдельно — нет UX-нужды.
- Биллинг лимита размера/количества override — в #4 Modules.

Связано: spec `2026-05-24-workspace-icons-design.md` (этот план — её реализация фазы 1), spec `2026-05-17-connect-flow-lifecycle-design.md` §8, memory [[server_structure]] [[feedback_site_workflow]] [[build_npx_node_dir_trap]].
