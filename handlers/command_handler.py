#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.commands.economy_commands import (
    safe_name, balance_command, pay_command, give_pulse_command, wipe_balances_command 
)

from database.db_friend import get_user # Импорт из файла друга
#from handlers.profile_handlers import show_profile
from handlers.commands.donation_commands import donate_command as _donate_command
from handlers.commands.exchange_commands import course_command as _course_command
from handlers.commands.top_commands import top_command as _top_command, top5_command as _top5_command
from handlers.commands.system_commands import (
    start_command as _start_command,
    menu_command as _menu_command,
    help_command as _help_command,
)
from handlers.lottery_handlers import LotteryHandler
from utils.helpers import format_number
from datetime import datetime

logger = logging.getLogger(__name__)
class CommandHandler:
    def __init__(self, db, target_chat_id, main_admin_id, bot_username=None):
        self.db = db
        self.target_chat_id = target_chat_id
        self.main_admin_id = main_admin_id
        self.bot_username = bot_username
        self.lottery_handler = LotteryHandler(db, target_chat_id, main_admin_id, bot_username)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command — delegates to system_commands"""
        from database.db_friend import is_blacklisted, get_blacklist_reason
        from config import OWNER_ID

        user_id = update.effective_user.id
        user = await get_user(user_id) # Проверяем в базе друга

        # Если пользователя нет в базе ИЛИ у него не заполнено имя (q_name)
        if user_id == self.main_admin_id:
            logger.info(f"👑 Владелец {user_id} зашел в систему")
            # Сразу переходим к твоему обычному коду старта (лотереи и т.д.)
            pass
        else:
            # Проверяем чёрный список ДО всех остальных проверок
            if await is_blacklisted(user_id):
                reason = await get_blacklist_reason(user_id)
                try:
                    owner_chat = await context.bot.get_chat(OWNER_ID)
                    owner_name = owner_chat.full_name or str(OWNER_ID)
                except Exception:
                    owner_name = str(OWNER_ID)
                await update.message.reply_text(
                    f"⛔ {update.effective_user.first_name}, ты заблокирован(а) "
                    f"по решению администрации чата Pulse 4ever.\n\n"
                    f"📝 Причина: {reason}\n\n"
                    f"Если считаешь, что это ошибка — свяжись с администратором: "
                    f'<a href="tg://user?id={OWNER_ID}">{owner_name}</a>',
                    parse_mode="HTML"
                )
                return

            # 2. Если это обычный юзер, проверяем регистрацию в базе друга
            user = await get_user(user_id)

            if not user or not user.get('q_name'):
                await update.message.reply_text(
                    "Привет! Ты еще не зарегистрирован. Напиши /register"
                )
                return
            if user.get('status') != 'approved':
                await update.message.reply_text("⏳ Твоя анкета еще на проверке у администраторов. Пожалуйста, подожди!")
            return
        
        # --- ИНТЕГРАЦИЯ МОЕЙ РЕФЕРАЛКИ ---
        if context.args:
            token = context.args[0]
            referrer_id = self.db.get_referrer_by_token(token) 
            if referrer_id:
                context.user_data['referred_by'] = referrer_id
                logger.info(f"Юзер {user_id} пришел по токену от {referrer_id}")
                
        # Проверяем deep link для лотереи: /start lottery_123
        if context.args and len(context.args) > 0:
            arg = context.args[0]
            
            # Deep link для лотереи
            if arg.startswith('lottery_'):
                try:
                    lottery_id = int(arg.split('_')[1])
                    await self._show_lottery_deeplink(update, context, lottery_id)
                    return
                except (IndexError, ValueError):
                    pass  # Если ошибка парсинга - продолжаем обычный /start
        
        # Обычный /start
        await _start_command(update, context, self.db, self.target_chat_id)

    async def set_bank_command(self, update, context):
        """Установить баланс банка: /set_bank 1000000"""
        if update.effective_user.id != self.main_admin_id:
            return
        if not context.args:
            await update.message.reply_text("Использование: /set_bank 1000000")
            return
        amount = int(context.args[0])
        self.db.set_setting('bank_balance', str(amount))
        self.db.conn.commit()
        await update.message.reply_text(f"✅ Банк установлен: {amount} 💎")

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command — delegates to system_commands"""
        await _menu_command(update, context, self.db, self.main_admin_id)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command — delegates to system_commands"""
        await _help_command(update, context)

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command — delegates to economy_commands"""
        await balance_command(update, context, self.db)

    async def top_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /top command — delegates to top_commands"""
        await _top_command(update, context, self.db)

    async def give_pulse_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /give_pulse command — delegates to economy_commands"""
        await give_pulse_command(update, context, self.db, self.main_admin_id)

    async def pay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pay command — delegates to economy_commands"""
        await pay_command(update, context, self.db)

    async def donate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /donate command — delegates to donation_commands"""
        await _donate_command(update, context, self.db)

    async def course_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /курс or /course or /kurs command"""
        await _course_command(update=update, context=context, db=self.db, admin_id=self.main_admin_id, target_chat_id=self.target_chat_id)

    async def top5_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /top5 command — delegates to top_commands"""
        await _top5_command(update, context, self.db, self.main_admin_id, self.target_chat_id)

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /profile command"""
        await show_profile(update, context, self.db, update.effective_user.id)

    async def wipe_balances_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /wipe_balances command"""
        await wipe_balances_command(update, context, self.db, self.main_admin_id)

    async def fix_left_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверить всех пользователей через Telegram API и пометить вышедших (is_left=1)"""
        try:
            from database.db_friend import is_admin as is_reg_admin
            user_id = update.effective_user.id
            is_owner = user_id == self.main_admin_id
            user_data = self.db.get_user(user_id)
            # Проверяем: владелец, админ в основной БД, или админ в db_friend
            is_main_admin = False
            if user_data:
                try:
                    is_main_admin = bool(user_data['is_owner'] or user_data['is_admin'])
                except (KeyError, IndexError):
                    pass
            is_friend_admin = await is_reg_admin(user_id)
            if not (is_owner or is_main_admin or is_friend_admin):
                await update.message.reply_text("❌ Нет доступа.")
                return

            import asyncio
            rows = self.db.conn.execute(
                'SELECT user_id FROM users WHERE is_left = 0 AND is_owner = 0'
            ).fetchall()
            users = list(rows)
            total = len(users)
            batch_size = 10
            msg = await update.message.reply_text(f"⏳ Проверяю {total} участников батчами по {batch_size}...")

            errors = 0

            async def check_user(uid):
                nonlocal errors
                try:
                    member = await context.bot.get_chat_member(self.target_chat_id, uid, read_timeout=5, write_timeout=5)
                    if member.status in ('left', 'kicked'):
                        return uid
                    return None
                except Exception as e:
                    errors += 1
                    err_str = str(e).lower()
                    # Если юзер не найден, удалён, заблокировал бота — помечаем как вышедшего
                    if any(kw in err_str for kw in ('not found', 'forbidden', 'kicked', 'deactivated', 'blocked')):
                        logger.info(f"fix_left: {uid} помечен (ошибка API: {e})")
                        return uid
                    logger.warning(f"fix_left: не удалось проверить {uid}: {e}")
                    return None

            marked = 0
            for i in range(0, total, batch_size):
                batch = [row[0] for row in users[i:i + batch_size]]
                results = await asyncio.gather(*[check_user(uid) for uid in batch])
                for uid in results:
                    if uid:
                        self.db.conn.execute('UPDATE users SET is_left = 1 WHERE user_id = ?', (uid,))
                        marked += 1
                self.db.conn.commit()
                await asyncio.sleep(2)

            await msg.edit_text(
                f"✅ Готово!\n"
                f"Проверено: {total}\n"
                f"Помечено как вышедших: {marked}\n"
                f"Ошибок API: {errors}"
            )
        except Exception as e:
            logger.error(f"fix_left_command error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def remove_from_top_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Убрать пользователя из топов по @username или user_id. Доступно @Nersys и владельцу."""
        try:
            caller = update.effective_user
            caller_username = (caller.username or '').lower()
            is_allowed = (caller.id == self.main_admin_id or caller_username == 'nersys')
            if not is_allowed:
                await update.message.reply_text("❌ Нет доступа.")
                return

            if not context.args:
                await update.message.reply_text("Использование: /remove_from_top @username или /remove_from_top 123456789")
                return

            target = context.args[0].lstrip('@')
            # Поиск: сначала по username, потом по user_id
            target_user = None
            try:
                target_id = int(target)
                target_user = self.db.get_user(target_id)
            except ValueError:
                # Ищем по username
                self.db.cursor.execute('SELECT * FROM users WHERE username = ?', (target,))
                row = self.db.cursor.fetchone()
                if row:
                    target_user = row

            if not target_user:
                await update.message.reply_text(f"❌ Пользователь «{target}» не найден в базе.")
                return

            uid = target_user['user_id']
            uname = target_user['username'] or target_user['first_name'] or str(uid)

            if target_user['is_left']:
                await update.message.reply_text(f"ℹ️ @{uname} уже помечен как вышедший.")
                return

            # Пометить + заморозить + вернуть в банк
            from datetime import timedelta
            balance = float(target_user['balance'] or 0)
            self.db.cursor.execute('UPDATE users SET is_left = 1 WHERE user_id = ?', (uid,))
            self.db.conn.commit()

            result = f"✅ @{uname} убран из топов (is_left=1)"
            if balance > 0:
                now = datetime.now()
                freeze_until = now + timedelta(days=30)
                self.db.cursor.execute(
                    'UPDATE users SET frozen_balance = ?, freeze_until = ? WHERE user_id = ?',
                    (balance, freeze_until, uid)
                )
                self.db.update_user_balance(uid, 0, 'set')
                self.db.update_bank_balance(balance, 'add')
                self.db.conn.commit()
                from utils.helpers import format_number
                result += f"\n💰 Баланс {format_number(balance)} 💎 заморожен на 30 дней и возвращён в банк"

            await update.message.reply_text(result)
        except Exception as e:
            logger.error(f"remove_from_top error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def unfreeze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Разморозить пульсы пользователя по @username или user_id. Доступно @Nersys и владельцу."""
        try:
            caller = update.effective_user
            caller_username = (caller.username or '').lower()
            is_allowed = (caller.id == self.main_admin_id or caller_username == 'nersys')
            if not is_allowed:
                await update.message.reply_text("❌ Нет доступа.")
                return

            if not context.args:
                await update.message.reply_text("Использование: /unfreeze @username или /unfreeze 123456789")
                return

            target = context.args[0].lstrip('@')
            target_user = None
            try:
                target_id = int(target)
                target_user = self.db.get_user(target_id)
            except ValueError:
                self.db.cursor.execute('SELECT * FROM users WHERE username = ?', (target,))
                row = self.db.cursor.fetchone()
                if row:
                    target_user = row

            if not target_user:
                await update.message.reply_text(f"❌ Пользователь «{target}» не найден в базе.")
                return

            uid = target_user['user_id']
            uname = target_user['username'] or target_user['first_name'] or str(uid)

            try:
                frozen_balance = float(target_user['frozen_balance'] or 0)
            except (KeyError, IndexError):
                frozen_balance = 0

            if frozen_balance <= 0:
                await update.message.reply_text(f"ℹ️ У @{uname} нет замороженных пульсов.")
                return

            from utils.helpers import format_number

            bank_balance = self.db.get_bank_balance()
            restore_amount = frozen_balance
            if bank_balance < frozen_balance:
                restore_amount = bank_balance

            self.db.update_bank_balance(restore_amount, 'subtract')
            self.db.update_user_balance(uid, restore_amount, 'add')
            self.db.add_transaction(
                None, uid, restore_amount, 'unfreeze_manual',
                f'Ручная разморозка администратором {caller.id}'
            )
            self.db.cursor.execute(
                'UPDATE users SET is_left = 0, frozen_balance = 0, freeze_until = NULL WHERE user_id = ?',
                (uid,)
            )
            self.db.conn.commit()

            result = (
                f"✅ @{uname} разморожен!\n"
                f"💰 {format_number(restore_amount)} 💎 возвращено на баланс\n"
                f"🏦 Банк: {format_number(self.db.get_bank_balance())} 💎"
            )
            await update.message.reply_text(result)

        except Exception as e:
            logger.error(f"unfreeze error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def _show_lottery_deeplink(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lottery_id: int):
        """Показать виджет покупки лотереи при переходе по deep link."""
        user = update.effective_user
        
        # Регистрируем если не зарегистрирован
        user_data = self.db.get_user(user.id)
        if not user_data:
            self.db.add_user(user.id, user.username, user.first_name, user.last_name)
        
        # Делегируем в LotteryHandler — он покажет виджет +/−
        await self.lottery_handler.handle_start_lottery(update, context, lottery_id)
