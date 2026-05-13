"""Smoke-check: миграция multi-tenancy применена к live БД."""
import sqlite3, sys, os

DB = os.path.join(os.path.dirname(__file__), '..', 'database', 'bot_database.db')
c = sqlite3.connect(DB)

try:
    ws = c.execute('SELECT id, name, is_pulse_themed, plan FROM workspaces').fetchall()
    print('workspaces:', ws)
    if not ws:
        print('[FAIL] no workspaces — миграция up не применена')
        sys.exit(1)
    members = c.execute('SELECT workspace_id, user_id, role FROM workspace_members').fetchall()
    print('members:', members)

    # Sample tenanted tables
    for tbl in ('economy_settings', 'transactions', 'users', 'bbs_profiles',
                'journal_messages', 'reactor', 'titles'):
        try:
            row = c.execute(
                f"SELECT COUNT(*) FROM {tbl}"
            ).fetchone()
            cols = [r[1] for r in c.execute(f"PRAGMA table_info({tbl})").fetchall()]
            has_ws = 'workspace_id' in cols
            print(f'  {tbl}: rows={row[0]} workspace_id={"YES" if has_ws else "NO"}')
        except sqlite3.OperationalError as e:
            print(f'  {tbl}: table missing ({e})')
    print('[OK] migration state looks good')
except Exception as e:
    print(f'[FAIL] {e}')
    sys.exit(1)
finally:
    c.close()
