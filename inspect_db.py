import sqlite3

db_path = r"C:\bot_2\telegram_bot2\Временные\mybot\bot_database.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# Check users table schema
if ('users',) in tables:
    cursor.execute("PRAGMA table_info(users)")
    print("Schema of users:", cursor.fetchall())
    
    # Let's count them
    cursor.execute("SELECT COUNT(*) FROM users")
    print("Total users:", cursor.fetchone()[0])
    
    # Get a sample
    cursor.execute("SELECT * FROM users LIMIT 3")
    print("Sample:", cursor.fetchall())

conn.close()
