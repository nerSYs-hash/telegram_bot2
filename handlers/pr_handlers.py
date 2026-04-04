#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Пресс-релизы, настройки, управление фичами — HUB-файл.

Путь: handlers/pr_handlers.py (остаётся на прежнем месте)

Реальная логика вынесена в:
    handlers/PR/press_release_pr.py   — пресс-релизы
    handlers/PR/setting_function_pr.py — настройки и управление функциями

Этот файл ТОЛЬКО реэкспортирует функции, чтобы callback_handler.py
продолжал работать без изменений:

    from handlers.pr_handlers import (
        show_settings, start_press_release, ...
    )
"""

# ── Настройки и управление функциями ──
from handlers.PR.setting_function_pr import (
    show_settings,
    show_features_management,
    toggle_feature,
)

# ── Пресс-релизы ──
from handlers.PR.press_release_pr import (
    _resolve_thread_name,
    start_press_release,
    handle_pr_target_selection,
    handle_pr_publish_now,
    handle_pr_schedule,
    show_scheduled_posts,
    handle_pr_delete,
    handle_pr_cancel,
    handle_pr_edit,
    handle_pr_edit_text,
    handle_pr_edit_photo,
    handle_pr_edit_remove_photo,
    handle_pr_edit_time,
    handle_pr_edit_target,
    handle_pr_edit_publish_now,
    handle_pr_add_photo,
    handle_pr_remove_photo,
    handle_pr_full_preview,
    handle_pr_retarget,
    handle_pr_refresh_topics,
)
