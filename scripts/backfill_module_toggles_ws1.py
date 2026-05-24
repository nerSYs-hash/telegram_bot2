"""Одноразовый идемпотентный backfill module_toggles для workspace=1 (Pulse Москва).

V1.17.0k3: единый источник правды теперь
`database.db_module_toggles.DEFAULT_PULSE_ENABLED` (= seed для любого нового
Pulse-themed workspace). Этот скрипт — тонкая обёртка, чтобы привести ws=1
к тому же набору без отдельного списка.

Повторный запуск ничего не делает (ON CONFLICT DO NOTHING внутри seed).

Использование:
    python scripts/backfill_module_toggles_ws1.py [path/to/db]
"""
import sqlite3
import sys

from database.db_module_toggles import seed_default_modules

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "pulse_bot.db"
WS_ID = 1
SYSTEM_USER = 0


def main():
    conn = sqlite3.connect(DB_PATH)
    inserted = seed_default_modules(
        conn, WS_ID, is_pulse_themed=True, user_id=SYSTEM_USER
    )
    print(f"backfill ws={WS_ID}: inserted={inserted} new module rows "
          f"(existing rows untouched).")


if __name__ == "__main__":
    main()
