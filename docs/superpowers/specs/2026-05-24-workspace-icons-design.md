# Иконки сообществ — Design

**Дата:** 2026-05-24
**Подпроект:** иконки/аватары workspace на сайте (companion к P4 connect-flow site-UI).
**Версия:** `V1.17.0j` · ветка `feat/V1.17.0j-workspace-icons`.
**Флаг:** `WORKSPACE_ICONS` (дефолт **OFF** = байт-в-байт; ON = бэкенд лениво кеширует и отдаёт URL, фронт показывает картинку поверх монограммы).
**Процесс:** решение архитектуры (гибрид, фазированно) согласовано с Ильёй 2026-05-24.

---

## 1. Проблема

После P4 (V1.17.0i) карточки сообществ показывают ярлык «⭐ Главное / №N доп.»
и красный 🔴-бейдж, но «лицо» сообщества — монограмма-буква по id (одна
из 6 цветовых плиток). Это работает, но:

- сообщества визуально не отличимы пока не прочитаешь название;
- нет связи с привычным узнаванием TG-чата по аватарке.

Запрос Ильи (17.05 + 24.05 подтверждено): иконки/аватары сообществ.
Раскрыто на C при выборе из A/B/C — auto из TG (фаза 1) + опциональный
upload-override (фаза 2, эта спека не покрывает реализацию).

## 2. Ground truth (что есть и чего нет)

- В `bot_chats` хранится `chat_id` каждого подключённого чата + `role` (`main`/`admin`/`journal`/None). `workspace_id` идёт через FK-логику (без явного FK).
- Bot API доступен: `bot.get_chat(chat_id)` возвращает `Chat` с `photo: ChatPhoto?` (поля `small_file_id`/`big_file_id`), `bot.get_file(file_id)` → `File.file_path` → CDN URL `https://api.telegram.org/file/bot<TOKEN>/<file_path>`.
- **Ловушка:** CDN URL содержит токен бота → отдавать клиенту нельзя. Нужен серверный прокси + локальный кеш бинарника.
- В `workspaces` таблице полей под иконку нет. В `Admin_SITE/components/workspaces/WorkspaceSwitcher.jsx` и `WorkspaceList.jsx` уже есть fallback-монограмма (6 цветовых плиток по id) — её оставляем как fallback.
- Прод: `/root/PulsBot/` (рабочая директория), `git reset --hard origin/main` затирает git-tracked, untracked в `.gitignore` — переживают деплой. Безопаснее держать кеш **вне репо**: `/var/cache/pulsbot/ws_icons/<ws_id>.jpg`. На локалке (Windows) — `./.cache/ws_icons/<ws_id>.jpg` относительно `WorkingDirectory`.

## 3. Подходы (рассмотрено 3, решение C)

**A. Только auto из TG** — дёрнули `getChat` → `getFile` → кеш + прокси. Дёшево, без UI. Минус: «брендировать» workspace отдельно от чата нельзя.

**B. Только upload через сайт** — владелец грузит файл, храним статически. Минус: ручная работа сразу + storage/валидация UI.

**C. Гибрид фазированно (выбрано)** — фаза 1 = A. Фаза 2 = добавить
override-поле, upload через сайт. Иконка = override ?? auto. Эта спека
покрывает фазу 1 + закладывает фаза 2-поля так, чтобы при включении
override не требовалось второй миграции.

## 4. Дизайн (компоненты)

Всё за флагом `WORKSPACE_ICONS` (OFF = ни новых полей в JSON, ни прокси-эндпоинта; миграция аддитивна и безвредна при OFF).

**D1 — Миграция `workspaces`: иконочные колонки.**
Идемпотентно добавить (PRAGMA-проверка, образец `add_removed_at_to_bot_chats`):
- `icon_file_id TEXT` — `small_file_id` от TG, инвалидация кеша при смене.
- `icon_cached_at TIMESTAMP` — когда последний раз обновили локальный файл.
- `icon_source TEXT` (`'tg'` / `'upload'`) — задел под фазу 2; в фазе 1 всегда `'tg'`.
- `icon_local_path TEXT` — относительный путь под кешем (или NULL = нет картинки).

**D2 — Локальный кеш + конфиг.**
`WORKSPACE_ICONS_CACHE_DIR` env (дефолт `/var/cache/pulsbot/ws_icons` на проде, `./.cache/ws_icons` локально). Создаётся при старте, mode 0o755. Файлы — `<ws_id>.jpg` (TG отдаёт jpeg для chat photo).

**D3 — Сервис `services/workspace_icon.py`.**
- `pick_chat_for_icon(conn, ws_id) -> int?` — выбирает chat_id для иконки: первый `role='main'` с `removed_at IS NULL`, иначе первый не-removed любой роли, иначе `None`.
- `refresh_workspace_icon(bot, conn, ws_id) -> Optional[Path]` — async: `bot.get_chat(chat_id)`; если `photo` есть и `small_file_id` отличается от `icon_file_id` → `bot.get_file`; скачать; сохранить в `<cache>/<ws_id>.jpg`; обновить колонки. Если фото нет → `icon_local_path=NULL`, `icon_cached_at=now` (фиксируем «попытались, пусто»). Любая ошибка TG → лог + return prev path (не падать).
- `should_refresh(ws_row, ttl_s=604800) -> bool` — true если `icon_cached_at IS NULL` или старше TTL (7 дней по умолчанию).

**D4 — Endpoint `GET /api/workspaces/{ws}/icon.jpg`.**
Auth-required (как и остальные `/api/workspaces/*`). Логика:
1. `_check_role(ws, user_id, 'moderator')` — иначе 403/404.
2. Если `WORKSPACE_ICONS=OFF` → 404.
3. Прочитать `icon_local_path` из БД; если файла нет / устарел → асинхронно запустить `refresh_workspace_icon` (best-effort, не блокирует первый запрос).
4. Если файл есть → `FileResponse(local_path, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=300'})` (5 мин в браузере — балансирует свежесть после смены фото).
5. Если файла нет → 404 (фронт ловит `onError` → fallback на монограмму).

**D5 — JSON-выдача API: `icon_url`.**
- `get_workspaces_for_user`: добавить `icon_url: f"/api/workspaces/{ws_id}/icon.jpg"` если флаг ON И `icon_local_path` не NULL; иначе `null`. Не блокирует ничего — клиент со `<img onError>` сам падает на монограмму.
- `get_workspace_details`: то же поле в `workspace.icon_url`.
- При OFF поле либо отсутствует (старое поведение), либо всегда `null`.

**D6 — Фон-задача периодического refresh.**
В существующем job-планировщике бота (`bot.py` / `scheduler.py` если есть) добавить ежедневный обход всех `workspaces` где `should_refresh` → `refresh_workspace_icon`. Это снимает первое-обращение-холодное-старт-долго: к моменту когда юзер открывает сайт, файл уже в кеше. Job дешёвая — `getChat` лимит 30/sec для бота, на 10–100 workspace незаметно. При OFF задача не регистрируется.

**D7 — Сайт: `<img>` поверх монограммы.**
- В `WorkspaceList.jsx`, `WorkspaceSwitcher.jsx`, `WorkspacePage.jsx` (header), `WorkspaceList.jsx empty-state не трогаем — там Plug icon`.
- Паттерн: внутри плитки/тайла — если `ws.icon_url` задан, рендерим `<img src={ws.icon_url} className="w-full h-full object-cover rounded-xl" onError={e => e.currentTarget.style.display='none'}/>` поверх монограммы (z-index или conditional). При 404 / load fail — `onError` скрывает `<img>`, монограмма видна.
- `<img>` нужно передавать токен в Authorization (это статика через `/api`). Альтернатива: использовать query-параметр `?t=<jwt>` и middleware пускает GET на `*/icon.jpg` через query-auth — но это размывает аутентификацию. **Проще:** `<img>` грузит через `fetch` с заголовком, blob → `URL.createObjectURL`. Делаем mini-helper `useAuthImage(url, token)` в `Admin_SITE/components/shared/` → возвращает локальный `blob:`-URL. Это держит auth-flow единым.

## 5. Поток данных

```
[Фронт: open Dashboard]
  → GET /api/workspaces (Bearer JWT)
  → JSON содержит icon_url или null для каждого ws
  → <img> через useAuthImage:
       fetch(icon_url, {Authorization}) → blob → <img src=blob:...>
       onError → монограмма

[Бэкенд: эндпоинт icon.jpg]
  → check role
  → если файл свежий (cached_at внутри TTL) → отдать FileResponse
  → если устарел / нет / NULL → spawn refresh_workspace_icon в фоне,
    отдать что есть (или 404 первый раз)

[Бот: ежедневный job]
  → для каждого ws: pick_chat_for_icon → refresh если should_refresh
  → промахи логируем, не падаем
```

## 6. Обработка ошибок

- `bot.get_chat` 403/чат удалён → `icon_local_path=NULL`, `icon_cached_at=now`; фронт сам fallback на монограмму. Перезапросим через TTL.
- Гонка: два refresh одновременно для одного ws → пишем в temp файл `<ws>.jpg.tmp.<pid>` → `os.replace` атомарно. На Windows local — тот же приём, `os.replace` атомарен.
- Кеш-дир недоступен (permissions) → лог warning, фича работает только в памяти БД-метаданных, эндпоинт всегда 404. Не падаем.
- JWT-юзер потерял доступ к ws — `_check_role` → 404. Утечек чужих картинок нет (auth обязательна).
- Telegram CDN URL с токеном НЕ попадает в БД и НЕ отдаётся клиенту — только в локальной памяти на момент скачивания.

## 7. Тесты (TDD)

- `test_workspace_icon_migration.py`: 4 колонки добавляются идемпотентно, на отсутствующей таблице не падает.
- `test_workspace_icon_service.py`:
  - `pick_chat_for_icon` — main > admin > journal > None; soft-removed чаты игнорируются; пустой ws → None.
  - `refresh_workspace_icon` с замоканным bot: обновляет колонки и пишет файл; при отсутствии photo пишет NULL-путь и обновляет cached_at; при исключении возвращает старый путь.
  - `should_refresh` TTL: NULL → True, свежий → False, старый → True.
- `test_workspace_icon_route.py`:
  - GET без auth → 401; чужой ws → 404; OFF-флаг → 404; кеш-файл есть → 200 + jpeg headers; кеш-файла нет → 404 (smoke первого запроса до фонового refresh).
- `test_workspaces_api.py` доп.: при ON и наличии файла — `icon_url` в JSON; при OFF — поле отсутствует или null.
- Полный регресс → 0 регрессий (флаг OFF строго байт-в-байт).

## 8. Вне скоупа

- **Фаза 2 — upload-override.** Колонки `icon_source='upload'` + новый эндпоинт `POST /api/workspaces/{ws}/icon` с multipart, валидация (≤2 MB, jpeg/png), ресайз через Pillow. Дизайн делим отдельной спекой, чтобы не раздувать срез.
- Большой формат (`big_file_id`) для модалок «деталей сообщества» — пока хватает small (160×160). Если понадобится — добавим вторую колонку и второй файл `<ws>_big.jpg`.
- Привязка иконки к конкретной роли чата (например иконка main + иконка журнал) — usability сомнительно, не делаем.
- Биллинг (платный override / удаление лимита размера) — отдельная задача в #4 Modules.

## 9. Activation plan (путь A, как H/I/g/i)

1. Спека → план → реализация на ветке `feat/V1.17.0j-workspace-icons` (TDD, флаг OFF).
2. merge → main → авто-деплой (бэкенд рестарт; миграция аддитивна; флаг OFF = байт-в-байт; эндпоинт `icon.jpg` без флага возвращает 404).
3. Проверка прода чист (pulsbot+pulsapi active; миграция применилась).
4. `mkdir -p /var/cache/pulsbot/ws_icons && chown root:root && chmod 755` на проде (одноразово; идемпотентно).
5. `.env`: `WORKSPACE_ICONS=1` + `WORKSPACE_ICONS_CACHE_DIR=/var/cache/pulsbot/ws_icons` → `systemctl restart pulsbot pulsapi`.
6. **Сайт-деплой** (`[Site]`) — отдельный шаг, `<img onError>` уже даёт graceful degradation если бэкенд флаг OFF (просто монограммы как сейчас).
7. Smoke с Ильёй: открыть Pulse Москва на сайте → видна аватарка main-чата (через 2-5 сек после первого захода, потом мгновенно из кеша); удалить фото в Telegram → через сутки (или ручной refresh) → монограмма.

Откат: убрать флаг + рестарт; кеш-файлы можно стереть `rm -rf /var/cache/pulsbot/ws_icons` — БД-метаданные восстановятся при следующем включении.

## 10. Assumptions (брейншторм автономный + согласовано Ильёй)

1. Гибрид C, фаза 1 = auto-from-TG. Фаза 2 (upload-override) — позже отдельной спекой; колонки задела сразу (`icon_source`), чтобы избежать второй миграции.
2. Source-of-truth для auto = main-чат с `removed_at IS NULL`; fallback на любой не-removed; pure-empty ws → NULL → монограмма.
3. TTL = 7 дней; явный refresh через ежедневный job + ленивый refresh при первом запросе если устарело.
4. Кеш — на диске вне репо (`/var/cache/pulsbot/ws_icons`), персистентен через `git reset --hard`.
5. Auth для `icon.jpg` — Bearer JWT через fetch + blob (не query-param), консистентно с остальным API.
6. `<img onError>` на фронте — встроенный graceful fallback на монограмму; не нужен предзапрос «есть ли картинка».
7. Фаза 2 НЕ начинаем без явного запроса Ильи (память `feedback_autonomy`: автономия в работе, но новые скоупы — с согласованием).

Связано: spec `2026-05-17-connect-flow-lifecycle-design.md` §8 (out-of-scope иконок — здесь раскрываем), plan `2026-05-17-connect-flow-site-ui.md` (P4, текущая база), memory [[feedback_site_workflow]] [[server_structure]] [[build_npx_node_dir_trap]].
