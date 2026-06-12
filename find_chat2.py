import sqlite3, os

dbs = [
    r'c:\bot_2\telegram_bot2\Временные\mybot\bot_database.db'
]

for dbpath in dbs:
    try:
        db = sqlite3.connect(dbpath)
        c = db.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in c.fetchall()]
        
        if 'bot_chats' in tables:
            c.execute("SELECT * FROM bot_chats")
            rows = c.fetchall()
            if len(rows) > 0:
                print(f"=== {dbpath} ===")
                print(f"Found {len(rows)} chats in bot_chats")
                print("Chats:", rows)
        if 'bot_chat_topics' in tables:
            c.execute("SELECT * FROM bot_chat_topics")
            rows = c.fetchall()
            if len(rows) > 0:
                print(f"Found {len(rows)} topics in bot_chat_topics")
                print("Sample:", rows[:2])
        if 'topics' in tables:
            c.execute("SELECT * FROM topics WHERE thread_name IS NOT NULL LIMIT 2")
            rows = c.fetchall()
            if len(rows) > 0:
                print("Found named topics in topics table")
                print("Sample:", rows)

        db.close()
    except Exception as e:
        print(f"Error reading {dbpath}: {e}")
