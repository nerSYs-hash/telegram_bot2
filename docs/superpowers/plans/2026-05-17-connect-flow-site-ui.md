# Connect-flow Site-UI (P4 — C6 + C8) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-05-17-connect-flow-lifecycle-design.md` (§C6 «сайт-бейдж бот не в чате», §C8 «Главное vs Доп.»).
**Sibling plan (backend, в main):** `docs/superpowers/plans/2026-05-17-connect-flow-lifecycle.md` (P1–P3).
**Версия:** `V1.17.0i` (новый скоуп; h-семейство h1–h20 занято Экономикой/Статистикой/Новостями). Коммиты с тегом `[Site]` где меняется только фронт.
**Ветка:** `feat/V1.17.0i-connect-flow-site-ui`.
**Деплой:** отдельный юнит (см. memory `feedback_site_workflow`): локальный билд → проверка → push → деплой. **C7 уже сделано отдельно бэкенд-планом, тут не дублируем.**

**Goal:** Сайт показывает (а) красный бейдж «🔴 бот не в чате» когда сообщество без активных чатов или у конкретного чата `removed_at IS NOT NULL`; (б) ярлык «⭐ Главное» на pulse-themed сообществе и «доп. №N» на остальных, с порядком «главное сверху». Read-only индикаторы, без новых пользовательских действий.

**Architecture:** Бэкенд-довесок аддитивный (новые ключи в dict-выдаче, изменение `ORDER BY`) — флага не нужно, API совместим со старыми клиентами (просто игнорят новые поля). Фронт читает новые поля; при их отсутствии (старый бэкенд) тихий фолбэк на текущий вид.

**Tech Stack:** Python 3, FastAPI (pass-through), sqlite3, pytest. React 18 + Vite + Tailwind (`Admin_SITE/`). Сборка: `node node_modules/vite/bin/vite.js build` (см. memory `build_npx_node_dir_trap` — `npx vite build` падает).

**Scope:** только C6+C8. Иконки/аватары сообществ — отдельный companion-spec (см. §8 design-спеки). Связь с UI отключённого чата в TG (текст «переподключён») — уже сделано бэкенд-планом (Task 5 / V1.17.0h5).

---

## File Structure

- **Modify** `database/db_workspaces.py`
  - `get_workspaces_for_user` → +`is_primary`, +`active_chats_count`; `ORDER BY is_pulse_themed DESC, created_at ASC` (главное первым, затем по дате создания).
  - `get_workspace_details` → в списке чатов добавить `removed_at`; активные (`removed_at IS NULL`) сверху, затем по текущему `role`-порядку.
- **Modify** `tests/test_db_workspaces.py` — расширить тесты обеих функций.
- **Modify** `tests/test_workspaces_api.py` — sanity по новым ключам в API-ответе (pass-through).
- **Modify** `Admin_SITE/components/workspaces/WorkspaceList.jsx`
  - Карточка сообщества: красный 🔴-бейдж если `active_chats_count === 0`; ярлык «⭐ Главное» при `is_primary`; счётчик `active/total` если есть отключённые.
- **Modify** `Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx`
  - В заголовке списка `<option>` — `⭐` рядом с primary, «#N доп.» рядом с прочими; в текущей плашке маленький `⭐` если активное — primary.
- **Modify** `Admin_SITE/components/workspaces/WorkspacePage.jsx`
  - Каждый чат: 🔴 «бот не в чате» + приглушение если `removed_at`; шапка чатов — «N активных / M всего».
- **Build** `Admin_SITE/dist/*` — пересобрать локально, закоммитить (паттерн `chore [Site]: пересборка dist`).
- **NOT touched:** маршруты `api/workspaces_routes.py` (pass-through dict — поля идут автоматически); бэкенд connect-flow / migrations (уже в main).

---

# PHASE P4-A — Backend API extensions (additive, без флага)

### Task 1: `get_workspaces_for_user` — `is_primary`, `active_chats_count`, порядок

**Files:**
- Modify: `database/db_workspaces.py:116–131`
- Test: `tests/test_db_workspaces.py`

- [ ] **Step 1: Write the failing test** (добавить в `tests/test_db_workspaces.py`)

```python
def test_workspaces_for_user_has_is_primary_and_active_count(tmp_path):
    import sqlite3
    from database.migrations.multi_tenancy import up_create_workspaces_tables
    from database.db_workspaces import (
        create_workspace, add_member, add_bot_chat, get_workspaces_for_user,
        soft_remove_bot_chat,
    )
    conn = sqlite3.connect(":memory:")
    up_create_workspaces_tables(conn)
    conn.execute(
        "CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,"
        " added_by_user_id INTEGER, title TEXT, chat_type TEXT, role TEXT,"
        " added_at TEXT, removed_at TIMESTAMP)"
    )
    # Главное (pulse-themed) — создаём позже, но должно идти первым.
    secondary = create_workspace(conn, "Вторичный", owner_user_id=42,
                                 is_pulse_themed=False, plan='free')
    add_member(conn, secondary, 42, 'owner')
    primary = create_workspace(conn, "Главный Pulse", owner_user_id=42,
                               is_pulse_themed=True, plan='free')
    add_member(conn, primary, 42, 'owner')
    # Чаты: 2 активных в primary, 1 активный + 1 soft-removed в secondary.
    add_bot_chat(conn, -101, primary, added_by=42, title="A", chat_type="supergroup", role='main')
    add_bot_chat(conn, -102, primary, added_by=42, title="B", chat_type="supergroup", role='admin')
    add_bot_chat(conn, -201, secondary, added_by=42, title="C", chat_type="supergroup", role='main')
    add_bot_chat(conn, -202, secondary, added_by=42, title="D", chat_type="supergroup", role='admin')
    soft_remove_bot_chat(conn, -202)

    rows = get_workspaces_for_user(conn, 42)
    assert [r['id'] for r in rows] == [primary, secondary]      # primary сверху
    assert rows[0]['is_primary'] is True
    assert rows[1]['is_primary'] is False
    assert rows[0]['chats_count'] == 2 and rows[0]['active_chats_count'] == 2
    assert rows[1]['chats_count'] == 2 and rows[1]['active_chats_count'] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_workspaces.py -k is_primary -q`
Expected: FAIL — ключей `is_primary`/`active_chats_count` нет; порядок может не совпасть (`created_at DESC` ставит secondary сверху).

- [ ] **Step 3: Write minimal implementation** (`database/db_workspaces.py:116–131`)

```python
def get_workspaces_for_user(conn: sqlite3.Connection, user_id: int) -> list:
    """Все workspaces где user — member. Включает role, счётчики и порядок «главное сверху».

    V1.17.0i (C8): is_primary = is_pulse_themed; список отсортирован
    `is_pulse_themed DESC, created_at ASC` — главное первым, далее по дате
    создания (стабильно для нумерации «доп. №N» на фронте).
    V1.17.0i (C6): active_chats_count = bot_chats без `removed_at`.
    Старое `chats_count` сохранено как «всего» для обратной совместимости.
    """
    has_removed = _bot_chats_has_removed_at(conn)
    active_clause = (
        "(SELECT COUNT(*) FROM bot_chats WHERE workspace_id=w.id AND removed_at IS NULL)"
        if has_removed
        else "(SELECT COUNT(*) FROM bot_chats WHERE workspace_id=w.id)"
    )
    rows = conn.execute(f'''
        SELECT
            w.id, w.name, w.owner_user_id, w.is_pulse_themed, w.plan,
            m.role,
            (SELECT COUNT(*) FROM workspace_members WHERE workspace_id=w.id) AS members_count,
            (SELECT COUNT(*) FROM bot_chats WHERE workspace_id=w.id) AS chats_count,
            {active_clause} AS active_chats_count
        FROM workspaces w
        JOIN workspace_members m ON m.workspace_id = w.id
        WHERE m.user_id = ?
        ORDER BY w.is_pulse_themed DESC, w.created_at ASC
    ''', (user_id,)).fetchall()
    keys = ('id', 'name', 'owner_user_id', 'is_pulse_themed', 'plan',
            'role', 'members_count', 'chats_count', 'active_chats_count')
    result = []
    for r in rows:
        d = dict(zip(keys, r))
        d['is_primary'] = bool(d['is_pulse_themed'])
        result.append(d)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_workspaces.py -k is_primary -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add database/db_workspaces.py tests/test_db_workspaces.py
git commit -m "feat(V1.17.0i1): API списка сообществ — is_primary + active_chats_count + порядок (главное сверху)"
```

---

### Task 2: `get_workspace_details` — `removed_at` в чатах + активные сверху

**Files:**
- Modify: `database/db_workspaces.py:134–167`
- Test: `tests/test_db_workspaces.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workspace_details_chats_expose_removed_at_active_first():
    import sqlite3
    from database.migrations.multi_tenancy import up_create_workspaces_tables
    from database.db_workspaces import (
        create_workspace, add_member, add_bot_chat, get_workspace_details,
        soft_remove_bot_chat,
    )
    conn = sqlite3.connect(":memory:")
    up_create_workspaces_tables(conn)
    conn.execute(
        "CREATE TABLE bot_chats (chat_id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,"
        " added_by_user_id INTEGER, title TEXT, chat_type TEXT, role TEXT,"
        " added_at TEXT, removed_at TIMESTAMP)"
    )
    ws = create_workspace(conn, "W", owner_user_id=42, is_pulse_themed=False, plan='free')
    add_member(conn, ws, 42, 'owner')
    add_bot_chat(conn, -1, ws, added_by=42, title="A", chat_type="supergroup", role='main')
    add_bot_chat(conn, -2, ws, added_by=42, title="B", chat_type="supergroup", role='admin')
    soft_remove_bot_chat(conn, -1)        # main → отключён

    d = get_workspace_details(conn, ws)
    # ключ присутствует у каждого чата
    assert all('removed_at' in c for c in d['chats'])
    # активный (-2) идёт раньше soft-removed (-1)
    ids = [c['chat_id'] for c in d['chats']]
    assert ids.index(-2) < ids.index(-1)
    removed = next(c for c in d['chats'] if c['chat_id'] == -1)
    active = next(c for c in d['chats'] if c['chat_id'] == -2)
    assert removed['removed_at'] is not None
    assert active['removed_at'] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_workspaces.py -k chats_expose_removed_at -q`
Expected: FAIL — ключа `removed_at` нет; порядок по `role` ставит main (-1) первым.

- [ ] **Step 3: Write minimal implementation** (`database/db_workspaces.py:134–167`)

```python
def get_workspace_details(conn: sqlite3.Connection, workspace_id: int) -> Optional[dict]:
    """Workspace + список членов + список чатов.

    V1.17.0i (C6): в чате отдаём `removed_at`; активные (`removed_at IS NULL`)
    сверху, далее текущий порядок по role и дате — чтобы UI красил
    отключённые приглушённо в конце.
    """
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

    has_removed = _bot_chats_has_removed_at(conn)
    select_cols = ("chat_id, title, chat_type, added_by_user_id, added_at, role, "
                   + ("removed_at" if has_removed else "NULL AS removed_at"))
    order_clause = (
        "ORDER BY CASE WHEN removed_at IS NULL THEN 0 ELSE 1 END, "
        "         CASE role WHEN 'main' THEN 0 WHEN 'admin' THEN 1 "
        "                   WHEN 'journal' THEN 2 ELSE 3 END, added_at DESC"
        if has_removed else
        "ORDER BY CASE role WHEN 'main' THEN 0 WHEN 'admin' THEN 1 "
        "                   WHEN 'journal' THEN 2 ELSE 3 END, added_at DESC"
    )
    chats = conn.execute(
        f"SELECT {select_cols} FROM bot_chats WHERE workspace_id=? {order_clause}",
        (workspace_id,)
    ).fetchall()

    return {
        'workspace': {
            'id': ws_row[0], 'name': ws_row[1], 'owner_user_id': ws_row[2],
            'is_pulse_themed': bool(ws_row[3]), 'plan': ws_row[4],
            'created_at': ws_row[5],
        },
        'members': [{'user_id': m[0], 'role': m[1], 'joined_at': m[2]} for m in members],
        'chats': [{'chat_id': c[0], 'title': c[1], 'chat_type': c[2],
                   'added_by': c[3], 'added_at': c[4], 'role': c[5],
                   'removed_at': c[6]} for c in chats],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_workspaces.py -k chats_expose_removed_at -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add database/db_workspaces.py tests/test_db_workspaces.py
git commit -m "feat(V1.17.0i2): API детали сообщества — removed_at в чатах + активные сверху"
```

---

### Task 3: API regress + sanity

**Files:**
- Modify: `tests/test_workspaces_api.py` (1–2 ассерта на новые ключи в JSON-ответе).

- [ ] **Step 1: Дописать sanity** в существующий API-тест списка/деталей:

```python
def test_list_workspaces_exposes_new_keys(client_with_seed):
    client, _ = client_with_seed
    r = client.get("/api/workspaces", headers=AUTH)
    assert r.status_code == 200
    ws_list = r.json()["workspaces"]
    assert ws_list, "ожидаем хотя бы один workspace"
    sample = ws_list[0]
    for k in ("is_primary", "active_chats_count", "chats_count"):
        assert k in sample, f"ключ {k} обязан быть в API-ответе"


def test_workspace_details_chats_expose_removed_at(client_with_seed):
    client, ws_id = client_with_seed
    r = client.get(f"/api/workspaces/{ws_id}", headers=AUTH)
    assert r.status_code == 200
    for c in r.json()["chats"]:
        assert "removed_at" in c
```

(адаптировать фикстуры под существующий стиль файла; имена `client_with_seed`/`AUTH` — заглушки, использовать локальные)

- [ ] **Step 2:** `.venv\Scripts\python.exe -m pytest tests/ -q --no-header` → 0 failed, новые тесты зелёные, существующие 219+ не упали (новые dict-ключи не должны ломать никого — старые ассерты на конкретные ключи продолжат работать).

- [ ] **Step 3: Commit**

```bash
git add tests/test_workspaces_api.py
git commit -m "test(V1.17.0i3): sanity-ассерты на новые ключи API (workspaces list + details)"
```

---

# PHASE P4-B — Site UI (бейдж + ярлык, build [Site])

> Все коммиты этой фазы с тегом `[Site]`. Файл `Admin_SITE/dist/*` пересобирается одним отдельным коммитом в конце фазы (см. Task 7), как принято (`chore [Site]: пересборка dist`).

### Task 4: `WorkspaceSwitcher` — звёздочка primary + нумерация доп.

**Files:**
- Modify: `Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx`

- [ ] **Step 1: Implement.** API уже отдаёт массив в нужном порядке (главное первым). В компоненте:
  - В `<option>`: префикс `⭐ ` если `w.is_primary`, иначе `№N доп. · ` где N = индекс среди не-primary, начиная с 2 (первое доп = №2, второе = №3 и т.д.).
  - В компактной плашке (`title` + текущая иконка-плитка): к `title` приписать `· главное` или `· доп. №N`.

Минимальное изменение в строке `{list.map(...)}`:

```jsx
{(() => {
  let extraIdx = 1;
  return list.map((w) => {
    const isPrimary = !!w.is_primary;
    const label = isPrimary
      ? `⭐ ${w.name} · ${w.role}`
      : `№${++extraIdx} доп. · ${w.name} · ${w.role}`;
    return <option key={w.id} value={w.id}>{label}</option>;
  });
})()}
```

И `title` в выбранной плашке:

```jsx
title={`Активное сообщество: ${cur?.name || ''}${cur?.is_primary ? ' · главное' : ' · доп.'}`}
```

- [ ] **Step 2: Manual smoke** через `Admin_SITE/preview.html` (см. memory `design_part2_preview_2026_05_18`) — открыть `localhost:5173/preview.html`, проверить нет регресса вёрстки.

- [ ] **Step 3: Commit**

```bash
git add Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx
git commit -m "feat(V1.17.0i4) [Site]: свитчер — звёздочка у главного + нумерация доп."
```

---

### Task 5: `WorkspaceList` — 🔴-бейдж + ярлык «Главное/доп. №N»

**Files:**
- Modify: `Admin_SITE/components/workspaces/WorkspaceList.jsx`

- [ ] **Step 1: Implement.** В блоке `{workspaces.map(ws => (...))}`:
  1. Вычислить `extraIdx` синхронно с свитчером (нумерация доп. начинается со 2).
  2. Бейдж справа в шапке карточки (рядом с `ChevronRight`):
     - если `ws.is_primary`: «⭐ Главное» (тёплый warn-стиль).
     - иначе: «№N доп.» (нейтральный bd2-стиль).
  3. Красный 🔴-бейдж под счётчиком если `(ws.active_chats_count ?? ws.chats_count) === 0`:
     - текст: «🔴 Бот не в чате».
     - подсказка (`title`): «Pulse Bot был удалён из подключённого чата. Добавьте его обратно — роль и настройки сохранены.»
  4. Счётчик чатов: если `ws.active_chats_count !== undefined && ws.active_chats_count < ws.chats_count`, показать `«{active}/{total} чат.»` вместо `«{total} чат.»` — короткий сигнал что часть отключена.

Шаблон вставки (рядом с текущим `<div className="text-[10px] uppercase ...">{ws.role} · {ws.members_count} участн. · {ws.chats_count} чат.</div>`):

```jsx
const active = ws.active_chats_count ?? ws.chats_count;
const total  = ws.chats_count;
const allRemoved = total > 0 && active === 0;
const chatsLabel = active === total
  ? `${total} чат.`
  : `${active}/${total} чат.`;
// ...
<div className="text-[10px] uppercase tracking-widest font-bold text-lbl mt-0.5">
  {ws.role} · {ws.members_count} участн. · {chatsLabel}
</div>
{allRemoved && (
  <div
    title="Pulse Bot был удалён из подключённого чата. Добавьте его обратно — роль и настройки сохранены."
    className="mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-md
               text-[10px] font-black uppercase tracking-wide
               bg-[color-mix(in_oklab,var(--danger)_14%,transparent)] text-danger
               border border-[color-mix(in_oklab,var(--danger)_36%,transparent)]">
    🔴 Бот не в чате
  </div>
)}
```

Ярлык primary/доп. — справа от заголовка карточки, до `ChevronRight`:

```jsx
{ws.is_primary ? (
  <span className="px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-wide
                   bg-[color-mix(in_oklab,var(--warn)_16%,transparent)] text-warn
                   border border-[color-mix(in_oklab,var(--warn)_36%,transparent)]">
    ⭐ Главное
  </span>
) : (
  <span className="px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-wide
                   bg-sf2 text-txd border border-bd2">
    №{extraIdx} доп.
  </span>
)}
```

- [ ] **Step 2: Manual smoke** через `preview.html` (или storybook-аналог если есть): убедиться что бейдж рендерится при mock-данных без `active_chats_count` (fallback) и при `active_chats_count === 0`.

- [ ] **Step 3: Commit**

```bash
git add Admin_SITE/components/workspaces/WorkspaceList.jsx
git commit -m "feat(V1.17.0i5) [Site]: карточки сообществ — бейдж «бот не в чате» + ярлык главное/доп."
```

---

### Task 6: `WorkspacePage` — per-chat 🔴 + шапка «N активных»

**Files:**
- Modify: `Admin_SITE/components/workspaces/WorkspacePage.jsx`

- [ ] **Step 1: Implement.**
  1. Шапка блока «Чаты»: вместо `Чаты ({details.chats.length})` показать `Чаты ({активные} активных · {всего})` если есть отключённые.
  2. Per-chat row: если `c.removed_at`:
     - контейнер `<div>` приглушить (`opacity-60` + `border-l-4 border-danger`).
     - после заголовка чата добавить плашку «🔴 Бот не в чате — добавьте обратно».
     - кнопку «Отключить» (`LogOut`) скрыть для уже soft-removed (бессмысленно).

Минимальная вставка в шапку:

```jsx
const activeCount = details.chats.filter(c => !c.removed_at).length;
const totalCount  = details.chats.length;
const chatsTitle  = activeCount === totalCount
  ? `Чаты (${totalCount})`
  : `Чаты (${activeCount} активных · ${totalCount})`;
// ...
<MessageCircle className="mr-2 text-ok" size={14}/> {chatsTitle}
```

В рендере `details.chats.map(c => ...)`:

```jsx
const isRemoved = !!c.removed_at;
return (
  <div
    key={c.chat_id}
    className={`p-3 rounded-2xl transition-opacity ${
      isRemoved
        ? 'bg-sf2 opacity-60 border-l-4 border-[color-mix(in_oklab,var(--danger)_60%,transparent)]'
        : 'bg-sf2'
    }`}>
    {/* существующий заголовок чата */}
    {isRemoved && (
      <div className="mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-md
                      text-[10px] font-black uppercase tracking-wide
                      bg-[color-mix(in_oklab,var(--danger)_14%,transparent)] text-danger
                      border border-[color-mix(in_oklab,var(--danger)_36%,transparent)]">
        🔴 Бот не в чате — добавьте обратно, роль восстановится
      </div>
    )}
    {/* кнопку «Отключить» рендерить только если !isRemoved */}
  </div>
);
```

- [ ] **Step 2: Manual smoke** — в `preview.html`/реальном dev-API убедиться, что (а) шапка показывает «N активных», (б) приглушённый чат выглядит читаемо.

- [ ] **Step 3: Commit**

```bash
git add Admin_SITE/components/workspaces/WorkspacePage.jsx
git commit -m "feat(V1.17.0i6) [Site]: детали сообщества — приглушение отключённых чатов + шапка «N активных»"
```

---

### Task 7: Локальный билд + sanity

- [ ] **Step 1:** В `Admin_SITE/` — `node node_modules/vite/bin/vite.js build` (НЕ `npx vite build` — см. `build_npx_node_dir_trap`).
- [ ] **Step 2:** Проверить `Admin_SITE/dist/index.html` присутствует и не пустой; быстро открыть локально (например `python -m http.server` в `dist/`) и убедиться, что нет 500/пустоты в свитчере/списке.
- [ ] **Step 3: Commit dist**

```bash
git add Admin_SITE/dist
git commit -m "chore [Site]: пересборка dist под V1.17.0i (бейдж + ярлык главное/доп.)"
```

---

### Task 8: Финальный regress

- [ ] **Step 1:** `.venv\Scripts\python.exe -m pytest tests/ -q --no-header` → all green (новые backend-тесты + база).
- [ ] **Step 2:** Сверка по спеке: C6✓Tasks 1+2+5+6 · C8✓Tasks 1+4+5.
- [ ] **Step 3: Commit (если правки регрессий)**

```bash
git commit -m "test(V1.17.0i7): финальный регресс зелёный, P4 готов к merge+deploy"
```

---

## Activation (ГЕЙТ с Ильёй) — публикация сайта

Деплой сайта — наружный, hard-to-reverse шаг. Выполняется ТОЛЬКО с явным «go» Ильи (memory `feedback_site_workflow`).

1. Merge `feat/V1.17.0i-connect-flow-site-ui` → `main` (после ревью Ильи).
2. Push → авто-деплой бэкенда (`deploy.yml`, поля API аддитивны, рестарт `pulsbot+pulsapi` без рисков).
3. Сайт-деплой по существующему процессу `[Site]` (локальный билд уже в репо).
4. Smoke с Ильёй:
   - Открыть сайт → видно ⭐ у Pulse Москва, «доп. №2/№3» у Кирилла/прочих.
   - Удалить бота из тест-чата (Кирилл ws7) → в течение секунд карточка показывает 🔴 «Бот не в чате».
   - Открыть детали → отключённый чат приглушён, с подсказкой.
   - Вернуть бота → бейдж исчезает (после reload).
5. Откат: revert последнего merge на main + откатить `Admin_SITE/dist` к предыдущему артефакту; API-поля остаются — старый сайт их игнорит.

---

## Out of scope (явно)

- Real-time push «бот удалён» (UI обновляется на reload/перезаход — не SSE).
- Иконки/аватары сообществ (companion-spec, §8 design-спеки).
- Кнопка «Подключить бота заново» прямо из карточки — отдельная UX-итерация (memory `bot_removal_status_gap`); сейчас owner и так видит CTA «Подключить ещё чат» в `WorkspaceList`.
- Любая правка connect-flow в боте (всё в P1–P3 уже в main за флагом `CONNECT_FLOW_V2`).

Связано: spec `2026-05-17-connect-flow-lifecycle-design.md`, plan `2026-05-17-connect-flow-lifecycle.md`, memory [[bot-removal-status-gap]] [[feedback_site_workflow]] [[build_npx_node_dir_trap]] [[design_part2_preview_2026_05_18]].
