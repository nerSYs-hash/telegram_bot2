import sqlite3

db = sqlite3.connect(r'c:\bot_2\telegram_bot2\Временные\mybot\bot_database.db')
c = db.cursor()

c.execute("SELECT thread_id, name FROM bot_chat_topics WHERE chat_id=-1003516353279")
print("bot_chat_topics:")
for r in c.fetchall(): print(r)

c.execute("SELECT thread_id, thread_name FROM topics WHERE chat_id=-1003516353279")
print("\ntopics:")
for r in c.fetchall(): print(r)

db.close()
