"""V1.17.0h C7: одноразовая безопасная консолидация workspace.

Перепривязывает bot_chats из пустых source-ws в целевой ws (роли
сохраняются), удаляет опустевшие source-ws + их workspace_members.
Защита: source с непустыми tenant-данными → ConsolidateBlocked.

Usage:
  python -m scripts.consolidate_workspaces --db database/bot_database.db --from 5,6 --into 1            # dry-run
  python -m scripts.consolidate_workspaces --db database/bot_database.db --from 5,6 --into 1 --apply     # выполнить
Бэкап БД делается автоматически перед --apply.
"""
import argparse, os, shutil, sqlite3, sys
from datetime import datetime

from database.db_workspaces import TENANT_TABLES


class ConsolidateBlocked(Exception):
    pass


def _tenant_rows(conn, ws_id):
    total = 0
    for t in TENANT_TABLES:
        try:
            total += conn.execute(
                f"SELECT COUNT(*) FROM {t} WHERE workspace_id=?", (ws_id,)
            ).fetchone()[0]
        except sqlite3.OperationalError:
            pass
    return total


def consolidate(conn, from_ids, into_id, apply=False):
    plan = []
    for src in from_ids:
        n = _tenant_rows(conn, src)
        if n > 0:
            raise ConsolidateBlocked(
                f"ws={src} имеет {n} tenant-строк — авто-консолидация запрещена, нужно ручное решение")
        chats = conn.execute(
            "SELECT chat_id, role FROM bot_chats WHERE workspace_id=?", (src,)).fetchall()
        plan.append((src, chats))
        for cid, role in chats:
            print(f"[plan] bot_chats chat_id={cid} role={role}: ws {src} -> {into_id}")
        print(f"[plan] DELETE workspace_members ws={src}; DELETE workspaces id={src}")
    if not apply:
        print("[dry-run] изменения НЕ применены (--apply чтобы выполнить)")
        return
    try:
        conn.execute("BEGIN")
        for src, _ in plan:
            conn.execute("UPDATE bot_chats SET workspace_id=? WHERE workspace_id=?", (into_id, src))
            conn.execute("DELETE FROM workspace_members WHERE workspace_id=?", (src,))
            conn.execute("DELETE FROM workspaces WHERE id=?", (src,))
        conn.execute("COMMIT")
        print(f"[done] консолидация выполнена: {from_ids} -> {into_id}")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _backup(db_path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = f"{db_path}.pre_consolidate_{ts}"
    shutil.copy2(db_path, dest)
    print(f"[backup] {dest}")
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--from", dest="from_ids", required=True, help="напр. 5,6")
    ap.add_argument("--into", dest="into_id", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    from_ids = [int(x) for x in a.from_ids.split(",") if x.strip()]
    if a.apply:
        _backup(a.db)
    conn = sqlite3.connect(a.db)
    try:
        consolidate(conn, from_ids, a.into_id, apply=a.apply)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
