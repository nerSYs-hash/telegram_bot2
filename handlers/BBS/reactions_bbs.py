#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Система «Симпатий» BBS — подсчёт уникальных реакций и начисление бонусов.
"""

import logging
from datetime import datetime
from utils.helpers import format_number

# Константы
BBS_BONUS_AMOUNT = 10       # Пульсов автору за 10 реакций
BBS_BONUS_COOLDOWN = 30     # Дней между бонусами автору
AMBASSADOR_REWARD = 20.0    # Награда "Амбассадор Любви" (20 💎)


async def handle_bbs_reaction(reaction_update, context, db, target_chat_id):
    """
    Обработчик реакций для BBS-постов.
    """
    if not reaction_update:
        return False

    message_id = reaction_update.message_id
    user = reaction_update.user
    if not user:
        return False

    try:
        db.cursor.execute(
            'SELECT id, user_id, reaction_count, bonus_paid_at FROM bbs_profiles WHERE message_ids LIKE ?',
            (f'%{message_id}%',)
        )
        profile = db.cursor.fetchone()
    except Exception:
        return False

    if not profile:
        return False

    profile = dict(profile)
    profile_id = profile['id']
    author_id = profile['user_id']

    # Самолайки не считаем
    if user.id == author_id:
        return True

    try:
        # 1. Записываем реакцию в БД
        db.cursor.execute(
            'INSERT OR IGNORE INTO bbs_reactions (profile_id, user_id, message_id) VALUES (?, ?, ?)',
            (profile_id, user.id, message_id),
        )
        
        # Если реакция новая (добавлена впервые)
        if db.cursor.rowcount > 0:
            # Обновляем счетчик симпатий у автора анкеты
            db.cursor.execute(
                "UPDATE bbs_profiles SET reaction_count = reaction_count + 1, updated_at = datetime('now') WHERE id = ?",
                (profile_id,),
            )
            db.conn.commit()
            new_count = profile['reaction_count'] + 1
            logging.info(f"BBS: Profile {profile_id} reaction from {user.id}, total={new_count}")

            # Проверяем бонус для АВТОРА анкеты (за популярность)
            if new_count >= 10:
                await _try_award_bonus(db, profile, author_id)

            # 2. ПРОВЕРЯЕМ СЕКРЕТ "АМБАССАДОР ЛЮБВИ" (Для того, кто поставил лайк)
            # Ищем, есть ли среди поставленных реакций ❤️ или 🔥
            has_love_emoji = False
            for r in reaction_update.new_reaction:
                if getattr(r, 'emoji', '') in ('❤️', '❤', '🔥'):
                    has_love_emoji = True
                    break
            
            if has_love_emoji:
                await _check_ambassador_of_love(db, user, context)

    except Exception as e:
        logging.error(f"BBS: Error processing reaction: {e}")

    return True


async def _check_ambassador_of_love(db, user, context):
    """Скрытая механика: 3 реакции ❤️/🔥 на разные анкеты за 24 часа = +20 💎"""
    
    # 1. Проверяем, получал ли он этот бонус сегодня (защита от абуза)
    db.cursor.execute(
        "SELECT 1 FROM combo_claims WHERE user_id = ? AND combo_name = 'ambassador_of_love' AND date(claimed_at) = date('now')",
        (user.id,)
    )
    if db.cursor.fetchone():
        return  # Сегодня уже получал, выходим

    # 2. Считаем, скольким РАЗНЫМ анкетам он поставил лайк за последние 24 часа
    db.cursor.execute('''
        SELECT COUNT(DISTINCT profile_id) as unique_profiles
        FROM bbs_reactions
        WHERE user_id = ? AND created_at >= datetime('now', '-24 hours')
    ''', (user.id,))
    
    res = db.cursor.fetchone()
    unique_count = res['unique_profiles'] if res else 0

    # 3. Если оценил 3 разные анкеты — выдаем награду!
    if unique_count >= 3:
        bank_balance = db.get_bank_balance()
        if bank_balance < AMBASSADOR_REWARD:
            return
        
        # Начисляем Пульсы
        db.update_user_balance(user.id, AMBASSADOR_REWARD, 'add')
        db.update_bank_balance(AMBASSADOR_REWARD, 'subtract')
        db.add_transaction(None, user.id, AMBASSADOR_REWARD, 'combo_reward', 'Секрет: Амбассадор Любви (BBS)')
        
        # Записываем, что квест на сегодня выполнен
        db.cursor.execute(
            "INSERT INTO combo_claims (user_id, combo_name, reward, claimed_at) VALUES (?, 'ambassador_of_love', ?, datetime('now'))",
            (user.id, AMBASSADOR_REWARD)
        )
        db.conn.commit()
        
        logging.info(f"💖 СЕКРЕТ РАСКРЫТ: user={user.id} стал Амбассадором Любви (+{AMBASSADOR_REWARD} 💎)")
        
        # Отправляем радостное уведомление в ЛС
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=(
                    "🤫 <b>СЕКРЕТ РАСКРЫТ!</b>\n\n"
                    "Вы оценили 3 разные анкеты в BBS!\n"
                    "Скрытый навык <b>«💖 Амбассадор Любви»</b> приносит вам бонус: <b>+20 💎</b>!\n\n"
                    "<i>(Этот секрет можно открывать 1 раз в день)</i>"
                ),
                parse_mode='HTML'
            )
        except Exception:
            pass


async def _try_award_bonus(db, profile, author_id):
    """Начислить бонус автору за популярность анкеты (10 реакций)."""
    last_paid = profile.get('bonus_paid_at')
    if last_paid:
        try:
            if (datetime.now() - datetime.fromisoformat(last_paid)).days < BBS_BONUS_COOLDOWN:
                return
        except Exception:
            pass

    bank_balance = db.get_bank_balance()
    if bank_balance < BBS_BONUS_AMOUNT:
        return

    db.update_user_balance(author_id, BBS_BONUS_AMOUNT, 'add')
    db.update_bank_balance(BBS_BONUS_AMOUNT, 'subtract')
    db.add_transaction(None, author_id, BBS_BONUS_AMOUNT, 'bbs_popularity', 'Популярность BBS')

    now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.cursor.execute('UPDATE bbs_profiles SET bonus_paid_at = ? WHERE user_id = ?', (now_iso, author_id))
    db.conn.commit()
    logging.info(f"BBS: Awarded {BBS_BONUS_AMOUNT} pulses to {author_id}")