"""
Миграция: исправление composite PK для 7 таблиц.
ID: 2026-05-13-composite-pk-fix
Spec: docs/superpowers/specs/2026-05-13-bot-connection-flow-design.md

После multi-tenancy миграции (V1.17.0a22) в этих таблицах PK/UNIQUE НЕ включают
workspace_id, поэтому два workspace не могут иметь одинаковые ключи. Фиксим
через rebuild-pattern (CREATE...AS SELECT, DROP, RENAME).
"""
import os
import shutil
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'bot_database.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')

REBUILT_TABLES = {
    'economy_settings':         ['workspace_id', 'key'],
    'economy_section_toggles':  ['workspace_id', 'category'],
    'branding_settings':        ['workspace_id', 'key'],
    'user_stats':               ['workspace_id', 'user_id', 'date'],
    'user_stats_hourly':        ['workspace_id', 'user_id', 'date', 'hour'],
    'chat_stats':               ['workspace_id', 'date'],
    'topics':                   ['workspace_id', 'chat_id', 'thread_id'],
}


_LITERAL_DEFAULTS = {'NULL', 'TRUE', 'FALSE',
                     'CURRENT_TIMESTAMP', 'CURRENT_DATE', 'CURRENT_TIME'}


def _quote_default(dflt: str) -> str:
    """SQLite требует expression DEFAULT-ы (типа datetime('now')) быть в скобках.
    Литералы (числа, строки в кавычках, NULL, CURRENT_TIMESTAMP) — без скобок.
    """
    s = str(dflt).strip()
    if s.upper() in _LITERAL_DEFAULTS:
        return s
    if s.startswith("'") or s.startswith('"'):
        return s
    # Number?
    try:
        float(s)
        return s
    except ValueError:
        pass
    # Expression — wrap
    if s.startswith('(') and s.endswith(')'):
        return s
    return f"({s})"


def backup_db(db_path: str = DB_PATH) -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(BACKUP_DIR, f'pre_composite_pk_{ts}.db')
    shutil.copy2(db_path, dest)
    return dest


def _rebuild_table(conn: sqlite3.Connection, tbl: str, pk_cols: list) -> None:
    """Пересоздаёт таблицу с composite PK через CREATE...INSERT...DROP...RENAME."""
    cols_info = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
    if not cols_info:
        print(f'[skip] {tbl}: table does not exist')
        return
    # Already has composite PK?
    current_pk = sorted([r[1] for r in cols_info if r[5] > 0])
    if current_pk == sorted(pk_cols):
        print(f'[skip] {tbl}: already has composite PK {pk_cols}')
        return

    col_defs = []
    col_names = []
    for cid, name, ctype, notnull, dflt, pk in cols_info:
        d = f"{name} {ctype}"
        if notnull:
            d += " NOT NULL"
        if dflt is not None:
            d += f" DEFAULT {_quote_default(dflt)}"
        col_defs.append(d)
        col_names.append(name)
    col_defs.append(f"PRIMARY KEY ({', '.join(pk_cols)})")
    cols_csv = ', '.join(col_names)
    conn.execute(f"DROP TABLE IF EXISTS {tbl}__new")
    conn.execute(f"CREATE TABLE {tbl}__new ({', '.join(col_defs)})")
    conn.execute(f"INSERT INTO {tbl}__new ({cols_csv}) SELECT {cols_csv} FROM {tbl}")
    conn.execute(f"DROP TABLE {tbl}")
    conn.execute(f"ALTER TABLE {tbl}__new RENAME TO {tbl}")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_workspace ON {tbl}(workspace_id)")
    print(f'[ok] rebuilt {tbl} with PK {pk_cols}')


def migrate_up(db_path: str = DB_PATH) -> str:
    backup = backup_db(db_path)
    print(f'[backup] {backup}')
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        for tbl, pk_cols in REBUILT_TABLES.items():
            _rebuild_table(conn, tbl, pk_cols)
        conn.commit()
    finally:
        conn.close()
    print('[done] composite_pk_fix migrate_up complete')
    return backup


def _restore_single_pk(conn: sqlite3.Connection, tbl: str, single_pk: str) -> None:
    """Откат: пересоздать таблицу с одиночным PK (как было до)."""
    cols_info = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
    if not cols_info:
        return
    col_defs = []
    col_names = []
    for cid, name, ctype, notnull, dflt, pk in cols_info:
        d = f"{name} {ctype}"
        if name == single_pk:
            d += " PRIMARY KEY"
        elif notnull:
            d += " NOT NULL"
        if dflt is not None and name != single_pk:
            d += f" DEFAULT {_quote_default(dflt)}"
        col_defs.append(d)
        col_names.append(name)
    cols_csv = ', '.join(col_names)
    conn.execute(f"DROP TABLE IF EXISTS {tbl}__old")
    conn.execute(f"CREATE TABLE {tbl}__old ({', '.join(col_defs)})")
    conn.execute(f"INSERT INTO {tbl}__old ({cols_csv}) SELECT {cols_csv} FROM {tbl}")
    conn.execute(f"DROP TABLE {tbl}")
    conn.execute(f"ALTER TABLE {tbl}__old RENAME TO {tbl}")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_workspace ON {tbl}(workspace_id)")


_ORIGINAL_PK = {
    'economy_settings':        'key',
    'economy_section_toggles': 'category',
    'branding_settings':       'key',
}


def migrate_down(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        for tbl, single_pk in _ORIGINAL_PK.items():
            _restore_single_pk(conn, tbl, single_pk)
        # user_stats/chat_stats/topics/user_stats_hourly — оригинально без PK, только UNIQUE.
        # Пересоздать без PRIMARY KEY clause.
        for tbl in ('user_stats', 'user_stats_hourly', 'chat_stats', 'topics'):
            cols_info = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
            if not cols_info:
                continue
            col_defs = []
            col_names = []
            for cid, name, ctype, notnull, dflt, pk in cols_info:
                d = f"{name} {ctype}"
                if notnull and name != 'workspace_id':
                    d += " NOT NULL"
                if dflt is not None:
                    d += f" DEFAULT {dflt}"
                col_defs.append(d)
                col_names.append(name)
            cols_csv = ', '.join(col_names)
            conn.execute(f"DROP TABLE IF EXISTS {tbl}__old")
            conn.execute(f"CREATE TABLE {tbl}__old ({', '.join(col_defs)})")
            conn.execute(f"INSERT INTO {tbl}__old ({cols_csv}) SELECT {cols_csv} FROM {tbl}")
            conn.execute(f"DROP TABLE {tbl}")
            conn.execute(f"ALTER TABLE {tbl}__old RENAME TO {tbl}")
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_workspace ON {tbl}(workspace_id)")
        conn.commit()
    finally:
        conn.close()
    print('[done] composite_pk_fix migrate_down complete')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'down':
        migrate_down()
    else:
        migrate_up()
