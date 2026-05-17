# Subproject I — Bot per-Workspace Owner Recognition (Design Spec)

**Дата:** 2026-05-17 · **Версия:** V1.17.0f · **Ветка:** `feat/V1.17.0f-bot-per-ws-owner`
**Статус:** дизайн заапрувлен Ильёй, готов к writing-plans.

## Контекст / зачем

После активации Подпроекта H (бот резолвит чаты per-workspace за флагом
`H_RUNTIME_WS=1`, в проде с 17.05) на живом тесте вскрылось: Кирилл
(`8376708692`, owner ws=7 «Тест коннект») в ЛС с ботом идёт **как простой
участник**. Гейт H больше не блокирует его («ты заблокирован в Pulse 4ever»
ушло), но бот не распознаёт его как **владельца своего workspace**.

Причина — owner/admin в боте определяется **single-tenant**:
- `handlers/admin_moderation.py:932 _is_owner_or_deputy(user_id)` —
  `user_id == config.OWNER_ID` → `user_has("admins.view")` → `is_deputy()`;
  `user_has`/`is_deputy` бьют в legacy `pulse_bot.db` (одно-tenant роль).
- `handlers/commands/system_commands.py:20 get_main_reply_keyboard()` —
  `user_id == main_admin_id` / `db.get_user().is_owner` (флаги
  `bot_database.db.users`, одно-tenant) → Кирилл получает «❓ FAQ».

Per-WS RBAC уже сделан для **сайта** в Подпроекте #3
(`api/workspace_rbac.py:resolve_ws_role` — keystone, маппит
`workspace_members.role` → permissions-роль). Бот этого не использует.
Subproject I = бот-аналог: дать боту собственный keystone, резолвящий
владельца **per-workspace**, как H дал `resolve_gate_chat`.

## Цель

При `I_WS_RBAC=1` бот распознаёт пользователя как **владельца его
workspace** (owner-доступы, «Панель Владельца») по `workspace_members`,
а не по single-tenant `main_admin_id`/`config.OWNER_ID`. Pulse-владелец —
без регресса. Флаг OFF → байт-в-байт текущее поведение.

## Не-цели (scope guard)

- **Только owner-уровень.** Зам/админ/granular per-resource permissions в
  боте — НЕ трогаем (остаются single-tenant Pulse как сейчас). Полный
  per-resource RBAC в боте — отдельный будущий подпроект.
- **Кнопочный инвентарь не сохраняем.** Илья: большинство owner-кнопок
  бота всё равно урезается. Цель — *распознавание* владельца, не паритет
  каждой кнопки.
- Pulse-тематические owner-фичи (лотерея/банк/детализация,
  `== self.main_admin_id` в command_handler/message_handler) — вне
  MVP-спины (см. §2, фаза 2 опционально).
- Сайт (`api/*`) не трогаем — там per-WS RBAC уже есть (#3).

## §1. Архитектура — бот-keystone

Новый модуль **`bot_core/ws_role.py`**, единственный вход:

```python
resolve_bot_role(conn, context, user_id) -> str
    # 'developer' | 'owner' | 'deputy' | 'admin' | 'user'
is_ws_owner(conn, context, user_id) -> bool
    # MVP-предикат: роль in ('owner', 'developer')
```

- **Резолв ws переиспользует машинерию H** (без дублирования):
  - групповой чат → `ws_ctx` из `context.chat_data/user_data`
    (кладёт `resolve_workspace_middleware` в `bot.py`);
  - ЛС → `bot_core.ws_resolver.resolve_user_primary_workspace(conn, user_id)`
    (примитив H/e6, в проде): owner → admin → меньший `workspace_id`.
- Получив `ws_id`, зовёт **существующий
  `api/workspace_rbac.py:resolve_ws_role(conn, user_id, ws_id, DEVELOPER_ID)`**
  — не дублируем маппинг `workspace_members.role`→роль, переиспользуем
  keystone #3 (`owner`→owner, `admin`→deputy, `moderator`→admin,
  не член→user, `DEVELOPER_ID`=Илья→developer god-mode, проверяется первым).
- За флагом **`I_WS_RBAC`** (env, `_TRUTHY` как `H_RUNTIME_WS`, дефолт OFF).
  Хелпер `i_ws_rbac_enabled()` в `bot_core/ws_role.py`. Флаг OFF → keystone
  не вызывается на горячем пути, старая логика нетронута.

Один бот-keystone, тестируется изолированно (паттерн H
`resolve_gate_chat`). `api/workspace_rbac` импортируется ботом как
библиотека — модуль чистый (sqlite3 + ContextVar, без FastAPI-зависимостей
на нужных функциях).

## §2. Точки интеграции + Pulse-safe

**MVP-спина (2 точки покрывают «Кирилл = владелец»):**

| Точка | Сейчас (single-tenant) | `I_WS_RBAC=1` |
|---|---|---|
| `admin_moderation._is_owner_or_deputy(user_id, context=None)` | `user_id==OWNER_ID` → `user_has("admins.view")` → `is_deputy` | если флаг ON и `context`: `is_ws_owner(conn, context, user_id)` True → return True; **иначе старая логика как fallback** |
| `system_commands.get_main_reply_keyboard(db,user_id,main_admin_id,context=None)` | `user_id==main_admin_id` / `db.get_user().is_owner` | + `is_ws_owner(...)` → показать «👑 Панель Владельца» |

Сигнатурная проблема: `_is_owner_or_deputy(user_id)` не имеет `context`
(нужен для резолва ws). Решение: добавить **опциональный** `context=None`;
при `context=None` или флаг OFF → строго старое поведение (вызовы без
context остаются single-tenant — безопасный дефолт). Места вызова с
доступным `context`/`update` прокидывают его (адресный аудит ~6 вызовов
`_is_owner_or_deputy` в плане writing-plans).

**Прочие `== self.main_admin_id`** (`command_handler.py:488`,
`message_handler.py:625/646/811` — лотерея/банк/детализация): **фаза 2,
опционально** — провести через `is_ws_owner` если дёшево, но НЕ критерий
приёмки I (кнопки урезаются).

**Pulse-safe (флаг ON, Pulse-владелец `7536752126`):**
- `DEVELOPER_ID` (Илья) → `resolve_ws_role` = `developer` god-mode → owner
  везде, как раньше. ✅
- Витя `7536752126` — член `workspace_members` ws=1 role=`owner` (данные
  прода подтверждены 17.05) → `is_ws_owner`=True. ✅
- `user_id == OWNER_ID` остаётся **внутри** `_is_owner_or_deputy` как
  первый быстрый чек/fallback → даже при пустом membership-резолве
  Pulse-владелец не теряет доступ. **Байт-в-байт для Pulse.**
- Кирилл `8376708692`: в своём ws=7 (owner) → True; в Pulse-чате
  `-1003900924578` (не член ws=1) → не owner Pulse (корректная изоляция
  тенантов). ✅

**Откат:** убрать `I_WS_RBAC` из `.env` + рестарт → ровно старая логика.
Fallback-ветки НЕ удаляются — они и есть текущее поведение.

## §3. Тестирование + критерий приёмки

**Юнит — `tests/test_ws_role.py`** (in-memory `workspace_members`):
- owner ws=1 (Витя) → owner; owner ws=7 (Кирилл) в своём ws → owner;
  Кирилл в ws=1 → user; `DEVELOPER_ID` → developer в любом ws;
  не член → user; ЛС-резолв через `resolve_user_primary_workspace`
  (owner→admin→меньший ws).
- **Флаг OFF → `is_ws_owner` не на горячем пути; `_is_owner_or_deputy`
  с флагом OFF идентична до/после** (байт-в-байт гарантия — отдельный тест).

**Регресс-гейт:** полный `.venv\Scripts\python.exe -m pytest tests/ -q`
зелёный (база H = 167+, новые тесты I сверху, 0 регрессий).

**Smoke на проде (флаг ON, с Ильёй, как активация H):**
1. Илья в ЛС → «👑 Панель Владельца» на месте, панель открывается
   (Pulse без регресса).
2. Кирилл `8376708692` в ЛС → видит «👑 Панель Владельца» вместо «❓ FAQ»,
   панель открывается для ЕГО ws.
3. Кирилл в Pulse-чате `-1003900924578` → НЕ owner Pulse (изоляция).
4. Откат-проба: флаг OFF + рестарт → Кирилл снова участник, Илья без
   изменений.

**Критерий приёмки I (MVP):** при `I_WS_RBAC=1` Кирилл в ЛС распознаётся
ботом как владелец своего ws (Панель Владельца доступна), Pulse-владелец
без регресса, флаг OFF = байт-в-байт.

## Активация (путь A, как H)

Код за флагом → merge `feat/V1.17.0f-bot-per-ws-owner`→main→авто-деплой
(флаг OFF, байт-в-байт) → проверить прод чист → flip `I_WS_RBAC=1` в
`/root/PulsBot/.env` + рестарт pulsbot → smoke с Ильёй+Кириллом. Откат
мгновенный (убрать флаг + рестарт). БД-миграций нет (читаем существующий
`workspace_members`) → откат чистый.

## Self-Review

- Живая боль (2-й владелец не распознан в боте) → §2 спина
  (`_is_owner_or_deputy` + reply-keyboard), фундамент §1 keystone. ✅
- Keystone переиспользует `resolve_ws_role` (#3) и ws-резолв H — не
  дублируем, не переписываем. Strangler + флаг. ✅
- Pulse-safe: тройная защита (developer god-mode, owner-membership ws=1,
  `OWNER_ID` fallback) → байт-в-байт. ✅
- Скоуп зажат: только owner, 2 точки-спины, фаза 2 явно опциональна,
  сайт/granular/Pulse-фичи — не-цели. Достаточно для одного плана. ✅
- Зависимость: I осмыслен только при H ON (ws резолвится). Отдельный
  флаг `I_WS_RBAC` → независимый откат от H. ✅
- БД: `workspace_members` в `bot_database.db` (бот-conn). `resolve_ws_role`
  принимает `conn` → передаём бот-conn. `permissions.py`/`pulse_bot.db`
  для owner-MVP НЕ нужен (owner = membership-роль, не granular). ✅
