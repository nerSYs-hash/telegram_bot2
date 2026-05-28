# Дорожная карта к полной изоляции workspace-ов

> **Цель проекта** (Илья 28.05.2026): добавили бота в чат → всё работает само в этом workspace, без беготни. Полная изоляция WS друг от друга: чаты, статистика, права, регистрация, журнал. Один бот = много изолированных «миров».
>
> **Текущий процент готовности: ~80%** (28.05 Этап A T7+T8/9 — код готов и зелёный локально).

## 🔴 28.05 ~16:00 ИНЦИДЕНТ: история Pulse была смешана с PositivЭ

См. memory `incident_pulse_history_merged_2026_05_28`. Закрыто Вариантом B:
- DELETE из user_stats/chat_stats/messages/topics/journal_messages/etc. строк с date<2026-05-25 или chat_id∉PositivЭ.
- Балансы users сохранены полностью (@ares0255 и др.).
- Бэкап `pre_pulse_history_purge_20260528_160257` сохранён.

Урок: ДО merge-операций ВСЕГДА проверять что лежит в целевом ws.



## 📌 Прогресс Этапа C (V1.17.0M1-...)

| Task | Что | Статус |
|---|---|---|
| C1 | `admin_moderation._admin_dest` + миграция 4/5 callsites (досье, карточка заявки) | ✅ V1.17.0M1 |
| C2 | `anketa_edit_handlers._rebuild_and_update` + 5 callers per-ws | ✅ V1.17.0M2 |
| C3 | `bug_tracker_handlers` chat_id per-ws (BUG_THREADS — dead, оставлен) | ✅ V1.17.0M3 |
| C4 | `exit_survey_handlers` admin-чат per-ws (отчёт ухода) | ✅ V1.17.0M4 |
| C5 | `command_handler` /setup-команды (4 места) | 🔜 |
| C6 | `send_applications_button` startup — итерация по всем ws | 🔜 |
| C7 | Журнал-канал legacy fallback (`settings.journal_channel_id` → удалить) | 🔜 |

## 📌 Прогресс Этапа A (V1.17.0L1-...)

| Task | Что | Статус |
|---|---|---|
| T1 | `is_ws_admin()` в `bot_core/ws_role.py` + тесты | ✅ V1.17.0L1 |
| T2 | `owner_handlers._is_owner` per-ws + 27 callsites + тесты | ✅ V1.17.0L2 |
| T3 | `bingo_handlers._is_owner_user` per-ws + тесты | ✅ V1.17.0L3 |
| T4 | `lottery_handlers._is_owner_user` per-ws + тесты | ✅ V1.17.0L4 |
| T5 | `titles_handlers` owner-check | ⏭ skip (нет owner-check, есть только destination main_admin_id для DM) |
| T6 | `admin_moderation._is_strict_owner` per-ws + 3 deputy gates | ✅ V1.17.0L5 |
| T7 | `message_handler.is_user_excluded` per-ws + caller + тесты | ✅ V1.17.0L6 |
| T8 | Локально `I_WS_RBAC=1` + регресс-тесты (383/383) | ✅ 28.05 |
| T9 | Прод `I_WS_RBAC=1` + критерий приёмки | 🔜 (ждёт Илью для приёмки) |



## ✅ Уже работает (80%)

| Аспект | Состояние |
|---|---|
| Таблицы `workspaces` / `workspace_members` / `bot_chats` | Есть на проде, активная БД 40 МБ |
| `bot_chats.role IN ('main','admin','journal')` per ws | ✅ |
| Бот фильтрует сообщения per-ws (`_gate_target_chat` через `resolve_gate_chat`) | ✅ |
| Бот фильтрует админ-чат per-ws (фикс k22) | ✅ |
| Статистика `user_stats` per-ws (M1 Stats Backbone, 27.05) | ✅ |
| Журнал per-ws (`bot_chats.role='journal'`) | ✅ |
| Модули per-ws (`module_toggles`) | ✅ |
| Onboarding: бот добавлен в чат → авто-создание ws + member + bot_chat | ✅ (Подпроект #2) |
| Сайт: per-ws авторизация (`workspace_rbac` + middleware `X-Workspace-Id`) | ✅ |
| Сайт: API `/api/workspaces/*` per-ws CRUD | ✅ |
| Сайт: список членов/чатов из `workspace_members` + `bot_chats` | ✅ |
| Сайт ↔ Бот: фикс 3.2 mirror `users.is_admin` при add админа с сайта | ✅ |
| Бот ↔ TG: фикс k23 `promote_chat_member` при add админа из бот-панели | ✅ |
| Бот ↔ Сайт: фикс k23 INSERT `workspace_members` при add из бота | ✅ |
| **`chat_stats` per-ws — все поля сводно (msgs/words/active/replies/mentions/media)** | ✅ V1.17.0k27 + backfill k28 |
| **Пульт Владельца — `_is_owner` per-ws через workspace_members** | ✅ V1.17.0L2 (Этап A T2) |
| **Bingo/Lottery — `_is_owner_user` per-ws** | ✅ V1.17.0L3/L4 (Этап A T3/T4) |
| **`admin_moderation` strict_owner gates (назначение/снятие замов) per-ws** | ✅ V1.17.0L5 (Этап A T6) |
| **`message_handler.is_user_excluded` per-ws (mining gate)** | ✅ V1.17.0L6 (Этап A T7) |
| **`OWNER_ID` глобал — Pulse-safe fallback, основной путь per-ws** | ✅ V1.17.0L2/L5/L6 (Этап A) |
| **`is_owner_or_deputy()` через `bot_core.ws_role.is_ws_owner`** | ✅ (раньше через подпроект I, сейчас полноценно живёт) |

## ⚠️ Работает частично

| Аспект | Что не так | Куда фиксить |
|---|---|---|
| `journal-канал` для ws=1 | Хранится одновременно в `bot_chats.role='journal'` И в `settings.journal_channel_id` (legacy fallback). TG-меню «Канал N» пишет в settings, сайт читает из bot_chats | Этап C |
| Onboarding UX | Технически бот создаёт ws, но юзеру не приходит явная инструкция «иди на сайт залогинься» | Этап E |
| Этап A flip на проде | Код залит, локально 383/383 зелёный. На проде `I_WS_RBAC=1` уже стоит. Нужна ручная приёмка Ильи (добавить юзера на сайте → проверить что бот сразу его признаёт) | T9/Этап A |
| **Экономика real-time** | `get_dynamic_economy_config` читает БД через `db.get_econ`, но wrapper хардкодит `_DEFAULT_WS_ID=1` (`database/db_manager.py:688`). Для ws=1 PositivЭ работает, для ws=2+ нужен ws_id из контекста сообщения | Параллельно с Этапом B |

## ❌ Не работает (нарушает изоляцию)

| Аспект | Проблема | Куда фиксить |
|---|---|---|
| **`db_friend.py` / `pulse_bot.db`** | Вторая БД для регистрации/заявок/блэклиста/замов/инвайтов БЕЗ `workspace_id`. На ws=2 анкеты пойдут в общую очередь, ЧС будет глобальный, замы Pulse станут замами PositivE. **Треть бота не изолирована.** | Этап B |
| `ADMIN_CHAT_ID` хардкод в `admin_moderation.py` (10 мест) | Карточки заявок, досье, кнопки панели — отправляются в `ADMIN_CHAT_ID` из `.env`. ws=2 не сможет получать свои заявки в свой admin-чат. Чек прав (`_is_strict_owner`) уже per-ws (T6), но destination отправки — нет. | Этап C |
| `APPLICATIONS_THREAD_ID` / `DOSSIER_THREAD_ID` хардкод | Треды берутся из `.env`, не из `bot_chat_topics.kind`. ws=2 без своих тредов = заявки идут в Pulse-тред | Этап C |
| `Site/backend/main.py` (старый сайт-backend) | Endpoints per-chat (`/api/admin/{chat_id}/...`), не per-ws. Скорее всего deprecated, но если используется — нарушает изоляцию | Этап B/проверить |
| Регистрация (анкета) при заявке | `CHAT_ID` хардкод в `registration.py` для `get_chat_member`. Анкета привязана к одному чату | Этап B |
| Центр подключений на сайте | Нет единого UI. Журнал-канал только в боте; «где админка» дублируется бот/сайт; нет «создать тред в admin-чате при подключении». Bug-треды/BBS нельзя подключить без правки .env | Этап C (расширенный) |

## 🗺️ Дорожная карта (5 этапов)

### Этап A — Single source of truth для прав (1-2 сессии)
**Цель:** одна правда о правах. Решает «3 системы прав».

- Бот проверяет права через `workspace_members.role` (с учётом chat_id → ws_id).
- `users.is_admin/is_owner` → derived view, вычисляется из `workspace_members`.
- TG `promoteChatMember` → побочный эффект при INSERT/DELETE в `workspace_members` (триггер уровня кода).
- `OWNER_ID` → удаляется как глобал, заменяется на `resolve_ws_role(ws_id, user_id) == 'owner'`.
- `is_owner_or_deputy` → переписан через workspace_members.

**Критерий приёмки:** добавил юзера админом на сайте → бот в чате этого ws сразу его признаёт, в других ws игнорирует. Удалил с сайта → во всех 3 точках сразу снято.

### Этап B — db_friend → multi-tenant (2-3 сессии)
**Цель:** изоляция регистрации/заявок/ЧС/замов.

- ALTER `users` (pulse_bot.db) / `applications` / `admins` / `blacklist` / `invite_links` — добавить `workspace_id`. Сид существующих → ws=1.
- Все запросы `db_friend.*` — принимают `workspace_id` параметром.
- Регистрация перестаёт быть привязанной к одному `CHAT_ID`. При входе в любой чат, привязанный к ws, открывается анкета этого ws (если включена).
- ЧС в одном ws не блокирует юзера в другом.
- Deputies, invite_links — per-ws.

**Критерий приёмки:** юзер заходит в ws=2 → анкета настроек ws=2. В ws=1 заблокирован → в ws=2 всё открыто.

### Этап C — ADMIN_CHAT_ID + треды per-ws (1 сессия)
**Цель:** заявки/досье/кнопки идут в админский чат и треды своего ws.

- Все `ADMIN_CHAT_ID` отправки заменить на `resolve_admin_chat(context, ...)`.
- `APPLICATIONS_THREAD_ID` / `DOSSIER_THREAD_ID` / `BUG_THREAD_*` → `resolve_thread(kind)`.
- Журнал в `settings.journal_channel_id` для ws=1 → перенести в `bot_chats.role='journal'`, удалить fallback.
- TG-меню бота «Журнал → Канал N» → пишет в `bot_chats`, не в `settings`.

**Критерий приёмки:** owner ws=2 жмёт «Новые заявки» → карточки приходят в его админ-чат, не в Pulse-админ-чат.

### Этап D — chat_stats фикс (1 короткая сессия)
**Цель:** все поля сводной статистики чата пишутся.

- Найти где обновляется `chat_stats.total_messages` / `active_users` / `total_chars` — починить ON CONFLICT (по аналогии с user_stats фиксом из k8a).
- Backfill потерянных полей из `user_stats` SUM (за дни где есть user_stats но нет chat_stats).

**Критерий приёмки:** график «сообщения по дням» на сайте показывает реальные цифры для всех дней.

### Этап E — Onboarding UX до конца (1 сессия)
**Цель:** юзеру не нужно ничего объяснять.

- Когда бот добавлен в новый чат:
  - Авто-создание ws ✅ (есть)
  - DM-сообщение владельцу: «✅ Подключил твой чат «X». Зайди на сайт <ссылка> для настройки.»
  - Авто-вход на сайт через Telegram OAuth с переходом сразу на свой ws.
- На сайте «онбординг-туториал» для нового владельца (модули, заявки, статистика).
- Уведомление «всё готово» когда основные модули включены.

**Критерий приёмки:** Илья даёт ссылку на бота другу → друг создал группу, добавил бота → друг получил DM-инструкцию → друг зашёл на сайт через TG-login → видит свой ws с базовым набором модулей и пустой статистикой → начинает писать в чате → статистика растёт. Без участия Ильи.

## 🎯 Приоритет

Илья ставит цель «полная изоляция». Сверху вниз по важности для этой цели:

1. **Этап A** — критичен. Без one-source-of-truth прав — любая правка может развалить.
2. **Этап B** — критичен. Без него треть бота (регистрация/заявки/ЧС) общая. Для SaaS-онбординга юзеров `db_friend` обязательно multi-tenant.
3. **Этап C** — необходим для ws=2 (заявки/досье идут в свои треды).
4. **Этап D** — UX-фикс для статистики на сайте. Не блокирует, но видно невооружённым глазом.
5. **Этап E** — после A-D всё уже работает. E — это polish и автоматизация UX.

## ⏱️ Оценка

| Этап | Время | Риск |
|---|---|---|
| A | 1-2 дня | Средний (трогает права везде) |
| B | 2-3 дня | **Высокий** (treть бота, нужен бэкап + тесты) |
| C | 0.5-1 день | Низкий (механическая замена + хелперы готовы) |
| D | 0.5 дня | Низкий |
| E | 1 день | Низкий (в основном фронт + DM-bot-message) |

**Итого: 5-7 рабочих дней** до 100% изоляции.

## Связано

- `core_truth_workspace_isolation` (memory) — формулировка цели
- `idea_centralized_rbac_2026_05_28` (memory) — детали Этапа A
- `blocker_before_new_ws_2026_05_28` (memory) — Группы 1-4 закрыты сегодня, Группа 5 = sanity (работает)
- `docs/AUDIT_hardcoded_chat_ids_2026-05-28.md` — карта для Этапа C
- `docs/AUDIT_db_friend_2026-05-28.md` — карта для Этапа B
- `docs/SPEC_multi_tenancy_completion.md` — общая спека M1-M8
