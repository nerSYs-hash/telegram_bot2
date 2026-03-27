#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Наложение VIP-бейджа на фото анкеты BBS.
Бейдж накладывается в правый верхний угол.
"""

import io
import os
import logging
from PIL import Image

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VIP_BADGE_PATH = os.path.join(_BASE_DIR, 'assets', 'vip_badge.png')

# Кеш бейджа (загружаем один раз)
_badge_cache = None


def _load_badge():
    """Загружает VIP-бейдж из файла (с кешем)."""
    global _badge_cache
    if _badge_cache is not None:
        return _badge_cache
    try:
        img = Image.open(VIP_BADGE_PATH).convert('RGBA')
        # Убираем полупрозрачные артефакты — alpha < 128 → полностью прозрачный
        pixels = img.load()
        w, h = img.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if a < 128:
                    pixels[x, y] = (0, 0, 0, 0)
        _badge_cache = img
        return _badge_cache
    except Exception as e:
        logger.error(f"VIP badge load error: {e}")
        return None


async def apply_vip_badge(bot, photo_file_id: str, badge_ratio: float = 0.25) -> bytes:
    """
    Скачивает фото по file_id, накладывает VIP-бейдж в правый верхний угол.

    Args:
        bot: экземпляр telegram.Bot
        photo_file_id: file_id фото из Telegram
        badge_ratio: размер бейджа относительно ширины фото (0.25 = 25%)

    Returns:
        bytes — обработанное фото в формате JPEG
    """
    badge = _load_badge()
    if badge is None:
        # Если бейдж не загрузился — возвращаем оригинал
        file = await bot.get_file(photo_file_id)
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        return buf.getvalue()

    # Скачиваем фото
    file = await bot.get_file(photo_file_id)
    photo_buf = io.BytesIO()
    await file.download_to_memory(photo_buf)
    photo_buf.seek(0)

    # Открываем и накладываем
    photo = Image.open(photo_buf).convert('RGBA')
    pw, ph = photo.size

    # Масштабируем бейдж
    badge_size = int(pw * badge_ratio)
    resized_badge = badge.resize((badge_size, badge_size), Image.LANCZOS)

    # Позиция: правый верхний угол
    x = pw - badge_size
    y = 0

    # Накладываем с прозрачностью
    photo.paste(resized_badge, (x, y), resized_badge)

    # Конвертируем в RGB (JPEG не поддерживает альфа)
    result = photo.convert('RGB')
    out_buf = io.BytesIO()
    result.save(out_buf, format='JPEG', quality=92)
    out_buf.seek(0)
    return out_buf.getvalue()
