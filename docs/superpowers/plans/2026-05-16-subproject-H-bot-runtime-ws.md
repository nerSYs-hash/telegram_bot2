# Subproject H — Bot Runtime per-Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Бот в Телеграме перестаёт быть Pulse-хардкодом: chat_id/thread_id/роли резолвятся per-workspace из БД, а не из `config.py`/`.env`. Второй владелец может управлять ботом в СВОЁМ сообществе (сейчас ловит «ты заблокирован в Pulse 4ever»).

**Architecture:** Поверх готового `bot_core/workspace_context.build_context(conn, chat_id, user_id)` (резолвит ws по chat_id, есть из #1/#2) добавляем **аддитивные резолверы** `resolve_role_chat(conn, ws, role)` и `resolve_thread(conn, ws, kind)`, читающие `bot_chats.role` (F) и `bot_chat_topics` (есть). Миграция сидит Pulse ws=1 текущими `.env`-значениями. Затем — поэтапная замена `config.CHAT_ID/ADMIN_CHAT_ID/*_THREAD_ID` и Pulse-гейта на резолверы, за feature-flag, Pulse-safe. **Strangler, не переписывание.**

**Tech Stack:** python-telegram-bot, sqlite3 (`database/bot_database.db`), pytest.

**Риск:** ломает ЖИВОЙ прод (Pulse = Илья). Строго TDD, бэкап БД перед миграцией, НЕ авто-деплой на прод. Фазы H3+ (перепроводка живых хендлеров) — только при Илье, стейджем.

---

## Контекст-аудит (зафиксировано 16.05)

- `config.py`: модульные константы из env с Pulse-дефолтами — `OWNER_ID` (7536752126), `CHAT_ID`, `ADMIN_CHAT_ID`, `DOSSIER_THREAD_ID`(176), `APPLICATIONS_THREAD_ID`(241), `BUG_THREAD_BOT`(12195), `BUG_THREAD_SITE`(14235), `JOURNAL_CHANNEL_ID`. **34 файла** импортируют эти константы.
- Готово к переиспользованию: `bot_core/workspace_context.py` (`resolve_workspace_for_chat`, `build_context`, `pulse_only`, кеш + `invalidate_cache`); middleware в `bot.py` кладёт `ws_ctx` в `context.user_data/chat_data`.
- `bot_chats(chat_id, workspace_id, role, ...)` — `role ∈ main|admin|journal|NULL` (из F, V1.17.0c).
- `bot_chat_topics(workspace_id, chat_id, thread_id, name, source)` + `get_bot_chats`/`upsert_bot_chat_topic` — в `database/db_press_release.py`.
- Живой инцидент: `handlers/message_handler.py` — блок-лист (стр.~321), Pulse-сообщение «Доступ открывается…» (стр.~816), `ADMIN_CHAT_ID` хардкод (стр.~195); те же гейты в `handlers/registration_conversation.py`, `handlers/command_handler.py`. Гейтят по Pulse-чату, не по сообществу юзера → 2-й владелец заблокирован.

## Фазы

| Фаза | Что | Риск | Когда |
|---|---|---|---|
| **H1** | Аддитивные резолверы `resolve_role_chat`/`resolve_thread` + тесты. НИЧЕГО не меняет в поведении бота. | 🟢 нулевой | автономно сейчас |
| **H2** | Миграция-сидер: Pulse ws=1 ← текущие `.env` в `bot_chats.role` + `bot_chat_topics`. Идемпотентна, бэкап. | 🟢 (только пишет данные для ws=1) | автономно сейчас |
| **H3** | Pulse-гейт (блок-лист/онбординг/меню) → по `build_context().workspace_id`, не по `config.CHAT_ID`. Feature-flag. | 🔴 живой прод | С ИЛЬЁЙ, стейдж |
| **H4** | Замена `config.*_THREAD_ID`/`ADMIN_CHAT_ID` на `resolve_thread`/`resolve_role_chat` в хендлерах (по группам). | 🔴 живой прод | С ИЛЬЁЙ, стейдж |
| **H5** | UI «Топики» (сайт) + удаление `.env`-веток. | 🟡 | после H3-H4 |

> Автономный объём этой сессии: **H1 + H2** (безопасное, аддитивное, полностью под тестами). H3+ требуют Илью (как деплой #3).

---

### Task 1 (H1): Резолверы `resolve_role_chat` / `resolve_thread`

**Files:**
- Create: `bot_core/ws_resolver.py`
- Test: `tests/test_ws_resolver.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_ws_resolver.py
import sqlite3
import pytest
from bot_core.ws_resolver import resolve_role_chat, resolve_thread, invalidate_resolver_cache


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.executescript('''
        CREATE TABLE bot_chats (
            chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
            role TEXT
        );
        CREATE TABLE bot_chat_topics (
            workspace_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            thread_id INTEGER NOT NULL, name TEXT, source TEXT,
            kind TEXT
        );
    ''')
    c.execute("INSERT INTO bot_chats VALUES (-100, 1, 'main')")
    c.execute("INSERT INTO bot_chats VALUES (-200, 1, 'admin')")
    c.execute("INSERT INTO bot_chats VALUES (-300, 2, 'main')")
    c.execute("INSERT INTO bot_chat_topics VALUES (1, -200, 241, 'Заявки', 'manual', 'applications')")
    c.commit()
    yield c
    c.close()
    invalidate_resolver_cache()


def test_resolve_main_chat(conn):
    assert resolve_role_chat(conn, 1, 'main') == -100

def test_resolve_admin_chat(conn):
    assert resolve_role_chat(conn, 1, 'admin') == -200

def test_resolve_role_chat_other_ws(conn):
    assert resolve_role_chat(conn, 2, 'main') == -300

def test_resolve_role_chat_missing_returns_none(conn):
    assert resolve_role_chat(conn, 1, 'journal') is None

def test_resolve_thread_by_kind(conn):
    assert resolve_thread(conn, 1, 'applications') == 241

def test_resolve_thread_missing_returns_none(conn):
    assert resolve_thread(conn, 1, 'dossier') is None

def test_resolve_thread_other_ws_isolated(conn):
    assert resolve_thread(conn, 2, 'applications') is None
```

- [ ] **Step 2: Run, expect fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ws_resolver.py -q`
Expected: `ModuleNotFoundError: No module named 'bot_core.ws_resolver'`

- [ ] **Step 3: Implement**

```python
# bot_core/ws_resolver.py
"""Per-workspace резолверы chat_id/thread_id (Подпроект H).

Аддитивно поверх bot_chats.role (F) и bot_chat_topics. НЕ меняет
поведение существующих хендлеров — их перепроводка в фазах H3/H4.
"""
import sqlite3
from typing import Optional

_role_chat_cache: dict[tuple[int, str], Optional[int]] = {}
_thread_cache: dict[tuple[int, str], Optional[int]] = {}


def resolve_role_chat(
    conn: sqlite3.Connection, workspace_id: int, role: str
) -> Optional[int]:
    """chat_id чата с ролью role (main|admin|journal) в workspace.
    None если в этом ws нет чата с такой ролью."""
    key = (workspace_id, role)
    if key in _role_chat_cache:
        return _role_chat_cache[key]
    row = conn.execute(
        "SELECT chat_id FROM bot_chats WHERE workspace_id=? AND role=? LIMIT 1",
        (workspace_id, role),
    ).fetchone()
    val = row[0] if row else None
    _role_chat_cache[key] = val
    return val


def resolve_thread(
    conn: sqlite3.Connection, workspace_id: int, kind: str
) -> Optional[int]:
    """thread_id топика вида kind (applications|dossier|bug_bot|bug_site|bbs)
    в workspace. Источник — bot_chat_topics.kind. None если не настроен."""
    key = (workspace_id, kind)
    if key in _thread_cache:
        return _thread_cache[key]
    row = conn.execute(
        "SELECT thread_id FROM bot_chat_topics "
        "WHERE workspace_id=? AND kind=? LIMIT 1",
        (workspace_id, kind),
    ).fetchone()
    val = row[0] if row else None
    _thread_cache[key] = val
    return val


def invalidate_resolver_cache() -> None:
    """Сброс кешей (вызывать при смене ролей чатов / топиков с сайта)."""
    _role_chat_cache.clear()
    _thread_cache.clear()
```

- [ ] **Step 4: Run, expect pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ws_resolver.py -q`
Expected: 7 passed

- [ ] **Step 5: Commit**

```
git add bot_core/ws_resolver.py tests/test_ws_resolver.py
git commit -m "feat(V1.17.0e1): ws_resolver - resolve_role_chat/resolve_thread (additivno, povedenie bota ne menyaetsya)"
```

---

### Task 2 (H2): `bot_chat_topics.kind` колонка + миграция-сидер Pulse ws=1

**Files:**
- Create: `database/migrations/ws_runtime_seed.py`
- Test: `tests/test_ws_runtime_seed.py`

**Зачем:** `resolve_thread` читает `bot_chat_topics.kind`, но колонки `kind` ещё нет, и Pulse-топики там не засеяны. Миграция: (1) `ALTER TABLE bot_chat_topics ADD COLUMN kind TEXT` (идемпотентно), (2) для ws=1 проставляет `bot_chats.role='main'/'admin'` если ещё NULL и сидит `bot_chat_topics` строки kind=applications/dossier/bug_bot/bug_site из текущих `config.*`. Только ws=1, идемпотентно, бэкап БД делает вызывающий (RUNBOOK).

- [ ] **Step 1: Failing test**

```python
# tests/test_ws_runtime_seed.py
import sqlite3
import pytest
from database.migrations.ws_runtime_seed import up_add_kind_column, seed_pulse_ws1


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.executescript('''
        CREATE TABLE bot_chats (
            chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, role TEXT
        );
        CREATE TABLE bot_chat_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            thread_id INTEGER NOT NULL, name TEXT, source TEXT,
            UNIQUE(chat_id, thread_id)
        );
    ''')
    c.execute("INSERT INTO bot_chats VALUES (-100, 1, NULL)")
    c.commit()
    yield c
    c.close()


def test_add_kind_column_idempotent(conn):
    up_add_kind_column(conn)
    up_add_kind_column(conn)  # второй раз не падает
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chat_topics)")]
    assert 'kind' in cols


def test_seed_pulse_sets_main_role(conn):
    up_add_kind_column(conn)
    seed_pulse_ws1(conn, main_chat_id=-100, admin_chat_id=-100,
                   threads={'applications': 241, 'dossier': 176})
    role = conn.execute("SELECT role FROM bot_chats WHERE chat_id=-100").fetchone()[0]
    assert role == 'main'


def test_seed_pulse_inserts_threads(conn):
    up_add_kind_column(conn)
    seed_pulse_ws1(conn, main_chat_id=-100, admin_chat_id=-100,
                   threads={'applications': 241, 'dossier': 176})
    rows = dict(conn.execute(
        "SELECT kind, thread_id FROM bot_chat_topics WHERE workspace_id=1"
    ).fetchall())
    assert rows == {'applications': 241, 'dossier': 176}


def test_seed_idempotent(conn):
    up_add_kind_column(conn)
    seed_pulse_ws1(conn, main_chat_id=-100, admin_chat_id=-100,
                   threads={'applications': 241})
    seed_pulse_ws1(conn, main_chat_id=-100, admin_chat_id=-100,
                   threads={'applications': 241})
    n = conn.execute(
        "SELECT COUNT(*) FROM bot_chat_topics WHERE workspace_id=1 AND kind='applications'"
    ).fetchone()[0]
    assert n == 1
```

- [ ] **Step 2: Run, expect fail** — `ModuleNotFoundError: database.migrations.ws_runtime_seed`

- [ ] **Step 3: Implement**

```python
# database/migrations/ws_runtime_seed.py
"""H2: kind-колонка + сидер Pulse ws=1 из текущих .env-значений.

Идемпотентно. Только ws=1. Бэкап БД делает RUNBOOK перед запуском.
"""
import sqlite3


def up_add_kind_column(conn: sqlite3.Connection) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chat_topics)")]
    if 'kind' not in cols:
        conn.execute("ALTER TABLE bot_chat_topics ADD COLUMN kind TEXT")
    conn.commit()


def seed_pulse_ws1(
    conn: sqlite3.Connection,
    main_chat_id: int,
    admin_chat_id: int,
    threads: dict,
) -> None:
    """Проставляет роли чатов ws=1 (если NULL) и сидит kind-топики.
    threads: {'applications': 241, 'dossier': 176, 'bug_bot': ..., ...}."""
    cur = conn.execute(
        "SELECT role FROM bot_chats WHERE chat_id=? AND workspace_id=1",
        (main_chat_id,),
    ).fetchone()
    if cur is not None and (cur[0] is None or cur[0] == ''):
        conn.execute(
            "UPDATE bot_chats SET role='main' WHERE chat_id=? AND workspace_id=1",
            (main_chat_id,),
        )
    a_cur = conn.execute(
        "SELECT role FROM bot_chats WHERE chat_id=? AND workspace_id=1",
        (admin_chat_id,),
    ).fetchone()
    if a_cur is not None and (a_cur[0] is None or a_cur[0] == '') and admin_chat_id != main_chat_id:
        conn.execute(
            "UPDATE bot_chats SET role='admin' WHERE chat_id=? AND workspace_id=1",
            (admin_chat_id,),
        )
    for kind, thread_id in threads.items():
        if not thread_id:
            continue
        exists = conn.execute(
            "SELECT 1 FROM bot_chat_topics WHERE workspace_id=1 AND kind=?",
            (kind,),
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO bot_chat_topics "
            "(workspace_id, chat_id, thread_id, name, source, kind) "
            "VALUES (1, ?, ?, ?, 'h2_seed', ?)",
            (admin_chat_id, thread_id, kind, kind),
        )
    conn.commit()
```

- [ ] **Step 4: Run, expect pass** — 4 passed

- [ ] **Step 5: Commit**

```
git add database/migrations/ws_runtime_seed.py tests/test_ws_runtime_seed.py
git commit -m "feat(V1.17.0e2): migraciya ws_runtime_seed - kind kolonka + sider Pulse ws=1 iz .env (idempotent)"
```

---

### Task 3 (H1/H2 gate): полный регресс + smoke

- [ ] `.venv\Scripts\python.exe -m pytest tests/ -q` → всё зелёное (H1/H2 аддитивны, ничего не ломают).
- [ ] `.venv\Scripts\python.exe -c "import bot_core.ws_resolver, database.migrations.ws_runtime_seed; print('OK')"`
- [ ] Коммит не нужен (только проверка).

---

### Task 4+ (H3–H5) — НЕ автономно, с Ильёй

H3: в `message_handler.py`/`registration_conversation.py`/`command_handler.py` Pulse-гейт (блок-лист/«Доступ открывается»/меню) считать по `build_context(conn, chat.id, user.id).workspace_id` и блок-листу ЭТОГО ws, а не `config.CHAT_ID`. За feature-flag `H_RUNTIME_WS` (env, дефолт off на проде до проверки).
H4: заменить `config.ADMIN_CHAT_ID`/`*_THREAD_ID` в группах хендлеров на `resolve_role_chat(conn, ws, 'admin')`/`resolve_thread(conn, ws, kind)`. По одной группе = коммит + тест.
H5: UI «Топики» на сайте (поля kind→thread_id) + выпил `.env`-веток.

Каждая H3/H4 правка: TDD, прогон на dev-боте (`devbot.service`), бэкап БД, флаг, потом прод с Ильёй. **Никогда не авто-деплой H3+ на прод.**

---

## Self-Review

- Живая боль (2-й владелец заблокирован Pulse-гейтом) → решается в H3 (гейт по ws), фундамент H1/H2. ✅
- Резолверы аддитивны, поведение бота не меняют до H3 → безопасно автономно. ✅
- Миграция только ws=1, идемпотентна, бэкап в RUNBOOK → Pulse не ломается. ✅
- `resolve_thread` зависит от `bot_chat_topics.kind` → создаётся в H2 до использования. ✅
- Типы/имена: `resolve_role_chat(conn, ws, role)`, `resolve_thread(conn, ws, kind)`, `invalidate_resolver_cache()`, `up_add_kind_column`, `seed_pulse_ws1` — согласованы между Task 1/2/4.
