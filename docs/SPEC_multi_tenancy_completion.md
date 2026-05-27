# 🔴 SPEC: Multi-tenancy Completion (SaaS Readiness)

**Статус:** СВЕРХСРОЧНО · стартуем СР 27.05.2026
**Owner:** Илья + Claude
**Блокер:** ПОДКЛЮЧЕНИЕ НОВЫХ WS ОСТАНОВЛЕНО до завершения этой спеки
**Цель:** через 1-2 недели любой новый владелец подключает бота и **всё работает изолированно по его ws** (статистика, экономика, журнал, BBS, кабинет, токены, профиль).

---

## Контекст
Multi-tenancy мигрировался поэтапно с мая 2026. Готово ~30%: таблицы workspaces, RBAC, Switcher, connect-flow, partial economy/press-release. **НЕ готово 18 областей** — каждая показывает Pulse-данные вместо данных нового ws.

PositivЭ (ws=4) подключён 25.05 как тестовый стенд → выявлено что:
- статистика на сайте → Pulse-цифры
- статистика в боте (/stats, /top) → Pulse
- сообщения нового чата выкидываются `message_handler.py:204`
- кабинет/баланс/токены — Pulse
- журнал/анкеты/BBS — Pulse

**Это не баг — это незавершённая миграция.** Подробный анализ: `session_2026_05_25_stats_multitenant`.

---

## Полная таблица дыр (18 областей)

| # | Область | Где сломано | Серьёзность |
|---|---|---|---|
| 1 | Статистика сайт | `api.py:_compute_stats`, `_build_daily/monthly_history`, `_widget_*` | 🔴 |
| 2 | Статистика бот /stats | `handlers/Stats/*`, `handlers/commands/top_commands.py` | 🔴 |
| 3 | Сообщения чата (single-chat gate) | `handlers/message_handler.py:204` | 🔴 |
| 4 | Майнинг пульсов | `handlers/messages/mining_logic.py` | 🔴 |
| 5 | Топ-5 | `handlers/commands/top_commands.py` | 🔴 |
| 6 | Реакции | `handlers/messages/events_logic.py` | 🔴 |
| 7 | Журнал событий | `handlers/journal_handlers.py` | 🔴 |
| 8 | BBS (анкеты профилей) | `handlers/BBS/*`, env `BBS_THREAD_ID` | 🔴 |
| 9 | Анкеты заявок (регистрация) | `handlers/registration_conversation.py`, `admin_moderation.py` | 🔴 |
| 10 | Чёрный список | `database/db_friend.py` | 🔴 |
| 11 | Лотерея | `handlers/lottery_handlers.py` | 🔴 |
| 12 | Донаты | `handlers/donate_handlers.py` | 🔴 |
| 13 | Подарки | `handlers/gift_handlers.py` | 🔴 |
| 14 | Курс / Банк | `api.py`, `db_settings` | 🔴 |
| 15 | Кабинет/токены сайт | `bot_core/web_auth.py` | 🔴 |
| 16 | Триггеры | `handlers/triggers_handlers.py` | 🟡 (module_toggles частично) |
| 17 | Шиппер | `handlers/shipper_logic.py` | 🟡 |
| 18 | Регистрация-анкета (Pulse-текст) | `handlers/registration_conversation.py` | 🟡 |

Частично готовое (требует валидации, не переписывания): пресс-релиз, combo/sprint, экономика модули, RBAC, connect-flow, my_chat_member.

---

## Правило done для каждой области
1. Миграция: все таблицы области имеют `workspace_id NOT NULL`.
2. Все SELECT/INSERT/UPDATE используют `current_ws_id()` (`api.workspace_rbac`).
3. Тест изоляции: `tests/test_<area>_ws_isolation.py` — два ws, данные ws=1 не видны в ws=2 и наоборот.
4. Бэкфил: исторические данные → `workspace_id = 1` (Pulse).
5. Документ в `docs/CHANGELOG.md` + bump версии.

---

## Порядок выполнения (8-12 сессий)

### Подпроект M1 — Stats Backbone (1-2 сессии)
- Миграция `user_stats.workspace_id`.
- #1 Статистика сайт + #2 Статистика бот + #4 Майнинг + #5 Топ + #6 Реакции.
- E2E: «ws=2 не видит цифр ws=1».

### Подпроект M2 — Message Pipeline (1 сессия)
- #3 message_handler multi-chat.
- Включить `H_RUNTIME_WS=ON` на проде после smoke.
- E2E: сообщения нового чата пишутся в его `user_stats`.

### Подпроект M3 — Журнал & События (1 сессия)
- #7 Журнал + проверка событий (join/leave/kick) per-ws.

### Подпроект M4 — Заявки/BBS (1-2 сессии)
- #8 BBS thread per-ws (в `workspaces.settings_json` или новая колонка).
- #9 Заявки регистрации per-ws (`APPLICATIONS_THREAD_ID` уезжает в `workspaces`).
- #18 Текст анкеты — настраиваемый (или skip-вариант для не-Pulse-тематики).

### Подпроект M5 — Экономика-2 (1-2 сессии)
- #10 ЧС per-ws.
- #11 Лотерея per-ws.
- #12 Донаты per-ws.
- #13 Подарки per-ws.
- #14 Курс / Банк per-ws.

### Подпроект M6 — Кабинет (1 сессия)
- #15 Токены/баланс на сайте — JWT с активным ws.

### Подпроект M7 — Модерация (1 сессия)
- #16 Триггеры per-ws (есть module_toggles, нужен SQL-фильтр).
- #17 Шиппер per-ws (settings).

### Подпроект M8 — Финал (1 сессия)
- e2e smoke для нового ws: подключить тестовый ws=99, прогнать все 18 областей.
- Документ `docs/SAAS_READINESS_CHECKLIST.md` — чек для новых владельцев.
- Снять блокер «не подключать новые ws».

---

## Расписание
- **Пн 26.05** — Илья отдых, я делаю SPEC доводку (если попросит).
- **Ср 27.05** — старт M1 Stats Backbone.
- **Цель:** к Пн 9.06 — M1-M5 закрыты. К Пн 16.06 — M6-M8, снятие блокера.

## Стоп-правила (важно)
1. ❌ НЕ подключать новые ws (кроме тестового) до закрытия M8.
2. ❌ НЕ смешивать developer-readonly правки (висят локально) со stats fix — отдельной веткой после M1.
3. ❌ НЕ создавать новые модули/фичи до закрытия M8 — все ресурсы на multi-tenancy.
4. ✅ Каждая область закрывается с e2e-тестом изоляции, иначе не считаем done.

## Связанная память
- [[session_2026_05_25_stats_multitenant]] — диагностика двух главных дыр
- [[platform_pivot_2026_05_08]] — исходный SaaS-pivot
- [[pattern_current_ws_id]] — канонический паттерн фильтра
- [[session_2026_05_17_H_activation]] — H_RUNTIME_WS флаг
- [[PRODUCT_AREAS]] — карта продукта (нужно обновить блокер)
