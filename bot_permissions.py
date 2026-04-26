"""
Async-обёртки над permissions.py для использования в хендлерах бота.

permissions.py работает с ролями (строка), но в боте у нас есть только user_id —
этот модуль резолвит user_id → role через pulse_bot.db и предоставляет
короткие async-функции для проверки прав.

Использование:
    from bot_permissions import user_has, get_user_role

    if await user_has(user_id, "admins.view"):
        ...
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _pulse_db_path() -> str:
    return os.path.join(_BASE_DIR, "pulse_bot.db")


async def get_user_role(user_id: int) -> str:
    """
    Возвращает роль пользователя: owner / deputy / admin / user.

    Резолвинг:
    1) user_id == OWNER_ID (config) или MAIN_ADMIN_ID (env) → 'owner'
    2) Иначе — читаем поле role из pulse_bot.db.users
    3) Если записи нет → 'user'
    """
    try:
        from config import OWNER_ID
        if user_id == OWNER_ID:
            return "owner"
    except Exception:
        pass

    try:
        main_admin_id = int(os.getenv('MAIN_ADMIN_ID', 0))
        if main_admin_id and user_id == main_admin_id:
            return "owner"
    except Exception:
        pass

    path = _pulse_db_path()
    if not os.path.exists(path):
        return "user"
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("SELECT role FROM users WHERE tg_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0]).lower()
    except Exception as e:
        logger.warning(f"⚠️ bot_permissions: ошибка чтения роли user_id={user_id}: {e}")
    return "user"


async def user_has(user_id: int, permission: str) -> bool:
    """Проверка: есть ли у пользователя указанное permission."""
    role = await get_user_role(user_id)
    try:
        from permissions import has_permission
        return has_permission(role, permission)
    except Exception as e:
        logger.warning(f"⚠️ bot_permissions: ошибка проверки {permission} для {user_id}: {e}")
        return False
