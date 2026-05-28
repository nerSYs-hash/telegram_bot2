# Audit — где хранится journal-канал PositivЭ (-1003930021144)

> Пункт **1.4** блокера `blocker_before_new_ws_2026_05_28`. Илья «привязал журнал через интерфейс» — пишет в TG и (как он сказал) на сайт, но в **списке чатов** на сайте не виден. Аудит — где реально лежит и почему сайт не показывает.

## Открытие

Журнал имеет **двойную систему хранения**:

### A. Per-workspace через `bot_chats.role='journal'` (новый путь, M3)
- `bot_core/ws_resolver.resolve_role_chat(conn, ws_id, 'journal')`.
- API endpoint `api/workspaces_routes.py:188` принимает `role: 'main'|'admin'|'journal'|null` и обновляет `bot_chats.role`.
- API `handlers/bot_membership.py:169-245` ставит роль на чат при подключении.

### B. Legacy через `settings.journal_channel_id` (старый путь, single-tenant)
- Ключи в таблице `settings` (`bot_database.db`):
  - `journal_channel_id` — главный канал журнала.
  - `journal_channel_id_2`, `journal_thread_id_2` — второй канал/тред.
  - `journal_channel_id_3`, `journal_thread_id_3` — третий.
- TG-интерфейс бота: «Панель Владельца → Журнал → Канал N» вызывает `handlers/journal_handlers.show_journal_channel_menu` → при привязке делает `db.set_setting('journal_channel_id', str(channel_id))`.
- ВНЕ `bot_chats` — никаких параллельных записей.

## Как `_get_journal_channel(chat_id)` выбирает

`handlers/journal_handlers.py:67-102` — кейс с известным `chat_id` события:
1. Через `resolve_workspace_for_chat` определяет ws.
2. Ищет `bot_chats.role='journal'` для этого ws.
3. Если нашёл → возвращает его.
4. Если ws=1 и не нашёл → fallback на `settings.journal_channel_id`.
5. Если ws≠1 и не нашёл → возвращает `None` (silent skip — не спамим чужой ws Pulse-журналом).

При вызовах без `chat_id` (log_trigger, log_admin_action и т.п.) — сразу `settings.journal_channel_id`.

## Что на проде PositivЭ (28.05)

- Канал `-1003930021144` хранится в `settings.journal_channel_id` (через TG-интерфейс).
- **НЕ записан в `bot_chats`** (поэтому сайт не видит — сайт читает только bot_chats per-ws).
- **`bot_database.db` имеет таблицу `settings` (key/value).** Это не та `settings`, которая в `db_friend.py/pulse_bot.db` — у нас две таблицы с одним именем в разных файлах. Здесь — основная.

## Почему пишет в TG и «на сайт» одновременно

Илья сказал «пишет в TG и на сайт». Скорее всего:
- **В TG** — бот, через `_get_journal_channel` → fallback на settings → шлёт в `-1003930021144`. ✅
- **«На сайт»** — возможно Илья имел в виду что событие появляется в Журнале на сайте. Но если bot_chats пустой по journal, и API сайта читает события через `journal/events` с фильтром по `bot_chats.role='journal'` → пусто. Это надо уточнить.

  Альтернатива: на сайте есть отдельный backend-роут, который читает `messages`/`stat_events_log` напрямую по chat_id из settings. Тогда события видны, но «в списке чатов» канал не показан (отдельный список чатов читает только bot_chats).

## Решение для Группы 2 блокера

Один insert при миграции выравнивает обе системы:

```sql
-- 1) Берём канал из settings
SELECT value FROM settings WHERE key = 'journal_channel_id';
-- = '-1003930021144'

-- 2) Вставляем в bot_chats как journal для ws=1 (PositivЭ)
INSERT INTO bot_chats(chat_id, workspace_id, role, ...)
VALUES (-1003930021144, 1, 'journal', ...);
```

Чтобы не было двойной правды:
- После миграции `_get_journal_channel(chat_id)` будет находить канал в `bot_chats` сразу — fallback на settings не сработает.
- Чтения через TG-меню «Канал N» оставить как есть (это второй/третий, разные роли).
- TG-меню «Канал 1» нужно перевести на запись в `bot_chats` через `db_workspaces.attach_chat_to_workspace` (вместо `db.set_setting`). Это правка в Группе 4 блокера.

## Что НЕЛЬЗЯ ломать

- `journal_channel_id_2/3` — это **второй и третий** каналы журнала (отдельные роли в TG-меню). Они тоже legacy, но **есть в проде**. После миграции на bot_chats — `bot_chats` должен поддержать множественные journal-роли per ws ИЛИ нужны отдельные роли `journal_2`/`journal_3`. Сейчас bot_chats CHECK CONSTRAINT принимает только `'main'|'admin'|'journal'` (см. `scripts/V1_17_0c1_add_chat_role.py`). Расширить CHECK при миграции.

## Связано

- `handlers/journal_handlers.py:67-102` — резолвер.
- `bot_core/ws_resolver.py` — per-ws.
- `database/db_workspaces.py:265` — attach_chat_to_workspace.
- `scripts/V1_17_0c1_add_chat_role.py` — миграция (если запускалась).
- Memory: `subproject_H_chat_roles_runtime`, `bot_removal_status_gap`.
