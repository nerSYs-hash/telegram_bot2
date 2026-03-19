#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Утилиты для анализа сообщений."""


def is_media_message(message):
    """Check if message contains media"""
    return any([
        message.photo,
        message.video,
        message.animation,  # GIF
        message.voice,
        message.video_note,  # Video circle
        message.audio,
        message.document,
        message.sticker,
        bool(message.entities and any(e.type == 'url' for e in message.entities))
    ])

def count_words(text):
    """Count words in text"""
    if not text:
        return 0
    return len(text.split())
