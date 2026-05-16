"""V1.17.0c1: добавить колонку bot_chats.role + сделать type nullable.

Часть подпроекта F (роли чатов в workspace UI). Колонка role хранит назначенную
владельцем семантику чата: 'main' / 'admin' / 'journal' (или NULL = без роли).
Параллельно завершаем отложенный fix V1.17.0b20 — переводим колонку `type`
(legacy small-bot) в NULLABLE, иначе add_bot_chat() падает на NOT NULL.

Делается за один rebuild через CREATE...AS SELECT...DROP...RENAME (стандартный
SQLite паттерн — ALTER COLUMN отсутствует).

Идемпотентен:
- если bot_chats.role уже существует И bot_chats.type уже nullable → no-op
- иначе rebuild

Run: python scripts/V1_17_0c1_add_chat_role.py
"""
import os
import sqlite3
import shutil
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'bot_database.db')


def main(db_path: str = DB_PATH) -> int:
    if not os.path.exists(db_path):
        print(f'[FAIL] DB not found: {db_path}', file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    try:
        cols = {r[1]: r for r in conn.execute('PRAGMA table_info(bot_chats)').fetchall()}
        has_role = 'role' in cols
        type_nullable = cols.get('type', (None, None, None, 0))[3] == 0

        if has_role and type_nullable:
            print('[skip] bot_chats.role уже есть и type уже nullable — no-op')
            return 0

        # Backup
        backup_dir = os.path.join(os.path.dirname(db_path), '..', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'pre_chat_role_{ts}.db')
        shutil.copy2(db_path, backup_path)
        print(f'[backup] {backup_path}')

        print('=== BEFORE ===')
        for r in conn.execute('PRAGMA table_info(bot_chats)').fetchall():
            print(' ', r)

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
                chat_type         TEXT,
                role              TEXT CHECK (role IS NULL OR role IN ('main','admin','journal'))
            )
        ''')
        print('[ok] created bot_chats_new')

        # SELECT с COALESCE на role чтобы перенести если уже была
        existing_cols = set(cols.keys())
        role_select = 'role' if 'role' in existing_cols else 'NULL'

        cur = conn.execute(f'''
            INSERT INTO bot_chats_new
                (chat_id, type, title, username, is_forum, added_at, removed_at,
                 last_seen_at, workspace_id, added_by_user_id, chat_type, role)
            SELECT chat_id, type, title, username, is_forum, added_at, removed_at,
                   last_seen_at, workspace_id, added_by_user_id, chat_type, {role_select}
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
            print(' ', r)
        print('\n[done] bot_chats.role добавлен, type теперь nullable')
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
