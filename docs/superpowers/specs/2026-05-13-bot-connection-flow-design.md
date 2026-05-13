# Bot Connection Flow — дизайн

**Дата:** 2026-05-13
**Подпроект:** #2 из 6 (платформенный pivot Pulse → ChatKeeper-style SaaS)
**Зависимости:** Подпроект #1 (Multi-tenancy foundation, готов V1.17.0a22)
**Статус:** Дизайн на ревью

## Контекст

После Подпроекта #1 у нас есть `workspaces`, `workspace_members`, `bot_chats`, middleware `WorkspaceContext` и декоратор `@pulse_only`. Все Pulse-данные находятся в `workspace_id=1`. Middleware для unknown-чатов использует fallback на ws=1 — это временная мера; в проде новые чаты сейчас невозможно подключить как отдельный workspace.

Этот подпроект делает то, без чего multi-tenancy остаётся "архитектурой в вакууме": **новый владелец сообщества может через сайт привязать свой Telegram-чат и получить отдельный workspace**.

## Цели

- **Само-обслуживание онбординга**: владелец чата без участия Вити подключает бота, получает кабинет, видит свой чат, может пригласить помощников.
- **Безопасное создание workspace**: только реальные владельцы чатов (= те кто добавил бота) попадают в `workspace_members.role='owner'`. Случайное добавление чужим — отвергается.
- **Pulse-данные изолированы**: Pulse-анкета (`/start` flow) запускается только для ws=1, не для других сообществ.
- **Несколько сообществ под одним аккаунтом**: один Telegram-юзер может владеть N workspace, каждый со своим набором чатов.
- **Composite PK debt закрыт**: 7 таблиц (`economy_settings`, `economy_section_toggles`, `branding_settings`, `user_stats`, `user_stats_hourly`, `chat_stats`, `topics`) пересоздаются с `(workspace_id, …)` PK — теперь второй workspace физически может сидеться.

## Non-goals (отложено)

- **Конструктор регистрационной анкеты** — модуль `registration_form` для не-Pulse сообществ. Подпроект #4.
- **Передача owner** другому юзеру. Позже.
- **Удаление workspace** с очисткой данных. Позже.
- **Billing**, тарифы. Подпроект #6.
- **Per-workspace stats UI** (графики, метрики). Подпроект #5.
- **Каталог модулей**, включение/выключение фич per workspace. Подпроект #4.

## Поток подключения (happy path)

```
1. Юзер заходит в бота @Pulse_On_bot → /start
   └─ Бот в DM: «Привет, я Pulse Bot. Чтобы подключить чат — открой сайт.»
      [Кнопка: Открыть сайт]

2. Юзер на сайте логинится через Telegram Login Widget
   └─ POST /api/auth/telegram → сессия (httpOnly cookie)
   └─ Если у юзера нет workspace → дашборд показывает карточку «БЕЗ ЧАТА → Подключить чат» (уже есть)

3. Юзер жмёт «Подключить чат» → модалка «5 простых шагов» (уже есть)
   └─ CTA «Открыть Telegram» → https://t.me/Pulse_On_bot?startgroup=true

4. Юзер выбирает свою группу → подтверждает добавление → даёт права админа

5. Бот ловит `my_chat_member` event с new_status in ('member','administrator')
   ├─ resolve from_user.id (кто добавил)
   ├─ check #1: user_id есть в `site_users`?
   │   └─ НЕТ → бот пишет в чат «❌ Тот кто меня добавил, не зарегистрирован
   │            на сайте: <ссылка>» → leaves чат → return
   ├─ check #2: chat_id уже есть в `bot_chats`?
   │   └─ ДА → бот пишет «❌ Чат уже привязан к другому сообществу.» → leaves → return
   └─ всё ОК:
      ├─ CREATE workspace(name=chat.title, owner=from_user, plan='free', is_pulse_themed=0)
      ├─ INSERT workspace_members(ws_id, from_user, role='owner')
      ├─ INSERT bot_chats(chat_id, ws_id, added_by=from_user)
      ├─ в чат: «✅ Сообщество подключено. Управление — на сайте.»
      └─ в DM владельцу: «✅ Чат «<title>» добавлен в твой кабинет.»

6. Сайт через polling (или SSE) видит новый workspace → карточка
   обновляется: «БЕЗ ЧАТА» → «Мои сообщества: [<title>]»
```

## Поток `/start` в боте

```
/start без параметров
└─ DM-приветствие + кнопка «Открыть сайт»

/start join_<workspace_id>
└─ Резолвит workspace
   ├─ ws.is_pulse_themed=1 (Pulse) → текущий registration flow (анкета)
   └─ ws.is_pulse_themed=0 → простой welcome: «Добро пожаловать в <name>»

/start own
└─ DM-приветствие для «будущего владельца» + кнопка «Открыть сайт»
```

## Entity-модель (delta к #1)

Новая таблица:

```sql
CREATE TABLE site_users (
  user_id        INTEGER PRIMARY KEY,           -- = Telegram user_id
  username       TEXT,
  first_name     TEXT,
  last_name      TEXT,
  photo_url      TEXT,                          -- от Telegram Login Widget
  auth_date      INTEGER NOT NULL,              -- unix ts последнего логина
  hash_verified  INTEGER NOT NULL DEFAULT 0,    -- bool: hash от TG прошёл проверку
  created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE site_sessions (
  session_id     TEXT PRIMARY KEY,              -- uuid4
  user_id        INTEGER NOT NULL REFERENCES site_users(user_id),
  created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at     TEXT NOT NULL,                 -- created_at + 30 days
  user_agent     TEXT,
  ip             TEXT
);
CREATE INDEX idx_site_sessions_user ON site_sessions(user_id);
```

Изменения в существующих:

```sql
-- bot_chats: + added_by_user_id, + title, + chat_type, + added_at
ALTER TABLE bot_chats ADD COLUMN added_by_user_id INTEGER;
ALTER TABLE bot_chats ADD COLUMN title            TEXT;
ALTER TABLE bot_chats ADD COLUMN chat_type        TEXT;
ALTER TABLE bot_chats ADD COLUMN added_at         TEXT;
```

Composite PK debt fix — 7 таблиц через rebuild-pattern:

```sql
-- Пример для economy_settings:
CREATE TABLE economy_settings__new (
  workspace_id INTEGER NOT NULL,
  key          TEXT    NOT NULL,
  value        TEXT,
  PRIMARY KEY (workspace_id, key)
);
INSERT INTO economy_settings__new SELECT workspace_id, key, value FROM economy_settings;
DROP TABLE economy_settings;
ALTER TABLE economy_settings__new RENAME TO economy_settings;
```

Аналогично: `economy_section_toggles(workspace_id,category)`, `branding_settings(workspace_id,key)`, `user_stats UNIQUE(workspace_id,user_id,date)`, `user_stats_hourly UNIQUE(workspace_id,user_id,date,hour)`, `chat_stats UNIQUE(workspace_id,date)`, `topics UNIQUE(workspace_id,chat_id,thread_id)`.

Миграция: `database/migrations/composite_pk_fix.py` с `up()`/`down()` и backup.

## API

| Метод | Путь | Auth | Назначение |
|---|---|---|---|
| POST | `/api/auth/telegram` | — | Telegram Login Widget callback. Принимает `id, hash, auth_date, …` от Telegram, проверяет HMAC по `BOT_TOKEN`, апсертит `site_users`, создаёт session cookie. |
| POST | `/api/auth/logout` | session | Удаляет session_id из `site_sessions`. |
| GET | `/api/me` | session | Возвращает `{user_id, username, photo_url, workspaces: [...]}`. |
| GET | `/api/workspaces` | session | Список workspace где session.user_id состоит. С полями `{id, name, role, members_count, chats_count, plan, is_pulse_themed}`. |
| GET | `/api/workspaces/:id` | session + member | Детали workspace + список членов + список чатов. |
| POST | `/api/workspaces/:id/members` | session + owner | Пригласить помощника: `{user_id, role}`. role ∈ ('admin','moderator'). |
| DELETE | `/api/workspaces/:id/members/:user_id` | session + owner | Убрать члена. Owner себя удалить не может. |
| PATCH | `/api/workspaces/:id` | session + owner | Переименовать (только `name` пока). |

Middleware `require_session`: читает cookie `session_id`, ищет в `site_sessions`, проверяет `expires_at > now`, кладёт `session.user_id` в request scope. Истёкшие сессии → `401`.

Авторизация уровня workspace: `require_member(role_min='moderator')` — проверяет членство и роль в нужном WS. Несоответствие → `403`.

## UI на сайте

Все компоненты — из `Admin_SITE/components/shared/` (DS V1.16.14): `<Button>` (primary/secondary/ghost/danger), `<Card>` (accent='blue'|'violet'|'pink'|'amber'|'emerald'), `<Toggle>`, `<StyledSelect>`. Радиус везде `rounded-2xl` (16px). Hover на primary CTA — Aceternity glow. Шрифты: лейблы `text-[10px] uppercase tracking-widest font-black text-gray-400`, заголовки `text-base font-black text-gray-900`, тело `text-sm font-medium text-gray-700`.

### 1. Страница логина (новая)

`/login` — единственный экран до сессии. Центрированный `<Card padding="xl" accent="blue" glow>`:
- Логотип Pulse, `text-2xl font-black`
- Подпись «Войди через Telegram чтобы управлять своими сообществами», `text-sm text-gray-500`
- Telegram Login Widget (iframe от Telegram, виджет 5-го размера, corner radius 16)
- Внизу мелким `text-[10px] uppercase tracking-widest text-gray-400` — «Powered by Pulse SaaS»

### 2. Дашборд — состояние «нет чатов» (уже есть, расширяем)

Текущая карточка «БЕЗ ЧАТА → Подключить чат» в `AdminDashboard.jsx:5070-5089` остаётся. Модалка 5-шагов остаётся (`:5176-5228`). Меняется только источник `profileData.bot_username` — теперь из `/api/me`, а не захардкоженный.

### 3. Дашборд — состояние «есть чаты» (новое)

Заменить захардкоженный блок «Чат» (`:5091-5122` — `joined_at`/`last_message`/`total_messages`) на **список сообществ**:

```
<Card padding="lg" accent="blue">
  <h3 class="font-black text-gray-900 text-xs uppercase mb-3">
    <Users class="mr-2 text-blue-500" size={14}/> Мои сообщества
  </h3>
  <div class="space-y-2">
    {workspaces.map(ws => (
      <button onClick={() => navigateToWorkspace(ws.id)}
              class="w-full flex items-center justify-between p-3 bg-gray-50 rounded-2xl
                     hover:bg-blue-50 hover:border-blue-200 transition-all">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center">
            <MessageCircle size={16} class="text-blue-600"/>
          </div>
          <div class="text-left">
            <div class="font-black text-sm text-gray-900">{ws.name}</div>
            <div class="text-[10px] uppercase tracking-widest font-bold text-gray-400">
              {ws.role} · {ws.members_count} участников
            </div>
          </div>
        </div>
        <ChevronRight size={16} class="text-gray-400"/>
      </button>
    ))}
  </div>
  <button onClick={() => setShowConnectChat(true)}
          class="mt-3 w-full flex items-center justify-center gap-2 py-2.5
                 border-2 border-dashed border-blue-200 rounded-2xl
                 text-blue-600 font-black text-xs uppercase tracking-wide
                 hover:bg-blue-50 transition-all">
    <Plus size={14}/> Подключить ещё чат
  </button>
</Card>
```

### 4. Страница workspace (новое)

`/workspaces/:id` — детали сообщества. Сверху `<Stepper>` (если есть, иначе breadcrumb). Три секции (каждая — `<Card accent>`):

**A. Общее** (accent=blue):
- Имя (редактируемое только owner, через inline-edit с `<Input>` когда сделают компонент)
- Тариф (`plan: free`) — placeholder для #6
- Toggle `is_pulse_themed` — disabled для не-Pulse юзеров, видно только developer

**B. Чаты** (accent=emerald):
- Список `bot_chats` для этого workspace
- Каждый чат: title, chat_type (group/supergroup), added_at, added_by
- CTA «Подключить ещё чат» → та же модалка 5-шагов

**C. Помощники** (accent=violet):
- Таблица членов: avatar, username, role (chip: owner/admin/moderator), joined_at
- Owner всегда сверху, без удаления
- CTA «Пригласить помощника» (primary button) → модалка:
  - Input «Telegram username или ID»
  - `<StyledSelect>` роль (admin / moderator)
  - Lookup: ищем в `site_users`. Если не найден — текст «Этот юзер ещё не логинился на сайте. Попроси его войти через Telegram-кнопку.»
  - CTA «Добавить» (primary, loading state на Aceternity glow)
- Кнопка «Удалить» рядом с каждым (`<Button variant="danger" size="sm">`), confirm-модалка

## Бот — `my_chat_member` handler

Новый файл `handlers/bot_membership.py`:

```python
async def on_bot_added_to_chat(update, context, db):
    """ChatMemberHandler: bot's own membership changed."""
    new = update.my_chat_member.new_chat_member
    if new.user.id != context.bot.id:
        return  # не про нас
    if new.status not in ('member', 'administrator'):
        return  # left/kicked — обработать отдельно (removal)

    chat = update.my_chat_member.chat
    from_user = update.my_chat_member.from_user

    # check 1: registered on site?
    site_user = db.get_site_user(from_user.id)
    if not site_user:
        await context.bot.send_message(chat.id,
            "❌ Тот кто меня добавил, не зарегистрирован на сайте.\n"
            f"Зайди сюда: {SITE_URL}/login")
        await context.bot.leave_chat(chat.id)
        return

    # check 2: chat already bound?
    existing_ws = db.get_workspace_by_chat(chat.id)
    if existing_ws:
        await context.bot.send_message(chat.id,
            "❌ Этот чат уже привязан к другому сообществу на сайте.")
        await context.bot.leave_chat(chat.id)
        return

    # create workspace
    ws_id = create_workspace(db, name=chat.title or f"Чат {chat.id}",
                              owner_user_id=from_user.id)
    add_member(db, ws_id, from_user.id, role='owner')
    add_bot_chat(db, chat.id, ws_id, added_by=from_user.id,
                 title=chat.title, chat_type=chat.type)
    invalidate_cache(chat.id)

    await context.bot.send_message(chat.id,
        f"✅ Сообщество «{chat.title}» подключено к Pulse SaaS.\n"
        f"Управление — на сайте: {SITE_URL}")
    await context.bot.send_message(from_user.id,
        f"✅ Чат «{chat.title}» добавлен в твой кабинет.\n"
        f"Зайди на сайт чтобы настроить: {SITE_URL}")
```

Регистрация в `bot.py.setup_handlers()`:

```python
from telegram.ext import ChatMemberHandler
self.application.add_handler(
    ChatMemberHandler(self.on_bot_added_to_chat,
                      ChatMemberHandler.MY_CHAT_MEMBER)
)
```

`/start` обновляется в `handlers/commands/system_commands.py`:

```python
async def start_command(update, context, db):
    args = context.args  # /start <param>
    user_id = update.effective_user.id

    # /start join_<ws_id>
    if args and args[0].startswith('join_'):
        ws_id = int(args[0][5:])
        ws = db.get_workspace(ws_id)
        if not ws:
            await update.message.reply_text("❌ Сообщество не найдено.")
            return
        if ws['is_pulse_themed']:
            # Pulse anketa flow — current registration_conversation
            return await start_pulse_registration(update, context, db)
        # generic welcome
        await update.message.reply_text(
            f"👋 Добро пожаловать в «{ws['name']}»!\n"
            f"Ты получишь информацию от ботa в чате сообщества.")
        return

    # /start own → site
    # /start без параметров → site
    await update.message.reply_text(
        "Привет 👋 Я Pulse Bot.\n\n"
        "Чтобы подключить свой чат — открой сайт.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Открыть сайт", url=SITE_URL)
        ]]))
```

Текущая `registration_conversation` (Pulse-анкета) теперь триггерится только из `/start join_1` для Pulse-сообщества. Это **не ломает существующих юзеров Pulse** — они либо уже зарегистрированы, либо приходят через welcome в чате Pulse Москва, где кнопка ведёт на `/start join_1`.

## Изменения в middleware

`bot_core/workspace_context.py.resolve_workspace_middleware`: убрать fallback `ws=1` для unknown-чатов. Вместо — `ws_ctx = None`. Декораторы `@pulse_only` уже корректно скипают `None`. Это безопасный шаг — production fallback больше не нужен после #2.

Для **DM** (нет `effective_chat.id` как группового) middleware ставит `ws_ctx=None` — handlers сами решают (большинство DM-команд глобальные: /start, /help, /menu).

## Безопасность

| Угроза | Митигация |
|---|---|
| Чужой добавил бота в мой чат как admin (хочет угнать workspace) | Только админ чата может добавить бота с правами. Если у злоумышленника был доступ — это уже скомпрометированный чат, не наша зона. |
| Telegram Login Widget hash подделан | Проверка HMAC по `BOT_TOKEN` в `/api/auth/telegram`, отказ если hash не совпадает. Стандартная процедура Telegram. |
| Session hijacking | `httpOnly`+`secure`+`samesite=lax` cookie. 30 дней TTL. Logout удаляет из `site_sessions`. |
| Owner добавляет случайно левых людей через `POST /members` | Lookup в `site_users` — только зарегистрированные. Помощник видит сообщество только после самостоятельного логина. |
| Member из бывшего workspace продолжает видеть данные через старую сессию | Каждый API проверяет `workspace_members` на каждый запрос (не кешируем). Удалённый член сразу теряет доступ. |
| Composite PK debt → дубликаты записей при втором workspace | Закрываем rebuild-pattern миграцией (часть этого подпроекта). |

## Testing

- **Unit** (pytest):
  - `test_on_bot_added_to_chat`: 4 кейса (happy / not registered / already bound / left status)
  - `test_start_command_routing`: `/start`, `/start join_1`, `/start join_42`, `/start own`
  - `test_auth_telegram_hash_verify`: верный / поддельный HMAC
  - `test_workspace_members_api`: list / add / delete / role permissions
  - `test_composite_pk_migration`: round-trip on real db copy
- **Integration**: telethon-like мок update'ов, проверка что `workspaces`/`bot_chats`/`workspace_members` создаются с правильными значениями
- **Manual smoke** на staging:
  - 2-й тестовый чат подключаем под отдельным TG-аккаунтом
  - Проверяем что Pulse-чат не сломался
  - Помощника приглашаем, проверяем что видит workspace, но не может назначить других

## Открытые вопросы

1. **Бот сам не может покинуть чат с админскими правами** — если `from_user` не зарегистрирован, `leave_chat` сработает только если бот не последний админ. Edge case: что если чат пустой? Решение: пишем сообщение и оставляем бота в чате, owner может убрать вручную. Зафиксируем "best-effort leave".
2. **Telegram Login Widget требует HTTPS** — `puls-chat.ru` уже HTTPS, ok. Bot domain в BotFather → `/setdomain puls-chat.ru`.
3. **Refresh workspaces на дашборде** — polling каждые 30 сек или SSE? Для MVP — polling, простой `useEffect` с `setInterval`. SSE → подпроект #5.
4. **`bot_chats.added_at` для существующих Pulse-чатов** — backfill `NOW()` при миграции (приближённо).
5. **Welcome-сообщение от Pulse-чата с кнопкой /start join_1** — Pulse Москва ещё не имеет такого welcome. Добавлять в #2 или оставить как есть? Предлагаю добавить: единое welcome для всех новых членов (кнопка → `t.me/Pulse_On_bot?start=join_1`).
