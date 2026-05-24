# Runbook: консолидация combo_claims / sprint_claims по workspace

**Дата:** 2026-05-25
**Версия:** V1.17.0k2
**Кто запускает:** Илья на проде, после планового бэкапа.

## Зачем

Артефакт connect-flow (до V1.17.0h) — Pulse-сообщество порождало по
workspace на каждый связанный чат (main / admin / journal). После
тенантизации combo_claims/sprint_claims строки получали `workspace_id`
того ws, в чьём чате юзер замайнил. Логически это один Pulse, физически
строки размазаны по ws=1/5/6.

Пока скрипт `consolidate_workspaces.py` (`scripts/consolidate_workspaces.py`)
не «видел» combo_claims/sprint_claims в своём safety-списке — после
консолидации ws5/ws6 → ws1 эти строки осиротевали бы навсегда.

V1.17.0k2:
- `database/db_workspaces.py:TENANT_TABLES` расширен на `combo_claims`,
  `sprint_claims` — теперь и cascade-чистка, и safety-проверка их видят.
- Новый скрипт `scripts/migrate_combo_sprint_workspaces.py` — точечная
  миграция строк с conflict-resolve по claimed_at.

## Pre-flight

```bash
# 1. убедиться что бот остановлен (или хотя бы майнинг)
systemctl status pulse-bot

# 2. ручной бэкап БД (скрипт делает свой, но лишний не помешает)
cp database/bot_database.db database/bot_database.db.pre_k2_$(date +%F)
```

## Что переносим

ws-источники, ws-цель — определяет Илья по проду. Стандартный план:
`5,6 → 1`.

## Dry-run (без --apply)

```bash
cd /opt/pulse_bot
python -m scripts.migrate_combo_sprint_workspaces \
    --db database/bot_database.db \
    --from 5,6 --into 1
```

Вывод покажет таблицу:

```
Table          From    Rows  Conflicts  Fresh moves
combo_claims      5     N1         C1           F1
combo_claims      6     N2         C2           F2
sprint_claims     5     ...
...
TOTAL                  SUM
```

- **Rows** — сколько строк сейчас на src
- **Conflicts** — сколько уже имеют дубликат на into (PK столкновение)
- **Fresh moves** — сколько уедет чистым UPDATE
- `Conflicts + Fresh moves = Rows`

## Apply

```bash
python -m scripts.migrate_combo_sprint_workspaces \
    --db database/bot_database.db \
    --from 5,6 --into 1 --apply
```

Скрипт:
1. делает бэкап `database/bot_database.db.pre_combo_sprint_migrate_<TS>`
2. в одной транзакции для каждой таблицы:
   - удаляет более **старую** строку из конфликтующей пары
     (PK = `(user_id, combo_name)` / `(user_id, sprint_name, window_key)`)
   - UPDATE-ит `workspace_id` оставшихся src-строк на into

## Verify

```sql
SELECT workspace_id, COUNT(*) FROM combo_claims  GROUP BY workspace_id;
SELECT workspace_id, COUNT(*) FROM sprint_claims GROUP BY workspace_id;
```

Должно остаться только `workspace_id=1` (для нашего сценария 5,6→1).

## Откат

Из бэкапа:

```bash
systemctl stop pulse-bot
cp database/bot_database.db.pre_combo_sprint_migrate_<TS> \
   database/bot_database.db
systemctl start pulse-bot
```

## Идемпотентность

Повторный запуск с `--apply` после успешной миграции = no-op
(скрипт обнаруживает `TOTAL=0` и завершается).

## Следующий шаг (опционально)

После того как combo/sprint консолидированы, можно запустить полную
ws-консолидацию `consolidate_workspaces.py`:

```bash
python -m scripts.consolidate_workspaces \
    --db database/bot_database.db --from 5,6 --into 1 --apply
```

Этот скрипт перевяжет `bot_chats` и удалит пустые ws5/ws6. Safety
теперь увидит combo/sprint и не даст удалить ws с непустыми claim-данными
(если миграция не была выполнена) — это и есть желаемое поведение.

## Связано

- `docs/superpowers/specs/2026-05-17-connect-flow-lifecycle-design.md` §C7
- `memory/pattern_current_ws_id.md`
- `memory/multi_tenancy_pk_debt.md`
