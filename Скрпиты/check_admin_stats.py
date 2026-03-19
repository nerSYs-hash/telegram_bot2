#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import sys

def check_admin_stats(db_path='database/bot_database.db'):
    """Проверить статистику админов"""
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("=" * 60)
        print("ПРОВЕРКА СТАТИСТИКИ АДМИНИСТРАТОРОВ")
        print("=" * 60)
        
        # 1. Получить всех админов
        cursor.execute('''
            SELECT user_id, username, first_name, is_admin, is_owner, balance
            FROM users 
            WHERE is_admin = 1 OR is_owner = 1
        ''')
        admins = cursor.fetchall()
        
        if not admins:
            print("\n⚠️  В базе НЕТ пользователей с флагами is_admin или is_owner!")
            print("Нужно пометить админов вручную.")
            return
        
        print(f"\n<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Найдено админов: {len(admins)}")
        print("\nСписок администраторов:")
        for admin in admins:
            admin_type = "👑 Владелец" if admin['is_owner'] else "👮 Админ"
            username = admin['username'] or admin['first_name'] or 'Unknown'
            print(f"  {admin_type} | ID: {admin['user_id']} | @{username} | Баланс: {admin['balance']}")
        
        # 2. Проверить статистику сообщений админов
        print("\n" + "=" * 60)
        print("СТАТИСТИКА СООБЩЕНИЙ АДМИНОВ")
        print("=" * 60)
        
        for admin in admins:
            user_id = admin['user_id']
            username = admin['username'] or admin['first_name'] or 'Unknown'
            
            # Статистика из user_stats
            cursor.execute('''
                SELECT 
                    SUM(total_messages) as total_msgs,
                    SUM(total_words) as total_words,
                    SUM(total_chars) as total_chars
                FROM user_stats
                WHERE user_id = ?
            ''', (user_id,))
            
            stats = cursor.fetchone()
            
            # Сообщения из таблицы messages
            cursor.execute('''
                SELECT COUNT(*) as msg_count
                FROM messages
                WHERE user_id = ?
            ''', (user_id,))
            
            msg_count = cursor.fetchone()['msg_count']
            
            print(f"\n@{username} (ID: {user_id}):")
            print(f"  📊 user_stats: {stats['total_msgs'] or 0} сообщений, {stats['total_words'] or 0} слов, {stats['total_chars'] or 0} символов")
            print(f"  💬 messages: {msg_count} записей")
            
            if stats['total_msgs'] is None or stats['total_msgs'] == 0:
                print(f"  ❌ ПРОБЛЕМА: Статистика НЕ ведётся для этого админа!")
            else:
                print(f"  <tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Статистика ведётся")
        
        # 3. Проверить, попадают ли админы в топ
        print("\n" + "=" * 60)
        print("ПРОВЕРКА ТОПА БОГАЧЕЙ (exclude_admins=True)")
        print("=" * 60)
        
        cursor.execute('''
            SELECT user_id, username, first_name, balance, is_admin, is_owner
            FROM users 
            WHERE is_admin = 0 AND is_owner = 0
            ORDER BY balance DESC 
            LIMIT 5
        ''')
        
        top_users = cursor.fetchall()
        
        if top_users:
            print("\nТоп-5 (без админов):")
            for idx, user in enumerate(top_users, 1):
                username = user['username'] or user['first_name'] or 'Unknown'
                print(f"  {idx}. @{username} — {user['balance']} <tg-emoji emoji-id="5368324170671202286">💎</tg-emoji>")
        else:
            print("\n⚠️  Нет пользователей для топа (кроме админов)")
        
        # 4. Проверить топ БЕЗ фильтра (все пользователи)
        print("\n" + "=" * 60)
        print("ПРОВЕРКА ТОПА ВСЕХ ПОЛЬЗОВАТЕЛЕЙ (include admins)")
        print("=" * 60)
        
        cursor.execute('''
            SELECT user_id, username, first_name, balance, is_admin, is_owner
            FROM users 
            ORDER BY balance DESC 
            LIMIT 10
        ''')
        
        all_top = cursor.fetchall()
        
        print("\nТоп-10 (все пользователи):")
        for idx, user in enumerate(all_top, 1):
            username = user['username'] or user['first_name'] or 'Unknown'
            admin_mark = " 👮" if user['is_admin'] or user['is_owner'] else ""
            print(f"  {idx}. @{username} — {user['balance']} <tg-emoji emoji-id="5368324170671202286">💎</tg-emoji>{admin_mark}")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'database/bot_database.db'
    check_admin_stats(db_path)
