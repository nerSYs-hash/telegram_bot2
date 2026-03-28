import sqlite3
import os

dbs = ['bot_database.db', 'pulse_bot.db', 'database.db']
for db in dbs:
    if os.path.exists(db):
        print(f"Checking {db}...")
        try:
            conn = sqlite3.connect(db)
            c = conn.cursor()
            
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_posts'")
            if not c.fetchone():
                print("No scheduled_posts table")
                continue
                
            c.execute("SELECT id, text, publish_at, status FROM scheduled_posts;")
            posts = c.fetchall()
            if posts:
                print("Scheduled posts:")
                for p in posts:
                    print(p)
            else:
                print("No rows.")
            conn.close()
        except sqlite3.Error as e:
            print("Error connecting", e)
