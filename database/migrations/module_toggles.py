"""Module toggles migration — 3 tables + index.
ID: 2026-05-20-module-toggles
Spec: docs/superpowers/specs/2026-05-20-module-toggles-design.md
"""
import sqlite3


def up(conn: sqlite3.Connection) -> None:
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS module_toggles (
            workspace_id INTEGER NOT NULL,
            module_id    TEXT    NOT NULL,
            is_enabled   INTEGER NOT NULL DEFAULT 0,
            updated_by   INTEGER,
            updated_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, module_id)
        );

        CREATE TABLE IF NOT EXISTS module_toggle_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            module_id    TEXT    NOT NULL,
            action       TEXT    NOT NULL CHECK (action IN ('enable','disable')),
            reason       TEXT,
            changed_by   INTEGER NOT NULL,
            changed_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_mth_ws_mod
            ON module_toggle_history(workspace_id, module_id, changed_at DESC);

        CREATE TABLE IF NOT EXISTS module_toggle_cache_version (
            workspace_id INTEGER PRIMARY KEY,
            version      INTEGER NOT NULL DEFAULT 0
        );
    ''')
    conn.commit()
