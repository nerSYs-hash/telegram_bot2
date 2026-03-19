#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Проверка баланса пользователя
"""

import sqlite3
import sys

def check_user_balance(user_id, db_path='database/bot_database.db'):
    """Проверить баланс пользователя"""
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("=" * 60)
        print(f"ПРОВЕРКА ПОЛЬЗОВАТЕЛЯ {user_id}")
        print("=" * 60)
        
        # Получить данные пользователя
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            print(f"\n❌ Пользователь {user_id} не найден в базе!")
            conn.close()
            return
        
        print(f"\n👤 Информация о пользователе:")
        print(f"  User ID: {user['user_id']}")
        print(f"  Username: @{user['username'] or 'не установлен'}")
        print(f"  First name: {user['first_name'] or 'не установлено'}")
        print(f"  is_admin: {user['is_admin']}")
        print(f"  is_owner: {user['is_owner']}")
        print(f"  💰 Баланс: {user['balance']} пульсов")
        
        # Получить историю транзакций
        cursor.execute('''
            SELECT * FROM transactions 
            WHERE to_user_id = ? OR from_user_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        ''', (user_id, user_id))
        
        transactions = cursor.fetchall()
        
        if transactions:
            print(f"\n📊 Последние 10 транзакций:")
            for tx in transactions:
                direction = "➡️ Получено" if tx['to_user_id'] == user_id else "⬅️ Отправлено"
                print(f"  {direction}: {tx['amount']} пульсов | {tx['transaction_type']} | {tx['timestamp']}")
        else:
            print(f"\n⚠️  Транзакций не найдено")
        
        # Получить статистику сообщений
        cursor.execute('''
            SELECT 
                SUM(total_messages) as msgs,
                SUM(total_words) as words,
                SUM(total_chars) as chars
            FROM user_stats
            WHERE user_id = ?
        ''', (user_id,))
        
        stats = cursor.fetchone()
        
        print(f"\n📈 Статистика активности:")
        print(f"  Сообщений: {stats['msgs'] or 0}")
        print(f"  Слов: {stats['words'] or 0}")
        print(f"  Символов: {stats['chars'] or 0}")
        
        print("\n" + "=" * 60)
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование: python3 check_user_balance.py <user_id>")
        print("Пример: python3 check_user_balance.py 8376708692")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    db_path = sys.argv[2] if len(sys.argv) > 2 else 'database/bot_database.db'
    check_user_balance(user_id, db_path)
