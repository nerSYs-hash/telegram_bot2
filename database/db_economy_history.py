"""
История изменений настроек экономики + данные для мини-графика.
"""
#test
import logging

logger = logging.getLogger(__name__)


def get_history_for_key(db, key: str, limit: int = 20, offset: int = 0) -> dict:
    """Возвращает историю изменений строки + данные для графика."""
    try:
        # Записи истории с инфо о пользователе
        db.cursor.execute(
            """
            SELECT h.id, h.action, h.old_value, h.new_value,
                   h.old_enabled, h.new_enabled, h.comment,
                   h.changed_by, h.changed_by_role, h.rollback_of, h.changed_at,
                   u.username, u.first_name,
                   (SELECT COUNT(*) FROM economy_history r WHERE r.rollback_of = h.id) as is_rolled_back
            FROM economy_history h
            LEFT JOIN users u ON u.user_id = h.changed_by
            WHERE h.setting_key = ?
            ORDER BY h.changed_at DESC
            LIMIT ? OFFSET ?
            """,
            (key, limit, offset)
        )
        rows = db.cursor.fetchall()

        entries = []
        for r in rows:
            entries.append({
                "id":            r['id'],
                "action":        r['action'],
                "old_value":     r['old_value'],
                "new_value":     r['new_value'],
                "old_enabled":   r['old_enabled'],
                "new_enabled":   r['new_enabled'],
                "comment":       r['comment'],
                "changed_by": {
                    "id":       r['changed_by'],
                    "username": r['username'] or '',
                    "name":     r['first_name'] or '',
                    "role":     r['changed_by_role'],
                },
                "rollback_of":   r['rollback_of'],
                "changed_at":    r['changed_at'],
                "is_rolled_back": bool(r['is_rolled_back']),
                "can_rollback":  r['action'] != 'toggle' and not bool(r['is_rolled_back']),
            })

        chart_data = get_history_chart_data(db, key)

        return {"entries": entries, "chart_data": chart_data}
    except Exception as e:
        logger.error(f"get_history_for_key error: {e}")
        return {"entries": [], "chart_data": []}


def get_history_chart_data(db, key: str) -> list:
    """Данные для мини-графика: дата + значение (только edit и rollback)."""
    try:
        # Получаем тип значения
        db.cursor.execute(
            "SELECT value_type FROM economy_settings WHERE key = ?", (key,)
        )
        row = db.cursor.fetchone()
        vt = row['value_type'] if row else 'float'

        db.cursor.execute(
            """
            SELECT DATE(changed_at) as date, new_value
            FROM economy_history
            WHERE setting_key = ? AND action IN ('edit', 'rollback') AND new_value IS NOT NULL
            ORDER BY changed_at ASC
            """,
            (key,)
        )
        rows = db.cursor.fetchall()

        result = []
        for r in rows:
            try:
                if vt == 'int':
                    val = int(r['new_value'])
                elif vt == 'float':
                    val = float(r['new_value'])
                else:
                    val = r['new_value']
                result.append({"date": r['date'], "value": val})
            except Exception:
                pass
        return result
    except Exception as e:
        logger.error(f"get_history_chart_data error: {e}")
        return []


def get_cancellations(db, limit: int = 50, offset: int = 0) -> list:
    try:
        db.cursor.execute(
            "SELECT * FROM economy_cancellations ORDER BY executed_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = db.cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_cancellations(history) error: {e}")
        return []
