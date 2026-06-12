import sqlite3
db = sqlite3.connect('database/bot_database.db')
db.row_factory = sqlite3.Row

print("=== bot_chats ===")
for row in db.execute("SELECT * FROM bot_chats").fetchall():
    print(dict(row))

print("\n=== bot_chat_topics ===")
for row in db.execute("SELECT * FROM bot_chat_topics").fetchall():
    print(dict(row))

print("\n=== scheduled_posts ===")
for row in db.execute("SELECT id, title, status, status_log FROM scheduled_posts ORDER BY id DESC LIMIT 5").fetchall():
    print(dict(row))

print("\n=== press_release_targets ===")
for row in db.execute("SELECT * FROM press_release_targets ORDER BY id DESC LIMIT 5").fetchall():
    print(dict(row))
