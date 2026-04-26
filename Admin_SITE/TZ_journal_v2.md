# ТЗ для Sonnet — Журнал v2 (кнопки, аватары, цитаты)

> Версия: V1.12.10m+ (Site)
> Контекст: Илья — разработчик. Коммиты: `fix(V1.12.10m): [Site] ...`, `feat(V1.12.10m): [bot+Site] ...`. После Site → отдельный коммит, после bot — общий.

## 0. Что трогаем

- **Бот (Python, PTB):**
  - `C:\bot_2\telegram_bot2\api.py` — REST API (FastAPI)
  - `C:\bot_2\telegram_bot2\handlers\journal_handlers.py` — формирование журналов (только смотреть, не править кроме п.3)
  - `C:\bot_2\telegram_bot2\handlers\callback\owner_callbacks.py` строки 196-360 — паттерн действий `jban_/jkick_/jmute_/jremute_`
- **Сайт (React + Vite + Tailwind):**
  - `C:\bot_2\telegram_bot2\Admin_SITE\AdminDashboard.jsx` — основной компонент (~5673 строк)
  - Сборка: `npm run build` в `Admin_SITE/`
- **БД:** SQLite. Таблица `settings (key TEXT PRIMARY KEY, value TEXT)`. Хелперы: `db.get_setting(key, default)`, `db.set_setting(key, value)`.

---

## 1. Журнал — кнопки действий по типу события

### 1.1 Что есть в боте (источник истины — `journal_handlers.py`)

| Тип (event_type / `log.type`) | Кнопки (Inline) под записью в TG-канале журнала |
|---|---|
| `join` | 💬 Написать в ЛС · 🚫 Забанить · 🗑 Удалить · 🔇 Заглушить навсегда |
| `leave` | 💬 Написать в ЛС |
| `kick` | (без кнопок) |
| `ban` | 💬 Написать в ЛС · 🔊 Размьютить · 🚫 Забанить · 🗑 Удалить · 🔇 Заглушить навсегда |
| `mute` | 💬 Написать в ЛС · 🔊 Размьютить · 🚫 Забанить · 🗑 Удалить |
| `unmute` | 💬 Написать в ЛС |
| `unban` | 💬 Написать в ЛС |
| `trigger` | 💬 Написать в ЛС *(в боте без модерационных кнопок; на сайте «Амнистия» уже выведена — оставить и подключить)* |
| `blacklist` (added) | 💬 Написать в ЛС · 🚫 Забанить · 🗑 Удалить |
| `exit_survey` | 💬 Написать в ЛС |

> На сайте сейчас: «Написать в ЛС» (работает) + по 1 декоративной кнопке на тип (`mute`→Размутить, `ban`→Разбанить, `trigger`→Амнистия, `join`→Досье) — **они не работают**. Нужно дополнить набор согласно таблице выше и подключить к API.

### 1.2 Эндпоинты API (добавить в `api.py`)

Все защищаем существующим `Depends(verify_token)` / `is_admin`-проверкой (паттерн смотри в `/api/features` toggle и в существующих POST). `target_chat_id` берём из `bot_state` или env — паттерн уже есть в `owner_callbacks.py`.

```
POST /api/journal/action
body: { user_id: int, action: 'ban' | 'kick' | 'mute_forever' | 'unmute' | 'unban' | 'amnesty' }
```

Внутри роутера — переиспользовать логику из `owner_callbacks.py:204-360`:
- `ban` → `bot.ban_chat_member` + `log_ban(...)`
- `kick` → `bot.ban_chat_member` + `bot.unban_chat_member(only_if_banned=True)` + `log_kick(...)`
- `mute_forever` → `restrict_chat_member(ChatPermissions(can_send_messages=False, ...))` + `log_mute(...)`
- `unmute` → `restrict_chat_member(can_send_messages=True, ...)` + `log_unmute(...)`
- `unban` → `bot.unban_chat_member(only_if_banned=False)` + `log_unban(...)`
- `amnesty` → снять штрафы триггера (см. как сделано «Амнистия» в TG, скорее всего просто `delete_user_warns` / снять флаги — поискать в `triggers_handlers.py` по слову «амнист»; если в боте такой нет — пометить TODO и пока убрать кнопку с сайта)

Возврат: `{ ok: true }` или `{ ok: false, error: '...' }` со статусом 400.

> Доступ: только пользователи с `permissions.journal.moderate` или is_owner/is_admin. Паттерн RBAC уже внедряется (см. `project_rbac_migration.md`).

```
GET /api/user/{user_id}/dossier
```
Минимальный объект для модалки досье на сайте: `{ user_id, username, first_name, photo_url, joined_at, last_message, total_messages, is_blacklisted, freeze_until }` — большая часть полей уже есть в `users` + `regs`. Паттерн собрать как в `/profile/me`.

### 1.3 Сайт — UI

В `AdminDashboard.jsx`, `case 'journal':` (строки 1006–1068):

Заменить блок `grid grid-cols-2 gap-2` на расширенный набор кнопок в зависимости от `log.type`. Карта кнопок:

```js
const JOURNAL_ACTIONS = {
  join:      ['ban', 'kick', 'mute_forever', 'dossier'],
  leave:     [],
  ban:       ['unban', 'kick', 'mute_forever'],          // Размут не нужен — он не в муте
  mute:      ['unmute', 'ban', 'kick'],
  trigger:   ['amnesty'],
  blacklist: ['ban', 'kick'],
  // unban/unmute/kick/exit_survey — без действий, только «Написать в ЛС»
};
```

Стиль кнопок — взять из существующих (`bg-{color}-50 text-{color}-700 ... border border-{color}-200`):
- `ban` — red
- `kick` — rose
- `unban` — blue
- `mute_forever` — yellow (значок 🔇)
- `unmute` — green
- `amnesty` — orange
- `dossier` — indigo (открывает модалку с досье — см. п.2.3)

Обработчик — общая функция:

```js
const journalAction = async (userId, action) => {
  try {
    const r = await fetch('/api/journal/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ user_id: userId, action })
    });
    const d = await r.json();
    if (d.ok) { showToast('Готово'); fetchJournal(); }
    else      { showToast(d.error || 'Ошибка', 'error'); }
  } catch (e) { showToast('Сеть', 'error'); }
};
```

Если `showToast` ещё не глобальный — добавить минимальный (или через `alert`/state-флаг как сделано в `staffError`).

---

## 2. Аватар пользователя в карточке журнала

### 2.1 Эндпоинт

В `users` таблице **нет** колонки `photo_url`. Решение — отдать аватар через прокси-URL:

```
GET /api/user/{user_id}/avatar
```

Реализация:
1. `bot.get_user_profile_photos(user_id, limit=1)` — паттерн уже есть в `handlers/profile_tracker.py:87`
2. Если есть фото → `file = await bot.get_file(photos.photos[0][-1].file_id)` → `await file.download_as_bytearray()` → отдать `Response(content=..., media_type='image/jpeg')`
3. Если нет — `Response(status_code=204)` (фронт нарисует инициалы)
4. **Кэш в памяти**: `dict[user_id] -> (bytes, ts)` на 24 часа, чтобы не долбить TG API на каждый рендер
5. Заголовок ответа: `Cache-Control: public, max-age=86400`

### 2.2 Сайт — карточка

В `case 'journal':` каждая карточка — добавить шапку с круглым аватаром + ID/имя:

```jsx
<div className="flex items-center gap-3">
  <UserAvatar userId={log.user_id} size={40} />
  <div className="flex-1 min-w-0">
    <div className="font-black text-sm text-gray-900 truncate">{log.user || '—'}</div>
    <div className="text-[10px] text-gray-400 font-mono">ID {log.user_id}</div>
  </div>
  <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${tagStyle}`}>{log.tag}</span>
</div>
<div className="text-[11px] text-gray-300 font-mono">{log.time?.replace('T',' ')}</div>
```

Компонент `UserAvatar` (новый, рядом с другими хелперами в начале AdminDashboard.jsx):

```jsx
const UserAvatar = React.memo(({ userId, size = 40, name = '' }) => {
  const [err, setErr] = useState(false);
  const initials = (name || '?').slice(0, 1).toUpperCase();
  const px = `${size}px`;
  if (!userId || err) {
    return (
      <div className="rounded-full bg-gradient-to-tr from-blue-500 to-indigo-600 flex items-center justify-center text-white font-black flex-shrink-0"
           style={{ width: px, height: px, fontSize: size * 0.45 }}>
        {initials}
      </div>
    );
  }
  return (
    <img
      src={`/api/user/${userId}/avatar`}
      alt=""
      onError={() => setErr(true)}
      className="rounded-full object-cover flex-shrink-0 border border-gray-100"
      style={{ width: px, height: px }}
    />
  );
});
```

> Обязательно `React.memo` — иначе при `fetchJournal` каждые N сек будут лишние запросы.

### 2.3 Модалка «Досье» (для `join` карточек)

Открывается по кнопке Досье. Запрос → `/api/user/{user_id}/dossier`. Содержимое: большой аватар + 2 колонки (Telegram / Чат), как сделано на странице Профиль (строки 4754–4914) — переиспользовать стиль.

---

## 3. Настраиваемые цитаты (`<blockquote>`)

### 3.1 Текущее состояние

Сейчас в `AdminDashboard.jsx:1050` стиль вшит в Tailwind arbitrary selectors:
```
[&_blockquote]:border-l-4 [&_blockquote]:border-orange-300
[&_blockquote]:bg-orange-50 [&_blockquote]:px-3 [&_blockquote]:py-2
[&_blockquote]:my-2 [&_blockquote]:rounded-r-xl
```

Цитаты приходят с бэкенда внутри `log.text` (HTML, рендер через `dangerouslySetInnerHTML`).

### 3.2 Хранилище настроек

Ключи в `settings` (ничего не мигрировать — `set_setting` создаёт on-the-fly):

| Ключ | Значения | Default |
|---|---|---|
| `journal_quote_bg`        | hex `#fff7ed`           | `#fff7ed` |
| `journal_quote_stripe_mode` | `solid` \| `alternating` | `solid` |
| `journal_quote_stripe_color1` | hex `#fdba74`         | `#fdba74` |
| `journal_quote_stripe_color2` | hex `#f87171`         | `#f87171` |

Эндпоинты:

```
GET  /api/ui_settings  → { journal_quote_bg, journal_quote_stripe_mode, journal_quote_stripe_color1, journal_quote_stripe_color2, ...на будущее }
POST /api/ui_settings  body: { ...любые из вышеперечисленных }, права: is_owner
```

### 3.3 Сайт — раздел «Меню системы» (`case 'system':`, строка 1113)

Добавить после блока «Управление функциями» (строка 1244) новый блок «Стиль цитат журнала»:

- 4 цвет-пикера (нативный `<input type="color">` + ручной hex рядом)
- Радио `solid` / `alternating` — при `solid` второй цвет дизейблим
- Превью внизу: настоящий `<blockquote>` с тестовым текстом
- Кнопка «Сохранить» → `POST /api/ui_settings`

Состояние и загрузка:

```js
const [quoteCfg, setQuoteCfg] = useState({
  bg: '#fff7ed', stripeMode: 'solid',
  stripe1: '#fdba74', stripe2: '#f87171'
});
useEffect(() => {
  fetch('/api/ui_settings').then(r=>r.json()).then(d => setQuoteCfg({
    bg: d.journal_quote_bg ?? '#fff7ed',
    stripeMode: d.journal_quote_stripe_mode ?? 'solid',
    stripe1: d.journal_quote_stripe_color1 ?? '#fdba74',
    stripe2: d.journal_quote_stripe_color2 ?? '#f87171',
  }));
}, []);
```

### 3.4 Применение к карточкам журнала

Вшитые `[&_blockquote]:...` убираем. Вместо этого — **CSS-переменные на root карточки**:

```jsx
<div
  className="bg-white p-5 rounded-[2rem] border border-gray-100 shadow-sm space-y-3"
  style={{
    '--q-bg':       quoteCfg.bg,
    '--q-stripe-1': quoteCfg.stripe1,
    '--q-stripe-2': quoteCfg.stripeMode === 'alternating' ? quoteCfg.stripe2 : quoteCfg.stripe1,
  }}
>
```

В `index.css` — глобальный стиль:

```css
.journal-html blockquote {
  position: relative;
  background: var(--q-bg);
  padding: 0.5rem 0.75rem 0.5rem 0.875rem;
  margin: 0.5rem 0;
  border-radius: 0 0.75rem 0.75rem 0;     /* острые слева, скруглённые справа */
  font-style: italic;
  color: #374151;
}
.journal-html blockquote::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: linear-gradient(
    to bottom,
    var(--q-stripe-1) 0%, var(--q-stripe-1) 50%,
    var(--q-stripe-2) 50%, var(--q-stripe-2) 100%
  );
  /* при solid обе переменные равны → всё одного цвета */
}
```

Для `alternating` без зоопарка — один градиент 50/50, два цвета. Если хочется именно «чередующиеся полоски» (как зебра), заменить `linear-gradient` на `repeating-linear-gradient`:

```css
background: repeating-linear-gradient(
  to bottom,
  var(--q-stripe-1) 0 8px,
  var(--q-stripe-2) 8px 16px
);
```

> **Уточнение у владельца:** «чередующая разноцветная полоска» — это градиент 2 цвета сверху/снизу, или зебра-полоски по 8px? **Ставлю по умолчанию zebra (`repeating-linear-gradient`)**, т.к. «чередующиеся» естественно читается так. Если потом скажут «нет, градиент» — поменять одну строку CSS.

И добавить `className="journal-html"` к контейнеру с `dangerouslySetInnerHTML`.

---

## 4. Чеклист коммитов

### Коммит 1 — bot side (API)
```
feat(V1.12.10m): [bot] журнал — экшены /api/journal/action + /api/user/{id}/avatar + /api/user/{id}/dossier + /api/ui_settings (GET/POST)
```
Файлы: `api.py`. Никакие хендлеры в боте не трогаем — переиспользуем `log_ban/log_kick/...` и paттерн из `owner_callbacks.py`.

### Коммит 2 — site side
```
feat(V1.12.10m): [Site] журнал — рабочие кнопки модерации, аватары, настраиваемые цитаты в Меню системы
```
Файлы: `Admin_SITE/AdminDashboard.jsx`, `Admin_SITE/index.css`, `Admin_SITE/CHANGELOG_SITE.md`. Перед коммитом: `npm run build` в `Admin_SITE/` — `dist/` тоже коммитим (паттерн уже принят в репо).

---

## 5. Памятки

- **БД-доступ:** `db.cursor` + `db.conn`, sqlite3.Row не имеет `.get()` — обращение `r['key']` в try/except (см. `feedback_sqlite_row.md`).
- **Безопасность вызова бота из API:** `bot` лежит в `app.state.bot` (или ищи паттерн в существующих `/api/...` где уже зовётся `app.state.bot.send_message`). Если контекста нет — `application` импортируется из главного модуля.
- **Каскад:** проверить, что после `journalAction` обновляется список (`fetchJournal()`), и тип лога новой записи будет уже корректный (`ban`, `kick`, `mute`, `unmute`, `unban`).
- **Скриншот UI:** перед сдачей собрать `npm run build`, открыть бот через TWA / прямую вкладку браузера, потыкать кнопки на реальной записи. Прокликать минимум: ban → unban, mute → unmute.
- **CHANGELOG_SITE.md** — добавить запись V1.12.10m в начало; русский, 3-5 пунктов.

## 6. Что НЕ делать

- Не менять формат `log.text` на бэкенде (HTML с `<blockquote>`, `<a>`) — фронт справится.
- Не трогать `log_ban/log_kick/...` — действия с сайта **обязаны** проходить через них (чтобы запись в журнал летела как от админа-инициатора).
- Кнопку «Написать в ЛС» (deeplink `tg://user?id=...`) не ломать.
- Не плодить отдельные эндпоинты `/api/journal/ban`, `/api/journal/kick` — единый `/api/journal/action` с полем `action`.
