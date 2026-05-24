"""Утилита: скачивание/локальная копия БД бота (вспомогательный скрипт)."""

import sqlite3
conn = sqlite3.connect('bot_database.db')
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
for row in cursor.fetchall():
    if row[0]: print(row[0] + '\n')
