"""DEV-ONLY: демо-данные Статистики для ЛОКАЛЬНОЙ БД.

Заполняет:
  • user_stats_hourly  — почасовые данные (для теплокарт №4/5);
  • user_stats.edited_count / links_sent — для виджетов №8/9.

Нужно, чтобы собрать и посмотреть виджеты Статистики без живого
сообщества. На реальном чате живые данные просто заменят демо.

⚠️ НЕ запускать на проде. Трогает только указанную БД.

Использование:
    python scripts/seed_stats_demo.py [path/to/db] [days]
    (по умолчанию database/bot_database.db, 90 дней)
"""
import random
import sqlite3
import sys
from datetime import date, timedelta

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "database/bot_database.db"
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 90
WS_ID = 1

# Суточный ритм: вес активности по часам 0..23 (ночью тихо, вечером пик).
HOUR_WEIGHTS = [
    2,  1,  1,  1,  1,  2,  4,  8,    # 00-07
    14, 20, 24, 26, 25, 24, 23, 24,   # 08-15
    27, 30, 32, 30, 26, 20, 12, 6,    # 16-23
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    users = [r[0] for r in cur.execute(
        "SELECT user_id FROM users WHERE is_admin=0 AND is_owner=0 LIMIT 120"
    ).fetchall()]
    if not users:
        print("нет пользователей в БД — нечего наполнять")
        return

    today = date.today()
    hourly_rows = 0

    for d in range(DAYS):
        day = today - timedelta(days=d)
        iso = day.isoformat()
        weekend = day.weekday() >= 5
        day_factor = random.uniform(0.7, 1.3) * (0.7 if weekend else 1.0)

        for hour in range(24):
            base = HOUR_WEIGHTS[hour] * day_factor
            n_active = max(0, int(random.gauss(base * 0.5, base * 0.25)))
            n_active = min(n_active, len(users))
            if n_active == 0:
                continue
            for uid in random.sample(users, n_active):
                msgs = max(1, int(random.gauss(3, 2)))
                cur.execute(
                    '''INSERT OR REPLACE INTO user_stats_hourly
                       (workspace_id, user_id, date, hour, total_messages,
                        total_chars, total_words, reactions_given,
                        reactions_received, replies_received, replies_sent,
                        mentions_received, media_sent, other_threads_posts)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (WS_ID, uid, iso, hour, msgs,
                     msgs * random.randint(20, 120), msgs * random.randint(3, 20),
                     random.randint(0, 3), random.randint(0, 4),
                     random.randint(0, 2), random.randint(0, msgs),
                     random.randint(0, 1), random.randint(0, 1), 0))
                hourly_rows += 1

    # edited_count / links_sent на дневных строках user_stats
    daily = cur.execute(
        "SELECT workspace_id, user_id, date, total_messages FROM user_stats "
        "WHERE total_messages > 0"
    ).fetchall()
    for ws, uid, dt, tm in daily:
        edited = int(tm * random.uniform(0.03, 0.15))
        links = int(tm * random.uniform(0.05, 0.20))
        cur.execute(
            "UPDATE user_stats SET edited_count=?, links_sent=? "
            "WHERE workspace_id=? AND user_id=? AND date=?",
            (edited, links, ws, uid, dt))

    conn.commit()
    print(f"demo seed готово: {hourly_rows} почасовых строк, "
          f"{len(daily)} дневных строк обновлено (edited/links)")


if __name__ == "__main__":
    main()
