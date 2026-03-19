#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import html
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import format_number, get_today_date_msk
from config.emojis import ICON_MONEY_BAG, ICON_ROCKET, ICON_MILITARY_MEDAL

def _ensure_profile_columns(db):
    """Секретный предохранитель: автоматически добавляет нужные колонки в БД, если их еще нет"""
    try:
        db.cursor.execute("ALTER TABLE users ADD COLUMN notifications_enabled INTEGER DEFAULT 1")
    except Exception:
        pass
    try:
        db.cursor.execute("ALTER TABLE bbs_profiles ADD COLUMN hide_age INTEGER DEFAULT 0")
    except Exception:
        pass
    db.conn.commit()


async def show_profile(update_or_query, context, db, user_id):
    """Генерация и отображение Личного кабинета пользователя"""
    
    query = getattr(update_or_query, 'callback_query', None)
    if query:
        user = query.from_user
        send_method = query.edit_message_text
        alert_method = query.answer
    elif hasattr(update_or_query, 'edit_message_text'):
        query = update_or_query
        user = query.from_user
        send_method = query.edit_message_text
        alert_method = query.answer
    else:
        user = update_or_query.message.from_user
        send_method = update_or_query.message.reply_text
        alert_method = update_or_query.message.reply_text

    if not db.is_feature_enabled('profile'):
        await alert_method("⛔️ Личный кабинет временно отключен администрацией.")
        return

    user_data = db.get_user(user_id)
    if not user_data:
        await alert_method("❌ Вы не зарегистрированы. Напишите что-нибудь в чат или нажмите /start.")
        return

    days_in_chat = 0
    joined_at = user_data['joined_at']
    if joined_at:
        try:
            joined_date = datetime.strptime(str(joined_at)[:10], "%Y-%m-%d")
            days_in_chat = (datetime.now() - joined_date).days
        except Exception:
            pass

    try:
        db.cursor.execute('''
            SELECT title_name, emoji FROM titles 
            WHERE user_id = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            ORDER BY granted_at DESC LIMIT 1
        ''', (user_id,))
        title_row = db.cursor.fetchone()
    except Exception:
        title_row = None
    
    status_text = f"[{title_row['emoji']} {title_row['title_name']}]" if title_row else "[Участник]"
    
    if user_data['is_owner']: 
        status_text = "[👑 Создатель]"
    elif user_data['is_admin']: 
        status_text = "[⭐ Администратор]"

    balance = float(user_data['balance'] or 0)
    frozen = float(user_data['frozen_balance'] or 0)
    
    try:
        db.cursor.execute("SELECT SUM(amount) as tot FROM transactions WHERE to_user_id = ? AND transaction_type = 'message_reward'", (user_id,))
        tot_earned_row = db.cursor.fetchone()
        total_earned = float(tot_earned_row['tot'] or 0) if tot_earned_row else 0.0
    except Exception:
        total_earned = 0.0
    
    try:
        db.cursor.execute("SELECT SUM(amount) as tot FROM reactor WHERE user_id = ?", (user_id,))
        tot_reactor_row = db.cursor.fetchone()
        reactor_donated = float(tot_reactor_row['tot'] or 0) if tot_reactor_row else 0.0
    except Exception:
        reactor_donated = 0.0

    today = get_today_date_msk()
    try:
        db.cursor.execute("SELECT total_messages FROM user_stats WHERE user_id = ? AND date = ?", (user_id, today))
        today_stats = db.cursor.fetchone()
        today_msgs = today_stats['total_messages'] if today_stats else 0
    except Exception:
        today_msgs = 0
    
    combos_today, sprints_today = 0, 0
    try:
        db.cursor.execute("SELECT COUNT(*) as cnt FROM combo_claims WHERE user_id = ? AND date(claimed_at) = ?", (user_id, today))
        combo_row = db.cursor.fetchone()
        if combo_row: combos_today = combo_row['cnt']
    except Exception:
        pass 

    try:
        db.cursor.execute("SELECT COUNT(*) as cnt FROM sprint_claims WHERE user_id = ? AND date(claimed_at) = ?", (user_id, today))
        sprint_row = db.cursor.fetchone()
        if sprint_row: sprints_today = sprint_row['cnt']
    except Exception:
        pass 

    bbs_profile = None
    try:
        db.cursor.execute("SELECT city, reaction_count FROM bbs_profiles WHERE user_id = ?", (user_id,))
        bbs_profile = db.cursor.fetchone()
    except Exception:
        pass
    
    safe_first_name = html.escape(user.first_name or "Пользователь")
    username_text = f"@{user.username}" if user.username else safe_first_name
    safe_username = html.escape(username_text)
    
    text = f"🪪 <b>ПАСПОРТ PULSE</b>\n\n"
    text += f"👤 <b>Имя:</b> {safe_first_name} ({safe_username})\n"
    text += f"{ICON_MILITARY_MEDAL} <b>Статус:</b> <code>{html.escape(status_text)}</code>\n"
    text += f"⏳ <b>В чате:</b> {days_in_chat} дней\n\n"
    
    text += f"{ICON_MONEY_BAG} <b>КОШЕЛЕК И ЭКОНОМИКА</b>\n\n"
    
    text += f"💰 <b>Баланс:</b> {format_number(balance)} Пульсов\n"
    if frozen > 0:
        text += f"🧊 <b>Заморожено:</b> {format_number(frozen)} 💎\n"
    text += f"📈 <b>Заработано (всего):</b> {format_number(total_earned)} 💎\n"
    text += f"☢️ <b>Вложено в Реактор:</b> {format_number(reactor_donated)} 💎\n\n"
    
    text += f"⚡️ <b>АКТИВНОСТЬ СЕГОДНЯ</b>\n"
    text += f"💬 <b>Сообщений:</b> {today_msgs} / 50 <i>(Лимит энергии)</i>\n"
    text += f"🔥 <b>Открыто Комбо:</b> {combos_today} шт.\n"
    text += f"{ICON_ROCKET} <b>Закрыто Спринтов:</b> {sprints_today} шт.\n\n"
    
    text += f"💘 <b>BBS (ЗНАКОМСТВА)</b>\n"
    if bbs_profile:
        import json
        try:
            cities = json.loads(bbs_profile['city']) if bbs_profile['city'] else []
            city_str = html.escape(cities[0]) if cities else "Не указан"
        except:
            city_str = "Не указан"
        text += f"💌 <b>Анкета:</b> Активна ({city_str})\n"
        text += f"👀 <b>Симпатий:</b> {bbs_profile['reaction_count']} ❤️\n"
    else:
        text += f"💌 <b>Анкета:</b> Не создана\n"

    # ИСПРАВЛЕНИЕ: Кнопка настроек теперь ведет на настоящий маршрут, а не на заглушку
    keyboard =[[InlineKeyboardButton("💸 Перевести Пульсы", callback_data="donate_to_user_start")],[InlineKeyboardButton("❤️ Моя Анкета BBS", callback_data="bbs_dating")],[InlineKeyboardButton("📜 Мои Квесты (Скоро)", callback_data="stub_quests"), InlineKeyboardButton("🛍 Рынок (Скоро)", callback_data="stub_market")],[InlineKeyboardButton("⚙️ Настройки Профиля", callback_data="profile_settings")],[InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await send_method(text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception:
        try:
            if hasattr(update_or_query, 'message') and update_or_query.message:
                await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except:
            pass


# ═══════════════════════════════════════════════════════════════
# МЕНЮ НАСТРОЕК
# ═══════════════════════════════════════════════════════════════

async def show_profile_settings(query, user, db):
    """Отображение настроек: Уведомления, Скрытие возраста и т.д."""
    _ensure_profile_columns(db)
    
    # 1. Читаем текущий статус уведомлений
    try:
        db.cursor.execute("SELECT notifications_enabled FROM users WHERE user_id = ?", (user.id,))
        user_row = db.cursor.fetchone()
        notifs_enabled = bool(user_row['notifications_enabled']) if user_row else True
    except Exception:
        notifs_enabled = True
        
    # 2. Читаем статус анкеты BBS
    has_bbs = False
    hide_age = False
    try:
        db.cursor.execute("SELECT hide_age FROM bbs_profiles WHERE user_id = ?", (user.id,))
        bbs_row = db.cursor.fetchone()
        if bbs_row:
            has_bbs = True
            hide_age = bool(bbs_row['hide_age'])
    except Exception:
        pass
        
    text = "⚙️ <b>НАСТРОЙКИ ПРОФИЛЯ</b>\n\n"
    text += "Здесь вы можете управлять своей приватностью и системными уведомлениями бота.\n\n"
    text += "<i>Совет: если бот слишком часто присылает вам чеки о добыче Пульсов — отключите уведомления.</i>"
    
    btn_notif = "✅ Уведомления в ЛС (Вкл)" if notifs_enabled else "❌ Уведомления в ЛС (Откл)"
    btn_age = "👻 Скрыть возраст в анкете BBS (Вкл)" if hide_age else "👁 Показывать возраст в BBS"
    
    keyboard =[[InlineKeyboardButton(btn_notif, callback_data=f"prof_notif_{int(not notifs_enabled)}")]
    ]
    
    # Показываем кнопку скрытия возраста ТОЛЬКО если у человека создана анкета
    if has_bbs:
        keyboard.append([InlineKeyboardButton(btn_age, callback_data=f"prof_age_{int(not hide_age)}")])
        
    keyboard.append([InlineKeyboardButton("🔙 Назад в Паспорт", callback_data="menu_profile")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def toggle_profile_setting(query, data, user, db):
    """Обработка переключения тумблеров в настройках"""
    _ensure_profile_columns(db)
    
    parts = data.split('_')
    setting_type = parts[1] # notif или age
    new_val = int(parts[2])
    
    try:
        if setting_type == 'notif':
            db.cursor.execute("UPDATE users SET notifications_enabled = ? WHERE user_id = ?", (new_val, user.id))
            db.conn.commit()
            if new_val:
                await query.answer("🔔 Уведомления включены!", show_alert=False)
            else:
                await query.answer("🔕 Уведомления отключены! Бот перестанет спамить в ЛС.", show_alert=True)
                
        elif setting_type == 'age':
            db.cursor.execute("UPDATE bbs_profiles SET hide_age = ? WHERE user_id = ?", (new_val, user.id))
            db.conn.commit()
            if new_val:
                await query.answer("👻 Теперь ваш возраст скрыт из анкет BBS!", show_alert=False)
            else:
                await query.answer("👁 Ваш возраст снова виден в анкете.", show_alert=False)
                
    except Exception as e:
        import logging
        logging.error(f"Ошибка БД в настройках профиля: {e}")
        await query.answer("❌ Ошибка базы данных", show_alert=True)
            
    # Обязательно перерисовываем меню, чтобы кнопка обновилась визуально!
    await show_profile_settings(query, user, db)
