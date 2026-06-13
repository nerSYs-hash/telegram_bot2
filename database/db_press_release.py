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

V1.17.0a14 (multi-tenancy): все CRUD-функции принимают workspace_id первым
аргументом после `db`. Tables: scheduled_posts, bot_chats, bot_chat_topics,
press_release_templates, press_release_versions, press_release_targets,
branding_settings — все ALTER-нуты workspace_id миграцией multi_tenancy.py.
TODO(multi-tenancy-pk): branding_settings.key — нужен composite PK
(workspace_id, key); фикс перед onboarding 2-го workspace (см. memo
`multi_tenancy_pk_debt.md`).
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

def upsert_bot_chat(db, workspace_id: int, chat_id: int, chat_type: str, title: str = None,
                    username: str = None, is_forum: bool = False) -> None:
    """Добавить/обновить запись о чате где есть бот.

    Важно: chat_id — PK, и каждый чат принадлежит ровно одному workspace
    (Telegram chat не может быть в двух tenant-ах одновременно). При апсерте
    workspace_id перезаписывается на текущий — это правильно, потому что
    привязка чата к workspace определяется при добавлении бота владельцем.
    """
    db.cursor.execute('''
        INSERT INTO bot_chats (workspace_id, chat_id, type, title, username, is_forum, added_at, last_seen_at, removed_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL)
        ON CONFLICT(chat_id) DO UPDATE SET
            workspace_id = excluded.workspace_id,
            type         = excluded.type,
            title        = excluded.title,
            username     = excluded.username,
            is_forum     = excluded.is_forum,
            last_seen_at = CURRENT_TIMESTAMP,
            removed_at   = NULL
    ''', (workspace_id, chat_id, chat_type, title, username, 1 if is_forum else 0))
    db.conn.commit()


def mark_bot_chat_removed(db, chat_id: int) -> None:
    """Бот покинул чат — пометить removed_at.

    workspace_id не нужен: chat_id уникален глобально, и удаление чата
    однозначно идентифицируется по chat_id.
    """
    db.cursor.execute(
        "UPDATE bot_chats SET removed_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
        (chat_id,)
    )
    db.conn.commit()


def get_bot_chats(db, workspace_id: int, include_removed: bool = False) -> list:
    """Список чатов где сейчас есть бот (или все, если include_removed) для workspace."""
    if include_removed:
        where = "WHERE workspace_id = ?"
    else:
        where = "WHERE workspace_id = ? AND removed_at IS NULL"
    db.cursor.execute(f'''
        SELECT chat_id, type, title, username, is_forum, added_at, removed_at
        FROM bot_chats {where}
        ORDER BY title COLLATE NOCASE
    ''', (workspace_id,))
    return [dict(r) for r in db.cursor.fetchall()]


# ════════════════════════════════════════════════════════════════════
# bot_chat_topics
# ════════════════════════════════════════════════════════════════════

def upsert_bot_chat_topic(db, workspace_id: int, chat_id: int, thread_id: int,
                          name: str = None, source: str = 'auto') -> None:
    """Добавить/обновить топик форума."""
    db.cursor.execute('''
        INSERT INTO bot_chat_topics (workspace_id, chat_id, thread_id, name, source)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chat_id, thread_id) DO UPDATE SET
            name       = COALESCE(excluded.name, name),
            updated_at = CURRENT_TIMESTAMP
    ''', (workspace_id, chat_id, thread_id, name, source))
    db.conn.commit()


def get_bot_chat_topics(db, workspace_id: int, chat_id: int) -> list:
    """Список топиков для конкретного чата (в скоупе workspace)."""
    db.cursor.execute('''
        SELECT b.id, b.chat_id, b.thread_id, 
               CASE WHEN t.thread_name IS NOT NULL AND t.thread_name != '' THEN t.thread_name ELSE b.name END as name, 
               b.source, b.created_at
        FROM bot_chat_topics b
        LEFT JOIN topics t ON b.chat_id = t.chat_id AND b.thread_id = t.thread_id
        WHERE b.workspace_id = ? AND b.chat_id = ?
        ORDER BY b.thread_id
    ''', (workspace_id, chat_id))
    
    topics = []
    for r in db.cursor.fetchall():
        d = dict(r)
        name = d.get('name') or ''
        if name.strip():
            topics.append(d)
            
    return topics


def delete_bot_chat_topic(db, workspace_id: int, chat_id: int, thread_id: int) -> bool:
    db.cursor.execute(
        "DELETE FROM bot_chat_topics WHERE workspace_id = ? AND chat_id = ? AND thread_id = ?",
        (workspace_id, chat_id, thread_id)
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


def create_press_release(db, workspace_id: int, author_id: int, **fields) -> int:
    """Создать пресс-релиз. По умолчанию status=draft, publish_at=NULL.
       Multi-target пишется отдельно через add_target()."""
    fields.setdefault('status', 'draft')
    fields.setdefault('bold_header', 1)
    fields.setdefault('add_signature', 1)
    # publish_at — обязателен в схеме, кладём заглушку для черновиков
    if not fields.get('publish_at'):
        fields['publish_at'] = '1970-01-01 00:00:00'
    else:
        fields['publish_at'] = fields['publish_at'].replace('T', ' ')[:19]
    # target_chat_id — обязателен в схеме (NOT NULL); для черновиков 0
    fields.setdefault('target_chat_id', 0)

    cols = ['workspace_id', 'author_id'] + [k for k in fields if k in ALLOWED_FIELDS]
    vals = [workspace_id, author_id] + [fields[k] for k in cols[2:]]
    placeholders = ','.join('?' * len(cols))
    db.cursor.execute(
        f"INSERT INTO scheduled_posts ({','.join(cols)}, updated_at) VALUES ({placeholders}, CURRENT_TIMESTAMP)",
        vals
    )
    db.conn.commit()
    return db.cursor.lastrowid


def update_press_release(db, workspace_id: int, post_id: int, **fields) -> bool:
    """Обновить поля пресс-релиза. Только поля из ALLOWED_FIELDS."""
    updates = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}
    if 'publish_at' in updates and updates['publish_at']:
        updates['publish_at'] = updates['publish_at'].replace('T', ' ')[:19]
    if not updates:
        return False
    set_clause = ', '.join(f'{k} = ?' for k in updates)
    vals = list(updates.values()) + [post_id, workspace_id]
    db.cursor.execute(
        f"UPDATE scheduled_posts SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
        f"WHERE id = ? AND workspace_id = ?",
        vals
    )
    db.conn.commit()
    return db.cursor.rowcount > 0


def get_press_release(db, workspace_id: int, post_id: int) -> Optional[dict]:
    db.cursor.execute('''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
        WHERE sp.id = ? AND sp.workspace_id = ?
    ''', (post_id, workspace_id))
    row = db.cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d['targets'] = get_targets(db, workspace_id, post_id)
    return d


def list_press_releases(db, workspace_id: int, status: str = None, limit: int = 200) -> list:
    """Список постов. status: draft/scheduled/published/failed/cancelled (или None=все)."""
    sql = '''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
        WHERE sp.workspace_id = ?
    '''
    params = [workspace_id]
    if status:
        sql += " AND sp.status = ?"
        params.append(status)
    sql += " ORDER BY COALESCE(sp.updated_at, sp.created_at) DESC LIMIT ?"
    params.append(limit)
    db.cursor.execute(sql, params)
    return [dict(r) for r in db.cursor.fetchall()]


def delete_press_release(db, workspace_id: int, post_id: int) -> bool:
    """Полное удаление поста (вместе с таргетами и версиями — каскадом)."""
    db.cursor.execute(
        "DELETE FROM scheduled_posts WHERE id = ? AND workspace_id = ?",
        (post_id, workspace_id)
    )
    db.conn.commit()
    return db.cursor.rowcount > 0


def cancel_press_release(db, workspace_id: int, post_id: int, by_user_id: int) -> bool:
    db.cursor.execute('''
        UPDATE scheduled_posts
        SET status = 'cancelled',
            cancelled_at = CURRENT_TIMESTAMP,
            cancelled_by = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND workspace_id = ? AND status IN ('scheduled','draft')
    ''', (by_user_id, post_id, workspace_id))
    db.conn.commit()
    return db.cursor.rowcount > 0


def restore_press_release(db, workspace_id: int, post_id: int) -> bool:
    """cancelled/failed → draft (возврат на редактирование)."""
    db.cursor.execute('''
        UPDATE scheduled_posts
        SET status = 'draft',
            cancelled_at = NULL, cancelled_by = NULL, failed_reason = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND workspace_id = ? AND status IN ('cancelled','failed')
    ''', (post_id, workspace_id))
    db.conn.commit()
    return db.cursor.rowcount > 0


def mark_failed(db, workspace_id: int, post_id: int, reason: str) -> None:
    db.cursor.execute('''
        UPDATE scheduled_posts
        SET status = 'failed', failed_reason = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND workspace_id = ?
    ''', (reason, post_id, workspace_id))
    db.conn.commit()


def mark_published(db, workspace_id: int, post_id: int) -> None:
    db.cursor.execute('''
        UPDATE scheduled_posts
        SET status = 'published', published_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND workspace_id = ?
    ''', (post_id, workspace_id))
    db.conn.commit()


def clone_press_release(db, workspace_id: int, post_id: int, new_author_id: int) -> Optional[int]:
    """Дублировать пост → возвращает id копии (status=draft)."""
    src = get_press_release(db, workspace_id, post_id)
    if not src:
        return None
    fields = {k: src.get(k) for k in (
        'title', 'text', 'photo_file_id', 'signature', 'bold_header',
        'add_signature', 'inline_keyboard', 'settings_json',
        'pre_publish_reminder', 'template_id', 'target_chat_id', 'thread_id'
    )}
    fields['title'] = (fields.get('title') or '') + ' (копия)'
    fields['status'] = 'draft'
    new_id = create_press_release(db, workspace_id, new_author_id, **fields)
    # Копируем таргеты
    for t in src.get('targets', []):
        add_target(db, workspace_id, new_id, t['chat_id'], t.get('thread_id'))
    return new_id


def get_pending_press_releases(db, workspace_id: int, before_time: str) -> list:
    """Возвращает посты status=scheduled с publish_at <= before_time для workspace.

    Note: publisher loop вызывает это для каждого workspace отдельно (или
    проходит по всем workspaces). Для глобального обхода всех тенантов
    workspace_id=None пока не поддерживается — добавим если потребуется.
    """
    db.cursor.execute('''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
        WHERE sp.workspace_id = ? AND sp.status IN ('scheduled', 'pending') AND REPLACE(sp.publish_at, 'T', ' ') <= ?
        ORDER BY sp.publish_at ASC
    ''', (workspace_id, before_time))
    return [dict(r) for r in db.cursor.fetchall()]


def get_all_pending_press_releases(db, before_time: str) -> list:
    """Cross-workspace: все scheduled-релизы со всех тенантов (для глобального
    publisher loop в bot.py). Возвращает sp.workspace_id чтобы вызывающий мог
    собрать WorkspaceContext."""
    db.cursor.execute('''
        SELECT sp.*, u.username, u.first_name
        FROM scheduled_posts sp
        LEFT JOIN users u ON sp.author_id = u.user_id
        WHERE sp.status IN ('scheduled', 'pending') AND REPLACE(sp.publish_at, 'T', ' ') <= ?
        ORDER BY sp.workspace_id, sp.publish_at ASC
    ''', (before_time,))
    return [dict(r) for r in db.cursor.fetchall()]


def count_recent_press_releases(db, workspace_id: int, author_id: int, since_iso: str) -> int:
    """Сколько релизов автор опубликовал/запланировал начиная с since_iso (для throttling)."""
    db.cursor.execute('''
        SELECT COUNT(*) AS n FROM scheduled_posts
        WHERE workspace_id = ?
          AND author_id = ?
          AND status IN ('scheduled','published')
          AND COALESCE(published_at, created_at) >= ?
    ''', (workspace_id, author_id, since_iso))
    row = db.cursor.fetchone()
    return int(row['n']) if row else 0


# ════════════════════════════════════════════════════════════════════
# Multi-target
# ════════════════════════════════════════════════════════════════════

def add_target(db, workspace_id: int, post_id: int, chat_id: int, thread_id: int = None) -> int:
    db.cursor.execute('''
        INSERT INTO press_release_targets (workspace_id, post_id, chat_id, thread_id)
        VALUES (?, ?, ?, ?)
    ''', (workspace_id, post_id, chat_id, thread_id))
    db.conn.commit()
    return db.cursor.lastrowid


def replace_targets(db, workspace_id: int, post_id: int, targets: list) -> None:
    """targets: [{'chat_id':..., 'thread_id':...}, ...]"""
    db.cursor.execute(
        "DELETE FROM press_release_targets WHERE workspace_id = ? AND post_id = ?",
        (workspace_id, post_id)
    )
    for t in targets:
        db.cursor.execute('''
            INSERT INTO press_release_targets (workspace_id, post_id, chat_id, thread_id)
            VALUES (?, ?, ?, ?)
        ''', (workspace_id, post_id, t['chat_id'], t.get('thread_id')))
    db.conn.commit()


def get_targets(db, workspace_id: int, post_id: int) -> list:
    db.cursor.execute('''
        SELECT id, chat_id, thread_id, published_at, message_ids, error
        FROM press_release_targets
        WHERE workspace_id = ? AND post_id = ?
        ORDER BY id
    ''', (workspace_id, post_id))
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


def mark_target_published(db, workspace_id: int, target_id: int, message_ids: list) -> None:
    db.cursor.execute('''
        UPDATE press_release_targets
        SET published_at = CURRENT_TIMESTAMP,
            message_ids = ?,
            error = NULL
        WHERE id = ? AND workspace_id = ?
    ''', (json.dumps(message_ids), target_id, workspace_id))
    db.conn.commit()


def mark_target_error(db, workspace_id: int, target_id: int, error: str) -> None:
    db.cursor.execute(
        "UPDATE press_release_targets SET error = ? WHERE id = ? AND workspace_id = ?",
        (error, target_id, workspace_id)
    )
    db.conn.commit()


# ════════════════════════════════════════════════════════════════════
# Шаблоны
# ════════════════════════════════════════════════════════════════════

def list_templates(db, workspace_id: int) -> list:
    db.cursor.execute('''
        SELECT * FROM press_release_templates
        WHERE workspace_id = ?
        ORDER BY name COLLATE NOCASE
    ''', (workspace_id,))
    return [dict(r) for r in db.cursor.fetchall()]


def get_template(db, workspace_id: int, template_id: int) -> Optional[dict]:
    db.cursor.execute(
        "SELECT * FROM press_release_templates WHERE id = ? AND workspace_id = ?",
        (template_id, workspace_id)
    )
    row = db.cursor.fetchone()
    return dict(row) if row else None


def create_template(db, workspace_id: int, name: str, created_by: int, **fields) -> int:
    cols = ['workspace_id', 'name', 'created_by'] + [k for k in fields if k in {
        'text', 'photo_file_id', 'inline_keyboard', 'settings_json',
        'bold_header', 'add_signature', 'signature'
    }]
    vals = [workspace_id, name, created_by] + [fields[k] for k in cols[3:]]
    placeholders = ','.join('?' * len(cols))
    db.cursor.execute(
        f"INSERT INTO press_release_templates ({','.join(cols)}) VALUES ({placeholders})",
        vals
    )
    db.conn.commit()
    return db.cursor.lastrowid


def update_template(db, workspace_id: int, template_id: int, **fields) -> bool:
    allowed = {'name', 'text', 'photo_file_id', 'inline_keyboard',
               'settings_json', 'bold_header', 'add_signature', 'signature'}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    set_clause = ', '.join(f'{k} = ?' for k in updates)
    vals = list(updates.values()) + [template_id, workspace_id]
    db.cursor.execute(
        f"UPDATE press_release_templates SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
        f"WHERE id = ? AND workspace_id = ?",
        vals
    )
    db.conn.commit()
    return db.cursor.rowcount > 0


def delete_template(db, workspace_id: int, template_id: int) -> bool:
    db.cursor.execute(
        "DELETE FROM press_release_templates WHERE id = ? AND workspace_id = ?",
        (template_id, workspace_id)
    )
    db.conn.commit()
    return db.cursor.rowcount > 0


# ════════════════════════════════════════════════════════════════════
# История версий
# ════════════════════════════════════════════════════════════════════

def save_version(db, workspace_id: int, post_id: int, snapshot: dict, saved_by: int) -> int:
    """Сохранить версию и инкрементировать version в scheduled_posts."""
    db.cursor.execute(
        "SELECT COALESCE(MAX(version),0)+1 AS v FROM press_release_versions "
        "WHERE workspace_id = ? AND post_id = ?",
        (workspace_id, post_id)
    )
    next_v = db.cursor.fetchone()['v']
    db.cursor.execute('''
        INSERT INTO press_release_versions (workspace_id, post_id, version, snapshot, saved_by)
        VALUES (?, ?, ?, ?, ?)
    ''', (workspace_id, post_id, next_v, json.dumps(snapshot, ensure_ascii=False), saved_by))
    db.cursor.execute(
        "UPDATE scheduled_posts SET version = ? WHERE id = ? AND workspace_id = ?",
        (next_v, post_id, workspace_id)
    )
    db.conn.commit()
    return next_v


def list_versions(db, workspace_id: int, post_id: int) -> list:
    db.cursor.execute('''
        SELECT v.id, v.version, v.saved_at, v.saved_by, u.username, u.first_name
        FROM press_release_versions v
        LEFT JOIN users u ON v.saved_by = u.user_id
        WHERE v.workspace_id = ? AND v.post_id = ?
        ORDER BY v.version DESC
    ''', (workspace_id, post_id))
    return [dict(r) for r in db.cursor.fetchall()]


def get_version_snapshot(db, workspace_id: int, version_id: int) -> Optional[dict]:
    db.cursor.execute(
        "SELECT snapshot FROM press_release_versions WHERE id = ? AND workspace_id = ?",
        (version_id, workspace_id)
    )
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
# TODO(multi-tenancy-pk): PK у branding_settings всё ещё `key`. Перед
# onboarding 2-го workspace нужно пересоздать таблицу с composite PK
# (workspace_id, key) — см. multi_tenancy_pk_debt.md. Сейчас два workspace
# не могут иметь одинаковые ключи брендинга.

def get_branding(db, workspace_id: int, key: str, default=None):
    db.cursor.execute(
        "SELECT value FROM branding_settings WHERE workspace_id = ? AND key = ?",
        (workspace_id, key)
    )
    row = db.cursor.fetchone()
    return row['value'] if row else default


def set_branding(db, workspace_id: int, key: str, value: str, by_user_id: int) -> None:
    # ON CONFLICT(key) — пока однотенантный PK; перед multi-tenant нужен
    # composite PK (workspace_id, key). См. TODO выше.
    db.cursor.execute('''
        INSERT INTO branding_settings (workspace_id, key, value, updated_by, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(workspace_id, key) DO UPDATE SET
            workspace_id = excluded.workspace_id,
            value = excluded.value,
            updated_by = excluded.updated_by,
            updated_at = CURRENT_TIMESTAMP
    ''', (workspace_id, key, value, by_user_id))
    db.conn.commit()


def get_all_branding(db, workspace_id: int) -> dict:
    db.cursor.execute(
        "SELECT key, value FROM branding_settings WHERE workspace_id = ?",
        (workspace_id,)
    )
    return {r['key']: r['value'] for r in db.cursor.fetchall()}
