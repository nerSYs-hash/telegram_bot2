#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование добавленных параметров статистики
"""

import re

def test_callback_handler():
    """Проверка что все 7 параметров добавлены в callback_handler.py"""
    
    with open('/home/claude/final_check/callback_handler.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("="*70)
    print("ПРОВЕРКА callback_handler.py")
    print("="*70)
    
    # Проверка текстового сообщения
    print("\n1. ТЕКСТОВОЕ СООБЩЕНИЕ (stats_message):")
    print("-"*70)
    
    text_params = {
        'Коэффициент вовлеченности': r'Коэффициент вовлеченности:.*%',
        'КОРП': r'КОРП \(реакции оставленные\)',
        'КПРП': r'КПРП \(реакции полученные\)',
        'КОПЮП': r'КОПЮП \(ответы пользователю\)',
        'КОПЯП': r'КОПЯП \(ответы пользователя\)',
        'КУПП': r'КУПП \(упоминания @\)',
        'ПИВДВП': r'ПИВДВП \(публ\. в других ветках\)'
    }
    
    for name, pattern in text_params.items():
        if re.search(pattern, content):
            print(f"   <tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> {name} - найден")
        else:
            print(f"   ❌ {name} - НЕ НАЙДЕН!")
    
    # Проверка Excel
    print("\n2. EXCEL (stats_data['general']):")
    print("-"*70)
    
    excel_params = {
        'Коэффициент вовлеченности': r"'📊 Коэффициент вовлеченности'",
        'КОРП': r"'КОРП - Реакции оставленные'",
        'КПРП': r"'КПРП - Реакции полученные'",
        'КОПЮП': r"'КОПЮП - Ответы пользователю'",
        'КОПЯП': r"'КОПЯП - Ответы пользователя'",
        'КУПП': r"'КУПП - Упоминания @'",
        'ПИВДВП': r"'ПИВДВП - Публ\. в других ветках'"
    }
    
    for name, pattern in excel_params.items():
        if re.search(pattern, content):
            print(f"   <tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> {name} - найден")
        else:
            print(f"   ❌ {name} - НЕ НАЙДЕН!")
    
    # Проверка SQL запросов
    print("\n3. SQL ЗАПРОСЫ:")
    print("-"*70)
    
    sql_checks = {
        'reactions_given': 'SUM(reactions_given)',
        'reactions_received': 'SUM(reactions_received)',
        'replies_sent': 'SUM(replies_sent)',
        'replies_received': 'SUM(replies_received)',
        'mentions_received': 'SUM(mentions_received)',
        'other_threads_posts': 'SUM(other_threads_posts)'
    }
    
    for name, pattern in sql_checks.items():
        count = content.count(pattern)
        if count >= 2:  # Должно быть минимум 2 раза (текст + Excel)
            print(f"   <tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> {name} - найден {count} раз(а)")
        else:
            print(f"   ❌ {name} - найден только {count} раз(а)!")
    
    # Итог
    print("\n" + "="*70)
    print("ИТОГО:")
    print("="*70)
    
    all_text_ok = all(re.search(p, content) for p in text_params.values())
    all_excel_ok = all(re.search(p, content) for p in excel_params.values())
    all_sql_ok = all(content.count(p) >= 2 for p in sql_checks.values())
    
    if all_text_ok and all_excel_ok and all_sql_ok:
        print("<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> ВСЕ 7 ПАРАМЕТРОВ ДОБАВЛЕНЫ ПРАВИЛЬНО!")
        print("<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Текстовое сообщение: OK")
        print("<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> Excel: OK")
        print("<tg-emoji emoji-id="5314250708482513617">✅</tg-emoji> SQL запросы: OK")
        return True
    else:
        print("❌ ЕСТЬ ОШИБКИ!")
        if not all_text_ok:
            print("❌ Текстовое сообщение: ПРОБЛЕМЫ")
        if not all_excel_ok:
            print("❌ Excel: ПРОБЛЕМЫ")
        if not all_sql_ok:
            print("❌ SQL запросы: ПРОБЛЕМЫ")
        return False

if __name__ == '__main__':
    success = test_callback_handler()
    print("\n" + "="*70)
    if success:
        print("<tg-emoji emoji-id="5377497390565939754">🎉</tg-emoji> ТЕСТ ПРОЙДЕН! ФАЙЛ ГОТОВ К ИСПОЛЬЗОВАНИЮ!")
    else:
        print("⚠️ ТЕСТ НЕ ПРОЙДЕН! ПРОВЕРЬТЕ ФАЙЛ!")
    print("="*70)
