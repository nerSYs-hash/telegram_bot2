# 🏗 #0 — Engagement Engine (архитектурная спека)

> Запрошено Ильёй 16.05.2026 («разобрать #0»). Это **дизайн, не реализация** — обсуждаем, не кодим (Фаза A роадмапа не трогается).
> Контекст: 17 идей из `IDEAS_BACKLOG.md` — это **1 движок + контент**. Здесь — движок.
> Принцип №1: **обобщаем существующий `mining_logic.py`, НЕ переписываем с нуля.** Экономика работает в проде — ломать нельзя.

---

## 1. Зачем движок (проблема)

Сейчас каждая механика жила бы своим кодом: ачивки считали бы свои счётчики, квесты — свои, battle-pass — свои, промокоды — свою выдачу. Это N таблиц прогресса, N мест выдачи наград, N багов рассинхрона. Плюс всё надо сделать **per-workspace** (SaaS) и включаемым тумблером.

**Решение:** один core из 5 слоёв. Контент-идеи (#1,#5,#6,#7,#15,#17…) становятся **строками конфига**, а не кодом.

```
СОБЫТИЕ ──▶ [1 Event Bus] ──▶ [2 Counters] ──▶ [3 Objective Registry+Evaluator]
                                                          │
                              [5 UI/Claim] ◀── [4 Reward Dispatcher] ◀──┘
```

---

## 2. Что УЖЕ есть в коде (фундамент, обобщаем)

Из `handlers/messages/mining_logic.py` (прочитано):
- **Извлечение события** из `telegram.Message` (text/photo/video/voice/audio/gif/reply/thread) — `process_mining_reward()`. → зародыш слоя 1.
- **Счётчики по окнам** 1ч/12ч/24ч — `_query_user_sprint_metrics()` (из `user_stats`+`messages`). → зародыш слоя 2.
- **Реестр целей**: `SPRINTS_CONFIG` (`target/hours/coeff/metric/allowed_threads`), `COMBO_COEFFICIENTS`, `PENALTY_COEFFICIENTS`. → зародыш слоя 3 (но захардкожен в .py).
- **Evaluator**: `check_completed_sprints()`, `calculate_instant_combos()`, `calculate_social_combos()`. → слой 3.
- **Выдача**: `db.update_user_balance` + `db.add_transaction` + claim-таблицы `combo_claims/sprint_claims` + бафф `users.mining_buff_*`. → зародыш слоя 4.
- **Конфиг из БД**: `get_dynamic_economy_config()` + `db.get_econ()` + master-switch `db.is_econ_section_enabled('mining')`. → паттерн для per-workspace конфига.
- **Scheduler**: APScheduler уже в проекте (видно по venv).
- Титулы: `db_titles.py` (готовый получатель наград). Топы: `handlers/Stats/*`.

**Вывод:** движок = вынести эти зашитые в `mining_logic.py` паттерны в **обобщённый, конфигурируемый, per-workspace слой**, оставив экономику одним из его consumer'ов.

---

## 3. Пять слоёв

### Слой 1 — Event Bus (нормализация событий)
Единая точка: бот публикует нормализованное событие вместо того, чтобы каждая фича сама лезла в `Message`.

```
Event = { workspace_id, user_id, chat_id, thread_id, type, payload, ts }
type ∈ { message_sent, media_sent(kind), reaction_given, reaction_received,
         reply_sent, reply_received, payment(/pay), reactor_donate,
         command_used(cmd), voice_chat_started/ended, chat_join,
         daily_login, shop_purchase, lottery_win, bingo_line/fullhouse, … }
```
- Источник: `message_handler.py` / `handle_reaction` / `reactor_handlers.py` / `donate` уже ловят эти события — добавляем **один вызов `engine.emit(event)`** рядом, аддитивно, ничего не ломая.
- Consumers подписаны: экономика (как сейчас), ачивки, квесты, лягушка, Око Пульса, «самый самый».
- Не обязательно персистить все события — переиспользуем существующие `messages`/`user_stats` как источник истины; шина — диспетчер в рантайме.

### Слой 2 — Counters store (обобщённые счётчики)
Generic-замена `_query_user_sprint_metrics`.
```
engagement_counters(workspace_id, user_id, metric, window_key, value, updated_at)
PK (workspace_id, user_id, metric, window_key)
```
- `window_key`: `lifetime` / `2026-05-16` (day) / `2026-W20` (week) / `2026-05-16T14_1h` / `season:1` — формат окон уже есть в `_get_sprint_window_key()`.
- Инкремент из Event Bus. Чтение — для evaluator и UI.
- Долгие метрики ачивок (#1: «намайнено всего», «дней в боте») = окно `lifetime`.

### Слой 3 — Objective Registry + Evaluator (контент = данные)
Реестр целей в БД (а не в .py) — это и есть «Стол Крафта» для Гримуара (#3) и редактируемые квесты (#5).
```
engagement_objectives(
  workspace_id, objective_id, kind, config_json, reward_json,
  toggle_key, season_id, levels_json, enabled, schedule_json)
kind ∈ { achievement(×4 уровня), daily_quest, weekly_quest,
         streak, combo, sprint, riddle, hidden_trigger, post_of_day }
config_json: { metric, target, window, allowed_threads, composite[…] }
```
- Evaluator обобщает `check_completed_sprints` / `calculate_instant_combos`: на событие → пересчитать релевантные objectives юзера → вернуть «выполненные/новый уровень».
- Ачивки (#1) = objective с `levels_json` (4 порога ×4 награды).
- Квесты (#5) = objectives + ежедневный рандом-сэмпл N штук (Scheduler пишет «активные сегодня» юзеру).
- Загадки (#7) = objective с `hidden_trigger` + текст-обёртка (триггер не показывается).
- **Содержимое (100 квестов / 30 загадок / 20 BP)** грузится сидом в эту таблицу (`data/quests_seed.json`), не хардкод.

### Слой 4 — Reward Dispatcher (единая выдача)
Одна функция `grant_reward(ws, user, reward_spec, source)` — единственное место начисления.
```
reward_spec ∈ { pulses(n) | title(id,ttl) | buff(mult,ttl) |
                lottery_ticket(n) | bingo_card(n) | promo_code(pool) |
                cosmetic(id) | privilege(id) }
```
- Внутри: переиспользует `db.update_user_balance` + `db.add_transaction` (как сейчас «Тайное Комбо/Спринт»), `db_titles`, `users.mining_buff_*`.
- Идемпотентность через claim-таблицы (паттерн `combo_claims`/`sprint_claims` обобщить в `engagement_progress`).
- Промокоды (#8) — это reward-type + отдельный вход `/code`.

### Слой 5 — Progress / Claim / UI
```
engagement_progress(workspace_id, user_id, objective_id, level,
                    progress, status, updated_at, claimed_at)
engagement_rewards_pending(workspace_id, user_id, reward_json, source,
                    created_at, claimed_at)   -- очередь для «💰 Забрать награды»
```
- `/profile` (#9) = UI-хаб: читает progress/counters, рисует прогресс-бары/паспорт.
- Кнопка «💰 Забрать награды» (#6) → claim из `rewards_pending` → `grant_reward` → гифка-сундук (тактильная выдача).

---

## 4. Multi-tenancy (обязательно)
- Все 4 новые таблицы — с `workspace_id` в PK (как `user_stats`/`chat_stats` после V1.17.0a16).
- Конфиг/тумблеры через паттерн `get_econ`/`section_toggles` (per-workspace).
- ⚠️ **Блокер:** `[multi_tenancy_pk_debt]` (composite PK для `economy_settings`/`section_toggles`) надо закрыть до 2-го workspace — движок усугубит долг, если не починить.
- Free/paid overlay (`[paid_overlay_idea]`): дефолтные objectives — free; кастомные (Стол Крафта #3) — paid. Реестр это поддерживает через `workspace_id` + `enabled`.

---

## 5. Синергия с #14 (Smart Topic Router)
Слой 1 (Event Bus) и #14 оба правят `message_handler.py` и оба убирают хардкод `THREAD_IDS` (`mining_logic.py:92-97`). **`allowed_threads` в objectives должны ссылаться на роли веток из `topic_routes` (#14), а не на числовые ID.** ⇒ #14 (= Подпроект H) логично делать **перед/вместе** со слоем 1 движка. Это сцепка Фазы A↔B.

---

## 6. Порядок сборки (внутри #0, после Фазы A)

| Шаг | Что | Риск | Зависит |
|---|---|---|---|
| 0.1 | Event Bus — `emit()` рядом с существующими хендлерами (аддитивно) | низкий | #14 (роли веток) |
| 0.2 | Counters store (обобщить `_query_user_sprint_metrics`) | низкий | 0.1 |
| 0.3 | Objective Registry + Evaluator (вынести SPRINTS/COMBO в БД) | **средний** (живая экономика) | 0.2 |
| 0.4 | Reward Dispatcher (централизовать выдачу) | средний | 0.3 |
| 0.5 | Progress/Pending + Claim-UI в `/profile` (#9) | низкий | 0.4 |
| 0.6 | Per-workspace конфиг + тумблеры + фикс PK-долга | **блокер SaaS** | — |
| 0.7 | Scheduler-хуки (рандом дейликов, стрик-ресет, сезон, Лягушка, expiry кодов) | низкий | 0.3 |

**Стратегия миграции:** движок поднимается **рядом** с `mining_logic.py`, экономика становится первым consumer'ом постепенно (strangler-pattern). Никакого «переписать всё сразу».

---

## 7. Открытые вопросы по #0 (обсудить)
1. **#14 перед #0?** Подтверждаем: Smart Topic Router (= Подпроект H) идёт раньше слоя 1, иначе `allowed_threads` снова захардкодим.
2. **Рефактор экономики:** обобщаем `mining_logic` инкрементально (strangler) или замораживаем его и строим движок только для нового контента? (Рекомендую strangler.)
3. **PK-долг:** чинить `[multi_tenancy_pk_debt]` в рамках 0.6 или раньше?
4. **Хранение событий:** шина рантайм-only (дёшево) или персист `engagement_events` для аналитики/Око Пульса (#11)? (#11 хочет историю — возможно нужен лог.)
5. **Контент-сид:** формат `data/quests_seed.json` — единый для ачивок/квестов/загадок? (Рекомендую да — один реестр.)
