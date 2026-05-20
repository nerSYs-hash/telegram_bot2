"""Одноразово (но идемпотентно): включить module_toggles для workspace=1 (Витя)
для модулей, чьи фичи сейчас реально работают в проде.

Не включаем sprints/combos — их функционал ещё не подключён.
Повторный запуск ничего не делает (ON CONFLICT DO NOTHING).

Использование:
    python scripts/backfill_module_toggles_ws1.py [path/to/db]

Если путь не указан, используется 'pulse_bot.db' в текущей директории.
"""
import sqlite3
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "pulse_bot.db"

ENABLED_FOR_WS1 = [
    "triggers", "press_release", "shipper", "horoscope",
    "economy", "statistics", "top5", "donations",
    "bbs_pulse", "bbs_other", "bbs_anketa", "bbs_vip", "titles",
    "journal",
    # sprints, combos — НЕ включаем (не работают по факту, см. контракт IA_MODULES).
]

WS_ID = 1
SYSTEM_USER = 0  # 0 = system/migration

def main():
    conn = sqlite3.connect(DB_PATH)
    inserted = 0
    for mid in ENABLED_FOR_WS1:
        cur = conn.execute(
            '''INSERT INTO module_toggles (workspace_id, module_id, is_enabled, updated_by)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(workspace_id, module_id) DO NOTHING''',
            (WS_ID, mid, SYSTEM_USER),
        )
        if cur.rowcount:
            inserted += 1
            conn.execute(
                '''INSERT INTO module_toggle_history (workspace_id, module_id, action, reason, changed_by)
                   VALUES (?, ?, 'enable', 'backfill V1.17.0h0', ?)''',
                (WS_ID, mid, SYSTEM_USER),
            )
    # bump cache_version один раз для WS=1 (даже если новых вставок не было — это no-op safe)
    if inserted:
        conn.execute(
            '''INSERT INTO module_toggle_cache_version (workspace_id, version) VALUES (?, 1)
               ON CONFLICT(workspace_id) DO UPDATE SET version = version + 1''',
            (WS_ID,),
        )
    conn.commit()
    print(f"backfill: inserted={inserted}, total_targets={len(ENABLED_FOR_WS1)}")

if __name__ == "__main__":
    main()
