# Runbook — Multi-tenancy deploy (V1.17.0a1 → a21)

Дата создания: 2026-05-13. Версия: V1.17.0a21.

Цель: безопасно выкатить multi-tenancy фундамент в прод (single-tenant
режим, ws=1 Pulse Москва, никаких новых workspace ещё нет).

После деплоя поведение бота **идентично pre-V1.17**:
- middleware ставит fallback `ws=1, is_pulse_themed=True` для любого update,
- декоратор `@pulse_only` пропускает 100% хендлеров (т.к. Pulse=True),
- все wrapper'ы в `db_manager` прокидывают `workspace_id=1` placeholder.

---

## Pre-flight checklist

- [ ] Текущая ветка `Интеграция-множетсвенные-пользователи` смержена в `main`
      (по решению Вити 13.05 — сразу в main, минуя dev).
- [ ] `git log main` показывает коммиты `V1.17.0a1 … V1.17.0a22`.
- [ ] `pytest tests/test_multi_tenancy_migration.py tests/test_db_workspaces.py tests/test_workspace_context.py tests/test_economy_isolation.py` → 28 PASS локально.
- [ ] `python -c "import bot"` локально без ошибок.
- [ ] `MAIN_ADMIN_ID` в проде совпадает с локальным (Витя = 1283941769).

## Деплой шаги (прод сервер)

```bash
# 0. SSH на сервер, переход в каталог бота
cd /opt/pulse_bot   # см. server_structure.md
source venv/bin/activate

# 1. ОСТАНОВИТЬ бот — это критично, миграция меняет схему
sudo systemctl stop pulse_bot

# 2. РУЧНОЙ бэкап БД (помимо автобэкапа миграции)
cp database/bot_database.db database/bot_database.db.bak.pre_v17

# 3. Pull свежий код
git fetch origin
git checkout main
git pull --ff-only

# 4. Прогон миграции
python -m database.migrations.multi_tenancy
#    Ожидаемый output:
#    [backup] <auto-backup path>
#    [ok] tenantized <table>  ×50
#    [done] migrate_up complete

# 5. Smoke-check состояния
python scripts/check_migration_state.py
#    Ожидаемый output:
#    workspaces: [(1, 'Pulse Москва', 1, 'free')]
#    members: [(1, <MAIN_ADMIN_ID>, 'owner')]
#    [OK] migration state looks good

# 6. Smoke-импорт
python -c "import bot; print('bot import OK')"

# 7. Запуск
sudo systemctl start pulse_bot
sudo systemctl status pulse_bot   # должен быть active (running)

# 8. Smoke в боте (Telegram):
#    - /start в DM боту — отвечает
#    - сообщение в основном чате — экономика мигалится (см. в логах)
#    - открыть BBS → меню рисуется
#    - открыть Реактор → меню рисуется
#    - открыть Шипер (если включен) → меню рисуется

tail -f logs/bot.log    # следить минут 5 на наличие traceback
```

## Acceptance после деплоя

- В логах НЕТ `sqlite3.OperationalError: no such column: workspace_id`.
- В логах НЕТ `pulse_only skip` (если есть — значит middleware не отработал
  или ws_ctx не пробрасывается; критично).
- Журнал событий продолжает писать (`journal_messages` пополняется).
- Топы и /top работают.
- Экономика начисляется за сообщения (проверить `transactions` SELECT за
  последние 5 минут).

## Rollback (если что-то идёт не так)

### Способ 1 — простой (восстановление из бэкапа):
```bash
sudo systemctl stop pulse_bot
cp database/bot_database.db.bak.pre_v17 database/bot_database.db
git checkout <previous tag, e.g. V1.16.14u>
sudo systemctl start pulse_bot
```

### Способ 2 — миграция down (если код уже несовместим, но БД нужно
ОСТАВИТЬ с новыми данными):
```bash
sudo systemctl stop pulse_bot
python -m database.migrations.multi_tenancy down
#    Ожидание:
#    [ok] removed workspace_id from <table>  ×50
#    [done] migrate_down complete
git checkout <previous tag>
sudo systemctl start pulse_bot
```

Способ 1 быстрее и безопаснее — рекомендуется по умолчанию.

## Известные ограничения V1.17.0a21

1. **Composite PK debt** (см. `memory/multi_tenancy_pk_debt.md`):
   таблицы `economy_settings`, `economy_section_toggles`, `branding_settings`,
   `user_stats_hourly`, `user_stats`, `chat_stats`, `topics` имеют PK/UNIQUE
   без `workspace_id` — нельзя seed-ить для ws≠1. Фиксить **перед** onboarding
   2-го workspace (подпроект #2).
2. **journal/lottery/triggers/bingo/гифты** — пока НЕ тенантизированы (universal
   модули, но SQL inline без `workspace_id`). В single-tenant работают
   как до. Фиксить в подпроекте #4 (Module system) или V1.18.
3. **db_friend** (`pulse_bot.db`) — legacy small-bot БД, вне скоупа.
4. **users.joined_at** vs `workspace_members.joined_at` — `get_joined_users_count`
   считает по global `users.joined_at`. При втором workspace переписать через
   JOIN на `workspace_members`.

## Связанные документы

- Spec: `docs/superpowers/specs/2026-05-08-multi-tenancy-foundation-design.md` (если есть)
- Plan: `docs/superpowers/plans/2026-05-08-multi-tenancy-foundation.md` (если есть)
- Audit: `docs/AUDIT_SaaS_Coverage_2026-05-08.md`
- Memory:
  - `platform_pivot_2026_05_08.md` — стратегия SaaS pivot
  - `multi_tenancy_pk_debt.md` — composite PK долг
  - `session_2026_05_13_phase5.md` — Phase 5 итоги

---

## V1.17.0b — Bot connection flow + composite PK fix

**Подпроект #2** (Bot Connection Flow). Ветка: `feat/V1.17.0b-bot-connection-flow`.
Включает 15 коммитов V1.17.0b1-b15. Backend (DB+handler+API) + UI (4 React-компонента).

### Что нового

- **Composite PK fix** (b1) — rebuild 7 таблиц (`economy_settings`, `economy_section_toggles`,
  `branding_settings`, `user_stats_hourly`, `user_stats`, `chat_stats`, `topics`)
  с `PRIMARY KEY (workspace_id, ...)` — закрыт долг из a21.
- **bot_chats** расширен (b2): `added_by_user_id`, `title`, `chat_type`, `added_at`.
- **Само-онбординг** (b4-b5): `ChatMemberHandler.MY_CHAT_MEMBER` на добавление бота
  в чат → создаёт workspace с `owner_user_id = тот, кто добавил`, привязывает chat
  через `add_bot_chat`. Если from_user не зарегистрирован на сайте — leave_chat.
- **/start join_<ws>** (b6) — deep-link для приглашения участника в конкретный ws.
- **Middleware fallback убран** (b7) — unknown chats честно `ws_ctx=None` (защита
  от утечки Pulse-данных).
- **API** (b8-b11): `GET /api/workspaces`, `GET/{id}`, `POST/DELETE /members`, `PATCH /{id}`.
- **UI** (b12-b15): `WorkspaceList` (список на дашборде), `WorkspacePage`
  (детали+rename+чаты+помощники), `InviteMemberModal`, hook `useWorkspaces` с
  polling 30s.

### Deploy steps

После применения V1.17.0a21 и smoke прохождения:

```bash
# 1. На сервере: остановить бота, бэкап
sudo systemctl stop pulse_bot
cp /opt/pulse_bot/database/bot_database.db /opt/backups/bot_database.pre_b15.db

# 2. Pull
cd /opt/pulse_bot
git fetch origin
git checkout feat/V1.17.0b-bot-connection-flow   # или merge в main + checkout main

# 3. Миграции (идемпотентные, можно перезапускать)
.venv/bin/python -m database.migrations.composite_pk_fix
.venv/bin/python -m database.migrations.bot_chats_extend

# 4. Sanity check
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import bot; print('OK')"

# 5. Build UI и положить на nginx
cd Admin_SITE
npm install            # если node_modules не свежий
npm run build
cp -r dist/* /var/www/pulse-admin/

# 6. Запустить бота
sudo systemctl start pulse_bot
sudo systemctl status pulse_bot
```

### Smoke checklist после деплоя

1. Залогиниться на сайт **новым** TG-аккаунтом (не Витя)
2. Дашборд: empty state "Без чата"
3. В Telegram: создать тестовую группу, добавить `@Pulse_On_bot` как админа
4. В чате: ожидаемое сообщение «✅ Сообщество «...» подключено к Pulse SaaS»
5. В DM от бота: «✅ Чат «...» добавлен в твой кабинет»
6. Refresh сайт → карточка нового сообщества появилась
7. Open → «Помощники» → «Пригласить» → user_id Вити → admin → 200
8. Logout → login Витей → видит новый workspace с role=admin
9. Pulse-чат (workspace=1): BBS / Реактор / `/top` работают как раньше

### Rollback

```bash
sudo systemctl stop pulse_bot
cp /opt/backups/bot_database.pre_b15.db /opt/pulse_bot/database/bot_database.db
git checkout <prev tag, например V1.17.0a22>
sudo systemctl start pulse_bot
```

Миграция `composite_pk_fix` имеет down-функцию (rebuild обратно к старому PK),
но если есть данные нового workspace — они потеряются. Использовать только
вместе с откатом БД из бэкапа.

---

## V1.17.0d — Web Auth + per-WS RBAC (Подпроект #3)

Что меняется: сайт считает роль/права для **активного сообщества**
(заголовок `X-Workspace-Id`), middleware блокирует доступ к чужому
сообществу (403). JWT больше НЕ делает кого-либо глобальным владельцем —
только `DEVELOPER_ID` (Илья) имеет сквозной доступ.

### Pre-deploy (локально И на сервере, ДО рестарта)

```bash
python scripts/verify_ws_rbac_pulse.py     # обязан вернуть exit 0 (OK: ws=1 ...)
```

Если FAIL — НЕ деплоить: владелец Pulse не записан в `workspace_members`
как `owner`. Починить данные (см. `scripts/reset_workspace_owner.py`),
повторить проверку.

### Deploy

```bash
git pull --ff-only
sudo systemctl restart pulse_bot           # api в том же процессе → нужен рестарт
# фронт: статика уже в Admin_SITE/dist (закоммичена), nginx раздаёт напрямую
```

### Post-deploy smoke

1. Владелец Pulse логинится → видит «Pulse Москва», role=owner, меню полное
2. Второй владелец чужого ws логинится → видит ТОЛЬКО свой ws
3. Переключалка сообществ в шапке → меню/права меняются без релогина
4. Запрос к чужому ws (подменить X-Workspace-Id) → 403

### Rollback

```bash
git revert <диапазон V1.17.0d1..d11>   # либо checkout пред-тега
sudo systemctl restart pulse_bot
```

БД-миграций в #3 НЕТ (только код + ContextVar) — откат безопасен,
данные не теряются.
