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
