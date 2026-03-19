#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт миграции данных из user_stats в messages
Используйте для заполнения таблицы messages историческими данными
"""

import sqlite3
from datetime import datetime, timedelta

def migrate_data():
    print("🔄 МИГРАЦИЯ ДАННЫХ: user_stats → messages\n")
    
    db_path = 'database/bot_database.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Проверяем, есть ли данные в user_stats
    cursor.execute('SELECT COUNT(*) as count FROM user_stats WHERE total_messages > 0')
    stats_count = cursor.fetchone()['count']
    
    print(f"📊 Найдено записей в user_stats: {stats_count}")
    
    if stats_count == 0:
        print("⚠️  Нет данных для миграции!")
        conn.close()
        return
    
    # Проверяем, есть ли уже данные в messages
    cursor.execute('SELECT COUNT(*) as count FROM messages')
    msg_count = cursor.fetchone()['count']
    
    print(f"💬 Текущих записей в messages: {msg_count}")
    
    if msg_count > 0:
        response = input("\n⚠️  В таблице messages уже есть данные. Продолжить? (yes/no): ")
        if response.lower() not in ['yes', 'y', 'да']:
            print("Отменено.")
            conn.close()
            return
    
    print("\n🔄 Начинаем миграцию...\n")
    
    # Получаем все записи из user_stats
    cursor.execute('''
        SELECT user_id, date, total_messages
        FROM user_stats
        WHERE total_messages > 0
        ORDER BY date ASC
    ''')
    
    stats = cursor.fetchall()
    total_migrated = 0
    
    for stat in stats:
        user_id = stat['user_id']
        date = stat['date']
        total_messages = stat['total_messages']
        
        # Создаём синтетические записи сообщений
        # Распределяем их равномерно по дню
        
        # Конвертируем дату в datetime
        if isinstance(date, str):
            date_obj = datetime.strptime(date, '%Y-%m-%d')
        else:
            date_obj = datetime.combine(date, datetime.min.time())
        
        # Создаём записи с интервалом
        interval_minutes = 1440 / max(total_messages, 1)  # 1440 минут в дне
        
        for i in range(total_messages):
            timestamp = date_obj + timedelta(minutes=i * interval_minutes)
            
            cursor.execute('''
                INSERT INTO messages (user_id, chat_id, message_text, message_type, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, 0, '[migrated from stats]', 'text', timestamp))
            
            total_migrated += 1
        
        if total_migrated % 100 == 0:
            print(f"  <tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Мигрировано {total_migrated} сообщений...")
    
    conn.commit()
    
    print(f"\n<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> МИГРАЦИЯ ЗАВЕРШЕНА!")
    print(f"📊 Всего мигрировано: {total_migrated} сообщений")
    
    # Проверяем результат
    cursor.execute('SELECT COUNT(*) as count FROM messages')
    new_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(DISTINCT user_id) as count FROM messages')
    users_count = cursor.fetchone()['count']
    
    print(f"💬 Сообщений в таблице: {new_count}")
    print(f"👥 Уникальных пользователей: {users_count}")
    
    conn.close()
    print("\nГотово! Теперь статистика будет отображаться корректно.")

if __name__ == '__main__':
    try:
        migrate_data()
    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        import traceback
        traceback.print_exc()
