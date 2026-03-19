#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Расчёт майнинга, активности и лотереи."""

import math


def calculate_mining_reward(active_core_count, difficulty_k=5.0):
    """
    Calculate mining reward based on active core
    Formula: K / sqrt(Active Core)
    """
    if active_core_count == 0:
        active_core_count = 1
    
    reward = difficulty_k / math.sqrt(active_core_count)
    return round(reward, 2)

def calculate_message_quality_score_A(word_count=0, char_count=0, is_reply=False,
                                      is_media=False, mentions_count=0):
    """
    Фактор A: качество текущего сообщения.
    Возвращает значение 0.0–1.0.
    """
    score = 0.0

    # Слова (макс 0.40)
    if word_count >= 20:
        score += 0.40
    elif word_count >= 10:
        score += 0.25
    elif word_count >= 3:
        score += 0.10
    # < 3 слов → 0 (штраф через отсутствие бонуса)

    # Символы — дополнительный бонус за длину (макс 0.15)
    if char_count >= 150:
        score += 0.15
    elif char_count >= 60:
        score += 0.07

    # Ответ на чужое сообщение (0.25)
    if is_reply:
        score += 0.25

    # Медиа (0.15)
    if is_media:
        score += 0.15

    # Упоминания (макс 0.05)
    if mentions_count > 0:
        score += min(mentions_count * 0.025, 0.05)

    return round(min(score, 1.0), 4)


def calculate_historical_score_B(avg_daily_messages_7d):
    """
    Фактор B: историческая активность за 7 дней.
    avg_daily_messages_7d — среднее сообщений в день за 7 дней.
    Возвращает значение 0.0–1.0.
    
    Шкала:
      0  сообщ/день → 0.0
      3  сообщ/день → 0.3
      7  сообщ/день → 0.6
      15+ сообщ/день → 1.0
    """
    if avg_daily_messages_7d <= 0:
        return 0.0
    return round(min(avg_daily_messages_7d / 15.0, 1.0), 4)


def calculate_combined_quality_multiplier(score_A, score_B):
    """
    Комбинированный множитель качества.
    
    Формула: 0.5 + (0.6×A + 0.4×B) × 0.8
    Диапазон: ×0.5 (минимум) – ×1.3 (максимум)
    """
    combined = 0.6 * score_A + 0.4 * score_B
    multiplier = 0.5 + combined * 0.8
    return round(max(0.5, min(1.3, multiplier)), 3)


def calculate_user_activity_score(user_stats, chat_stats):
    """
    Calculate user activity score (АктП) based on formula
    """
    if not chat_stats or chat_stats['total_messages'] == 0:
        return 0.0
    
    score = 0.0
    
    # 1. ОКСП - Total characters (1%)
    if user_stats.get('total_chars', 0) > 0 and chat_stats.get('total_chars', 0) > 0:
        score += 0.01 * (chat_stats['total_chars'] / user_stats['total_chars'])
    
    # 2. СДСП - Average message length (7%)
    user_avg_len = user_stats.get('total_chars', 0) / max(user_stats.get('total_messages', 1), 1)
    chat_avg_len = chat_stats.get('total_chars', 0) / max(chat_stats.get('total_messages', 1), 1)
    if user_avg_len > 0 and chat_avg_len > 0:
        score += 0.07 * (chat_avg_len / user_avg_len)
    
    # 3. КСП - Word count (1%)
    if user_stats.get('total_words', 0) > 0 and chat_stats.get('total_words', 0) > 0:
        score += 0.01 * (chat_stats['total_words'] / user_stats['total_words'])
    
    # 4. КОРП - Reactions given (8%)
    if user_stats.get('reactions_given', 0) > 0 and chat_stats.get('total_reactions', 0) > 0:
        score += 0.08 * (chat_stats['total_reactions'] / user_stats['reactions_given'])
    
    # 5. КПРП - Reactions received (8%)
    if user_stats.get('reactions_received', 0) > 0 and chat_stats.get('total_reactions', 0) > 0:
        score += 0.08 * (chat_stats['total_reactions'] / user_stats['reactions_received'])
    
    # 6. КОПЮП - Replies received (20%)
    if user_stats.get('replies_received', 0) > 0 and chat_stats.get('total_replies', 0) > 0:
        score += 0.20 * (chat_stats['total_replies'] / user_stats['replies_received'])
    
    # 7. КОПЯП - Replies sent (20%)
    if user_stats.get('replies_sent', 0) > 0 and chat_stats.get('total_replies', 0) > 0:
        score += 0.20 * (chat_stats['total_replies'] / user_stats['replies_sent'])
    
    # 8. КУПП - Mentions received (20%)
    if user_stats.get('mentions_received', 0) > 0 and chat_stats.get('total_mentions', 0) > 0:
        score += 0.20 * (chat_stats['total_mentions'] / user_stats['mentions_received'])
    
    # 9. МедиаП - Media sent (7%)
    if user_stats.get('media_sent', 0) > 0 and chat_stats.get('total_media', 0) > 0:
        score += 0.07 * (chat_stats['total_media'] / user_stats['media_sent'])
    
    # 10. ПИВДВП - Other threads posts (8%)
    if user_stats.get('other_threads_posts', 0) > 0 and chat_stats.get('other_threads_posts', 0) > 0:
        score += 0.08 * (chat_stats['other_threads_posts'] / user_stats['other_threads_posts'])
    
    # 11. ПЗП - Warnings penalty (REMOVED - no longer affects activity)
    # Warnings are tracked but do NOT reduce activity score
    
    return round(score, 2)

def calculate_heat_multiplier(messages_last_10min, avg_per_10min):
    """
    "Тепловой" множитель — реагирует на текущую активность чата.
    
    Сравнивает сообщений за последние 10 минут со средним за 10 минут.
    
    Диапазон: ×0.85 (тихий чат) – ×1.15 (горячий чат)
    
    Шкала:
      messages < 0.3 × avg  → ×0.85  (очень тихо)
      messages < 0.7 × avg  → ×0.92  (ниже нормы)
      messages ≈ avg        → ×1.00  (норма)
      messages > 1.5 × avg  → ×1.08  (активно)
      messages > 2.5 × avg  → ×1.15  (горячо)
    """
    if avg_per_10min <= 0:
        return 1.0  # нет истории — нейтрально

    ratio = messages_last_10min / avg_per_10min

    if ratio >= 2.5:
        return 1.15
    elif ratio >= 1.5:
        return 1.08
    elif ratio >= 0.7:
        return 1.00
    elif ratio >= 0.3:
        return 0.92
    else:
        return 0.85


def calculate_lottery_chances(user_tickets, total_tickets):
    """Calculate lottery winning chances"""
    if total_tickets == 0:
        return 0.0
    return round((user_tickets / total_tickets) * 100, 2)
