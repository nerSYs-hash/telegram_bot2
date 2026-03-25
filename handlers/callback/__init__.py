<<<<<<< HEAD
from .callback_router import CallbackHandler
=======
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handlers/callback/__init__.py — обратная совместимость.

Позволяет старому коду:
    from handlers.callback_handler import CallbackHandler
→   from handlers.callback import CallbackHandler
"""
from handlers.callback.callback_router import CallbackHandler

__all__ = ['CallbackHandler']
>>>>>>> 42e8e40
