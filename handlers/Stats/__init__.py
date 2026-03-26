#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handlers/Stats/__init__.py — обратная совместимость.

Позволяет старому коду продолжать работать:
    from handlers.stats_handlers import show_top, generate_export_file
→   from handlers.Stats import show_top, generate_export_file
"""

# Меню, коллбэки, интервью при выходе
from handlers.Stats.stats_controller import (
    show_stats_menu,
    show_stats_period_menu,
    handle_stats_export,
    handle_stats_callback,
    handle_exit_interview,
)

# Топы
from handlers.Stats.stats_tops import (
    show_top,
    show_top5_menu,
    show_top5_activists,
    show_top5_rich,
    _filter_active_users,
)

# Экспорт
from handlers.Stats.stats_exporters import (
    generate_export_file,
    _add_rate_sheet_to_excel,
)

# Калькуляторы
from handlers.Stats.stats_calculators import (
    calculate_chat_health_indices,
)

__all__ = [
    'show_stats_menu', 'show_stats_period_menu', 'handle_stats_export',
    'handle_stats_callback', 'handle_exit_interview',
    'show_top', 'show_top5_menu',
    'show_top5_activists', 'show_top5_rich', '_filter_active_users',
    'generate_export_file', '_add_rate_sheet_to_excel',
    'calculate_chat_health_indices',
]
