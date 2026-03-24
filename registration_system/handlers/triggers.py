import logging
import random
import json
from aiogram import Router, F
from aiogram.types import Message

from database import get_enabled_triggers, increment_violation, reset_violations
from constants import TriggerConditions, TriggerActions, TriggerTarget, UserRole

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def process_triggers(message: Message):
    if not message.text:
        return
        
    triggers = await get_enabled_triggers()
    text = message.text.lower()
    
    for trigger in triggers:
        # Проверка вероятности
        if random.randint(1, 100) > trigger['probability']:
            continue
            
        # Проверка условий
        keywords = trigger['keywords'].lower().split(',')
        match = False
        
        condition = trigger['condition']
        if condition == TriggerConditions.EXACT:
            match = any(kw.strip() == text for kw in keywords)
        elif condition == TriggerConditions.CONTAINS:
            match = any(kw.strip() in text for kw in keywords)
        elif condition == TriggerConditions.STARTS_WITH:
            match = any(text.startswith(kw.strip()) for kw in keywords)
        elif condition == TriggerConditions.ENDS_WITH:
            match = any(text.endswith(kw.strip()) for kw in keywords)
        
        if not match:
            continue
            
        # Выполнение действий
        actions = json.loads(trigger['actions'])
        for action_type, action_value in actions.items():
            try:
                if action_type == TriggerActions.SEND_CHAT_MESSAGE:
                    await message.answer(action_value)
                elif action_type == TriggerActions.DELETE_MESSAGE:
                    await message.delete()
                elif action_type == TriggerActions.MUTE:
                    # Логика мута (нужны права админа)
                    pass
                elif action_type == TriggerActions.KICK:
                    await message.chat.ban(message.from_user.id)
            except Exception as e:
                logger.error(f"Failed to execute trigger action {action_type}: {e}")
                
        # Накопительные действия
        if trigger['cumulative_enabled']:
            count = await increment_violation(message.from_user.id, trigger['id'])
            if count >= trigger['cumulative_threshold']:
                # Выполняем финальное действие
                final_action = trigger['cumulative_final_action']
                if final_action == TriggerActions.KICK:
                    await message.chat.ban(message.from_user.id)
                # Сбрасываем счетчик если нужно
                if trigger['cumulative_reset'] == 'after_action':
                    await reset_violations(message.from_user.id, trigger['id'])