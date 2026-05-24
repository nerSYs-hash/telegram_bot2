"""V1.17.0k2: миграция combo_claims/sprint_claims с разных workspace в один.

Назначение
==========
Артефакт connect-flow: один логический Pulse оказался размазан по нескольким
workspace_id (1/5/6 на проде по состоянию на 17.05). После C7-консолидации
ws-сирот (`consolidate_workspaces.py`) bot_chats и members перевязаны в ws1,
а combo_claims/sprint_claims остались с workspace_id источника — потому что
их не было в `TENANT_TABLES`. Этот скрипт переводит их в целевой ws.

PK-конфликты
============
- combo_claims PK: (user_id, combo_name) — дневной квест.
- sprint_claims PK: (user_id, sprint_name, window_key) — окно (1/12/24 ч).

Если на целевом ws уже есть строка с тем же PK — оставляем ту, у которой
свежее `claimed_at` (квест выдаётся за день/окно, не суммируется). Это
сохраняет идемпотентность повторного запуска: при apply на уже-чистой БД
ничего не происходит.

Usage
=====
  python -m scripts.migrate_combo_sprint_workspaces \
      --db database/bot_database.db --from 5,6 --into 1            # dry-run
  python -m scripts.migrate_combo_sprint_workspaces \
      --db database/bot_database.db --from 5,6 --into 1 --apply    # выполнить

Бэкап делается автоматически перед --apply (как в consolidate_workspaces).
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime


# (table, conflict-key columns, "newer wins" column)
CLAIM_TABLES = (
    ('combo_claims',  ('user_id', 'combo_name'),              'claimed_at'),
    ('sprint_claims', ('user_id', 'sprint_name', 'window_key'), 'claimed_at'),
)


def _count(conn, table, ws_id):
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE workspace_id=?", (ws_id,)
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def _plan(conn, from_ids, into_id):
    """Считает что куда поедет. Возвращает список:
        (table, src_ws, total_src, conflicts, fresh_moves)
    где conflicts — сколько строк дубликат-PK на into_id, fresh_moves —
    чистый UPDATE без конфликта."""
    rows = []
    for tbl, pk_cols, _ in CLAIM_TABLES:
        for src in from_ids:
            total = _count(conn, tbl, src)
            if total == 0:
                rows.append((tbl, src, 0, 0, 0))
                continue
            pk_join = ' AND '.join(f's.{c}=t.{c}' for c in pk_cols)
            conflicts = conn.execute(
                f"SELECT COUNT(*) FROM {tbl} s JOIN {tbl} t ON {pk_join} "
                f"WHERE s.workspace_id=? AND t.workspace_id=?",
                (src, into_id),
            ).fetchone()[0]
            fresh = total - conflicts
            rows.append((tbl, src, total, conflicts, fresh))
    return rows


def _apply(conn, from_ids, into_id):
    """Выполняет миграцию в одной транзакции. PK-конфликты резолвятся
    через DELETE «старшей» строки (по claimed_at), затем UPDATE
    workspace_id у источника."""
    conn.execute('BEGIN')
    try:
        for tbl, pk_cols, recency in CLAIM_TABLES:
            for src in from_ids:
                if src == into_id:
                    continue
                pk_join = ' AND '.join(f's.{c}=t.{c}' for c in pk_cols)
                # 1) среди конфликтов удалить ту строку, что старее
                conn.execute(
                    f"DELETE FROM {tbl} WHERE rowid IN ("
                    f"  SELECT CASE WHEN s.{recency} >= t.{recency} "
                    f"              THEN t.rowid ELSE s.rowid END "
                    f"  FROM {tbl} s JOIN {tbl} t ON {pk_join} "
                    f"  WHERE s.workspace_id=? AND t.workspace_id=?"
                    f")",
                    (src, into_id),
                )
                # 2) то, что осталось на src — переводим в into
                conn.execute(
                    f"UPDATE {tbl} SET workspace_id=? WHERE workspace_id=?",
                    (into_id, src),
                )
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise


def _backup(db_path):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = f'{db_path}.pre_combo_sprint_migrate_{ts}'
    shutil.copy2(db_path, dest)
    print(f'[backup] {dest}')
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--from', dest='from_ids', required=True,
                    help='workspace_id источников через запятую, напр. 5,6')
    ap.add_argument('--into', dest='into_id', type=int, required=True,
                    help='workspace_id назначения (обычно 1 = Pulse)')
    ap.add_argument('--apply', action='store_true',
                    help='Выполнить миграцию (по умолчанию dry-run).')
    a = ap.parse_args(argv)

    from_ids = [int(x) for x in a.from_ids.split(',') if x.strip()]
    if a.into_id in from_ids:
        print(f'[error] --into={a.into_id} не должен быть в --from', file=sys.stderr)
        return 2

    if a.apply:
        _backup(a.db)
    conn = sqlite3.connect(a.db)

    rows = _plan(conn, from_ids, a.into_id)
    print(f'Migration plan: ws from {from_ids} -> ws {a.into_id}')
    print(f'{"Table":<16}{"From":>6}{"Rows":>8}{"Conflicts":>12}{"Fresh moves":>14}')
    grand_total = grand_conf = grand_fresh = 0
    for tbl, src, total, conf, fresh in rows:
        print(f'{tbl:<16}{src:>6}{total:>8}{conf:>12}{fresh:>14}')
        grand_total += total
        grand_conf += conf
        grand_fresh += fresh
    print(f'{"TOTAL":<16}{"":>6}{grand_total:>8}{grand_conf:>12}{grand_fresh:>14}')

    if grand_total == 0:
        print('[no-op] нечего переносить')
        return 0
    if not a.apply:
        print('[dry-run] изменения НЕ применены; добавь --apply')
        return 0

    _apply(conn, from_ids, a.into_id)
    print(f'[done] перенесено: {grand_fresh} строк (resolved {grand_conf} конфликтов)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
