"""
Миграция V1.17.0h19 — колонка topic_scope в economy_settings.

Хранит JSON-массив thread_id топиков, в которых работает параметр
(penalty / combo / sprint). NULL или пусто = весь чат (все топики).

Идемпотентно: колонка добавляется только если её ещё нет.
"""
import logging

logger = logging.getLogger(__name__)


def up(conn) -> None:
    try:
        cur = conn.cursor()
        cols = [r[1] for r in cur.execute("PRAGMA table_info(economy_settings)").fetchall()]
        if 'topic_scope' not in cols:
            cur.execute("ALTER TABLE economy_settings ADD COLUMN topic_scope TEXT")
            conn.commit()
            logger.info("economy_topic_scope: колонка topic_scope добавлена")
    except Exception as e:
        logger.error("economy_topic_scope migration failed: %s", e)
