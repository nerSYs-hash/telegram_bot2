import sqlite3

try:
    db = sqlite3.connect(r'c:\bot_2\telegram_bot2\database\bot_database.db')
    c = db.cursor()
    c.execute("SELECT chat_id, title FROM bot_chats")
    chats = c.fetchall()
    print("Chats:", chats)
    
    for chat_id, title in chats:
        print(f"\n=== Chat: {title} ({chat_id}) ===")
        c.execute("SELECT thread_id, name FROM bot_chat_topics WHERE chat_id=?", (chat_id,))
        bt = c.fetchall()
        print(f"bot_chat_topics ({len(bt)}):", bt[:5])
        
        c.execute("SELECT thread_id, thread_name FROM topics WHERE chat_id=?", (chat_id,))
        top = c.fetchall()
        print(f"topics ({len(top)}):", top[:5])
        
        c.execute('''
            SELECT b.thread_id, b.name as b_name, t.thread_name as t_name
            FROM bot_chat_topics b
            LEFT JOIN topics t ON b.chat_id = t.chat_id AND b.thread_id = t.thread_id
            WHERE b.chat_id = ?
        ''', (chat_id,))
        join_res = c.fetchall()
        print(f"JOIN result ({len(join_res)}):", join_res[:5])

    db.close()
except Exception as e:
    print('ERROR:', e)
