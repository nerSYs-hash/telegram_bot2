# Subproject I — Bot per-Workspace Owner Recognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Бот распознаёт пользователя как владельца ЕГО workspace (owner-доступы, «Панель Владельца») per-workspace через `workspace_members`, а не по single-tenant `config.OWNER_ID`/`main_admin_id`, за флагом `I_WS_RBAC` (OFF → байт-в-байт).

**Architecture:** Новый бот-keystone `bot_core/ws_role.py` (`resolve_bot_role`/`is_ws_owner`, флаг `i_ws_rbac_enabled()`) переиспользует `api/workspace_rbac.resolve_ws_role` (keystone #3) + ws-машинерию H (`ws_ctx` из `context` / `resolve_user_primary_workspace`). Две точки-спины (`_is_owner_or_deputy`, `get_main_reply_keyboard`) получают опциональный `context` и за флагом сначала спрашивают keystone, иначе — прежняя логика как fallback. Strangler, не переписывание.

**Tech Stack:** python-telegram-bot, sqlite3 (`bot_database.db`, путь `os.getenv('DB_PATH','database/bot_database.db')`), pytest. Ветка `feat/V1.17.0f-bot-per-ws-owner` (создана, спека `412ebb9`).

---

## Контекст-аудит (зафиксировано 17.05)

- `_is_owner_or_deputy(user_id)` — `handlers/admin_moderation.py:932`. Тело:
  `if user_id==config.OWNER_ID: return True` → `if await bot_permissions.user_has(user_id,"admins.view"): return True` → `return await database.db_friend.is_deputy(user_id)`. Вызовы (все имеют `context`/`update`): `admin_moderation.py:653` (`handle_owner_panel_button(update,context,btn)`), `:973` (`panel_callback(update,context)`), `:1125` (`handle_panel_text_input`, есть `update`/`context`), `handlers/owner_handlers.py:925` (есть `context`), `handlers/message_handler.py:234,670,931` (есть `context`).
- `get_main_reply_keyboard(db,user_id=None,main_admin_id=None)` — `handlers/commands/system_commands.py:20`. `is_owner = user_id and main_admin_id and user_id==main_admin_id`; иначе `db.get_user(user_id)['is_owner'/'is_admin']`. Вызовы: `system_commands.py:177,182`, `handlers/registration_conversation.py:276` (все async-хендлеры с `context` в области видимости).
- Keystone #3: `api/workspace_rbac.py:resolve_ws_role(conn,user_id,ws_id,developer_id=0) -> str` (`owner→owner, admin→deputy, moderator→admin, не член→user, developer_id→developer`). `api` — пакет (есть `api/__init__.py`), импорт `from api.workspace_rbac import resolve_ws_role` рабочий.
- H-машинерия (в проде): `bot_core/ws_resolver.resolve_user_primary_workspace(conn,user_id)`; `ws_ctx` кладёт `resolve_workspace_middleware` (`bot.py`) в `context.chat_data/user_data['ws_ctx']`, объект имеет `.workspace_id` (паттерн в `ws_resolver.resolve_gate_chat`).
- `config.OWNER_ID = int(os.getenv("MAIN_ADMIN_ID",7536752126))`; `config.DEVELOPER_ID = int(os.getenv("DEVELOPER_ID",7536752126))`. Прод-данные подтверждены: `workspace_members` ws1→`7536752126` owner, ws7→`8376708692` owner.
- БД-conn паттерн в коде: `os.getenv('DB_PATH','database/bot_database.db')` + `sqlite3.connect` (`owner_handlers.py:944`). Keystone открывает свой short-lived conn → НЕ пере-плумим conn через 6 точек.

---

### Task 1: Бот-keystone `bot_core/ws_role.py` + флаг

**Files:**
- Create: `bot_core/ws_role.py`
- Test: `tests/test_ws_role.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ws_role.py
import sqlite3
import pytest
from bot_core.ws_role import i_ws_rbac_enabled, resolve_bot_role, is_ws_owner


class _Ctx:
    """Фейк telegram context: ws_ctx в chat_data, как кладёт middleware."""
    def __init__(self, ws_id=None):
        self.chat_data = {}
        self.user_data = {}
        if ws_id is not None:
            self.chat_data['ws_ctx'] = type('WS', (), {'workspace_id': ws_id})()


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.execute("CREATE TABLE workspace_members (workspace_id INTEGER, user_id INTEGER, role TEXT)")
    c.execute("INSERT INTO workspace_members VALUES (1, 7536752126, 'owner')")
    c.execute("INSERT INTO workspace_members VALUES (7, 8376708692, 'owner')")
    c.execute("INSERT INTO workspace_members VALUES (7, 555, 'moderator')")
    c.commit()
    yield c
    c.close()


def test_flag_off_default(monkeypatch):
    monkeypatch.delenv('I_WS_RBAC', raising=False)
    assert i_ws_rbac_enabled() is False

@pytest.mark.parametrize('val', ['1', 'true', 'YES', 'on'])
def test_flag_on_truthy(monkeypatch, val):
    monkeypatch.setenv('I_WS_RBAC', val)
    assert i_ws_rbac_enabled() is True

def test_flag_off_resolve_returns_user(monkeypatch, conn):
    monkeypatch.delenv('I_WS_RBAC', raising=False)
    assert resolve_bot_role(_Ctx(7), 8376708692, conn=conn) == 'user'
    assert is_ws_owner(_Ctx(7), 8376708692, conn=conn) is False

def test_owner_in_own_ws_group(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    assert resolve_bot_role(_Ctx(7), 8376708692, conn=conn) == 'owner'
    assert is_ws_owner(_Ctx(7), 8376708692, conn=conn) is True

def test_owner_cross_ws_is_user(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    # Кирилл (owner ws=7) в Pulse-чате ws=1 → не owner
    assert resolve_bot_role(_Ctx(1), 8376708692, conn=conn) == 'user'

def test_pulse_owner_ws1(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    assert is_ws_owner(_Ctx(1), 7536752126, conn=conn) is True

def test_developer_god_mode(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    monkeypatch.setenv('DEVELOPER_ID', '999')
    # 999 не член ни одного ws, но developer → god-mode в любом ws
    assert resolve_bot_role(_Ctx(7), 999, conn=conn) == 'developer'
    assert is_ws_owner(_Ctx(7), 999, conn=conn) is True

def test_dm_resolves_ws_by_membership(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    # ЛС: ws_ctx нет → resolve_user_primary_workspace по членству → ws=7
    assert is_ws_owner(_Ctx(None), 8376708692, conn=conn) is True

def test_non_member_is_user(monkeypatch, conn):
    monkeypatch.setenv('I_WS_RBAC', '1')
    assert resolve_bot_role(_Ctx(7), 424242, conn=conn) == 'user'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ws_role.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot_core.ws_role'`

- [ ] **Step 3: Write minimal implementation**

```python
# bot_core/ws_role.py
"""Per-workspace owner-распознавание для бота (Подпроект I).

Бот-keystone: роль юзера в ЕГО workspace через #3-keystone
api.workspace_rbac.resolve_ws_role + ws-машинерию H. За флагом
I_WS_RBAC (дефолт OFF → бот-owner логика single-tenant байт-в-байт).
"""
import os
import sqlite3
from typing import Optional

_TRUTHY = {'1', 'true', 'yes', 'on'}


def i_ws_rbac_enabled() -> bool:
    """I feature-flag. OFF (дефолт) → бот-owner логика прежняя
    single-tenant. Включается env I_WS_RBAC=1 (с Ильёй, как H)."""
    return os.getenv('I_WS_RBAC', '').strip().lower() in _TRUTHY


def _ws_from_context(context) -> Optional[int]:
    """ws_id из ws_ctx (кладёт resolve_workspace_middleware в bot.py
    в context.chat_data/user_data). None если нет (напр. ЛС)."""
    for attr in ('chat_data', 'user_data'):
        store = getattr(context, attr, None)
        if isinstance(store, dict) and store.get('ws_ctx') is not None:
            ws_id = getattr(store['ws_ctx'], 'workspace_id', None)
            if ws_id is not None:
                return ws_id
    return None


def resolve_bot_role(context, user_id: int,
                     conn: Optional[sqlite3.Connection] = None) -> str:
    """'developer'|'owner'|'deputy'|'admin'|'user' для user_id в его ws.

    Флаг OFF → всегда 'user' (вызывающий уходит на старую single-tenant
    логику — байт-в-байт). ws: группа → ws_ctx; ЛС → членство (H).
    conn=None → открываем свой к DB_PATH (и закрываем)."""
    if not i_ws_rbac_enabled():
        return 'user'
    own = conn is None
    if own:
        conn = sqlite3.connect(os.getenv('DB_PATH', 'database/bot_database.db'))
    try:
        ws_id = _ws_from_context(context)
        if ws_id is None:
            from bot_core.ws_resolver import resolve_user_primary_workspace
            ws_id = resolve_user_primary_workspace(conn, user_id)
        if ws_id is None:
            return 'user'
        from config import DEVELOPER_ID
        from api.workspace_rbac import resolve_ws_role
        return resolve_ws_role(conn, user_id, ws_id, DEVELOPER_ID or 0)
    except Exception:
        return 'user'  # Pulse-safe: любая ошибка → старая логика у вызывающего
    finally:
        if own:
            conn.close()


def is_ws_owner(context, user_id: int,
                conn: Optional[sqlite3.Connection] = None) -> bool:
    """MVP-предикат: владелец (или developer god-mode) своего ws."""
    return resolve_bot_role(context, user_id, conn) in ('owner', 'developer')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ws_role.py -q`
Expected: PASS (13 passed — 9 funcs, `test_flag_on_truthy` parametrized ×4, +`test_moderator_is_not_owner`)

- [ ] **Step 5: Commit**

```bash
git add bot_core/ws_role.py tests/test_ws_role.py
git commit -m "feat(V1.17.0f1): bot-keystone ws_role - resolve_bot_role/is_ws_owner za flagom I_WS_RBAC (pereispolzuet resolve_ws_role #3 + ws-mashineriyu H, flag OFF -> 'user' bayt-v-bayt)"
```

---

### Task 2: Провести `_is_owner_or_deputy` за флагом + точки вызова

**Files:**
- Modify: `handlers/admin_moderation.py:932` (тело `_is_owner_or_deputy`) + вызовы `:653,:973,:1125`
- Modify: `handlers/owner_handlers.py:925`
- Modify: `handlers/message_handler.py:234,670,931`
- Test: `tests/test_i_owner_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_i_owner_gate.py
import asyncio
import pytest
import handlers.admin_moderation as am


class _Ctx:
    def __init__(self): self.chat_data = {}; self.user_data = {}


def _run(coro): return asyncio.get_event_loop().run_until_complete(coro)


def test_off_context_none_old_path(monkeypatch):
    # Флаг роли нет, context=None → ветка I пропущена, идём по старой логике.
    monkeypatch.setattr(am, 'OWNER_ID', 111, raising=False)
    # user != OWNER_ID, user_has падает/False, is_deputy False → False
    monkeypatch.setattr('bot_permissions.user_has', lambda *a, **k: _aw(False))
    monkeypatch.setattr('database.db_friend.is_deputy', lambda *a, **k: _aw(False))
    assert _run(am._is_owner_or_deputy(222, context=None)) is False


def test_owner_id_shortcut_still_first(monkeypatch):
    from config import OWNER_ID
    assert _run(am._is_owner_or_deputy(OWNER_ID, context=None)) is True


def test_flag_on_ws_owner_true(monkeypatch):
    # context задан, is_ws_owner True → _is_owner_or_deputy True (per-WS).
    monkeypatch.setattr('bot_core.ws_role.is_ws_owner', lambda *a, **k: True)
    assert _run(am._is_owner_or_deputy(8376708692, context=_Ctx())) is True


def test_flag_on_ws_not_owner_falls_through(monkeypatch):
    # is_ws_owner False → не теряем старый путь (fallback).
    monkeypatch.setattr('bot_core.ws_role.is_ws_owner', lambda *a, **k: False)
    monkeypatch.setattr('bot_permissions.user_has', lambda *a, **k: _aw(False))
    monkeypatch.setattr('database.db_friend.is_deputy', lambda *a, **k: _aw(False))
    assert _run(am._is_owner_or_deputy(424242, context=_Ctx())) is False


async def _aw(v): return v
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_i_owner_gate.py -q`
Expected: FAIL — `TypeError: _is_owner_or_deputy() got an unexpected keyword argument 'context'`

- [ ] **Step 3: Modify `_is_owner_or_deputy` (admin_moderation.py:932)**

Заменить всё тело функции (строки 932–956) на:

```python
async def _is_owner_or_deputy(user_id: int, context=None) -> bool:
    """
    Проверка: владелец или зам владельца (доступ к Панели Владельца).

    Подпроект I: при context!=None и флаге I_WS_RBAC=1 — per-WS owner
    через bot_core.ws_role.is_ws_owner. context=None / флаг OFF /
    is_ws_owner=False → ПРЕЖНЯЯ single-tenant логика (байт-в-байт).
    """
    from config import OWNER_ID
    if user_id == OWNER_ID:
        return True

    if context is not None:
        try:
            from bot_core.ws_role import is_ws_owner
            if is_ws_owner(context, user_id):
                return True
        except Exception:
            pass

    try:
        from bot_permissions import user_has
        if await user_has(user_id, "admins.view"):
            return True
    except Exception:
        pass

    from database.db_friend import is_deputy
    return await is_deputy(user_id)
```

- [ ] **Step 4: Wire call sites to pass `context`**

Точечные правки (только аргумент добавляется):

- `handlers/admin_moderation.py:653`:
  `if not await _is_owner_or_deputy(user_id):` → `if not await _is_owner_or_deputy(user_id, context):`
- `handlers/admin_moderation.py:973`:
  `if not await _is_owner_or_deputy(user_id):` → `if not await _is_owner_or_deputy(user_id, context):`
- `handlers/admin_moderation.py:1125`:
  `if not await _is_owner_or_deputy(update.effective_user.id):` → `if not await _is_owner_or_deputy(update.effective_user.id, context):`
- `handlers/owner_handlers.py:925`:
  `if not await _is_owner_or_deputy(query.from_user.id):` → `if not await _is_owner_or_deputy(query.from_user.id, context):`
- `handlers/message_handler.py:234`:
  `is_owner = await _is_owner_or_deputy(user.id)` → `is_owner = await _is_owner_or_deputy(user.id, context)`
- `handlers/message_handler.py:670`:
  `await send_admin_panel(context.bot, message.chat.id, is_owner=await _is_owner_or_deputy(user.id))` → `... is_owner=await _is_owner_or_deputy(user.id, context))`
- `handlers/message_handler.py:931`:
  `await send_admin_panel(context.bot, message.chat.id, is_owner=await _is_owner_or_deputy(user.id))` → `... is_owner=await _is_owner_or_deputy(user.id, context))`

(Все 7 мест — async-хендлеры PTB, `context` в области видимости. Прочие вызовы без лёгкого `context` — оставить как есть, дефолт `context=None` = старое поведение, безопасно.)

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_i_owner_gate.py -q`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add handlers/admin_moderation.py handlers/owner_handlers.py handlers/message_handler.py tests/test_i_owner_gate.py
git commit -m "feat(V1.17.0f2): _is_owner_or_deputy per-WS za flagom I_WS_RBAC + provodka 7 tochek vyzova (context), flag OFF/context None -> bayt-v-bayt"
```

---

### Task 3: Провести `get_main_reply_keyboard` за флагом + точки вызова

**Files:**
- Modify: `handlers/commands/system_commands.py:20` (`get_main_reply_keyboard`) + вызовы `:177,:182`
- Modify: `handlers/registration_conversation.py:276`
- Test: `tests/test_i_reply_keyboard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_i_reply_keyboard.py
import pytest
from handlers.commands.system_commands import get_main_reply_keyboard


class _DB:
    def is_feature_enabled(self, _): return True
    def get_user(self, _): return {'is_owner': 0, 'is_admin': 0}


class _Ctx:
    def __init__(self): self.chat_data = {}; self.user_data = {}


def _btn_texts(markup):
    return [b.text for row in markup.keyboard for b in row]


def test_owner_button_for_pulse_owner_unchanged():
    m = get_main_reply_keyboard(_DB(), user_id=111, main_admin_id=111)
    assert "👑 Панель Владельца" in _btn_texts(m)


def test_member_no_context_is_faq():
    m = get_main_reply_keyboard(_DB(), user_id=222, main_admin_id=111)
    assert "❓ FAQ" in _btn_texts(m)
    assert "👑 Панель Владельца" not in _btn_texts(m)


def test_ws_owner_with_context_gets_owner_button(monkeypatch):
    monkeypatch.setattr('bot_core.ws_role.is_ws_owner', lambda *a, **k: True)
    m = get_main_reply_keyboard(_DB(), user_id=8376708692,
                                main_admin_id=111, context=_Ctx())
    assert "👑 Панель Владельца" in _btn_texts(m)


def test_context_none_unchanged(monkeypatch):
    # context=None → ветка I пропущена, обычный участник = FAQ.
    m = get_main_reply_keyboard(_DB(), user_id=8376708692,
                                main_admin_id=111, context=None)
    assert "❓ FAQ" in _btn_texts(m)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_i_reply_keyboard.py -q`
Expected: FAIL — `TypeError: get_main_reply_keyboard() got an unexpected keyword argument 'context'`

- [ ] **Step 3: Modify `get_main_reply_keyboard` (system_commands.py:20)**

Заменить сигнатуру и блок определения ролей (строки 20–36) на:

```python
def get_main_reply_keyboard(db, user_id=None, main_admin_id=None, context=None):
    """
    Нижняя клавиатура — только базовые кнопки.
    Владелец видит [👑 Панель Владельца], Админ — [📋 Новые заявки], остальные — [❓ FAQ].

    Подпроект I: при context!=None и флаге I_WS_RBAC=1 владелец СВОЕГО ws
    тоже видит «Панель Владельца». context=None / флаг OFF → байт-в-байт.
    """
    profile_enabled = db.is_feature_enabled('profile')
    balance_or_profile = KeyboardButton("👤 Профиль") if profile_enabled else KeyboardButton("💰 Баланс")

    is_owner = user_id and main_admin_id and user_id == main_admin_id
    is_deputy = False
    is_admin = False

    if not is_owner and user_id and context is not None:
        try:
            from bot_core.ws_role import is_ws_owner
            if is_ws_owner(context, user_id):
                is_owner = True
        except Exception:
            pass

    if user_id and not is_owner:
        u = db.get_user(user_id)
        if u and u.get('is_owner'):
            is_deputy = True  # зам владельца — видит полную панель
        elif u and u.get('is_admin'):
            is_admin = True
```

(строки 38–49 — блок `if is_owner or is_deputy: ... return ReplyKeyboardMarkup(...)` — НЕ трогаем.)

- [ ] **Step 4: Wire call sites to pass `context`**

- `handlers/commands/system_commands.py:177`:
  `reply_markup=get_main_reply_keyboard(db, user.id, admin_id)` → `reply_markup=get_main_reply_keyboard(db, user.id, admin_id, context)`
- `handlers/commands/system_commands.py:182`:
  `reply_markup=get_main_reply_keyboard(db, user.id, admin_id)` → `reply_markup=get_main_reply_keyboard(db, user.id, admin_id, context)`
- `handlers/registration_conversation.py:276`:
  `reply_markup=get_main_reply_keyboard(main_db, user_id, OWNER_ID)` → `reply_markup=get_main_reply_keyboard(main_db, user_id, OWNER_ID, context)`

(Все три — внутри async-хендлеров с `context`. Если при правке окажется, что в конкретной точке `context` недоступен — оставить вызов без 4-го аргумента: дефолт `None` = старое поведение, безопасно.)

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_i_reply_keyboard.py -q`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add handlers/commands/system_commands.py handlers/registration_conversation.py tests/test_i_reply_keyboard.py
git commit -m "feat(V1.17.0f3): get_main_reply_keyboard per-WS owner-knopka za flagom I_WS_RBAC + 3 tochki vyzova (context), context None -> bayt-v-bayt"
```

---

### Task 4: Регресс-гейт + smoke + заметка активации

- [ ] **Step 1: Полный регресс**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: всё зелёное (база H = 167 + новые I-тесты, 0 регрессий). I аддитивен и за флагом OFF.

- [ ] **Step 2: Smoke-импорт (нет циклических импортов bot→api)**

Run: `.venv\Scripts\python.exe -c "import bot_core.ws_role, handlers.admin_moderation, handlers.commands.system_commands; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Байт-в-байт проба флага OFF (ручная верификация)**

Run: `.venv\Scripts\python.exe -c "import os; os.environ.pop('I_WS_RBAC',None); from bot_core.ws_role import i_ws_rbac_enabled, resolve_bot_role; print(i_ws_rbac_enabled(), resolve_bot_role(type('C',(),{'chat_data':{},'user_data':{}})(), 8376708692))"`
Expected: `False user` (флаг OFF → keystone не резолвит, вызывающие на старом пути)

- [ ] **Step 4: Коммит не нужен (только проверки). Активация — отдельно, с Ильёй.**

> **Активация (путь A, как H — НЕ авто):** merge `feat/V1.17.0f-bot-per-ws-owner`→`main`→авто-деплой (флаг OFF, байт-в-байт) → проверить прод чист (pulsbot active, журнал) → flip `I_WS_RBAC=1` в `/root/PulsBot/.env` + `systemctl restart pulsbot` → smoke: (1) Илья в ЛС видит «👑 Панель Владельца», панель открывается; (2) Кирилл `8376708692` в ЛС видит «👑 Панель Владельца» (а не «❓ FAQ»), панель его ws; (3) Кирилл в Pulse-чате `-1003900924578` НЕ owner; (4) откат-проба: убрать `I_WS_RBAC` + рестарт → Кирилл снова участник. БД-миграций нет → откат чистый.

---

## Self-Review

- **Spec coverage:** §1 keystone → Task 1. §2 две точки-спины (`_is_owner_or_deputy`, `get_main_reply_keyboard`) + Pulse-safe (`OWNER_ID` shortcut сохранён первым, developer god-mode в `resolve_ws_role`, owner-membership ws=1) → Task 2/3. §3 тесты (юнит keystone, флаг-OFF байт-в-байт, регресс-гейт, smoke, критерий приёмки) → Task 1/4. Активация путём A → Task 4 заметка. Прочие `==main_admin_id` (фаза 2 опц.) — спекой объявлены не-целью, в плане намеренно нет. ✅ Гэпов нет.
- **Placeholder scan:** все шаги с полным кодом/командами/ожиданием; «оставить как есть» — явное определённое правило (дефолт None=старое), не плейсхолдер. ✅
- **Type consistency:** `i_ws_rbac_enabled()`, `resolve_bot_role(context,user_id,conn=None)`, `is_ws_owner(context,user_id,conn=None)` — единообразны в Task 1/2/3 (Task 2/3 зовут `is_ws_owner(context,user_id)`, conn по умолчанию открывается из DB_PATH). `_is_owner_or_deputy(user_id,context=None)` и `get_main_reply_keyboard(db,user_id,main_admin_id,context=None)` — сигнатуры согласованы с правками точек вызова. ✅
- **Сигнатура vs спека:** спека §1 писала `resolve_bot_role(conn,context,user_id)`; план уточнил на `resolve_bot_role(context,user_id,conn=None)` — намеренно, чтобы НЕ пере-плумивать conn через 6 single-arg точек (`_is_owner_or_deputy` не имеет conn). Соответствует намерению спеки (keystone + переиспользование), снижает риск. ✅
