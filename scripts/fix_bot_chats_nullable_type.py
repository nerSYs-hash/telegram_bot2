"""Hotfix V1.17.0b20: rebuild bot_chats — сделать колонку type nullable.

Проблема: старая схема имела `type TEXT NOT NULL` без default. Новый код
(handlers/bot_membership + db_workspaces.add_bot_chat) пишет в `chat_type`,
а не в `type`, → INSERT падает с `NOT NULL constraint failed: bot_chats.type`.

Rebuild через CREATE...AS SELECT...DROP...RENAME — стандартный SQLite паттерн.
Сохраняем все колонки и дефолты, кроме NOT NULL у `type`.

Идемпотентный (DROP IF EXISTS bot_chats_new в начале).

Run: python scripts/fix_bot_chats_nullable_type.py
"""
import os
import sqlite3
import shutil
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'bot_database.db')


def main():
    if not os.path.exists(DB_PATH):
        print(f'[FAIL] DB not found: {DB_PATH}')
        return

    # Backup
    backup_dir = os.path.join(os.path.dirname(DB_PATH), '..', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'pre_bot_chats_fix_{ts}.db')
    shutil.copy2(DB_PATH, backup_path)
    print(f'[backup] {backup_path}')

    conn = sqlite3.connect(DB_PATH)
    try:
        print('=== BEFORE ===')
        for r in conn.execute('PRAGMA table_info(bot_chats)').fetchall():
            print(r)

        # Check if rebuild needed
        cols = {r[1]: r for r in conn.execute('PRAGMA table_info(bot_chats)').fetchall()}
        type_col = cols.get('type')
        if not type_col:
            print('[skip] no column "type" — nothing to fix')
            return
        if type_col[3] == 0:  # notnull flag
            print('[skip] column "type" already nullable — already fixed')
            return

        conn.execute('DROP TABLE IF EXISTS bot_chats_new')
        conn.execute('''
            CREATE TABLE bot_chats_new (
                chat_id           INTEGER PRIMARY KEY,
                type              TEXT,
                title             TEXT,
                username          TEXT,
                is_forum          INTEGER DEFAULT 0,
                added_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                removed_at        TIMESTAMP,
                last_seen_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                workspace_id      INTEGER NOT NULL DEFAULT 1,
                added_by_user_id  INTEGER,
                chat_type         TEXT
            )
        ''')
        print('[ok] created bot_chats_new')

        cur = conn.execute('''
            INSERT INTO bot_chats_new
                (chat_id, type, title, username, is_forum, added_at, removed_at,
                 last_seen_at, workspace_id, added_by_user_id, chat_type)
            SELECT chat_id, type, title, username, is_forum, added_at, removed_at,
                   last_seen_at, workspace_id, added_by_user_id, chat_type
            FROM bot_chats
        ''')
        print(f'[ok] copied {cur.rowcount} rows')

        conn.execute('DROP TABLE bot_chats')
        conn.execute('ALTER TABLE bot_chats_new RENAME TO bot_chats')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_bot_chats_workspace '
                     'ON bot_chats(workspace_id)')
        conn.commit()
        print('[ok] renamed + reindexed')

        print('=== AFTER ===')
        for r in conn.execute('PRAGMA table_info(bot_chats)').fetchall():
            print(r)
        print('\n[done] bot_chats.type теперь nullable')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
