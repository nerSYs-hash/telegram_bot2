#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Механики активных товаров из черного рынка.
Обработка срабатывания услуг во время использования бота.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# TITLE - Кастомный титул с админскими правами
# ════════════════════════════════════════════════════════════════════════════════

async def apply_title_to_user(context, chat_id: int, user_id: int, title_text: str) -> bool:
    """Выдаёт серый кастомный титул пользователю.

    Три шага (Telegram требует именно такой порядок):
    1. Назначить минимальным админом — иначе set_chat_administrator_custom_title отказывает.
    2. Установить текст титула.
    3. Снять права — титул остаётся серым, зелёный тег исчезает.
    """
    try:
        # Шаг 1: временно назначить админом (нужно для установки титула)
        await context.bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            can_manage_chat=True,
            can_post_messages=False,
            can_edit_messages=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
            can_manage_video_chats=False,
        )

        # Шаг 2: установить текст титула
        await context.bot.set_chat_administrator_custom_title(
            chat_id=chat_id,
            user_id=user_id,
            custom_title=title_text
        )

        # Шаг 3: снять права → титул становится серым, юзер не admin.
        # Передаём только can_manage_chat=False: channel-only параметры
        # (can_post_messages, can_edit_messages) вызывают BadRequest в супергруппе
        # при полном снятии прав.
        await context.bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            can_manage_chat=False,
        )

        logger.info(f"✅ Title applied (grey): user={user_id}, title={title_text}")
        return True
    except Exception as e:
        logger.error(f"Error applying title: {e}")
        return False


async def remove_title_from_user(context, chat_id: int, user_id: int) -> bool:
    """Снимает админские права и кастомный титул (когда истекает срок)."""
    try:
        await context.bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            is_anonymous=False
        )
        
        logger.info(f"✅ Title removed: user={user_id}")
        return True
    except Exception as e:
        logger.error(f"Error removing title: {e}")
        return False


# ════════════════════════════════════════════════════════════════════════════════
# CHECK SERVICES - Проверка активных услуг пользователя
# ════════════════════════════════════════════════════════════════════════════════

def get_active_services(db, user_id: int) -> dict:
    """Получить все активные услуги пользователя с проверкой сроков."""
    import time
    
    try:
        db.cursor.execute('''
            SELECT id, service_type, status, expires_at, content, start_time
            FROM marketplace_services
            WHERE user_id = ? AND status = 'active'
        ''', (user_id,))
        
        services = {}
        for row in db.cursor.fetchall():
            service_type = row['service_type']
            expires_at = row['expires_at']
            
            # Проверяем просроченные услуги
            if expires_at:
                try:
                    if float(expires_at) < time.time():
                        # Услуга истекла, пропускаем
                        continue
                except:
                    pass
            
            services[service_type] = {
                'id': row['id'],
                'status': row['status'],
                'expires_at': expires_at,
                'content': row['content'],
                'start_time': row['start_time']
            }
        
        return services
    except Exception as e:
        logger.error(f"Error getting active services: {e}")
        return {}


async def cleanup_expired_titles(context, db, chat_id: int):
    """Проверяет и снимает админские права при истечении титула.
    Должна вызваться периодически через scheduler.
    """
    import time
    
    try:
        current_time = time.time()
        
        # Получаем все истекшие титулы
        db.cursor.execute('''
            SELECT user_id, content FROM marketplace_services
            WHERE service_type = 'title' AND status = 'active'
            AND expires_at IS NOT NULL AND expires_at < ?
        ''', (current_time,))
        
        expired_titles = db.cursor.fetchall()
        
        for row in expired_titles:
            user_id = row['user_id']
            title_text = row['content']
            
            # Снимаем админские права
            success = await remove_title_from_user(context, chat_id, user_id)
            
            if success:
                # Отмечаем в БД как истекшие
                db.cursor.execute('''
                    UPDATE marketplace_services
                    SET status = 'expired'
                    WHERE user_id = ? AND service_type = 'title' AND status = 'active'
                    AND expires_at < ?
                ''', (user_id, current_time))
                db.conn.commit()
                
                logger.info(f"🔄 Title expired and removed: user={user_id}, title={title_text}")
    
    except Exception as e:
        logger.error(f"Error cleaning up expired titles: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# ENTRANCE - Глашатай (первое сообщение за день)
# ════════════════════════════════════════════════════════════════════════════════

def should_announce_entrance(db, user_id: int) -> bool:
    """Проверить, нужно ли объявлять вход пользователя."""
    from utils.helpers import get_moscow_time
    
    services = get_active_services(db, user_id)
    if 'entrance' not in services:
        return False
    
    # Проверяем, есть ли уже сообщение этого пользователя сегодня
    today, = get_moscow_time().strftime('%Y-%m-%d'),
    
    try:
        db.cursor.execute('''
            SELECT COUNT(*) as cnt FROM messages
            WHERE user_id = ? AND DATE(created_at) = ?
        ''', (user_id, today))
        
        row = db.cursor.fetchone()
        count = row['cnt'] if row else 0
        
        # Если это первое сообщение за день - объявляем!
        return count == 1
    except:
        return False


# ════════════════════════════════════════════════════════════════════════════════
# PRANK - Ядовитый плевок (пранк с подменой сообщения)
# ════════════════════════════════════════════════════════════════════════════════

def get_pending_prank(db, victim_id: int):
    """Проверить, есть ли активный пранк на этого пользователя."""
    try:
        db.cursor.execute('''
            SELECT id, user_id, content, status
            FROM marketplace_services
            WHERE content LIKE ?
            AND status = 'pending'
            LIMIT 1
        ''', (f'%victim_id:{victim_id}%',))
        
        return db.cursor.fetchone()
    except:
        return None


def mark_prank_used(db, prank_id: int):
    """Отметить пранк как использованный."""
    try:
        db.cursor.execute('''
            UPDATE marketplace_services
            SET status = 'used'
            WHERE id = ?
        ''', (prank_id,))
        db.conn.commit()
    except Exception as e:
        logger.error(f"Error marking prank as used: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# LUCK PAW - Лапка на удачу (увеличение крита)
# ════════════════════════════════════════════════════════════════════════════════

def get_critical_multiplier(db, user_id: int) -> dict:
    """Получить шанс и множитель критического удара."""
    services = get_active_services(db, user_id)
    
    base_chance = 0.02  # 2%
    base_multiplier = 10  # x10
    
    if 'luck_paw' in services:
        # С буфом - 15% шанс на x10
        return {
            'chance': 0.15,
            'multiplier': 10,
            'has_buff': True
        }
    
    return {
        'chance': base_chance,
        'multiplier': base_multiplier,
        'has_buff': False
    }


def apply_critical_hit(db, user_id: int, base_reward: float) -> tuple[float, bool]:
    """Применить критический удар если сработал."""
    import random
    
    crit_info = get_critical_multiplier(db, user_id)
    
    if random.random() < crit_info['chance']:
        crit_reward = base_reward * crit_info['multiplier']
        return crit_reward, crit_info['has_buff']
    
    return base_reward, False


# ════════════════════════════════════════════════════════════════════════════════
# VIP TOP - Украшение ника в топах и списках
# ════════════════════════════════════════════════════════════════════════════════

def format_vip_name(name: str, db, user_id: int) -> str:
    """Отформатировать имя с VIP-украшением если активно."""
    services = get_active_services(db, user_id)
    
    if 'vip_top' in services:
        return f"🌟 ꧁ {name} ꧂ 🌟"
    
    return name


# ════════════════════════════════════════════════════════════════════════════════
# TITLE - Кастомный титул
# ════════════════════════════════════════════════════════════════════════════════

def get_user_title(db, user_id: int) -> str:
    """Получить кастомный титул пользователя если активен."""
    services = get_active_services(db, user_id)
    
    if 'title' in services:
        # content хранит текст титула
        title_text = services['title'].get('content', '[TITUL]')
        return f"[{title_text}]"
    
    return ""


# ════════════════════════════════════════════════════════════════════════════════
# TOAD SKIN - Жабья шкура (анонимные сообщения)
# ════════════════════════════════════════════════════════════════════════════════

def get_anon_messages_left(db, user_id: int) -> int:
    """Получить количество оставшихся анонимных сообщений."""
    try:
        db.cursor.execute('''
            SELECT content FROM marketplace_services
            WHERE user_id = ? AND service_type = 'toad_skin' AND status = 'active'
            LIMIT 1
        ''', (user_id,))
        
        row = db.cursor.fetchone()
        if row and row['content']:
            # Format: anon_msgs_left:3
            parts = row['content'].split(':')
            if len(parts) == 2:
                return int(parts[1])
        
        return 0
    except:
        return 0


def use_anon_message(db, user_id: int) -> bool:
    """Использовать одно анонимное сообщение. Вернуть True если есть еще."""
    try:
        left = get_anon_messages_left(db, user_id)
        if left > 0:
            left -= 1
            if left > 0:
                # Обновляем счетчик
                db.cursor.execute('''
                    UPDATE marketplace_services
                    SET content = ?
                    WHERE user_id = ? AND service_type = 'toad_skin' AND status = 'active'
                ''', (f'anon_msgs_left:{left}', user_id))
            else:
                # Последнее сообщение - помечаем как использованную
                db.cursor.execute('''
                    UPDATE marketplace_services
                    SET status = 'used'
                    WHERE user_id = ? AND service_type = 'toad_skin' AND status = 'active'
                ''', (user_id,))
            
            db.conn.commit()
            return left > 0
        
        return False
    except Exception as e:
        logger.error(f"Error using anon message: {e}")
        return False


# ════════════════════════════════════════════════════════════════════════════════
# BOUNTY - Заказ за голову (охота)
# ════════════════════════════════════════════════════════════════════════════════

def get_active_bounty(db) -> dict:
    """Получить активный заказ за голову (если есть)."""
    try:
        db.cursor.execute('''
            SELECT id, user_id, content, status, start_time
            FROM marketplace_services
            WHERE service_type = 'bounty' AND status = 'active'
            LIMIT 1
        ''')
        
        row = db.cursor.fetchone()
        if row:
            # content формат: victim_id:12345
            if ':' in row['content']:
                victim_id = int(row['content'].split(':')[1])
                return {
                    'id': row['id'],
                    'buyer_id': row['user_id'],
                    'victim_id': victim_id,
                    'status': row['status']
                }
        
        return {}
    except:
        return {}


def reward_bounty_hunter(db, hunter_id: int, bounty_price: int):
    """Дать награду охотнику за голову."""
    try:
        # Охотник получает куш
        reward = bounty_price * 2  # Двойная стоимость заказа
        db.update_user_balance(hunter_id, reward, 'add')
        db.update_bank_balance(reward, 'subtract')
        db.add_transaction(
            None, hunter_id, reward,
            'bounty_reward',
            'Награда за охоту на голову'
        )
        
        logger.info(f"Bounty reward: {hunter_id} got {reward} 💎")
    except Exception as e:
        logger.error(f"Error rewarding bounty hunter: {e}")


def penalize_bounty_victim(db, victim_id: int):
    """Штрафовать жертву заказа."""
    try:
        penalty = 50
        db.update_user_balance(victim_id, penalty, 'subtract')
        db.update_bank_balance(penalty, 'add')
        db.add_transaction(
            victim_id, None, penalty,
            'bounty_penalty',
            'Штраф за охоту на голову'
        )
        
        logger.info(f"Bounty penalty: {victim_id} lost {penalty} 💎")
    except Exception as e:
        logger.error(f"Error penalizing bounty victim: {e}")


def close_bounty(db, bounty_id: int):
    """Закрыть заказ за голову."""
    try:
        db.cursor.execute('''
            UPDATE marketplace_services
            SET status = 'used'
            WHERE id = ?
        ''', (bounty_id,))
        db.conn.commit()
    except Exception as e:
        logger.error(f"Error closing bounty: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# VOICE ABOVE - Голос свыше (анонимный рупор)
# ════════════════════════════════════════════════════════════════════════════════

def has_voice_above(db, user_id: int) -> bool:
    """Проверить, куплен ли "Голос свыше"."""
    try:
        db.cursor.execute('''
            SELECT id FROM marketplace_services
            WHERE user_id = ? AND service_type = 'voice_above' AND status = 'pending'
        ''', (user_id,))
        
        return db.cursor.fetchone() is not None
    except:
        return False


def publish_voice_above(db, user_id: int, text: str) -> bool:
    """Опубликовать сообщение через 'Голос свыше'."""
    try:
        db.cursor.execute('''
            UPDATE marketplace_services
            SET status = 'used', content = ?
            WHERE user_id = ? AND service_type = 'voice_above' AND status = 'pending'
        ''', (text, user_id))
        
        db.conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error publishing voice above: {e}")
        return False


# ════════════════════════════════════════════════════════════════════════════════
# RP COMMANDS - Ролевые команды (команды привета)
# ════════════════════════════════════════════════════════════════════════════════

def has_rp_commands(db, user_id: int) -> bool:
    """Проверить, куплены ли ролевые команды."""
    services = get_active_services(db, user_id)
    return 'rp_cmds' in services


# ════════════════════════════════════════════════════════════════════════════════
# NEON SKIN - Скин профиля "Неоновое Болото"
# ════════════════════════════════════════════════════════════════════════════════

def has_neon_skin(db, user_id: int) -> bool:
    """Проверить, есть ли скин профиля."""
    try:
        db.cursor.execute('''
            SELECT id FROM marketplace_services
            WHERE user_id = ? AND service_type = 'neon_skin' AND status = 'active'
        ''', (user_id,))
        
        return db.cursor.fetchone() is not None
    except:
        return False


# ════════════════════════════════════════════════════════════════════════════════
# VIP BBS - VIP-Анкета в BBS (Знакомства)
# ════════════════════════════════════════════════════════════════════════════════

def should_republish_bbs(db, user_id: int) -> bool:
    """Проверить, нужно ли пересчёт переопубликовать анкету."""
    try:
        db.cursor.execute('''
            SELECT id FROM marketplace_services
            WHERE user_id = ? AND service_type = 'vip_bbs' AND content = 'bbs_repub_sent'
        ''', (user_id,))
        
        return db.cursor.fetchone() is not None
    except:
        return False


# ════════════════════════════════════════════════════════════════════════════════
# UTILITIES - Вспомогательные функции
# ════════════════════════════════════════════════════════════════════════════════

def cleanup_expired_services(db, user_id: int):
    """Очистить истекшие услуги (маркировать как 'expired')."""
    import time
    
    try:
        current_time = time.time()
        db.cursor.execute('''
            UPDATE marketplace_services
            SET status = 'expired'
            WHERE user_id = ? AND status = 'active' 
              AND expires_at IS NOT NULL AND expires_at < ?
        ''', (user_id, current_time))
        
        db.conn.commit()
    except Exception as e:
        logger.error(f"Error cleaning up expired services: {e}")


def get_service_remaining_time(expires_at) -> str:
    """Получить оставшееся время для услуги."""
    import time
    
    if not expires_at:
        return "∞ (Навсегда)"
    
    try:
        remaining = float(expires_at) - time.time()
        if remaining <= 0:
            return "Истекла"
        
        days = int(remaining // 86400)
        hours = int((remaining % 86400) // 3600)
        
        if days > 0:
            return f"{days}ч {hours}м"
        elif hours > 0:
            minutes = int((remaining % 3600) // 60)
            return f"{hours}ч {minutes}м"
        else:
            minutes = int(remaining // 60)
            return f"{minutes}м"
    except:
        return "?"
