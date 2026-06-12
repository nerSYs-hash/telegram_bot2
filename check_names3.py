import sqlite3

db = sqlite3.connect(r'c:\bot_2\telegram_bot2\Временные\mybot\bot_database.db')
c = db.cursor()

c.execute('''
    SELECT b.thread_id, b.name as b_name, t.thread_name as t_name
    FROM bot_chat_topics b
    LEFT JOIN topics t ON b.chat_id = t.chat_id AND b.thread_id = t.thread_id
    WHERE b.chat_id = -1003516353279
''')
rows = c.fetchall()
print("Total rows:", len(rows))
for r in rows[:15]:
    print(r)

db.close()
