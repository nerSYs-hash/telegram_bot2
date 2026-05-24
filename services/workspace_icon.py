"""V1.17.0j: auto-иконка workspace из main-чата Telegram (фаза 1).

Логика:
  - `pick_chat_for_icon(conn, ws_id)` — выбирает chat_id для иконки:
    main > admin > journal > любой не-removed > None.
  - `should_refresh(meta, ttl_s)` — true если `icon_cached_at` пуст или
    устарел (TTL по умолчанию 7 дней).
  - `refresh_workspace_icon(bot, conn, ws_id)` — async: `getChat` →
    если есть `small_file_id` → `getFile` → скачать в кеш-файл (атомарно
    через temp+`os.replace`) → обновить БД-метаданные.

Все ошибки TG ловятся локально — фронт корректен (fallback на монограмму).
При успехе `icon_cached_at` всегда обновляется (включая случаи «фото нет» —
чтобы не дёргать TG каждый запрос). При исключении — не обновляется, чтобы
повторить при следующем запросе.

См. `docs/superpowers/specs/2026-05-24-workspace-icons-design.md`.
"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from bot_core.workspace_icons import cache_dir

logger = logging.getLogger(__name__)
_DEFAULT_TTL_S = 7 * 24 * 60 * 60  # 7 дней


def pick_chat_for_icon(conn, ws_id: int) -> Optional[int]:
    """main > admin > journal > любой без role > None. Soft-removed игнорируем.

    `added_at ASC` — детерминированно при равной роли (старейший чат стабилен
    при перезаливе плеера).
    """
    row = conn.execute('''
        SELECT chat_id FROM bot_chats
        WHERE workspace_id=? AND removed_at IS NULL
        ORDER BY CASE role
                   WHEN 'main'    THEN 0
                   WHEN 'admin'   THEN 1
                   WHEN 'journal' THEN 2
                   ELSE 3
                 END,
                 added_at ASC
        LIMIT 1
    ''', (ws_id,)).fetchone()
    return row[0] if row else None


def should_refresh(meta: dict, ttl_s: int = _DEFAULT_TTL_S) -> bool:
    """True если `icon_cached_at` отсутствует/мусор/старше TTL."""
    cached_at = meta.get('icon_cached_at') if meta else None
    if not cached_at:
        return True
    try:
        ts = datetime.fromisoformat(str(cached_at).replace('Z', '').strip())
    except (ValueError, AttributeError):
        return True
    return datetime.utcnow() - ts > timedelta(seconds=ttl_s)


def _ensure_cache_dir() -> Path:
    p = Path(cache_dir())
    p.mkdir(parents=True, exist_ok=True)
    return p


async def refresh_workspace_icon(bot, conn, ws_id: int) -> Optional[str]:
    """Подтянуть иконку main-чата ws_id из Telegram.

    Возвращает абсолютный путь к скачанному файлу или None если:
      - нет ни одного активного чата (icon_local_path=NULL, cached_at=now);
      - у чата нет фото (icon_local_path=NULL, cached_at=now);
      - произошла ошибка TG (БД не трогаем — попробуем снова при след. запросе).
    """
    chat_id = pick_chat_for_icon(conn, ws_id)
    if chat_id is None:
        # Нет активных чатов — фиксируем «попытались, пусто» чтобы не долбить.
        conn.execute(
            "UPDATE workspaces SET icon_cached_at=CURRENT_TIMESTAMP, "
            "icon_local_path=NULL WHERE id=?", (ws_id,)
        )
        conn.commit()
        return None
    try:
        chat = await bot.get_chat(chat_id)
        photo = getattr(chat, 'photo', None)
        small_id = getattr(photo, 'small_file_id', None) if photo else None
        if not small_id:
            # Бот доступ имеет, но у чата нет фото.
            conn.execute(
                "UPDATE workspaces SET icon_cached_at=CURRENT_TIMESTAMP, "
                "icon_local_path=NULL, icon_file_id=NULL WHERE id=?",
                (ws_id,)
            )
            conn.commit()
            return None
        cache = _ensure_cache_dir()
        tmp = cache / f"{ws_id}.jpg.tmp"
        final = cache / f"{ws_id}.jpg"
        f = await bot.get_file(small_id)
        await f.download_to_drive(str(tmp))
        os.replace(str(tmp), str(final))  # атомарно на любых ОС
        conn.execute(
            "UPDATE workspaces SET icon_file_id=?, icon_local_path=?, "
            "icon_cached_at=CURRENT_TIMESTAMP, icon_source='tg' WHERE id=?",
            (small_id, str(final), ws_id)
        )
        conn.commit()
        return str(final)
    except Exception as e:
        # Ошибка TG (403/network/...) — не трогаем БД, чтобы повторить.
        logger.warning(f"refresh_workspace_icon ws={ws_id} chat={chat_id}: {e}")
        return None
