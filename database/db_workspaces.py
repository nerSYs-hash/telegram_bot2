"""CRUD для workspaces и workspace_members. Используется в bot.py и api.py."""
import sqlite3
from typing import Optional, List
from dataclasses import dataclass
from bot_core.connect_flow import connect_flow_v2_enabled


@dataclass
class Workspace:
    id: int
    name: str
    owner_user_id: int
    is_pulse_themed: bool
    plan: str
    settings_json: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row[0], name=row[1], owner_user_id=row[2],
            is_pulse_themed=bool(row[3]), plan=row[4],
            settings_json=row[5], created_at=row[6], updated_at=row[7],
        )


@dataclass
class WorkspaceMember:
    workspace_id: int
    user_id: int
    role: str  # 'owner' | 'admin' | 'moderator'
    joined_at: str


def create_workspace(
    conn: sqlite3.Connection, name: str, owner_user_id: int,
    is_pulse_themed: bool = False, plan: str = 'free',
) -> int:
    """Создаёт workspace, возвращает его id. Owner автоматически добавляется в members."""
    cur = conn.execute(
        'INSERT INTO workspaces (name, owner_user_id, is_pulse_themed, plan) '
        'VALUES (?, ?, ?, ?)',
        (name, owner_user_id, 1 if is_pulse_themed else 0, plan)
    )
    ws_id = cur.lastrowid
    conn.execute(
        'INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)',
        (ws_id, owner_user_id, 'owner')
    )
    conn.commit()
    return ws_id


def get_workspace(conn: sqlite3.Connection, ws_id: int) -> Optional[Workspace]:
    row = conn.execute(
        'SELECT id, name, owner_user_id, is_pulse_themed, plan, settings_json, '
        'created_at, updated_at FROM workspaces WHERE id=?', (ws_id,)
    ).fetchone()
    return Workspace.from_row(row) if row else None


def list_workspaces_for_user(
    conn: sqlite3.Connection, user_id: int
) -> List[Workspace]:
    """Все workspaces где user является членом."""
    rows = conn.execute(
        'SELECT w.id, w.name, w.owner_user_id, w.is_pulse_themed, w.plan, '
        '       w.settings_json, w.created_at, w.updated_at '
        'FROM workspaces w '
        'JOIN workspace_members m ON m.workspace_id = w.id '
        'WHERE m.user_id=? '
        'ORDER BY w.created_at',
        (user_id,)
    ).fetchall()
    return [Workspace.from_row(r) for r in rows]


def add_member(
    conn: sqlite3.Connection, ws_id: int, user_id: int, role: str
) -> None:
    if role not in ('owner', 'admin', 'moderator'):
        raise ValueError(f'Invalid role: {role}')
    conn.execute(
        'INSERT OR REPLACE INTO workspace_members (workspace_id, user_id, role) '
        'VALUES (?, ?, ?)',
        (ws_id, user_id, role)
    )
    conn.commit()


def remove_member(conn: sqlite3.Connection, ws_id: int, user_id: int) -> None:
    """Owner-а удалять нельзя — отдельный transfer_ownership."""
    role = get_member_role(conn, ws_id, user_id)
    if role == 'owner':
        raise ValueError('Cannot remove owner. Transfer ownership first.')
    conn.execute(
        'DELETE FROM workspace_members WHERE workspace_id=? AND user_id=?',
        (ws_id, user_id)
    )
    conn.commit()


def get_member_role(
    conn: sqlite3.Connection, ws_id: int, user_id: int
) -> Optional[str]:
    row = conn.execute(
        'SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?',
        (ws_id, user_id)
    ).fetchone()
    return row[0] if row else None


# ── V1.17.0b3: helpers для UI и onboarding flow ──

def get_workspaces_for_user(conn: sqlite3.Connection, user_id: int) -> list:
    """Все workspaces где user — member. Включает role и счётчики.

    V1.17.0i (C8): сортировка `is_pulse_themed DESC, created_at ASC` —
    главное сообщество первым, далее по дате создания (стабильно для
    UI-нумерации «доп. №N»). Поле `is_primary` дублирует `is_pulse_themed`
    как явный UX-флаг.
    V1.17.0i (C6): `active_chats_count` — bot_chats без `removed_at`.
    Старое `chats_count` сохранено как «всего» для обратной совместимости;
    разница = soft-removed чаты. На схеме без колонки `removed_at` (старые
    БД до миграции h-семейства) active_chats_count == chats_count.
    """
    has_removed = _bot_chats_has_removed_at(conn)
    active_expr = (
        "(SELECT COUNT(*) FROM bot_chats WHERE workspace_id=w.id AND removed_at IS NULL)"
        if has_removed
        else "(SELECT COUNT(*) FROM bot_chats WHERE workspace_id=w.id)"
    )
    rows = conn.execute(f'''
        SELECT
            w.id, w.name, w.owner_user_id, w.is_pulse_themed, w.plan,
            m.role,
            (SELECT COUNT(*) FROM workspace_members WHERE workspace_id=w.id) AS members_count,
            (SELECT COUNT(*) FROM bot_chats WHERE workspace_id=w.id) AS chats_count,
            {active_expr} AS active_chats_count
        FROM workspaces w
        JOIN workspace_members m ON m.workspace_id = w.id
        WHERE m.user_id = ?
        ORDER BY w.is_pulse_themed DESC, w.created_at ASC, w.id ASC
    ''', (user_id,)).fetchall()
    keys = ('id', 'name', 'owner_user_id', 'is_pulse_themed', 'plan',
            'role', 'members_count', 'chats_count', 'active_chats_count')
    result = []
    for r in rows:
        d = dict(zip(keys, r))
        d['is_primary'] = bool(d['is_pulse_themed'])
        result.append(d)
    return result


def get_workspace_details(conn: sqlite3.Connection, workspace_id: int) -> Optional[dict]:
    """Workspace + список членов + список чатов."""
    ws_row = conn.execute(
        'SELECT id, name, owner_user_id, is_pulse_themed, plan, created_at '
        'FROM workspaces WHERE id=?', (workspace_id,)
    ).fetchone()
    if not ws_row:
        return None

    members = conn.execute('''
        SELECT user_id, role, joined_at
        FROM workspace_members WHERE workspace_id=?
        ORDER BY CASE role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,
                 joined_at
    ''', (workspace_id,)).fetchall()

    # V1.17.0i (C6): отдаём removed_at каждому чату; активные сверху, отключённые внизу.
    # На старой схеме без колонки — SELECT NULL и стабильный порядок по role/дате.
    has_removed = _bot_chats_has_removed_at(conn)
    if has_removed:
        chats = conn.execute('''
            SELECT chat_id, title, chat_type, added_by_user_id, added_at, role, removed_at
            FROM bot_chats WHERE workspace_id=?
            ORDER BY
              CASE WHEN removed_at IS NULL THEN 0 ELSE 1 END,
              CASE role WHEN 'main' THEN 0 WHEN 'admin' THEN 1 WHEN 'journal' THEN 2 ELSE 3 END,
              added_at DESC
        ''', (workspace_id,)).fetchall()
    else:
        chats = conn.execute('''
            SELECT chat_id, title, chat_type, added_by_user_id, added_at, role, NULL AS removed_at
            FROM bot_chats WHERE workspace_id=?
            ORDER BY
              CASE role WHEN 'main' THEN 0 WHEN 'admin' THEN 1 WHEN 'journal' THEN 2 ELSE 3 END,
              added_at DESC
        ''', (workspace_id,)).fetchall()

    return {
        'workspace': {
            'id': ws_row[0], 'name': ws_row[1], 'owner_user_id': ws_row[2],
            'is_pulse_themed': bool(ws_row[3]), 'plan': ws_row[4],
            'created_at': ws_row[5],
        },
        'members': [{'user_id': m[0], 'role': m[1], 'joined_at': m[2]} for m in members],
        'chats': [{'chat_id': c[0], 'title': c[1], 'chat_type': c[2],
                   'added_by': c[3], 'added_at': c[4], 'role': c[5],
                   'removed_at': c[6]} for c in chats],
    }


def update_workspace_name(conn: sqlite3.Connection, workspace_id: int, new_name: str) -> None:
    conn.execute(
        "UPDATE workspaces SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (new_name, workspace_id)
    )
    conn.commit()


def add_bot_chat(conn: sqlite3.Connection, chat_id: int, workspace_id: int,
                 added_by: int, title: Optional[str], chat_type: Optional[str],
                 role: Optional[str] = None) -> None:
    """Привязывает chat к workspace (upsert по chat_id). role: 'main'|'admin'|'journal'|None."""
    if role is not None and role not in ('main', 'admin', 'journal'):
        raise ValueError(f'Invalid chat role: {role!r}')
    conn.execute('''
        INSERT INTO bot_chats (chat_id, workspace_id, added_by_user_id, title, chat_type, role, added_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id) DO UPDATE SET
          workspace_id=excluded.workspace_id,
          added_by_user_id=excluded.added_by_user_id,
          title=excluded.title,
          chat_type=excluded.chat_type
    ''', (chat_id, workspace_id, added_by, title, chat_type, role))
    conn.commit()


def update_bot_chat_role(conn: sqlite3.Connection, chat_id: int, role: Optional[str]) -> None:
    """Меняет роль чата. role: 'main'|'admin'|'journal'|None (без роли)."""
    if role is not None and role not in ('main', 'admin', 'journal'):
        raise ValueError(f'Invalid chat role: {role!r}')
    conn.execute('UPDATE bot_chats SET role=? WHERE chat_id=?', (role, chat_id))
    conn.commit()


def get_workspace_by_chat(conn: sqlite3.Connection, chat_id: int) -> Optional[int]:
    """Возвращает workspace_id если chat привязан, иначе None.
    При CONNECT_FLOW_V2 ON: soft-removed чат (removed_at IS NOT NULL) → None."""
    if connect_flow_v2_enabled() and _bot_chats_has_removed_at(conn):
        row = conn.execute(
            'SELECT workspace_id FROM bot_chats '
            'WHERE chat_id=? AND removed_at IS NULL', (chat_id,)
        ).fetchone()
    else:
        row = conn.execute(
            'SELECT workspace_id FROM bot_chats WHERE chat_id=?', (chat_id,)
        ).fetchone()
    return row[0] if row else None


# ── V1.17.0c (G): удаление чатов и сообществ ──

def remove_bot_chat(conn: sqlite3.Connection, chat_id: int) -> None:
    """Удаляет запись чата из bot_chats. Workspace и members не трогает."""
    conn.execute('DELETE FROM bot_chats WHERE chat_id=?', (chat_id,))
    conn.commit()


def _bot_chats_has_removed_at(conn: sqlite3.Connection) -> bool:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_chats)").fetchall()]
    return 'removed_at' in cols


def soft_remove_bot_chat(conn: sqlite3.Connection, chat_id: int) -> None:
    """V1.17.0h: мягкое отключение — removed_at=now, workspace_id/role сохраняются.
    Если колонки removed_at нет (старая схема) — фолбэк на hard delete."""
    if _bot_chats_has_removed_at(conn):
        conn.execute(
            "UPDATE bot_chats SET removed_at=CURRENT_TIMESTAMP WHERE chat_id=?",
            (chat_id,))
    else:
        conn.execute("DELETE FROM bot_chats WHERE chat_id=?", (chat_id,))
    conn.commit()


def get_disconnected_bot_chat(conn: sqlite3.Connection, chat_id: int):
    """Вернёт {'workspace_id','role'} если чат soft-removed, иначе None."""
    if not _bot_chats_has_removed_at(conn):
        return None
    row = conn.execute(
        "SELECT workspace_id, role FROM bot_chats "
        "WHERE chat_id=? AND removed_at IS NOT NULL", (chat_id,)
    ).fetchone()
    return {'workspace_id': row[0], 'role': row[1]} if row else None


def list_chat_ids_for_workspace(conn: sqlite3.Connection, workspace_id: int) -> list:
    """Возвращает chat_id всех чатов привязанных к workspace."""
    return [r[0] for r in conn.execute(
        'SELECT chat_id FROM bot_chats WHERE workspace_id=?', (workspace_id,)
    ).fetchall()]


# V1.17.0h: единый список tenant-таблиц с колонкой workspace_id.
# Реюз: C9 (delete cascade) и scripts/consolidate_workspaces.py (safety).
TENANT_TABLES = (
    'economy_settings', 'economy_section_toggles', 'branding_settings',
    'user_stats', 'user_stats_hourly', 'chat_stats', 'topics', 'triggers',
)


def delete_workspace(conn: sqlite3.Connection, workspace_id: int) -> None:
    """Удаляет workspace полностью: members + bot_chats + сам workspace.

    При CONNECT_FLOW_V2 ON — дополнительно чистит tenant-данные (C9).
    Запрещает удаление is_pulse_themed=1 (защита Pulse-сообщества).
    """
    row = conn.execute(
        'SELECT is_pulse_themed FROM workspaces WHERE id=?', (workspace_id,)
    ).fetchone()
    if not row:
        return
    if row[0]:
        raise ValueError('Нельзя удалить Pulse-themed сообщество')
    if connect_flow_v2_enabled():
        for t in TENANT_TABLES:
            try:
                conn.execute(f'DELETE FROM {t} WHERE workspace_id=?', (workspace_id,))
            except sqlite3.OperationalError:
                pass  # таблицы может не быть в этой БД — ок
    conn.execute('DELETE FROM bot_chats WHERE workspace_id=?', (workspace_id,))
    conn.execute('DELETE FROM workspace_members WHERE workspace_id=?', (workspace_id,))
    conn.execute('DELETE FROM workspaces WHERE id=?', (workspace_id,))
    conn.commit()
