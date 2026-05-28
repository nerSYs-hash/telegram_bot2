"""Group 2 блокера: миграции multi-tenancy + сид PositivЭ ws=1.

Назначение: довести single-tenant prod-БД (32 таблицы) до состояния multi-tenant,
готового к подключению второго workspace. Проходит цепочкой все существующие
миграции в правильном порядке и сидит PositivЭ как ws=1.

Шаги:
  0. Бэкап исходной БД в database/backups/pre_group2_*.db
  1. init_press_release_tables  → создаёт bot_chats + bot_chat_topics + пресс-релиз таблицы
  2. multi_tenancy.migrate_up   → workspaces, workspace_members, +workspace_id во все TENANTED_TABLES, сидит ws=1
  3. bot_chats_extend           → 4 onboarding-колонки в bot_chats
  4. V1_17_0c1_add_chat_role    → bot_chats.role + type nullable
  5. add_removed_at_to_bot_chats (idempotent, для совместимости)
  6. add_icon_columns_to_workspaces
  7. ws_runtime_seed.up_add_kind_column → bot_chat_topics.kind
  8. composite_pk_fix.migrate_up → composite PK для user_stats / chat_stats / economy_*
  9. module_toggles.up           → module_toggles, module_toggle_history, *_cache_version
 10. СИД PositivЭ:
       UPDATE workspaces SET name='PositivЭ', is_pulse_themed=0 WHERE id=1
       INSERT bot_chats: -1003516353279 (main), -1003956360865 (admin), -1003930021144 (journal)
       seed_default_modules для ws=1 (basic-набор, т.к. is_pulse_themed=0)
 11. VERIFY: распечатать workspaces, members, bot_chats, module_toggles, ws-распределение user_stats

Запуск (локально на копии prod-БД):
    python scripts/group2_seed_positiv_workspace.py --db database/backups/prod_bot_database_*.db

Запуск на проде (после restart pulsbot.service stop):
    python /root/PulsBot/scripts/group2_seed_positiv_workspace.py \\
        --db /root/PulsBot/economybot/database/bot_database.db

Идемпотентен: все шаги повторно безопасны.
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime


PARENT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PARENT_PATH not in sys.path:
    sys.path.insert(0, PARENT_PATH)


# ── PositivЭ constants ──
OWNER_USER_ID = 7536752126
WS_NAME = 'PositivЭ'
IS_PULSE_THEMED = False
MAIN_CHAT_ID = -1003516353279
ADMIN_CHAT_ID = -1003956360865
JOURNAL_CHAT_ID = -1003930021144


class _DbLike:
    """Минимальная обёртка над connection чтобы передавать в db_migrations.* и
    init_press_release_tables (они ждут db.cursor / db.conn)."""
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()
        self.cursor.row_factory = sqlite3.Row


def step_backup(db_path):
    backup_dir = os.path.join(os.path.dirname(db_path) or '.', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(backup_dir, f'pre_group2_{os.path.basename(db_path)}_{ts}.db')
    shutil.copy2(db_path, dest)
    return dest


def step_init_press_release(db_path):
    from database import db_press_release as dpr
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        db = _DbLike(conn)
        dpr.init_press_release_tables(db)
        conn.commit()
    finally:
        conn.close()


def step_multi_tenancy(db_path):
    from database.migrations import multi_tenancy as mt
    mt.migrate_up(db_path, owner_user_id=OWNER_USER_ID)


def step_bot_chats_extend(db_path):
    from database.migrations import bot_chats_extend as bce
    bce.migrate_up(db_path)


def step_v1_17_0c1(db_path):
    from scripts import V1_17_0c1_add_chat_role as v17c1
    v17c1.main(db_path)


def step_removed_at_icon_kind(db_path):
    from database import db_migrations as dbm
    from database.migrations import ws_runtime_seed as wsrt
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        db = _DbLike(conn)
        dbm.add_removed_at_to_bot_chats(db)
        dbm.add_icon_columns_to_workspaces(db)
        wsrt.up_add_kind_column(conn)
        conn.commit()
    finally:
        conn.close()


def step_composite_pk(db_path):
    from database.migrations import composite_pk_fix as cpf
    cpf.migrate_up(db_path)


def step_module_toggles(db_path):
    from database.migrations import module_toggles as mtog
    conn = sqlite3.connect(db_path)
    try:
        mtog.up(conn)
        conn.commit()
    finally:
        conn.close()


def step_seed_positiv(db_path):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE workspaces SET name=?, is_pulse_themed=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=1",
            (WS_NAME, 1 if IS_PULSE_THEMED else 0)
        )
        print(f'[seed] workspaces.id=1 -> name="{WS_NAME}" is_pulse_themed={int(IS_PULSE_THEMED)} '
              f'(rowcount={cur.rowcount})')

        # owner member
        cur.execute(
            "INSERT OR REPLACE INTO workspace_members(workspace_id, user_id, role) "
            "VALUES (1, ?, 'owner')", (OWNER_USER_ID,)
        )
        print(f'[seed] workspace_members owner={OWNER_USER_ID}')

        # 3 чата
        for cid, role, title in [
            (MAIN_CHAT_ID,    'main',    'PositivЭ (main)'),
            (ADMIN_CHAT_ID,   'admin',   'PositivЭ (admin)'),
            (JOURNAL_CHAT_ID, 'journal', 'PositivЭ (journal)'),
        ]:
            cur.execute('''
                INSERT INTO bot_chats(chat_id, type, title, workspace_id, role,
                                      added_by_user_id, chat_type, added_at, last_seen_at)
                VALUES (?, 'supergroup', ?, 1, ?, ?, 'supergroup',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                  workspace_id=excluded.workspace_id,
                  role=excluded.role,
                  title=COALESCE(bot_chats.title, excluded.title),
                  removed_at=NULL
            ''', (cid, title, role, OWNER_USER_ID))
            print(f'[seed] bot_chats {cid} role={role}')
        conn.commit()

        # default modules (basic, т.к. is_pulse_themed=False)
        try:
            from database.db_module_toggles import seed_default_modules
            seed_default_modules(conn, 1, is_pulse_themed=IS_PULSE_THEMED, user_id=OWNER_USER_ID)
            print('[seed] default modules (basic set)')
        except Exception as e:
            print(f'[warn] seed_default_modules: {e}')
    finally:
        conn.close()


def step_verify(db_path):
    print('\n=== VERIFY ===')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        print('\nworkspaces:')
        for r in conn.execute('SELECT id, name, owner_user_id, is_pulse_themed, plan FROM workspaces'):
            print(' ', dict(r))

        print('\nworkspace_members:')
        for r in conn.execute('SELECT workspace_id, user_id, role FROM workspace_members'):
            print(' ', dict(r))

        print('\nbot_chats:')
        for r in conn.execute('SELECT chat_id, workspace_id, role, title, removed_at FROM bot_chats'):
            print(' ', dict(r))

        print('\nmodule_toggles per ws:')
        for r in conn.execute(
            'SELECT workspace_id, COUNT(*) AS modules, '
            'SUM(is_enabled) AS enabled FROM module_toggles GROUP BY workspace_id'
        ):
            print(' ', dict(r))

        print('\nworkspace_id distribution sample (user_stats):')
        try:
            for r in conn.execute(
                'SELECT workspace_id, COUNT(*) AS rows FROM user_stats '
                'GROUP BY workspace_id ORDER BY workspace_id'
            ):
                print(' ', dict(r))
        except sqlite3.OperationalError as e:
            print(' ', f'(skip: {e})')

        print('\nbot_chats schema:')
        for r in conn.execute('PRAGMA table_info(bot_chats)').fetchall():
            print(' ', tuple(r))
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True, help='path to bot_database.db')
    ap.add_argument('--no-verify', action='store_true')
    ap.add_argument('--skip-backup', action='store_true',
                    help='пропустить шаг 0 (например если копия уже сделана scp)')
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f'[fail] db not found: {args.db}')
        sys.exit(1)
    print(f'[*] target db: {args.db}')

    if not args.skip_backup:
        backup = step_backup(args.db)
        print(f'[backup] {backup}')
    else:
        print('[skip] step 0 backup (--skip-backup)')

    print('\n=== STEP 1: init_press_release_tables (bot_chats / bot_chat_topics) ===')
    step_init_press_release(args.db)

    print('\n=== STEP 2: multi_tenancy.migrate_up (workspaces + workspace_id) ===')
    step_multi_tenancy(args.db)

    print('\n=== STEP 3: bot_chats_extend (4 onboarding-колонки) ===')
    step_bot_chats_extend(args.db)

    print('\n=== STEP 4: V1.17.0c1 add_chat_role (bot_chats.role + type nullable) ===')
    step_v1_17_0c1(args.db)

    print('\n=== STEP 5/6/7: removed_at + icon columns + bot_chat_topics.kind ===')
    step_removed_at_icon_kind(args.db)

    print('\n=== STEP 8: composite_pk_fix ===')
    step_composite_pk(args.db)

    print('\n=== STEP 9: module_toggles ===')
    step_module_toggles(args.db)

    print('\n=== STEP 10: seed PositivЭ ===')
    step_seed_positiv(args.db)

    if not args.no_verify:
        step_verify(args.db)


if __name__ == '__main__':
    main()
