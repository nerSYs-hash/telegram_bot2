#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль лотереи v3.

Чат:   компактное сообщение + быстрые кнопки [1][3][5][10] + «Купить в ЛС»
ЛС:    +/− виджет выбора количества → подтверждение покупки
Админ: создание (цена → время → режим), список, ручной розыгрыш
Авто:  pin при создании, unpin + розыгрыш по таймеру, 20% комиссия
"""

import random, logging
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import format_number, format_duration

logger = logging.getLogger(__name__)

MIN_PARTICIPANTS = 5  # Минимум участников для проведения лотереи
COMMISSION = 0.20
MAX_TICKETS = 10
JACKPOT_TAX = 0.05       # 5% от каждого билета → в Джекпот-пул
JACKPOT_LUCKY = 77       # Число для срыва джекпота (1-100)
PRIZE_SHARES = {1: {1: 1.0}, 2: {1: 0.70, 2: 0.30}, 3: {1: 0.60, 2: 0.25, 3: 0.15}}
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


class LotteryHandler:
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

#####
    # ══════════════════════════════════════════
    #  ТАБЛИЦЫ
    # ══════════════════════════════════════════

    def _ensure_tables(self):
        try:
            self.db.cursor.execute('''CREATE TABLE IF NOT EXISTS lotteries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_price INTEGER NOT NULL DEFAULT 100,
                duration INTEGER NOT NULL DEFAULT 3600,
                end_time TIMESTAMP NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                total_pool REAL NOT NULL DEFAULT 0,
                winner_id INTEGER, message_id INTEGER,
                winners_mode INTEGER NOT NULL DEFAULT 1)''')
            self.db.cursor.execute('''CREATE TABLE IF NOT EXISTS lottery_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lottery_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lottery_id) REFERENCES lotteries(id))''')
            self.db.cursor.execute("PRAGMA table_info(lotteries)")
            cols = {r[1] for r in self.db.cursor.fetchall()}
            for c, t in [('winner_id','INTEGER'),('message_id','INTEGER'),
                         ('winners_mode','INTEGER NOT NULL DEFAULT 1')]:
                if c not in cols:
                    self.db.cursor.execute(f'ALTER TABLE lotteries ADD COLUMN {c} {t}')
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"Ensure tables: {e}")

    # ══════════════════════════════════════════
    #  ДЖЕКПОТ «ПУЛЬСАР»
    # ══════════════════════════════════════════

    def _jackpot_pool(self):
        """Текущий размер джекпот-пула."""
        val = self.db.get_setting('jackpot_pool', '0')
        return int(float(val))

    def _jackpot_add(self, amount):
        """Добавить в джекпот-пул."""
        current = self._jackpot_pool()
        self.db.set_setting('jackpot_pool', str(current + int(amount)))

    def _jackpot_reset(self):
        """Сбросить джекпот-пул в 0."""
        self.db.set_setting('jackpot_pool', '0')

    # ══════════════════════════════════════════
    #  ХЕЛПЕРЫ
    # ══════════════════════════════════════════

    def _get(self, lid, active=False):
        sql = 'SELECT * FROM lotteries WHERE id = ?'
        if active: sql += " AND status='active'"
        self.db.cursor.execute(sql, (lid,))
        return self.db.cursor.fetchone()

    def _active(self):
        self.db.cursor.execute("SELECT * FROM lotteries WHERE status='active' ORDER BY id DESC")
        return self.db.cursor.fetchall()

    def _my(self, lid, uid):
        self.db.cursor.execute('SELECT COUNT(*) c FROM lottery_tickets WHERE lottery_id=? AND user_id=?',(lid,uid))
        r=self.db.cursor.fetchone(); return r['c'] if r else 0

    def _total(self, lid):
        self.db.cursor.execute('SELECT COUNT(*) c FROM lottery_tickets WHERE lottery_id=?',(lid,))
        r=self.db.cursor.fetchone(); return r['c'] if r else 0

    def _parts(self, lid):
        self.db.cursor.execute('SELECT COUNT(DISTINCT user_id) c FROM lottery_tickets WHERE lottery_id=?',(lid,))
        r=self.db.cursor.fetchone(); return r['c'] if r else 0

    def _remain(self, lot):
        try:
            end=datetime.strptime(str(lot['end_time'])[:19],'%Y-%m-%d %H:%M:%S')
            s=(end-datetime.now()).total_seconds()
            return format_duration(int(s)) if s>0 else "завершается…"
        except: return "—"

    def _expired(self, lot):
        try:
            end_raw = str(lot['end_time'])[:19]
            end = datetime.strptime(end_raw, '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            is_exp = now >= end
            if is_exp:
                logger.info(f"Lottery #{lot['id']} expired: end={end_raw}, now={now.strftime('%Y-%m-%d %H:%M:%S')}")
            return is_exp
        except Exception as e:
            logger.error(f"_expired error for lottery #{lot['id']}: {e}, raw end_time={lot['end_time']}")
            return False

    def _mode(self, lot):
        try: return lot['winners_mode'] or 1
        except: return 1

    def _name(self, uid):
        d=self.db.get_user(uid)
        if d and d['username']: return f"@{d['username']}"
        if d and d['first_name']: return d['first_name']
        return f"ID {uid}"

    # ══════════════════════════════════════════
    #  ТЕКСТЫ И КЛАВИАТУРЫ
    # ══════════════════════════════════════════

    def _chat_text(self, lid, lot):
        """Компактное HTML-сообщение для чата."""
        pool = lot['total_pool']
        net = pool * (1 - COMMISSION)
        mode = self._mode(lot)
        t = self._total(lid)
        p = self._parts(lid)
        r = self._remain(lot)
        price = lot['ticket_price']

        # Заголовок
        mode_tag = "ТОП-3" if mode == 3 else ""
        header = f"🎰 <b>ЛОТЕРЕЯ #{lid}</b>"
        if mode_tag:
            header += f" | {mode_tag}"

        # Призы в одну строку
        if mode >= 3 and p >= 0:
            shares = PRIZE_SHARES.get(min(mode, 3), {1: 1.0})
            prizes = " / ".join(
                f"{MEDALS[k]}{format_number(net * v)}"
                for k, v in shares.items())
            pool_line = f"💰 {format_number(pool)} 💎 → {prizes}"
        else:
            pool_line = f"💰 Джекпот: {format_number(net)} 💎"

        # Джекпот «Пульсар»
        jp = self._jackpot_pool()
        jp_line = f"\n🌟 <b>Пульсар:</b> {format_number(jp)} 💎" if jp > 0 else ""

        text = (
            f"{header}\n\n"
            f"{pool_line}\n"
            f"🎫 {price} 💎 · макс {MAX_TICKETS} · ⏳ {r}\n"
            f"👥 {p} · 🎟 {t}"
            f"{jp_line}"
        )
        return text

    def _chat_kb(self, lid):
        """Клавиатура в групповом чате: быстрая покупка + ЛС."""
        row1 = [
            InlineKeyboardButton("🎟1", callback_data=f"buy_ticket_{lid}_1"),
            InlineKeyboardButton("🎟3", callback_data=f"buy_ticket_{lid}_3"),
            InlineKeyboardButton("🎟5", callback_data=f"buy_ticket_{lid}_5"),
            InlineKeyboardButton("🎟10", callback_data=f"buy_ticket_{lid}_10"),
        ]
        row2 = [
            InlineKeyboardButton("💼 Мои билеты", callback_data=f"my_tickets_{lid}"),
        ]
        # Кнопка «В ЛС» ведёт прямо к покупке конкретной лотереи
        if self.bot_username:
            row2.append(InlineKeyboardButton(
                "📲 В ЛС", url=f"https://t.me/{self.bot_username}?start=lottery_{lid}"))
        return InlineKeyboardMarkup([row1, row2])

    def _dm_widget_text(self, lid, lot, uid, qty):
        """Текст виджета покупки в ЛС."""
        pool = lot['total_pool']
        my = self._my(lid, uid)
        can = MAX_TICKETS - my
        price = lot['ticket_price']
        cost = price * qty
        mode = self._mode(lot)
        mode_txt = "🏆 1 победитель" if mode == 1 else "🏆 ТОП-3 (60/25/15%)"

        jp = self._jackpot_pool()
        jp_line = f"\n🌟 Пульсар: {format_number(jp)} 💎" if jp > 0 else ""

        return (
            f"🎰 <b>Лотерея #{lid}</b>\n\n"
            f"💰 Банк: {format_number(pool)} 💎 | ⏳ {self._remain(lot)}\n"
            f"🎫 Билет: {price} 💎 | {mode_txt}\n"
            f"🎟 Ваших: {my}/{MAX_TICKETS}"
            f"{jp_line}\n\n"
            f"Выбрано: <b>{qty}</b> билет(ов) = <b>{format_number(cost)} 💎</b>"
        )

    def _dm_widget_kb(self, lid, qty):
        """Клавиатура +/− в ЛС."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅️", callback_data=f"lott_dec_{lid}_{qty}"),
                InlineKeyboardButton(f"🎟 {qty}", callback_data="lott_noop"),
                InlineKeyboardButton("➡️", callback_data=f"lott_inc_{lid}_{qty}"),
            ],
            [InlineKeyboardButton(
                f"🎟 Купить {qty} билет(ов)",
                callback_data=f"lott_buy_{lid}_{qty}")],
            [InlineKeyboardButton(
                "💼 Мои билеты", callback_data=f"my_tickets_{lid}")],
            [
                InlineKeyboardButton("🔄", callback_data=f"lott_dm_{lid}"),
                InlineKeyboardButton("🔙 Назад", callback_data="menu_activities"),
            ],
        ])

    # ══════════════════════════════════════════
    #  ТОЧКА ВХОДА — menu_lottery
    # ══════════════════════════════════════════

    async def show_lottery_menu(self, query, user):
        if self._is_owner_user(user):
            await self._admin_menu(query)
        else:
            await self._user_menu(query, user)

    async def _admin_menu(self, query):
        kb = [[InlineKeyboardButton("🚀 Создать", callback_data="lottery_create")],
              [InlineKeyboardButton("📋 Активные", callback_data="lottery_list")],
              [InlineKeyboardButton("🔙 Назад", callback_data="menu_activities")]]
        await query.edit_message_text(
            "🎰 <b>УПРАВЛЕНИЕ ЛОТЕРЕЕЙ</b>\n\nВыберите действие:",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

    async def _user_menu(self, query, user):
        lots = self._active()
        if not lots:
            await query.edit_message_text(
                "🎰 Нет активных лотерей.\nСледите за чатом!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="menu_activities")]]))
            return

        # Если одна лотерея — сразу виджет покупки
        if len(lots) == 1:
            lot = lots[0]
            lid = lot['id']
            my = self._my(lid, user.id)
            can = MAX_TICKETS - my
            qty = min(1, can) if can > 0 else 0
            if qty == 0:
                qty = 1  # покажем, кнопка купить заблокируется по лимиту
            await query.edit_message_text(
                self._dm_widget_text(lid, lot, user.id, qty),
                parse_mode='HTML',
                reply_markup=self._dm_widget_kb(lid, qty))
            return

        # Несколько лотерей — список с кнопками
        text = "🎰 <b>АКТИВНЫЕ ЛОТЕРЕИ</b>\n\n"
        kb = []
        for lot in lots:
            lid = lot['id']
            my = self._my(lid, user.id)
            text += (
                f"#{lid} · 💰{format_number(lot['total_pool'])} · "
                f"🎫{lot['ticket_price']}💎 · ⏳{self._remain(lot)}\n"
                f"   🎟 Ваших: {my}/{MAX_TICKETS}\n\n")
            kb.append([InlineKeyboardButton(
                f"🎟 Купить #{lid}", callback_data=f"lott_dm_{lid}")])
        kb.append([InlineKeyboardButton("🔄 Обновить", callback_data="menu_lottery")])
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_activities")])
        await query.edit_message_text(text, parse_mode='HTML',
                                      reply_markup=InlineKeyboardMarkup(kb))

    # ══════════════════════════════════════════
    #  ВИДЖЕТ +/− В ЛС  (lott_*)
    # ══════════════════════════════════════════

    async def handle_lott_callback(self, query, data, user, context):
        """Обработка lott_inc / lott_dec / lott_buy / lott_dm / lott_noop."""

        if data == "lott_noop":
            await query.answer()
            return

        parts = data.split('_')  # lott_{action}_{lid}_{qty?}
        action = parts[1]

        if action == "dm":
            # Открыть виджет покупки для конкретной лотереи
            lid = int(parts[2])
            lot = self._get(lid, active=True)
            if not lot:
                await query.answer("❌ Лотерея не найдена.", show_alert=True)
                return
            my = self._my(lid, user.id)
            qty = min(1, MAX_TICKETS - my) if my < MAX_TICKETS else 1
            await query.answer()
            await query.edit_message_text(
                self._dm_widget_text(lid, lot, user.id, qty),
                parse_mode='HTML',
                reply_markup=self._dm_widget_kb(lid, qty))
            return

        lid = int(parts[2])
        qty = int(parts[3]) if len(parts) > 3 else 1

        lot = self._get(lid, active=True)
        if not lot:
            await query.answer("❌ Лотерея завершена.", show_alert=True)
            return

        my = self._my(lid, user.id)
        can = MAX_TICKETS - my

        if action == "inc":
            qty = min(qty + 1, can, MAX_TICKETS)
            await query.answer()
            await query.edit_message_text(
                self._dm_widget_text(lid, lot, user.id, qty),
                parse_mode='HTML',
                reply_markup=self._dm_widget_kb(lid, qty))

        elif action == "dec":
            qty = max(qty - 1, 1)
            await query.answer()
            await query.edit_message_text(
                self._dm_widget_text(lid, lot, user.id, qty),
                parse_mode='HTML',
                reply_markup=self._dm_widget_kb(lid, qty))

        elif action == "buy":
            # Покупка из ЛС
            await self._do_buy(query, lid, lot, qty, user, context, from_dm=True)

    # ══════════════════════════════════════════
    #  ADMIN FSM  (lottery_*)
    # ══════════════════════════════════════════

    async def handle_lottery_callback(self, query, data, user, context):

        if data == "lottery_create":
            if not self._is_owner_user(user):
                await query.answer("⛔", show_alert=True); return
            kb = [[InlineKeyboardButton("💎 10", callback_data="lottery_price_10"),
                   InlineKeyboardButton("💎 100", callback_data="lottery_price_100"),
                   InlineKeyboardButton("💎 500", callback_data="lottery_price_500")],
                  [InlineKeyboardButton("🔙", callback_data="menu_lottery")]]
            await query.edit_message_text(
                "🎰 <b>НОВАЯ ЛОТЕРЕЯ</b>\n\nШаг 1/3 — Цена билета:",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("lottery_price_"):
            price = int(data.split('_')[2])
            context.user_data['lottery_price'] = price
            kb = [[InlineKeyboardButton("⏱ 1мин (тест)", callback_data="lottery_duration_60")],
                  [InlineKeyboardButton("⏱ 1ч", callback_data="lottery_duration_3600"),
                   InlineKeyboardButton("⏱ 24ч", callback_data="lottery_duration_86400")],
                  [InlineKeyboardButton("🔙", callback_data="menu_lottery")]]
            await query.edit_message_text(
                f"🎰 <b>НОВАЯ ЛОТЕРЕЯ</b>\n\n✅ Билет: {price} 💎\nШаг 2/3 — Длительность:",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("lottery_duration_"):
            dur = int(data.split('_')[2])
            context.user_data['lottery_duration'] = dur
            price = context.user_data.get('lottery_price', 100)
            kb = [[InlineKeyboardButton("🏆 1 победитель", callback_data="lottery_mode_1")],
                  [InlineKeyboardButton("🥇🥈🥉 ТОП-3 (60/25/15%)", callback_data="lottery_mode_3")],
                  [InlineKeyboardButton("🔙", callback_data="menu_lottery")]]
            await query.edit_message_text(
                f"🎰 <b>НОВАЯ ЛОТЕРЕЯ</b>\n\n"
                f"✅ Билет: {price} 💎\n✅ Время: {format_duration(dur)}\n",
                
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("lottery_mode_"):
            wm = int(data.split('_')[2])
            price = context.user_data.get('lottery_price', 100)
            dur = context.user_data.get('lottery_duration', 3600)
            end = datetime.now() + timedelta(seconds=dur)
            end_str = end.strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"Creating lottery: price={price}, dur={dur}, end_time={end_str}, mode={wm}")
            try:
                self.db.cursor.execute(
                    'INSERT INTO lotteries (ticket_price,duration,end_time,status,total_pool,winners_mode)'
                    " VALUES (?,?,?,'active',0,?)", (price, dur, end_str, wm))
                self.db.conn.commit()
                lid = self.db.cursor.lastrowid
            except Exception as e:
                await query.edit_message_text(f"❌ {e}"); return

            await self._publish(lid, context)

            ml = "1 победитель" if wm == 1 else "ТОП-3"
            await query.edit_message_text(
                f"✅ <b>Лотерея #{lid}</b> создана!\n\n"
                f"💎 {price} · ⏱ {format_duration(dur)} · 🏆 {ml}\n",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]]))

        elif data == "lottery_list":
            lots = self._active()
            if not lots:
                text = "📋 Нет активных."
            else:
                text = "🎰 <b>АКТИВНЫЕ:</b>\n\n"
                for l in lots:
                    i=l['id']
                    text += (f"#{i} · {l['ticket_price']}💎 · "
                             f"💰{format_number(l['total_pool'])} · "
                             f"👥{self._parts(i)} ({self._total(i)}бил.) · "
                             f"⏰{self._remain(l)}\n")
            kb = [[InlineKeyboardButton(f"🏆 Розыгрыш #{l['id']}",
                    callback_data=f"lottery_draw_{l['id']}")] for l in (lots or [])]
            kb.append([InlineKeyboardButton("🔙", callback_data="menu_lottery")])
            await query.edit_message_text(text, parse_mode='HTML',
                                          reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith("lottery_draw_"):
            if not self._is_owner_user(user):
                await query.answer("⛔", show_alert=True); return
            lid = int(data.split('_')[2])
            res = await self._draw(lid, context)
            await query.edit_message_text(res, parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋", callback_data="lottery_list"),
                     InlineKeyboardButton("🔙", callback_data="back_to_menu")]]))

    # ══════════════════════════════════════════
    #  ПОКУПКА БИЛЕТОВ  (buy_ticket из чата)
    # ══════════════════════════════════════════

    async def handle_buy_ticket(self, query, data, user, context):
        try:
            parts = data.split('_')
            lid = int(parts[2]); count = int(parts[3])
        except (IndexError, ValueError):
            await query.answer("❌", show_alert=True); return

        lot = self._get(lid, active=True)
        if not lot:
            await query.answer("❌ Лотерея завершена.", show_alert=True); return
        if self._expired(lot):
            await query.answer("⏰ Время вышло!", show_alert=True); return

        await self._do_buy(query, lid, lot, count, user, context, from_dm=False)

    async def _do_buy(self, query, lid, lot, count, user, context, from_dm=False):
        """Общая логика покупки — из чата и из ЛС."""
        if self._is_owner_user(user):
            await query.answer("⚠️ Админ не может покупать!", show_alert=True); return

        # Master-switch раздела «🎰 Лотерея»
        try:
            if not self.db.is_econ_section_enabled('lottery'):
                await query.answer("⏸ Лотерея временно отключена", show_alert=True); return
        except Exception:
            pass

        ud = self.db.get_user(user.id)
        if not ud:
            await query.answer("❌ /start", show_alert=True); return

        my = self._my(lid, user.id)
        can = MAX_TICKETS - my
        if can <= 0:
            await query.answer(f"❌ Лимит {MAX_TICKETS} билетов!", show_alert=True); return
        if count > can:
            await query.answer(f"❌ Можно ещё: {can}", show_alert=True); return

        price = lot['ticket_price']
        cost = price * count
        if ud['balance'] < cost:
            await query.answer(
                f"❌ Нужно {format_number(cost)} 💎\nУ вас {format_number(ud['balance'])} 💎",
                show_alert=True); return

        try:
            self.db.update_user_balance(user.id, cost, 'subtract')
            self.db.update_bank_balance(cost, 'add')
            self.db.add_transaction(user.id, None, cost, 'lottery_ticket',
                                    f"Покупка {count} бил. лотереи #{lid}")
            for _ in range(count):
                self.db.cursor.execute(
                    'INSERT INTO lottery_tickets (lottery_id,user_id) VALUES (?,?)',
                    (lid, user.id))
            self.db.cursor.execute(
                'UPDATE lotteries SET total_pool=total_pool+? WHERE id=?',
                (cost, lid))

            # 💎 Джекпот-налог: 5% от стоимости билета → в Пульсар-пул
            jackpot_tax = int(cost * JACKPOT_TAX)
            if jackpot_tax > 0:
                self._jackpot_add(jackpot_tax)

            self.db.conn.commit()
        except Exception as e:
            logger.error(f"Buy error: {e}")
            await query.answer(f"❌ {e}", show_alert=True); return

        new_my = self._my(lid, user.id)
        upd = self._get(lid)
        pool = upd['total_pool'] if upd else cost

        await query.answer(
            f"✅ Куплено: {count}\n"
            f"💎 Списано: {format_number(cost)}\n"
            f"🎟 Ваших: {new_my}/{MAX_TICKETS}\n"
            f"💰 Джекпот: {format_number(pool)}",
            show_alert=True)

        # Обновляем сообщение в чате
        await self._refresh(lid, context)

        # Если из ЛС — обновляем виджет
        if from_dm and upd:
            new_can = MAX_TICKETS - new_my
            new_qty = min(1, new_can) if new_can > 0 else 1
            try:
                await query.edit_message_text(
                    self._dm_widget_text(lid, upd, user.id, new_qty),
                    parse_mode='HTML',
                    reply_markup=self._dm_widget_kb(lid, new_qty))
            except:
                pass

    # ══════════════════════════════════════════
    #  МОИ БИЛЕТЫ
    # ══════════════════════════════════════════

    async def handle_my_tickets(self, query, data, user, context):
        try: lid = int(data.split('_')[2])
        except: await query.answer("❌", show_alert=True); return
        lot = self._get(lid)
        if not lot: await query.answer("❌", show_alert=True); return
        my = self._my(lid, user.id); t = self._total(lid)
        ch = f"{(my/t*100):.1f}%" if t>0 and my>0 else "—"
        st = "🟢" if lot['status']=='active' else "🔴"
        await query.answer(
            f"🎟 Ваших: {my}/{MAX_TICKETS}\n🎫 Всего: {t}\n"
            f"📊 Шанс: {ch}\n💰 Банк: {format_number(lot['total_pool'])}\n{st}",
            show_alert=True)

    # ══════════════════════════════════════════
    #  РОЗЫГРЫШ
    # ══════════════════════════════════════════

    async def _draw(self, lid, context) -> str:
        lot = self._get(lid)
        if not lot: return "❌ Не найдена."
        if lot['status'] != 'active': return f"❌ #{lid} уже завершена."

        self.db.cursor.execute(
            'SELECT user_id, COUNT(*) tc FROM lottery_tickets WHERE lottery_id=? GROUP BY user_id',
            (lid,))
        rows = self.db.cursor.fetchall()

        # Нет билетов вообще
        if not rows:
            self.db.cursor.execute("UPDATE lotteries SET status='cancelled' WHERE id=?",(lid,))
            self.db.conn.commit()
            await self._finish_msg(lid, context, cancelled=True)
            await self._unpin(lid, context)
            return f"🎰 #{lid} отменена — нет билетов."

        # ПРОВЕРКА: Менее 5 участников → возврат денег
        participants_count = len(rows)
        if participants_count < MIN_PARTICIPANTS:
            ticket_price = lot['ticket_price']
            
            try:
                # Возврат денег КАЖДОМУ участнику БЕЗ комиссии
                refund_list = []
                for row in rows:
                    user_id = row['user_id']
                    tickets_bought = row['tc']
                    refund_amount = ticket_price * tickets_bought

                    # Возвращаем деньги (из банка)
                    self.db.update_bank_balance(refund_amount, 'subtract')
                    self.db.update_user_balance(user_id, refund_amount, 'add')
                    self.db.add_transaction(
                        None, user_id, refund_amount, 'lottery_refund',
                        f"Возврат за лотерею #{lid} (недостаточно участников)")
                    
                    refund_list.append((user_id, refund_amount, tickets_bought))
                
                # Обновляем статус
                self.db.cursor.execute(
                    "UPDATE lotteries SET status='cancelled' WHERE id=?", (lid,))
                self.db.conn.commit()
                
                # Сообщение в чат
                chat_msg = (
                    f"🎰 <b>ЛОТЕРЕЯ #{lid} НЕ СОСТОЯЛАСЬ</b>\n\n"
                    f"❌ Недостаточно участников ({participants_count}/{MIN_PARTICIPANTS})\n\n"
                    f"💰 Всем участникам возвращена <b>полная стоимость</b> билетов\n"
                    f"📨 Проверьте баланс и уведомления в ЛС"
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=self.target_chat_id, 
                        text=chat_msg,
                        parse_mode='HTML')
                except Exception as e:
                    logger.error(f"Failed to send chat notification: {e}")
                
                # Уведомления в ЛС каждому участнику
                for user_id, refund_amount, tickets_count in refund_list:
                    user_data = self.db.get_user(user_id)
                    user_name = user_data['first_name'] if user_data and user_data['first_name'] else 'Участник'
                    
                    dm_msg = (
                        f"🎰 <b>Лотерея #{lid} не состоялась</b>\n\n"
                        f"❌ Недостаточно участников для розыгрыша\n"
                        f"(Требуется минимум {MIN_PARTICIPANTS}, было {participants_count})\n\n"
                        f"💰 <b>Возврат:</b> {format_number(refund_amount)} 💎 Пульсов\n"
                        f"🎟 За {tickets_count} билет(ов)\n\n"
                        f"✅ Средства <b>полностью</b> возвращены на ваш счёт"
                    )
                    
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=dm_msg,
                            parse_mode='HTML')
                    except Exception as e:
                        logger.warning(f"Failed to send DM to {user_id}: {e}")
                
            except Exception as e:
                logger.error(f"Refund error for lottery #{lid}: {e}")
                return f"❌ Ошибка возврата: {e}"
            
            # Обновляем/удаляем сообщение в чате
            await self._finish_msg(lid, context, cancelled=True, min_participants_failed=True)
            await self._unpin(lid, context)
            
            logger.info(f"Lottery #{lid} cancelled: {participants_count}/{MIN_PARTICIPANTS} participants")
            return (f"🎰 Лотерея #{lid} не состоялась\n"
                    f"❌ Участников: {participants_count}/{MIN_PARTICIPANTS}\n"
                    f"💰 Возвращено денег: {len(refund_list)} участникам")

        pool = lot['total_pool']
        comm = pool * COMMISSION
        net = pool - comm
        total_t = sum(r['tc'] for r in rows)
        parts = len(rows)
        mode = self._mode(lot)
        places = min(mode, parts)
        shares = PRIZE_SHARES.get(places, {1: 1.0})

        ids = [r['user_id'] for r in rows]
        wts = [r['tc'] for r in rows]
        rem_ids, rem_wts = list(ids), list(wts)

        winners = []
        for place in range(1, places + 1):
            w = random.choices(rem_ids, weights=rem_wts, k=1)[0]
            prize = int(net * shares[place])
            tix = next(r['tc'] for r in rows if r['user_id'] == w)
            winners.append((w, place, prize, tix))
            idx = rem_ids.index(w)
            rem_ids.pop(idx); rem_wts.pop(idx)

        try:
            # Комиссия остаётся в банке (деньги уже там после покупки билетов)
            comm_int = int(comm)
            self.db.add_transaction(None, None, comm_int, 'lottery_commission',
                                    f"Комиссия {int(COMMISSION*100)}% лотереи #{lid}")
            # Призы — из банка
            for (uid, place, prize, _) in winners:
                if prize <= 0: continue
                self.db.update_bank_balance(prize, 'subtract')
                self.db.update_user_balance(uid, prize, 'add')
                pl = f" ({place}-е место)" if places > 1 else ""
                self.db.add_transaction(None, uid, prize, 'lottery_win',
                                        f"Выигрыш лотереи #{lid}{pl}")
            self.db.cursor.execute(
                "UPDATE lotteries SET status='completed', winner_id=? WHERE id=?",
                (winners[0][0], lid))
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"Draw #{lid}: {e}"); return f"❌ {e}"

        await self._finish_msg(lid, context, winners=winners,
                               total_t=total_t, parts=parts, comm=comm_int, pool=pool)
        await self._unpin(lid, context)

        # ═══ ДЖЕКПОТ «ПУЛЬСАР» — шанс 1% (число 77) ═══
        jackpot_text = ""
        jp_pool = self._jackpot_pool()
        if jp_pool > 0 and winners:
            lucky_number = random.randint(1, 100)
            main_winner_id = winners[0][0]
            main_winner_name = self._name(main_winner_id)
            logger.info(f"Jackpot roll for lottery #{lid}: {lucky_number} (need {JACKPOT_LUCKY})")

            if lucky_number == JACKPOT_LUCKY:
                # 🎉 ДЖЕКПОТ СОРВАН!
                try:
                    self.db.update_bank_balance(jp_pool, 'subtract')
                    self.db.update_user_balance(main_winner_id, jp_pool, 'add')
                    self.db.add_transaction(
                        None, main_winner_id, jp_pool, 'jackpot_win',
                        f"Джекпот «Пульсар» при лотерее #{lid}")
                    self._jackpot_reset()
                    self.db.conn.commit()

                    jp_msg = (
                        f"🌟🌟🌟 <b>ДЖЕКПОТ «ПУЛЬСАР» СОРВАН!</b> 🌟🌟🌟\n\n"
                        f"🎰 Лотерея #{lid} · Число: <b>{lucky_number}</b>\n"
                        f"🏆 {main_winner_name} забирает <b>{format_number(jp_pool)} 💎</b>!\n\n"
                        f"💫 Пул Пульсара обнулён. Копилка начинается заново!"
                    )
                    try:
                        await context.bot.send_message(
                            chat_id=self.target_chat_id, text=jp_msg, parse_mode='HTML')
                    except Exception as e:
                        logger.error(f"Jackpot announce: {e}")

                    jackpot_text = f"\n\n🌟 ДЖЕКПОТ: +{format_number(jp_pool)} 💎 → {main_winner_name}"
                    logger.info(f"JACKPOT WON by {main_winner_id}: {jp_pool}")

                except Exception as e:
                    logger.error(f"Jackpot payout error: {e}")
            else:
                # Джекпот устоял
                jp_msg = (
                    f"🎲 Число: <b>{lucky_number}</b> (нужно {JACKPOT_LUCKY})\n"
                    f"🌟 Джекпот «Пульсар» устоял!\n"
                    f"💰 Пул: <b>{format_number(jp_pool)} 💎</b> → следующая игра"
                )
                try:
                    await context.bot.send_message(
                        chat_id=self.target_chat_id, text=jp_msg, parse_mode='HTML')
                except Exception as e:
                    logger.error(f"Jackpot survive msg: {e}")

        lines = []
        for (uid, place, prize, tix) in winners:
            m = MEDALS.get(place, "🏅")
            lines.append(f"{m} {self._name(uid)} — {format_number(prize)}💎 ({tix}бил.)")
        return (f"✅ <b>Лотерея #{lid}</b> разыграна!\n\n"
                + "\n".join(lines)
                + jackpot_text)
                

    # ══════════════════════════════════════════
    #  ФОНОВАЯ ЗАДАЧА
    # ══════════════════════════════════════════

    async def check_lottery_end(self, bot):
        for lot in self._active():
            lid = lot['id']
            if self._expired(lot):
                logger.info(f"Lottery #{lid} expired (end_time={lot['end_time']}) → drawing…")
                try: await self._draw(lid, _Ctx(bot))
                except Exception as e: logger.error(f"Auto-draw #{lid}: {e}")

    # ══════════════════════════════════════════
    #  DEEP-LINK ИЗ /start lottery_{id}
    # ══════════════════════════════════════════

    async def handle_start_lottery(self, update, context, lottery_id=None):
        """
        Вызывается из start_command когда payload = 'lottery' или 'lottery_N'.
        Показывает виджет покупки в ЛС.
        
        Добавьте в command_handler.py → start_command:
            if args and args[0].startswith('lottery'):
                parts = args[0].split('_')
                lid = int(parts[1]) if len(parts) > 1 else None
                await self.lottery_handler.handle_start_lottery(update, context, lid)
                return
        """
        user = update.effective_user
        lots = self._active()

        if not lots:
            await update.message.reply_text(
                "🎰 Нет активных лотерей.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Меню", callback_data="back_to_menu")]]))
            return

        # Если указан конкретный ID — показываем его
        if lottery_id:
            lot = self._get(lottery_id, active=True)
            if lot:
                my = self._my(lottery_id, user.id)
                can = MAX_TICKETS - my
                qty = min(1, can) if can > 0 else 1
                await update.message.reply_text(
                    self._dm_widget_text(lottery_id, lot, user.id, qty),
                    parse_mode='HTML',
                    reply_markup=self._dm_widget_kb(lottery_id, qty))
                return

        # Иначе — первая активная
        lot = lots[0]
        lid = lot['id']
        my = self._my(lid, user.id)
        can = MAX_TICKETS - my
        qty = min(1, can) if can > 0 else 1
        await update.message.reply_text(
            self._dm_widget_text(lid, lot, user.id, qty),
            parse_mode='HTML',
            reply_markup=self._dm_widget_kb(lid, qty))

    # ══════════════════════════════════════════
    #  СООБЩЕНИЯ + PIN
    # ══════════════════════════════════════════

    async def _publish(self, lid, context):
        lot = self._get(lid)
        if not lot: return
        try:
            msg = await context.bot.send_message(
                chat_id=self.target_chat_id,
                text=self._chat_text(lid, lot),
                parse_mode='HTML',
                reply_markup=self._chat_kb(lid))
            self.db.cursor.execute('UPDATE lotteries SET message_id=? WHERE id=?',
                                   (msg.message_id, lid))
            self.db.conn.commit()
            # Закрепляем без уведомления
            try:
                await context.bot.pin_chat_message(
                    chat_id=self.target_chat_id,
                    message_id=msg.message_id,
                    disable_notification=True)
                logger.info(f"Lottery #{lid} pinned")
            except Exception as e:
                logger.warning(f"Pin failed (no rights?): {e}")
        except Exception as e:
            logger.error(f"Publish failed: {e}")

    async def _refresh(self, lid, context):
        lot = self._get(lid)
        if not lot or not lot['message_id']: return
        try:
            await context.bot.edit_message_text(
                chat_id=self.target_chat_id,
                message_id=lot['message_id'],
                text=self._chat_text(lid, lot),
                parse_mode='HTML',
                reply_markup=self._chat_kb(lid))
        except Exception as e:
            if 'not modified' not in str(e).lower():
                logger.warning(f"Refresh: {e}")

    async def _unpin(self, lid, context):
        lot = self._get(lid)
        if not lot or not lot['message_id']: return
        try:
            await context.bot.unpin_chat_message(
                chat_id=self.target_chat_id,
                message_id=lot['message_id'])
            logger.info(f"Lottery #{lid} unpinned")
        except Exception as e:
            logger.warning(f"Unpin failed: {e}")

    async def _finish_msg(self, lid, context, cancelled=False,
                          winners=None, total_t=0, parts=0, comm=0, pool=0,
                          min_participants_failed=False):
        lot = self._get(lid)
        if not lot or not lot['message_id']: return

        if min_participants_failed:
            text = (f"🎰 <b>ЛОТЕРЕЯ #{lid} — НЕ СОСТОЯЛАСЬ</b>\n\n"
                    f"❌ Недостаточно участников (минимум {MIN_PARTICIPANTS})\n"
                    f"💰 Всем возвращена полная стоимость билетов")
        elif cancelled:
            text = f"🎰 <b>ЛОТЕРЕЯ #{lid} — ОТМЕНЕНА</b>\n\nНет билетов."
        else:
            text = f"🏆 <b>ЛОТЕРЕЯ #{lid} — РЕЗУЛЬТАТ</b>\n\n"
            for (uid, place, prize, tix) in (winners or []):
                m = MEDALS.get(place, "🏅")
                name = self._name(uid)
                if len(winners) == 1:
                    text += f"🎉 Победитель: {name}\n💰 {format_number(prize)} 💎 ({tix}/{total_t} бил.)\n"
                else:
                    text += f"{m} {name} — {format_number(prize)} 💎 ({tix} бил.)\n"
            text += (f"\n👥 {parts} участн. · 💰 банк {format_number(pool)} 💎\n"
                     f"Поздравляем! 🎊")
        try:
            await context.bot.edit_message_text(
                chat_id=self.target_chat_id, message_id=lot['message_id'],
                text=text, parse_mode='HTML', reply_markup=None)
        except Exception as e:
            logger.warning(f"Finish msg: {e}")


class _Ctx:
    def __init__(self, bot): self.bot = bot
