"""V1.17.0j: флаг workspace-icons и путь к кешу.

Зеркало `bot_core/connect_flow.py` / `bot_core/login_button.py`. По умолчанию
флаг OFF = эндпоинт `/api/workspaces/{id}/icon.jpg` отдаёт 404, поле
`icon_url` в API не выставляется, job-а прогрева кеша не регистрируется.
Миграция колонок `workspaces.icon_*` аддитивна и безвредна при OFF.

При ON:
- бот лениво кеширует small_file_id chat photo на диск (TTL 7 дней);
- FastAPI отдаёт картинку из кеша через защищённый эндпоинт с Bearer JWT;
- фронт грузит её через `useAuthImage` (fetch → blob URL), при ошибке
  показывает монограмму-fallback (текущее поведение).

См. `docs/superpowers/specs/2026-05-24-workspace-icons-design.md`.
"""
import os

_TRUTHY = {"1", "true", "yes", "on"}


def workspace_icons_enabled() -> bool:
    """True если в окружении WORKSPACE_ICONS=1/true/yes/on (любой регистр)."""
    return os.getenv("WORKSPACE_ICONS", "").strip().lower() in _TRUTHY


def cache_dir() -> str:
    """Путь к директории кеша иконок.

    Прод (Linux): дефолт `/var/cache/pulsbot/ws_icons` — вне репо, переживает
    `git reset --hard` при деплое.
    Локально (Windows/macOS): дефолт `./.cache/ws_icons` относительно
    рабочей директории.
    Переопределяется env `WORKSPACE_ICONS_CACHE_DIR`.
    """
    if os.name == "nt":
        default = os.path.join(".cache", "ws_icons")
    else:
        default = "/var/cache/pulsbot/ws_icons"
    return os.getenv("WORKSPACE_ICONS_CACHE_DIR", default)
