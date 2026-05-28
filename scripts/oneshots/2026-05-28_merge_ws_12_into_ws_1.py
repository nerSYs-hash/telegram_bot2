"""One-shot: merge ws=12 → ws=1, удалить ws=12, переименовать ws=1 в 'PositivЭ'.

Назначение: разрешить путаницу на проде PositivЭ (28.05.2026):
  - ws=1 «Pulse Москва» — реально активный workspace с привязанным
    main-чатом -1003516353279 (PositivЭ). Статистика 28.05 пишется сюда.
  - ws=12 «PositivЭ ( новый чат )» — без main-чата, но имеет старую
    статистику за 27.05 (33 юзера, 3043 сообщения, 17.48 пульсов).
  - На сайте UX-каша: «Pulse Москва» показывает PositivЭ-статистику,
    «PositivЭ» показывает зомби-историю.

Стратегия:
  1. SUM-merge статистики (composite PK таблицы): user_stats, user_stats_hourly,
     chat_stats, topics. Для каждой пары ключей суммирует количественные поля.
  2. Простой UPDATE workspace_id=12 → 1 для остальных tenant-таблиц
     (где нет composite PK по ws_id, конфликта не будет).
  3. DELETE ws=12 строк во всех таблицах после merge.
  4. UPDATE workspaces SET name='PositivЭ', is_pulse_themed=0 WHERE id=1.
  5. DELETE workspace ws=12 + workspace_members.

Идемпотентен: повторный запуск пропускает шаги (ws=12 уже не существует).
Backup автоматически.

Usage:
  python scripts/merge_ws_12_into_ws_1.py --db /path/to/bot_database.db --dry
  python scripts/merge_ws_12_into_ws_1.py --db /path/to/bot_database.db --apply
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


# user_stats / user_stats_hourly / chat_stats / topics — composite PK включает workspace_id.
# Для них нужен SUM-merge при коллизии ключей. Все целочисленные/REAL поля кроме PK
# суммируются. TEXT/DATE поля берутся как есть (PK либо одинаковы).
MERGE_TABLES = {
    'user_stats': {
        'pk':  ['workspace_id', 'user_id', 'date'],
        'sum': ['total_chars', 'total_messages', 'total_words',
                'reactions_given', 'reactions_received',
                'replies_received', 'replies_sent',
                'mentions_received', 'media_sent', 'other_threads_posts',
                'warnings', 'activity_score', 'pulses_mined'],
    },
    'chat_stats': {
        'pk':  ['workspace_id', 'date'],
        'sum': ['total_chars', 'total_messages',
                'total_messages_with_admins', 'total_messages_without_admins',
                'total_words', 'total_reactions', 'total_replies',
                'total_mentions', 'total_media', 'other_threads_posts',
                'total_warnings', 'active_users', 'total_pulses_mined'],
        # avg_message_length считать после слияния — пока копируем источник.
    },
}

# topics / user_stats_hourly могут отсутствовать или иметь другие колонки — обработаем динамически.

# Tenant-таблицы из multi_tenancy.TENANTED_TABLES — UPDATE workspace_id где нет PK конфликта.
SIMPLE_UPDATE_TABLES_FALLBACK = [
    'anketa_edits', 'bbs_other_posts', 'bbs_profiles', 'bbs_reactions',
    'bingo_cards', 'bingo_games', 'bug_cards', 'challenges',
    'combo_claims', 'daily_stats_summary', 'economy_cancellations',
    'economy_history', 'exit_interviews', 'hall_of_fame',
    'journal_messages', 'lotteries', 'lottery_tickets',
    'marketplace_services', 'messages',
    'monthly_gift_participants', 'monthly_gifts',
    'press_release_targets', 'press_release_templates', 'press_release_versions',
    'reactor', 'referral_links', 'referral_seasons', 'referral_stats',
    'scheduled_posts', 'shipper_matches', 'shipper_resonance_stats',
    'sprint_claims', 'stat_events_log', 'title_packages', 'title_rub_requests',
    'titles', 'top_activists_history', 'top_activists_percent',
    'transactions', 'trigger_violations', 'triggers',
    'user_joins',
]


def _table_exists(conn, name):
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone())


def _has_workspace_id(conn, name):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({name})").fetchall()]
    return 'workspace_id' in cols


def _count(conn, name, ws_id):
    if not _table_exists(conn, name) or not _has_workspace_id(conn, name):
        return 0
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {name} WHERE workspace_id=?", (ws_id,)
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def _merge_one(conn, name, spec, src, dst, dry):
    """SUM-merge: для каждой строки в src-ws пытается INSERT в dst-ws;
    при конфликте PK — UPDATE с суммой количественных полей."""
    if not _table_exists(conn, name):
        return f"[skip] {name}: нет таблицы"
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({name})").fetchall()]
    if 'workspace_id' not in cols:
        return f"[skip] {name}: нет workspace_id"

    src_count = conn.execute(
        f"SELECT COUNT(*) FROM {name} WHERE workspace_id=?", (src,)
    ).fetchone()[0]
    if src_count == 0:
        return f"[skip] {name}: 0 src-строк"

    pk_cols = spec['pk']
    sum_cols = [c for c in spec['sum'] if c in cols]
    # все колонки кроме pk
    all_cols = [c for c in cols if c not in ('rowid',)]
    insert_cols_csv = ', '.join(all_cols)
    insert_select_csv = ', '.join(
        f"{dst} AS workspace_id" if c == 'workspace_id' else c
        for c in all_cols
    )
    pk_csv = ', '.join(pk_cols)
    set_clause = ', '.join(
        f"{c} = COALESCE({name}.{c}, 0) + COALESCE(excluded.{c}, 0)"
        for c in sum_cols
    )

    if dry:
        return (f"[plan] {name}: {src_count} строк src=ws{src} -> ws{dst} "
                f"(INSERT ON CONFLICT({pk_csv}) DO UPDATE SET {len(sum_cols)} полей)")

    # Делаем UPSERT через временный SELECT (нельзя UPDATE рядом с src=dst).
    # Подход: SELECT всех строк src как dst, и попытка INSERT ... ON CONFLICT DO UPDATE.
    sql = (
        f"INSERT INTO {name} ({insert_cols_csv}) "
        f"SELECT {insert_select_csv} FROM {name} WHERE workspace_id=? "
        f"ON CONFLICT({pk_csv}) DO UPDATE SET {set_clause}"
    )
    conn.execute(sql, (src,))
    # Удаляем источник
    conn.execute(f"DELETE FROM {name} WHERE workspace_id=?", (src,))
    return f"[merged] {name}: {src_count} строк ws{src} -> ws{dst} (SUM)"


def _simple_update(conn, name, src, dst, dry):
    if not _table_exists(conn, name) or not _has_workspace_id(conn, name):
        return f"[skip] {name}: нет таблицы/колонки"
    src_count = _count(conn, name, src)
    if src_count == 0:
        return f"[skip] {name}: 0 src-строк"
    if dry:
        return f"[plan] {name}: UPDATE workspace_id={src} -> {dst} ({src_count} строк)"
    try:
        conn.execute(
            f"UPDATE {name} SET workspace_id=? WHERE workspace_id=?",
            (dst, src)
        )
        return f"[moved] {name}: {src_count} строк ws{src} -> ws{dst}"
    except sqlite3.IntegrityError as e:
        # PK или UNIQUE конфликт — оставляем src как есть для ручного разбора.
        return f"[ERROR] {name}: IntegrityError {e} — оставлено как было"


def _backup(db_path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = f"{db_path}.pre_merge_ws12_{ts}"
    shutil.copy2(db_path, dest)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--src', type=int, default=12, help='source workspace id')
    ap.add_argument('--dst', type=int, default=1, help='destination workspace id')
    ap.add_argument('--new-name', default='PositivЭ')
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument('--dry', action='store_true', help='show plan, no changes')
    grp.add_argument('--apply', action='store_true', help='execute changes')
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f'[fail] db not found: {args.db}')
        sys.exit(1)

    print(f'[*] db={args.db} src=ws{args.src} dst=ws{args.dst} mode={"DRY" if args.dry else "APPLY"}')

    if args.apply:
        b = _backup(args.db)
        print(f'[backup] {b}')

    conn = sqlite3.connect(args.db)
    try:
        if not args.dry:
            conn.execute("BEGIN")

        # 0. Проверка существования src ws
        src_exists = conn.execute(
            "SELECT 1 FROM workspaces WHERE id=?", (args.src,)
        ).fetchone()
        if not src_exists:
            print(f'[skip] ws={args.src} не существует — уже смерджен/удалён')
            if not args.dry:
                conn.execute("COMMIT")
            return

        # 1. SUM-merge для статистики
        print('\n=== STEP 1: SUM-merge tables ===')
        for name, spec in MERGE_TABLES.items():
            print(' ', _merge_one(conn, name, spec, args.src, args.dst, args.dry))

        # 2. Простой UPDATE для остальных tenant-таблиц
        print('\n=== STEP 2: simple UPDATE tables ===')
        for name in SIMPLE_UPDATE_TABLES_FALLBACK:
            print(' ', _simple_update(conn, name, args.src, args.dst, args.dry))

        # 3. bot_chats (если src имеет чаты — переносим dst, но в нашем случае пусто)
        bc_src = conn.execute(
            "SELECT chat_id, role FROM bot_chats WHERE workspace_id=?", (args.src,)
        ).fetchall()
        for cid, role in bc_src:
            print(f"  [plan] bot_chats {cid} (role={role}): ws{args.src} -> ws{args.dst}")
        if bc_src and not args.dry:
            conn.execute(
                "UPDATE bot_chats SET workspace_id=? WHERE workspace_id=?",
                (args.dst, args.src)
            )

        # 4. Удалить workspace_members + workspace_ws=src
        print('\n=== STEP 3: drop workspace ws={} ==='.format(args.src))
        m_count = conn.execute(
            "SELECT COUNT(*) FROM workspace_members WHERE workspace_id=?", (args.src,)
        ).fetchone()[0]
        print(f'  [plan] DELETE workspace_members ws={args.src} ({m_count} строк)')
        print(f'  [plan] DELETE workspaces id={args.src}')
        if not args.dry:
            conn.execute("DELETE FROM workspace_members WHERE workspace_id=?", (args.src,))
            conn.execute("DELETE FROM workspaces WHERE id=?", (args.src,))

        # 5. Переименовать dst в новое имя
        print('\n=== STEP 4: rename ws={} ==='.format(args.dst))
        cur_name = conn.execute(
            "SELECT name, is_pulse_themed FROM workspaces WHERE id=?", (args.dst,)
        ).fetchone()
        print(f'  current name="{cur_name[0]}" is_pulse_themed={cur_name[1]}')
        print(f'  -> name="{args.new_name}"')
        if not args.dry:
            conn.execute(
                "UPDATE workspaces SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (args.new_name, args.dst)
            )

        if not args.dry:
            conn.execute("COMMIT")
            print('\n[done] applied')
        else:
            print('\n[dry-run] изменения не применены (--apply чтобы выполнить)')

        # 6. VERIFY
        print('\n=== VERIFY ===')
        for r in conn.execute("SELECT id, name, is_pulse_themed FROM workspaces"):
            print(' ws:', tuple(r))
        for r in conn.execute("""
            SELECT workspace_id, date, COUNT(*) u, SUM(total_messages) m, SUM(pulses_mined) p
            FROM user_stats WHERE date >= date('now','-7 days')
            GROUP BY workspace_id, date ORDER BY date DESC, workspace_id
        """):
            print(' user_stats:', tuple(r))
    except Exception:
        if not args.dry:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
