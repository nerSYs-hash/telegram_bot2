"""
Обработчики событий для бота Pulse 4ever
Импорт всех роутеров для регистрации в main.py
"""

from .registration import router as registration_router
from .admin import router as admin_router
from .owner import router as owner_router
from .chat_member import router as chat_member_router
from .triggers import router as triggers_router
from .reminder import router as reminder_router
from .exit_survey import router as exit_survey_router
from .reminder_all import router as reminder_all_router

__all__ = [
    'registration_router',
    'admin_router',
    'owner_router',
    'chat_member_router',
    'triggers_router',
    'reminder_router',
    'exit_survey_router',
    'reminder_all_router'
]