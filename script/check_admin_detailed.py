#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Детальная проверка флагов администратора
"""

import sqlite3
from dotenv import load_dotenv
import os

load_dotenv()

MAIN_ADMIN_ID = int(os.getenv('MAIN_ADMIN_ID', 0))

def check_admin_detailed(db_path='database/bot_database.db'):
    """Детальная проверка администратора"""
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("=" * 70)
        print("ДЕТАЛЬНАЯ ПРОВЕРКА АДМИНИСТРАТОРА")
        print("=" * 70)
        
        print(f"\n📋 MAIN_ADMIN_ID из .env: {MAIN_ADMIN_ID}")
        
        # Получить данные пользователя
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (MAIN_ADMIN_ID,))
        user = cursor.fetchone()
        
        if not user:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: Пользователь {MAIN_ADMIN_ID} НЕ НАЙДЕН в базе!")
            conn.close()
            return
        
        print(f"\n✅ Пользователь найден в базе:")
        print(f"  user_id: {user['user_id']}")
        print(f"  username: @{user['username'] or 'не установлен'}")
        print(f"  first_name: {user['first_name'] or 'не установлено'}")
        
        print(f"\n🔍 ПРОВЕРКА ФЛАГОВ:")
        print(f"  is_admin: {user['is_admin']} (тип: {type(user['is_admin'])})")
        print(f"  is_owner: {user['is_owner']} (тип: {type(user['is_owner'])})")
        
        # Проверка булевых значений
        is_admin_bool = bool(user['is_admin'])
        is_owner_bool = bool(user['is_owner'])
        is_admin_eq_1 = (user['is_admin'] == 1)
        is_owner_eq_1 = (user['is_owner'] == 1)
        
        print(f"\n🧪 ТЕСТЫ:")
        print(f"  bool(is_admin): {is_admin_bool}")
        print(f"  bool(is_owner): {is_owner_bool}")
        print(f"  is_admin == 1: {is_admin_eq_1}")
        print(f"  is_owner == 1: {is_owner_eq_1}")
        print(f"  is_admin or is_owner: {user['is_admin'] or user['is_owner']}")
        
        # Проверка как в коде бота
        is_admin_by_flag = user['is_admin'] == 1 or user['is_owner'] == 1
        is_admin_by_id = (user['user_id'] == MAIN_ADMIN_ID)
        is_admin_or_owner = is_admin_by_flag or is_admin_by_id
        
        print(f"\n🤖 СИМУЛЯЦИЯ ПРОВЕРКИ В БОТЕ:")
        print(f"  is_admin_by_flag: {is_admin_by_flag}")
        print(f"  is_admin_by_id: {is_admin_by_id}")
        print(f"  is_admin_or_owner: {is_admin_or_owner}")
        
        if is_admin_or_owner:
            print(f"\n✅ РЕЗУЛЬТАТ: Пользователь БУДЕТ заблокирован от получения наград")
        else:
            print(f"\n❌ ПРОБЛЕМА: Пользователь НЕ будет заблокирован!")
            print(f"\n🔧 ИСПРАВЛЕНИЕ:")
            
            cursor.execute('''
                UPDATE users 
                SET is_admin = 1, is_owner = 1
                WHERE user_id = ?
            ''', (MAIN_ADMIN_ID,))
            conn.commit()
            
            print(f"  ✅ Флаги установлены: is_admin=1, is_owner=1")
            print(f"  ⚠️  Необходимо перезапустить бота!")
        
        print("\n" + "=" * 70)
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'database/bot_database.db'
    check_admin_detailed(db_path)
