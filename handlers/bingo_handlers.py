#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Пульс-Бинго — интерактивная мини-игра.

Админ: создать → настроить цену/интервал → запустить
Юзер: купить карточку → получить 3×3 в ЛС → отмечать шары → БИНГО!
Авто: scheduler кидает шары в чат каждые N минут
"""

import json, random, logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import format_number

logger = logging.getLogger(__name__)

BINGO_RANGE = 30          # Числа от 1 до 30
BINGO_CARD_SIZE = 9       # 3×3
CHEAT_PENALTY = 100       # Штраф за попытку схитрить
BINGO_LINES = [
    [0,1,2], [3,4,5], [6,7,8],  # строки
    [0,3,6], [1,4,7], [2,5,8],  # столбцы
    [0,4,8], [2,4,6],            # диагонали
]


class BingoHandler:
    def __init__(self, db, target_chat_id, main_admin_id, bot_username=None):
        self.db = db
        self.target_chat_id = target_chat_id
        self.main_admin_id = main_admin_id
        self.bot_username = bot_username
        self._ensure_tables()

    def _is_owner_user(self, user) -> bool:
        """Проверка: главный владелец ИЛИ зам (is_owner=1)."""
        if user.id == self.main_admin_id:
            return True
        u = self.db.get_user(user.id)
        return bool(u and u['is_owner'])

    # ══════════════════════════════════════════
    #  ТАБЛИЦЫ
    # ══════════════════════════════════════════

    def _ensure_tables(self):
        try:
            self.db.cursor.execute('''CREATE TABLE IF NOT EXISTS bingo_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_price INTEGER NOT NULL DEFAULT 500,
                ball_interval INTEGER NOT NULL DEFAULT 120,
                status TEXT NOT NULL DEFAULT 'waiting',
                total_pool INTEGER NOT NULL DEFAULT 0,
                winner_id INTEGER,
                balls_drawn TEXT NOT NULL DEFAULT '[]',
                last_ball_at TIMESTAMP,
                message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            self.db.cursor.execute('''CREATE TABLE IF NOT EXISTS bingo_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                card_data TEXT NOT NULL,
                marked TEXT NOT NULL DEFAULT '[0,0,0,0,0,0,0,0,0]',
                has_bingo INTEGER NOT NULL DEFAULT 0,
                card_message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES bingo_games(id),
                UNIQUE(game_id, user_id)
            )''')
            self.db.conn.commit()
            logger.info("Bingo tables ensured.")
        except Exception as e:
            logger.error(f"Bingo ensure tables: {e}")

    # ══════════════════════════════════════════
    #  ХЕЛПЕРЫ
    # ══════════════════════════════════════════

    def _game(self, gid, status=None):
        sql = 'SELECT * FROM bingo_games WHERE id=?'
        params = [gid]
        if status:
            sql += ' AND status=?'
            params.append(status)
        self.db.cursor.execute(sql, params)
        return self.db.cursor.fetchone()

    def _active_games(self):
        self.db.cursor.execute(
            "SELECT * FROM bingo_games WHERE status IN ('waiting','active') ORDER BY id DESC")
        return self.db.cursor.fetchall()

    def _card(self, gid, uid):
        self.db.cursor.execute(
            'SELECT * FROM bingo_cards WHERE game_id=? AND user_id=?', (gid, uid))
        return self.db.cursor.fetchone()

    def _players_count(self, gid):
        self.db.cursor.execute(
            'SELECT COUNT(*) c FROM bingo_cards WHERE game_id=?', (gid,))
        r = self.db.cursor.fetchone()
        return r['c'] if r else 0

    def _balls(self, game):
        try: return json.loads(game['balls_drawn'])
        except: return []

    def _card_nums(self, card):
        try: return json.loads(card['card_data'])
        except: return []

    def _card_marks(self, card):
        try: return json.loads(card['marked'])
        except: return [0]*9

    def _gen_card(self):
        """Генерация 9 уникальных чисел 1..30."""
        return random.sample(range(1, BINGO_RANGE + 1), BINGO_CARD_SIZE)

    def _check_bingo(self, marks):
        """Проверить есть ли линия."""
        for line in BINGO_LINES:
            if all(marks[i] for i in line):
                return True
        return False

    def _name(self, uid):
        d = self.db.get_user(uid)
        if d and d['username']: return f"@{d['username']}"
        if d and d['first_name']: return d['first_name']
        return f"ID {uid}"

    # ══════════════════════════════════════════
    #  КЛАВИАТУРА КАРТОЧКИ (ЛС)
    # ══════════════════════════════════════════

    def _card_kb(self, gid, card):
        """3×3 клавиатура карточки для ЛС."""
        nums = self._card_nums(card)
        marks = self._card_marks(card)
        rows = []
        for r in range(3):
            row = []
            for c in range(3):
                idx = r * 3 + c
                num = nums[idx]
                if marks[idx]:
                    row.append(InlineKeyboardButton("✅", callback_data="bcard_noop"))
                else:
                    row.append(InlineKeyboardButton(
                        str(num), callback_data=f"bcard_{gid}_{num}"))
            rows.append(row)
        return InlineKeyboardMarkup(rows)

    def _bingo_kb(self, gid):
        """Кнопка БИНГО! (заменяет карточку)."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔥 БИНГО! 🔥", callback_data=f"bbingo_{gid}")]
        ])

    def _card_text(self, gid, game, uid):
        """Текст над карточкой."""
        balls = self._balls(game)
        last5 = balls[-5:] if balls else []
        last_str = " ".join(f"<b>{b}</b>" for b in last5) if last5 else "—"
        players = self._players_count(gid)
        pool = game['total_pool']

        return (
            f"🎱 <b>Бинго #{gid}</b>\n\n"
            f"💰 Банк: {format_number(pool)} 💎\n"
            f"👥 Игроков: {players}\n"
            f"🎱 Последние шары: {last_str}\n"
            f"🔢 Выпало: {len(balls)}/{BINGO_RANGE}\n\n"
            f"Нажимайте числа, которые уже выпали!"
        )

    # ══════════════════════════════════════════
    #  МЕНЮ (ТОЧКА ВХОДА) — menu_bingo
    # ══════════════════════════════════════════

    async def show_bingo_menu(self, query, user):
        if self._is_owner_user(user):
            await self._admin_menu(query)
        else:
            await self._user_menu(query, user)

    async def _admin_menu(self, query):
        games = self._active_games()
        text = "🎱 <b>УПРАВЛЕНИЕ БИНГО</b>\n\n"
        if games:
            for g in games:
                gid = g['id']
                balls = self._balls(g)
                text += (f"#{gid} · {g['status']} · 💰{format_number(g['total_pool'])} · "
                         f"👥{self._players_count(gid)} · 🎱{len(balls)} шаров\n")
            text += "\n"
        else:
            text += "Нет активных игр.\n\n"

        kb = [[InlineKeyboardButton("🆕 Создать игру", callback_data="bingo_create")]]
        for g in (games or []):
            gid = g['id']
            if g['status'] == 'waiting':
                kb.append([InlineKeyboardButton(
                    f"▶️ Запустить #{gid}", callback_data=f"bingo_start_{gid}")])
            kb.append([InlineKeyboardButton(
                f"🛑 Отменить #{gid}", callback_data=f"bingo_cancel_{gid}")])
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_activities")])
        await query.edit_message_text(text, parse_mode='HTML',
                                      reply_markup=InlineKeyboardMarkup(kb))

    async def _user_menu(self, query, user):
        games = self._active_games()
        if not games:
            await query.edit_message_text(
                "🎱 Нет активных игр Бинго.\nСледите за чатом!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="menu_activities")]]))
            return

        text = "🎱 <b>ПУЛЬС-БИНГО</b>\n\n"
        kb = []
        for g in games:
            gid = g['id']
            card = self._card(gid, user.id)
            status_txt = "⏳ Набор" if g['status'] == 'waiting' else "🟢 Идёт"
            text += (f"#{gid} · {status_txt} · 💰{format_number(g['total_pool'])} · "
                     f"🎫{g['ticket_price']}💎 · 👥{self._players_count(gid)}\n")
            if card:
                kb.append([InlineKeyboardButton(
                    f"🎱 Моя карточка #{gid}", callback_data=f"bcard_show_{gid}")])
            else:
                kb.append([InlineKeyboardButton(
                    f"🎫 Купить карточку #{gid}", callback_data=f"bingo_buy_{gid}")])
        kb.append([InlineKeyboardButton("🔄 Обновить", callback_data="menu_bingo")])
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_activities")])
        await query.edit_message_text(text, parse_mode='HTML',
                                      reply_markup=InlineKeyboardMarkup(kb))

    # ══════════════════════════════════════════
    #  ADMIN CALLBACKS (bingo_*)
    # ══════════════════════════════════════════

    async def handle_bingo_callback(self, query, data, user, context):
        """Роутер для bingo_* колбэков."""

        if data == "bingo_create":
            if not self._is_owner_user(user):
                await query.answer("⛔", show_alert=True); return
            kb = [
                [InlineKeyboardButton("💎 100", callback_data="bingo_price_100"),
                 InlineKeyboardButton("💎 500", callback_data="bingo_price_500"),
                 InlineKeyboardButton("💎 1000", callback_data="bingo_price_1000")],
                [InlineKeyboardButton("🔙", callback_data="menu_bingo")]
            ]
            await query.edit_message_text(
                "🎱 <b>НОВАЯ ИГРА БИНГО</b>\n\nШаг 1/2 — Цена карточки:",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("bingo_price_"):
            price = int(data.split('_')[2])
            context.user_data['bingo_price'] = price
            kb = [
                [InlineKeyboardButton("⏱ 30 сек (тест)", callback_data="bingo_interval_30")],
                [InlineKeyboardButton("⏱ 2 мин", callback_data="bingo_interval_120"),
                 InlineKeyboardButton("⏱ 5 мин", callback_data="bingo_interval_300")],
                [InlineKeyboardButton("🔙", callback_data="menu_bingo")]
            ]
            await query.edit_message_text(
                f"🎱 <b>НОВАЯ ИГРА БИНГО</b>\n\n"
                f"✅ Карточка: {price} 💎\nШаг 2/2 — Интервал шаров:",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("bingo_interval_"):
            interval = int(data.split('_')[2])
            price = context.user_data.get('bingo_price', 500)
            try:
                self.db.cursor.execute(
                    "INSERT INTO bingo_games (ticket_price,ball_interval,status,total_pool,balls_drawn)"
                    " VALUES (?,?,'waiting',0,'[]')", (price, interval))
                self.db.conn.commit()
                gid = self.db.cursor.lastrowid
            except Exception as e:
                await query.edit_message_text(f"❌ {e}"); return

            # Сообщение в чат
            await self._publish_game(gid, context)

            await query.edit_message_text(
                f"✅ <b>Бинго #{gid}</b> создано!\n\n"
                f"🎫 Карточка: {price} 💎\n"
                f"⏱ Интервал: {interval} сек\n"
                f"📨 Опубликовано в чате\n\n"
                f"Нажмите ▶️ Запустить, когда наберётся достаточно игроков.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 К Бинго", callback_data="menu_bingo")]]))

        elif data.startswith("bingo_start_"):
            if not self._is_owner_user(user):
                await query.answer("⛔", show_alert=True); return
            gid = int(data.split('_')[2])
            game = self._game(gid, status='waiting')
            if not game:
                await query.answer("❌ Игра не найдена.", show_alert=True); return
            players = self._players_count(gid)
            if players < 2:
                await query.answer("❌ Нужно минимум 2 игрока!", show_alert=True); return

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.db.cursor.execute(
                "UPDATE bingo_games SET status='active', last_ball_at=? WHERE id=?",
                (now, gid))
            self.db.conn.commit()

            try:
                await context.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=(f"🎱 <b>БИНГО #{gid} НАЧАЛОСЬ!</b>\n\n"
                          f"👥 Игроков: {players}\n"
                          f"💰 Банк: {format_number(game['total_pool'])} 💎\n\n"
                          f"Шары начинают выпадать! Следите за чатом 👀"),
                    parse_mode='HTML')
            except Exception as e:
                logger.error(f"Bingo start announce: {e}")

            await query.edit_message_text(
                f"▶️ <b>Бинго #{gid}</b> запущено! Шары полетели.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 К Бинго", callback_data="menu_bingo")]]))

        elif data.startswith("bingo_cancel_"):
            if not self._is_owner_user(user):
                await query.answer("⛔", show_alert=True); return
            gid = int(data.split('_')[2])
            game = self._game(gid)
            if not game or game['status'] == 'finished':
                await query.answer("❌", show_alert=True); return

            # Возврат денег
            self.db.cursor.execute(
                'SELECT user_id FROM bingo_cards WHERE game_id=?', (gid,))
            cards = self.db.cursor.fetchall()
            price = game['ticket_price']
            for c in cards:
                uid = c['user_id']
                self.db.update_bank_balance(price, 'subtract')
                self.db.update_user_balance(uid, price, 'add')
                self.db.add_transaction(None, uid, price, 'bingo_refund',
                                        f"Возврат за Бинго #{gid}")
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"🎱 Бинго #{gid} отменено.\n💰 Возврат: {format_number(price)} 💎",
                        parse_mode='HTML')
                except: pass

            self.db.cursor.execute(
                "UPDATE bingo_games SET status='cancelled' WHERE id=?", (gid,))
            self.db.conn.commit()

            await query.edit_message_text(
                f"🛑 Бинго #{gid} отменено. Возвращено {len(cards)} игрокам.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 К Бинго", callback_data="menu_bingo")]]))

        # Покупка карточки (для юзеров)
        elif data.startswith("bingo_buy_"):
            gid = int(data.split('_')[2])
            await self._buy_card(query, gid, user, context)

    # ══════════════════════════════════════════
    #  ПОКУПКА КАРТОЧКИ
    # ══════════════════════════════════════════

    async def _buy_card(self, query, gid, user, context):
        game = self._game(gid)
        if not game or game['status'] not in ('waiting', 'active'):
            await query.answer("❌ Игра недоступна.", show_alert=True); return

        if self._is_owner_user(user):
            await query.answer("⚠️ Админ не может играть!", show_alert=True); return

        # Уже есть карточка?
        existing = self._card(gid, user.id)
        if existing:
            await query.answer("❌ У вас уже есть карточка!", show_alert=True); return

        ud = self.db.get_user(user.id)
        if not ud:
            await query.answer("❌ /start", show_alert=True); return

        price = game['ticket_price']
        if ud['balance'] < price:
            await query.answer(
                f"❌ Нужно {format_number(price)} 💎\nУ вас {format_number(ud['balance'])} 💎",
                show_alert=True); return

        # Списываем и создаём карточку
        try:
            self.db.update_user_balance(user.id, price, 'subtract')
            self.db.update_bank_balance(price, 'add')
            self.db.add_transaction(user.id, None, price, 'bingo_ticket',
                                    f"Карточка Бинго #{gid}")

            card_nums = self._gen_card()
            self.db.cursor.execute(
                "INSERT INTO bingo_cards (game_id,user_id,card_data) VALUES (?,?,?)",
                (gid, user.id, json.dumps(card_nums)))

            self.db.cursor.execute(
                'UPDATE bingo_games SET total_pool=total_pool+? WHERE id=?',
                (price, gid))
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"Bingo buy: {e}")
            await query.answer(f"❌ {e}", show_alert=True); return

        # Отправляем карточку в ЛС
        card = self._card(gid, user.id)
        if card:
            try:
                msg = await context.bot.send_message(
                    chat_id=user.id,
                    text=self._card_text(gid, game, user.id),
                    parse_mode='HTML',
                    reply_markup=self._card_kb(gid, card))
                # Сохраняем message_id карточки для обновления
                self.db.cursor.execute(
                    'UPDATE bingo_cards SET card_message_id=? WHERE game_id=? AND user_id=?',
                    (msg.message_id, gid, user.id))
                self.db.conn.commit()
            except Exception as e:
                logger.warning(f"Send card DM to {user.id}: {e}")

        await query.answer(
            f"✅ Карточка куплена!\n💎 Списано: {format_number(price)}\n📲 Карточка отправлена в ЛС",
            show_alert=True)

        # Обновляем сообщение в чате
        await self._refresh_game_msg(gid, context)

    # ══════════════════════════════════════════
    #  ОТМЕТКА ЧИСЛА НА КАРТОЧКЕ (bcard_*)
    # ══════════════════════════════════════════

    async def handle_card_callback(self, query, data, user, context):
        """Обработка нажатий на числа в карточке."""

        if data == "bcard_noop":
            await query.answer(); return

        # Показать карточку
        if data.startswith("bcard_show_"):
            gid = int(data.split('_')[2])
            game = self._game(gid)
            card = self._card(gid, user.id)
            if not game or not card:
                await query.answer("❌ Карточка не найдена.", show_alert=True); return
            
            if card['has_bingo']:
                await query.edit_message_text(
                    self._card_text(gid, game, user.id),
                    parse_mode='HTML',
                    reply_markup=self._bingo_kb(gid))
            else:
                await query.edit_message_text(
                    self._card_text(gid, game, user.id),
                    parse_mode='HTML',
                    reply_markup=self._card_kb(gid, card))
            return

        # bcard_{gid}_{num}
        parts = data.split('_')
        gid = int(parts[1])
        num = int(parts[2])

        game = self._game(gid)
        if not game or game['status'] != 'active':
            await query.answer("❌ Игра не активна.", show_alert=True); return

        card = self._card(gid, user.id)
        if not card:
            await query.answer("❌ У вас нет карточки.", show_alert=True); return

        balls = self._balls(game)
        nums = self._card_nums(card)
        marks = self._card_marks(card)

        # Число не на карточке?
        if num not in nums:
            await query.answer("❌ Это число не на вашей карточке.", show_alert=True); return

        idx = nums.index(num)

        # Уже отмечено?
        if marks[idx]:
            await query.answer("✅ Уже отмечено.", show_alert=True); return

        # ПРОВЕРКА: шар реально выпал?
        if num not in balls:
            # ШТРАФ за хитрость
            try:
                self.db.update_user_balance(user.id, CHEAT_PENALTY, 'subtract')
                self.db.update_bank_balance(CHEAT_PENALTY, 'add')
                self.db.add_transaction(user.id, None, CHEAT_PENALTY, 'bingo_penalty',
                                        f"Штраф Бинго #{gid}: число {num} не выпадало")
                self.db.conn.commit()
            except Exception as e:
                logger.error(f"Bingo penalty: {e}")
            await query.answer(
                f"❌ Число {num} ещё НЕ выпадало!\n"
                f"💸 Штраф: {CHEAT_PENALTY} 💎",
                show_alert=True)
            return

        # ✅ Отмечаем
        marks[idx] = 1
        self.db.cursor.execute(
            'UPDATE bingo_cards SET marked=? WHERE game_id=? AND user_id=?',
            (json.dumps(marks), gid, user.id))
        self.db.conn.commit()

        # Проверяем БИНГО
        if self._check_bingo(marks):
            self.db.cursor.execute(
                'UPDATE bingo_cards SET has_bingo=1 WHERE game_id=? AND user_id=?',
                (gid, user.id))
            self.db.conn.commit()

            await query.answer("🔥 БИНГО! Скорее нажимай кнопку!", show_alert=True)
            await query.edit_message_text(
                f"🔥🔥🔥 <b>БИНГО!</b> 🔥🔥🔥\n\n"
                f"У вас линия! Нажмите кнопку ПЕРВЫМ, чтобы забрать банк!",
                parse_mode='HTML',
                reply_markup=self._bingo_kb(gid))
        else:
            await query.answer(f"✅ {num} отмечено!")
            # Обновляем карточку
            card = self._card(gid, user.id)  # перечитываем
            await query.edit_message_text(
                self._card_text(gid, game, user.id),
                parse_mode='HTML',
                reply_markup=self._card_kb(gid, card))

    # ══════════════════════════════════════════
    #  КНОПКА БИНГО (bbingo_*)
    # ══════════════════════════════════════════

    async def handle_bingo_claim(self, query, data, user, context):
        """Первый нажавший БИНГО забирает банк."""
        gid = int(data.split('_')[1])

        game = self._game(gid, status='active')
        if not game:
            await query.answer("❌ Игра завершена.", show_alert=True); return

        card = self._card(gid, user.id)
        if not card or not card['has_bingo']:
            await query.answer("❌ У вас нет Бинго!", show_alert=True); return

        # Забираем банк
        prize = game['total_pool']
        try:
            self.db.update_bank_balance(prize, 'subtract')
            self.db.update_user_balance(user.id, prize, 'add')
            self.db.add_transaction(None, user.id, prize, 'bingo_win',
                                    f"Выигрыш Бинго #{gid}")
            self.db.cursor.execute(
                "UPDATE bingo_games SET status='finished', winner_id=? WHERE id=?",
                (user.id, gid))
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"Bingo claim: {e}")
            await query.answer(f"❌ {e}", show_alert=True); return

        winner_name = self._name(user.id)

        await query.answer(f"🎉 Вы выиграли {format_number(prize)} 💎!", show_alert=True)
        await query.edit_message_text(
            f"🎉 <b>ВЫ ВЫИГРАЛИ БИНГО #{gid}!</b>\n\n"
            f"💰 Приз: {format_number(prize)} 💎",
            parse_mode='HTML')

        # Объявление в чат
        try:
            await context.bot.send_message(
                chat_id=self.target_chat_id,
                text=(f"🎱🔥 <b>БИНГО #{gid} — ПОБЕДА!</b>\n\n"
                      f"🏆 {winner_name} собрал(а) линию первым!\n"
                      f"💰 Выигрыш: {format_number(prize)} 💎\n\n"
                      f"🎉 Поздравляем!"),
                parse_mode='HTML')
        except Exception as e:
            logger.error(f"Bingo win announce: {e}")

        # Уведомляем остальных
        self.db.cursor.execute(
            'SELECT user_id FROM bingo_cards WHERE game_id=? AND user_id!=?',
            (gid, user.id))
        others = self.db.cursor.fetchall()
        for o in others:
            try:
                await context.bot.send_message(
                    chat_id=o['user_id'],
                    text=(f"🎱 Бинго #{gid} завершено.\n"
                          f"🏆 Победитель: {winner_name}\n"
                          f"Удачи в следующей игре!"),
                    parse_mode='HTML')
            except: pass

    # ══════════════════════════════════════════
    #  ФОНОВАЯ ЗАДАЧА — ШАРЫ
    # ══════════════════════════════════════════

    async def draw_ball(self, bot):
        """
        Вызывается из scheduler каждые 30 сек.
        Проверяет активные игры — если пора, кидает шар.
        """
        self.db.cursor.execute("SELECT * FROM bingo_games WHERE status='active'")
        games = self.db.cursor.fetchall()

        for game in games:
            gid = game['id']
            interval = game['ball_interval']
            last_at = game['last_ball_at']

            # Проверяем интервал
            if last_at:
                try:
                    last = datetime.strptime(str(last_at)[:19], '%Y-%m-%d %H:%M:%S')
                    elapsed = (datetime.now() - last).total_seconds()
                    if elapsed < interval:
                        continue
                except: pass

            balls = self._balls(game)
            available = [n for n in range(1, BINGO_RANGE + 1) if n not in balls]

            if not available:
                # Все шары выпали — принудительно завершаем
                logger.info(f"Bingo #{gid}: all balls drawn, no winner → finishing")
                self.db.cursor.execute(
                    "UPDATE bingo_games SET status='finished' WHERE id=?", (gid,))
                self.db.conn.commit()
                try:
                    await bot.send_message(
                        chat_id=self.target_chat_id,
                        text=f"🎱 <b>Бинго #{gid}</b> — все {BINGO_RANGE} шаров выпали!\n"
                             f"Игра завершена без победителя.",
                        parse_mode='HTML')
                except: pass
                continue

            # Выбираем шар
            ball = random.choice(available)
            balls.append(ball)
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            self.db.cursor.execute(
                'UPDATE bingo_games SET balls_drawn=?, last_ball_at=? WHERE id=?',
                (json.dumps(balls), now, gid))
            self.db.conn.commit()

            logger.info(f"Bingo #{gid}: ball {ball} (total {len(balls)}/{BINGO_RANGE})")

            # Сообщение в чат
            try:
                await bot.send_message(
                    chat_id=self.target_chat_id,
                    text=f"🎱 <b>Шар:</b>  <code>{ball}</code>   "
                         f"<i>(Бинго #{gid} · {len(balls)}/{BINGO_RANGE})</i>",
                    parse_mode='HTML')
            except Exception as e:
                logger.error(f"Ball announce: {e}")

            # Обновляем карточки в ЛС у всех игроков
            self.db.cursor.execute(
                'SELECT * FROM bingo_cards WHERE game_id=?', (gid,))
            all_cards = self.db.cursor.fetchall()
            
            # Перечитываем game для актуальных данных
            game = self._game(gid)

            for card in all_cards:
                uid = card['user_id']
                mid = card['card_message_id']
                if not mid:
                    continue
                try:
                    c = self._card(gid, uid)  # свежие данные
                    if c and c['has_bingo']:
                        await bot.edit_message_text(
                            chat_id=uid, message_id=mid,
                            text=self._card_text(gid, game, uid),
                            parse_mode='HTML',
                            reply_markup=self._bingo_kb(gid))
                    elif c:
                        await bot.edit_message_text(
                            chat_id=uid, message_id=mid,
                            text=self._card_text(gid, game, uid),
                            parse_mode='HTML',
                            reply_markup=self._card_kb(gid, c))
                except Exception as e:
                    if 'not modified' not in str(e).lower():
                        logger.warning(f"Update card DM {uid}: {e}")

    # ══════════════════════════════════════════
    #  СООБЩЕНИЕ В ЧАТЕ
    # ══════════════════════════════════════════

    async def _publish_game(self, gid, context):
        game = self._game(gid)
        if not game: return

        text = (
            f"🎱 <b>ПУЛЬС-БИНГО #{gid}</b>\n\n"
            f"🎫 Карточка: {game['ticket_price']} 💎\n"
            f"⏱ Шары: каждые {game['ball_interval']} сек\n"
            f"👥 Игроков: {self._players_count(gid)}\n\n"
            f"Купи карточку и собери линию первым!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎫 Купить карточку", callback_data=f"bingo_buy_{gid}")],
            [InlineKeyboardButton("💼 Моя карточка", callback_data=f"bcard_show_{gid}")],
        ])
        try:
            msg = await context.bot.send_message(
                chat_id=self.target_chat_id, text=text,
                parse_mode='HTML', reply_markup=kb)
            self.db.cursor.execute(
                'UPDATE bingo_games SET message_id=? WHERE id=?',
                (msg.message_id, gid))
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"Publish bingo: {e}")

    async def _refresh_game_msg(self, gid, context):
        game = self._game(gid)
        if not game or not game['message_id']: return
        text = (
            f"🎱 <b>ПУЛЬС-БИНГО #{gid}</b>\n\n"
            f"🎫 Карточка: {game['ticket_price']} 💎\n"
            f"💰 Банк: {format_number(game['total_pool'])} 💎\n"
            f"👥 Игроков: {self._players_count(gid)}\n\n"
            f"Купи карточку и собери линию первым!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎫 Купить карточку", callback_data=f"bingo_buy_{gid}")],
            [InlineKeyboardButton("💼 Моя карточка", callback_data=f"bcard_show_{gid}")],
        ])
        try:
            await context.bot.edit_message_text(
                chat_id=self.target_chat_id, message_id=game['message_id'],
                text=text, parse_mode='HTML', reply_markup=kb)
        except Exception as e:
            if 'not modified' not in str(e).lower():
                logger.warning(f"Refresh bingo msg: {e}")
