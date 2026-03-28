#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.commands.economy_commands import (
    safe_name, balance_command, pay_command, give_pulse_command, wipe_balances_command 
)

from database.db_friend import get_user, get_user_pending_application
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
            # Проверяем фактическое нахождение в чате
            is_member = False
            try:
                from telegram import ChatMemberStatus
                if self.target_chat_id and self.target_chat_id != 0:
                    member = await context.bot.get_chat_member(self.target_chat_id, user_id)
                    is_member = member.status in (
                        ChatMemberStatus.MEMBER,
                        ChatMemberStatus.ADMINISTRATOR,
                        ChatMemberStatus.OWNER,
                    ) or (member.status == ChatMemberStatus.RESTRICTED and getattr(member, 'is_member', True))
            except Exception as e:
                logger.warning(f"start_command: API membership check failed for {user_id}: {e}")
                is_member = False

            # Фоллбэк: проверяем основную БД
            if not is_member:
                try:
                    main_user = self.db.get_user(user_id)
                    if main_user:
                        try:
                            is_left = main_user['is_left']
                        except (KeyError, IndexError):
                            is_left = 1
                        if not is_left:
                            is_member = True
                            logger.info(f"start_command: user {user_id} found in main DB (is_left=0)")
                except Exception as e:
                    logger.warning(f"start_command: main DB fallback failed for {user_id}: {e}")

            # Вышедший из чата — уже одобрен, просто вернулся; ИЛИ фактически в чате
            if is_member or user.get('status') in ('approved', 'in_chat', 'registered', 'left'):
                # Если он фактически в чате, но статус старый, починим
                try:
                    from database.db_friend import close_user_applications
                    # Всегда закрываем старые анкеты, если доступ уже есть
                    await close_user_applications(user_id)
                    
                    if is_member and user.get('status') not in ('approved', 'in_chat', 'registered'):
                        from database.db_friend import update_user as update_reg_user
                        await update_reg_user(user_id, status='in_chat')
                except Exception as e:
                    logger.error(f"Failed to sync status/close apps for {user_id}: {e}")
                pass  # пропускаем проверку, продолжаем обычный /start
            else:
                # Проверяем есть ли активная заявка
                pending_app = await get_user_pending_application(user_id)
                if pending_app:
                    await update.message.reply_text("⏳ Твоя анкета ещё на проверке у администраторов. Пожалуйста, подожди!")
                else:
                    # Заявка потерялась — предлагаем пройти заново
                    kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton("📝 Подать заявку заново", callback_data="restart_registration")
                    ]])
                    await update.message.reply_text(
                        "⚠️ Похоже, что-то пошло не так — твоя заявка не найдена в системе.\n\n"
                        "Нажми кнопку ниже, чтобы пройти анкету заново:",
                        reply_markup=kb
                    )
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
            user_data = self.db.get_user(update.effective_user.id)
            is_allowed = (update.effective_user.id == self.main_admin_id or
                          (user_data and (user_data.get('is_owner') or user_data.get('is_admin'))))
            if not is_allowed:
                await update.message.reply_text("❌ Нет доступа.")
                return

            import asyncio
            rows = self.db.conn.execute(
                'SELECT user_id FROM users WHERE is_left = 0 AND is_owner = 0'
            ).fetchall()
            users = list(rows)
            total = len(users)
            msg = await update.message.reply_text(f"⏳ Проверяю {total} участников батчами по 30...")

            async def check_user(uid):
                try:
                    member = await context.bot.get_chat_member(self.target_chat_id, uid, read_timeout=5, write_timeout=5)
                    return uid if member.status in ('left', 'kicked') else None
                except Exception:
                    return None

            marked = 0
            batch_size = 30
            for i in range(0, total, batch_size):
                batch = [row[0] for row in users[i:i + batch_size]]
                results = await asyncio.gather(*[check_user(uid) for uid in batch])
                for uid in results:
                    if uid:
                        self.db.conn.execute('UPDATE users SET is_left = 1 WHERE user_id = ?', (uid,))
                        marked += 1
                self.db.conn.commit()
                await asyncio.sleep(1)

            await msg.edit_text(
                f"✅ Готово!\n"
                f"Проверено: {total}\n"
                f"Помечено как вышедших: {marked}"
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

    async def panel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /panel — открыть Панель Владельца из любого чата"""
        user_id = update.effective_user.id
        from database.db_friend import is_admin as is_reg_admin
        is_owner = user_id == self.main_admin_id
        user_data = self.db.get_user(user_id)
        is_admin = is_owner or (user_data and (user_data.get('is_admin') or user_data.get('is_owner')))
        if not is_admin:
            return
        from handlers.admin_moderation import send_admin_panel
        chat_id = update.effective_chat.id
        thread_id = update.message.message_thread_id if update.message and update.message.message_thread_id else None
        await send_admin_panel(context.bot, chat_id, is_owner=is_owner, thread_id=thread_id)

    async def test_wipe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """[DEV ONLY] /test_wipe — удалить тестовых пользователей за последние 24 часа из обеих БД"""
        if update.effective_user.id != self.main_admin_id:
            return

        from datetime import timedelta
        import aiosqlite
        from database.db_friend import DB_PATH as FRIEND_DB_PATH

        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()

        # 1. Берём ID из db_friend (pulse_bot.db) — там регистрация, колонка tg_id
        friend_ids = []
        try:
            async with aiosqlite.connect(FRIEND_DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT tg_id FROM users WHERE created_at >= ? AND tg_id != ?",
                    (cutoff, self.main_admin_id)
                ) as cur:
                    rows = await cur.fetchall()
                    friend_ids = [r['tg_id'] for r in rows]

                if friend_ids:
                    ph = ','.join('?' * len(friend_ids))
                    await db.execute(f"DELETE FROM applications WHERE user_id IN ({ph})", friend_ids)
                    await db.execute(f"DELETE FROM users WHERE tg_id IN ({ph})", friend_ids)
                    await db.commit()
        except Exception as e:
            logger.error(f"test_wipe db_friend error: {e}")

        # 2. Удаляем те же ID из основной БД (bot_database.db)
        main_deleted = 0
        if friend_ids:
            ph = ','.join('?' * len(friend_ids))
            for table in ('transactions', 'user_activity', 'messages'):
                try:
                    self.db.cursor.execute(f"DELETE FROM {table} WHERE user_id IN ({ph})", friend_ids)
                except Exception:
                    pass
            self.db.cursor.execute(f"DELETE FROM users WHERE user_id IN ({ph})", friend_ids)
            main_deleted = self.db.cursor.rowcount
            self.db.conn.commit()

        # 3. Кикаем из Telegram-группы (иначе новая invite link будет недействительна)
        kicked = 0
        for uid in friend_ids:
            try:
                await context.bot.ban_chat_member(self.target_chat_id, uid)
                await context.bot.unban_chat_member(self.target_chat_id, uid)  # снимаем бан сразу (soft kick)
                kicked += 1
            except Exception:
                pass

        await update.message.reply_text(
            f"🧹 [DEV] Из db_friend удалено: {len(friend_ids)} польз.\n"
            f"Из основной БД удалено: {main_deleted} польз.\n"
            f"Из Telegram-группы кикнуто: {kicked} польз."
        )

    async def wipe_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """[DEV ONLY] /wipe_user USER_ID — полностью удалить пользователя из обеих БД + кикнуть из чата"""
        if update.effective_user.id != self.main_admin_id:
            return

        if not context.args:
            await update.message.reply_text("Использование: /wipe_user USER_ID")
            return

        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ USER_ID должен быть числом")
            return

        import aiosqlite
        from database.db_friend import DB_PATH as FRIEND_DB_PATH

        # 1. Удаляем из db_friend (pulse_bot.db)
        friend_deleted = 0
        try:
            async with aiosqlite.connect(FRIEND_DB_PATH) as db:
                await db.execute("DELETE FROM applications WHERE user_id = ?", (target_id,))
                await db.execute("DELETE FROM users WHERE tg_id = ?", (target_id,))
                friend_deleted = db.total_changes
                await db.commit()
        except Exception as e:
            logger.error(f"wipe_user db_friend error: {e}")

        # 2. Удаляем из основной БД
        main_deleted = 0
        try:
            for table in ('transactions', 'user_activity', 'messages'):
                try:
                    self.db.cursor.execute(f"DELETE FROM {table} WHERE user_id = ?", (target_id,))
                except Exception:
                    pass
            self.db.cursor.execute("DELETE FROM users WHERE user_id = ?", (target_id,))
            main_deleted = self.db.cursor.rowcount
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"wipe_user main db error: {e}")

        # 3. Кикаем из Telegram-группы
        kicked = False
        try:
            await context.bot.ban_chat_member(self.target_chat_id, target_id)
            await context.bot.unban_chat_member(self.target_chat_id, target_id)
            kicked = True
        except Exception as e:
            logger.warning(f"wipe_user kick error: {e}")

        await update.message.reply_text(
            f"🧹 [DEV] Пользователь {target_id}:\n"
            f"  db_friend: {'удалён' if friend_deleted else 'не найден'}\n"
            f"  основная БД: {'удалён' if main_deleted else 'не найден'}\n"
            f"  Telegram-группа: {'кикнут' if kicked else 'ошибка/не в группе'}"
        )

    async def _show_lottery_deeplink(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lottery_id: int):
        """Показать виджет покупки лотереи при переходе по deep link."""
        user = update.effective_user
        
        # Регистрируем если не зарегистрирован
        user_data = self.db.get_user(user.id)
        if not user_data:
            self.db.add_user(user.id, user.username, user.first_name, user.last_name)
        
        # Делегируем в LotteryHandler — он покажет виджет +/−
        await self.lottery_handler.handle_start_lottery(update, context, lottery_id)
