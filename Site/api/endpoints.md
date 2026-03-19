# Pulse Chat — API Endpoints

Документация по REST API для связи фронтенда с Python-бэкендом.
Бэкенд: FastAPI + SQLite (из существующего бота).

## Базовый URL
```
Production: https://api.pulse-chat.ru/v1
Dev:        http://localhost:8000/v1
```

## Авторизация
Все запросы (кроме /auth/*) требуют заголовок:
```
Authorization: Bearer <jwt_token>
```

---

## AUTH

| Метод | Endpoint         | Описание            | Body                              |
|-------|------------------|----------------------|-----------------------------------|
| POST  | /auth/register   | Регистрация          | {name, phone, password}           |
| POST  | /auth/login      | Вход                 | {phone, password}                 |
| POST  | /auth/refresh    | Обновить токен       | {refresh_token}                   |

## USER / PROFILE

| Метод | Endpoint             | Описание               |
|-------|----------------------|-------------------------|
| GET   | /user/profile        | Получить профиль        |
| PATCH | /user/profile        | Обновить профиль        |
| GET   | /user/{id}           | Профиль другого юзера   |

## ECONOMY

| Метод | Endpoint                  | Описание                     |
|-------|---------------------------|-------------------------------|
| GET   | /economy/balance          | Баланс текущего юзера         |
| GET   | /economy/course           | Текущий курс Пульса           |
| POST  | /economy/transfer         | Перевод {to_user_id, amount}  |
| POST  | /economy/donate           | Донат {target, amount}        |
| GET   | /economy/transactions     | История операций (?page=)     |

## TOP

| Метод | Endpoint        | Описание                |
|-------|-----------------|--------------------------|
| GET   | /top/rich       | ТОП-5 богачей            |
| GET   | /top/active     | ТОП-5 активистов         |

## LOTTERY

| Метод | Endpoint                    | Описание                |
|-------|-----------------------------|--------------------------|
| GET   | /lottery/list               | Активные лотереи         |
| GET   | /lottery/{id}               | Детали лотереи           |
| POST  | /lottery/{id}/buy           | Купить билет {count}     |
| GET   | /lottery/{id}/my-tickets    | Мои билеты               |

## BBS

| Метод | Endpoint              | Описание                    |
|-------|-----------------------|------------------------------|
| GET   | /bbs/profiles         | Лента анкет                  |
| GET   | /bbs/profile/{id}     | Одна анкета                  |
| POST  | /bbs/profile          | Создать/обновить анкету      |
| POST  | /bbs/react            | Реакция {profile_id, type}   |
| POST  | /bbs/report           | Жалоба {profile_id, reason}  |

## CHAT (WebSocket)

```
ws://api.pulse-chat.ru/v1/ws?token=<jwt>
```

### Сообщения (JSON):
```json
// Отправка
{"type": "message", "chat_id": 101, "text": "Привет!", "reply_to": null}

// Получение
{"type": "message", "id": "msg_123", "chat_id": 101, "from": 1, "text": "Ответ", "ts": 1710600000000}

// Печатает
{"type": "typing", "chat_id": 101, "user_id": 1}

// Статус
{"type": "status", "user_id": 1, "online": true}
```

## STATS (admin)

| Метод | Endpoint                  | Описание                   |
|-------|---------------------------|-----------------------------|
| GET   | /stats?period=day         | Статистика за период        |
| GET   | /stats/export?format=xlsx | Экспорт в файл              |

---

## Маппинг бот → API

| Функция бота              | API endpoint              |
|---------------------------|---------------------------|
| /start                    | POST /auth/register       |
| /balance                  | GET /economy/balance      |
| /pay                      | POST /economy/transfer    |
| /donate                   | POST /economy/donate      |
| /курс, /course            | GET /economy/course       |
| /top, /top5               | GET /top/rich, /top/active|
| /profile                  | GET /user/profile         |
| menu_lottery              | GET /lottery/list         |
| buy_ticket_               | POST /lottery/{id}/buy    |
| menu_bbs                  | GET /bbs/profiles         |
| bbs_create                | POST /bbs/profile         |
| menu_stats                | GET /stats                |
| Майнинг (message_handler) | Автоматически на бэкенде  |
