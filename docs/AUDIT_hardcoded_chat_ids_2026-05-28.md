# Audit — хардкод TARGET_CHAT_ID / CHAT_ID / ADMIN_CHAT_ID / thread-IDs

> **Назначение:** реестр всех мест, где код читает один чат/тред «единственным истинным» из .env или константы. Этот хардкод убивает изоляцию workspace-ов: при подключении второго ws бот по таким местам продолжит работать со ws=1.
>
> **Источник:** `git grep` по проекту 2026-05-28. Версия фикса: пункт **1.2** блокера `blocker_before_new_ws_2026_05_28`.
>
> **Цель аудита:** не править прямо сейчас — а зафиксировать карту перед массовой заменой в Группе 4 блокера (per-workspace mode бота).

---

## 1. Источники переменных

| Где | Что определяет | Источник |
|---|---|---|
| `.env` (прод, /root/PulsBot/.env) | `TARGET_CHAT_ID`, `CHAT_ID`, `ADMIN_CHAT_ID`, `DOSSIER_THREAD_ID`, `APPLICATIONS_THREAD_ID`, `JOURNAL_CHANNEL_ID` | Финальный источник |
| `config.py` (top-level модуль) | `CHAT_ID`, `ADMIN_CHAT_ID`, `DOSSIER_THREAD_ID`, `APPLICATIONS_THREAD_ID`, `JOURNAL_CHANNEL_ID` | Читает `os.getenv("CHAT_ID", ...)` |
| `config/__init__.py` (пакет) | `CHAT_ID`, `ADMIN_CHAT_ID`, `DOSSIER_THREAD_ID`, `APPLICATIONS_THREAD_ID` | Читает `os.getenv('TARGET_CHAT_ID', ...)` |
| `config/bot.py` | `self.target_chat_id` | Читает `os.getenv('TARGET_CHAT_ID')` |
| `bot.py:99` | `self.target_chat_id` | На bot-instance |

⚠️ **Дубликат config.py vs config/**: одновременно существуют top-level модуль и одноимённый пакет. По правилу импорта Python пакет имеет приоритет — значит `config.py` фактически мёртв (но import-syntax `from config import X` рабочий через пакет). Подлежит чистке в **тех-долге**, не в скоупе блокера.

⚠️ **TARGET_CHAT_ID vs CHAT_ID**: фактически дубликаты. .env содержит обе с одним значением (память `prod_reality_2026_05_28`). Финальное состояние — оставить одну `TARGET_CHAT_ID`.

## 2. Что уже готово (фундамент per-workspace)

- `bot_core/ws_resolver.py`:
  - `resolve_role_chat(conn, workspace_id, role)` — читает `bot_chats.role IN ('main','admin','journal')`.
  - `resolve_thread(conn, workspace_id, kind)` — читает `bot_chat_topics.kind IN ('applications','dossier','bug_bot','bug_site','bbs')`.
  - `effective_main_chat(...)` — main_chat per ws + fallback на `CHAT_ID`.
  - `resolve_gate_chat(...)` — context-aware обёртка для message_handler / registration.
  - Флаг `H_RUNTIME_WS` (default ON с M2).
- В `handlers/message_handler.py:204` главный gate уже через `_gate_target_chat`.
- В `handlers/command_handler.py:115-119` и `handlers/registration_conversation.py:230-239` — gate через `resolve_gate_chat`.

**Чего нет (нужно по аналогии добавить):**
- `effective_admin_chat(...)` — обёртка для ADMIN_CHAT_ID per ws.
- `effective_journal_chat(...)` — обёртка для JOURNAL_CHANNEL_ID.
- `effective_thread(kind)` — обёртка для DOSSIER_THREAD_ID / APPLICATIONS_THREAD_ID / BUG_*.

## 3. Карта хардкода по use-cases

### A. Главный gate сообщений (УЖЕ per-ws через ws_resolver)
- `handlers/message_handler.py:204` — `_gate_target_chat(context)`. ✅
- `handlers/command_handler.py:115-119` — `resolve_gate_chat`. ✅
- `handlers/registration_conversation.py:230-327` — `resolve_gate_chat`. ✅

### B. ADMIN_CHAT_ID — хардкод (требует per-ws)
- `handlers/message_handler.py:205-206` — exception gate для admin-чата (FSM-вводы).
- `handlers/admin_moderation.py:115, 132, 643, 806, 862, 922` — отправка карточек заявок, досье, панелей.
- `handlers/anketa_edit_handlers.py:225, 265, 285, 323, 336` — досье через анкету.
- `handlers/bug_tracker_handlers.py:14, 365` — отправка багов.
- `handlers/command_handler.py:61, 72, 160, 176` — `/setup`-команды.
- `handlers/exit_survey_handlers.py:576, 605` — рассылка ушедших.
- `handlers/registration_conversation.py:16` — импорт для отправки заявок.

### C. CHAT_ID — get_chat_member / линки (требует per-ws)
- `handlers/registration.py:210-212, 628-630` — `bot.get_chat_member(CHAT_ID, user_id)` (проверка состоит ли в чате).
- `handlers/admin_moderation.py:155, 373, 1328, 1339, 1361, 1370, 1385, 1443, 1499, 1514` — много, в т.ч. `get_chat_member`, инлайн-ссылки `t.me/c/...`.
- `handlers/approval_handlers.py:143, 206` — ссылка-приглашение.
- `handlers/triggers_handlers.py:762, 778` — `db.get_all_topics(CHAT_ID)`.
- `handlers/command_handler.py:92, 119` — ссылка + gate.
- `handlers/exit_survey_handlers.py:158-160, 684-685` — `bot.get_chat(TARGET_CHAT_ID)`.

### D. APPLICATIONS_THREAD_ID / DOSSIER_THREAD_ID (треды — per-ws через bot_chat_topics)
- `handlers/admin_moderation.py:17, 116, 133, 644, 862, 923` — треды заявок/досье.
- `handlers/anketa_edit_handlers.py:26, 266, 285, 324, 337` — досье.
- `handlers/command_handler.py:72, 161, 177` — заявки в setup-команде.
- `handlers/registration_conversation.py:16` — импорт.
- `handlers/get_thread_id.py:5, 38` — служебная команда.

### E. JOURNAL_CHANNEL_ID
- `config.py:20` — единственное место. По коду — устанавливается через бота динамически. См. пункт **1.4** блокера (где реально хранится сейчас).

### F. TARGET_CHAT_ID в API / Site / тестах
- `api.py:1480, 1736-1738` — отправка сообщений от имени бота (HTTPException если не задан).
- `api/titles_routes.py:68-70` — то же для титулов.
- `Site/backend/main.py:1416-1428` — сайт читает `.env` бота напрямую (читает файл!).
- `handlers/Stats/stats_tops.py:134, 160` — отправка топа.
- `handlers/Stats/stats_controller.py:1199, 1243` — legacy (мёртвый файл по памяти `session_2026_05_27_m1_progress`).
- `handlers/commands/system_commands.py:552-554` — `/setup_welcome`.
- `handlers/titles_handlers.py:291` — функция-helper.
- `handlers/BBS/editing_bbs.py:28` — BBS editor.
- `tests/test_setup_welcome.py:28-45` — тесты через monkeypatch.

### G. Скрипты (низкий приоритет, разовые)
- `script/check_env.py`, `script/view_topics.py`, `script/update_topic_name.py`
- `Скрпиты/check_env.py`, `Скрпиты/view_topics.py`, `Скрпиты/update_topic_name.py`, `Скрпиты/send_press_release.py` — **дубликат с опечаткой**, кандидат на удаление.
- `scripts/reset_workspace_owner.py:34, 56, 191-192` — наш CLI-помощник, использует TARGET_CHAT_ID как параметр.

## 4. План замены (в Группе 4 блокера)

Приоритет по риску слома изоляции:

| Приоритет | Группа use-case | Действие |
|---|---|---|
| **1 (высокий)** | B (ADMIN_CHAT_ID gate в message_handler) | Заменить хардкод на per-ws через новый `effective_admin_chat` |
| **1 (высокий)** | C (get_chat_member CHAT_ID в registration) | Заменить на `resolve_gate_chat` (уже есть) |
| **2 (средний)** | B (ADMIN_CHAT_ID отправка в admin_moderation/anketa_edit/bug_tracker) | Заменить на `effective_admin_chat` |
| **2 (средний)** | D (треды) | Заменить на `resolve_thread(kind)` |
| **3 (низкий)** | F (API/Site/Stats отправки) | API ждёт ws_id из заголовка — заменить на per-ws |
| **3 (низкий)** | C (линки t.me/c/{CHAT_ID}) | Из main_chat workspace |
| **отложить** | G (скрипты), дубликат config.py | После закрытия блокера |

## 5. Тех-долг (не в скоупе блокера, фиксируем)

- **Дубликат `config.py` и `config/__init__.py`** — выбрать пакет, top-level удалить.
- **Дубликат `script/` и `Скрпиты/`** — `Скрпиты/` (опечатка) удалить.
- **`handlers/Stats/stats_controller.py`** — мёртвый файл (память `session_2026_05_27_m1_progress`), удалить с разрешения.

## 6. Что менять/выкатывать на проде

Сначала — **прод должен иметь таблицы** `workspaces / workspace_members / bot_chats / bot_chat_topics`. По памяти `prod_reality_2026_05_28` — их там НЕТ. Группа 2 блокера. До неё пункт 1.2 = только аудит (этот файл).

После Группы 2 — Группа 4 действует по плану §4 этого файла.

---

См. также:
- `docs/SPEC_multi_tenancy_completion.md` (общая спека M1-M8)
- `bot_core/ws_resolver.py` (готовый фундамент per-ws)
- Memory: `blocker_before_new_ws_2026_05_28`, `prod_reality_2026_05_28`, `subproject_H_chat_roles_runtime`.
