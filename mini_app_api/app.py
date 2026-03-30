from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, Query
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def _resolve_db_path() -> Path:
    db_path = os.getenv('DATABASE_PATH', 'database/bot_database.db')
    candidate = Path(db_path)
    return candidate if candidate.is_absolute() else BASE_DIR / candidate


DB_PATH = _resolve_db_path()

app = FastAPI(title='Pulse Mini App API', version='0.1.0')
def _allowed_origins() -> list[str]:
    base = [
        'http://127.0.0.1:3000',
        'http://localhost:3000',
        'https://web.telegram.org',
        'https://web.telegram.org/a',
    ]
    extra_raw = os.getenv('MINI_APP_ALLOWED_ORIGINS', '')
    extra = [o.strip() for o in extra_raw.split(',') if o.strip()]
    return list(dict.fromkeys(base + extra))  # дедупликация сохраняет порядок


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def _fetch_user(user_id: int | None) -> dict[str, Any] | None:
    if user_id is None or not DB_PATH.exists():
        return None

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        row = connection.execute(
            '''
            SELECT user_id, username, first_name, last_name, balance, is_admin, is_owner, is_left
            FROM users
            WHERE user_id = ?
            ''',
            (user_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    display_name = row['first_name'] or row['username'] or f"User {row['user_id']}"
    return {
        'userId': row['user_id'],
        'username': row['username'],
        'displayName': display_name,
        'balance': int(row['balance'] or 0),
        'isAdmin': bool(row['is_admin']),
        'isOwner': bool(row['is_owner']),
        'isLinked': True,
        'isLeft': bool(row['is_left']),
    }


def _build_guest(user_id: int | None) -> dict[str, Any]:
    return {
        'userId': user_id,
        'username': None,
        'displayName': 'Гость Mini App',
        'balance': 0,
        'isAdmin': False,
        'isOwner': False,
        'isLinked': False,
        'isLeft': False,
    }


@app.get('/api/mini-app/health')
def mini_app_health() -> dict[str, Any]:
    return {
        'ok': True,
        'service': 'pulse-mini-app-api',
        'databasePath': str(DB_PATH),
        'databaseExists': DB_PATH.exists(),
    }


@app.get('/api/mini-app/bootstrap')
def mini_app_bootstrap(
    user_id: int | None = Query(default=None),
    x_telegram_user_id: int | None = Header(default=None, alias='X-Telegram-User-Id'),
) -> dict[str, Any]:
    resolved_user_id = user_id or x_telegram_user_id
    user = _fetch_user(resolved_user_id) or _build_guest(resolved_user_id)

    return {
        'ok': True,
        'environment': os.getenv('APP_ENV', 'development'),
        'launchMode': 'telegram' if x_telegram_user_id else 'browser',
        'user': user,
        'sections': [
            {
                'id': 'profile',
                'title': 'Профиль',
                'description': 'Отсюда начнем: паспорт пользователя, роль, базовые статусы и данные из БД.',
                'state': 'ready',
            },
            {
                'id': 'bbs',
                'title': 'BBS',
                'description': 'Анкета, статус публикации и удаление BBS-профиля прямо из Mini App.',
                'state': 'ready',
            },
            {
                'id': 'economy',
                'title': 'Экономика',
                'description': 'Баланс, история операций и статистика приходов/расходов.',
                'state': 'ready',
            },
        ],
    }


@app.get('/api/mini-app/profile/{user_id}')
def mini_app_profile(user_id: int) -> dict[str, Any]:
    if not DB_PATH.exists():
        return {'ok': False, 'error': 'database not found'}

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        user_row = connection.execute(
            '''
            SELECT user_id, username, first_name, last_name,
                   balance, frozen_balance, is_admin, is_owner,
                   is_qualified, is_left, joined_at, last_active, referral_code
            FROM users WHERE user_id = ?
            ''',
            (user_id,),
        ).fetchone()

        if user_row is None:
            return {'ok': False, 'error': 'user not found'}

        stats_row = connection.execute(
            '''
            SELECT
                COALESCE(SUM(total_messages), 0)  AS total_messages,
                COALESCE(SUM(total_chars), 0)     AS total_chars,
                COALESCE(SUM(reactions_given), 0) AS reactions_given,
                MAX(date)                         AS last_active_date
            FROM user_stats WHERE user_id = ?
            ''',
            (user_id,),
        ).fetchone()

        try:
            bbs_row = connection.execute(
                'SELECT 1 FROM bbs_profiles WHERE user_id = ? LIMIT 1', (user_id,)
            ).fetchone()
            has_bbs = bbs_row is not None
        except sqlite3.OperationalError:
            has_bbs = False

        ref_row = connection.execute(
            'SELECT COUNT(*) AS cnt FROM users WHERE referrer_id = ?', (user_id,)
        ).fetchone()
    finally:
        connection.close()

    display_name = (
        user_row['first_name']
        or user_row['username']
        or f"User {user_row['user_id']}"
    )

    return {
        'ok': True,
        'profile': {
            'userId': user_row['user_id'],
            'username': user_row['username'],
            'displayName': display_name,
            'firstName': user_row['first_name'],
            'lastName': user_row['last_name'],
            'balance': int(user_row['balance'] or 0),
            'frozenBalance': int(user_row['frozen_balance'] or 0),
            'isAdmin': bool(user_row['is_admin']),
            'isOwner': bool(user_row['is_owner']),
            'isQualified': bool(user_row['is_qualified']),
            'isLeft': bool(user_row['is_left']),
            'joinedAt': user_row['joined_at'],
            'lastActive': user_row['last_active'],
            'referralCode': user_row['referral_code'],
            'referralCount': int(ref_row['cnt'] or 0) if ref_row else 0,
            'stats': {
                'totalMessages': int(stats_row['total_messages'] or 0) if stats_row else 0,
                'totalChars': int(stats_row['total_chars'] or 0) if stats_row else 0,
                'reactionsGiven': int(stats_row['reactions_given'] or 0) if stats_row else 0,
                'lastActiveDate': stats_row['last_active_date'] if stats_row else None,
            },
            'hasBbsProfile': has_bbs,
        },
    }



@app.get('/api/mini-app/bbs/{user_id}')
def mini_app_bbs_get(user_id: int) -> dict[str, Any]:
    if not DB_PATH.exists():
        return {'ok': False, 'hasProfile': False, 'error': 'database not found'}

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            """
            SELECT id, user_id, username, name, age, city, roles, goals,
                   about, params, photos, reaction_count, published_at,
                   created_at, message_ids, thread_id
            FROM bbs_profiles WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return {'ok': True, 'hasProfile': False}
    finally:
        connection.close()

    if row is None:
        return {'ok': True, 'hasProfile': False}

    import json as _json

    def _parse_list(raw):
        if not raw:
            return []
        try:
            result = _json.loads(raw)
            return result if isinstance(result, list) else []
        except Exception:
            return []

    is_published = bool(row['published_at'] and row['message_ids'])

    return {
        'ok': True,
        'hasProfile': True,
        'profile': {
            'id': row['id'],
            'userId': row['user_id'],
            'username': row['username'],
            'name': row['name'],
            'age': row['age'],
            'city': _parse_list(row['city']),
            'roles': _parse_list(row['roles']),
            'goals': _parse_list(row['goals']),
            'about': row['about'],
            'params': row['params'],
            'photos': _parse_list(row['photos']),
            'reactionCount': int(row['reaction_count'] or 0),
            'publishedAt': row['published_at'],
            'createdAt': row['created_at'],
            'isPublished': is_published,
        },
    }


@app.delete('/api/mini-app/bbs/{user_id}')
def mini_app_bbs_delete(user_id: int) -> dict[str, Any]:
    if not DB_PATH.exists():
        return {'ok': False, 'error': 'database not found'}

    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute('DELETE FROM bbs_profiles WHERE user_id = ?', (user_id,))
        connection.commit()
    except sqlite3.OperationalError as exc:
        return {'ok': False, 'error': str(exc)}
    finally:
        connection.close()

    return {'ok': True}


@app.get('/api/mini-app/economy/{user_id}')
def mini_app_economy(
    user_id: int,
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, Any]:
    if not DB_PATH.exists():
        return {'ok': False, 'error': 'database not found'}

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        user_row = connection.execute(
            'SELECT balance, frozen_balance FROM users WHERE user_id = ?',
            (user_id,),
        ).fetchone()

        if user_row is None:
            return {'ok': False, 'error': 'user not found'}

        uid_str = str(user_id)
        txn_rows = connection.execute(
            '''
            SELECT id, from_user_id, to_user_id, amount,
                   transaction_type, description, timestamp
            FROM transactions
            WHERE from_user_id = ?1 OR CAST(from_user_id AS TEXT) = ?2
               OR to_user_id   = ?1 OR CAST(to_user_id   AS TEXT) = ?2
            ORDER BY id DESC
            LIMIT ?3
            ''',
            (user_id, uid_str, limit),
        ).fetchall()

        stats_row = connection.execute(
            '''
            SELECT
                COALESCE(SUM(CASE
                    WHEN to_user_id = ?1 OR CAST(to_user_id AS TEXT) = ?2
                    THEN amount ELSE 0 END), 0) AS total_received,
                COALESCE(SUM(CASE
                    WHEN from_user_id = ?1 OR CAST(from_user_id AS TEXT) = ?2
                    THEN amount ELSE 0 END), 0) AS total_sent
            FROM transactions
            ''',
            (user_id, uid_str),
        ).fetchone()
    finally:
        connection.close()

    txns = []
    for row in txn_rows:
        to_val = row['to_user_id']
        is_incoming = (to_val == user_id or str(to_val) == uid_str)
        txns.append({
            'id': row['id'],
            'direction': 'in' if is_incoming else 'out',
            'amount': round(float(row['amount'] or 0), 2),
            'type': row['transaction_type'],
            'description': row['description'],
            'fromUserId': row['from_user_id'],
            'toUserId': row['to_user_id'],
            'timestamp': row['timestamp'],
        })

    return {
        'ok': True,
        'economy': {
            'balance': int(user_row['balance'] or 0),
            'frozenBalance': int(user_row['frozen_balance'] or 0),
            'totalReceived': round(float(stats_row['total_received'] or 0), 2),
            'totalSent': round(float(stats_row['total_sent'] or 0), 2),
            'transactions': txns,
        },
    }


