# Audit — database/db_friend.py (живое / мёртвое)

> **Назначение:** реестр функций `database/db_friend.py` с пометкой «активна / мёртвая», и план миграции на основную БД (`bot_database.db` через `db_manager`). Пункт **1.3** блокера `blocker_before_new_ws_2026_05_28`.
>
> **Источник:** grep `from database.db_friend import` по проекту 2026-05-28.
>
> **Контекст:** db_friend.py — НЕ legacy, как считалось. Это активная вторая БД (`pulse_bot.db`), отдельная от основной (`bot_database.db`). На ней живёт регистрационный flow: заявки, анкеты, инвайт-ссылки, блэклист, заместители владельца, реферальный учёт, опрос ушедших, журнал сообщений (фото-досье), и часть админ-команд. Удалять её одним коммитом нельзя — пересекается с третью бота.

---

## 1. Архитектурная реальность (на проде 28.05)

- Бот стартует с **двумя SQLite-файлами**:
  - `bot_database.db` (через `database/db_manager.Database`) — экономика, статистика, токены, экспириенс, multi-tenancy (workspaces, bot_chats, ...).
  - `pulse_bot.db` (через `database/db_friend.py`, `aiosqlite`) — регистрация и заявки.
- Инициализация: `bot.py:140` зовёт `await init_friend_db()` при старте → создаёт таблицы в `pulse_bot.db` если их нет.
- Поэтому утверждение «таблицы admins НЕТ на проде» из `prod_reality_2026_05_28` — относится к `bot_database.db`, не к `pulse_bot.db`. В `pulse_bot.db` таблица admins есть, и `db_friend.add_admin` туда писал — но НИКТО кроме регистрации это поле не читает (см. ниже).

## 2. Карта функций по статусу

Легенда:
- **АКТИВ** — импортируется handler-ом, выполняется в проде.
- **ВНУТР** — используется только внутри `db_friend.py`.
- **МЁРТВ** — никем не импортируется, не выполняется.
- **УБРАЛИ 1.1** — больше не используется, можно удалить.

### Инициализация / служебные
| Функция | Статус | Кто использует |
|---|---|---|
| `init_db` | АКТИВ | bot.py:140 (init_friend_db) |
| `row_to_dict`, `rows_to_dict_list`, `generate_referral_code`, `db_pool` | ВНУТР/АКТИВ | сам db_friend + reminder_logic, callback_router |

### Users (регистрация — анкета)
| Функция | Статус | Кто использует |
|---|---|---|
| `get_user` | АКТИВ | bot.py, command_handler, anketa_edit, callback_router, events_logic, profile, regis* |
| `create_user` | АКТИВ | command_handler:260, admin_moderation:277, regis_conv:15 |
| `update_user` | АКТИВ | utils/membership:120, approval, admin_moderation, regis_conv, reminder_logic, callback_router, events_logic |
| `get_user_by_username` | АКТИВ | regis_conv:656 |
| `get_user_by_referral_code` | ВНУТР | process_referral |
| `update_last_seen` | **МЁРТВ** | — |
| `get_users_with_incomplete_questionnaire` | **МЁРТВ** | — |
| `get_users_with_unused_link` | АКТИВ | reminder_logic:4 |

### Referral
| Функция | Статус | Кто использует |
|---|---|---|
| `process_referral` | АКТИВ | admin_moderation:334 |
| `confirm_referral` | АКТИВ | events_logic:401 |
| `get_referral_stats`, `get_referral_code` | **МЁРТВ** | — (есть db_referrals в основной БД) |

### Applications (заявки)
| Функция | Статус | Кто использует |
|---|---|---|
| `create_application`, `save_application_message_id`, `add_application_message`, `get_application_messages`, `clear_application_messages` | АКТИВ | regis_conv, admin_moderation |
| `get_new_applications`, `lock_application`, `unlock_application`, `set_application_skipped`, `delete_application`, `approve_application`, `reject_application`, `get_application`, `cancel_user_applications`, `get_user_pending_application`, `close_user_applications` | АКТИВ | admin_moderation, regis_conv, approval, callback_router, command_handler |
| `cleanup_expired_locks` | ВНУТР | get_new_applications |

### Admin (роль)
| Функция | Статус | Кто использует |
|---|---|---|
| `is_admin` | АКТИВ | admin_moderation:711, command_handler:486 (`as is_reg_admin` — проверка «регистрационный админ») |
| `add_admin` | **УБРАЛИ 1.1** | — |
| `remove_admin` | **УБРАЛИ 1.1** | — |
| `get_all_admins` | АКТИВ | regis_conv:15 (рассылка карточек заявок) |

### Deputy (зам владельца)
| Функция | Статус | Кто использует |
|---|---|---|
| `add_deputy`, `remove_deputy` | АКТИВ | admin_moderation:1240/1280 |
| `is_deputy` | АКТИВ | horoscope, PR/press_release, profile, admin_moderation, admin_logic |
| `get_all_deputies` | АКТИВ | bot.py:235 (рассылка апдейтов), admin_moderation, top_and_stats, Stats/stats_tops |

### Blacklist
| Функция | Статус | Кто использует |
|---|---|---|
| `is_blacklisted`, `get_blacklist_reason` | АКТИВ | bot.py:836, command_handler:238, regis_conv:118 |
| `add_to_blacklist`, `remove_from_blacklist` | АКТИВ | events_logic:78/117, admin_moderation:1127 (FSM) |
| `get_blacklist_count`, `get_blacklist_with_users` | АКТИВ | admin_moderation:1127 (FSM) |

### Invite links
| Функция | Статус | Кто использует |
|---|---|---|
| `create_invite_link` | АКТИВ | command_handler:376, regis_conv:351 |
| `deactivate_invite_link`, `get_active_invite_link` | АКТИВ | events_logic:375 |

### Settings (key/value)
| Функция | Статус | Кто использует |
|---|---|---|
| `get_setting`, `set_setting` | **МЁРТВ** | — (есть db_settings в основной БД) |

### Journal messages (фото-досье)
| Функция | Статус | Кто использует |
|---|---|---|
| `add_journal_message`, `get_last_profile_message`, `delete_journal_message`, `get_old_journal_photos` | **МЁРТВ** | — |

### Survey (опрос ушедших)
| Функция | Статус | Кто использует |
|---|---|---|
| `save_survey_result`, `should_send_survey`, `get_survey_stats` | **МЁРТВ** | — (есть exit_interviews в основной БД) |

### Triggers
| Функция | Статус | Кто использует |
|---|---|---|
| `get_enabled_triggers`, `create_trigger`, `update_trigger`, `delete_trigger`, `toggle_trigger`, `get_all_triggers` | **МЁРТВ** | — (есть отдельная таблица `triggers` в основной БД через `triggers_handlers.py`) |

### Violations
| Функция | Статус | Кто использует |
|---|---|---|
| `increment_violation`, `reset_violations`, `get_violation_count`, `cleanup_old_violations` | **МЁРТВ** | — |

### Inactive
| Функция | Статус | Кто использует |
|---|---|---|
| `get_inactive_users` | **МЁРТВ** | — |

## 3. Итог

**Активный скоуп `db_friend.py`:** регистрация (users-анкета), applications, deputies, blacklist, invite_links, referral (частично). ~40 функций.

**Мёртвый код:** ~20 функций — settings, journal_messages, survey_results, triggers, violations, get_inactive_users, get_users_with_incomplete_questionnaire, update_last_seen, get_referral_stats/code. Их таблицы (`settings`, `journal_messages`, `survey_results`, `triggers`, `violations`) создаются `init_db`, но никто не пишет/читает. Дублируются в основной БД или в db_settings.

## 4. План закрытия в скоупе блокера

**Решение:** db_friend.py **НЕ удалять и не переписывать в этой итерации** — это треть бота, отложит блокер на месяцы. Вместо этого:

1. **СЕЙЧАС (в Группе 2 блокера)** — добавить `workspace_id` в таблицы db_friend, которые должны делиться между ws:
   - `users` (анкета — per-ws? возможно нет, юзер один на бота)
   - `applications` — **точно per-ws** (заявка на конкретный чат)
   - `admins` (если оставляем регистрационных) — per-ws
   - `blacklist` — per-ws (ЧС одного ws не должен блокить другой)
   - `invite_links` — per-ws (ссылка на конкретный чат)
   - **deputies** — per-ws (зам конкретного владельца)
   - `application_messages` — per-ws (карточки в админский тред конкретного ws)

2. **ОТЛОЖИТЬ (после блокера)** — слияние двух БД в одну. Это отдельный большой проект, не критичен для подключения второго ws.

3. **МОЖНО СЕЙЧАС** — удалить мёртвые функции/таблицы из db_friend (settings, journal_messages, survey_results, triggers, violations). Это разгрузит БД и упростит миграции. Делать отдельным коммитом после Группы 1.

4. **СДЕЛАНО (1.1)** — `add_admin/remove_admin` из db_friend больше не вызываются handlerами. Сами функции в db_friend остаются (на случай восстановления), но в Группу 4 их можно удалить.

## 5. Связано

- `docs/SPEC_multi_tenancy_completion.md` — общая спека (M1-M8 не покрывала db_friend!).
- `docs/AUDIT_hardcoded_chat_ids_2026-05-28.md` — параллельный аудит хардкода (1.2).
- Memory: `db_friend_legacy_debt`, `blocker_before_new_ws_2026_05_28`, `prod_reality_2026_05_28`.
