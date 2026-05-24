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


# ── Default seed lists для нового workspace (V1.17.0k3) ───────────────────────
#
# Generic ws (is_pulse_themed=False) — пробный набор «без денежной механики»:
# что точно полезно любому новому владельцу любого чата сразу из коробки.
# Экономика/майнинг/BBS/донаты — opt-in: их владелец сам включает по мере
# готовности (тренируется на каталоге, не ловит сюрпризов).
DEFAULT_GENERIC_ENABLED = (
    "statistics", "top5", "triggers", "press_release", "journal",
)

# Pulse-themed ws (is_pulse_themed=True) — расширенный набор: исторически
# на ws=1 у Вити включены все эти модули (см. scripts/backfill_module_toggles_ws1.py).
# Сюда переезжаем как «канонический список Pulse-сообщества» — чтобы новый
# Pulse-владелец получал тот же опыт без отдельного backfill-прогона.
# NB: sprints/combos исключены — функционал майнинга есть, но эти подмодули
# в каталоге как отдельные тумблеры пока не enforce'ятся в боте (см. план 7.x).
DEFAULT_PULSE_ENABLED = (
    "statistics", "top5", "triggers", "press_release", "journal",
    "mining", "penalty", "lottery", "bingo", "monthly_gift", "referral",
    "bbs_bonus", "bbs_pulse", "bbs_other", "bbs_anketa", "bbs_vip",
    "shipper", "donations", "titles", "horoscope",
)


def seed_default_modules(
    conn: sqlite3.Connection,
    workspace_id: int,
    is_pulse_themed: bool = False,
    user_id: int = 0,
) -> int:
    """Включает дефолтный набор модулей для свежего workspace.

    Идемпотентна: повторный вызов не перезаписывает уже выставленные
    тумблеры (ON CONFLICT DO NOTHING). Это важно — owner мог явно
    выключить что-то после создания ws, повторный seed не должен это
    откатить (например, при повторном run create_workspace в тестах).

    Args:
        is_pulse_themed: True → расширенный набор (Pulse-фичи).
                         False → утилитарный набор (statistics/top5/triggers/...).
        user_id: автор записи в module_toggle_history; 0 = system/seed.

    Returns:
        Сколько модулей реально включено (новых строк в module_toggles).
    """
    targets = DEFAULT_PULSE_ENABLED if is_pulse_themed else DEFAULT_GENERIC_ENABLED
    # Фильтруем по каталогу: если какой-то id устарел/удалён — тихо пропускаем,
    # не падаем. Каталог = единственная правда (shared/modules_catalog.json).
    targets = [mid for mid in targets if mid in VALID_MODULE_IDS]

    inserted = 0
    for mid in targets:
        cur = conn.execute(
            '''INSERT INTO module_toggles (workspace_id, module_id, is_enabled, updated_by)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(workspace_id, module_id) DO NOTHING''',
            (workspace_id, mid, user_id),
        )
        if cur.rowcount:
            inserted += 1
            conn.execute(
                '''INSERT INTO module_toggle_history
                   (workspace_id, module_id, action, reason, changed_by)
                   VALUES (?, ?, 'enable', 'seed (new workspace defaults)', ?)''',
                (workspace_id, mid, user_id),
            )
    if inserted:
        _bump_cache_version(conn, workspace_id)
    conn.commit()
    return inserted


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
