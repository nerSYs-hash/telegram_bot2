# Module Toggles — единая система вкл/выкл модулей (шаг #7)

**Дата:** 2026-05-20
**Контекст в памяти:** `modules_hub_state_2026_05_19`, `module_connect_enforcement`,
`feedback_module_catalog_monetization`, `modular_ia_pivot_2026_05_19`.
**Парные доки:** `docs/IA_MODULES_Puls_Chat.md`.

## 1. Зачем

Хаб «Модули» собран (V1.17.0g…g7h), но подключение модуля — это скелет в
`localStorage['pulse_connected_modules']`. Цель — заменить скелет на реальный
механизм:

- состояние **в БД** (multi-tenant per workspace);
- единый **API** между сайтом и ботом (никаких localStorage / параллельных
  настроек в `.env`);
- **энфорс в боте**: модуль OFF = функция в боте молчит;
- единый компонент тумблера, доступный в 2 местах (карточка каталога +
  «паспорт» модуля), и отдельная плоская вкладка «Тумблеры».

## 2. Скоуп

### Что в скоупе спеки (шаг 7.0)

Только **механизм**, без подключения реальных модулей к энфорсу:

- БД-таблицы `module_toggles` + `module_toggle_history`.
- API-эндпоинты `/api/workspaces/<ws_id>/modules/...`.
- Bot helper `is_module_enabled` + декоратор `@requires_module` + кеш с
  версионированием. На реальные хэндлеры ещё **не вешается** на шаге 7.0.
- React-хук `useModules(wsId)`, компонент `<ModuleToggle moduleId=…/>`,
  компонент `<ModuleHeader/>` (паспорт), модалка причины при OFF.
- Вкладка **«Тумблеры модулей»** в Системе — grid в **2 колонки**.
- **Поиск** в каталоге `ModulesHub`: input сверху, фильтрация по
  name+description в реальном времени.
- Удаление `localStorage['pulse_connected_modules']` (один раз при первой
  загрузке после деплоя — UI должен корректно мигрировать состояние).
- Миграция-backfill для `workspace=1` (Витя): вставить `is_enabled=1` для
  модулей, чьи фичи сейчас реально работают.

### Что НЕ в скоупе (отдельные шаги 7.1–7.4)

- Подключение `@requires_module` к реальным хэндлерам — поштучно:
  - **7.1 Триггеры** — первый эталон.
  - **7.2 Гороскоп**.
  - **7.3 Пресс-релизы**.
  - **7.4 Шиппер** (включая связку «Шиппер OFF → его строки в Экономике
    становятся неактивными»).
- Решение о **подтумблерах** внутри каждого модуля (см. §10 «Открытые
  вопросы»). Подтумблеры обсуждаются и утверждаются индивидуально на
  соответствующем шаге.

### Что НЕ делаем сейчас

- Новый ресурс `modules` в каталоге прав с actions `enable/disable/confirm`.
- Workflow «зам инициирует отключение → владелец подтверждает».
- Pending-таблица, очередь подтверждений.
- Любое усложнение `OWNER_LEVEL_PERMISSIONS`.

## 3. Архитектура (срез по слоям)

```
Сайт (React)                 API (Flask, api.py)            БД                 Бот (PTB)
─────────────                 ─────────────────────          ──                 ──────────
<ModuleToggle>  ───POST────▶  /modules/<mid>/enable    ──▶  module_toggles  ◀── is_module_enabled()
<ModuleHeader>                /modules/<mid>/disable        module_toggle_     │
useModules()    ◀──GET─────   /modules                       history           │
ModulesHub                    /modules/<mid>/history          (cache_version)  │
вкладка                                                                        │
«Тумблеры»                                                                     ▼
                                                                       @requires_module(mid)
                                                                       silent return при OFF
```

Истина — БД. Сайт читает через API, бот читает через `db_module_toggles`
напрямую с локальным кешем. API при write дёргает
`db_module_toggles.bump_cache_version(ws_id)`; бот при следующем чтении
сравнивает версию и инвалидирует свой кеш.

## 4. БД

```sql
CREATE TABLE module_toggles (
    workspace_id INTEGER NOT NULL,
    module_id    TEXT    NOT NULL,
    is_enabled   INTEGER NOT NULL DEFAULT 0,
    updated_by   INTEGER,
    updated_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, module_id)
);

CREATE TABLE module_toggle_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    module_id    TEXT    NOT NULL,
    action       TEXT    NOT NULL CHECK (action IN ('enable','disable')),
    reason       TEXT,
    changed_by   INTEGER NOT NULL,
    changed_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_mth_ws_mod ON module_toggle_history(workspace_id, module_id, changed_at DESC);

CREATE TABLE module_toggle_cache_version (
    workspace_id INTEGER PRIMARY KEY,
    version      INTEGER NOT NULL DEFAULT 0
);
```

**Дефолт:** отсутствие строки в `module_toggles` = `is_enabled=0`.
Новый workspace получает всё OFF автоматически.

**Backfill для `workspace=1`:** одноразовая миграция вставляет
`is_enabled=1` для текущего работающего набора: `triggers`,
`press_release`, `shipper`, `horoscope` (плюс остальные модули каталога,
которые сегодня по факту работают у Вити — список финализируется при
написании миграции по аудиту каталога `ModulesHub`).

**`module_id`** — id карточки из каталога `ModulesHub`. Никаких enum в
БД — белый список валидируется в `db_module_toggles`. Единый источник
списка: новый файл `shared/modules_catalog.json` (в корне репо), который
читают и сайт (через Vite `import json`), и бекенд (через `json.load` при
старте процесса). Один файл — одна правда.

## 5. API

Auth — текущий middleware `api.py` (owner+deputy могут писать, admin —
только GET).

```
GET  /api/workspaces/<ws_id>/modules
     → 200 [{id, is_enabled, updated_at, updated_by_name}, ...]

POST /api/workspaces/<ws_id>/modules/<module_id>/enable
     body: {}
     → 200 {is_enabled: true} | 403 | 404

POST /api/workspaces/<ws_id>/modules/<module_id>/disable
     body: {"reason": "не нужен в моём чате"}   # reason обязателен и непустой
     → 200 {is_enabled: false} | 400 (reason пустой) | 403 | 404

GET  /api/workspaces/<ws_id>/modules/<module_id>/history?limit=20
     → 200 [{action, reason, changed_by_name, changed_at}, ...]
```

Каждый POST атомарно:
1. UPDATE/INSERT в `module_toggles`;
2. INSERT в `module_toggle_history`;
3. `bump_cache_version(ws_id)`.

Ошибки: 404 — `module_id` не в белом списке; 403 — нет прав; 400 — пустой
reason при disable; 409 — текущее состояние уже совпадает с запрошенным
(тогда no-op, без записи в историю).

## 6. UI

### 6.1 Хук + компонент тумблера

`Admin_SITE/src/hooks/useModules.js`:
```
useModules(wsId)
  → { modules, loading, error,
      enable(mid), disable(mid, reason),
      history(mid) }
```

`Admin_SITE/src/components/ModuleToggle.jsx`:
```
<ModuleToggle moduleId="triggers" wsId={wsId} size="md|sm" />
```
- Один источник истины: внутри использует `useModules`, мутации оптимистичны
  с откатом при ошибке.
- Клик OFF → модалка `<DisableReasonModal/>` (textarea, ≥3 символа,
  кнопка «Подтвердить отключение»).
- Клик ON → мгновенно.
- При отсутствии прав — disabled с tooltip «нет прав».

### 6.2 Места отображения

1. **Карточка каталога** `ModulesHub.jsx` — кнопка «Подключить/Отключить»
   заменяется на `<ModuleToggle>` (визуально остаётся как кнопка, но логика
   общая).
2. **`<ModuleHeader/>`** — общий «паспорт» сверху экрана модуля
   (иконка + название + краткое описание + `<ModuleToggle>` справа).
   На шаге 7.0 компонент создаётся и подключается к одной демо-странице
   («Триггеры» как preview), но без энфорса.
3. **Вкладка «Тумблеры модулей»** — пункт в сайдбаре «Система»:
   - Grid в **2 колонки** (responsive: 1 колонка на узких экранах).
   - Каждая ячейка: `[иконка] Название · короткое описание · <ModuleToggle>`.
   - Плоский список, без секций каталога.
   - Поиск (тот же input-компонент) сверху.

### 6.3 Поиск в `ModulesHub`

- Input в шапке хаба, плейсхолдер «Найти модуль…».
- Фильтрация по `name + description`, регистр-независимо, простое
  `includes`. Без fuzzy/диакритики на 7.0 (добавим если попросит).
- Подсветка совпадения через `<mark>` в названии и описании.
- Empty state: «Ничего не найдено по запросу „<q>“ · сбросить».
- Debounce 150 мс, очистка по Esc.

### 6.4 Удаление localStorage

При первом запуске после деплоя 7.0: код в `AdminDashboard.jsx` удаляет
`localStorage.removeItem('pulse_connected_modules')` (одноразовая чистка
по флагу `localStorage['pulse_modules_migrated_v1']='1'`).

## 7. Энфорс в боте

`bot_core/module_guard.py`:
```python
def requires_module(module_id: str):
    def deco(handler):
        async def wrapped(update, context, *a, **kw):
            ws = resolve_workspace(update)
            if not is_module_enabled(ws.id, module_id):
                return  # silent
            return await handler(update, context, *a, **kw)
        return wrapped
    return deco
```

`database/db_module_toggles.py`:
- `is_module_enabled(ws_id, module_id) -> bool` — с in-memory кешем
  `{(ws_id, module_id): (value, version)}`, TTL 30 с **или** инвалидация
  по `version != current_version(ws_id)` (что сработает раньше).
- `bump_cache_version(ws_id)` — INSERT OR REPLACE INTO
  `module_toggle_cache_version`.
- Тонкая прослойка `set_module_state(ws_id, module_id, is_enabled,
  reason, user_id)` — атомарно: upsert + history + bump.

**На шаге 7.0** декоратор существует, helper существует, но **не
применяется ни к одному хэндлеру**. Применение — поштучно на 7.1–7.4
с тестом «OFF → молчит».

## 8. План выката (итеративно)

| Шаг   | Что          | Коммиты/PR                         |
|-------|--------------|------------------------------------|
| 7.0   | Механизм     | fix(V1.17.0h0…) — БД, API, UI, бот-helper |
| 7.1   | Триггеры     | feat(V1.17.0h1) — guard + ModuleHeader + обсуждение подтумблеров |
| 7.2   | Гороскоп     | feat(V1.17.0h2) — guard + обсуждение «нужен ли тумблер автокрона» |
| 7.3   | Пресс-релизы | feat(V1.17.0h3) — guard + обсуждение «нужен ли тумблер авто-публикации» |
| 7.4   | Шиппер       | feat(V1.17.0h4) — guard + связка «Шиппер OFF ⇒ его строки в Экономике disabled» |

Каждый шаг = отдельный feature-PR в `main`. Между шагами — пауза на
подтверждение Илья: «нужен ли подтумблер в этом модуле, и если да —
какой именно».

## 9. Тесты

- `tests/test_db_module_toggles.py` — CRUD, изоляция per-workspace, дефолт
  OFF, bump_cache_version.
- `tests/test_api_module_toggles.py` — 4 эндпоинта, права (admin POST →
  403), 400 при пустом reason, 409 при no-op.
- `tests/test_module_guard.py` — декоратор: OFF → silent, ON → вызов
  оборачиваемого handler'а, кеш-инвалидация после write.
- На шагах 7.1–7.4 — точечные:
  `test_triggers_off_silent.py`, `test_horoscope_off_no_cron.py`,
  `test_press_release_off_no_publish.py`,
  `test_shipper_off_economy_lines_disabled.py`.

## 10. Открытые вопросы (решаются на шагах 7.1–7.4)

- **Триггеры (7.1):** есть ли подтумблеры? (наш текущий тезис — нет, у
  каждого триггера уже есть свой ON/OFF).
- **Гороскоп (7.2):** нужен ли подтумблер «утренняя авторассылка»?
- **Пресс-релизы (7.3):** нужен ли подтумблер «авто-публикация по
  расписанию»? Ручная отправка под тумблер не идёт.
- **Шиппер (7.4):** не дублируем настройки Экономики; решаем точку
  применения guard (один guard на входной handler или несколько на местах
  Экономики, где Шиппер начисляет).

**Правило для всех будущих модулей** (запомнить в `feedback_*`): новый
тумблер добавляется ТОЛЬКО там, где есть осмысленное независимое поведение;
дублирование с существующими настройками — запрещено.

## 11. Риски

- **Гонка кеша бота**: ws_id у бота читается с задержкой 30 с (или быстрее
  через version-bump). Для шага 7.0 это приемлемо. Если на 7.1 окажется
  ощутимо медленно — снизим TTL до 5 с.
- **Backfill для workspace=1**: если миграция ошибочно включит модуль,
  который у Вити фактически не должен быть включён — Витя выключит сам
  одним кликом. Невозможно случайно включить чужой модуль из-за per-ws PK.
- **Удаление localStorage**: пользователь, который успел «подключить» в
  старом UI, увидит после деплоя новое состояние. Это ожидаемо (старое
  состояние было локально и без значения для бота).
