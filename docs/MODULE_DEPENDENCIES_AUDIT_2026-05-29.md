# Аудит модульных зависимостей и переиспользуемого функционала

> **Цель:** перед тем как делать UI цепочки 🔗 на сайте — выписать **что от чего зависит** и **какой функционал переиспользуется в разных модулях/ветках**.
>
> **Скоуп:** все модули из `shared/modules_catalog.json` + handler'ы бота.
> **Исключено:** Bug Tracker (репорты) — по решению Ильи 29.05.
>
> **Источники:** `shared/modules_catalog.json`, `Admin_SITE/components/modules/ModulesHub.jsx` SECTIONS, grep по `handlers/` и `bot_core/`.

---

## 1. Иерархия модулей (как сейчас в каталоге)

Поле `parent` в каталоге уже определяет **визуальную** иерархию. Поле `requires` (предлагаемое) определит **бизнес-зависимость** — модуль не работает без родителя.

### 1.1 Семейство BBS (Доска знакомств)

| Модуль                            | Текущий parent | Предлагаемый `requires` | Почему                                                                                                       |
| --------------------------------------- | --------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `bbs_pulse` (Пульс ББС)       | —                    | —                                    | Базовый: лента анкет. Источник правды для остальных.                    |
| `bbs_other` (ББС Другое)     | —                    | `bbs_pulse`                         | Доп. форматы досок — без основной не имеет смысла.                         |
| `bbs_edit` (Ред.анкет ББС) | —                    | `bbs_pulse`                         | Редактор анкет — без бизнес-сущности «анкета» нет смысла.          |
| `vip_bbs` (VIP BBS, paid)             | —                    | `bbs_pulse`                         | VIP-эффекты НА анкете — без анкет ничего не показывать.                  |
| `bbs_bonus` (BBS-бонусы)        | section economy       | `bbs_pulse`                         | Награды за заполнение анкеты ББС. Без анкет нечего награждать. |

### 1.2 Семейство Экономика → Майнинг

| Модуль                 | parent             | `requires`                | Почему                                                                           |
| ---------------------------- | ------------------ | --------------------------- | -------------------------------------------------------------------------------------- |
| `economy` (Базовая) | —                 | —                          | Корень: банк, балансы, отмены выплат. Системный. |
| `mining`                   | parent `economy` | `economy`                 | Майнинг = первичный источник пульсов.                   |
| `sprints`                  | parent `mining`  | `mining`                  | Спринты = бонусы майнинга. Сам не майнит.              |
| `combos`                   | parent `mining`  | `mining`                  | Комбо = бонусы майнинга.                                            |
| `penalty`                  | parent `mining`  | `mining`                  | Штрафы = списания из майнинг-наград.                      |
| `lottery`                  | parent `economy` | `economy`                 | Используется банк.                                                     |
| `bingo`                    | parent `economy` | `economy`                 | Используется банк.                                                     |
| `monthly_gift`             | parent `economy` | `economy`                 | Бонус из банка.                                                            |
| `referral`                 | parent `economy` | `economy`                 | Награда из банка.                                                        |
| `bbs_bonus`                | parent `economy` | `economy` + `bbs_pulse` | **Двойная зависимость:** банк и анкеты.             |
| `shipper`                  | parent `economy` | `economy`                 | Награды парам из банка.                                             |

### 1.3 Семейство Регистрация / Заявки / ЧС

| Модуль/функционал                   | Где живёт                                           | `requires`                                   |
| --------------------------------------------------- | ----------------------------------------------------------- | ---------------------------------------------- |
| `registration` (Регистрация)           | `handlers/registration*.py`                               | —                                             |
| Заявки (`applications` тред)            | `handlers/admin_moderation.py`                            | `registration`                               |
| Досье (`dossier` тред)                   | `handlers/admin_moderation.py`                            | `registration`                               |
| ЧС (`blacklist`)                                | `database/db_friend.py`, `handlers/admin_moderation.py` | — (самостоятельный)            |
| Замы (`admins`)                               | `database/db_friend.py`                                   | —                                             |
| Invite links (одноразовые)               | `database/db_friend.py`                                   | —                                             |
| Опрос при выходе (`survey_results`) | `handlers/exit_survey_handlers.py`                        | — (триггерится при leave-event) |
| Реф через анкету                      | `database/db_friend.process_referral`                     | `referral` + `registration`                |
| Реф через TG-invite (P1)                    | `events_logic.handle_member_left` ref-block               | `referral` (без registration)             |

Реф-система имеет **OR-зависимость**: либо `registration` ON (использует deep-link), либо OFF (использует TG-invite). Закрепить как «**мягкая зависимость**».

### 1.4 Семейство Журнал

Все 15 суб-категорий имеют parent `journal` в каталоге → следовательно `requires: journal`. Тут просто.

Дополнительно:

- `journal:trigger` → нужен ещё `triggers` ON (иначе нечего журналировать).
- `journal:join` → перекрытие с `registration` (новички через анкету vs через invite).
- `journal:blacklist` → может писать события `add_to_blacklist` независимо от `registration`.
- `journal:survey` → тесно с `exit_survey` (но это не модуль в каталоге).

### 1.5 Контент

| Модуль      | `requires`                                                 |
| ----------------- | ------------------------------------------------------------ |
| `press_release` | — (самостоятельный, тред в чате)    |
| `triggers`      | —                                                           |
| `horoscope`     | —                                                           |
| `donations`     | `economy` (переводы используют банк) |

### 1.6 Аналитика

| Модуль                                | `requires`                                                                 |
| ------------------------------------------- | ---------------------------------------------------------------------------- |
| `statistics` (контейнер)         | —                                                                           |
| `chart:users` / `chart:messages` / etc. | `statistics` (parent)                                                      |
| `top5`                                    | `statistics` (использует user_stats и SUM активности) |

---

## 2. Переиспользуемый функционал между модулями

Не модули — это **код-уровень** компоненты которые виcят в нескольких ветках сайта/бота.

### 2.1 Анкета (`q_name`, `q_age`, `q_city`, `q_therapy`)

Поля анкеты юзера хранятся в `pulse_bot.db.users` (`q_name`, `q_age`, `q_city`, `q_therapy`).

Используется в:

- `handlers/registration.py` / `registration_conversation.py` — заполнение при регистрации.
- `handlers/admin_moderation.py` — отображение в карточке заявки, в досье.
- `handlers/anketa_edit_handlers.py` — редактирование (модуль bbs_edit).
- `handlers/BBS/*.py` — отображение в ленте ББС.
- `api.py` `/api/admin/profile/me` — отдача в кабинет на сайте.

**Зависимость:** все «потребители» анкеты падают back to fallback (показывают «—») если поле пустое. Но **функционал** в БББ имеет смысл только если у юзера анкета заполнена → анкета приходит из `registration`.

### 2.2 Балансы и транзакции

`users.balance`, `users.frozen_balance`, `transactions` table.

Используется в:

- `handlers/messages/mining_logic.py` — начисление за сообщения.
- `handlers/lottery_handlers.py` — призы и стоимости билетов.
- `handlers/bingo_handlers.py` — то же.
- `handlers/gift_handlers.py` — переводы.
- `handlers/donate_handlers.py` — донаты.
- `handlers/titles_handlers.py` — покупка титулов.
- `handlers/shipper_handlers.py` / `shipper_logic.py` — награды парам.
- `handlers/messages/events_logic.py` — заморозка/разморозка при leave/return + реф-награды.
- `utils/exchange_rate.py` — обменный курс.

**Источник правды:** `users.balance`. Все мутации обязаны идти через `db.update_user_balance(user_id, amount, 'add'|'sub')` + `db.add_transaction(...)` для аудита.

### 2.3 Треды админ-чата (kind = `applications`, `dossier`)

Резолвятся через `bot_core/ws_resolver.resolve_admin_thread(conn, context, kind, fallback)`.

Используется в:

- `handlers/admin_moderation.py` (V1.17.0M1) — карточки заявок + досье.
- `handlers/anketa_edit_handlers.py` (V1.17.0M2) — обновление досье.
- `handlers/command_handler.py` (V1.17.0M5) — /resend_dossier.
- `handlers/bug_tracker_handlers.py` (V1.17.0M3) — баг-треды (исключаем по решению).
- `handlers/exit_survey_handlers.py` (V1.17.0M4) — отчёт ухода.

**Источник правды:** `bot_chat_topics.kind` per-ws.

### 2.4 Module guards (тумблеры модулей)

`bot_core/module_guard.is_module_enabled_cached(conn, ws_id, module_id)` — единая проверка «модуль включён?».

Используется в:

- `handlers/messages/mining_logic.py` — гарды Майнинг/Спринты/Комбо/Штрафы/Рефералы.
- `database/db_manager.is_econ_section_enabled` (V1.17.0h3) — Экономика-категории как модули.
- `handlers/lottery_handlers.py`, `bingo_handlers.py` — гард модуля.
- `handlers/BBS/*.py` — гард модуля bbs.
- `handlers/horoscope_handler.py` — гард модуля.
- `handlers/shipper_logic.py` — гард модуля.
- `Admin_SITE/components/modules/ModulesHub.jsx` — UI toggle.

**Источник правды:** `module_toggles(workspace_id, module_id, is_enabled)`. Cache key: `module_toggle_cache_version`.

### 2.5 Чаты per-ws (main / admin / journal)

`bot_chats.role IN ('main', 'admin', 'journal')` + `bot_chat_topics.kind` (треды).

Резолверы в `bot_core/ws_resolver.py`:

- `resolve_role_chat(conn, ws_id, role)` — main/admin/journal чат.
- `resolve_admin_chat(conn, context, fallback)` — context-aware.
- `effective_journal_chat(conn, ws_ctx, fallback, enabled, user_id)`.
- `resolve_user_primary_workspace(conn, user_id)` — ws по членству.

Используется буквально в **каждом handler-е** который отправляет сообщения боту в чат:

- `journal_handlers.py` — все логи событий.
- `triggers_handlers.py` — триггер-реакции.
- `BBS/publishing_bbs.py` — лента ББС.
- `PR/press_release_pr.py` — анонсы.
- `bbs_bonus`, `monthly_gift` — публичные награды.
- `lottery_handlers.py`, `bingo_handlers.py` — игровые посты.
- `shipper_handlers.py` — посты пар.

### 2.6 Реф-флоу (V1.17.0P1-P5)

Распределено по нескольким файлам, но это ОДНА система:

- **Создание ссылки:** `system_commands.send_my_referral_link` (P2) — kbd «🎟 Моя ссылка» / `/myref` (P4).
- **Трекинг по TG-invite:** `events_logic.handle_member_left` (P1) — парсит `invite_link.name='ref_<uid>'`.
- **Трекинг по deep-link:** `db_friend.process_referral` (legacy) — через анкету.
- **Квалификация:** `referral_utils.check_referral_qualification` — общая.
- **Начисление:** `bot.py:349` — читает `economy_settings.referral.qualified_reward`.
- **Текст сообщения:** `settings.referral_message_*` (P4) + `economy_settings.referral.*` (placeholders).

Это ОДИН модуль `referral` снаружи. Внутри — две реализации (deep-link / TG-invite), переключение по `is_feature_enabled('registration')`.

### 2.7 Профиль юзера (avatars, presence, last_active, last_exit_at)

Используется в:

- `handlers/admin_moderation.py` `_send_dossier` — лицо в досье через `utils/face_detector`.
- `handlers/anketa_edit_handlers.py` — инжект `presence` (был в чате?) в досье.
- `handlers/profile_handlers.py` — «Профиль» кнопка.
- `handlers/BBS/publishing_bbs.py` — аватар в ленте.
- `handlers/exit_survey_handlers.py` — определение что юзер ушёл.
- `events_logic.handle_user_left/returned` — заморозка/разморозка балансов.

### 2.8 Permissions / RBAC

`api/workspace_rbac.resolve_ws_role`, `bot_core/ws_role.is_ws_owner`/`is_ws_admin`, `permissions.has_permission`.

Используется в:

- Бот: `handlers/owner_handlers.py` (Пульт Владельца), `admin_moderation._is_strict_owner`, `bingo`/`lottery._is_owner_user`, `message_handler.is_user_excluded`.
- API: каждый endpoint с `@require_permission` или ручным `current_ws_id() + resolve_ws_role`.
- Сайт: `AdminDashboard.isOwner / isAdmin` для рендеринга «Права»/«Панель Владельца».

### 2.9 Журнал событий (logger функции)

`handlers/journal_handlers.py` экспортирует:

- `log_join`, `log_leave`, `log_mute`, `log_unmute`, `log_ban`, `log_unban`, `log_kick`, `log_warn`, `log_blacklist`, `log_admin_action`, `log_survey`, `log_profile_change`, `log_photo_change`, `log_activity`, `log_trigger`.

Вызываются из:

- `events_logic.py` — все TG-события юзеров.
- `admin_moderation.py` — действия админа.
- `triggers_handlers.py` — срабатывания триггеров.
- `exit_survey_handlers.py` — опрос ухода.
- `BBS/*.py` — изменения профиля.

Каждый log_* проверяет `module_toggles.journal:<kind>` отдельным гардом.

---

## 3. Кросс-секции UI

«Один и тот же функционал виден в нескольких разделах сайта» (Илья 29.05).

| Функционал                                                                      | Где виден на сайте                                                                                                                                                             | Источник                                                                 |
| ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| **Балансы юзеров**                                                     | Топ-5, Статистика по пользователям, Профиль (в кабинете каждого), Экономика → Журнал транзакций (будущий) | `users.balance`                                                                |
| **Анкеты (q_*)**                                                              | Заявки (карточка), Досье, ББС-лента, Профиль на сайте                                                                                                | `pulse_bot.db.users` q_*                                                       |
| **Реф-награда**                                                           | Экономика → Рефералы (настройка), Большое реф-сообщение (текст), Маленькое /myref (текст), уведомления юзеру | `economy_settings.referral.qualified_reward` + `settings.referral_message_*` |
| **Журнал событий**                                                     | Журнал → 15 категорий, Журнал транзакций (экон), Активности                                                                                     | `journal_messages` + `transactions`                                          |
| **TG треды**                                                                   | Заявки (admin-chat thread), Досье (тот же), Журнал (отдельный канал)                                                                                      | `bot_chat_topics.kind`                                                         |
| **Триггеры**                                                                | Триггеры (модуль), Журнал → Триггеры, Триггеры в Экономике (награды за условия)                                                | `triggers` table                                                               |
| **Дизайн-настройки журнала** (`journal_quote_*` цвета) | Журнал → Настройки оформления                                                                                                                                       | `settings.journal_quote_*`                                                     |

---

## 4. Тумблер-системы (3 источника, синхронны)

Тех-долг из `[[bot_feature_panel_legacy.md]]`:

| Точка                                                                         | Где                                            | Что хранит                                                         |
| ---------------------------------------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------- |
| **A.** Бот «Управление функциями»                    | TG-меню админа                          | `settings.feature_<id>` (`feature_referral`, `feature_lottery`, etc.) |
| **B.** Сайт → Модули → карточки                          | `Admin_SITE/components/modules/ModulesHub.jsx`  | `module_toggles(workspace_id, module_id, is_enabled)`                     |
| **C.** Сайт → Экономика → карточки категорий | `Admin_SITE/components/economy/EconomyPage.jsx` | `economy_section_toggles(category, is_enabled, workspace_id)`             |

С V1.17.0h3 (`[[economy_module_toggles_h3]]`):

- `db_manager.is_econ_section_enabled` читает из `module_toggles` (B) → fallback на C.
- A продолжает писать в `settings.feature_*` (legacy).
- Sync между ними **не автоматический** — могут разойтись при правке только в одной точке.

**На сегодня на проде (диагностика 29.05):** для PositivЭ ws=1 все три синхронны для `referral` (=1). То есть **в данных всё ок**. Проблема Ильи была **stale `active_ws_id=12` в localStorage** (вчерашний merge ws=12 → ws=1), фикс V1.17.0P6.

---

## 5. Что предлагается сделать дальше

### 5.1 Расширить каталог модулей полем `requires`

Минимальный патч в `shared/modules_catalog.json`:

- `bbs_other.requires = "bbs_pulse"`
- `bbs_edit.requires = "bbs_pulse"`
- `vip_bbs.requires = "bbs_pulse"`
- `bbs_bonus.requires = "bbs_pulse"` (плюс auto `economy` через parent)
- `sprints.requires = "mining"` (уже parent)
- `combos.requires = "mining"`
- `penalty.requires = "mining"`
- `donations.requires = "economy"`
- `journal:trigger.requires = "triggers"` (soft, можно и без)
- `journal:join.requires = "registration"` (если registration OFF, события всё равно идут)

### 5.2 UI-логика в карточке модуляconst parentEnabled = !mod.requires || connected[mod.requires];

```jsx
const showChainIcon = !!mod.requires;
// ...
{showChainIcon && (
  <Tooltip text={parentEnabled
    ? `Требует модуль «${NAME_BY_ID[mod.requires]}» (включён)`
    : `Сначала включи модуль «${NAME_BY_ID[mod.requires]}»`}>
    <LinkIcon size={14} className={parentEnabled ? 'text-ok' : 'text-warn'} />
  </Tooltip>
)}
// Кнопка «Подключить» disabled={!parentEnabled}
```

### 5.3 Этап F (централизация тумблеров) — отдельно

Не часть текущей правки. Описано в `[[bot_feature_panel_legacy.md]]`:

- Все 3 точки читают из `module_toggles` (новой).
- `is_feature_enabled` (legacy) → wrapper на `is_module_enabled_cached`.
- Удалить бот-меню «Управление функциями» (или редирект на сайт).
- Удалить `economy_section_toggles` таблицу — derived view.

---

## Связано

- `[[bot_feature_panel_legacy.md]]` — тех-долг 3-х систем тумблеров.
- `[[idea_connections_hub_site_2026_05_28]]` — Центр подключений (модули + треды).
- `[[economy_module_toggles_h3]]` — V1.17.0h3 моста section_toggles → module_toggles.
- `[[economy_categories_as_modules]]` — модель «каждая категория эконом = модуль».
- `[[modules_paid_badge_future]]` — будущее: бейджи free/paid.
- `[[feedback_module_cross_link]]` — cross-link Шиппер↔Экономика паттерн.
- `[[idea_referrals_without_registration]]` — реф-флоу без анкеты (P1).
