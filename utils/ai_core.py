#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import aiohttp
import logging

logger = logging.getLogger(__name__)

async def ask_ai(prompt: str) -> str:
    """Отправляет запрос к нейросети и возвращает текстовый ответ."""
    api_key = os.getenv("AI_API_KEY")
    api_base = os.getenv("AI_API_BASE", "https://openrouter.ai/api/v1/chat/completions")
    model = os.getenv("AI_MODEL", "llama3-70b-8192")

    if not api_key:
        return "❌ Ошибка: API ключ для ИИ не настроен в файле .env!"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Системный промпт — здесь задается характер бота!
    system_prompt = (
        "Ты — умный, ироничный и дружелюбный ИИ-ассистент в Telegram-чате Pulse. "
        "Отвечай кратко, емко и используй эмодзи. Общайся с пользователем как хороший друг."
    )

    payload = {
        "model": model,
        "messages":[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_base, headers=headers, json=payload, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                else:
                    error_text = await resp.text()
                    logger.error(f"Ошибка ИИ: {resp.status} - {error_text}")
                    return "❌ ИИ сейчас отдыхает (ошибка сервера). Попробуйте позже!"
    except Exception as e:
        logger.error(f"Сбой подключения к ИИ: {e}")
        return "❌ Не удалось связаться с мозговым центром ИИ."