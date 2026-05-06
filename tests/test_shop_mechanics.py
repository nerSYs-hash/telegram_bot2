import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_apply_title_promotes_with_manage_chat():
    """promote_chat_member must be called with can_manage_chat=True."""
    context = MagicMock()
    context.bot.promote_chat_member = AsyncMock(return_value=True)
    context.bot.set_chat_administrator_custom_title = AsyncMock(return_value=True)

    from handlers.shop_mechanics import apply_title_to_user
    result = await apply_title_to_user(context, -1001234567890, 12345, "Спикер")

    assert result is True
    kwargs = context.bot.promote_chat_member.call_args.kwargs
    assert kwargs.get('can_manage_chat') is True, f"can_manage_chat must be True, got: {kwargs}"
    context.bot.set_chat_administrator_custom_title.assert_awaited_once_with(
        chat_id=-1001234567890, user_id=12345, custom_title="Спикер"
    )


@pytest.mark.asyncio
async def test_apply_title_returns_false_on_telegram_error():
    """Returns False when Telegram API raises."""
    context = MagicMock()
    context.bot.promote_chat_member = AsyncMock(side_effect=Exception("TG error"))
    context.bot.set_chat_administrator_custom_title = AsyncMock()

    from handlers.shop_mechanics import apply_title_to_user
    result = await apply_title_to_user(context, -1001234567890, 12345, "Спикер")

    assert result is False
