import sqlite3

db = sqlite3.connect('database/bot_db.sqlite')
db.row_factory = sqlite3.Row

print("=== topics table ===")
for row in db.execute("SELECT * FROM topics LIMIT 10").fetchall():
    print(dict(row))

print("\n=== bot_chat_topics table ===")
for row in db.execute("SELECT * FROM bot_chat_topics LIMIT 10").fetchall():
    print(dict(row))
