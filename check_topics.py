"""Утилита-проверялка списка топиков чата (диагностика, разовый запуск)."""

import sqlite3

db = 'bot_database.db'
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute("SELECT * FROM topics")
topics = c.fetchall()
for t in topics:
    print(t)
conn.close()
