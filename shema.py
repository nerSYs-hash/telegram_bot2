import sqlite3

# Замени 'database.sqlite' на название твоего файла БД
conn = sqlite3.connect('database.sqlite') 
cursor = conn.cursor()

# Достаем структуру всех таблиц
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
for row in cursor.fetchall():
    if row[0]:
        print(row[0] + "\n")