#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для проверки настроек бота
"""

from dotenv import load_dotenv
import os

load_dotenv()

print("=" * 60)
print("ПРОВЕРКА НАСТРОЕК БОТА (.env)")
print("=" * 60)

# Основные настройки
bot_token = os.getenv('BOT_TOKEN')
main_admin_id = os.getenv('MAIN_ADMIN_ID')
target_chat_id = os.getenv('TARGET_CHAT_ID')

print(f"\n🤖 BOT_TOKEN: {'✅ Установлен' if bot_token else '❌ НЕ УСТАНОВЛЕН'}")
print(f"👑 MAIN_ADMIN_ID: {main_admin_id or '❌ НЕ УСТАНОВЛЕН'}")
print(f"💬 TARGET_CHAT_ID: {target_chat_id or '❌ НЕ УСТАНОВЛЕН'}")

if main_admin_id and target_chat_id:
    print(f"\n📋 ВАЖНО:")
    print(f"  • Администратор с ID {main_admin_id} должен:")
    print(f"    1) Быть участником чата с ID {target_chat_id}")
    print(f"    2) Писать сообщения В ЭТОМ чате (не в личку боту)")
    print(f"    3) Бот должен иметь права читать сообщения в чате")
    
print("\n" + "=" * 60)
print("Что нужно проверить:")
print("=" * 60)
print("1. ID чата правильный? (отрицательный для групп: -100...)")
print("2. Админ пишет именно в этот чат?")
print("3. Бот добавлен в чат и имеет права читать сообщения?")
print("4. Privacy mode выключен? (Bot Settings → Group Privacy → TURN OFF)")
print("=" * 60)
