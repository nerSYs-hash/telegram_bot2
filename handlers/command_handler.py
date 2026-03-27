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
        user_id = update.effective_user.id
        user = await get_user(user_id) # Проверяем в базе друга

        # Если пользователя нет в базе ИЛИ у него не заполнено имя (q_name)
        if user_id == self.main_admin_id:
            logger.info(f"👑 Владелец {user_id} зашел в систему")
            # Сразу переходим к твоему обычному коду старта (лотереи и т.д.)
            pass 
        else:
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
            msg = await update.message.reply_text(f"⏳ Проверяю {total} участников батчами по 30...")

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
            batch_size = 10
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

    async def _show_lottery_deeplink(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lottery_id: int):
        """Показать виджет покупки лотереи при переходе по deep link."""
        user = update.effective_user
        
        # Регистрируем если не зарегистрирован
        user_data = self.db.get_user(user.id)
        if not user_data:
            self.db.add_user(user.id, user.username, user.first_name, user.last_name)
        
        # Делегируем в LotteryHandler — он покажет виджет +/−
        await self.lottery_handler.handle_start_lottery(update, context, lottery_id)
