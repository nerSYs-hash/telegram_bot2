"""CRUD для module_toggles + history + cache_version.

Используется и api/modules_routes.py (через web), и bot_core/module_guard.py
(через прямой импорт). Единый источник списка модулей — shared/modules_catalog.json.
"""
import json
import sqlite3
from pathlib import Path
from typing import List, Optional

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "shared" / "modules_catalog.json"
_CATALOG = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
VALID_MODULE_IDS = {m["id"] for m in _CATALOG["modules"]}
_MODULE_META = {m["id"]: m for m in _CATALOG["modules"]}


def _validate_module_id(module_id: str) -> None:
    if module_id not in VALID_MODULE_IDS:
        raise ValueError(f"Unknown module_id: {module_id}")


def is_module_enabled(conn: sqlite3.Connection, workspace_id: int, module_id: str) -> bool:
    _validate_module_id(module_id)
    row = conn.execute(
        "SELECT is_enabled FROM module_toggles WHERE workspace_id=? AND module_id=?",
        (workspace_id, module_id),
    ).fetchone()
    return bool(row and row[0])


def set_module_state(
    conn: sqlite3.Connection,
    workspace_id: int,
    module_id: str,
    is_enabled: bool,
    reason: Optional[str],
    user_id: int,
) -> None:
    _validate_module_id(module_id)
    if not is_enabled and not (reason and reason.strip()):
        raise ValueError("reason required when disabling a module")
    conn.execute(
        '''INSERT INTO module_toggles (workspace_id, module_id, is_enabled, updated_by, updated_at)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(workspace_id, module_id) DO UPDATE SET
               is_enabled=excluded.is_enabled,
               updated_by=excluded.updated_by,
               updated_at=CURRENT_TIMESTAMP''',
        (workspace_id, module_id, 1 if is_enabled else 0, user_id),
    )
    conn.execute(
        '''INSERT INTO module_toggle_history (workspace_id, module_id, action, reason, changed_by)
           VALUES (?, ?, ?, ?, ?)''',
        (workspace_id, module_id, "enable" if is_enabled else "disable", reason, user_id),
    )
    _bump_cache_version(conn, workspace_id)
    conn.commit()


def get_modules(conn: sqlite3.Connection, workspace_id: int) -> List[dict]:
    rows = conn.execute(
        "SELECT module_id, is_enabled, updated_at, updated_by "
        "FROM module_toggles WHERE workspace_id=?",
        (workspace_id,),
    ).fetchall()
    state = {r[0]: {"is_enabled": bool(r[1]), "updated_at": r[2], "updated_by": r[3]} for r in rows}
    result = []
    for m in _CATALOG["modules"]:
        s = state.get(m["id"], {"is_enabled": False, "updated_at": None, "updated_by": None})
        result.append({
            "id": m["id"], "name": m["name"], "section": m["section"],
            "description": m["description"], **s,
        })
    return result


def list_history(
    conn: sqlite3.Connection,
    workspace_id: int,
    module_id: str,
    limit: int = 20,
) -> List[dict]:
    _validate_module_id(module_id)
    rows = conn.execute(
        '''SELECT action, reason, changed_by, changed_at
           FROM module_toggle_history
           WHERE workspace_id=? AND module_id=?
           ORDER BY changed_at DESC, id DESC LIMIT ?''',
        (workspace_id, module_id, limit),
    ).fetchall()
    return [
        {"action": r[0], "reason": r[1], "changed_by": r[2], "changed_at": r[3]}
        for r in rows
    ]


def get_cache_version(conn: sqlite3.Connection, workspace_id: int) -> int:
    row = conn.execute(
        "SELECT version FROM module_toggle_cache_version WHERE workspace_id=?",
        (workspace_id,),
    ).fetchone()
    return row[0] if row else 0


def _bump_cache_version(conn: sqlite3.Connection, workspace_id: int) -> None:
    conn.execute(
        '''INSERT INTO module_toggle_cache_version (workspace_id, version)
           VALUES (?, 1)
           ON CONFLICT(workspace_id) DO UPDATE SET version = version + 1''',
        (workspace_id,),
    )
