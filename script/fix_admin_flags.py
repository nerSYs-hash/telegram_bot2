#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для установки флагов администратора в базе данных
"""

import sqlite3
import sys
from dotenv import load_dotenv
import os

load_dotenv()

MAIN_ADMIN_ID = int(os.getenv('MAIN_ADMIN_ID', 0))

def fix_admin_flags(db_path='database/bot_database.db'):
    """Установить флаги is_admin и is_owner для главного администратора"""
    
    if not MAIN_ADMIN_ID:
        print("❌ MAIN_ADMIN_ID не установлен в .env файле!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("=" * 60)
        print("УСТАНОВКА ФЛАГОВ АДМИНИСТРАТОРА")
        print("=" * 60)
        
        # Проверяем текущее состояние
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (MAIN_ADMIN_ID,))
        user = cursor.fetchone()
        
        if not user:
            print(f"\n❌ Пользователь с ID {MAIN_ADMIN_ID} не найден в базе!")
            print("Сначала администратор должен написать /start боту")
            conn.close()
            return
        
        print(f"\n📋 Текущее состояние пользователя {MAIN_ADMIN_ID}:")
        print(f"  Username: @{user['username'] or 'не установлен'}")
        print(f"  First name: {user['first_name'] or 'не установлено'}")
        print(f"  is_admin: {bool(user['is_admin'])}")
        print(f"  is_owner: {bool(user['is_owner'])}")
        print(f"  Balance: {user['balance']} пульсов")
        
        # Устанавливаем флаги
        cursor.execute('''
            UPDATE users 
            SET is_admin = 1, is_owner = 1
            WHERE user_id = ?
        ''', (MAIN_ADMIN_ID,))
        
        conn.commit()
        
        # Проверяем результат
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (MAIN_ADMIN_ID,))
        updated_user = cursor.fetchone()
        
        print(f"\n✅ Флаги обновлены!")
        print(f"  is_admin: {bool(updated_user['is_admin'])}")
        print(f"  is_owner: {bool(updated_user['is_owner'])}")
        
        print("\n" + "=" * 60)
        print("ПРОВЕРКА: Теперь админ НЕ должен получать пульсы")
        print("=" * 60)
        print("1. Перезапустите бота")
        print("2. Админ пишет сообщение в чат")
        print("3. Проверьте logs/bot.log - должно быть:")
        print("   🚫 User XXX is admin/owner - NO reward given")
        print("4. Баланс админа не должен увеличиться")
        print("=" * 60)
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'database/bot_database.db'
    fix_admin_flags(db_path)
