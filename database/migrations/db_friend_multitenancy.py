"""V1.17.0O1 [Этап B B1]: миграция pulse_bot.db (db_friend) на multi-tenant.

Добавляет колонку `workspace_id INTEGER NOT NULL DEFAULT 1` ко всем таблицам
которые исторически создавались без неё. Idempotent — повторный запуск
безопасен (PRAGMA-проверка).

Применяется при старте бота из bot.py / handlers/db_friend.init_db.
На проде уже применён вручную 28.05.2026 ~17:43 (бэкап pre_stage_b_20260528_174323).

Pulse-safe: все существующие данные → workspace_id=1 (Pulse Москва → PositivЭ).
Pulse и PositivЭ это один ws=1, изоляция в Этапе B даёт фундамент для второго ws.

См. [[blocker_before_new_ws_2026_05_28]] и docs/ROADMAP_full_isolation_2026-05-28.md
этап B.
"""
from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

TABLES_NEEDING_WS = (
    'users',
    'applications',
    'admins',
    'invite_links',
    'blacklist',
    'journal_messages',
    'referral_transactions',
    'survey_results',
    'violations',
    'settings',
    'application_messages',
)


def _has_workspace_id(conn: sqlite3.Connection, table: str) -> bool:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return 'workspace_id' in cols


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def migrate_db_friend_to_multitenant(db_path: str = 'pulse_bot.db') -> int:
    """Применяет миграцию. Возвращает кол-во таблиц где была добавлена колонка."""
    added = 0
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        conn.execute("BEGIN IMMEDIATE")
        for table in TABLES_NEEDING_WS:
            if not _table_exists(conn, table):
                continue
            if _has_workspace_id(conn, table):
                continue
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN workspace_id INTEGER NOT NULL DEFAULT 1"
                )
                added += 1
                logger.info(
                    f"[db_friend MT] добавлен workspace_id в {table} "
                    f"(DEFAULT 1, существующие → ws=1)"
                )
            except sqlite3.OperationalError as e:
                logger.debug(f"[db_friend MT] {table}: {e}")
        conn.execute("COMMIT")
        conn.close()
        if added == 0:
            logger.info("[db_friend MT] миграция не требуется (все таблицы уже OK)")
        else:
            logger.info(f"[db_friend MT] миграция применена к {added} таблицам")
    except Exception as e:
        logger.error(f"[db_friend MT] ошибка миграции: {e}")
    return added


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--db', default='pulse_bot.db', help='Путь к pulse_bot.db')
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    n = migrate_db_friend_to_multitenant(args.db)
    print(f"Готово: добавлено в {n} таблиц.")
