import sqlite3, os

# Find the main working DB
for dbfile in ['pulse.db', 'pulse_bot.db', 'bot_data.db', 'database.sqlite']:
    path = rf'c:\bot_2\telegram_bot2\{dbfile}'
    if os.path.exists(path):
        try:
            db = sqlite3.connect(path)
            db.row_factory = sqlite3.Row
            c = db.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]
            if 'topics' in tables or 'bot_chat_topics' in tables:
                print(f"\n=== {dbfile} ===")
                print("Tables:", tables)
                if 'topics' in tables:
                    c.execute("PRAGMA table_info(topics)")
                    print("topics schema:", [r[1] for r in c.fetchall()])
                    c.execute("SELECT * FROM topics LIMIT 5")
                    for r in c.fetchall():
                        print(" ", dict(r))
                if 'bot_chat_topics' in tables:
                    c.execute("PRAGMA table_info(bot_chat_topics)")
                    print("bot_chat_topics schema:", [r[1] for r in c.fetchall()])
                    c.execute("SELECT * FROM bot_chat_topics LIMIT 5")
                    for r in c.fetchall():
                        print(" ", dict(r))
            db.close()
        except Exception as e:
            print(f"{dbfile}: {e}")
