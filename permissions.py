"""
Единая модель прав доступа (RBAC) с динамической раскладкой по ролям.

Архитектура:
    КАТАЛОГ (статичный, в коде)        — все возможные resource.action.
    РАСКЛАДКА (динамическая, в БД)     — какие permissions включены для каждой роли.

Owner всегда получает '*' (нельзя выключить — защита от self-lock).
User — всегда пустой список.
Редактируются: admin и deputy.

Источник БД: pulse_bot.db (рядом с api.py / основным main.py).

Использование:
    from permissions import has_permission, get_role_accesses, init_permissions_db

    init_permissions_db()                     # вызвать один раз при старте
    if has_permission(role, "triggers.delete"):
        ...
"""

import os
import sqlite3
import threading
import time
from typing import Optional

# ── РОЛИ ──
ROLE_OWNER     = "owner"
ROLE_DEVELOPER = "developer"
ROLE_DEPUTY    = "deputy"
ROLE_ADMIN     = "admin"
ROLE_USER      = "user"

ROLES = (ROLE_OWNER, ROLE_DEVELOPER, ROLE_DEPUTY, ROLE_ADMIN, ROLE_USER)
EDITABLE_ROLES = (ROLE_DEPUTY, ROLE_ADMIN)  # owner/developer/user не редактируются

ROLE_LABELS = {
    ROLE_OWNER:     "Владелец",
    ROLE_DEVELOPER: "Разработчик",
    ROLE_DEPUTY:    "Зам владельца",
    ROLE_ADMIN:     "Администратор",
    ROLE_USER:      "Без статуса",
}

# ── РЕСУРСЫ (каталог) ──
RESOURCES = {
    "triggers":   {"label": "Триггеры",           "icon": "ShieldAlert"},
    "shipper":    {"label": "Шиппер",             "icon": "HeartHandshake"},
    "broadcast":  {"label": "Рассылка",           "icon": "Send"},
    "journal":    {"label": "Журнал событий",     "icon": "ScrollText"},
    "statistics": {"label": "Статистика",         "icon": "PieChart"},
    "system":     {"label": "Системные настройки","icon": "Settings"},
    "admins":     {"label": "Управление админами","icon": "ShieldCheck"},
    "blacklist":  {"label": "Чёрный список",      "icon": "Ban"},
    "moderation": {"label": "Модерация чата",     "icon": "ShieldBan"},
    "economy":    {"label": "Экономика",          "icon": "Coins"},
}

# ── ДЕЙСТВИЯ (каталог) ──
ACTION_LABELS = {
    "view":     "просмотр",
    "create":   "создание",
    "edit":     "редактирование",
    "delete":   "удаление",
    "toggle":   "вкл/выкл",
    "export":   "выгрузка",
    "rollback": "откат изменений",
    "cancel":   "отмена выплат",
}

# ── ВСЕ ВОЗМОЖНЫЕ permissions (плоский список) ──
def all_permissions() -> list:
    return [f"{r}.{a}" for r in RESOURCES for a in ACTION_LABELS]


# ── ДЕФОЛТЫ для сидинга при первом старте ──
DEFAULT_ROLE_PERMISSIONS = {
    ROLE_DEPUTY: [
        "triggers.view",   "triggers.create", "triggers.edit", "triggers.delete", "triggers.toggle",
        "shipper.view",    "shipper.edit",    "shipper.toggle",
        "broadcast.view",  "broadcast.create","broadcast.edit","broadcast.delete",
        "journal.view",    "journal.export",
        "statistics.view", "statistics.export",
        "system.view",
        "admins.view",
        "blacklist.view",  "blacklist.create","blacklist.delete",
        "moderation.delete", "moderation.edit", "moderation.toggle",
        "economy.view",    "economy.edit",   "economy.toggle", "economy.rollback",
    ],
    ROLE_ADMIN: [
        "triggers.view",
        "shipper.view",
        "broadcast.view",
        "journal.view",
        "statistics.view",
        "moderation.delete",
        "economy.view",
    ],
}


# ── БД: путь и инициализация ──
def _db_path() -> str:
    """Путь к pulse_bot.db (рядом с этим файлом)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "pulse_bot.db")


def init_permissions_db(db_path: Optional[str] = None) -> None:
    """
    Создаёт таблицу role_permissions и заполняет дефолтами при первом старте.
    Безопасно вызывать многократно.
    """
    path = db_path or _db_path()
    if not os.path.exists(os.path.dirname(path)):
        return
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS role_permissions ("
            "  role       TEXT NOT NULL,"
            "  permission TEXT NOT NULL,"
            "  PRIMARY KEY (role, permission)"
            ")"
        )
        # INSERT OR IGNORE — безопасно добавляет новые разрешения не трогая существующие
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
            for perm in perms:
                conn.execute(
                    "INSERT OR IGNORE INTO role_permissions (role, permission) VALUES (?, ?)",
                    (role, perm),
                )
        conn.commit()
    finally:
        conn.close()


# ── КЕШ (TTL 5 секунд) ──
_cache: dict = {}            # {role: set(perms)}
_cache_at: float = 0.0
_cache_ttl: float = 5.0
_cache_lock = threading.Lock()


def _load_from_db() -> dict:
    """Читает раскладку из БД. Возвращает {role: set(permissions)}."""
    path = _db_path()
    result: dict = {role: set() for role in ROLES}
    if not os.path.exists(path):
        # Фолбэк: дефолты, если БД ещё не создана
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
            result[role] = set(perms)
        return result
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute("SELECT role, permission FROM role_permissions")
        for role, perm in cur.fetchall():
            result.setdefault(role, set()).add(perm)
        conn.close()
    except sqlite3.OperationalError:
        # Таблица ещё не создана — отдаём дефолты
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
            result[role] = set(perms)
    return result


def _get_cache() -> dict:
    """Возвращает кешированную раскладку, перечитывая БД раз в _cache_ttl секунд."""
    global _cache, _cache_at
    with _cache_lock:
        now = time.time()
        if not _cache or (now - _cache_at) > _cache_ttl:
            _cache = _load_from_db()
            _cache_at = now
        return _cache


def invalidate_cache() -> None:
    """Сбросить кеш (вызывать после изменения прав через API)."""
    global _cache, _cache_at
    with _cache_lock:
        _cache = {}
        _cache_at = 0.0


# ── ПУБЛИЧНЫЙ API ──
def normalize_role(role) -> str:
    r = (role or "").lower()
    return r if r in ROLES else ROLE_USER


def has_permission(role, permission: str) -> bool:
    """Главная проверка. Owner и Developer всегда True, user всегда False."""
    role = normalize_role(role)
    if role in (ROLE_OWNER, ROLE_DEVELOPER):
        return True
    if role == ROLE_USER:
        return False
    return permission in _get_cache().get(role, set())


def get_role_permissions(role) -> list:
    """Плоский список permissions для роли (для owner/developer — раскрывает '*')."""
    role = normalize_role(role)
    if role in (ROLE_OWNER, ROLE_DEVELOPER):
        return all_permissions()
    if role == ROLE_USER:
        return []
    return sorted(_get_cache().get(role, set()))


def set_role_permissions(role: str, permissions: list) -> None:
    """Перезаписать раскладку для роли (используется API). Игнорирует owner/user."""
    role = normalize_role(role)
    if role not in EDITABLE_ROLES:
        raise ValueError(f"Роль '{role}' не редактируется")
    valid = set(all_permissions())
    cleaned = sorted({p for p in permissions if p in valid})
    path = _db_path()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS role_permissions ("
            "  role TEXT NOT NULL, permission TEXT NOT NULL,"
            "  PRIMARY KEY (role, permission))"
        )
        conn.execute("DELETE FROM role_permissions WHERE role = ?", (role,))
        conn.executemany(
            "INSERT INTO role_permissions (role, permission) VALUES (?, ?)",
            [(role, p) for p in cleaned],
        )
        conn.commit()
    finally:
        conn.close()
    invalidate_cache()


def get_role_accesses(role) -> list:
    """
    Группированный список доступов для UI «Профиль».
    [{key, label, icon, actions: [{key, label}]}, ...]
    Только ресурсы, к которым есть хотя бы одно действие.
    """
    flat = get_role_permissions(role)
    grouped: dict = {}
    for perm in flat:
        if "." not in perm:
            continue
        res, act = perm.split(".", 1)
        if res not in RESOURCES or act not in ACTION_LABELS:
            continue
        grouped.setdefault(res, []).append(act)

    result = []
    for res_key, meta in RESOURCES.items():
        if res_key not in grouped:
            continue
        actions = [{"key": a, "label": ACTION_LABELS[a]} for a in grouped[res_key]]
        result.append({
            "key":     res_key,
            "label":   meta["label"],
            "icon":    meta["icon"],
            "actions": actions,
        })
    return result


def get_catalog() -> dict:
    """
    Полный каталог для UI редактора прав.
    Возвращает структуру для отрисовки матрицы «ресурс × действие».
    """
    return {
        "resources": [
            {"key": k, "label": v["label"], "icon": v["icon"]}
            for k, v in RESOURCES.items()
        ],
        "actions": [
            {"key": k, "label": v}
            for k, v in ACTION_LABELS.items()
        ],
        "roles": [
            {"key": r, "label": ROLE_LABELS[r], "editable": r in EDITABLE_ROLES}
            for r in ROLES
        ],
    }


def get_all_role_permissions() -> dict:
    """
    Текущая раскладка по всем ролям (для UI редактора).
    {role: [permissions]}
    """
    out = {}
    for role in ROLES:
        out[role] = get_role_permissions(role)
    return out
