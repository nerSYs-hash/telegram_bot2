# Срез D — Одно-тап вход бот → кабинет (LoginUrl) — Design

**Дата:** 2026-05-17
**Подпроект:** #3 Onboarding, срез D (первый тонкий срез; далее C хаб-клава, A/B нудж прав)
**Версия:** V1.17.0g · ветка `feat/V1.17.0g-login-url`
**Цель:** заменить ручную текст-ссылку `{SITE_URL}/login` на нативную
Telegram `LoginUrl`-кнопку: один тап в боте → юзер уже в своём кабинете,
без пароля и «хождения по кругу».

---

## Контекст (по аудиту 2026-05-17, проверено по коду+git)

Фундамент в проде: #2 коннект-флоу, #3 web-auth (JWT + Telegram-hash в
`api.py`, сервис `pulsapi`, смержен `ffb6971`), H, I. Пробел — UX последней
мили. ChatKeeper-воронка: A нудж прав / B подтверждение / C ЛС-хаб /
**D одно-тап LoginUrl** / E кабинет. Режем по D первым (дёшево, видимый
результат, нулевой риск).

**Ground truth `api.py` (прод):**
- `_verify_tg_hash(data)` — стандартная проверка подписи Telegram Login
  Widget (sorted `k=v\n`, HMAC-SHA256, secret = sha256(BOT_TOKEN)).
- `POST /api/auth/telegram` — принимает JSON-подпись → `_make_jwt` → `{token}`.
- `GET /api/auth/config` → `{bot_username}`.
- SPA (`Admin_SITE/AdminDashboard.jsx:204-215`): `window.onTelegramAuth`
  постит `/api/auth/telegram`, кладёт JWT в `localStorage['auth_token']`,
  затем работает по `Authorization: Bearer`.

**Различие, которое закрывает D:** веб-виджет шлёт **POST JSON**. Инлайн
`LoginUrl` Telegram отдаёт **GET с query-подписью** на настроенный домен.
Значит нужен GET-двойник существующей логики (реюз verify+jwt) +
кнопка в боте.

## Архитектура / поток

```
[ЛС бота] inline [🔑 Войти в кабинет]  (telegram.LoginUrl)
   │ юзер тапает → нативный диалог Telegram «Авторизоваться на puls-chat.ru как N»
   ▼ GET https://puls-chat.ru/api/auth/tg-callback?id=..&username=..&auth_date=..&hash=..
[api.py  GET /api/auth/tg-callback]
   • _verify_tg_hash(params)         (реюз)
   • now - auth_date > 86400 → ошибка (реюз правила)
   • _make_jwt({user_id,username,first_name,photo_url,is_admin,is_owner})
   • HTMLResponse: <script>localStorage.setItem('auth_token',"<JWT>");
                   location.replace('/')</script>
   ▼
[SPA puls-chat.ru/]  юзер уже залогинен в своём per-WS кабинете.
```

JWT-payload — **идентичен** `POST /api/auth/telegram` (тот же `_make_jwt`,
тот же developer-god-mode по `DEVELOPER_ID`). per-WS RBAC дальше делает #3
как сейчас. D не трогает роли.

## Компоненты

### 1. `api.py` — `GET /api/auth/tg-callback`
- Читает query-параметры в dict (`id, first_name, last_name, username,
  photo_url, auth_date, hash`). Все строки (как шлёт Telegram).
- Реюз `_verify_tg_hash` (тот же расчёт; Telegram даёт те же поля). При
  провале → `HTMLResponse` 401 с текстом «Ссылка устарела или подделана —
  вернись в бота и нажми Войти ещё раз» (без утечки деталей).
- Реюз правила `time.time() - int(auth_date) > 86400` → та же страница-ошибка.
- `_make_jwt` с тем же payload, что POST-ветка (developer-god-mode тоже).
- Успех → `HTMLResponse`:
  `<!doctype html><meta charset=utf-8><script>
   localStorage.setItem('auth_token',{json_jwt});location.replace('/')
   </script>Входим…`
  (JWT в JS-строку через `json.dumps` — экранирование).
- **Ноль изменений фронта, ноль пересборки** — страницу рендерит FastAPI.

### 2. `bot_core/login_button.py` (новый, маленький)
- `def login_keyboard(text: str = "🔑 Войти в кабинет") ->
  InlineKeyboardMarkup` → одна кнопка `InlineKeyboardButton(text,
  login_url=LoginUrl(url=_callback_url()))`.
- `_callback_url()` = `f"{SITE_URL}/api/auth/tg-callback"`,
  `SITE_URL = os.getenv('SITE_URL', 'https://puls-chat.ru')` (как в
  `bot_membership.py`).
- Единая точка построения кнопки (DRY) — реюзят и коннект-флоу, и `/login`,
  и потом хаб C.

### 3. `handlers/bot_membership.py` — проводка за флагом
Там, где сейчас отправляется текст с `{SITE_URL}`/`{SITE_URL}/login`
(сообщения «уже подключён», «создано новое сообщество», «успех» + DM
владельцу), при флаге ON добавлять `reply_markup=login_keyboard()` и
убирать сырую ссылку из текста. При флаге OFF — **текст байт-в-байт как
сейчас** (никакого reply_markup).

### 4. Команда `/login` (новый хендлер)
- `handlers/commands/login_command.py`: на `/login` в ЛС — сообщение
  «🔓 Твой кабинет Pulse SaaS» + `login_keyboard()`.
- Регистрация в `bot.py` рядом с прочими `CommandHandler`. При флаге OFF
  хендлер не регистрируется (или отвечает пусто) → байт-в-байт.
- Точка-возврата при «закрыл DM» + готовый крючок для хаба C.

### 5. Флаг `LOGIN_URL_BUTTON` (дом. правило: код+тумблер+FAQ)
- `os.getenv('LOGIN_URL_BUTTON','').strip().lower() in {'1','true','yes','on'}`
  — дефолт **OFF**.
- OFF = байт-в-байт: `bot_membership` шлёт прежний текст, `/login` не
  активен. GET-эндпоинт существует, но инертен пока не вызван → безопасен.
- ON = кнопка во всех точках + `/login`.
- Откат: снять флаг из `.env` + рестарт `pulsbot`. БД-миграций нет.
- FAQ-описание (3-й шаг чек-листа) = **код-коммит** (g5): FAQ захардкожен
  в `handlers/commands/system_commands.py` (`FAQ_COMMANDS_USER`,
  `FAQ_FEATURES`), НЕ DB/триггеры, на сайте не редактируется. Добавлен
  `FAQ_LOGIN_LINE` + хелпер `faq_commands_user_text()` (строка про /login
  только при флаге ON → OFF = FAQ байт-в-байт), оба рендера
  (`user_callbacks.py`, `handlers/utils/callback_handler.py`) зовут хелпер.
  [Ранее в спеке было ошибочно «FAQ DB/сайт» — исправлено.]

## Обработка ошибок
- Битая/протухшая подпись → страница-ошибка с кнопкой-ссылкой назад в
  бота (`https://t.me/<bot_username>`), без технических деталей.
- Юзер нажал «Отмена» в нативном диалоге → событие к нам не приходит,
  делать ничего не нужно.
- Домен не привязан в @BotFather → Telegram не покажет кнопку корректно.
  **Предусловие, не код:** веб-виджет в проде работает ⇒ домен почти
  наверняка уже привязан (виджет требует тот же `/setdomain`). Проверка —
  на активации; фикс при необходимости — `/setdomain puls-chat.ru` у
  @BotFather (делает владелец бота).

## Тесты (TDD)
- `tests/test_auth_tg_callback.py`: валидная подпись (собрать hash тем же
  алгоритмом) → 200, тело содержит `localStorage.setItem('auth_token'` и
  валидный JWT; битый hash → не 200, нет токена; `auth_date` старше суток
  → не 200; developer-id → `is_owner/is_admin=true` в JWT.
- `tests/test_login_button.py`: `login_keyboard()` → один
  `InlineKeyboardButton`, `login_url.url` == `{SITE_URL}/api/auth/tg-callback`.
- `tests/test_login_flag_off.py`: флаг OFF → `bot_membership` тексты
  байт-в-байт (нет `reply_markup`), `/login` неактивен.
- Прогон всего сьюта — без регрессов (база ~189).

## Вне скоупа (следующие срезы #3)
- C: универсальный `/start`-лендинг + постоянная reply-клава.
- A/B: реакция на add-без-прав / promote→admin.
- Двойной `MY_CHAT_MEMBER`-хендлер (bot.py:730/746) — техдолг, разобрать в A/B.

## Активация (отдельно, с Ильёй, путь A как H/I)
push ветки → main → авто-деплой (флаг OFF = байт-в-байт) → проверить прод
чист → проверить домен в @BotFather → в `/root/PulsBot/.env`
`LOGIN_URL_BUTTON=1` → `systemctl restart pulsbot` → smoke: тап кнопки в
ЛС → нативный диалог → кабинет без пароля. Откат = снять строку + рестарт.
