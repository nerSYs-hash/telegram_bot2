import sqlite3
import csv

db_path = r"C:\bot_2\telegram_bot2\Временные\mybot\bot_database.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT user_id, username, first_name, last_name FROM users ORDER BY first_name")
users = cursor.fetchall()

# Write to text file
with open(r"C:\bot_2\telegram_bot2\users_list.txt", "w", encoding="utf-8") as f:
    f.write(f"Список пользователей (всего {len(users)}):\n")
    f.write("-" * 50 + "\n")
    for u in users:
        uid, uname, fname, lname = u
        uname_str = f"@{uname}" if uname else "нет username"
        name_parts = [n for n in (fname, lname) if n]
        full_name = " ".join(name_parts) if name_parts else "без имени"
        f.write(f"ID: {uid:<12} | {uname_str:<20} | Имя: {full_name}\n")

# Write to CSV
with open(r"C:\bot_2\telegram_bot2\users_list.csv", "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f, delimiter=';')
    writer.writerow(["ID", "Username", "Имя", "Фамилия"])
    for u in users:
        uid, uname, fname, lname = u
        uname_str = f"@{uname}" if uname else ""
        writer.writerow([uid, uname_str, fname, lname])

conn.close()

print("Файлы users_list.txt и users_list.csv успешно созданы.")
