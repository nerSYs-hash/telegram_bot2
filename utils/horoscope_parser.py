#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Гибридный парсер гороскопов.
Берет НАСТОЯЩИЙ прогноз из XML-ленты астрологов (Ignio) 
и добавляет локальный колорит чата Pulse.
"""

import aiohttp
import xml.etree.ElementTree as ET
import random
import logging

logger = logging.getLogger(__name__)



# ────────────────────────────────────────
# Резервные тексты, если сайт астрологов вдруг сломается
BACKUP_TEXTS = {
    'aries': "День требует активности и решительных действий.",
    'taurus': "Сегодня лучше не торопиться и всё тщательно взвесить.",
    'gemini': "Отличный день для общения и получения новой информации.",
    'cancer': "Доверяйте своей интуиции, она сегодня вас не подведет.",
    'leo': "Вы в центре внимания! Используйте это обаяние в своих целях.",
    'virgo': "Мелочи сегодня решают всё. Будьте внимательны к деталям.",
    'libra': "Постарайтесь найти баланс между работой и отдыхом.",
    'scorpio': "Ваша проницательность поможет раскрыть любые секреты.",
    'sagittarius': "День хорош для планирования путешествий или обучения.",
    'capricorn': "Упорный труд сегодня принесет отличные результаты.",
    'aquarius': "Нестандартный подход поможет решить старую проблему.",
    'pisces': "Эмоциональный фон повышен, уделите время творчеству."
}

async def get_all_horoscopes(signs_list, tomorrow: bool = False):
    """
    Скачивает реальный XML-гороскоп без лишних добавлений.
    tomorrow=True — берёт тег <tomorrow> вместо <today>.
    """
    tag = 'tomorrow' if tomorrow else 'today'
    logger.info(f"🔮 Скачиваю свежий гороскоп от астрологов (тег: {tag})...")
    horoscopes = {}

    # Ссылка на бесплатный XML-канал гороскопов (работает всегда)
    url = "https://ignio.com/r/export/utf/xml/daily/com.xml"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    xml_data = await resp.text()
                    root = ET.fromstring(xml_data)

                    for sign in signs_list:
                        slug = sign['slug']
                        sign_node = root.find(slug)

                        if sign_node is not None:
                            node = sign_node.find(tag)
                            if node is None or not node.text:
                                node = sign_node.find('today')
                            text = node.text.strip() if (node is not None and node.text) else BACKUP_TEXTS.get(slug, "Нет данных")
                            horoscopes[slug] = text
                        else:
                            horoscopes[slug] = BACKUP_TEXTS.get(slug, "Нет данных")

                    logger.info("✅ Настоящий гороскоп успешно скачан и собран!")
                    return horoscopes
                else:
                    logger.error(f"❌ Ошибка сайта гороскопов: {resp.status}")
    except Exception as e:
        logger.error(f"❌ Ошибка парсинга XML: {e}")

    for sign in signs_list:
        slug = sign['slug']
        horoscopes[slug] = BACKUP_TEXTS.get(slug, "Звезды сегодня молчат.")

    return horoscopes
    """
    Скачивает реальный XML-гороскоп на сегодня и добавляет совет чата.
    """
    logger.info("🔮 Скачиваю свежий гороскоп от астрологов...")
    horoscopes = {}
    
    # Ссылка на бесплатный XML-канал гороскопов (работает всегда)
    url = "https://ignio.com/r/export/utf/xml/daily/com.xml"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    xml_data = await resp.text()
                    # Парсим XML
                    root = ET.fromstring(xml_data)
                    
                    for sign in signs_list:
                        slug = sign['slug']  # aries, taurus и т.д.
                        sign_node = root.find(slug)
                        
                        if sign_node is not None:
                            # Берем тег <today> из XML
                            today_text = sign_node.find('today').text.strip()
                            
                            # Выбираем случайный совет для чата
                            chat_advice = random.choice(CHAT_ADVICES)
                            
                            # Склеиваем настоящий гороскоп и наш совет
                            final_text = f"{today_text}\n\n<i>💡 Совет в Pulse: {chat_advice}</i>"
                            horoscopes[slug] = final_text
                        else:
                            horoscopes[slug] = BACKUP_TEXTS.get(slug, "---")
                            
                    logger.info("✅ Настоящий гороскоп успешно скачан и собран!")
                    return horoscopes
                else:
                    logger.error(f"❌ Ошибка сайта гороскопов: {resp.status}")
    except Exception as e:
        logger.error(f"❌ Ошибка парсинга XML: {e}")

    # Если сайт астрологов упал, отдаем бэкап с нашими советами
    for sign in signs_list:
        slug = sign['slug']
        horoscopes[slug] = f"{BACKUP_TEXTS.get(slug)}\n\n<i>💡 Совет в Pulse: {random.choice(CHAT_ADVICES)}</i>"

    return horoscopes