"""Утилита-хотфикс данных пользователя в БД (ручная операция)."""

import sqlite3
conn = sqlite3.connect('pulse_bot.db')
conn.execute("UPDATE users SET status='approved' WHERE tg_id=8376708692")
conn.commit()
cur = conn.execute("SELECT tg_id, status FROM users WHERE tg_id=8376708692")
print(cur.fetchone())
conn.close()
