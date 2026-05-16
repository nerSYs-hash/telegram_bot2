# Multi-tenancy Foundation — дизайн

**Дата:** 2026-05-08
**Ветка:** `Интеграция-множетсвенные-пользователи`
**Подпроект:** #1 из 6 (платформенный pivot Pulse → ChatKeeper-style SaaS)
**Статус:** Дизайн на ревью

## Контекст

Pulse эволюционирует из single-community бота (только Pulse Москва, MAIN_ADMIN_ID=Витя) в **мультитенантную SaaS-платформу** в стиле ChatKeeper. Любой владелец Telegram-сообщества сможет подключиться, получить базовую статистику + игровой движок (пульсы, экономика). Дополнительные модули (BBS, Активности, и т.д.) включаются опционально per workspace, часть бесплатно, часть по подписке. Pulse-тематические модули (ВИЧ/гей-консультирование) изолированы и доступны только верифицированным Pulse-network воркспейсам.

Это первый из 6 подпроектов. Текущая задача — заложить **фундамент мультитенантности**: схема БД, миграция существующих данных, изоляция в коде, ролевая модель.

## Цели

- **Workspace** становится первичной единицей данных. Все user-state и workspace-state таблицы получают `workspace_id`.
- Существующие Pulse-данные сохраняются без потерь, переезжают в `workspace_id=1` (Pulse Москва, owner=Витя).
- Юзер с одним Telegram-аккаунтом может состоять в нескольких воркспейсах с разными ролями и независимыми данными (Discord/Slack-style).
- Система ролей в воркспейсе обёрнута поверх существующей RBAC (V1.14.4) — переиспользуем 35 per-resource actions как набор для каждой роли.
- Pulse-тематические модули доступны только воркспейсам с `is_pulse_themed=true`. Изоляция на уровне приложения, не БД.

## Non-goals (для этого подпроекта)

- **Bot connection flow** — как новый чат подключается, что бот пишет владельцу. Это подпроект №2.
- **Web auth** — логин владельца, сессии, workspace switcher в UI. Подпроект №3.
- **Module catalog** — таблицы модулей и переключатели. Подпроект №4.
- **Stats** — изолированная аналитика per workspace. Подпроект №5.
- **Billing** — тарифы, платежи. Подпроект №6.
- **Миграция SQLite → PostgreSQL** — отложена до 50+ активных воркспейсов.

## Entity-модель

```
USER (Telegram-аккаунт)
  ├── id (= telegram user_id)
  ├── username, first_name, last_name (Telegram identity)
  └── created_at_global (когда впервые встретили в любом WS)

WORKSPACE (сообщество, например «Pulse Москва»)
  ├── id (auto-increment, workspace_id=1 → существующий Pulse)
  ├── name (display, e.g. «Pulse Москва»)
  ├── owner_user_id (FK → users.id)
  ├── is_pulse_themed (bool, default false)
  ├── plan (text, default 'free')
  ├── created_at, updated_at
  └── settings_json (workspace-level настройки)

WORKSPACE_MEMBER (юзер × workspace, с ролью)
  ├── workspace_id (FK)
  ├── user_id (FK)
  ├── role ('owner' | 'admin' | 'moderator')  — preset для RBAC
  ├── joined_at
  └── PRIMARY KEY (workspace_id, user_id)

CHATS (Telegram чаты, привязка к workspace)
  ├── chat_id (Telegram)
  ├── workspace_id (FK) — какому WS принадлежит этот чат
  ├── title, type (group/channel/forum)
  └── added_at, added_by_user_id
```

**Cardinality:**
- Один user → много workspaces (членство в нескольких сообществах)
- Один workspace → один owner (но может быть передан другому)
- Один workspace → много admin/moderator
- Один workspace → много чатов (главный чат + чат заявок + модераторский — все в одном WS)
- Один чат → ровно один workspace

## Изменения в схеме БД

### Новые таблицы

```sql
CREATE TABLE workspaces (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  name            TEXT NOT NULL,
  owner_user_id   INTEGER NOT NULL,
  is_pulse_themed INTEGER NOT NULL DEFAULT 0,  -- bool
  plan            TEXT NOT NULL DEFAULT 'free',
  settings_json   TEXT,                         -- JSON workspace-level
  created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (owner_user_id) REFERENCES users(user_id)
);

CREATE TABLE workspace_members (
  workspace_id INTEGER NOT NULL,
  user_id      INTEGER NOT NULL,
  role         TEXT NOT NULL CHECK (role IN ('owner','admin','moderator')),
  joined_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (workspace_id, user_id),
  FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id)      REFERENCES users(user_id)
);

CREATE INDEX idx_workspace_members_user ON workspace_members(user_id);
```

### Изменения в существующих таблицах (~52)

Шаблон ALTER для каждой workspace-state таблицы:

```sql
ALTER TABLE <table> ADD COLUMN workspace_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX idx_<table>_workspace ON <table>(workspace_id);
-- если есть запросы по (workspace_id, user_id) — составной индекс:
CREATE INDEX idx_<table>_ws_user ON <table>(workspace_id, user_id);
```

**Тенантизируем (~52):**
`anketa_edits`, `bbs_other_posts`, `bbs_profiles`, `bbs_reactions`, `bingo_cards`, `bingo_games`, `bot_chats`, `bot_chat_topics`, `branding_settings`, `bug_cards`, `challenges`, `chat_stats`, `combo_claims`, `daily_stats_summary`, `economy_cancellations`, `economy_history`, `economy_section_toggles`, `economy_settings`, `exit_interviews`, `hall_of_fame`, `journal_messages`, `lotteries`, `lottery_tickets`, `marketplace_services`, `messages`, `monthly_gift_participants`, `monthly_gifts`, `press_release_targets`, `press_release_templates`, `press_release_versions`, `reactor`, `referral_links`, `referral_seasons`, `referral_stats`, `scheduled_posts`, `shipper_matches`, `shipper_resonance_stats`, `sprint_claims`, `stat_events_log`, `title_packages`, `title_rub_requests`, `titles`, `top_activists_history`, `top_activists_percent`, `topics`, `transactions`, `trigger_violations`, `triggers`, `user_joins`, `user_stats`, `user_stats_hourly`.

**Глобальные (без workspace_id):**
- `users` — глобальный реестр Telegram-аккаунтов (hybrid identity).
- `exchange_rate_history` — глобальные курсы валют.
- `shipper_phrases` — общий corpus генератора (если используется как глобальный шаблон).
- `settings` — bot-level конфигурация (BOT_TOKEN, MAIN_ADMIN_ID, и т.п.).
- `sqlite_sequence` — служебная.

**Pulse-only активация:**
Таблицы `bbs_*`, `shipper_*`, `reactor`, `anketa_edits`, `exit_interviews` тенантизированы, но read/write происходит только если `workspace.is_pulse_themed=true`. Generic-воркспейсам эти модули недоступны на уровне приложения (роутер проверяет флаг до выполнения handlers).

## План миграции

### Подход: Big-bang в одном script-е, обратимый

Single dev (Илья), single live community (Витя), SQLite — фазированная миграция избыточна. Делаем atomic-миграцию с резервной копией:

1. **Снять backup** — `cp database/bot_database.db database/backup_pre_multitenancy_2026-05-08.db`.
2. **Создать миграционный скрипт** в `database/db_migrations.py`:
   - Создать `workspaces` table.
   - INSERT row workspace_id=1: name='Pulse Москва', owner_user_id=MAIN_ADMIN_ID (Витя), is_pulse_themed=1, plan='free'.
   - Создать `workspace_members` table.
   - INSERT Витя как owner workspace=1.
   - Опционально INSERT текущих существующих admin-ов (определить через старую систему прав).
   - Для каждой из ~52 таблиц: `ALTER TABLE ... ADD COLUMN workspace_id NOT NULL DEFAULT 1` + создать индексы.
3. **Обновить `bot_chats`** — все существующие чаты получают workspace_id=1.
4. **Обновить весь код** добавив `workspace_id` параметр в DB-функции (см. изоляция в коде ниже).
5. **Деплой за один раз** на staging/тест → smoke test → продакшен.

**Rollback план:**
- Backup восстанавливается из снимка.
- Миграционный скрипт также имеет `def downgrade()` который дропает workspaces/workspace_members и удаляет workspace_id колонки (`ALTER TABLE ... DROP COLUMN` через SQLite-обходной путь — пересоздать таблицу).

## Code isolation strategy

### Принцип

Все DB-функции, читающие/пишущие тенантизированные данные, **обязаны принимать `workspace_id` первым аргументом** (после `self`/`db`). Дисциплина + lint-rule (ниже).

### Реализация

1. **`get_workspace_id_from_chat(chat_id) → int`** — функция-резолвер: по telegram chat_id возвращает workspace_id из bot_chats. Кешируется в памяти. Используется в каждом обработчике сообщения как первый шаг.

2. **Контекстный объект `WorkspaceContext`**:
   ```python
   @dataclass
   class WorkspaceContext:
       workspace_id: int
       is_pulse_themed: bool
       plan: str
       member_role: Optional[str]  # роль текущего юзера в WS
   ```
   Создаётся в начале обработки каждого update'а. Прокидывается через handlers.

3. **Helper-обёртки в `db_manager.py`**:
   ```python
   def get_user_balance(self, ws_id: int, user_id: int) -> int:
       cur = self.conn.execute(
           'SELECT pulses FROM economy_history WHERE workspace_id=? AND user_id=? ORDER BY ts DESC LIMIT 1',
           (ws_id, user_id)
       )
       ...
   ```
   Каждая функция явно делает `WHERE workspace_id=?`. Аргумент обязательный, нет default.

4. **Lint-rule (опционально, в CI)**: regex grep для запросов `SELECT ... FROM <tenanted_table>` без `workspace_id` в WHERE. Либо AST-анализ. Для MVP — code review дисциплина.

5. **Pulse-themed gating** — на уровне роутера:
   ```python
   def pulse_only(handler):
       async def wrapper(update, ctx, ws_ctx, ...):
           if not ws_ctx.is_pulse_themed:
               return  # silent skip для не-Pulse WS
           return await handler(update, ctx, ws_ctx, ...)
       return wrapper

   @pulse_only
   async def bbs_handler(update, ctx, ws_ctx):
       ...
   ```

## Роли и интеграция с RBAC

Workspace роли — **пресеты** существующей RBAC (V1.14.4) per-user permissions (35 actions в каталоге).

| Роль       | Что включает |
|------------|---|
| **owner**     | Все 35 RBAC actions + `billing.*` + `workspace.delete` + `workspace.transfer_ownership`. Один на workspace. |
| **admin**     | Все RBAC actions кроме `billing.*` и `workspace.delete`. Может быть N. |
| **moderator** | Только `chat.moderate.*` + `stats.view` + `users.view`. Может быть N. |

При создании workspace_member-а с ролью X — RBAC permissions per-user заполняются из preset. Owner может потом override-ить indivudual actions через текущий RBAC UI.

**Изменение схемы RBAC:** существующая таблица permissions (per-user) получает `workspace_id` колонку. Один юзер может иметь разные permissions в разных воркспейсах.

## Update model

Стандартная SaaS-модель:
- **Один deploy** (backend + бот + сайт) → **обновление всех workspaces** мгновенно.
- Code one source-of-truth, нет per-tenant версий.
- DB schema migrations применяются ко всей БД (т.е. ко всем workspaces сразу).
- Pulse-only фичи деплоятся для всех, но read/write активны только для `is_pulse_themed=true`.
- Платные модули — после биллинга (подпроект 6) активируются по `workspace_features` таблице.

**Future-feature (не на MVP):** `workspace_features (workspace_id, feature_key, enabled)` для feature-flag-роллаута. Один deploy + постепенное включение per WS.

## Открытые вопросы (для будущих подпроектов)

- **Connection flow (#2):** как ровно происходит первая встреча — бот добавлен в чат, как создаётся workspace, как привязывается owner. Telegram Login Widget? Magic-код в чате?
- **Module catalog (#4):** какие модули отдельные сущности, как их каталогизировать (PR-релизы — модуль? стандарт?). Отдельная таблица `modules` + `workspace_modules`?
- **Pulse verification (#7):** как воркспейс становится `is_pulse_themed=true`. Ручная модерация Витей? Доменная привязка?

## Что меняется в существующем коде

Подсчёт высокого уровня:
- **db_manager.py + db_economy.py + db_*.py:** все DB-функции получают `workspace_id` первым аргументом. ~150-200 функций.
- **bot.py + handlers/:** все обработчики telegram-update'ов резолвят `workspace_id` в начале и прокидывают в DB-вызовы.
- **api.py (FastAPI):** все эндпоинты получают `workspace_id` из JWT-токена (после web-auth подпроекта №3, пока — из query-параметра или header X-Workspace-Id).
- **Frontend Admin_SITE:** workspace-context добавляется к запросам (после подпроекта №3 будет switcher). Сейчас на этапе подпроекта №1 — фронт не трогаем, остаётся работать в режиме «всегда workspace=1».

## Объём работы (оценка)

- Миграционный скрипт: ~1 день.
- Обновление `db_*.py` функций: ~2 дня.
- Обновление handlers + WorkspaceContext: ~2 дня.
- Тесты (миграция up/down, smoke-test всего бота на existing data): ~1 день.
- Итого: **~5-6 рабочих дней**, на одной feature-ветке без касания main.

## Следующие шаги

1. Юзер ревьюит этот спек.
2. После апрува — `superpowers:writing-plans` создаёт implementation plan с TDD-шагами.
3. Реализация на ветке `Интеграция-множетсвенные-пользователи` без касания main до полного теста.
