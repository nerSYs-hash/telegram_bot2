"""CRUD для workspaces и workspace_members. Используется в bot.py и api.py."""
import sqlite3
from typing import Optional, List
from dataclasses import dataclass


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
    """Все workspaces где user — member. Включает role и счётчики."""
    rows = conn.execute('''
        SELECT
            w.id, w.name, w.owner_user_id, w.is_pulse_themed, w.plan,
            m.role,
            (SELECT COUNT(*) FROM workspace_members WHERE workspace_id=w.id) AS members_count,
            (SELECT COUNT(*) FROM bot_chats WHERE workspace_id=w.id) AS chats_count
        FROM workspaces w
        JOIN workspace_members m ON m.workspace_id = w.id
        WHERE m.user_id = ?
        ORDER BY w.created_at DESC
    ''', (user_id,)).fetchall()
    keys = ('id', 'name', 'owner_user_id', 'is_pulse_themed', 'plan',
            'role', 'members_count', 'chats_count')
    return [dict(zip(keys, r)) for r in rows]


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

    chats = conn.execute('''
        SELECT chat_id, title, chat_type, added_by_user_id, added_at
        FROM bot_chats WHERE workspace_id=?
        ORDER BY added_at DESC
    ''', (workspace_id,)).fetchall()

    return {
        'workspace': {
            'id': ws_row[0], 'name': ws_row[1], 'owner_user_id': ws_row[2],
            'is_pulse_themed': bool(ws_row[3]), 'plan': ws_row[4],
            'created_at': ws_row[5],
        },
        'members': [{'user_id': m[0], 'role': m[1], 'joined_at': m[2]} for m in members],
        'chats': [{'chat_id': c[0], 'title': c[1], 'chat_type': c[2],
                   'added_by': c[3], 'added_at': c[4]} for c in chats],
    }


def update_workspace_name(conn: sqlite3.Connection, workspace_id: int, new_name: str) -> None:
    conn.execute(
        "UPDATE workspaces SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (new_name, workspace_id)
    )
    conn.commit()


def add_bot_chat(conn: sqlite3.Connection, chat_id: int, workspace_id: int,
                 added_by: int, title: Optional[str], chat_type: Optional[str]) -> None:
    """Привязывает chat к workspace (upsert по chat_id)."""
    conn.execute('''
        INSERT INTO bot_chats (chat_id, workspace_id, added_by_user_id, title, chat_type, added_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id) DO UPDATE SET
          workspace_id=excluded.workspace_id,
          added_by_user_id=excluded.added_by_user_id,
          title=excluded.title,
          chat_type=excluded.chat_type
    ''', (chat_id, workspace_id, added_by, title, chat_type))
    conn.commit()


def get_workspace_by_chat(conn: sqlite3.Connection, chat_id: int) -> Optional[int]:
    """Возвращает workspace_id если chat привязан, иначе None."""
    row = conn.execute(
        'SELECT workspace_id FROM bot_chats WHERE chat_id=?', (chat_id,)
    ).fetchone()
    return row[0] if row else None
