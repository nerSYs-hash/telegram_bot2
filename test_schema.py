import sqlite3
c = sqlite3.connect('database/bot_database.db')
print(c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='topics'").fetchone()[0])
