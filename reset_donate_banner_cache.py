#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Одноразовый скрипт: сбрасывает кэш file_id баннера донатов.

Telegram кэширует загруженный баннер по `file_id` и хранит его в таблице
`settings` под ключом `banner_fid_donate`. После замены файла
`assets/banners/donate_banner.jpg` кэш надо сбросить, иначе бот будет
продолжать слать в чат старую картинку (по сохранённому file_id).

Использование:
    cd C:\\bot_2\\telegram_bot2
    python reset_donate_banner_cache.py
    # или с явным путём БД:
    python reset_donate_banner_cache.py path/to/bot_database.db

После запуска при следующем показе баннера донатов бот загрузит файл с диска
и закэширует НОВЫЙ file_id.
"""

import os
import sqlite3
import sys


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.getenv(
        'DATABASE_PATH', 'database/bot_database.db'
    )

    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)

    if not os.path.exists(db_path):
        print(f"❌ БД не найдена: {db_path}")
        sys.exit(1)

    key = 'banner_fid_donate'

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = cur.fetchone()

    if row is None:
        print(f"ℹ️  Кэш '{key}' уже пуст (ничего удалять).")
    else:
        old = row[0]
        cur.execute('DELETE FROM settings WHERE key = ?', (key,))
        conn.commit()
        short = (old[:24] + '…') if old and len(old) > 24 else old
        print(f"✅ Удалён кэш '{key}' (был: {short}).")

    conn.close()
    print("Готово. При следующем показе баннер будет перезалит из файла.")


if __name__ == '__main__':
    main()
