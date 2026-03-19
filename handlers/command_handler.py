#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.commands.economy_commands import (
    safe_name, balance_command, pay_command, give_pulse_command, wipe_balances_command 
)
from handlers.profile_handlers import show_profile
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


class CommandHandler:
    def __init__(self, db, target_chat_id, main_admin_id, bot_username=None):
        self.db = db
        self.target_chat_id = target_chat_id
        self.main_admin_id = main_admin_id
        self.bot_username = bot_username
        self.lottery_handler = LotteryHandler(db, target_chat_id, main_admin_id, bot_username)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command — delegates to system_commands"""
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

    async def _show_lottery_deeplink(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lottery_id: int):
        """Показать виджет покупки лотереи при переходе по deep link."""
        user = update.effective_user
        
        # Регистрируем если не зарегистрирован
        user_data = self.db.get_user(user.id)
        if not user_data:
            self.db.add_user(user.id, user.username, user.first_name, user.last_name)
        
        # Делегируем в LotteryHandler — он покажет виджет +/−
        await self.lottery_handler.handle_start_lottery(update, context, lottery_id)
