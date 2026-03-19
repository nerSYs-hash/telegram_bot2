#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Обновление названий веток чата
"""

import sqlite3
import sys
from dotenv import load_dotenv
import os

load_dotenv()

TARGET_CHAT_ID = int(os.getenv('TARGET_CHAT_ID', 0))

def update_topic_name(thread_id, new_name, db_path='database/bot_database.db'):
    """Обновить название ветки"""
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("=" * 60)
        print("ОБНОВЛЕНИЕ НАЗВАНИЯ ВЕТКИ")
        print("=" * 60)
        
        # Получить текущую информацию
        if thread_id.lower() == 'none' or thread_id == '0':
            thread_id_value = None
        else:
            thread_id_value = int(thread_id)
        
        cursor.execute('''
            SELECT * FROM topics 
            WHERE chat_id = ? AND thread_id IS ?
        ''', (TARGET_CHAT_ID, thread_id_value))
        
        topic = cursor.fetchone()
        
        if not topic:
            print(f"\n❌ Ветка с ID '{thread_id}' не найдена!")
            print(f"\nЗапустите: python3 view_topics.py")
            print(f"чтобы увидеть список всех веток.")
            conn.close()
            return
        
        print(f"\n📋 Текущее название: {topic['thread_name']}")
        print(f"📝 Новое название: {new_name}")
        
        # Обновить название
        cursor.execute('''
            UPDATE topics 
            SET thread_name = ?
            WHERE chat_id = ? AND thread_id IS ?
        ''', (new_name, TARGET_CHAT_ID, thread_id_value))
        
        conn.commit()
        
        print(f"\n✅ Название успешно обновлено!")
        print(f"\nПроверьте: python3 view_topics.py")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

def main():
    if len(sys.argv) < 3:
        print("""
Использование: 
  python3 update_topic_name.py <thread_id> "<новое название>"

Примеры:
  # Обновить главный чат
  python3 update_topic_name.py none "Общий чат"
  
  # Обновить ветку с ID 123
  python3 update_topic_name.py 123 "Кулинария 🍳"
  
  # Обновить ветку с ID 456
  python3 update_topic_name.py 456 "Технологии 💻"

Сначала запустите view_topics.py чтобы узнать ID веток:
  python3 view_topics.py
""")
        sys.exit(1)
    
    thread_id = sys.argv[1]
    new_name = sys.argv[2]
    db_path = sys.argv[3] if len(sys.argv) > 3 else 'database/bot_database.db'
    
    update_topic_name(thread_id, new_name, db_path)

if __name__ == '__main__':
    main()
