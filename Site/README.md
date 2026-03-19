# Pulse Chat — Web Messenger

## Структура проекта

```
pulse-chat/
├── index.html                 # Единственная HTML-страница (SPA)
├── css/
│   ├── variables.css     +     # CSS-переменные: цвета, размеры, темы
│   ├── base.css           +    # Reset, типографика, скроллбары
│   ├── layout.css        +     # Сетка: sidebar, chat-view, pages
│   ├── components.css    +     # Кнопки, бейджи, инпуты, тоглы
│   ├── landing.css       +     # Стили лендинга
│   ├── auth.css          +     # Стили авторизации
│   ├── chat.css          +     # Пузыри, сообщения, input area
│   ├── profile.css      +      # Профиль / Личный кабинет
│   ├── modules.css      +      # Экономика, ТОП, Лотерея, BBS
│   └── animations.css    +     # Все @keyframes
│
├── js/
│   ├── core/
│   │   ├── app.js      +       # Инициализация, глобальные обработчики
│   │   ├── router.js          # SPA-роутер (showPage, history)
│   │   ├── theme.js           # Тёмная/светлая тема
│   │   └── state.js           # Глобальный стейт (currentUser, chats)
│   │
│   ├── modules/
│   │   ├── sidebar.js    +     # Список чатов, поиск, меню
│   │   ├── chat.js       +     # Сообщения, отправка, контекст-меню
│   │   ├── auth.js        +    # Логин, регистрация
│   │   ├── profile.js         # Профиль / Паспорт
│   │   ├── economy.js         # Баланс, переводы, курс, майнинг
│   │   ├── top.js             # ТОП-5 богачей и активистов
│   │   ├── lottery.js         # Лотерея
│   │   └── bbs.js             # BBS (доска знакомств)
│   │
│   ├── utils/
│   │   ├── helpers.js     +    # formatTime, escapeHTML, linkify
│   │   ├── api.js         +    # API-клиент для Python-бэкенда
│   │   └── storage.js      +   # localStorage обёртка
│   │
│   └── data/
│       └── mock.js      +      # Моковые данные для разработки
│
├── assets/
│   ├── icons/                 # SVG-иконки (если нужны свои)
│   └── images/                # Логотип, фоны
│
└── api/                       # Справка по API-эндпоинтам
    └── endpoints.md    +       # Документация API
```

## Технологии
- **Фронтенд:** Vanilla JS (ES6 modules), CSS Custom Properties
- **Бэкенд:** Python (FastAPI) — будущая интеграция
- **БД:** SQLite (из текущего бота)
- **Реалтайм:** WebSocket (планируется)

## Темы
Переключатель тёмная/светлая через `data-theme` на `<body>`.
Все цвета в `css/variables.css`.
