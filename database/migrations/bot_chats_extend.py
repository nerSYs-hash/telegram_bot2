"""Миграция: расширение bot_chats для self-onboarding.
ID: 2026-05-13-bot-chats-extend
Spec: docs/superpowers/specs/2026-05-13-bot-connection-flow-design.md

Добавляет 4 колонки нужные для onboarding flow:
- added_by_user_id: кто добавил бота в чат (= owner workspace по факту)
- title: название чата (snapshot на момент добавления)
- chat_type: group/supergroup/channel
- added_at: когда бот был добавлен (CURRENT_TIMESTAMP)
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'bot_database.db')

NEW_COLUMNS = {
    'added_by_user_id': 'INTEGER',
    'title':            'TEXT',
    'chat_type':        'TEXT',
    'added_at':         'TEXT',
}


def migrate_up(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chats)").fetchall()]
        for name, typ in NEW_COLUMNS.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE bot_chats ADD COLUMN {name} {typ}")
                print(f"[ok] added bot_chats.{name}")
            else:
                print(f"[skip] bot_chats.{name} already exists")
        conn.commit()
    finally:
        conn.close()
    print('[done] bot_chats_extend complete')


if __name__ == '__main__':
    migrate_up()
