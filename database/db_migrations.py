#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Миграции базы данных. Вынесено из Database."""

import logging


def migrate_to_decimal_balances(db):
    """Migrate balance fields from INTEGER to REAL for decimal support"""
    try:
        db.cursor.execute("PRAGMA table_info(users)")
        columns = {row['name']: row['type'] for row in db.cursor.fetchall()}

        if columns.get('balance') == 'INTEGER':
            logging.info("Migrating balances to REAL...")

            # 1. Create backup tables
            db.cursor.execute('CREATE TABLE users_backup AS SELECT * FROM users')
            db.cursor.execute('CREATE TABLE transactions_backup AS SELECT * FROM transactions')

            # 2. Drop original tables
            db.cursor.execute('DROP TABLE users')
            db.cursor.execute('DROP TABLE transactions')

            # 3. Create new tables with REAL types
            db.cursor.execute('''
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance REAL DEFAULT 0.0,
                    is_admin BOOLEAN DEFAULT 0,
                    is_owner BOOLEAN DEFAULT 0,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    referrer_id INTEGER,
                    referral_code TEXT UNIQUE,
                    is_qualified BOOLEAN DEFAULT 0,
                    frozen_balance REAL DEFAULT 0.0,
                    freeze_until TIMESTAMP,
                    is_left INTEGER DEFAULT 0,
                    FOREIGN KEY (referrer_id) REFERENCES users(user_id)
                )
            ''')

            db.cursor.execute('''
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id INTEGER,
                    to_user_id INTEGER,
                    amount REAL NOT NULL,
                    transaction_type TEXT NOT NULL,
                    description TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (from_user_id) REFERENCES users(user_id),
                    FOREIGN KEY (to_user_id) REFERENCES users(user_id)
                )
            ''')

            # 4. Copy data back
            db.cursor.execute('''
                INSERT INTO users
                SELECT user_id, username, first_name, last_name,
                       CAST(balance AS REAL), is_admin, is_owner,
                       joined_at, last_active, referrer_id, referral_code,
                       is_qualified, CAST(frozen_balance AS REAL), freeze_until,
                       COALESCE(is_left, 0)
                FROM users_backup
            ''')

            db.cursor.execute('''
                INSERT INTO transactions
                SELECT id, from_user_id, to_user_id, CAST(amount AS REAL),
                       transaction_type, description, timestamp
                FROM transactions_backup
            ''')

            # 5. Drop backup tables
            db.cursor.execute('DROP TABLE users_backup')
            db.cursor.execute('DROP TABLE transactions_backup')

            db.conn.commit()
            logging.info("✅ Migration to REAL balances completed!")
        else:
            logging.info("Balances already using REAL type")

    except Exception as e:
        logging.error(f"Error during migration: {e}")
        db.conn.rollback()
        try:
            db.cursor.execute('DROP TABLE IF EXISTS users')
            db.cursor.execute('DROP TABLE IF EXISTS transactions')
            db.cursor.execute('ALTER TABLE users_backup RENAME TO users')
            db.cursor.execute('ALTER TABLE transactions_backup RENAME TO transactions')
            db.conn.commit()
            logging.error("Migration failed, restored from backup")
        except:
            logging.error("Failed to restore from backup!")

    # MIGRATE user_stats and chat_stats pulses_mined to REAL
    try:
        db.cursor.execute("PRAGMA table_info(user_stats)")
        columns = {row['name']: row['type'] for row in db.cursor.fetchall()}

        if columns.get('pulses_mined') == 'INTEGER':
            logging.info("Migrating user_stats.pulses_mined to REAL...")

            db.cursor.execute('CREATE TABLE user_stats_backup AS SELECT * FROM user_stats')
            db.cursor.execute('DROP TABLE user_stats')

            db.cursor.execute('''
                CREATE TABLE user_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    date DATE NOT NULL,
                    total_chars INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    total_words INTEGER DEFAULT 0,
                    reactions_given INTEGER DEFAULT 0,
                    reactions_received INTEGER DEFAULT 0,
                    replies_received INTEGER DEFAULT 0,
                    replies_sent INTEGER DEFAULT 0,
                    mentions_received INTEGER DEFAULT 0,
                    media_sent INTEGER DEFAULT 0,
                    other_threads_posts INTEGER DEFAULT 0,
                    warnings INTEGER DEFAULT 0,
                    activity_score REAL DEFAULT 0,
                    pulses_mined REAL DEFAULT 0.0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, date)
                )
            ''')

            db.cursor.execute('''
                INSERT INTO user_stats
                SELECT id, user_id, date, total_chars, total_messages, total_words,
                       reactions_given, reactions_received, replies_received, replies_sent,
                       mentions_received, media_sent, other_threads_posts, warnings,
                       activity_score, CAST(pulses_mined AS REAL)
                FROM user_stats_backup
            ''')

            db.cursor.execute('DROP TABLE user_stats_backup')
            logging.info("✅ user_stats migrated")

        # Migrate chat_stats
        db.cursor.execute("PRAGMA table_info(chat_stats)")
        columns = {row['name']: row['type'] for row in db.cursor.fetchall()}

        if columns.get('total_pulses_mined') == 'INTEGER':
            logging.info("Migrating chat_stats.total_pulses_mined to REAL...")

            db.cursor.execute('CREATE TABLE chat_stats_backup AS SELECT * FROM chat_stats')
            db.cursor.execute('DROP TABLE chat_stats')

            db.cursor.execute('''
                CREATE TABLE chat_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    total_chars INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    total_messages_with_admins INTEGER DEFAULT 0,
                    total_messages_without_admins INTEGER DEFAULT 0,
                    total_words INTEGER DEFAULT 0,
                    total_reactions INTEGER DEFAULT 0,
                    total_replies INTEGER DEFAULT 0,
                    total_mentions INTEGER DEFAULT 0,
                    total_media INTEGER DEFAULT 0,
                    other_threads_posts INTEGER DEFAULT 0,
                    total_warnings INTEGER DEFAULT 0,
                    active_users INTEGER DEFAULT 0,
                    total_pulses_mined REAL DEFAULT 0.0,
                    avg_message_length REAL DEFAULT 0
                )
            ''')

            db.cursor.execute('''
                INSERT INTO chat_stats
                SELECT id, date, total_chars, total_messages, total_messages_with_admins,
                       total_messages_without_admins, total_words, total_reactions, total_replies,
                       total_mentions, total_media, other_threads_posts, total_warnings,
                       active_users, CAST(total_pulses_mined AS REAL), avg_message_length
                FROM chat_stats_backup
            ''')

            db.cursor.execute('DROP TABLE chat_stats_backup')
            logging.info("✅ chat_stats migrated")

        db.conn.commit()

    except Exception as e:
        logging.error(f"Error migrating stats tables: {e}")
        db.conn.rollback()


def add_telegram_message_id_to_messages(db):
    """Add telegram_message_id column to messages table for reaction tracking"""
    try:
        db.cursor.execute("PRAGMA table_info(messages)")
        columns = [row['name'] for row in db.cursor.fetchall()]

        if 'telegram_message_id' not in columns:
            logging.info("Adding telegram_message_id column to messages table...")

            db.cursor.execute('''
                ALTER TABLE messages ADD COLUMN telegram_message_id INTEGER
            ''')

            db.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_telegram_id 
                ON messages(chat_id, telegram_message_id)
            ''')

            db.conn.commit()
            logging.info("✅ telegram_message_id column added successfully")
        else:
            logging.info("telegram_message_id column already exists")

    except Exception as e:
        logging.error(f"Error adding telegram_message_id column: {e}")
        db.conn.rollback()


def migrate_monthly_gifts_tables(db):
    """Migrate old monthly_gifts table to new schema if needed"""
    try:
        db.cursor.execute("PRAGMA table_info(monthly_gifts)")
        columns = {row['name'] for row in db.cursor.fetchall()}

        if 'prize_type' not in columns and 'amount' in columns:
            logging.info("Migrating monthly_gifts to new schema...")
            db.cursor.execute('ALTER TABLE monthly_gifts RENAME TO monthly_gifts_old')
            db.cursor.execute('''
                CREATE TABLE monthly_gifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month TEXT NOT NULL,
                    prize_amount REAL DEFAULT 500,
                    prize_type TEXT DEFAULT 'pulses',
                    prize_description TEXT,
                    condition_type TEXT DEFAULT 'random',
                    condition_min_messages INTEGER DEFAULT 10,
                    condition_description TEXT,
                    winner_id INTEGER,
                    awarded_by INTEGER,
                    status TEXT DEFAULT 'active',
                    awarded_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    announced_in_chat BOOLEAN DEFAULT 0,
                    FOREIGN KEY (winner_id) REFERENCES users(user_id),
                    FOREIGN KEY (awarded_by) REFERENCES users(user_id)
                )
            ''')
            db.cursor.execute('''
                INSERT INTO monthly_gifts (month, prize_amount, winner_id, awarded_by, status, awarded_at)
                SELECT month, amount, winner_id, awarded_by, 'completed', awarded_at
                FROM monthly_gifts_old
            ''')
            db.cursor.execute('DROP TABLE monthly_gifts_old')
            db.conn.commit()
            logging.info("✅ monthly_gifts migrated to new schema")

        # Ensure participants table exists
        db.cursor.execute('''
            CREATE TABLE IF NOT EXISTS monthly_gift_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gift_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                messages_at_register INTEGER DEFAULT 0,
                is_qualified BOOLEAN DEFAULT 0,
                UNIQUE(gift_id, user_id),
                FOREIGN KEY (gift_id) REFERENCES monthly_gifts(id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        db.conn.commit()

    except Exception as e:
        logging.error(f"Error migrating monthly_gifts tables: {e}")
        db.conn.rollback()


def create_stat_events_log(db):
    """Создать таблицу дедупликации stat_events_log (идемпотентно)."""
    try:
        db.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stat_events_log (
                event_id  TEXT PRIMARY KEY,
                ts        INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER))
            )
        ''')
        db.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sel_ts ON stat_events_log(ts)
        ''')
        db.conn.commit()
        logging.info("✅ stat_events_log ready")
    except Exception as e:
        logging.error(f"create_stat_events_log error: {e}")


def add_removed_at_to_bot_chats(db):
    """V1.17.0h: добавить bot_chats.removed_at если колонки нет.

    Идемпотентно (PRAGMA-проверка), безопасно при флаге OFF — колонка
    аддитивна и не меняет поведения сама по себе.
    """
    try:
        db.cursor.execute("PRAGMA table_info(bot_chats)")
        cols = [row[1] for row in db.cursor.fetchall()]
        if not cols:
            logging.info("bot_chats table absent, skip removed_at migration")
            return
        if 'removed_at' not in cols:
            db.cursor.execute("ALTER TABLE bot_chats ADD COLUMN removed_at TIMESTAMP")
            db.conn.commit()
            logging.info("✅ bot_chats.removed_at column added")
        else:
            logging.info("bot_chats.removed_at already present")
    except Exception as e:
        logging.error(f"add_removed_at_to_bot_chats error: {e}")
        db.conn.rollback()
