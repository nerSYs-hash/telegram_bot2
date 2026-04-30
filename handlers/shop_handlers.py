#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.helpers import format_number

logger = logging.getLogger(__name__)

# ==========================================
# КАТАЛОГ ТОВАРОВ ЧЕРНОГО РЫНКА
# ==========================================
SHOP_CATALOG = {
    'ego': {
        'name': '👑 Статус и Эго',
        'items': {
            'entrance': {'name': '🚨 Вход с ноги (Глашатай)', 'price': 1, 'desc': 'Бот помпезно объявляет: "🚨 ВНИМАНИЕ! В чат зашел Олигарх @username!" при твоем первом сообщении за день. (7 дней)'},
            # V1.16.0d: 'title' переехал в /titles (меню Баланс → 🏷 Титулы) — двухвалютная покупка с пакетами.
            # Старые активные записи в marketplace_services продолжают жить и истекают штатно.
            'vip_top': {'name': '🌟 VIP-Оформление в ТОПе', 'price': 5, 'desc': 'Твой ник украшен звездами и выделяется: 🌟 ꧁ @Username ꧂ 🌟 во всех списках. (30 дней)'},
            'vip_bbs': {'name': '💝 VIP-Анкета в BBS', 'price': 10, 'desc': 'Твоя анкета в BBS переопубликуется с рамкой, анимированными эмодзи и закрепом (Pin) на сутки. Эффект взрыва сердечек!'},
        }
    },
    'utils': {
        'name': '🛠 Утилиты и Бусты',
        'items': {
            'shield': {'name': '🛡 Щит (Индульгенция)', 'price': 1, 'desc': 'Одноразовый щит. При следующем муте от админов - щит срабатывает и защищает тебя!'},
            'boost_x2': {'name': '⚡️ Бустер Майнинга (х2)', 'price': 8, 'desc': 'Удваивает твою базовую добычу Пульсов ровно на 24 часа. Нужна удача!'},
            'rp_cmds': {'name': '🎭 Ролевые команды', 'price': 3, 'desc': 'Доступ к командам /hug (обнять), /slap (шлепнуть), /kiss (поцеловать). (30 дней)'},
        }
    },
    'season1': {
        'name': '🐸 Сезон 1: Неслыханные Легенды',
        'items': {
            'frog_bait': {'name': '🪤 Золотая Приманка', 'price': 50, 'desc': 'Запускает ивент "Золотая Лягушка" в случайной ветке: 🐸 @username использовал приманку! Ловите!'},
            'prank': {'name': '🐸 Ядовитый плевок (Пранк)', 'price': 10, 'desc': 'Выбираешь жертву. Следующее сообщение жертвы удаляется и ботом пишется: 🐸 @Жертва квакнул: КВА-КВА!'},
            'toad_skin': {'name': '🐸 Жабья шкура (Анонимка)', 'price': 7, 'desc': 'Право написать 3 сообщения в Главный чат абсолютно анонимно через ЛС бота.'},
            'luck_paw': {'name': '🍀 Лапка на удачу (Бафф)', 'price': 12, 'desc': 'Увеличивает шанс "Критического удара" (х10 майнинг) с 2% до 15%. (24 часа)'},
            'neon_skin': {'name': '🖼️ Скин "Неоновое Болото"', 'price': 15, 'desc': 'Уникальный зеленый/неоновый фон для паспорта в /profile. Эксклюзив 1 сезона! (Навсегда)'},
        }
    },
    'super': {
        'name': '🔥 Супер-Фишки',
        'items': {
            'voice_above': {'name': '📢 Голос Свыше (Рупор)', 'price': 20, 'desc': 'Пишешь боту текст, он публикует в Главном чате от своего имени и закрепляет (Pin) на 1 час. Анонимно!'},
            'bounty': {'name': '🎯 Заказ за Голову', 'price': 100, 'desc': 'Объявляешь охоту на юзера. 🎯 Первый, кто ответит на сообщение жертвы - получает куш, жертва теряет -50 💎!'},
            'lootbox': {'name': '📦 Тайный Ящик', 'price': 5000, 'desc': 'Лотерея! Может быть: пусто, 1000 💎, Щит, или ДЖЕКПОТ 50000 💎!'},
        }
    }
}

async def show_shop_main(query_or_update, context, db, user_id):
    """Главное меню магазина (Категории)"""
    user_data = db.get_user(user_id)
    if not user_data:
        return

    # TODO: В будущем здесь будет проверка: if reactor_charge < 100: return "Рынок закрыт"
    
    text = (
        "🛍 <b>ЧЕРНЫЙ РЫНОК PULSE</b>\n\n"
        f"Твой баланс: <b>{format_number(user_data['balance'])} 💎</b>\n\n"
        "Здесь продается то, что нельзя купить за обычные деньги. "
        "Ассортимент обновляется.\n\n"
        "<i>Выберите категорию:</i>"
    )

    keyboard =[]
    for cat_id, cat_data in SHOP_CATALOG.items():
        keyboard.append([InlineKeyboardButton(cat_data['name'], callback_data=f"shop_cat_{cat_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Выход в меню", callback_data="back_to_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await query_or_update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')


async def show_shop_category(query, context, db, user_id, cat_id):
    """Список товаров в категории"""
    if cat_id not in SHOP_CATALOG:
        await query.answer("Категория не найдена!", show_alert=True)
        return

    cat_data = SHOP_CATALOG[cat_id]
    user_data = db.get_user(user_id)

    text = (
        f"📂 <b>{cat_data['name']}</b>\n"
        f"Твой баланс: {format_number(user_data['balance'])} 💎\n\n"
        f"<i>Выберите товар для просмотра:</i>"
    )

    keyboard = []
    for item_id, item_data in cat_data['items'].items():
        btn_text = f"{item_data['name']} — {format_number(item_data['price'])} 💎"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"shop_item_{cat_id}_{item_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к категориям", callback_data="shop_main")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_shop_item(query, context, db, user_id, cat_id, item_id):
    """Описание конкретного товара и кнопка покупки"""
    try:
        item = SHOP_CATALOG[cat_id]['items'][item_id]
    except KeyError:
        await query.answer("Товар не найден!", show_alert=True)
        return

    user_data = db.get_user(user_id)
    balance = float(user_data['balance'])
    price = float(item['price'])

    text = (
        f"🏷 <b>{item['name']}</b>\n\n"
        f"📝 <i>{item['desc']}</i>\n\n"
        f"💰 <b>Цена:</b> {format_number(price)} 💎\n"
        f"💳 <b>Твой баланс:</b> {format_number(balance)} 💎\n"
    )

    keyboard =[]
    if balance >= price:
        keyboard.append([InlineKeyboardButton("✅ КУПИТЬ", callback_data=f"shop_buy_{cat_id}_{item_id}")])
    else:
        text += "\n❌ <i>Недостаточно Пульсов для покупки!</i>"

    keyboard.append([InlineKeyboardButton("🔙 Назад к списку", callback_data=f"shop_cat_{cat_id}")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def buy_shop_item(query, context, db, user_id, cat_id, item_id):
    """Логика покупки товара"""
    try:
        item = SHOP_CATALOG[cat_id]['items'][item_id]
    except KeyError:
        await query.answer("Товар не найден!", show_alert=True)
        return

    user_data = db.get_user(user_id)
    price = float(item['price'])

    if float(user_data['balance']) < price:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return

    # 1. Списываем деньги
    db.update_user_balance(user_id, price, 'subtract')
    db.update_bank_balance(price, 'add')
    db.add_transaction(user_id, None, price, 'shop_purchase', f"Покупка: {item['name']}")

    # 2. Записываем товар в marketplace_services (все кроме разовых действий)
    if item_id not in ['frog_bait', 'prank', 'voice_above', 'bounty', 'vip_bbs']:
        try:
            db.cursor.execute('''
                INSERT INTO marketplace_services (service_type, user_id, price, status)
                VALUES (?, ?, ?, 'active')
            ''', (item_id, user_id, price))
            db.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка выдачи товара {item_id} юзеру {user_id}: {e}")

    # ════════════════════════════════════════════════════════════════════════════════
    # 🎭 РОЛЕВЫЕ КОМАНДЫ (rp_cmds)
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'rp_cmds':
        import time as time_module
        expires_at = time_module.time() + (30 * 24 * 3600)  # 30 дней
        db.cursor.execute(
            'UPDATE marketplace_services SET expires_at = ? WHERE user_id = ? AND service_type = ? AND status = ? ORDER BY id DESC LIMIT 1',
            (expires_at, user_id, 'rp_cmds', 'active')
        )
        db.conn.commit()
        success_text = (
            f"✅ <b>РОЛЕВЫЕ КОМАНДЫ АКТИВИРОВАНЫ!</b>\n\n"
            f"🎭 Теперь ты можешь использовать:\n"
            f"• /hug — обнять\n"
            f"• /slap — шлепнуть\n"
            f"• /kiss — поцеловать\n\n"
            f"⏰ Действуют 30 дней"
        )
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Продолжить покупки", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🏷️ КАСТОМНЫЙ ТИТУЛ — V1.16.0d: переехало в /titles (меню «Баланс → 🏷 Титулы»).
    # Здесь оставлен только защитный заглушка-обработчик на случай старых callback'ов
    # (новые кнопки из чёрного рынка не приведут в эту ветку — её нет в SHOP_CATALOG).
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'title':
        await query.edit_message_text(
            "🏷 <b>Покупка титула переехала</b>\n\n"
            "Теперь титулы покупаются через меню:\n"
            "/balance → 🏷 Титулы (или команда /titles).\n\n"
            "Там есть выбор срока (7д / 1мес / 3мес / 6мес / 1год) и оплата за Пульсы или Рубли.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏷 Открыть меню Титулов", callback_data="titles_menu")
            ]]),
            parse_mode='HTML',
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🚨 ВХОД С НОГИ (entrance)
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'entrance':
        import time as time_module
        expires_at = time_module.time() + (7 * 24 * 3600)
        db.cursor.execute(
            'UPDATE marketplace_services SET expires_at = ? WHERE user_id = ? AND service_type = ? AND status = ? ORDER BY id DESC LIMIT 1',
            (expires_at, user_id, 'entrance', 'active')
        )
        db.conn.commit()
        
        success_text = (
            f"✅ <b>ГЛАШАТАЙ АКТИВИРОВАН!</b>\n\n"
            f"🚨 Бот объявит на весь чат твой первый вход каждый день:\n"
            f"<b>\"🚨 ВНИМАНИЕ! В чат зашел Олигарх @username!\"</b>\n\n"
            f"⏰ Действует 7 дней"
        )
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Продолжить покупки", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🌟 VIP-ОФОРМЛЕНИЕ В ТОПЕ (vip_top)
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'vip_top':
        import time as time_module
        expires_at = time_module.time() + (30 * 24 * 3600)
        db.cursor.execute(
            'UPDATE marketplace_services SET expires_at = ? WHERE user_id = ? AND service_type = ? AND status = ? ORDER BY id DESC LIMIT 1',
            (expires_at, user_id, 'vip_top', 'active')
        )
        db.conn.commit()
        
        success_text = (
            f"✅ <b>VIP-СТАТУС АКТИВИРОВАН!</b>\n\n"
            f"🌟 Теперь в любых топах и списках ты выглядишь так:\n"
            f"<b>🌟 ꧁ @Username ꧂ 🌟</b>\n\n"
            f"⏰ Действует 30 дней"
        )
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Продолжить покупки", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 💝 VIP-АНКЕТА В BBS (vip_bbs)
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'vip_bbs':
        success_text = (
            f"✅ <b>VIP-АНКЕТА ГОТОВА К ПЕРЕОПУБЛИКАЦИИ!</b>\n\n"
            f"💝 Твоя анкета переопубликуется с:\n"
            f"• Красивой рамкой\n"
            f"• Анимированными эмодзи\n"
            f"• Закрепом (Pin) на сутки\n"
            f"• Эффектом 💥 взрыва сердечек!\n\n"
            f"<i>Волшебство происходит прямо сейчас...</i>"
        )
        
        # Сразу запускаем переопубликацию анкеты
        try:
            db.cursor.execute('''
                INSERT INTO marketplace_services (service_type, user_id, price, status, content)
                VALUES (?, ?, ?, 'used', 'bbs_repub_sent')
            ''', ('vip_bbs', user_id, price))
            db.conn.commit()
        except:
            pass
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Вернуться на Рынок", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🪤 ЗОЛОТАЯ ПРИМАНКА (frog_bait) - РАЗОВОЕ ДЕЙСТВИЕ
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'frog_bait':
        success_text = (
            f"✅ <b>ПРИМАНКА СРАБОТАЛА!</b>\n\n"
            f"🐸 <b>🐸 @{user_data.get('username', 'Unknown')} использовал золотую приманку!</b>\n"
            f"<b>Лягушка выпрыгнула, ловите!</b>\n\n"
            f"<i>Ивент \"Золотая Лягушка\" запущен в случайной ветке чата...</i>"
        )
        
        # Отмечаем товар как использованный
        try:
            db.cursor.execute('''
                INSERT INTO marketplace_services (service_type, user_id, price, status, content)
                VALUES (?, ?, ?, 'used', 'frog_event_triggered')
            ''', ('frog_bait', user_id, price))
            db.conn.commit()
        except:
            pass
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Вернуться на Рынок", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🐸 ЯДОВИТЫЙ ПЛЕВОК (prank) - РАЗОВОЕ ДЕЙСТВИЕ С ВЫБОРОМ ЖЕРТВЫ
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'prank':
        context.user_data['awaiting'] = f'prank_victim_{user_id}'
        
        success_text = (
            f"✅ <b>ПРАНК КУПЛЕН!</b>\n\n"
            f"🐸 Напишите боту в ЛС <b>ID жертвы</b> (можно найти в /top или /profile).\n\n"
            f"<i>Следующее сообщение жертвы будет удалено и заменено на 'КВА-КВА!'</i>"
        )
        
        # Сохраняем пранк в БД в статусе 'pending'
        try:
            db.cursor.execute('''
                INSERT INTO marketplace_services (service_type, user_id, price, status, content)
                VALUES (?, ?, ?, 'pending', 'awaiting_victim_id')
            ''', ('prank', user_id, price))
            db.conn.commit()
        except:
            pass
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Вернуться на Рынок", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🐸 ЖАБЬЯ ШКУРА (toad_skin) - 3 АНОНИМНЫХ СООБЩЕНИЯ
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'toad_skin':
        try:
            db.cursor.execute('''
                INSERT INTO marketplace_services (service_type, user_id, price, status, content)
                VALUES (?, ?, ?, 'active', 'anon_msgs_left:3')
            ''', ('toad_skin', user_id, price))
            db.conn.commit()
        except:
            pass
        
        success_text = (
            f"✅ <b>АНОНИМНОСТЬ РАЗБЛОКИРОВАНА!</b>\n\n"
            f"🐸 Теперь ты можешь отправить боту 3 сообщения, которые будут опубликованы в Главном чате:\n"
            f"<b>🐸 Анонимус:</b> [твой текст]\n\n"
            f"📝 Напиши боту текст, и он появится в чате с пометкой 'Анонимус'.\n"
            f"Осталось сообщений: <b>3</b>"
        )
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Вернуться на Рынок", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🍀 ЛАПКА НА УДАЧУ (luck_paw) - БАФФ НА КРИТ
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'luck_paw':
        import time as time_module
        expires_at = time_module.time() + (24 * 3600)
        db.cursor.execute(
            'UPDATE marketplace_services SET expires_at = ?, content = ? WHERE user_id = ? AND service_type = ? AND status = ? ORDER BY id DESC LIMIT 1',
            (expires_at, 'crit_boost:2to15', user_id, 'luck_paw', 'active')
        )
        db.conn.commit()
        
        success_text = (
            f"✅ <b>БАФФ УДАЧИ АКТИВИРОВАН!</b>\n\n"
            f"🍀 Шанс критического удара (×10 майнинг) увеличен:\n"
            f"• Было: 2%\n"
            f"• Стало: 15% ⚡️\n\n"
            f"⏰ Действует 24 часа"
        )
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Продолжить покупки", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 📢 ГОЛОС СВЫШЕ (voice_above) - АНОНИМНЫЙ РУПОР
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'voice_above':
        context.user_data['awaiting'] = f'voice_text_{user_id}'
        
        success_text = (
            f"✅ <b>ПОЛУЧИЛ ГОЛОС СВЫШЕ!</b>\n\n"
            f"📢 Напишите боту в ЛС текст сообщения (макс. 200 символов).\n\n"
            f"<b>Бот опубликует это в Главном чате от своего имени (никто не узнает, что это ты!)</b>\n\n"
            f"<i>Идеально для признаний, шуток или рекламы! Сообщение будет закреплено (Pin) на 1 час.</i>"
        )
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Вернуться на Рынок", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🎯 ЗАКАЗ ЗА ГОЛОВУ (bounty) - ОХОТА
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'bounty':
        context.user_data['awaiting'] = f'bounty_victim_{user_id}'
        
        success_text = (
            f"✅ <b>ОХОТА ОБЪЯВЛЕНА!</b>\n\n"
            f"🎯 Напишите боту в ЛС <b>ID жертвы</b> (из /top или /profile).\n\n"
            f"<b>В чате появится объявление:</b>\n"
            f"🎯 <b>ВНИМАНИЕ! За голову @Жертва назначена награда!</b>\n\n"
            f"<b>Правила:</b> Первый, кто сделает Reply на следующее сообщение жертвы, получит куш 💰\n"
            f"(Жертва теряет -50 💎)"
        )
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Вернуться на Рынок", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🎭 ЛУТБОКС - КАЗИНО
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'lootbox':
        import random
        chance = random.randint(1, 100)
        if chance <= 5: # 5% шанс на джекпот
            win = 50000
            db.update_user_balance(user_id, win, 'add')
            db.update_bank_balance(win, 'subtract')
            db.add_transaction(None, user_id, win, 'lootbox_win', "Джекпот из Лутбокса!")
            msg = f"📦 ВЫ ОТКРЫЛИ ЯЩИК...\n\n🎉 О БОЖЕ! ДЖЕКПОТ!!! Вы нашли {format_number(win)} 💎!"
        elif chance <= 30: # 25% шанс на утешительный приз
            win = 1000
            db.update_user_balance(user_id, win, 'add')
            db.update_bank_balance(win, 'subtract')
            db.add_transaction(None, user_id, win, 'lootbox_win', "Утешительный приз")
            msg = f"📦 ВЫ ОТКРЫЛИ ЯЩИК...\n\n✅ Внутри оказалось {format_number(win)} 💎! Неплохо."
        elif chance <= 50: # 20% шанс на Щит
            msg = f"📦 ВЫ ОТКРЫЛИ ЯЩИК...\n\n🛡️ Внутри спрятан ЩИТ! Защита от следующего мута добавлена в инвентарь."
            # Добавляем щит в инвентарь
            db.cursor.execute('''
                INSERT INTO marketplace_services (service_type, user_id, price, status)
                VALUES (?, ?, ?, 'active')
            ''', ('shield', user_id, 0))
            db.conn.commit()
        else: # 50% шанс на пустоту
            msg = f"📦 ВЫ ОТКРЫЛИ ЯЩИК...\n\n💨 Пффф... Там оказалась только пыль. Вы ничего не выиграли."
        
        await query.edit_message_text(
            msg, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Вернуться на Рынок", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # ⚡️ БУСТЕР X2 - УДВОЕНИЕ НАГРАД
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'boost_x2':
        import time as time_module
        expires_at = time_module.time() + (24 * 3600)
        db.cursor.execute(
            'UPDATE marketplace_services SET expires_at = ? WHERE user_id = ? AND service_type = ? AND status = ? ORDER BY id DESC LIMIT 1',
            (expires_at, user_id, 'boost_x2', 'active')
        )
        db.conn.commit()
        
        success_text = (
            f"✅ <b>БУСТЕР АКТИВИРОВАН!</b>\n\n"
            f"⚡️ Ваша добыча Пульсов удвоена на <b>24 часа</b>\n\n"
            f"Начало действия: <i>прямо сейчас</i>\n"
            f"Конец действия: <i>завтра в это время</i>"
        )

        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Продолжить покупки", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🛡️ ЩИТ - ЗАЩИТА ОТ МУТА
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'shield':
        success_text = (
            f"✅ <b>ЩИТ ПРИОБРЕТЕН!</b>\n\n"
            f"🛡️ Одноразовая защита от мута добавлена в инвентарь.\n"
            f"При следующем муте от админов - щит автоматически сработает!\n\n"
            f"⏰ Действует: до первого использования"
        )

        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Продолжить покупки", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # 🖼️ СКИН НЕОНОВОЕ БОЛОТО (neon_skin) - ЭКСКЛЮЗИВ
    # ════════════════════════════════════════════════════════════════════════════════
    if item_id == 'neon_skin':
        success_text = (
            f"✅ <b>ЭКСКЛЮЗИВНЫЙ СКИН ПРИМЕНЕН!</b>\n\n"
            f"🖼️ Твой профиль в /profile теперь украшен уникальным неоновым эффектом!\n\n"
            f"<i>Зеленый/неоновый фон для паспорта - эксклюзив сезона 1!</i>\n\n"
            f"⏰ Действует: <b>НАВСЕГДА</b>"
        )

        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Продолжить покупки", callback_data="shop_main")]]),
            parse_mode='HTML'
        )
        return

    # ════════════════════════════════════════════════════════════════════════════════
    # FALLBACK - стандартное сообщение для товаров без специальной логики
    # ════════════════════════════════════════════════════════════════════════════════
    success_text = (
        f"✅ <b>ПОКУПКА УСПЕШНА!</b>\n\n"
        f"Вы приобрели: <b>{item['name']}</b>\n"
        f"Списано: {format_number(price)} 💎\n\n"
        f"<i>Товар добавлен в ваш профиль!</i>"
    )

    await query.edit_message_text(
        success_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Продолжить покупки", callback_data="shop_main")]]),
        parse_mode='HTML'
    )