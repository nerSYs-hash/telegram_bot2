import sqlite3

try:
    db = sqlite3.connect(r'c:\bot_2\telegram_bot2\database\bot_database.db')
    c = db.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]
    print('topics table exists:', 'topics' in tables)
    if 'topics' in tables:
        c.execute("PRAGMA table_info(topics)")
        print('topics schema:', [r[1] for r in c.fetchall()])
        c.execute("SELECT * FROM topics LIMIT 3")
        print('topics data:', c.fetchall())
    print('bot_chat_topics table exists:', 'bot_chat_topics' in tables)
    if 'bot_chat_topics' in tables:
        c.execute("PRAGMA table_info(bot_chat_topics)")
        print('bot_chat_topics schema:', [r[1] for r in c.fetchall()])
        c.execute("SELECT * FROM bot_chat_topics LIMIT 3")
        print('bot_chat_topics data:', c.fetchall())
    db.close()
except Exception as e:
    print('ERROR:', e)
