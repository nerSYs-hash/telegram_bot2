# Telegram Desktop — Design Spec (извлечено из исходников)

## Шрифты
- Основной: Open Sans / system (-apple-system, Segoe UI)
- Размер текста: 13px (fsize)
- Semibold: 600 weight
- Дата: 13px
- Имя: semibold 13px
- Непрочитанные: 12px bold

## Список чатов (Dialogs)
- Высота строки: **62px** (обычный), **80px** (форум с топиками), **54px** (топик внутри форума)
- Аватар: **46px** (в списке чатов), **20px** (топик)
- Padding: 10px 8px 10px 8px
- Имя: left 68px, top 10px
- Превью: left 68px, top 34px
- Бейдж непрочитанных: height 19px, font 12px bold, padding 5px
- Онлайн-индикатор: **10px** диаметр, **2px** обводка
- Ширина сайдбара (мин): ~380px

## Сообщения (Messages)
- Max width: **430px**
- Padding: **11px 8px 11px 8px**
- Margin: 16px left, 6px top, 56px right, 2px bottom
- Bubble radius (large): **16px**
- Bubble radius (small/attached): 6px (roundRadiusLarge)
- Аватар отправителя: **33px**
- Reply bar: **2px** × **36px**
- Date font: **13px**
- Service message padding: 12px 3px 12px 4px
- Min width: 160px

## Ночная тема (Night)
- windowBg: **#17212b**
- dialogsBg: **#17212b**
- msgOutBg (свои): **#2b5278**
- msgInBg (чужие): **#182533**
- accent: **#5288c1**
- accentLight: **#6ab4f4**
- windowFg (текст): **#f5f5f5**
- windowSubTextFg: **#708499**
- menuIconFg: **#7e8e9f**
- dialogsNameFg: **#f5f5f5**
- dialogsTextFg: **#8d99a5**
- dialogsDateFg: **#6c7883**
- dialogsUnreadBg: **#5eb5f7**
- dialogsBgActive: **#2b5278**
- historyPeer colors (avatars):
  - Peer1: #e17076 (red)
  - Peer2: #7bc862 (green)
  - Peer3: #e5ca77 (yellow)
  - Peer4: #65aadd (blue)
  - Peer5: #a695e7 (purple)
  - Peer6: #ee7aae (pink)
  - Peer7: #6ec9cb (cyan)
  - Peer8: #faa774 (orange)

## Анимации
- Длительность: 150ms (быстрые), 300ms (средние)
- Easing: cubic-bezier(0.4, 0, 0.2, 1) — Material-like

## Header
- Высота: **54px**
- Back button: 40×40px
- Search input border-radius: 18px, height 35px

## Input area
- Min height: ~46px
- Emoji button: 34×34px
- Send button: round, ~34px
- Attach button: 34×34px
