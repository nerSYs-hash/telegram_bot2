import sqlite3
import sys
try:
    db = sqlite3.connect('database/bot_database.db')
    print("Schema:", db.execute("SELECT sql FROM sqlite_master WHERE name='branding_settings';").fetchone()[0])
except Exception as e:
    print("Error:", e)
