import sqlite3

db_path = r"C:\bot_2\telegram_bot2\database\bot_database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("Таблицы:", [t['name'] for t in tables])

# Ищем таблицу с ролями
for t in tables:
    name = t['name']
    try:
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({name})").fetchall()]
        if 'role_raw' in cols or 'role' in cols:
            print(f"\n=== {name} (есть role) ===")
            rows = conn.execute(f"SELECT * FROM {name} LIMIT 20").fetchall()
            for r in rows:
                print(dict(r))
    except Exception as e:
        print(f"  {name}: {e}")

conn.close()
