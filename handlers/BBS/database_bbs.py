#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL-схема и CRUD-операции для BBS.
"""

import logging

BBS_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS bbs_profiles (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL UNIQUE,
    username          TEXT,
    photos            TEXT    NOT NULL DEFAULT '[]',
    name              TEXT    NOT NULL,
    age               INTEGER NOT NULL,
    params            TEXT    DEFAULT NULL,
    roles             TEXT    NOT NULL DEFAULT '[]',
    city              TEXT    NOT NULL DEFAULT '[]',
    goals             TEXT    NOT NULL DEFAULT '[]',
    about             TEXT    DEFAULT NULL,
    message_ids       TEXT    DEFAULT NULL,
    thread_id         INTEGER DEFAULT NULL,
    published_at      TEXT    DEFAULT NULL,
    edited            INTEGER NOT NULL DEFAULT 0,
    edited_fields     TEXT    NOT NULL DEFAULT '[]',
    reaction_count    INTEGER NOT NULL DEFAULT 0,
    bonus_paid_at     TEXT    DEFAULT NULL,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bbs_reactions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id        INTEGER NOT NULL,
    user_id           INTEGER NOT NULL,
    message_id        INTEGER NOT NULL,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(profile_id, user_id),
    FOREIGN KEY (profile_id) REFERENCES bbs_profiles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bbs_profiles_user    ON bbs_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_bbs_reactions_profile ON bbs_reactions(profile_id);
CREATE INDEX IF NOT EXISTS idx_bbs_reactions_msg     ON bbs_reactions(message_id);
"""


def init_bbs_tables(db):
    """Создать таблицы BBS при старте бота."""
    try:
        db.cursor.executescript(BBS_TABLES_SQL)
        db.conn.commit()

        # Миграция: добавить edited_fields если колонки нет
        try:
            db.cursor.execute("SELECT edited_fields FROM bbs_profiles LIMIT 1")
        except Exception:
            db.cursor.execute("ALTER TABLE bbs_profiles ADD COLUMN edited_fields TEXT NOT NULL DEFAULT '[]'")
            db.conn.commit()
            logging.info("BBS: Migrated — added edited_fields column")

        logging.info("✅ BBS tables initialized")
    except Exception as e:
        logging.error(f"❌ Error initializing BBS tables: {e}")


def get_profile(db, user_id) -> dict | None:
    """Получить анкету из БД."""
    try:
        db.cursor.execute('SELECT * FROM bbs_profiles WHERE user_id = ?', (user_id,))
        row = db.cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logging.error(f"BBS: Error getting profile for {user_id}: {e}")
        return None
