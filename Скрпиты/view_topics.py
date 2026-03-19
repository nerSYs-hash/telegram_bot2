#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Просмотр всех веток/топиков чата и их статистики
"""

import sqlite3
import sys
from dotenv import load_dotenv
import os

load_dotenv()

TARGET_CHAT_ID = int(os.getenv('TARGET_CHAT_ID', 0))

def view_topics(db_path='database/bot_database.db'):
    """Просмотр всех веток чата"""
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("=" * 70)
        print("ВСЕ ВЕТКИ/ТОПИКИ ЧАТА")
        print("=" * 70)
        
        # Получить все ветки
        cursor.execute('''
            SELECT * FROM topics 
            WHERE chat_id = ?
            ORDER BY is_main_thread DESC, total_messages DESC
        ''', (TARGET_CHAT_ID,))
        
        topics = cursor.fetchall()
        
        if not topics:
            print(f"\n⚠️  Ветки не найдены.")
            print(f"Бот начнёт автоматически регистрировать ветки после получения сообщений.")
            conn.close()
            return
        
        print(f"\n📊 Найдено веток: {len(topics)}")
        print()
        
        for topic in topics:
            thread_type = "🏠 Главный чат" if topic['is_main_thread'] else "📌 Ветка"
            thread_id = topic['thread_id'] if topic['thread_id'] else "None"
            
            print(f"{thread_type}")
            print(f"  Название: {topic['thread_name']}")
            print(f"  Thread ID: {thread_id}")
            print(f"  💬 Всего сообщений: {topic['total_messages']}")
            print(f"  📅 Создана: {topic['created_at']}")
            print(f"  🕐 Последнее сообщение: {topic['last_message_at']}")
            print()
        
        # Статистика по всем веткам
        cursor.execute('''
            SELECT 
                message_thread_id,
                COUNT(*) as msg_count,
                COUNT(DISTINCT user_id) as unique_users
            FROM messages
            WHERE chat_id = ?
            GROUP BY message_thread_id
            ORDER BY msg_count DESC
        ''', (TARGET_CHAT_ID,))
        
        stats = cursor.fetchall()
        
        if stats:
            print("=" * 70)
            print("ДЕТАЛЬНАЯ СТАТИСТИКА ПО ВЕТКАМ")
            print("=" * 70)
            print()
            
            for stat in stats:
                thread_id = stat['message_thread_id']
                thread_label = "Главный чат" if thread_id is None else f"Ветка #{thread_id}"
                
                print(f"{thread_label}:")
                print(f"  💬 Сообщений: {stat['msg_count']}")
                print(f"  👥 Уникальных пользователей: {stat['unique_users']}")
                print()
        
        print("=" * 70)
        print("КАК ДОБАВИТЬ НОВЫЕ ВЕТКИ")
        print("=" * 70)
        print("""
<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Бот автоматически регистрирует все ветки!

Когда появляется новая ветка в вашей группе:
1. Пользователь пишет сообщение в новую ветку
2. Бот автоматически обнаруживает её
3. Ветка сохраняется в базу данных
4. Статистика начинает вестись автоматически

Вручную добавлять ничего не нужно! <tg-emoji emoji-id="5377497390565939754">🎉</tg-emoji>

Для просмотра актуального списка веток запускайте:
  python3 view_topics.py

Для изменения названия ветки в базе:
  UPDATE topics SET thread_name = 'Новое название' 
  WHERE chat_id = {TARGET_CHAT_ID} AND thread_id = <ID>;
""")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'database/bot_database.db'
    view_topics(db_path)
