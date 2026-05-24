"""H2: kind-колонка + сидер Pulse ws=1 из текущих .env-значений.

Идемпотентно. Только ws=1. Бэкап БД делает RUNBOOK перед запуском.
"""
import sqlite3


def up_add_kind_column(conn: sqlite3.Connection) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chat_topics)")]
    if 'kind' not in cols:
        conn.execute("ALTER TABLE bot_chat_topics ADD COLUMN kind TEXT")
    conn.commit()


def seed_pulse_ws1(
    conn: sqlite3.Connection,
    main_chat_id: int,
    admin_chat_id: int,
    threads: dict,
) -> None:
    """Проставляет роли чатов ws=1 (если NULL) и сидит kind-топики.
    threads: {'applications': 241, 'dossier': 176, 'bug_bot': ..., ...}."""
    cur = conn.execute(
        "SELECT role FROM bot_chats WHERE chat_id=? AND workspace_id=1",
        (main_chat_id,),
    ).fetchone()
    if cur is not None and (cur[0] is None or cur[0] == ''):
        conn.execute(
            "UPDATE bot_chats SET role='main' WHERE chat_id=? AND workspace_id=1",
            (main_chat_id,),
        )
    a_cur = conn.execute(
        "SELECT role FROM bot_chats WHERE chat_id=? AND workspace_id=1",
        (admin_chat_id,),
    ).fetchone()
    if a_cur is not None and (a_cur[0] is None or a_cur[0] == '') and admin_chat_id != main_chat_id:
        conn.execute(
            "UPDATE bot_chats SET role='admin' WHERE chat_id=? AND workspace_id=1",
            (admin_chat_id,),
        )
    for kind, thread_id in threads.items():
        if not thread_id:
            continue
        exists = conn.execute(
            "SELECT 1 FROM bot_chat_topics WHERE workspace_id=1 AND kind=?",
            (kind,),
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO bot_chat_topics "
            "(workspace_id, chat_id, thread_id, name, source, kind) "
            "VALUES (1, ?, ?, ?, 'h2_seed', ?)",
            (admin_chat_id, thread_id, kind, kind),
        )
    conn.commit()
