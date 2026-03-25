"""
Модуль для создания клавиатур бота
Содержит все inline и reply клавиатуры
"""
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from constants import Buttons


# ==================== REPLY КЛАВИАТУРЫ (ВНИЗУ ЭКРАНА) ====================

def create_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Создание reply-клавиатуры для администратора"""
    keyboard = [
        [KeyboardButton(text=Buttons.NEW_APPLICATIONS)],
        [KeyboardButton(text=Buttons.ADMINS), KeyboardButton(text=Buttons.BLACKLIST)],
        [KeyboardButton(text=Buttons.CHECK_USER), KeyboardButton(text=Buttons.TRIGGERS)]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )


def create_owner_reply_keyboard() -> ReplyKeyboardMarkup:
    """Создание reply-клавиатуры для владельца"""
    keyboard = [
        [KeyboardButton(text=Buttons.NEW_APPLICATIONS)],
        [KeyboardButton(text=Buttons.ADMINS), KeyboardButton(text=Buttons.BLACKLIST)],
        [KeyboardButton(text=Buttons.CHECK_USER), KeyboardButton(text=Buttons.TRIGGERS)],
        [KeyboardButton(text=Buttons.JOURNAL), KeyboardButton(text=Buttons.STATISTICS)]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Панель владельца..."
    )


# ==================== INLINE КЛАВИАТУРЫ (ПОД СООБЩЕНИЯМИ) ====================

def create_age_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения возраста"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="✅ Мне уже есть 18",
        callback_data="age_confirm"
    ))
    return builder.as_markup()


def create_rules_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для принятия правил"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📜 Правила чата",
        callback_data="rules_accept"
    ))
    return builder.as_markup()


def create_submit_application_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подачи заявки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📝 Подать заявку",
        callback_data="submit_app"
    ))
    return builder.as_markup()


def create_skip_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пропуска необязательных полей"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⏭ Пропустить",
        callback_data="skip_ref_code"
    ))
    return builder.as_markup()


def create_app_review_keyboard(app_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра заявки из уведомления"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="👁 Просмотреть заявку",
        callback_data=f"admin_apps"
    ))
    return builder.as_markup()


def create_application_navigation_keyboard(app_id: int, app_ids: list, current_index: int, has_prev: bool = False, has_next: bool = False) -> InlineKeyboardMarkup:
    """Создание клавиатуры для навигации по заявкам"""
    # Преобразуем список ID в строку для передачи в callback_data
    app_ids_str = ','.join(map(str, app_ids))
    
    buttons = []
    
    # Строка навигации
    nav_buttons = []
    if has_prev:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️ Предыдущая",
                callback_data=f"app_prev_{current_index}_{app_ids_str}"
            )
        )
    if has_next:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Следующая ▶️",
                callback_data=f"app_next_{current_index}_{app_ids_str}"
            )
        )
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Строка с действиями
    buttons.append([
        InlineKeyboardButton(
            text="✅ Одобрить",
            callback_data=f"app_approve_{app_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"app_reject_{app_id}"
        )
    ])
    
    # Информация о позиции
    buttons.append([
        InlineKeyboardButton(
            text=f"📋 {current_index + 1} из {len(app_ids)}",
            callback_data="ignore"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_dm_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для отправки личного сообщения пользователю"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💬 Написать в ЛС",
        url=f"tg://user?id={user_id}"
    ))
    return builder.as_markup()


def create_continue_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для продолжения заполнения анкеты"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⏩ Продолжить",
        callback_data="continue_questionnaire"
    ))
    return builder.as_markup()


def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры главного меню для пользователей с заполненной анкетой"""
    buttons = [
        [
            InlineKeyboardButton(
                text="📝 Заполнить новую анкету",
                callback_data="main_menu_fill_application"
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️ Редактировать анкету",
                callback_data="main_menu_edit_profile"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔍 Проверить статус заявки",
                callback_data="main_menu_check_status"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_owner_panel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура панели владельца"""
    buttons = [
        [
            InlineKeyboardButton(text="👤 Админы", callback_data="owner_admins"),
            InlineKeyboardButton(text="🚫 Черный список", callback_data="owner_blacklist")
        ],
        [
            InlineKeyboardButton(text="🔍 Проверка", callback_data="owner_check"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="owner_stats")
        ],
        [
            InlineKeyboardButton(text="📢 Журнал", callback_data="owner_journal"),
            InlineKeyboardButton(text="⚡ Триггеры", callback_data="owner_triggers")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_admin_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления администраторами"""
    buttons = [
        [
            InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add"),
            InlineKeyboardButton(text="➖ Удалить", callback_data="admin_remove")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_blacklist_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления черным списком"""
    buttons = [
        [
            InlineKeyboardButton(text="📋 Список", callback_data="blacklist_list"),
            InlineKeyboardButton(text="➕ Добавить", callback_data="blacklist_add")
        ],
        [
            InlineKeyboardButton(text="➖ Удалить", callback_data="blacklist_remove"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_blacklist_pagination_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура для пагинации черного списка"""
    buttons = []
    
    # Навигационные кнопки
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️ Предыдущая",
                callback_data=f"blacklist_page_{current_page - 1}"
            )
        )
    if current_page + 1 < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Следующая ▶️",
                callback_data=f"blacklist_page_{current_page + 1}"
            )
        )
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Кнопки действий
    buttons.append([
        InlineKeyboardButton(
            text="➕ Добавить",
            callback_data="blacklist_add"
        ),
        InlineKeyboardButton(
            text="➖ Удалить",
            callback_data="blacklist_remove"
        )
    ])
    
    # Кнопка назад
    buttons.append([
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="owner_blacklist"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_blacklist_list_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для списка черного списка"""
    buttons = [
        [
            InlineKeyboardButton(
                text="📋 Обновить список",
                callback_data="blacklist_list"
            )
        ],
        [
            InlineKeyboardButton(
                text="➕ Добавить",
                callback_data="blacklist_add"
            ),
            InlineKeyboardButton(
                text="➖ Удалить",
                callback_data="blacklist_remove"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="owner_blacklist"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_trigger_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления триггерами"""
    buttons = [
        [
            InlineKeyboardButton(text="✨ Создать", callback_data="trigger_create"),
            InlineKeyboardButton(text="📋 Список", callback_data="trigger_list")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_journal_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления журналом"""
    buttons = [
        [
            InlineKeyboardButton(
                text="🔌 Подключить канал",
                callback_data="journal_connect"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔍 Тест",
                callback_data="journal_test"
            ),
            InlineKeyboardButton(
                text="❌ Отключить",
                callback_data="journal_disconnect"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="admin_back"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_survey_keyboard(options: list, row_width: int = 2) -> InlineKeyboardMarkup:
    """Создание клавиатуры для опроса из списка опций"""
    builder = InlineKeyboardBuilder()
    for option in options:
        builder.button(text=option, callback_data=f"survey_{option.lower()}")
    builder.adjust(row_width)
    return builder.as_markup()


def create_exit_push_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пуш-уведомления при выходе (п.6.2 ТЗ)"""
    buttons = [
        [
            InlineKeyboardButton(
                text="💗 Вернуться в чат",
                callback_data="return_to_chat"
            )
        ],
        [
            InlineKeyboardButton(
                text="📝 Пройти опрос",
                callback_data="continue_survey"
            ),
            InlineKeyboardButton(
                text="❌ Не хочу",
                callback_data="decline_survey"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_return_chat_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для возврата в чат внутри опроса"""
    buttons = [
        [
            InlineKeyboardButton(
                text="💗 Вернуться в чат",
                callback_data="return_to_chat"
            )
        ],
        [
            InlineKeyboardButton(
                text="⏩ Продолжить",
                callback_data="continue_survey"
            ),
            InlineKeyboardButton(
                text="❌ Не хочу",
                callback_data="decline_survey"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_invite_friends_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для приглашения друзей"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🤝 Пригласить друга",
        switch_inline_query="Присоединяйся к Pulse 4ever! 🎉"
    ))
    return builder.as_markup()


def create_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для отмены действия"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel_action"
    ))
    return builder.as_markup()


def create_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения действия"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_action"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="back"
    ))
    return builder.as_markup()


def create_empty_keyboard() -> ReplyKeyboardRemove:
    """Пустая клавиатура (удаляет текущую)"""
    return ReplyKeyboardRemove()


# Алиас для обратной совместимости
create_admin_keyboard = create_admin_reply_keyboard