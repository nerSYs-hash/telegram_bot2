"""Мост legacy `feature_*` (глобал) → per-ws `module_toggles`.

Зачем: исторически видимость функций в боте решал глобальный
`settings.feature_<id>` (НЕ изолирован — один на все workspace). Современный
источник правды — per-ws `module_toggles` (см. bot_core/module_guard.py).
Этот мост позволяет постепенно перевести call-sites на per-ws, не ломая
ничего: каталожные функции читаются из module_toggles, всё остальное
(сироты без модуля, отсутствие ws-контекста, kill-switch H_RUNTIME_WS=0,
любой сбой) — мягкий fallback на legacy. Гасить функции мост не должен.

См. docs/UNIFIED_FEATURE_AUDIT_2026-05-30.md.
"""
import logging

logger = logging.getLogger(__name__)

# legacy feature_id → module_id из shared/modules_catalog.json.
# Включает alias-мост для исторического рассинхрона id:
#   top/top_commands → top5, donate → donations, bbs → bbs_pulse,
#   bbs_edit → bbs_anketa. Остальные совпадают 1-в-1.
# НЕ в каталоге (остаются legacy-глобал, ядро/просмотр): profile, bank,
# detalization, registration, activities (последняя — производный хаб).
FEATURE_TO_MODULE = {
    'statistics':   'statistics',
    'top':          'top5',
    'top_commands': 'top5',
    'bbs':          'bbs_pulse',
    'bbs_other':    'bbs_other',
    'bbs_edit':     'bbs_anketa',
    'horoscope':    'horoscope',
    'donate':       'donations',
    'referral':     'referral',
    'lottery':      'lottery',
    'bingo':        'bingo',
    'monthly_gift': 'monthly_gift',
    'titles':       'titles',
    'shipper':      'shipper',
}


def feature_enabled_ws(db, feature_name: str, ws_id) -> bool:
    """Per-ws видимость функции с мягким fallback на legacy-глобал.

    Каталожная функция + есть ws_id + runtime-ws включён → читаем
    per-ws module_toggles. Иначе (сирота / нет ws / kill-switch / сбой) →
    legacy `db.is_feature_enabled(feature_name)` (дефолт ON).
    """
    module_id = FEATURE_TO_MODULE.get(feature_name)
    if module_id is not None and ws_id is not None:
        try:
            from bot_core.ws_resolver import runtime_ws_enabled
            if runtime_ws_enabled():
                from bot_core.module_guard import is_module_enabled_cached
                return is_module_enabled_cached(db.conn, ws_id, module_id)
        except Exception as e:  # noqa: BLE001 — мост обязан не гасить функцию
            logger.warning("feature_enabled_ws fallback (%s→%s, ws=%s): %s",
                           feature_name, module_id, ws_id, e)
    return db.is_feature_enabled(feature_name)
