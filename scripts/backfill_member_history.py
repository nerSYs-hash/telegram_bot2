#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Одноразовый backfill member_history из legacy-данных (виджет «Новые / Вернувшиеся»).

Источники: user_joins, users.joined_at, transactions.return_on_leave,
эвристика повторного входа по user_stats после выхода.

Запуск (сначала dry-run):
    python scripts/backfill_member_history.py --db database/bot_database.db --dry-run

Применить:
    python scripts/backfill_member_history.py --db database/bot_database.db

Прод (бот остановлен):
    python /root/PulsBot/scripts/backfill_member_history.py \\
        --db /root/PulsBot/economybot/database/bot_database.db
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from database.db_member_history import (  # noqa: E402
    apply_backfill_events,
    collect_backfill_events,
    count_new_returning,
    create_member_history,
)


class _DB:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cursor = conn.cursor()


def _backup(db_path: str) -> str:
    os.makedirs(os.path.join(PARENT, 'database', 'backups'), exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(PARENT, 'database', 'backups', f'pre_member_history_backfill_{stamp}.db')
    shutil.copy2(db_path, dest)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill member_history из старых данных')
    parser.add_argument('--db', default='database/bot_database.db', help='Путь к bot_database.db')
    parser.add_argument('--workspace-id', type=int, default=1, help='WS по умолчанию (если нет колонки)')
    parser.add_argument('--dry-run', action='store_true', help='Только отчёт, без INSERT')
    parser.add_argument('--no-backup', action='store_true', help='Не копировать БД перед записью')
    args = parser.parse_args()

    db_path = args.db if os.path.isabs(args.db) else os.path.join(PARENT, args.db)
    if not os.path.isfile(db_path):
        print(f'ERROR: файл не найден: {db_path}')
        return 1

    if not args.dry_run and not args.no_backup:
        backup = _backup(db_path)
        print(f'Backup: {backup}')

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    db = _DB(conn)
    create_member_history(db)

    before = db.cursor.execute('SELECT COUNT(*) FROM member_history').fetchone()[0]

    events = collect_backfill_events(db, default_workspace_id=args.workspace_id)
    by_source: dict[str, int] = {}
    for ev in events:
        by_source[ev['source']] = by_source.get(ev['source'], 0) + 1

    result = apply_backfill_events(db, events, dry_run=args.dry_run)

    after = db.cursor.execute('SELECT COUNT(*) FROM member_history').fetchone()[0]

    # Пример: последние 30 дней (как у виджета «месяц» — широкое окно)
    import time as _time
    end_ts = int(_time.time())
    start_ts = end_ts - 30 * 86400
    sample = count_new_returning(db, args.workspace_id, start_ts, end_ts)

    print('=' * 60)
    print('member_history backfill')
    print('=' * 60)
    print(f'DB:              {db_path}')
    print(f'Workspace:       {args.workspace_id}')
    print(f'Dry run:         {args.dry_run}')
    print(f'Rows before:     {before}')
    print(f'Rows after:      {after}')
    print(f'Events collected:{len(events)}')
    print('By source:', dict(sorted(by_source.items())))
    print('Result:', result)
    print(f'Sample new/returning (30d window): {sample}')
    print('=' * 60)

    conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
