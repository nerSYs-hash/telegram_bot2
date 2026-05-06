#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пресс-Релизы (V1.16.14a) — единый модуль БД.

Содержит:
  • Миграции: расширение scheduled_posts + новые таблицы
  • bot_chats / bot_chat_topics — каталог чатов где есть бот
  • press_release_templates — шаблоны
  • press_release_versions — история версий
  • press_release_targets — multi-target (один пост → много чатов)
  • branding_settings — кастомная подпись
  • press_release_published — отслеживание опубликованных сообщений (для удаления)

Статусы scheduled_posts: draft / scheduled / published / failed / cancelled
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
# СХЕМА И МИГРАЦИИ
# ════════════════════════════════════════════════════════════════════

def init_press_release_tables(db) -> None:
    """Создаёт/мигрирует все таблицы пресс-релизов. Идемпотентно."""
    cur = db.cursor

    # ── Расширения scheduled_posts ──
    new_columns = {
        'title':                 "TEXT",
        'signature':             "TEXT",
        'bold_header':           "INTEGER DEFAULT 1",
        'add_signature':         "INTEGER DEFAULT 1",
        'inline_keyboard':       "TEXT",          # JSON: [[{text,type,value,emoji}],...]
        'settings_json':         "TEXT",          # JSON: {pin,disable_preview,disable_notify,content_protection,delete_after_publish:{enabled,value,unit}}
        'cancelled_at':          "TIMESTAMP",
        'cancelled_by':          "INTEGER",
        'failed_reason':         "TEXT",
        'updated_at':            "TIMESTAMP",
        'version':               "INTEGER DEFAULT 1",
        'pre_publish_reminder':  "INTEGER DEFAULT 0",   # 0=off, 5/15/60 минут
        'template_id':           "INTEGER",       # из какого шаблона создан
    }
    cur.execute("PRAGMA table_info(scheduled_posts)")
    existing = {row[1] for row in cur.fetchall()}
    for col, ddl in new_columns.items():
        if col not in existing:
            try:
                cur.execute(f"ALTER TABLE scheduled_posts ADD COLUMN {col} {ddl}")
            except Exception as e:
                logger.warning(f"add column scheduled_posts.{col}: {e}")

    # ── Каталог чатов где есть бот ──
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bot_chats (
            chat_id      INTEGER PRIMARY KEY,
            type         TEXT NOT NULL,            -- group / supergroup / channel / private
            title        TEXT,
            username     TEXT,
            is_forum     INTEGER DEFAULT 0,
            added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            removed_at   TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Подхваченные топики форумов ──
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bot_chat_topics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     INTEGER NOT NULL,
            thread_id   INTEGER NOT NULL,
            name        TEXT,
            source      TEXT DEFAULT 'auto',       -- auto / manual
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, thread_id)
        )
    ''')

    # ── Multi-target: один пост → много чатов/топиков ──
    cur.execute('''
        CREATE TABLE IF NOT EXISTS press_release_targets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id         INTEGER NOT NULL,
            chat_id         INTEGER NOT NULL,
            thread_id       INTEGER,
            published_at    TIMESTAMP,
            message_ids     TEXT,                 -- JSON list: [123, 124, ...]
            error           TEXT,
            FOREIGN KEY (post_id) REFERENCES scheduled_posts(id) ON DELETE CASCADE
        )
    ''')

    # ── Шаблоны ──
    cur.execute('''
        CREATE TABLE IF NOT EXISTS press_release_templates (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT NOT NULL,
            text              TEXT,
            photo_file_id     TEXT,
            inline_keyboard   TEXT,
            settings_json     TEXT,
            bold_header       INTEGER DEFAULT 1,
            add_signature     INTEGER DEFAULT 1,
            signature         TEXT,
            created_by        INTEGER,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── История версий ──
    cur.execute('''
        CREATE TABLE IF NOT EXISTS press_release_versions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id      INTEGER NOT NULL,
            version      INTEGER NOT NULL,
            snapshot     TEXT NOT NULL,            -- JSON всего поста
            saved_by     INTEGER,
            saved_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES scheduled_posts(id) ON DELETE CASCADE
        )
    ''')

    # ── Брендинг (key/value) ──
    cur.execute('''
        CREATE TABLE IF NOT EXISTS branding_settings (
            key         TEXT PRIMARY KEY,
            value       TEXT,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by  INTEGER
        )
    ''')

    db.conn.commit()
    logger.info("press_release tables ready")


# ════════════════════════════════════════════════════════════════════
# bot_chats
# ════════════════════════════════════════════════════════════════════

def upsert_bot_chat(db, chat_id: int, chat_type: str, title: str = None,
                    username: str = None, is_forum: bool = False) -> None:
    """Добавить/обновить запись о чате где есть бот."""
    db.cursor.execute('''
        INSERT INTO bot_chats (chat_id, type, title, username, is_forum, added_at, last_seen_at, removed_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL)
        ON CONFLICT(chat_id) DO UPDATE SET
            type         = excluded.type,
            title        = excluded.title,
            username     = excluded.username,
            is_forum     = excluded.is_forum,
            last_seen_at = CURRENT_TIMESTAMP,
            removed_at   = NULL
    ''', (chat_id, chat_type, title, username, 1 if is_forum else 0))
    db.conn.commit()


def mark_bot_chat_removed(db, chat_id: int) -> None:
    """Бот покинул чат — пометить removed_at."""
    db.cursor.execute(
        "UPDATE bot_chats SET removed_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
        (chat_id,)
    )
    db.conn.commit()


def get_bot_chats(db, include_removed: bool = False) -> list:
    """Список чатов где сейчас есть бот (или все, если include_removed)."""
    where = "" if include_removed else "WHERE removed_at IS NULL"
    db.cursor.execute(f'''
        SELECT chat_id, type, title, username, is_forum, added_at, removed_at
        FROM bot_chats {where}
        ORDER BY title COLLATE NOCASE
    ''')
    return [dict(r) for r in db.cursor.fetchall()]


# ════════════════════════════════════════════════════════════════════
# bot_chat_topics
# ════════════════════════════════════════════════════════════════════

def upsert_bot_chat_topic(db, chat_id: int, thread_id: int,
                          name: str = None, source: str = 'auto') -> None:
    """Добавить/обновить топик форума."""
    db.cursor.execute('''
        INSERT INTO bot_chat_topics (chat_id, thread_id, name, source)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chat_id, thread_id) DO UPDATE SET
            name       = COALESCE(excluded.name, name),
            updated_at = CURRENT_TIMESTAMP
    ''', (chat_id, thread_id, name, source))
    db.conn.commit()


def get_bot_chat_topics(db, chat_id: int) -> list:
    """Список топиков для конкретного чата."""
    db.cursor.execute('''
        SELECT id, chat_id, thread_id, name, source, created_at
        FROM bot_chat_topics
        WHERE chat_id = ?
        ORDER BY thread_id
    ''', (chat_id,))
    return [dict(r) for r in db.cursor.fetchall()]


def delete_bot_chat_topic(db, chat_id: int, thread_id: int) -> bool:
    db.cursor.execute(
        "DELETE FROM bot_chat_topics WHERE chat_id = ? AND thread_id = ?",
        (chat_id, thread_id)
    )
    db.conn.commit()
    return db.cursor.rowcount > 0


# ════════════════════════════════════════════════════════════════════
# press_release CRUD (расширенный scheduled_posts)
# ════════════════════════════════════════════════════════════════════

ALLOWED_FIELDS = frozenset({
    'title', 'text', 'photo_file_id', 'publish_at', 'status',
    'signature', 'bold_header', 'add_signature', 'inline_keyboard',
    'settings_json', 'pre_publish_reminder', 'template_id',
    'target_chat_id', 'thread_id',
})


def create_press_release(db, author_id: int, **fields) -> int:
    """Создать пресс-релиз. По умолчанию status=draft, publish_at=NULL.
       Multi-target пишется отдельно через add_target()."""
    fields.setdefault('status', 'draft')
    fields.setdefault('bold_header', 1)
    fields.setdefault('add_signature', 1)
    # publish_at — обязателен в схеме, кладём заглушку для черновиков
    if not fields.get('publish_at'):
        fields['publish_at'] = '1970-01-01 00:00:00'
    # target_chat_id — обязателен в схеме (NOT NULL); для черновиков 0
    fields.setdefault('target_chat_id', 0)

    cols = ['author_id'] + [k for k in fields if k in ALLOWED_FIELDS]
    vals = [author_id] + [fields[k] for k in cols[1:]]
    placeholders = ','.join('?' * len(cols))
    db.cursor.execute(
        f"INSERT INTO scheduled_posts ({','.join(cols)}, updated_at) VALUES ({placeholders}, CURRENT_TIMESTAMP)",
        vals
    )
    db.conn.commit()
    return db.cursor.lastrowid


def update_press_release(db, post_id: int, **fields) -> bool:
    """Обновить поля пресс-релиза. Только поля из ALLOWED_FIELDS."""
    updates = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}
    if not updates:
        return False
    set_clause = ', '.join(f'{k} = ?' for k in updates)
    vals = list(updates.values()) + [post_id]
    db.cursor.execute(
        f"UPDATE scheduled_posts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        vals
    )
    db.conn.commit()
    return db.cursor.rowcount > 0


def get_press_release(db, post_id: int) -> Optional[dict]:
    db.cursor.execute('''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
        WHERE sp.id = ?
    ''', (post_id,))
    row = db.cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d['targets'] = get_targets(db, post_id)
    return d


def list_press_releases(db, status: str = None, limit: int = 200) -> list:
    """Список постов. status: draft/scheduled/published/failed/cancelled (или None=все)."""
    sql = '''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
    '''
    params = []
    if status:
        sql += " WHERE sp.status = ?"
        params.append(status)
    sql += " ORDER BY COALESCE(sp.updated_at, sp.created_at) DESC LIMIT ?"
    params.append(limit)
    db.cursor.execute(sql, params)
    return [dict(r) for r in db.cursor.fetchall()]


def delete_press_release(db, post_id: int) -> bool:
    """Полное удаление поста (вместе с таргетами и версиями — каскадом)."""
    db.cursor.execute("DELETE FROM scheduled_posts WHERE id = ?", (post_id,))
    db.conn.commit()
    return db.cursor.rowcount > 0


def cancel_press_release(db, post_id: int, by_user_id: int) -> bool:
    db.cursor.execute('''
        UPDATE scheduled_posts
        SET status = 'cancelled',
            cancelled_at = CURRENT_TIMESTAMP,
            cancelled_by = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status IN ('scheduled','draft')
    ''', (by_user_id, post_id))
    db.conn.commit()
    return db.cursor.rowcount > 0


def restore_press_release(db, post_id: int) -> bool:
    """cancelled/failed → draft (возврат на редактирование)."""
    db.cursor.execute('''
        UPDATE scheduled_posts
        SET status = 'draft',
            cancelled_at = NULL, cancelled_by = NULL, failed_reason = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status IN ('cancelled','failed')
    ''', (post_id,))
    db.conn.commit()
    return db.cursor.rowcount > 0


def mark_failed(db, post_id: int, reason: str) -> None:
    db.cursor.execute('''
        UPDATE scheduled_posts
        SET status = 'failed', failed_reason = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (reason, post_id))
    db.conn.commit()


def mark_published(db, post_id: int) -> None:
    db.cursor.execute('''
        UPDATE scheduled_posts
        SET status = 'published', published_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (post_id,))
    db.conn.commit()


def clone_press_release(db, post_id: int, new_author_id: int) -> Optional[int]:
    """Дублировать пост → возвращает id копии (status=draft)."""
    src = get_press_release(db, post_id)
    if not src:
        return None
    fields = {k: src.get(k) for k in (
        'title', 'text', 'photo_file_id', 'signature', 'bold_header',
        'add_signature', 'inline_keyboard', 'settings_json',
        'pre_publish_reminder', 'template_id', 'target_chat_id', 'thread_id'
    )}
    fields['title'] = (fields.get('title') or '') + ' (копия)'
    fields['status'] = 'draft'
    new_id = create_press_release(db, new_author_id, **fields)
    # Копируем таргеты
    for t in src.get('targets', []):
        add_target(db, new_id, t['chat_id'], t.get('thread_id'))
    return new_id


def get_pending_press_releases(db, before_time: str) -> list:
    """Возвращает посты status=scheduled с publish_at <= before_time."""
    db.cursor.execute('''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
        WHERE sp.status = 'scheduled' AND sp.publish_at <= ?
        ORDER BY sp.publish_at ASC
    ''', (before_time,))
    return [dict(r) for r in db.cursor.fetchall()]


def count_recent_press_releases(db, author_id: int, since_iso: str) -> int:
    """Сколько релизов автор опубликовал/запланировал начиная с since_iso (для throttling)."""
    db.cursor.execute('''
        SELECT COUNT(*) AS n FROM scheduled_posts
        WHERE author_id = ?
          AND status IN ('scheduled','published')
          AND COALESCE(published_at, created_at) >= ?
    ''', (author_id, since_iso))
    row = db.cursor.fetchone()
    return int(row['n']) if row else 0


# ════════════════════════════════════════════════════════════════════
# Multi-target
# ════════════════════════════════════════════════════════════════════

def add_target(db, post_id: int, chat_id: int, thread_id: int = None) -> int:
    db.cursor.execute('''
        INSERT INTO press_release_targets (post_id, chat_id, thread_id)
        VALUES (?, ?, ?)
    ''', (post_id, chat_id, thread_id))
    db.conn.commit()
    return db.cursor.lastrowid


def replace_targets(db, post_id: int, targets: list) -> None:
    """targets: [{'chat_id':..., 'thread_id':...}, ...]"""
    db.cursor.execute("DELETE FROM press_release_targets WHERE post_id = ?", (post_id,))
    for t in targets:
        db.cursor.execute('''
            INSERT INTO press_release_targets (post_id, chat_id, thread_id)
            VALUES (?, ?, ?)
        ''', (post_id, t['chat_id'], t.get('thread_id')))
    db.conn.commit()


def get_targets(db, post_id: int) -> list:
    db.cursor.execute('''
        SELECT id, chat_id, thread_id, published_at, message_ids, error
        FROM press_release_targets WHERE post_id = ?
        ORDER BY id
    ''', (post_id,))
    out = []
    for r in db.cursor.fetchall():
        d = dict(r)
        if d.get('message_ids'):
            try:
                d['message_ids'] = json.loads(d['message_ids'])
            except (ValueError, TypeError):
                d['message_ids'] = []
        else:
            d['message_ids'] = []
        out.append(d)
    return out


def mark_target_published(db, target_id: int, message_ids: list) -> None:
    db.cursor.execute('''
        UPDATE press_release_targets
        SET published_at = CURRENT_TIMESTAMP,
            message_ids = ?,
            error = NULL
        WHERE id = ?
    ''', (json.dumps(message_ids), target_id))
    db.conn.commit()


def mark_target_error(db, target_id: int, error: str) -> None:
    db.cursor.execute(
        "UPDATE press_release_targets SET error = ? WHERE id = ?",
        (error, target_id)
    )
    db.conn.commit()


# ════════════════════════════════════════════════════════════════════
# Шаблоны
# ════════════════════════════════════════════════════════════════════

def list_templates(db) -> list:
    db.cursor.execute('''
        SELECT * FROM press_release_templates
        ORDER BY name COLLATE NOCASE
    ''')
    return [dict(r) for r in db.cursor.fetchall()]


def get_template(db, template_id: int) -> Optional[dict]:
    db.cursor.execute("SELECT * FROM press_release_templates WHERE id = ?", (template_id,))
    row = db.cursor.fetchone()
    return dict(row) if row else None


def create_template(db, name: str, created_by: int, **fields) -> int:
    cols = ['name', 'created_by'] + [k for k in fields if k in {
        'text', 'photo_file_id', 'inline_keyboard', 'settings_json',
        'bold_header', 'add_signature', 'signature'
    }]
    vals = [name, created_by] + [fields[k] for k in cols[2:]]
    placeholders = ','.join('?' * len(cols))
    db.cursor.execute(
        f"INSERT INTO press_release_templates ({','.join(cols)}) VALUES ({placeholders})",
        vals
    )
    db.conn.commit()
    return db.cursor.lastrowid


def update_template(db, template_id: int, **fields) -> bool:
    allowed = {'name', 'text', 'photo_file_id', 'inline_keyboard',
               'settings_json', 'bold_header', 'add_signature', 'signature'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    set_clause = ', '.join(f'{k} = ?' for k in updates)
    vals = list(updates.values()) + [template_id]
    db.cursor.execute(
        f"UPDATE press_release_templates SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        vals
    )
    db.conn.commit()
    return db.cursor.rowcount > 0


def delete_template(db, template_id: int) -> bool:
    db.cursor.execute("DELETE FROM press_release_templates WHERE id = ?", (template_id,))
    db.conn.commit()
    return db.cursor.rowcount > 0


# ════════════════════════════════════════════════════════════════════
# История версий
# ════════════════════════════════════════════════════════════════════

def save_version(db, post_id: int, snapshot: dict, saved_by: int) -> int:
    """Сохранить версию и инкрементировать version в scheduled_posts."""
    db.cursor.execute(
        "SELECT COALESCE(MAX(version),0)+1 AS v FROM press_release_versions WHERE post_id = ?",
        (post_id,)
    )
    next_v = db.cursor.fetchone()['v']
    db.cursor.execute('''
        INSERT INTO press_release_versions (post_id, version, snapshot, saved_by)
        VALUES (?, ?, ?, ?)
    ''', (post_id, next_v, json.dumps(snapshot, ensure_ascii=False), saved_by))
    db.cursor.execute(
        "UPDATE scheduled_posts SET version = ? WHERE id = ?",
        (next_v, post_id)
    )
    db.conn.commit()
    return next_v


def list_versions(db, post_id: int) -> list:
    db.cursor.execute('''
        SELECT v.id, v.version, v.saved_at, v.saved_by, u.username, u.first_name
        FROM press_release_versions v
        LEFT JOIN users u ON v.saved_by = u.user_id
        WHERE v.post_id = ?
        ORDER BY v.version DESC
    ''', (post_id,))
    return [dict(r) for r in db.cursor.fetchall()]


def get_version_snapshot(db, version_id: int) -> Optional[dict]:
    db.cursor.execute("SELECT snapshot FROM press_release_versions WHERE id = ?", (version_id,))
    row = db.cursor.fetchone()
    if not row:
        return None
    try:
        return json.loads(row['snapshot'])
    except (ValueError, TypeError):
        return None


# ════════════════════════════════════════════════════════════════════
# Брендинг (key-value)
# ════════════════════════════════════════════════════════════════════

def get_branding(db, key: str, default=None):
    db.cursor.execute("SELECT value FROM branding_settings WHERE key = ?", (key,))
    row = db.cursor.fetchone()
    return row['value'] if row else default


def set_branding(db, key: str, value: str, by_user_id: int) -> None:
    db.cursor.execute('''
        INSERT INTO branding_settings (key, value, updated_by, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_by = excluded.updated_by,
            updated_at = CURRENT_TIMESTAMP
    ''', (key, value, by_user_id))
    db.conn.commit()


def get_all_branding(db) -> dict:
    db.cursor.execute("SELECT key, value FROM branding_settings")
    return {r['key']: r['value'] for r in db.cursor.fetchall()}
