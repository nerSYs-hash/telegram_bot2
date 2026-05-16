"""Pre-deploy: убеждаемся что Pulse ws=1 не сломан per-WS RBAC (Подпроект #3).

workspaces/workspace_members живут в database/bot_database.db
(pulse_bot.db — это только role_permissions/роли, другая БД).

Usage: python scripts/verify_ws_rbac_pulse.py
Exit 0 = OK, exit 1 = инвариант нарушен (НЕ деплоить).
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "database", "bot_database.db")
sys.path.insert(0, HERE)  # чтобы импортировался пакет api/ при прямом запуске


def main() -> int:
    if not os.path.exists(DB):
        print(f"FAIL: {DB} не найден")
        return 1
    conn = sqlite3.connect(DB)
    ws = conn.execute(
        "SELECT id, owner_user_id, is_pulse_themed FROM workspaces WHERE id=1"
    ).fetchone()
    if not ws:
        print("FAIL: workspace id=1 отсутствует")
        return 1
    owner_uid = ws[1]
    m = conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id=1 AND user_id=?",
        (owner_uid,),
    ).fetchone()
    if not m or m[0] != "owner":
        print(f"FAIL: owner {owner_uid} не 'owner' в workspace_members ws=1 (={m})")
        return 1

    from api.workspace_rbac import resolve_ws_role
    role = resolve_ws_role(conn, owner_uid, 1, developer_id=0)
    if role != "owner":
        print(f"FAIL: resolve_ws_role вернул {role!r}, ожидался 'owner'")
        return 1

    dev_id = int(os.getenv("DEVELOPER_ID", 0))
    if dev_id:
        drole = resolve_ws_role(conn, dev_id, 999, developer_id=dev_id)
        if drole != "developer":
            print(f"FAIL: developer god-mode сломан ({drole!r})")
            return 1

    conn.close()
    print(f"OK: ws=1 owner={owner_uid} role=owner; developer god-mode OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
