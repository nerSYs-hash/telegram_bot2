#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Прямое обновление флагов администратора в базе данных
"""

import sqlite3
import sys

ADMIN_ID = 7536752126  # Ваш ID администратора

def update_admin_flags(db_path='database/bot_database.db'):
    """Обновить флаги администратора"""
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("=" * 60)
        print("УСТАНОВКА ФЛАГОВ АДМИНИСТРАТОРА")
        print("=" * 60)
        
        # Проверяем текущее состояние
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (ADMIN_ID,))
        user = cursor.fetchone()
        
        if not user:
            print(f"\n❌ Пользователь {ADMIN_ID} не найден!")
            conn.close()
            return
        
        print(f"\n📋 ДО обновления:")
        print(f"  User ID: {user['user_id']}")
        print(f"  Username: @{user['username']}")
        print(f"  is_admin: {user['is_admin']}")
        print(f"  is_owner: {user['is_owner']}")
        
        # Обновляем флаги
        cursor.execute('''
            UPDATE users 
            SET is_admin = 1, is_owner = 1
            WHERE user_id = ?
        ''', (ADMIN_ID,))
        
        conn.commit()
        
        # Проверяем результат
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (ADMIN_ID,))
        updated = cursor.fetchone()
        
        print(f"\n✅ ПОСЛЕ обновления:")
        print(f"  is_admin: {updated['is_admin']}")
        print(f"  is_owner: {updated['is_owner']}")
        
        print("\n" + "=" * 60)
        print("✅ ГОТОВО!")
        print("=" * 60)
        print("Теперь выполните:")
        print("1. cp message_handler.py handlers/message_handler.py")
        print("2. Перезапустите бота")
        print("3. Админ пишет сообщение")
        print("4. Проверьте логи - должно быть:")
        print("   🚫 BLOCKED: User 7536752126 is admin/owner")
        print("=" * 60)
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'database/bot_database.db'
    update_admin_flags(db_path)
