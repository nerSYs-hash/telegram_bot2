#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Описание: Реэкспортёр для обратной совместимости.
Старый код, импортирующий из handlers.bbs_handlers, продолжит работать без изменений.
Вся логика теперь находится в подмодулях handlers/BBS/.
"""

# ── База данных ──
from handlers.BBS.database_bbs import init_bbs_tables, get_profile

# ── Реакции ──
from handlers.BBS.reactions_bbs import handle_bbs_reaction

# ── Очистка ──
from handlers.BBS.cleanup_bbs import cleanup_dead_profiles, on_member_left_cleanup

# ── Константы ──
from handlers.BBS.constants_bbs import (
    BBS, PARAM_OPTIONS, ROLE_OPTIONS, GOAL_OPTIONS, EDITABLE_FIELDS, NAME_REGEX,
)

# ── Хелперы ──
from handlers.BBS.helpers_bbs import (
    get_bbs_state, set_bbs_state, get_bbs_data, clear_bbs,
    build_profile_text, parse_age, city_to_hashtag,
)

# ── FSM шаги (создание анкеты) ──
from handlers.BBS.fsm_steps_bbs import (
    _step_msg,
    start_photo_step, handle_photo_input,
    start_name_step, handle_name_input,
    start_age_step, handle_age_input,
    start_params_step, build_params_keyboard, handle_param_value_input,
    start_role_step, build_role_keyboard,
    start_city_step, build_city_keyboard, handle_city_custom_input,
    start_goal_step, build_goal_keyboard,
    start_about_step, handle_about_input,
    show_preview,
)

# ── Публикация ──
from handlers.BBS.publishing_bbs import (
    publish_profile, delete_profile_messages, republish_profile,
)

# ── Редактирование ──
from handlers.BBS.editing_bbs import (
    apply_edit_and_republish, get_edited_fields, _build_edit_menu_keyboard,
    _build_edit_params_keyboard, _build_edit_role_keyboard,
    _build_edit_city_keyboard, _build_edit_goal_keyboard,
)

# ── Навигация ──
from handlers.BBS.navigation_bbs import show_bbs_menu, show_dating_menu

# ── Callback-диспетчер ──
from handlers.BBS.callback_bbs import handle_bbs_callback

# ── FSM ввод (текст/фото от пользователя) ──
from handlers.BBS.fsm_input_bbs import process_bbs_input
