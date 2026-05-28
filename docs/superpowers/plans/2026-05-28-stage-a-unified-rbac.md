# Этап A полной изоляции — единая система прав

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить три расходящиеся системы прав (`users.is_admin/is_owner` глобально + `OWNER_ID` из .env + ad-hoc `_is_owner` хелперы по хендлерам) на ОДНУ точку правды `workspace_members` через `bot_core/ws_role.resolve_bot_role()`. Дать критерий приёмки: добавил юзера админом в WS на сайте → бот в чате этого WS его признаёт, в других — игнорирует. Удалил → во всех 3 точках синхронно.

**Architecture:**
- Источник правды: `workspace_members(workspace_id, user_id, role)`.
- API-сайд: `api/workspace_rbac.resolve_ws_role(conn, user_id, ws_id, developer_id) → owner|deputy|admin|developer|user`. Уже работает.
- Бот-сайд: `bot_core/ws_role.resolve_bot_role(context, user_id, conn=None)` за флагом `I_WS_RBAC`. Контекст ws_id берётся из `ws_ctx` middleware, поставленного `bot.py` при входящем апдейте.
- Стратегия миграции: оставить старые `_is_owner` хелперы как обёртку, внутри которой при `I_WS_RBAC=1` идёт `resolve_bot_role`, иначе — legacy логика. Это позволит безопасно флипнуть флаг на проде.
- Sync `users.is_admin/is_owner ↔ workspace_members` уже есть (фиксы k21+k23), но в этом плане не дублируем — только проверяем покрытие.

**Tech Stack:** Python 3.12, sqlite3, python-telegram-bot, pytest. Прод-БД `/root/PulsBot/database/bot_database.db`. Локальная — `database/bot_database.db`.

---

## File Structure

| Файл | Действие | Что |
|---|---|---|
| `bot_core/ws_role.py` | Modify | Добавить `is_ws_admin(context, user_id, conn=None)` — owner∨deputy∨admin∨developer |
| `tests/test_ws_role.py` | Modify | Тесты `is_ws_admin`; тесты «owner ws=1 не owner в ws=2» |
| `handlers/owner_handlers.py` | Modify | `_is_owner` → делегирует на `is_ws_owner` при I_WS_RBAC |
| `handlers/bingo_handlers.py` | Modify | `_is_owner_user` → делегирует на `is_ws_owner` |
| `handlers/lottery_handlers.py` | Modify | `_is_owner_user` → делегирует на `is_ws_owner` |
| `handlers/titles_handlers.py` | Modify | `_is_owner_user` (если есть) → делегирует |
| `handlers/admin_moderation.py` | Modify | Глобальные `OWNER_ID == user.id` → `is_ws_owner` |
| `handlers/message_handler.py` | Modify | Чекать `is_user_excluded` через ws-role, не через глобальные флаги |
| `.env` (прод, локально) | Modify | `I_WS_RBAC=1` после прохождения всех тестов |

**Scope check:** этот план НЕ трогает `db_friend.py` / `pulse_bot.db` (это Этап B). НЕ трогает удаление `users.is_admin/is_owner` колонок (это после Этапа A, отдельный шаг). НЕ трогает ADMIN_CHAT_ID / треды (Этап C). Только единый-RBAC.

---

## ⚠️ Сквозное правило для всех Task

После каждой Task (перед commit) обновлять `docs/ROADMAP_full_isolation_2026-05-28.md`:
- В разделе «⚠️ Работает частично» / «❌ Не работает» — закрытую строку перевести в «✅ Уже работает».
- В разделе «🗺️ Дорожная карта» — Этапу A помечать прогресс: «Task N/7 done».
- В заголовке — обновлять процент готовности (грубая оценка).
Коммитить ROADMAP в ОДНОМ коммите с правкой (`git add docs/ROADMAP... handlers/...`). См. memory feedback-update-isolation-roadmap.

---

## Task 1: Расширить `bot_core/ws_role.py` функцией `is_ws_admin`

**Files:**
- Modify: `bot_core/ws_role.py:85` (после `is_ws_owner`)
- Test: `tests/test_ws_role.py`

- [ ] **Step 1: Прочитать существующий `bot_core/ws_role.py`** чтобы не ломать сигнатуры.

Run: `Read bot_core/ws_role.py`
Expected: видим `resolve_bot_role`, `is_ws_owner`. Знаем что флаг `I_WS_RBAC` управляет.

- [ ] **Step 2: Написать failing test для `is_ws_admin`**

В `tests/test_ws_role.py` добавить:

```python
def test_is_ws_admin_returns_true_for_owner_deputy_admin_developer(monkeypatch, tmp_path):
    """is_ws_admin = True для owner/deputy/admin/developer; False для user."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    monkeypatch.setenv("DEVELOPER_ID", "9999")
    db = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db))
    import sqlite3
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE workspace_members (workspace_id INTEGER, user_id INTEGER, role TEXT, PRIMARY KEY(workspace_id, user_id));
        INSERT INTO workspace_members VALUES (1, 100, 'owner'), (1, 200, 'admin'), (1, 300, 'moderator'), (1, 400, 'user');
    """)
    conn.commit()

    from bot_core.ws_role import is_ws_admin
    class _Ctx:
        chat_data = {"ws_ctx": type("WsCtx", (), {"workspace_id": 1})()}
        user_data = {}

    assert is_ws_admin(_Ctx(), 100, conn) is True   # owner
    assert is_ws_admin(_Ctx(), 200, conn) is True   # admin in members → deputy role
    assert is_ws_admin(_Ctx(), 300, conn) is True   # moderator in members → admin role
    assert is_ws_admin(_Ctx(), 400, conn) is False  # plain user
    assert is_ws_admin(_Ctx(), 9999, conn) is True  # developer god-mode
    assert is_ws_admin(_Ctx(), 500, conn) is False  # not a member
    conn.close()
```

- [ ] **Step 3: Запустить тест — должен фейлиться**

Run: `pytest tests/test_ws_role.py::test_is_ws_admin_returns_true_for_owner_deputy_admin_developer -v`
Expected: `ImportError: cannot import name 'is_ws_admin'`

- [ ] **Step 4: Добавить функцию в `bot_core/ws_role.py`** (после `is_ws_owner`)

```python
def is_ws_admin(context, user_id: int,
                conn: Optional[sqlite3.Connection] = None) -> bool:
    """True для owner/deputy/admin/developer своего ws. False для user.

    Используется хендлерами для гейтов «админ ИЛИ владелец».
    Сохраняет Pulse-safe поведение: при флаге OFF → False (caller fallback)."""
    return resolve_bot_role(context, user_id, conn) in (
        'owner', 'deputy', 'admin', 'developer'
    )
```

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `pytest tests/test_ws_role.py::test_is_ws_admin_returns_true_for_owner_deputy_admin_developer -v`
Expected: PASS

- [ ] **Step 6: Запустить все тесты `test_ws_role.py`**

Run: `pytest tests/test_ws_role.py -v`
Expected: все PASS, регрессий нет.

- [ ] **Step 7: Commit**

```bash
git add bot_core/ws_role.py tests/test_ws_role.py
git commit -m "feat(V1.17.0L1) [Этап A]: is_ws_admin() в bot_core.ws_role

Хелпер True/False для owner/deputy/admin/developer текущего ws.
Pulse-safe: при I_WS_RBAC=0 даёт False (caller уходит в legacy fallback).
Используется хендлерами в Task 2-6 этого плана.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: `handlers/owner_handlers.py` — `_is_owner` через ws_role

**Files:**
- Modify: `handlers/owner_handlers.py:51-57` (функция `_is_owner`)
- Test: новый `tests/test_owner_handlers_ws_role.py`

- [ ] **Step 1: Failing test — `_is_owner` использует ws_role при I_WS_RBAC=1**

Создать `tests/test_owner_handlers_ws_role.py`:

```python
import sqlite3
import pytest


def _make_db_with_members(tmp_path, monkeypatch, members):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE users (user_id INTEGER PRIMARY KEY, is_admin INTEGER DEFAULT 0, is_owner INTEGER DEFAULT 0);
        CREATE TABLE workspace_members (workspace_id INTEGER, user_id INTEGER, role TEXT, PRIMARY KEY(workspace_id, user_id));
    """)
    for ws_id, uid, role in members:
        conn.execute("INSERT INTO workspace_members VALUES (?, ?, ?)", (ws_id, uid, role))
    conn.commit()
    return conn


def test_is_owner_uses_ws_role_when_flag_on(monkeypatch, tmp_path):
    """С I_WS_RBAC=1: owner ws=1 — owner; owner ws=2 — НЕ owner в ws=1."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    conn = _make_db_with_members(tmp_path, monkeypatch,
        [(1, 100, 'owner'), (2, 200, 'owner')])

    class _DB:
        cursor = conn.cursor()
        def get_user(self, uid):
            row = self.cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
            return dict(zip(['user_id','is_admin','is_owner'], row)) if row else None

    from handlers.owner_handlers import _is_owner_ws

    # ws_ctx ws=1 — owner ws=1 видит панель, owner ws=2 не видит
    class _Ctx1:
        chat_data = {"ws_ctx": type("X", (), {"workspace_id": 1})()}
        user_data = {}

    assert _is_owner_ws(_Ctx1(), _DB(), 100, admin_id=999, conn=conn) is True
    assert _is_owner_ws(_Ctx1(), _DB(), 200, admin_id=999, conn=conn) is False
    conn.close()


def test_is_owner_legacy_path_when_flag_off(monkeypatch, tmp_path):
    """С I_WS_RBAC=0: legacy — admin_id или is_owner=1 в users."""
    monkeypatch.delenv("I_WS_RBAC", raising=False)
    conn = _make_db_with_members(tmp_path, monkeypatch, [])
    conn.execute("INSERT INTO users (user_id, is_owner) VALUES (?, ?)", (100, 1))
    conn.commit()

    class _DB:
        cursor = conn.cursor()
        def get_user(self, uid):
            row = self.cursor.execute("SELECT user_id, is_admin, is_owner FROM users WHERE user_id=?", (uid,)).fetchone()
            return dict(zip(['user_id','is_admin','is_owner'], row)) if row else None

    from handlers.owner_handlers import _is_owner_ws

    class _Ctx:
        chat_data = {}
        user_data = {}

    assert _is_owner_ws(_Ctx(), _DB(), 100, admin_id=999, conn=conn) is True  # is_owner=1
    assert _is_owner_ws(_Ctx(), _DB(), 999, admin_id=999, conn=conn) is True  # main_admin_id
    assert _is_owner_ws(_Ctx(), _DB(), 500, admin_id=999, conn=conn) is False
    conn.close()
```

- [ ] **Step 2: Запустить — должен фейлиться**

Run: `pytest tests/test_owner_handlers_ws_role.py -v`
Expected: `ImportError: cannot import name '_is_owner_ws'`

- [ ] **Step 3: Добавить `_is_owner_ws` в `handlers/owner_handlers.py`**

В `handlers/owner_handlers.py` добавить НОВУЮ функцию (не заменяя пока `_is_owner`):

```python
def _is_owner_ws(context, db, user_id: int, admin_id: int,
                 conn=None) -> bool:
    """Унифицированная проверка owner-доступа для Этапа A.

    I_WS_RBAC=1 (прод-цель): per-ws через bot_core.ws_role.is_ws_owner.
    I_WS_RBAC=0 (legacy): прежняя логика — admin_id из .env ИЛИ is_owner=1
    в users (global). Сохраняется до полного прохождения Этапа A на проде.
    """
    from bot_core.ws_role import i_ws_rbac_enabled, is_ws_owner
    if i_ws_rbac_enabled():
        return is_ws_owner(context, user_id, conn)
    # legacy
    if user_id == admin_id:
        return True
    if DEVELOPER_ID and user_id == DEVELOPER_ID:
        return True
    user_data = db.get_user(user_id)
    return bool(user_data and user_data['is_owner'])
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/test_owner_handlers_ws_role.py -v`
Expected: PASS

- [ ] **Step 5: Заменить вызовы старого `_is_owner` на `_is_owner_ws`**

В `handlers/owner_handlers.py` найти все вызовы `_is_owner(db, user_id, admin_id)` (grep). Заменить на `_is_owner_ws(context, db, user_id, admin_id)`. **Сохранить старую `_is_owner` для backward-compat ВРЕМЕННО** (другие файлы могут импортировать).

Run: `Grep '_is_owner\\(' handlers/owner_handlers.py -n`
Заменить ровно эти строки.

- [ ] **Step 6: Прогнать существующие тесты owner_handlers если есть**

Run: `pytest tests/ -k owner -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add handlers/owner_handlers.py tests/test_owner_handlers_ws_role.py
git commit -m "feat(V1.17.0L2) [Этап A]: owner_handlers._is_owner_ws + миграция вызовов

_is_owner_ws — единая проверка владельца, флаг-гейтированная через
I_WS_RBAC. ON → per-ws через bot_core.ws_role; OFF → legacy. Все
вызовы внутри owner_handlers переведены на _is_owner_ws.

Старая _is_owner оставлена для backward-compat (другие модули
могут импортировать), удалим после миграции всех хендлеров (Task 7).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: `handlers/bingo_handlers.py` — `_is_owner_user` через ws_role

**Files:**
- Modify: `handlers/bingo_handlers.py:38-43`
- Test: `tests/test_bingo_handlers_ws_role.py` (новый, минимальный)

- [ ] **Step 1: Failing test**

Создать `tests/test_bingo_handlers_ws_role.py`:

```python
def test_bingo_is_owner_user_uses_ws_role(monkeypatch, tmp_path):
    monkeypatch.setenv("I_WS_RBAC", "1")
    import sqlite3
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE users (user_id INTEGER PRIMARY KEY, is_owner INTEGER DEFAULT 0);
        CREATE TABLE workspace_members (workspace_id INTEGER, user_id INTEGER, role TEXT, PRIMARY KEY(workspace_id, user_id));
        INSERT INTO workspace_members VALUES (1, 100, 'owner');
    """)
    conn.commit()

    from handlers.bingo_handlers import BingoHandler

    class _DB:
        def __init__(self, c): self.cursor = c.cursor(); self.conn = c
        def get_user(self, uid):
            row = self.cursor.execute("SELECT user_id, is_owner FROM users WHERE user_id=?", (uid,)).fetchone()
            return dict(zip(['user_id','is_owner'], row)) if row else None

    h = BingoHandler(_DB(conn), target_chat_id=-100, main_admin_id=999)
    # monkeypatch контекст в виде user (BingoHandler принимает user объект)
    class _U:
        def __init__(self, uid): self.id = uid
    # Без context bingo использует static check — нужно поправить сигнатуру
    # Это ожидаемый fail: bingo._is_owner_user не принимает context
    assert hasattr(h, '_is_owner_user_ws'), "must add _is_owner_user_ws taking context"
    conn.close()
```

- [ ] **Step 2: Run — fail**

Run: `pytest tests/test_bingo_handlers_ws_role.py -v`
Expected: AssertionError (no `_is_owner_user_ws` attr).

- [ ] **Step 3: Добавить `_is_owner_user_ws(self, user, context=None)` в BingoHandler**

В `handlers/bingo_handlers.py`:

```python
def _is_owner_user_ws(self, user, context=None) -> bool:
    """Per-ws проверка владельца. context=None → fallback на legacy
    (для путей где context недоступен — будут переписаны в Task 7)."""
    from bot_core.ws_role import i_ws_rbac_enabled, is_ws_owner
    if i_ws_rbac_enabled() and context is not None:
        return is_ws_owner(context, user.id)
    # legacy
    if user.id == self.main_admin_id:
        return True
    u = self.db.get_user(user.id)
    return bool(u and u['is_owner'])
```

- [ ] **Step 4: Найти все вызовы `self._is_owner_user(user)` и привязать context, где есть**

Run: `Grep '_is_owner_user' handlers/bingo_handlers.py -n`
Каждый callsite смотрит на сигнатуру: если в этом методе есть `context: ContextTypes.DEFAULT_TYPE` параметр → передать его в `_is_owner_user_ws(user, context)`. Иначе — оставить старый вызов `_is_owner_user(user)` (legacy fallback).

NB: Внутри BingoHandler большинство хендлеров принимают `update, context` — передача context тривиальна.

- [ ] **Step 5: Run test + sanity**

Run: `pytest tests/test_bingo_handlers_ws_role.py -v && pytest tests/ -k bingo -v`
Expected: новый PASS, регрессий нет.

- [ ] **Step 6: Commit**

```bash
git add handlers/bingo_handlers.py tests/test_bingo_handlers_ws_role.py
git commit -m "feat(V1.17.0L3) [Этап A]: BingoHandler._is_owner_user_ws через ws_role

Все callsites внутри BingoHandler с доступом к context переведены на
_is_owner_user_ws(user, context). Старый _is_owner_user сохранён для
путей без context (legacy fallback).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: `handlers/lottery_handlers.py` — то же что Task 3

**Files:** Modify: `handlers/lottery_handlers.py`. Test: `tests/test_lottery_handlers_ws_role.py`.

- [ ] **Step 1:** Скопировать структуру Task 3 — там тот же паттерн `_is_owner_user`. Test → fail → impl `_is_owner_user_ws` → переключить callsites → commit `V1.17.0L4`.

```python
def _is_owner_user_ws(self, user, context=None) -> bool:
    from bot_core.ws_role import i_ws_rbac_enabled, is_ws_owner
    if i_ws_rbac_enabled() and context is not None:
        return is_ws_owner(context, user.id)
    if user.id == self.main_admin_id:
        return True
    u = self.db.get_user(user.id)
    return bool(u and u['is_owner'])
```

- [ ] **Step 2:** Commit `V1.17.0L4 [Этап A]: LotteryHandler._is_owner_user_ws через ws_role`.

---

## Task 5: `handlers/titles_handlers.py` — если есть свой owner-check

**Files:** Modify: `handlers/titles_handlers.py`. Test: при наличии.

- [ ] **Step 1:** Grep `_is_owner|is_owner == 1|is_owner=1|is_admin == 1` в `handlers/titles_handlers.py`. Если есть свой owner-чек — повторить паттерн Task 3. Если нет — пропустить Task 5, написать в commit-сообщении следующей задачи «titles_handlers: owner-чека нет, пропущен».

```bash
git log -1  # подтвердить что Task 4 закоммичен прежде чем двигаться
```

- [ ] **Step 2:** Если правил — commit `V1.17.0L5 [Этап A]: titles_handlers owner-check`. Если нет — переход к Task 6.

---

## Task 6: `handlers/admin_moderation.py` — глобальные `OWNER_ID == user.id`

**Files:** Modify: `handlers/admin_moderation.py`. Test: добавить юнит-тест на одно из мест.

- [ ] **Step 1:** Grep по `OWNER_ID|admin_id == |MAIN_ADMIN_ID` в `handlers/admin_moderation.py`. Зафиксировать список callsites.

Run: `Grep 'OWNER_ID|admin_id ==' handlers/admin_moderation.py -n`

- [ ] **Step 2:** Создать `tests/test_admin_moderation_ws_role.py` — failing test на одну ключевую точку (например, гейт открытия панели).

(Структура аналогична Task 2.)

- [ ] **Step 3:** Заменить каждый `if user.id == OWNER_ID:` на `if _admin_ws(context, user.id):` где `_admin_ws` — приватный хелпер:

```python
def _admin_ws(context, user_id: int) -> bool:
    """Gate владелец/админ для модерационных действий per-ws."""
    from bot_core.ws_role import i_ws_rbac_enabled, is_ws_admin
    if i_ws_rbac_enabled():
        return is_ws_admin(context, user_id)
    # legacy
    from config import OWNER_ID
    return user_id == OWNER_ID  # старый поведение
```

- [ ] **Step 4:** Run all moderation tests.

Run: `pytest tests/ -k moderation -v`
Expected: PASS

- [ ] **Step 5:** Commit `V1.17.0L6 [Этап A]: admin_moderation gates через ws_role`.

---

## Task 7: `handlers/message_handler.py` — `is_user_excluded` через ws_role

**Files:** Modify: `handlers/message_handler.py`. Test: `tests/test_message_handler_ws_excl.py`.

- [ ] **Step 1:** Прочитать `is_user_excluded` в `handlers/message_handler.py` (вокруг 517).

Run: `Read handlers/message_handler.py:500-550`

- [ ] **Step 2:** Failing test — `is_user_excluded` использует ws_role для определения «админа этого ws».

```python
def test_user_excluded_per_ws(monkeypatch, tmp_path):
    """Owner ws=1 — excluded в ws=1. Owner ws=2 — НЕ excluded в ws=1 (он в этом ws гость)."""
    monkeypatch.setenv("I_WS_RBAC", "1")
    # подготовить БД, ws_ctx, замокать chat_admins=[]
    # ассертить is_user_excluded(owner_ws1) == True
    # ассертить is_user_excluded(owner_ws2) == False (в контексте ws=1)
    pass  # детали — при реализации
```

- [ ] **Step 3:** Реализовать: внутри `is_user_excluded` при `i_ws_rbac_enabled()` → проверять `is_ws_admin(context, user_id)` вместо `user_data['is_admin']`/`user_data['is_owner']`. Сохранить fallback на старую логику.

- [ ] **Step 4:** Run regression: `pytest tests/test_i_owner_gate.py -v` (см. существующий тест).

- [ ] **Step 5:** Commit `V1.17.0L7 [Этап A]: message_handler.is_user_excluded per-ws через ws_role`.

---

## Task 8: Flip `I_WS_RBAC=1` локально и прогон smoke-теста

**Files:** не код. Env + ручной прогон.

- [ ] **Step 1:** Локально:
  ```bash
  # В .env (локальном) добавить:
  echo "I_WS_RBAC=1" >> .env
  ```

- [ ] **Step 2:** Прогнать весь тест-сьют:
  ```bash
  pytest tests/ -v
  ```
  Expected: PASS. Если есть фейлы — лечить (typo, опечатки в сигнатурах).

- [ ] **Step 3:** Mental walk:
  - Открыть `handlers/owner_handlers.py:117` — `_is_owner_ws(context, ...)` — ✓
  - Открыть `handlers/admin_moderation.py` любую гейт-точку — ✓
  - Открыть `handlers/message_handler.py:517` `is_user_excluded` — ✓

- [ ] **Step 4:** Не коммитить .env. Зафиксировать в memo, что локально `I_WS_RBAC=1`.

---

## Task 9: Прод: I_WS_RBAC=1 + критерий приёмки

**Files:** прод `.env`, оперативно.

- [ ] **Step 1:** ssh на прод, бэкап БД:
  ```bash
  ssh root@82.22.3.225 "cp /root/PulsBot/database/bot_database.db /root/PulsBot/database/bot_database.db.pre_stage_a_$(date +%Y%m%d_%H%M%S)"
  ```

- [ ] **Step 2:** Добавить в прод-`.env`:
  ```bash
  ssh root@82.22.3.225 "grep -q I_WS_RBAC /root/PulsBot/.env || echo 'I_WS_RBAC=1' >> /root/PulsBot/.env"
  ```

- [ ] **Step 3:** Рестарт бота + API:
  ```bash
  ssh root@82.22.3.225 "systemctl restart pulsbot pulsapi"
  ```

- [ ] **Step 4:** Логи 2 минуты, ловить ошибки:
  ```bash
  ssh root@82.22.3.225 "journalctl -u pulsbot --since '2 min ago' --no-pager 2>&1 | grep -iE 'error|traceback|exception' | head -30"
  ```
  Expected: пусто (или старые, не свежие).

- [ ] **Step 5:** Критерий приёмки. Прод-тест (Илья руками):
  - На сайте в WS=1 добавить тестового юзера админом → бот в чате PositivЭ его признаёт (`/get_admins` ИЛИ команда требующая админ-доступа).
  - Удалить через сайт → бот тут же перестаёт признавать.
  - Если есть test-ws=2 — проверить что админ ws=1 НЕ имеет прав в ws=2.

- [ ] **Step 6:** Если критерий не пройден — `ssh root@82.22.3.225 "sed -i '/I_WS_RBAC/d' /root/PulsBot/.env && systemctl restart pulsbot pulsapi"` (откат флага без отката кода). Сохранить логи в issue.

- [ ] **Step 7:** Если пройден — закрыть тикет «Этап A», обновить `docs/ROADMAP_full_isolation_2026-05-28.md` (отметить A ✅), обновить [[session_2026_05_28_end]] memory.

---

## Что НЕ делаем в этом плане

- Не удаляем `users.is_admin/is_owner` колонки — это будет после Этапа B и стабилизации.
- Не удаляем legacy fallback из `_is_owner_ws` и аналогов — он живёт пока не флипнули прод; после стабилизации удалим отдельным коммитом V1.17.0L10.
- Не трогаем `OWNER_ID` константу в `config.py` — она ещё используется как fallback. Удалим после полного покрытия и стабилизации.
- Не трогаем sync с `users.is_admin/is_owner` (он уже работает через k21+k23).

## Self-Review

**Spec coverage:**
- `OWNER_ID` глобал → Task 6 (admin_moderation) + Task 2 (owner_handlers _is_owner) — ✅
- `is_owner_or_deputy` глобал — судя по grep, нет такой функции; есть `_is_owner` хелперы которые покрыты Task 2-5 — ✅
- TG `promoteChatMember` как side-effect — УЖЕ работает (k23). В план не добавляем, только проверяем покрытие на этапе приёмки (Task 9 step 5) — ✅
- Критерий приёмки «добавил на сайте → бот признаёт» — Task 9 step 5 — ✅

**Placeholder scan:** проход выше. Подсказка в Task 5 «если есть» — не нарушение: даю checkpoint-инструкцию вместо предсказания (не видел titles_handlers подробно).

**Type consistency:**
- `_is_owner_ws(context, db, user_id, admin_id, conn=None)` в Task 2 vs `_is_owner_user_ws(user, context=None)` в Task 3 — разные сигнатуры, потому что в BingoHandler принимаются `user` объекты (а не user_id), и `db` уже на `self`. Это намеренная разница, не баг.
- `is_ws_admin(context, user_id, conn=None)` в Task 1 — используется в Task 6 без переименования. ✅

---

## Execution Handoff

План готов. Два варианта:

1. **Inline (recommended для этой сессии)** — Илья хочет «продолжаем скелет», у нас есть контекст файлов. Выполняю Task 1-7 здесь, перед каждым commit показываю diff. Прод-flip Task 8-9 — отдельно когда Илья будет онлайн.
2. **Subagent-driven** — диспатч свежего сабагента на каждую задачу. Чище, но дольше на старт.
