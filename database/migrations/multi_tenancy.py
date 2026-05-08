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
