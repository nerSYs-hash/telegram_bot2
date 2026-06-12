import sqlite3, os, glob

# Find all DB files
dbs = glob.glob(r'c:\bot_2\telegram_bot2\*.db') + glob.glob(r'c:\bot_2\telegram_bot2\*.sqlite')
print("DB files found:", dbs)

for dbpath in dbs:
    try:
        db = sqlite3.connect(dbpath)
        db.row_factory = sqlite3.Row
        c = db.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in c.fetchall()]
        
        if 'topics' in tables:
            print(f"\n=== {os.path.basename(dbpath)} has 'topics' ===")
            c.execute("PRAGMA table_info(topics)")
            cols = [(r[0], r[1], r[2]) for r in c.fetchall()]
            print("  Columns:", cols)
            c.execute("SELECT * FROM topics LIMIT 3")
            for r in c.fetchall():
                print("  Row:", dict(r))
        
        if 'bot_chat_topics' in tables:
            print(f"\n=== {os.path.basename(dbpath)} has 'bot_chat_topics' ===")
            c.execute("PRAGMA table_info(bot_chat_topics)")
            cols = [(r[0], r[1], r[2]) for r in c.fetchall()]
            print("  Columns:", cols)
            c.execute("SELECT COUNT(*) FROM bot_chat_topics")
            cnt = c.fetchone()[0]
            print(f"  Total rows: {cnt}")
            c.execute("SELECT * FROM bot_chat_topics LIMIT 5")
            for r in c.fetchall():
                print("  Row:", dict(r))
        
        db.close()
    except Exception as e:
        print(f"{os.path.basename(dbpath)}: ERROR {e}")
