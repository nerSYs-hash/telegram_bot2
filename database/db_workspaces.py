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
