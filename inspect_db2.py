import sqlite3
db = sqlite3.connect('database/bot_database.db')
db.row_factory = sqlite3.Row

print("=== scheduled_posts ===")
try:
    for row in db.execute("SELECT * FROM scheduled_posts ORDER BY id DESC LIMIT 5").fetchall():
        print(dict(row))
except Exception as e:
    print(e)
