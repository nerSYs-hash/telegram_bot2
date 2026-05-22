"""
Миграция V1.17.0h17 — правки текстов описаний параметров экономики.

Описания засеяны в economy_settings через INSERT OR IGNORE, поэтому на
уже существующих базах (local + prod) их надо обновить отдельно.

- penalty.toxic         — убрано «(AI-модератор)»
- defib.buff_multiplier — убрано статичное «(x3 = +200%)» (UI считает его
  динамически по текущему значению множителя)
- mining.global_rate + combo.* — «ставку» → «базовую ставку» (понятнее юзеру)

Идемпотентно: обновляет только строки, где описание реально отличается.
"""
import logging

logger = logging.getLogger(__name__)

DESCRIPTIONS = {
    'mining.global_rate':    'Единый множитель: итог = Σ коэф × базовую ставку',
    'penalty.toxic':         'Штраф за токсичное сообщение',
    'defib.buff_multiplier': 'Бонус к майнингу при дефибрилляторе',
    'combo.writer':          'Текст > 50 символов → коэфф × базовую ставку',
    'combo.illustrator':     'Текст > 50 символов + фото → коэфф × базовую ставку',
    'combo.reviewer':        'Видео + текст > 100 слов → коэфф × базовую ставку',
    'combo.dj':              'Ссылка на плейлист → коэфф × базовую ставку',
    'combo.sharp_tongue':    '> 2 ответов на пост (за сутки) → коэфф × базовую ставку',
    'combo.viral_post':      '> 2 реакций на пост → коэфф × базовую ставку',
    'combo.hit_post':        '4+ реакций на пост → коэфф × базовую ставку',
    'combo.legend_post':     '6+ реакций на пост → коэфф × базовую ставку',
}


def up(conn) -> None:
    try:
        cur = conn.cursor()
        changed = 0
        for key, desc in DESCRIPTIONS.items():
            cur.execute(
                "UPDATE economy_settings SET description = ? "
                "WHERE key = ? AND description != ?",
                (desc, key, desc),
            )
            changed += cur.rowcount
        conn.commit()
        if changed:
            logger.info("economy_text_fixes: обновлено описаний — %d", changed)
    except Exception as e:
        logger.error("economy_text_fixes migration failed: %s", e)
