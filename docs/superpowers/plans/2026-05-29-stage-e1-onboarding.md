# E1 — Упрощённое подключение чата (онбординг) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать «портянку» выбора сообщества из группового чата при подключении бота; группа всегда авто-привязывается как `main`, владелец получает DM, в чате — короткое самоудаляемое приветствие.

**Architecture:** Всё новое поведение прячется за уже существующим флагом `CONNECT_FLOW_V2` в `handlers/bot_membership.py`. При флаге OFF — старый код байт-в-байт (регресс-гарантия). При ON — новая упрощённая ветка: авто-создание workspace (`role='main'`, owner = добавивший), без inline-выбора и без гейта регистрации; приветствие в группе самоудаляется через job_queue; владельцу уходит DM. Роли/группировка чатов — будущий E2 (Центр подключений на сайте).

**Tech Stack:** python-telegram-bot (ChatMemberHandler, JobQueue), sqlite3, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-05-29-stage-e1-onboarding-design.md`

---

## Файловая карта

- **Modify:** `handlers/bot_membership.py` — текст-хелперы, job-хелперы самоудаления, новая ветка E1 в `on_bot_added_to_chat`.
- **Test:** `tests/test_bot_membership.py` — новые тесты под флагом `CONNECT_FLOW_V2=1`; существующие (флаг OFF) не трогаем.
- **Docs:** `docs/ROADMAP_full_isolation_2026-05-28.md`, `CHANGELOG.md`.

`on_connect_chat_callback` НЕ трогаем — он остаётся для legacy-режима (флаг OFF) и его тесты должны остаться зелёными.

---

## Task 1: Хелперы текстов и самоудаления приветствия

**Files:**
- Modify: `handlers/bot_membership.py` (после строки 34, рядом с `_login_kb`)
- Test: `tests/test_bot_membership.py`

- [ ] **Step 1: Write the failing tests**

Добавить в конец `tests/test_bot_membership.py`:

```python
# ── E1 (V1.17.0R): упрощённый онбординг ──

@pytest.mark.asyncio
async def test_schedule_greeting_delete_calls_run_once():
    from handlers.bot_membership import _schedule_greeting_delete
    ctx = MagicMock()
    ctx.job_queue.run_once = MagicMock()
    _schedule_greeting_delete(ctx, chat_id=-100, message_id=7, delay=120)
    ctx.job_queue.run_once.assert_called_once()
    _args, kwargs = ctx.job_queue.run_once.call_args
    assert kwargs['data'] == {'chat_id': -100, 'message_id': 7}


@pytest.mark.asyncio
async def test_schedule_greeting_delete_no_jobqueue_is_safe():
    from handlers.bot_membership import _schedule_greeting_delete
    ctx = MagicMock()
    ctx.job_queue = None
    # не должно бросать исключение
    _schedule_greeting_delete(ctx, chat_id=-100, message_id=7, delay=120)


@pytest.mark.asyncio
async def test_delete_greeting_job_calls_delete_message():
    from handlers.bot_membership import _delete_greeting_job
    ctx = MagicMock()
    ctx.bot.delete_message = AsyncMock()
    ctx.job.data = {'chat_id': -100, 'message_id': 7}
    await _delete_greeting_job(ctx)
    ctx.bot.delete_message.assert_awaited_once_with(-100, 7)


def test_owner_dm_text_contains_title_and_site():
    from handlers.bot_membership import _owner_dm_text, SITE_URL
    txt = _owner_dm_text('Моя Группа')
    assert 'Моя Группа' in txt
    assert SITE_URL in txt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_bot_membership.py -k "greeting or owner_dm" -v`
Expected: FAIL — `ImportError: cannot import name '_schedule_greeting_delete'` (и т.д.).

- [ ] **Step 3: Implement the helpers**

В `handlers/bot_membership.py` после функции `_login_kb` (строка 34) добавить:

```python
GREETING_DELETE_SECONDS = int(os.getenv('GREETING_DELETE_SECONDS', '120'))


def _greeting_text() -> str:
    """Короткое приветствие в группе (самоудаляемое). Тексты — черновик,
    финал согласуем перед выкатом (см. спеку E1)."""
    return (
        "👋 Привет! Я Puls_bot — статистика, экономика и модерация чата.\n"
        "⚠️ Для полной работы дай мне права администратора.\n"
        "Это сообщение исчезнет через пару минут, чтобы не засорять чат."
    )


def _owner_dm_text(chat_title: str) -> str:
    """Личное сообщение владельцу после подключения чата."""
    return (
        f"✅ Подключил чат «{chat_title}» к твоему кабинету.\n"
        f"Зайди настроить — роли, модули, статистика: {SITE_URL}"
    )


async def _delete_greeting_job(context):
    """JobQueue-callback: удаляет приветствие в группе. Ошибки не критичны."""
    data = context.job.data
    try:
        await context.bot.delete_message(data['chat_id'], data['message_id'])
    except Exception as e:
        logger.debug(f"greeting auto-delete failed: {e}")


def _schedule_greeting_delete(context, chat_id, message_id, delay=GREETING_DELETE_SECONDS):
    """Планирует самоудаление приветствия. job_queue может отсутствовать."""
    jq = getattr(context, 'job_queue', None)
    if jq is None:
        return
    try:
        jq.run_once(
            _delete_greeting_job, delay,
            data={'chat_id': chat_id, 'message_id': message_id},
            name=f"del_greeting_{chat_id}",
        )
    except Exception as e:
        logger.warning(f"schedule greeting delete failed: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_bot_membership.py -k "greeting or owner_dm" -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```
git add handlers/bot_membership.py tests/test_bot_membership.py
git commit -m "feat(V1.17.0R1) [E1]: хелперы онбординга — приветствие, DM, самоудаление"
```

---

## Task 2: Упрощённая ветка E1 — авто-`main`, без портянки и гейта

**Files:**
- Modify: `handlers/bot_membership.py` — вставить новую ветку в `on_bot_added_to_chat` ПОСЛЕ блока «3+4. Already bound?» (после его `return`, строка ~140) и ПЕРЕД «5. registered?» (строка ~142).
- Test: `tests/test_bot_membership.py`

- [ ] **Step 1: Write the failing tests**

Добавить в `tests/test_bot_membership.py`:

```python
@pytest.mark.asyncio
async def test_e1_owner_with_existing_ws_autoconnects(db, monkeypatch):
    """Флаг ON: владелец с сообществом добавляет бота → авто-создан НОВЫЙ ws
    role=main, БЕЗ inline-кнопок выбора, бот не уходит."""
    monkeypatch.setenv('CONNECT_FLOW_V2', '1')
    from handlers.bot_membership import on_bot_added_to_chat
    db.conn.execute("INSERT INTO users (user_id, username) VALUES (42,'alice')")
    db.conn.commit()
    create_workspace(db.conn, 'Existing', owner_user_id=42)  # ws=1

    update = _make_update(999, 'administrator', -200, 'New Chat', 'supergroup', 42)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)

    ws_id = db.get_workspace_by_chat(-200)
    assert ws_id is not None and ws_id != 1  # отдельный новый ws
    role = db.conn.execute(
        "SELECT role FROM bot_chats WHERE chat_id=?", (-200,)).fetchone()[0]
    assert role == 'main'
    ctx.bot.leave_chat.assert_not_called()
    # никаких connect_chat-кнопок ни в одном отправленном сообщении
    for _a, kwargs in ctx.bot.send_message.call_args_list:
        mk = kwargs.get('reply_markup')
        if mk is not None and hasattr(mk, 'inline_keyboard'):
            data = [b.callback_data for row in mk.inline_keyboard for b in row]
            assert not any((d or '').startswith('connect_chat') for d in data)


@pytest.mark.asyncio
async def test_e1_unregistered_connects_without_leave(db, monkeypatch):
    """Флаг ON: гейт регистрации убран — незарегистрированный подключает чат,
    бот НЕ уходит, ws создаётся с ним как owner."""
    monkeypatch.setenv('CONNECT_FLOW_V2', '1')
    from handlers.bot_membership import on_bot_added_to_chat
    update = _make_update(999, 'administrator', -210, 'Fresh', 'supergroup', 666)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)

    ws_id = db.get_workspace_by_chat(-210)
    assert ws_id is not None
    owner = db.conn.execute(
        "SELECT owner_user_id FROM workspaces WHERE id=?", (ws_id,)).fetchone()[0]
    assert owner == 666
    ctx.bot.leave_chat.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_bot_membership.py -k "e1_owner or e1_unregistered" -v`
Expected: FAIL — под флагом ON сейчас отрабатывает старая ветка #6 (кнопки) для owner и #5 (leave) для незарегистрированного.

- [ ] **Step 3: Implement the E1 branch**

В `handlers/bot_membership.py`, в `on_bot_added_to_chat`, сразу ПОСЛЕ блока «3+4. Already bound?» (после его `return` на строке ~140) и ПЕРЕД комментарием `# 5. registered?` вставить:

```python
    # ── E1 (V1.17.0R): упрощённый онбординг за флагом CONNECT_FLOW_V2 ──
    # Чат подключается «как есть» (role=main), owner = добавивший. Роли и
    # группировка в сообщества раздаются на сайте (E2 — Центр подключений).
    # Ноль inline-выбора в групповом чате; гейт регистрации убран (вход через
    # OAuth-кнопку сам создаёт сессию).
    if connect_flow_v2_enabled():
        ws_id = create_workspace(db.conn, chat_title, owner_user_id=from_user.id)
        add_bot_chat(db.conn, chat_id, ws_id, added_by=from_user.id,
                     title=chat_title, chat_type=chat.type, role='main')
        invalidate_cache(chat_id)
        logger.info(
            f"E1 auto-connect chat={chat_id} ws={ws_id} "
            f"owner={from_user.id} role=main"
        )
        # приветствие в группе (самоудаляемое)
        try:
            sent = await context.bot.send_message(
                chat_id, _greeting_text(), reply_markup=_login_kb())
            _schedule_greeting_delete(context, chat_id, sent.message_id)
        except Exception as e:
            logger.warning(f"E1 greeting send failed: {e}")
        # DM владельцу
        try:
            await context.bot.send_message(
                from_user.id, _owner_dm_text(chat_title),
                reply_markup=_login_kb())
        except Exception as e:
            logger.warning(f"E1 owner DM failed: {e}")
        return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_bot_membership.py -k "e1_owner or e1_unregistered" -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```
git add handlers/bot_membership.py tests/test_bot_membership.py
git commit -m "feat(V1.17.0R2) [E1]: авто-привязка main без портянки и гейта регистрации (флаг CONNECT_FLOW_V2)"
```

---

## Task 3: Приветствие в группе + DM владельцу действительно отправляются

**Files:**
- Test: `tests/test_bot_membership.py` (поведение уже реализовано в Task 2 — фиксируем контрактом)

- [ ] **Step 1: Write the failing tests**

Добавить в `tests/test_bot_membership.py`:

```python
@pytest.mark.asyncio
async def test_e1_sends_group_greeting_and_owner_dm(db, monkeypatch):
    """Флаг ON: бот шлёт приветствие в группу И отдельный DM владельцу."""
    monkeypatch.setenv('CONNECT_FLOW_V2', '1')
    from handlers.bot_membership import on_bot_added_to_chat
    update = _make_update(999, 'administrator', -220, 'Greet Chat', 'supergroup', 77)
    ctx = _make_context(999)
    await on_bot_added_to_chat(update, ctx, db)

    sent_chat_ids = [a[0] for a, _ in ctx.bot.send_message.call_args_list]
    assert -220 in sent_chat_ids          # приветствие в группу
    assert 77 in sent_chat_ids            # DM владельцу


@pytest.mark.asyncio
async def test_e1_schedules_greeting_self_delete(db, monkeypatch):
    """Флаг ON: самоудаление приветствия запланировано через job_queue."""
    monkeypatch.setenv('CONNECT_FLOW_V2', '1')
    from handlers.bot_membership import on_bot_added_to_chat
    update = _make_update(999, 'administrator', -230, 'Del Chat', 'supergroup', 88)
    ctx = _make_context(999)
    ctx.job_queue.run_once = MagicMock()
    await on_bot_added_to_chat(update, ctx, db)
    ctx.job_queue.run_once.assert_called_once()
```

Примечание: `_make_context` возвращает `ctx.bot.send_message = AsyncMock()`, который по умолчанию возвращает `MagicMock`, поэтому `sent.message_id` существует и `_schedule_greeting_delete` отработает.

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_bot_membership.py -k "e1_sends or e1_schedules" -v`
Expected: PASS (2 passed) — поведение уже реализовано в Task 2. Если падает — значит ветка из Task 2 не отправляет оба сообщения/не планирует удаление; исправить ветку.

- [ ] **Step 3: Commit**

```
git add tests/test_bot_membership.py
git commit -m "test(V1.17.0R3) [E1]: контракт приветствия в группе + DM владельцу + самоудаление"
```

---

## Task 4: Регресс — флаг OFF байт-в-байт

**Files:**
- Test: запуск всего файла + смежных.

- [ ] **Step 1: Run the full membership test file**

Run: `python -m pytest tests/test_bot_membership.py -v`
Expected: PASS — все старые тесты (`test_shows_buttons_when_user_owns_workspace`, `test_leaves_when_owner_not_registered`, и т.д.) зелёные, потому что они идут с флагом `CONNECT_FLOW_V2` по умолчанию OFF. Плюс новые E1-тесты зелёные.

- [ ] **Step 2: Run connect-flow lifecycle tests (флаг ON legacy callback)**

Run: `python -m pytest tests/test_connect_flow_lifecycle.py -v`
Expected: PASS — `on_connect_chat_callback` не менялся, reconnect-логика не менялась.

- [ ] **Step 3: Run lint guard (ruff, как в CI)**

Run: `python -m ruff check handlers/bot_membership.py tests/test_bot_membership.py`
Expected: без ошибок. Если ruff недоступен — пропустить, отметить в отчёте.

- [ ] **Step 4: No commit** (этап только проверочный; если правки понадобились — коммит `fix(V1.17.0R3a) [E1]: ...`).

---

## Task 5: Документация — ROADMAP + CHANGELOG

**Files:**
- Modify: `docs/ROADMAP_full_isolation_2026-05-28.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Обновить ROADMAP**

В `docs/ROADMAP_full_isolation_2026-05-28.md` в секции «Этап E» отметить, что E1 (путь 1 — подключение группы) сделан за флагом `CONNECT_FLOW_V2`; E2 (Центр подключений, роли/каналы) и E3 (туториал) — впереди. Добавить короткую таблицу прогресса Этапа E аналогично таблицам Этапов A/C.

- [ ] **Step 2: Обновить CHANGELOG**

В `CHANGELOG.md` добавить запись V1.17.0R1-R3: «E1 — упрощённое подключение чата: авто-привязка main, DM владельцу, самоудаляемое приветствие; портянка выбора и гейт регистрации убраны (за флагом CONNECT_FLOW_V2)».

- [ ] **Step 3: Commit**

```
git add docs/ROADMAP_full_isolation_2026-05-28.md CHANGELOG.md
git commit -m "docs(V1.17.0R4) [E1]: ROADMAP + CHANGELOG — упрощённый онбординг подключения"
```

---

## Отложено (вне E1, не делать в этом плане)

- **Финал текстов + реальные ссылки** (Поддержка/Новости/Инструкция) и **пользовательский FAQ-пункт** — зависят от согласованных формулировок (Илья отложил). Сделать перед выкатом/флипом флага, отдельной мелкой задачей.
- **Флип флагов на проде** (`CONNECT_FLOW_V2=ON`, `LOGIN_URL_BUTTON=ON`) — приёмка вместе с T9, ручной шаг Ильи.
- **E2 — Центр подключений** (роли/каналы, диплинк `?startchannel` механизм A) — отдельная спека.
- **E3 — туториал нового владельца** — отдельная спека.

## Самопроверка плана (выполнена при написании)

- **Покрытие спеки:** §3.1 поведение → Task 2; §3.2 сообщения/самоудаление → Task 1+3; §3.3 тумблер → ветка за `CONNECT_FLOW_V2` (Task 2), FAQ отложен с причиной; §4 edge cases → существующие ранние return сохранены (Task 4 регресс); §5 тесты → Task 1-4; §6 критерий приёмки → покрыт тестами Task 2-3 + ручной флип. Гэпов нет.
- **Плейсхолдеры:** нет «TBD»; отложенные пункты вынесены явно с причиной.
- **Согласованность типов:** `_schedule_greeting_delete(context, chat_id, message_id, delay)`, `_delete_greeting_job(context)` с `context.job.data={'chat_id','message_id'}`, `_owner_dm_text(chat_title)`, `_greeting_text()` — имена совпадают между Task 1 (определение) и Task 2-3 (использование).
