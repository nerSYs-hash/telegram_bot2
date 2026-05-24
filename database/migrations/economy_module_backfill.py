"""Economy modules backfill — module_toggles для эконом-модулей workspace=1.
ID: 2026-05-21-economy-module-backfill

Каталог shared/modules_catalog.json в V1.17.0h2 разбил единый модуль
`economy` на гранулярные:
    mining, sprints, combos, penalty, lottery, bingo,
    monthly_gift, referral, bbs_bonus.

Старый backfill (V1.17.0h0g) включал для ws=1 один общий `economy`.
После рейминга у новых module_id нет строк в module_toggles → по
дефолту OFF. Так как бот с V1.17.0h3 читает состояние разделов
Экономики именно из module_toggles, без этой миграции работающие на
проде фичи (майнинг/лотерея/бинго/...) погасли бы.

Миграция идемпотентна: только дозаполняет отсутствующие строки
(ON CONFLICT DO NOTHING — явное OFF от владельца не перетирается) и
убирает устаревшую строку `economy`.
"""
import sqlite3

WS_ID = 1
SYSTEM_USER = 0  # 0 = system/migration

# 9 эконом-модулей из секции "economy" каталога. Включаем для ws=1, т.к.
# их функционал реально работает на проде — поведение должно сохраниться.
ECONOMY_MODULES = [
    "mining", "sprints", "combos", "penalty", "lottery",
    "bingo", "monthly_gift", "referral", "bbs_bonus",
]


def up(conn: sqlite3.Connection) -> None:
    inserted = 0
    for module_id in ECONOMY_MODULES:
        cur = conn.execute(
            '''INSERT INTO module_toggles (workspace_id, module_id, is_enabled, updated_by)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(workspace_id, module_id) DO NOTHING''',
            (WS_ID, module_id, SYSTEM_USER),
        )
        if cur.rowcount:
            inserted += 1
            conn.execute(
                '''INSERT INTO module_toggle_history
                       (workspace_id, module_id, action, reason, changed_by)
                   VALUES (?, ?, 'enable', 'backfill V1.17.0h3 (economy split)', ?)''',
                (WS_ID, module_id, SYSTEM_USER),
            )

    # Устаревшая строка: модуль `economy` переименован в `mining` + гранулы.
    conn.execute(
        "DELETE FROM module_toggles WHERE workspace_id=? AND module_id='economy'",
        (WS_ID,),
    )

    if inserted:
        # Сбросить bot-кеш module_guard через bump версии.
        conn.execute(
            '''INSERT INTO module_toggle_cache_version (workspace_id, version)
               VALUES (?, 1)
               ON CONFLICT(workspace_id) DO UPDATE SET version = version + 1''',
            (WS_ID,),
        )
    conn.commit()
