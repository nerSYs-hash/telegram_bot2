#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
import logging

# ── Импорт модулей ──
from database.db_settings import (
    get_setting as _get_setting,
    set_setting as _set_setting,
    initialize_settings as _initialize_settings,
    is_feature_enabled as _is_feature_enabled,
    toggle_feature as _toggle_feature,
)
from database.db_users import (
    add_user as _add_user,
    get_user as _get_user,
    get_user_by_username as _get_user_by_username,
    update_user_balance as _update_user_balance,
    get_top_users_by_balance as _get_top_users_by_balance,
    get_top_daily_earners as _get_top_daily_earners,
    get_top_activists as _get_top_activists,
)
from database.db_transactions import (
    add_transaction as _add_transaction,
    get_bank_balance as _get_bank_balance,
    update_bank_balance as _update_bank_balance,
)
from database.db_stats import (
    update_user_activity as _update_user_activity,
    get_active_core_count as _get_active_core_count,
    register_topic as _register_topic,
    get_all_topics as _get_all_topics,
    update_topic_name as _update_topic_name,
    purge_unnamed_topics as _purge_unnamed_topics,
    get_joined_users_count as _get_joined_users_count,
    get_left_users_count as _get_left_users_count,
    get_user_dynamics_stats as _get_user_dynamics_stats,
)
from database.db_exchange import (
    set_exchange_rate as _set_exchange_rate,
    is_rate_manual as _is_rate_manual,
    get_rate_history as _get_rate_history,
    get_exchange_rate as _get_exchange_rate,
    get_rate_history_30d as _get_rate_history_30d,
    create_exchange_tables as _create_exchange_tables,
    save_top_snapshot as _save_top_snapshot,
    get_latest_top_snapshot as _get_latest_top_snapshot,
    get_previous_top_snapshot as _get_previous_top_snapshot,
    get_user_top_appearances as _get_user_top_appearances,
    get_all_top_appearances as _get_all_top_appearances,
    update_user_activity_hourly as _update_user_activity_hourly,
    save_top5_percent as _save_top5_percent,
    get_top5_percent as _get_top5_percent,
    cleanup_old_hourly_stats as _cleanup_old_hourly_stats,
)
from database.db_referrals import (
    create_referral_link as _create_referral_link,
    get_active_referral_link as _get_active_referral_link,
    get_or_create_referral_link as _get_or_create_referral_link,
    get_referrer_by_token as _get_referrer_by_token,
    use_referral_link as _use_referral_link,
    get_referral_link_stats as _get_referral_link_stats,
    record_user_join as _record_user_join,
    get_user_joins as _get_user_joins,
)
from database.db_scheduled import (
    add_scheduled_post as _add_scheduled_post,
    get_scheduled_post as _get_scheduled_post,
    update_scheduled_post as _update_scheduled_post,
    get_pending_scheduled_posts as _get_pending_scheduled_posts,
    mark_scheduled_post_published as _mark_scheduled_post_published,
    get_scheduled_posts_list as _get_scheduled_posts_list,
    delete_scheduled_post as _delete_scheduled_post,
)
from database.db_economy import (
    init_economy_tables as _init_economy_tables,
    get_econ as _get_econ,
    set_econ as _set_econ,
    toggle_econ as _toggle_econ,
    toggle_section as _toggle_econ_section,
    is_section_enabled as _is_econ_section_enabled,
    get_econ_categories as _get_econ_categories,
    get_econ_settings as _get_econ_settings,
    rollback_econ as _rollback_econ,
    cancel_pointwise as _cancel_pointwise,
    cancel_mass as _cancel_mass,
    get_cancellations as _get_economy_cancellations,
    get_economy_metrics as _get_economy_metrics,
)
from database.db_economy_history import (
    get_history_for_key as _get_econ_history,
    get_history_chart_data as _get_econ_chart_data,
)
from database.db_titles import (
    init_titles_tables as _init_titles_tables,
    seed_default_packages as _seed_title_packages,
    list_title_packages as _list_title_packages,
    get_title_package as _get_title_package,
    create_title_package as _create_title_package,
    update_title_package as _update_title_package,
    toggle_title_package as _toggle_title_package,
    create_title_request as _create_title_request,
    attach_owner_message as _attach_owner_message,
    get_title_request as _get_title_request,
    list_title_requests as _list_title_requests,
    count_title_requests_by_status as _count_title_requests_by_status,
    transition_title_request as _transition_title_request,
    expire_old_title_requests as _expire_old_title_requests,
)
from database.db_migrations import (
    migrate_to_decimal_balances as _migrate_to_decimal_balances,
    add_telegram_message_id_to_messages as _add_telegram_message_id_to_messages,
    migrate_monthly_gifts_tables as _migrate_monthly_gifts_tables,
    create_stat_events_log as _create_stat_events_log,
)
from database.db_stats import (
    register_stat_event as _register_stat_event,
    cleanup_stat_events_log as _cleanup_stat_events_log,
)


class Database:
    def __init__(self, db_path='database/bot_database.db'):
        """Initialize database connection"""
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Connect to SQLite database"""
        # timeout=30 — ждём блокировку до 30с вместо мгновенного "database is locked".
        # WAL — многопроцессный доступ (бот + api.py) без взаимных блокировок чтения/записи.
        self.conn = sqlite3.connect(
            self.db_path, check_same_thread=False, timeout=30.0
        )
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        try:
            self.cursor.execute('PRAGMA journal_mode=WAL')
            self.cursor.execute('PRAGMA busy_timeout=30000')
            self.cursor.execute('PRAGMA synchronous=NORMAL')
        except Exception:
            pass

    def create_tables(self):
        """Create all necessary tables"""

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                balance INTEGER DEFAULT 0,
                is_admin BOOLEAN DEFAULT 0,
                is_owner BOOLEAN DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                referrer_id INTEGER,
                referral_code TEXT UNIQUE,
                is_qualified BOOLEAN DEFAULT 0,
                frozen_balance INTEGER DEFAULT 0,
                freeze_until TIMESTAMP,
                is_left INTEGER DEFAULT 0,
                FOREIGN KEY (referrer_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER,
                to_user_id INTEGER,
                amount INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES users(user_id),
                FOREIGN KEY (to_user_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
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

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_stats (
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

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                html_report TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS lotteries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_price INTEGER NOT NULL,
                duration INTEGER NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT DEFAULT 'active',
                winner_id INTEGER,
                total_pool INTEGER DEFAULT 0,
                message_id INTEGER,
                FOREIGN KEY (winner_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS lottery_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lottery_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                tickets_count INTEGER DEFAULT 1,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lottery_id) REFERENCES lotteries(id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                donated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS referral_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                used_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (used_by) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_joins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                join_method TEXT NOT NULL DEFAULT 'unknown',
                referrer_id INTEGER,
                referral_token TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (referrer_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS referral_seasons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS referral_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                season_id INTEGER NOT NULL,
                referrals_count INTEGER DEFAULT 0,
                qualified_referrals INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (season_id) REFERENCES referral_seasons(id),
                UNIQUE(user_id, season_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS titles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title_name TEXT NOT NULL,
                title_type TEXT NOT NULL,
                emoji TEXT,
                multiplier REAL DEFAULT 1.0,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_permanent BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS hall_of_fame (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                season_id INTEGER NOT NULL,
                place INTEGER NOT NULL,
                medal_name TEXT NOT NULL,
                awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (season_id) REFERENCES referral_seasons(id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS exit_interviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reason_category TEXT,
                reason_text TEXT,
                left_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS marketplace_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_type TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                content TEXT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                expires_at REAL,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                challenge_type TEXT NOT NULL,
                reward INTEGER NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT DEFAULT 'active',
                winner_id INTEGER,
                FOREIGN KEY (winner_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_text TEXT,
                message_type TEXT,
                message_thread_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                thread_id INTEGER,
                thread_name TEXT,
                is_main_thread BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_messages INTEGER DEFAULT 0,
                UNIQUE(chat_id, thread_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_id INTEGER NOT NULL,
                text TEXT,
                photo_file_id TEXT,
                target_chat_id INTEGER NOT NULL,
                thread_id INTEGER,
                publish_at TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                FOREIGN KEY (author_id) REFERENCES users(user_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS shipper_phrases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                text TEXT NOT NULL
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS shipper_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER NOT NULL,
                user2_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                triggered INTEGER DEFAULT 0,
                triggered_at TIMESTAMP
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS shipper_resonance_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                trigger_type TEXT NOT NULL,
                multiplier REAL DEFAULT 2.0,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        ''')
        
        # Combo claims (daily quests tracking)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS combo_claims (
                user_id    INTEGER NOT NULL,
                combo_name TEXT    NOT NULL,
                reward     REAL    DEFAULT 0,
                claimed_at TEXT    NOT NULL,
                PRIMARY KEY (user_id, combo_name)
            )
        ''')
        
        # Sprint claims (timed quests tracking)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sprint_claims (
                user_id     INTEGER NOT NULL,
                sprint_name TEXT    NOT NULL,
                window_key  TEXT    NOT NULL,
                reward      REAL    DEFAULT 0,
                claimed_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, sprint_name, window_key)
            )
        ''')

        # Defibrillator buff columns in users table
        for col, col_def in [
            ('mining_buff_multiplier', 'REAL DEFAULT 1.0'),
            ('mining_buff_expires_at', 'TIMESTAMP'),
        ]:
            try:
                self.cursor.execute(f'ALTER TABLE users ADD COLUMN {col} {col_def}')
            except Exception:
                pass  # column already exists

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS monthly_gifts (
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

        self.cursor.execute('''
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

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS exchange_rate_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rate REAL NOT NULL,
                ai_value REAL DEFAULT 0,
                total_members INTEGER DEFAULT 0,
                avg_active REAL DEFAULT 0,
                denominator REAL DEFAULT 0,
                is_manual BOOLEAN DEFAULT 0,
                changed_by INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ── Таблица для Баг-трекера ──
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bug_cards (
                original_msg_id INTEGER PRIMARY KEY,
                author_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                topic TEXT,
                priority TEXT,
                original_text TEXT,
                is_photo BOOLEAN DEFAULT 0,
                media_file_id TEXT,
                card_msg_id INTEGER,
                comments_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Создаём таблицу top_activists_history + индексы
        _create_exchange_tables(self)

        self.conn.commit()

        # Initialize BBS tables (dating + other posts)
        from handlers.BBS.database_bbs import init_bbs_tables
        init_bbs_tables(self)

        # Run migrations
        _migrate_to_decimal_balances(self)
        _add_telegram_message_id_to_messages(self)
        _migrate_monthly_gifts_tables(self)
        _create_stat_events_log(self)

        # Migration: add is_left column to users
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN is_left INTEGER DEFAULT 0")
            self.conn.commit()
        except Exception:
            pass  # Column already exists

        self.seed_shipper_phrases_if_empty()

        # Initialize economy tables
        _init_economy_tables(self)

        # Initialize titles tables (V1.16.0)
        _init_titles_tables(self)
        _seed_title_packages(self)

        # Migration V1.16.0: добавить expires_at в marketplace_services
        try:
            self.cursor.execute(
                "ALTER TABLE marketplace_services ADD COLUMN expires_at REAL"
            )
            self.conn.commit()
        except Exception:
            pass  # Колонка уже существует

        # Migration V1.16.14a: пресс-релизы (расширение scheduled_posts + новые таблицы)
        try:
            from database.db_press_release import init_press_release_tables
            init_press_release_tables(self)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"init_press_release_tables: {e}")

    # ── Economy ──
    # TODO(multi-tenancy): workspace_id=1 placeholder. Когда WorkspaceContext
    # будет проброшен в handlers (Task 15), wrapper'ы примут workspace_id явно.
    # Сейчас Pulse Москва — единственный workspace, поэтому хардкод 1 безопасен.
    _DEFAULT_WS_ID = 1

    def get_econ(self, key, default=None, value_type='float'):
        return _get_econ(self, self._DEFAULT_WS_ID, key, default, value_type)

    def set_econ(self, key, value, comment, changed_by, changed_by_role):
        return _set_econ(self, self._DEFAULT_WS_ID, key, value, comment, changed_by, changed_by_role)

    def toggle_econ(self, key, comment, changed_by, changed_by_role):
        return _toggle_econ(self, self._DEFAULT_WS_ID, key, comment, changed_by, changed_by_role)

    def toggle_econ_section(self, category, comment, changed_by, changed_by_role):
        return _toggle_econ_section(self, self._DEFAULT_WS_ID, category, comment, changed_by, changed_by_role)

    def is_econ_section_enabled(self, category):
        return _is_econ_section_enabled(self, self._DEFAULT_WS_ID, category)

    def get_econ_categories(self):
        return _get_econ_categories(self, self._DEFAULT_WS_ID)

    def get_econ_settings(self, category=None, subcategory=None):
        return _get_econ_settings(self, self._DEFAULT_WS_ID, category=category, subcategory=subcategory)

    def rollback_econ(self, history_id, comment, changed_by, changed_by_role):
        return _rollback_econ(self, self._DEFAULT_WS_ID, history_id, comment, changed_by, changed_by_role)

    def get_econ_history(self, key, limit=20, offset=0):
        return _get_econ_history(self, self._DEFAULT_WS_ID, key, limit=limit, offset=offset)

    def get_econ_chart_data(self, key):
        return _get_econ_chart_data(self, self._DEFAULT_WS_ID, key)

    def cancel_pointwise(self, tx_id, mode, comment, executed_by, executed_by_role):
        return _cancel_pointwise(self, self._DEFAULT_WS_ID, tx_id, mode, comment, executed_by, executed_by_role)

    def cancel_mass(self, filter_dict, mode, comment, executed_by, executed_by_role):
        return _cancel_mass(self, self._DEFAULT_WS_ID, filter_dict, mode, comment, executed_by, executed_by_role)

    def get_economy_cancellations(self, limit=50, offset=0):
        return _get_economy_cancellations(self, self._DEFAULT_WS_ID, limit=limit, offset=offset)

    def get_economy_metrics(self):
        return _get_economy_metrics(self, self._DEFAULT_WS_ID)

    # ── Titles (V1.16.0) ──
    def list_title_packages(self, only_enabled=False):
        return _list_title_packages(self, only_enabled=only_enabled)

    def get_title_package(self, pkg_id):
        return _get_title_package(self, pkg_id)

    def create_title_package(self, label, duration_days, price_pulses, price_rub):
        return _create_title_package(self, label, duration_days, price_pulses, price_rub)

    def update_title_package(self, pkg_id, **fields):
        return _update_title_package(self, pkg_id, **fields)

    def toggle_title_package(self, pkg_id):
        return _toggle_title_package(self, pkg_id)

    def create_title_request(self, user_id, package_id, title_text, price_rub, duration_days):
        return _create_title_request(self, user_id, package_id, title_text, price_rub, duration_days)

    def attach_title_request_message(self, request_id, owner_chat_id, owner_msg_id):
        return _attach_owner_message(self, request_id, owner_chat_id, owner_msg_id)

    def get_title_request(self, request_id):
        return _get_title_request(self, request_id)

    def list_title_requests(self, status=None, limit=50, offset=0):
        return _list_title_requests(self, status=status, limit=limit, offset=offset)

    def count_title_requests_pending(self):
        return _count_title_requests_by_status(self, 'pending')

    def transition_title_request(self, request_id, new_status, decided_by=None,
                                 reject_reason=None, only_from='pending'):
        return _transition_title_request(self, request_id, new_status,
                                         decided_by=decided_by,
                                         reject_reason=reject_reason,
                                         only_from=only_from)

    def expire_old_title_requests(self, ttl_hours):
        return _expire_old_title_requests(self, ttl_hours)

    # ── Settings ──
    def get_setting(self, key, default=None):
        return _get_setting(self, key, default)

    def set_setting(self, key, value):
        _set_setting(self, key, value)

    def initialize_settings(self, initial_bank_balance=1000000, initial_difficulty_k=5.0):
        _initialize_settings(self, initial_bank_balance, initial_difficulty_k)

    def is_feature_enabled(self, feature_name):
        return _is_feature_enabled(self, feature_name)

    def toggle_feature(self, feature_name):
        return _toggle_feature(self, feature_name)

    # ── Users ──
    def add_user(self, user_id, username=None, first_name=None, last_name=None,
                 is_admin=False, is_owner=False):
        _add_user(self, user_id, username, first_name, last_name, is_admin, is_owner)

    def get_user(self, user_id):
        return _get_user(self, user_id)

    def get_user_by_username(self, username):
        return _get_user_by_username(self, username)

    def update_user_balance(self, user_id, amount, operation='add'):
        return _update_user_balance(self, user_id, amount, operation)

    def get_top_users_by_balance(self, limit=5, exclude_admins=True):
        return _get_top_users_by_balance(self, limit, exclude_admins)

    def get_top_daily_earners(self, date, limit=5):
        return _get_top_daily_earners(self, date, limit)

    def get_top_activists(self, date, limit=5):
        return _get_top_activists(self, date, limit)

    # ── Transactions & Bank ──
    def add_transaction(self, from_user_id, to_user_id, amount, transaction_type, description=None):
        return _add_transaction(self, from_user_id, to_user_id, amount, transaction_type, description)

    def get_bank_balance(self):
        return _get_bank_balance(self)

    def update_bank_balance(self, amount, operation='subtract'):
        return _update_bank_balance(self, amount, operation)

    # ── Stats ──
    def update_user_activity(self, user_id, date, event_id: str = None, **kwargs):
        _update_user_activity(self, user_id, date, event_id=event_id, **kwargs)

    def cleanup_stat_events_log(self, older_than_days: int = 3):
        _cleanup_stat_events_log(self, older_than_days)

    def get_active_core_count(self, date):
        return _get_active_core_count(self, date)

    def register_topic(self, chat_id, thread_id, thread_name=None):
        _register_topic(self, chat_id, thread_id, thread_name)

    def get_all_topics(self, chat_id):
        return _get_all_topics(self, chat_id)

    def update_topic_name(self, chat_id, thread_id, thread_name):
        _update_topic_name(self, chat_id, thread_id, thread_name)

    def purge_unnamed_topics(self, chat_id):
        return _purge_unnamed_topics(self, chat_id)

    def get_joined_users_count(self, start_date, end_date):
        return _get_joined_users_count(self, start_date, end_date)

    def get_left_users_count(self, start_date, end_date):
        return _get_left_users_count(self, start_date, end_date)

    def get_user_dynamics_stats(self, start_date, end_date):
        return _get_user_dynamics_stats(self, start_date, end_date)

    # ── Exchange Rate ──
    def set_exchange_rate(self, rate, changed_by=None, is_manual=False,
                          ai_value=0, total_members=0, avg_active=0, denominator=0):
        _set_exchange_rate(self, rate, changed_by, is_manual, ai_value, total_members, avg_active, denominator)

    def is_rate_manual(self):
        return _is_rate_manual(self)

    def get_rate_history(self, limit=48):
        return _get_rate_history(self, limit)

    def get_exchange_rate(self):
        return _get_exchange_rate(self)

    def get_rate_history_30d(self):
        return _get_rate_history_30d(self)

    # ── Top Activists History ──
    def save_top_snapshot(self, date, time_slot, user_id, rank, activity_index):
        _save_top_snapshot(self, date, time_slot, user_id, rank, activity_index)

    def get_latest_top_snapshot(self):
        return _get_latest_top_snapshot(self)

    def get_previous_top_snapshot(self):
        return _get_previous_top_snapshot(self)

    def get_user_top_appearances(self, user_id, days=30):
        return _get_user_top_appearances(self, user_id, days)

    def get_all_top_appearances(self, days=30):
        return _get_all_top_appearances(self, days)

    # ── Hourly Stats & % Activity ──
    def update_user_activity_hourly(self, user_id, date, hour, **kwargs):
        _update_user_activity_hourly(self, user_id, date, hour, **kwargs)

    def save_top5_percent(self, entries, window_start, window_end):
        _save_top5_percent(self, entries, window_start, window_end)

    def get_top5_percent(self):
        return _get_top5_percent(self)

    def cleanup_old_hourly_stats(self, days_to_keep=2):
        _cleanup_old_hourly_stats(self, days_to_keep)

    # ── Referrals ──
    def create_referral_link(self, user_id):
        return _create_referral_link(self, user_id)

    def get_active_referral_link(self, user_id):
        return _get_active_referral_link(self, user_id)

    def get_or_create_referral_link(self, user_id):
        return _get_or_create_referral_link(self, user_id)

    def get_referrer_by_token(self, token):
        return _get_referrer_by_token(self, token)

    def use_referral_link(self, token, used_by_user_id):
        return _use_referral_link(self, token, used_by_user_id)

    def get_referral_link_stats(self, user_id):
        return _get_referral_link_stats(self, user_id)

    def record_user_join(self, user_id, username, first_name, join_method,
                         referrer_id=None, referral_token=None):
        _record_user_join(self, user_id, username, first_name, join_method, referrer_id, referral_token)

    def get_user_joins(self, start_date=None, end_date=None):
        return _get_user_joins(self, start_date, end_date)

    # ── Scheduled Posts ──
    def add_scheduled_post(self, author_id, text, photo_file_id, target_chat_id, thread_id, publish_at):
        return _add_scheduled_post(self, author_id, text, photo_file_id, target_chat_id, thread_id, publish_at)

    def get_scheduled_post(self, post_id):
        return _get_scheduled_post(self, post_id)

    def update_scheduled_post(self, post_id, **kwargs):
        return _update_scheduled_post(self, post_id, **kwargs)

    def get_pending_scheduled_posts(self, before_time):
        return _get_pending_scheduled_posts(self, before_time)

    def mark_scheduled_post_published(self, post_id):
        _mark_scheduled_post_published(self, post_id)

    def get_scheduled_posts_list(self, status='pending'):
        return _get_scheduled_posts_list(self, status)

    def delete_scheduled_post(self, post_id):
        return _delete_scheduled_post(self, post_id)

    # ── Shipper Roulette ──
    def seed_shipper_phrases_if_empty(self):
        """Заполняет стартовые шаблоны шиппера, если таблица пуста."""
        try:
            self.cursor.execute('SELECT COUNT(*) AS cnt FROM shipper_phrases')
            row = self.cursor.fetchone()
            count = int(row['cnt']) if row and row['cnt'] is not None else 0
            if count > 0:
                return

            seed_rows = [
                ('hot18', '{user1} и {user2} были замечены в одной кабинке туалета клуба...'),
                ('hot18', '{user1} обещал показать {user2} свою "коллекцию игрушек" на выходных 🔞'),
                ('hot18', '{user1} теперь официально папик для {user2} 💸'),
                ('hot18', '{user1} делает {user2} такой массаж, после которого не ходят на работу 💆‍♂️'),
                ('hot18', '{user1} и {user2} сегодня тестируют наручники. Главное — не потерять ключи ⛓'),
                ('hot18', '{user1} стонет имя {user2} во сне. Совпадение? Не думаем! 💦'),
                ('hot18', '{user1} оставил засос на шее {user2}. Придется носить водолазку 🧣'),
                ('hot18', 'Кажется, {user1} и {user2} вчера переборщили с ролевыми играми 🩺'),
                ('hot18', '{user1} просит {user2} скинуть нюдсы. Чат требует того же! 📸'),
                ('hot18', '{user1} и {user2} заперлись в спальне. Просьба не беспокоить до утра 🚷'),
                ('hot18', '{user1} использует {user2} вместо подушки для обнимашек... и не только 🛏'),
                ('hot18', 'У {user1} фетиш на {user2}. Это уже не скрыть! 🥵'),
                ('hot18', '{user1} и {user2} еблись в сенях чата, пока админы спали! 😈'),
                ('hot18', '{user1} отшлепал {user2} за плохое поведение. И ему понравилось! 👏'),
                ('hot18', '{user1} делает {user2} минет. Приятного аппетита! 🍌'),
                ('funny', '{user1} и {user2} делят один аккаунт на сайте знакомств 🤡'),
                ('funny', '{user1} задолжал {user2} ящик пива за проигранный спор 🍻'),
                ('funny', '{user1} и {user2} — спонсоры локального дурдома в этом чате 🏥'),
                ('funny', '{user1} пытался соблазнить {user2}, но забыл выключить микрофон 🎤'),
                ('funny', '{user1} и {user2} поругались из-за того, кто сегодня снизу 🤼‍♂️'),
                ('funny', 'Кажется, {user1} тайно ворует мемы у {user2} 🥷'),
                ('funny', '{user1} и {user2} идут сдавать анализы вместе. Настоящая мужская дружба! 🩸'),
                ('funny', '{user1} записан в телефоне у {user2} как "Не брать трубку" 📵'),
                ('funny', '{user1} и {user2} собирают деньги на совместный поход к психотерапевту 🛋'),
                ('funny', '{user1} съел шаурму, которую {user2} оставил в холодильнике 🌯'),
                ('funny', '{user1} и {user2} опять спорят, кто из них красивее. Чат, рассудите! 🪞'),
                ('funny', '{user1} учит {user2} правильно флиртовать. Пока безуспешно 🤦‍♂️'),
                ('funny', '{user1} и {user2} — как Биба и Боба нашего чата 🤪'),
                ('funny', '{user1} кинул {user2} в ЧС, но мы-то знаем, что это любовь 💔'),
                ('funny', '{user1} и {user2} планируют захват админки. Готовьтесь! 🏴‍☠️'),
                ('romantic', '{user1} + {user2} = любовь и химия, которую не скрыть ❤️'),
                ('romantic', '{user1} тайно улыбается, когда видит сообщения от {user2} 😊'),
                ('romantic', '{user1} и {user2} могли бы стать отличной парой. Подумайте об этом! 👨‍❤️‍👨'),
                ('romantic', '{user1} хочет пригласить {user2} на кофе, но стесняется ☕️'),
                ('romantic', '{user1} и {user2} звучат в унисон. Идеальный мэтч! 🎵'),
                ('romantic', '{user1} готов отдать {user2} свой последний кусочек пиццы 🍕'),
                ('romantic', '{user1} и {user2} сегодня на одной волне ✨'),
                ('romantic', '{user1} хочет обнять {user2}. Но это не точно! 🫂'),
                ('romantic', '{user1} и {user2} — самое милое, что случалось с этим чатом за сегодня 🥺'),
                ('romantic', '{user1} смотрит на аватарку {user2} чаще, чем на себя в зеркало 🖼'),
                ('romantic', '{user1} и {user2} просто созданы друг для друга 🧩'),
                ('romantic', '{user1} готов слушать голосовые от {user2} часами 🎧'),
                ('romantic', '{user1} и {user2} — наша новая любимая пара! Горько! 🥂'),
                ('romantic', '{user1} греет ручки {user2} в этот холодный день 🧤'),
                ('romantic', '{user1} и {user2} сегодня делят один плед на двоих 🛋'),
            ]
            self.cursor.executemany(
                'INSERT INTO shipper_phrases (category, text) VALUES (?, ?)',
                seed_rows,
            )
            self.conn.commit()
        except Exception as e:
            logging.error(f"seed_shipper_phrases_if_empty error: {e}")

    def get_shipper_phrases(self):
        try:
            self.cursor.execute('SELECT id, category, text FROM shipper_phrases ORDER BY id DESC')
            return self.cursor.fetchall()
        except Exception as e:
            logging.error(f"get_shipper_phrases error: {e}")
            return []

    def get_shipper_phrases_by_category(self, category):
        try:
            self.cursor.execute(
                'SELECT id, category, text FROM shipper_phrases WHERE category = ? ORDER BY id DESC',
                (category,),
            )
            return self.cursor.fetchall()
        except Exception as e:
            logging.error(f"get_shipper_phrases_by_category error: {e}")
            return []

    def add_shipper_phrase(self, category, text):
        try:
            self.cursor.execute(
                'INSERT INTO shipper_phrases (category, text) VALUES (?, ?)',
                (category, text),
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            logging.error(f"add_shipper_phrase error: {e}")
            return None

    def delete_shipper_phrase(self, phrase_id):
        try:
            self.cursor.execute('DELETE FROM shipper_phrases WHERE id = ?', (phrase_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logging.error(f"delete_shipper_phrase error: {e}")
            return False

    def get_random_shipper_phrase(self):
        try:
            self.cursor.execute('SELECT id, category, text FROM shipper_phrases ORDER BY RANDOM() LIMIT 1')
            return self.cursor.fetchone()
        except Exception as e:
            logging.error(f"get_random_shipper_phrase error: {e}")
            return None

    def create_shipper_match(self, user1_id, user2_id, chat_id, message_id, expires_at):
        try:
            self.cursor.execute(
                '''
                INSERT INTO shipper_matches (user1_id, user2_id, chat_id, message_id, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (user1_id, user2_id, chat_id, message_id, expires_at),
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            logging.error(f"create_shipper_match error: {e}")
            return None

    def get_active_shipper_match_for_user(self, chat_id, user_id):
        try:
            self.cursor.execute(
                '''
                SELECT id, user1_id, user2_id, message_id, expires_at, triggered
                FROM shipper_matches
                WHERE chat_id = ?
                  AND triggered = 0
                  AND expires_at > CURRENT_TIMESTAMP
                  AND (user1_id = ? OR user2_id = ?)
                ORDER BY id DESC
                LIMIT 1
                ''',
                (chat_id, user_id, user_id),
            )
            return self.cursor.fetchone()
        except Exception as e:
            logging.error(f"get_active_shipper_match_for_user error: {e}")
            return None

    def mark_shipper_match_triggered(self, match_id):
        try:
            self.cursor.execute(
                'UPDATE shipper_matches SET triggered = 1, triggered_at = CURRENT_TIMESTAMP WHERE id = ?',
                (match_id,),
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logging.error(f"mark_shipper_match_triggered error: {e}")
            return False

    def add_shipper_resonance_stat(self, user_id, match_id, trigger_type, expires_at, multiplier=2.0):
        try:
            self.cursor.execute(
                '''
                INSERT INTO shipper_resonance_stats (user_id, match_id, trigger_type, multiplier, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (user_id, match_id, trigger_type, multiplier, expires_at),
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            logging.error(f"add_shipper_resonance_stat error: {e}")
            return None

    # ── Close ──
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


# Initialize database
if __name__ == '__main__':
    db = Database()
    db.initialize_settings()
    print("Database initialized successfully!")
