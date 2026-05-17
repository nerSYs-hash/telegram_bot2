"""V1.17.0h: флаг connect-flow lifecycle (зеркало bot_core/login_button.py).

OFF по умолчанию = строго байт-в-байт: hard-delete bot_chats,
старый connect-flow, get_workspace_by_chat/delete_workspace без изменений.
"""
import os

_TRUTHY = {"1", "true", "yes", "on"}


def connect_flow_v2_enabled() -> bool:
    return os.getenv("CONNECT_FLOW_V2", "").strip().lower() in _TRUTHY
