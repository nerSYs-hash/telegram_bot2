#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт миграции базы данных - добавление новых полей статистики
"""

import sqlite3
import sys

def migrate_database(db_path='database/bot_database.db'):
    """Обновить схему базы данных"""
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 70)
        print("МИГРАЦИЯ БАЗЫ ДАННЫХ")
        print("=" * 70)
        print()
        
        # Добавить новые колонки в user_stats
        print("📋 Обновление таблицы user_stats...")
        
        try:
            cursor.execute('ALTER TABLE user_stats ADD COLUMN pulses_mined INTEGER DEFAULT 0')
            print("  ✅ Добавлена колонка pulses_mined")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("  ℹ️  Колонка pulses_mined уже существует")
            else:
                raise
        
        # Добавить новые колонки в chat_stats
        print("\n📋 Обновление таблицы chat_stats...")
        
        new_columns = [
            ('total_messages_with_admins', 'INTEGER DEFAULT 0'),
            ('total_messages_without_admins', 'INTEGER DEFAULT 0'),
            ('total_pulses_mined', 'INTEGER DEFAULT 0'),
            ('avg_message_length', 'REAL DEFAULT 0')
        ]
        
        for column_name, column_type in new_columns:
            try:
                cursor.execute(f'ALTER TABLE chat_stats ADD COLUMN {column_name} {column_type}')
                print(f"  ✅ Добавлена колонка {column_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"  ℹ️  Колонка {column_name} уже существует")
                else:
                    raise
        
        # Создать таблицу topics если её нет (из предыдущих обновлений)
        print("\n📋 Проверка таблицы topics...")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                thread_id INTEGER,
                thread_name TEXT,
                is_main_thread BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_messages INTEGER DEFAULT 0,
                UNIQUE(chat_id, thread_id)
            )
        ''')
        print("  ✅ Таблица topics готова")
        
        # Обновить message_thread_id в messages если нужно
        print("\n📋 Проверка таблицы messages...")
        
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN message_thread_id INTEGER')
            print("  ✅ Добавлена колонка message_thread_id")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("  ℹ️  Колонка message_thread_id уже существует")
            else:
                raise
        
        # Обновить средние значения для существующих записей
        print("\n📋 Обновление средних значений...")
        
        cursor.execute('''
            UPDATE chat_stats
            SET avg_message_length = CASE 
                WHEN total_messages > 0 THEN CAST(total_chars AS REAL) / total_messages
                ELSE 0 
            END
            WHERE avg_message_length = 0
        ''')
        
        updated_rows = cursor.rowcount
        print(f"  ✅ Обновлено {updated_rows} записей")
        
        conn.commit()
        
        print("\n" + "=" * 70)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 70)
        print()
        print("Можете перезапускать бота:")
        print("  python3 bot.py")
        print()
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Ошибка при миграции: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'database/bot_database.db'
    migrate_database(db_path)
