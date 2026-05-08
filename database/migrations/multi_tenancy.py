"""
Миграция: добавление мультитенантности.
ID: 2026-05-08-multi-tenancy
Spec: docs/superpowers/specs/2026-05-08-multi-tenancy-foundation-design.md
"""
import os
import shutil
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'bot_database.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')


def backup_db(db_path: str = DB_PATH) -> str:
    """Делает копию БД перед миграцией. Возвращает путь к бэкапу."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(BACKUP_DIR, f'pre_multitenancy_{ts}.db')
    shutil.copy2(db_path, dest)
    return dest


def up_create_workspaces_tables(conn: sqlite3.Connection) -> None:
    """Создаёт workspaces и workspace_members таблицы."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS workspaces (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            owner_user_id   INTEGER NOT NULL,
            is_pulse_themed INTEGER NOT NULL DEFAULT 0,
            plan            TEXT    NOT NULL DEFAULT 'free',
            settings_json   TEXT,
            created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workspace_members (
            workspace_id INTEGER NOT NULL,
            user_id      INTEGER NOT NULL,
            role         TEXT    NOT NULL CHECK (role IN ('owner','admin','moderator')),
            joined_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, user_id),
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id);
    ''')
    conn.commit()


def up_seed_pulse_workspace(conn: sqlite3.Connection, owner_user_id: int) -> int:
    """Создаёт workspace_id=1 (Pulse Москва) с Витей-владельцем."""
    cur = conn.execute(
        'INSERT INTO workspaces (id, name, owner_user_id, is_pulse_themed, plan) '
        'VALUES (1, ?, ?, 1, ?)',
        ('Pulse Москва', owner_user_id, 'free')
    )
    conn.execute(
        'INSERT INTO workspace_members (workspace_id, user_id, role) '
        'VALUES (1, ?, ?)',
        (owner_user_id, 'owner')
    )
    conn.commit()
    return cur.lastrowid


def down_drop_workspaces_tables(conn: sqlite3.Connection) -> None:
    """Откат: удаляет workspaces и workspace_members."""
    conn.executescript('''
        DROP TABLE IF EXISTS workspace_members;
        DROP TABLE IF EXISTS workspaces;
    ''')
    conn.commit()


TENANTED_TABLES = [
    'anketa_edits', 'bbs_other_posts', 'bbs_profiles', 'bbs_reactions',
    'bingo_cards', 'bingo_games', 'bot_chats', 'bot_chat_topics',
    'branding_settings', 'bug_cards', 'challenges', 'chat_stats',
    'combo_claims', 'daily_stats_summary', 'economy_cancellations',
    'economy_history', 'economy_section_toggles', 'economy_settings',
    'exit_interviews', 'hall_of_fame', 'journal_messages', 'lotteries',
    'lottery_tickets', 'marketplace_services', 'messages',
    'monthly_gift_participants', 'monthly_gifts',
    'press_release_targets', 'press_release_templates', 'press_release_versions',
    'reactor', 'referral_links', 'referral_seasons', 'referral_stats',
    'scheduled_posts', 'shipper_matches', 'shipper_resonance_stats',
    'sprint_claims', 'stat_events_log', 'title_packages', 'title_rub_requests',
    'titles', 'top_activists_history', 'top_activists_percent', 'topics',
    'transactions', 'trigger_violations', 'triggers',
    'user_joins', 'user_stats', 'user_stats_hourly',
]

GLOBAL_TABLES = [
    'users', 'exchange_rate_history', 'shipper_phrases',
    'settings', 'sqlite_sequence',
]


def up_tenantize_existing_tables(conn: sqlite3.Connection) -> None:
    """ALTER каждую тенантизируемую таблицу: добавить workspace_id NOT NULL DEFAULT 1.
    Создать индекс idx_<table>_workspace.
    Существующие строки получают workspace_id=1 автоматически (DEFAULT 1)."""
    for tbl in TENANTED_TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (tbl,)
        ).fetchone()
        if not exists:
            print(f'[skip] table {tbl} does not exist')
            continue
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if 'workspace_id' in cols:
            print(f'[skip] {tbl}.workspace_id already exists')
            continue
        conn.execute(
            f'ALTER TABLE {tbl} ADD COLUMN workspace_id INTEGER NOT NULL DEFAULT 1'
        )
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{tbl}_workspace ON {tbl}(workspace_id)'
        )
        print(f'[ok] tenantized {tbl}')
    conn.commit()


def down_remove_workspace_id(conn: sqlite3.Connection) -> None:
    """Откат: удаляет workspace_id из всех тенантизированных таблиц.
    SQLite >=3.35 поддерживает ALTER DROP COLUMN; иначе fallback через rebuild."""
    sqlite_ver = sqlite3.sqlite_version_info
    for tbl in TENANTED_TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if 'workspace_id' not in cols:
            continue
        conn.execute(f'DROP INDEX IF EXISTS idx_{tbl}_workspace')
        if sqlite_ver >= (3, 35, 0):
            conn.execute(f'ALTER TABLE {tbl} DROP COLUMN workspace_id')
        else:
            kept_cols = [c for c in cols if c != 'workspace_id']
            cols_csv = ', '.join(kept_cols)
            conn.execute(f'CREATE TABLE {tbl}__new AS SELECT {cols_csv} FROM {tbl}')
            conn.execute(f'DROP TABLE {tbl}')
            conn.execute(f'ALTER TABLE {tbl}__new RENAME TO {tbl}')
        print(f'[ok] removed workspace_id from {tbl}')
    conn.commit()


def migrate_up(db_path: str = DB_PATH, owner_user_id: int | None = None) -> str:
    """Полная миграция up. Делает backup, создаёт таблицы, тенантизирует,
    создаёт workspace=1 (Pulse). Возвращает путь к backup."""
    if owner_user_id is None:
        owner_user_id = int(os.getenv('MAIN_ADMIN_ID', '0'))
        if not owner_user_id:
            raise ValueError('MAIN_ADMIN_ID not set in env and owner_user_id not passed')

    backup_path = backup_db(db_path)
    print(f'[backup] {backup_path}')

    conn = sqlite3.connect(db_path)
    try:
        up_create_workspaces_tables(conn)
        existing = conn.execute('SELECT 1 FROM workspaces WHERE id=1').fetchone()
        if not existing:
            up_seed_pulse_workspace(conn, owner_user_id)
        else:
            print('[skip] workspace_id=1 already exists')
        up_tenantize_existing_tables(conn)
    finally:
        conn.close()
    print('[done] migrate_up complete')
    return backup_path


def migrate_down(db_path: str = DB_PATH) -> None:
    """Полный откат. Бэкап делать ОТДЕЛЬНО руками если нужен."""
    conn = sqlite3.connect(db_path)
    try:
        down_remove_workspace_id(conn)
        down_drop_workspaces_tables(conn)
    finally:
        conn.close()
    print('[done] migrate_down complete')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'down':
        migrate_down()
    else:
        migrate_up()
