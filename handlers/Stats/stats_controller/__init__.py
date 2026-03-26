#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание: Пакет stats_controller — диспетчер статистики.
Реэкспортирует все публичные функции для обратной совместимости:
    from handlers.Stats.stats_controller import handle_stats_callback
    from handlers.Stats.stats_controller import show_stats_menu
    from handlers.Stats.stats_controller import handle_exit_interview
"""

from handlers.Stats.stats_controller.menu import (
    show_stats_menu,
    show_stats_period_menu,
    handle_stats_export,
)
from handlers.Stats.stats_controller.callback import (
    handle_stats_callback,
)
from handlers.Stats.stats_controller.interview import (
    handle_exit_interview,
)
from handlers.Stats.stats_exporters import (
    generate_export_file,
)

__all__ = [
    'show_stats_menu',
    'show_stats_period_menu',
    'handle_stats_export',
    'handle_stats_callback',
    'handle_exit_interview',
    'generate_export_file',
]
