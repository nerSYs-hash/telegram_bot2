# Кастомные титулы — двухвалютная покупка через меню Баланс

**Дата:** 2026-04-30
**Версия бота:** V1.15.x → следующая `V1.16.0`
**Статус:** дизайн утверждён, ждёт ревью спека и плана реализации

---

## 1. Цель

Дать пользователю возможность купить «кастомный титул» (приписка к нику в чате через `set_chat_administrator_custom_title`) двумя способами:

- **Пульсы** — полностью автоматически: списание → ввод текста → применение.
- **Рубли** — заявка Владельцу: ввод текста → карточка в ЛС Владельцу с кнопками `[Подтвердить]`/`[Отклонить]` → автоматическое применение после клика.

Управление пакетами/ценами — у Владельца в его меню. Юзер заходит через `Баланс → 🏷 Титулы` или команду `/titles`.

## 2. Решения, принятые на брейнсторминге

| # | Вопрос | Решение |
|---|---|---|
| 1 | Связь с существующим «Чёрным рынком» | Переиспользуем `apply_title_to_user`/`cleanup_expired_titles`/`get_user_title` и таблицу `marketplace_services`. Из чёрного рынка кнопку покупки Тега убираем. |
| 2 | Модель оплаты за рубли | Заявка в БД + кнопка подтверждения у Владельца в ЛС. Юзер пишет Владельцу для оплаты вне бота. |
| 3 | Сетка сроков | CRUD пакетов у Владельца. Сидинг: 7д / 1мес / 3мес / 6мес / 1год. Поддержка пакета «Навсегда» (`duration_days=NULL`). |
| 4 | Смена текста активного титула | Платно в Пульсах. Цена в панели Владельца, `0` = бесплатно. |
| 5 | Покупка пакета поверх активного | **Продлеваем** — `expires_at += duration`, текст не меняем. |

## 3. Что переиспользуем (НЕ трогаем код)

- `handlers/shop_mechanics.py::apply_title_to_user(context, chat_id, user_id, title_text)` — `promote_chat_member` + `set_chat_administrator_custom_title`.
- `handlers/shop_mechanics.py::cleanup_expired_titles(context, db, chat_id)` — фон, снимает права после `expires_at`.
- `handlers/shop_mechanics.py::get_user_title(db, user_id)` — отображает `[TITUL]` в чате/топах.
- Таблица `marketplace_services` со `service_type='title'`, `content=текст_тега`, `expires_at=...`, `status='active'/'expired'`.

## 4. Что удаляем

- В UI «Чёрного рынка» (там, где он сейчас отрисован) — убираем кнопку покупки Тега. Сам код `shop_mechanics` остаётся.
- Активные титулы из `marketplace_services`, купленные в чёрном рынке, продолжают жить и истекают штатно.

## 5. База данных

### 5.1. `title_packages` — пакеты подписки

```sql
CREATE TABLE IF NOT EXISTS title_packages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    label           TEXT    NOT NULL,           -- "1 месяц", "Навсегда"
    duration_days   INTEGER,                    -- NULL = навсегда
    price_pulses    INTEGER NOT NULL,
    price_rub       INTEGER,                    -- NULL или 0 = «только за пульсы», рублёвая кнопка скрыта у юзера
    is_enabled      INTEGER NOT NULL DEFAULT 1,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_title_packages_sort ON title_packages(is_enabled, sort_order);
```

**Сидинг (`INSERT OR IGNORE`)** — заглушка, цифры Витя поправит:

| label | duration_days | price_pulses | price_rub | sort_order |
|---|---|---|---|---|
| 7 дней | 7 | 5000 | 100 | 10 |
| 1 месяц | 30 | 15000 | 300 | 20 |
| 3 месяца | 90 | 40000 | 750 | 30 |
| 6 месяцев | 180 | 70000 | 1300 | 40 |
| 1 год | 365 | 120000 | 2400 | 50 |

### 5.2. `title_rub_requests` — заявки на оплату рублями

```sql
CREATE TABLE IF NOT EXISTS title_rub_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    package_id      INTEGER NOT NULL,
    title_text      TEXT    NOT NULL,
    price_rub       INTEGER NOT NULL,           -- зафиксировано на момент создания
    duration_days   INTEGER,                    -- копия из package на момент создания (NULL = навсегда)
    status          TEXT    NOT NULL DEFAULT 'pending',
                    -- pending | approved | rejected | rejected_user_left | expired
    owner_msg_id    INTEGER,                    -- id сообщения с кнопками у Владельца (для редактирования)
    owner_chat_id   INTEGER,                    -- куда отправили (= ЛС Владельца)
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    decided_at      TEXT,
    decided_by      INTEGER,
    reject_reason   TEXT,
    FOREIGN KEY (package_id) REFERENCES title_packages(id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_title_req_status ON title_rub_requests(status, created_at);
CREATE INDEX IF NOT EXISTS idx_title_req_user ON title_rub_requests(user_id, created_at);
```

### 5.3. Новые ключи в `settings`

| key | default | назначение |
|---|---|---|
| `title_rename_price_pulses` | `50` | цена смены текста активного титула. `0` = бесплатно |
| `title_request_ttl_hours` | `48` | через сколько часов pending заявка автоматически становится `expired` |

### 5.4. Миграция

Новый модуль `database/db_titles.py`:
- `init_titles_tables(db)` — `CREATE TABLE IF NOT EXISTS` для двух таблиц.
- `seed_default_packages(db)` — `INSERT OR IGNORE` пяти строк из таблицы выше.
- CRUD-функции для пакетов и заявок (тонкие).

Вызов `init_titles_tables(self) + seed_default_packages(self)` — в `database/db_manager.py::__init__` рядом с другими init.

## 6. UI юзера

### 6.1. Точка входа

- `handlers/callback/callback_router.py::show_balance` — последняя кнопка `[🏷 Титулы]` (`callback_data="titles_menu"`).
- Команда `/titles` — алиас, ведёт в тот же экран.

### 6.2. Главный экран `titles_menu`

```
🏷 КАСТОМНЫЙ ТИТУЛ

Это твоя приписка к нику в чате — будет видна всем
рядом с твоим именем.

[Если активен:]
  Сейчас: «Кодер»
  Действует до: 12.05.2026 (осталось 8 дн)
  [или «Бессрочно» если duration_days=NULL]

  [💎 Купить / Продлить]
  [✏️ Изменить текст · 50 💎]   ← только если активен
  [🔙 Назад]
```

### 6.3. Flow покупки

```
Шаг 1 → выбор пакета (titles_pkg_<id>):
  Кнопки на каждый is_enabled пакет, в порядке sort_order.
  «Навсегда» — отдельным сортом или внизу, по выбору Владельца.

Шаг 2 → выбор валюты (titles_buy_pulses_<pkg_id> | titles_buy_rub_<pkg_id>):
  💎 N Пульсов               ← всегда
  💳 N ₽ — оплата у Вити     ← только если price_rub не NULL и > 0

Шаг 3a (Пульсы) → FSM TITLE_AWAIT_TEXT_PULSES:
  «✏️ Введи текст титула (1–16 символов).»
  → валидация → BEGIN IMMEDIATE → проверка баланса → списание →
    apply_title_to_user → INSERT/UPDATE marketplace_services →
    «✅ Готово, твой титул "Кодер" активен до DD.MM.YYYY»

Шаг 3b (Рубли) → FSM TITLE_AWAIT_TEXT_RUB:
  «✏️ Введи текст титула (1–16 символов).»
  → валидация → INSERT title_rub_requests(status='pending') →
    отправка карточки Владельцу в ЛС, owner_msg_id сохраняется →
    юзеру: «📨 Заявка №142 отправлена. Напиши Вите: tg://user?id=...
            Сумма: 300 ₽. Когда подтвердит — придёт уведомление.»
    [📩 Написать Вите] [❌ Отменить заявку (titles_cancel_req_<id>)]
```

### 6.4. Flow переименования

```
Активный титул: «Кодер»
Цена: <title_rename_price_pulses> 💎
Баланс: NN 💎

  [✏️ Сменить] [🔙 Назад]

→ FSM TITLE_AWAIT_RENAME →
  валидация → если price>0: BEGIN IMMEDIATE + списание →
  set_chat_administrator_custom_title(chat_id, user_id, new_text) →
  UPDATE marketplace_services SET content=new_text WHERE service_type='title'
                                  AND user_id=? AND status='active'
  → «✅ Титул сменён на "Хакер".»
```

### 6.5. FSM-состояния и fallbacks

`ConversationHandler` с тремя состояниями:
- `TITLE_AWAIT_TEXT_PULSES`
- `TITLE_AWAIT_TEXT_RUB`
- `TITLE_AWAIT_RENAME`

Fallbacks на всех состояниях: `/cancel`, `/start`, `/titles` (выход с сообщением «Действие отменено»). Конвенция «команда сбрасывает FSM» уже подтверждена в V1.15.0d.

### 6.6. Валидация текста — `_validate_title_text(text) -> (ok: bool, reason: str | None)`

- длина после strip: 1–16 символов (Telegram-лимит на custom_title);
- разрешено: латиница, кириллица, цифры, пробел, `- _ . , ! ?`;
- запрещено: эмодзи (любые non-BMP / pictographic), `< > / \ @ #`, многострочность, табы;
- normalize: `strip()` + схлопнуть подряд идущие пробелы в один.

## 7. UI Владельца

### 7.1. Точка входа

В меню Владельца (`handlers/owner_handlers.py`) добавляется кнопка `[🛍 Настройка Титулов]` (`callback_data="owner_titles_menu"`).

### 7.2. Главный экран

```
🛍 НАСТРОЙКА ТИТУЛОВ

📦 Пакетов активно: 5
💸 Цена переименования: 50 💎
⏱ TTL заявок (рубли): 48 ч
📨 Pending заявок: 2

  [📦 Пакеты]
  [✏️ Цена переименования]
  [⏱ TTL заявок]
  [📨 Заявки на оплату (2)]
  [🔙 Назад]
```

### 7.3. Раздел «📦 Пакеты»

Список с цветовой индикацией `is_enabled` (🟢/⚪) + цены в Пульсах и Рублях. Внизу `[➕ Добавить пакет]`.

Тап по строке → карточка пакета:

```
📦 «1 месяц» (30 дней)
💎 15 000 Пульсов
💳 300 ₽

  [✏️ Изменить срок]
  [💎 Изменить цену в Пульсах]
  [💳 Изменить цену в Рублях]
  [🟢 Включить / 🔴 Выключить]
  [🗑 Удалить]
  [🔙 Назад]
```

- `[✏️ Изменить срок]` — мини-FSM на 1 шаг: число дней (или `0`/`-` для «Навсегда» = `NULL`).
- `[💎 Изменить цену в Пульсах]` — целое число > 0.
- `[💳 Изменить цену в Рублях]` — целое число ≥ 0. `0` (или удалённое значение → `NULL`) = скрыть рублёвую кнопку у юзера для этого пакета.
- `[🗑 Удалить]` — мягкое: `UPDATE is_enabled=0`. Никогда не `DELETE` — есть FK из `title_rub_requests.package_id`.

`[➕ Добавить пакет]` — `ConversationHandler` на 4 шага: label → duration_days → price_pulses → price_rub → INSERT.

### 7.4. «✏️ Цена переименования»

Один шаг, ввод целого ≥ 0. Подсказка «0 = бесплатно». Пишет `settings.title_rename_price_pulses`.

### 7.5. «⏱ TTL заявок»

Один шаг, ввод целого > 0 (часы). Пишет `settings.title_request_ttl_hours`.

### 7.6. «📨 Заявки на оплату»

Лента — pending первыми, ниже последние 10 решённых (`approved`/`rejected`/`rejected_user_left`/`expired`). Каждая `pending`-заявка имеет свои `[✅ Подтвердить]`/`[❌ Отклонить]`.

### 7.7. Карточка заявки в ЛС Владельцу

При создании заявки юзером бот **автоматически** шлёт Владельцу в ЛС:

```
📨 НОВАЯ ЗАЯВКА #142

👤 @vasya (id=12345)
📦 1 месяц (30 дней)
🏷 Текст: «Кодер»
💳 Сумма: 300 ₽

⌛ Истечёт через 48 ч.

  [✅ Подтвердить] [❌ Отклонить]
```

`owner_msg_id` и `owner_chat_id` сохраняются в `title_rub_requests` — нужны для последующего редактирования (убрать кнопки + проставить статус) после клика или истечения TTL.

После клика `[✅]` — карточка редактируется в:
```
📨 ЗАЯВКА #142 — ✅ ПОДТВЕРЖДЕНО

👤 @vasya · 1 мес · 300 ₽
🏷 Применён титул «Кодер» до 12.05.2026
👍 Витя · 30.04.2026 14:23
```

После `[❌]` — мини-FSM спросит причину (опц., можно `/skip`):
```
📨 ЗАЯВКА #142 — ❌ ОТКЛОНЕНО

👤 @vasya · 1 мес · 300 ₽
💬 Причина: «передумал»
👍 Витя · 30.04.2026 14:23
```

Юзеру в ЛС отправляется DM с финальным статусом.

## 8. Логика выдачи / продления

В `apply_title_purchase(db, context, user_id, title_text, duration_days)` (новая функция в `handlers/titles_handlers.py`):

```python
# атомарно
BEGIN IMMEDIATE
existing = SELECT * FROM marketplace_services
           WHERE user_id=? AND service_type='title' AND status='active'
           ORDER BY id DESC LIMIT 1

if existing and existing.expires_at IS NULL:
    # уже бессрочный — ничего не делаем, возвращаем "already_permanent"
    ROLLBACK
    return {'status': 'already_permanent'}

if existing:
    # ПРОДЛЕНИЕ: текст НЕ меняем, expires_at += duration_days
    if duration_days is None:
        new_expires = NULL  # навсегда поверх обычного — заменяем на NULL
    else:
        base = max(now(), existing.expires_at)
        new_expires = base + timedelta(days=duration_days)
    UPDATE marketplace_services SET expires_at=new_expires WHERE id=existing.id
    title_to_apply = existing.content
else:
    # НОВАЯ ПОКУПКА: вставляем новую запись с введённым текстом
    new_expires = NULL if duration_days is None else now() + timedelta(days=duration_days)
    INSERT INTO marketplace_services
        (user_id, service_type, status, content, expires_at, start_time)
        VALUES (?, 'title', 'active', ?, ?, now())
    title_to_apply = title_text

COMMIT

await apply_title_to_user(context, target_chat_id, user_id, title_to_apply)
return {'status': 'ok', 'text': title_to_apply, 'expires_at': new_expires}
```

Возвращает достаточно для DM юзеру и для ответа в UI.

## 9. Edge-cases

| # | Сценарий | Поведение |
|---|---|---|
| 1 | Юзер купил Пульсами, `apply_title_to_user` упал (бот не админ / chat error) | Откатываем списание (`update_user_balance(user, amount, 'add')` + ROLLBACK транзакции БД услуги). DM «⚠️ Не удалось применить — средства возвращены, сообщи Вите». Лог. |
| 2 | Витя нажал `[✅]` дважды (с двух устройств) | Транзакция `BEGIN IMMEDIATE` + `UPDATE ... WHERE status='pending'` → `cursor.rowcount==0` для второго клика → alert «⚠️ Заявка уже обработана». |
| 3 | Баланс < цены пакета в Пульсах | Кнопка валюты остаётся видимой; при клике `query.answer(alert='❌ Нужно N💎, у тебя M💎')`, в FSM не входим. |
| 4 | Невалидный текст | Бот отвечает в FSM `«❌ <причина>. Попробуй ещё или /cancel»`, **не выходит** из state. Деньги не трогаются. |
| 5 | Покупка обычного пакета поверх активной обычной подписки | См. §8: продлеваем `expires_at`, текст сохраняется. |
| 6 | Покупка «Навсегда» поверх обычной | `expires_at = NULL`, текст сохраняется. |
| 7 | Покупка обычной поверх «Навсегда» | Кнопка валюты возвращает alert «⚠️ У тебя бессрочный титул, докупать смысла нет». Деньги не трогаются. |
| 8 | Юзер вышел из чата с активным титулом | Текущий `cleanup_expired_titles` это не отлавливает — **вне scope**. |
| 9 | Витя подтвердил заявку, юзер уже не в чате | `apply_title_to_user` упадёт; ловим, статус → `rejected_user_left`, alert Вите «⚠️ Юзер не в чате», DM юзеру не шлём. |
| 10 | Переименование при `title_rename_price_pulses=0` | Пропускаем шаг списания, остальное стандартно. |
| 11 | Конкурентность нажатий Владельца | `BEGIN IMMEDIATE` + `WHERE status='pending'`, см. №2. |
| 12 | Юзер отменил заявку (`titles_cancel_req_<id>`) пока pending | `UPDATE status='rejected', reject_reason='cancelled by user'`. Карточка у Вити редактируется в «❌ Отменена юзером». |

## 10. Фоновые задачи

- **Существующая** `cleanup_expired_titles(context, db, chat_id)` — без изменений, она уже снимает права после `expires_at`.
- **Новая** `cleanup_expired_title_requests(db, context)` — раз в час:
  ```sql
  UPDATE title_rub_requests
  SET status='expired'
  WHERE status='pending'
    AND created_at < datetime('now', printf('-%d hours', :ttl))
  ```
  После update — для каждой заявки попытаться `editMessageReplyMarkup(owner_chat_id, owner_msg_id, reply_markup=None)` и `editMessageText` пометить «⌛ Истекла». Ошибки редактирования — лог, не падаем. Регистрация — в существующем `JobQueue` (там, где живёт `cleanup_expired_titles`).

## 11. Точки правок в существующем коде

| Файл | Что меняем |
|---|---|
| `database/db_titles.py` (НОВЫЙ) | `init_titles_tables`, `seed_default_packages`, CRUD пакетов, CRUD заявок |
| `database/db_manager.py` | вызов `init_titles_tables(self) + seed_default_packages(self)` в `__init__`; тонкие методы-обёртки `get_title_packages()`, `create_title_request()`, `get_title_request(id)`, `update_title_request_status(id, ...)`, `get_title_pending_count()` |
| `handlers/titles_handlers.py` (НОВЫЙ) | `ConversationHandler` юзера, callback'и `titles_menu/titles_pkg_*/titles_buy_*`, `_validate_title_text`, `apply_title_purchase`, обработка кнопок `[✅]/[❌]` Владельца на карточках заявок (`titles_req_approve_<id>`, `titles_req_reject_<id>`) |
| `handlers/owner_handlers.py` | кнопка `[🛍 Настройка Титулов]` + entry в роутер; FSM CRUD пакетов + цена переименования + TTL |
| `handlers/callback/callback_router.py::show_balance` | добавить кнопку `[🏷 Титулы]` (callback `titles_menu`) |
| `handlers/command_handler.py` | регистрация `/titles` |
| `bot.py` (или там где собирается JobQueue) | `application.job_queue.run_repeating(cleanup_expired_title_requests, interval=3600)` |
| Чёрный рынок UI (нужно найти при реализации) | убрать кнопку покупки Тега; в карточке выкупленного титула оставить отображение, но без новой покупки |

## 12. Что НЕ входит в scope (выносим на потом)

- Возврат Пульсов при ручной отмене активной подписки Владельцем
- Передача титула другому юзеру
- Экран «история покупок титулов» в UI юзера (БД пишется через `marketplace_services` + `title_rub_requests`, экран — отдельная задача)
- Уведомления юзеру «остался 1 день до истечения»
- Snooze/edit заявки Владельцем (только Подтвердить/Отклонить/cancel-by-user)
- Очистка title если юзер вышел из чата
- Пакетная отмена заявок Владельцем

## 13. Тест-сценарии (для ручной проверки после реализации)

1. **Сидинг** — на свежей БД после старта в `title_packages` появилось 5 строк, `settings.title_rename_price_pulses=50`, `settings.title_request_ttl_hours=48`.
2. **Покупка за Пульсы (новая)** — юзер `/titles` → выбрал «1 месяц» → Пульсы → ввёл «Тест» → списано 15000💎, в Telegram появилась приписка `[Тест]`, в `marketplace_services` строка с `expires_at = today+30`.
3. **Продление за Пульсы** — повторил покупку «3 месяца» → текст не меняется, `expires_at` стал `today+30+90`.
4. **Переименование** — нажал `[✏️ Изменить текст · 50💎]` → ввёл «Кодер» → списано 50💎, в Telegram текст обновился, в БД `content='Кодер'`.
5. **Бесплатное переименование** — Владелец установил `title_rename_price_pulses=0` → юзер сменил текст без списания.
6. **Заявка за рубли** — юзер выбрал «6 месяцев» → Рубли → ввёл «VIP» → Владельцу пришла карточка в ЛС → `[✅]` → титул применён, юзеру DM, карточка отредактирована.
7. **Отказ Владельца** — `[❌]` → причина «передумал» → юзеру DM, статус `rejected`.
8. **Двойной клик Вити** — нажал `[✅]` дважды быстро → второе нажатие — alert «уже обработана».
9. **Юзер отменил заявку** — нажал `[❌ Отменить]` пока `pending` → статус `rejected`, карточка у Вити редактируется в «отменена юзером».
10. **TTL заявки** — заявка старше 48 ч → фоновая job переводит в `expired`, карточка у Вити «⌛ Истекла».
11. **Купить «Навсегда» поверх обычной** — `expires_at=NULL`, текст сохранился.
12. **Купить обычную поверх «Навсегда»** — alert «у тебя бессрочный, смысла нет», деньги не списаны.
13. **Юзер не в чате при подтверждении** — Витя `[✅]` → лог ошибки, статус `rejected_user_left`, alert Вите.
14. **Невалидный текст** — `«@everyone»` → бот отвечает «❌ запрещены символы», FSM не выходит, баланс не тронут.
15. **Чёрный рынок** — кнопка покупки Тега исчезла, активные титулы из старых покупок продолжают работать до истечения.

## 14. Версия и коммит

Реализация — следующий релиз `V1.16.0` (минорная — новая фича). Коммиты — по подзадачам с буквами (`V1.16.0a`, `b`, …) или одним пакетом — по решению на этапе плана.
