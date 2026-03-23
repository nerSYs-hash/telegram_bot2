import sqlite3

def update_database():
    # ВАЖНО: Укажи тут имя своего файла базы данных. 
    # Если у тебя файл называется bot.db или database.sqlite, поменяй название ниже:
    db_name = 'bot_database.db' 
    
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    print("⏳ Начинаем обновление базы данных...")

    # 1. Создаем таблицу заявок
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        name TEXT,
        age INTEGER,
        city TEXT,
        therapy TEXT,
        ref_code TEXT,
        status TEXT DEFAULT 'pending',
        admin_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    print("✅ Таблица заявок (applications) готова.")

    # 2. Безопасно добавляем колонки в таблицу users (если их там еще нет)
    # Сначала проверяем, есть ли вообще таблица users
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    
    cursor.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in cursor.fetchall()]

    if 'is_banned' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0")
        print("✅ Добавлена колонка is_banned в таблицу users.")
    
    if 'ref_code' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN ref_code TEXT")
        print("✅ Добавлена колонка ref_code в таблицу users.")

    conn.commit()
    conn.close()
    print("🎉 База данных успешно обновлена! Можно запускать бота.")

if __name__ == '__main__':
    update_database()