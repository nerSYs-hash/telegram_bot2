import sqlite3
import traceback

c = sqlite3.connect('database/bot_database.db')
try:
    c.execute('''
        INSERT INTO bot_chat_topics (workspace_id, chat_id, thread_id, name, source)
        VALUES (1, 123, 456, 'test', 'auto')
        ON CONFLICT(chat_id, thread_id) DO UPDATE SET name='test'
    ''')
    print("SUCCESS")
except Exception as e:
    print("ERROR:", e)

try:
    c.execute('''
        INSERT INTO bot_chats (workspace_id, chat_id, type)
        VALUES (1, 123, 'group')
        ON CONFLICT(chat_id) DO UPDATE SET type='group'
    ''')
    print("SUCCESS chat")
except Exception as e:
    print("ERROR chat:", e)
