#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.commands.economy_commands import (
    safe_name, balance_command, pay_command, tip_command, give_pulse_command, wipe_balances_command
)
from utils.ai_core import ask_ai
from database.db_friend import get_user, get_user_pending_application, is_blacklisted, get_blacklist_reason
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
    async def restore_news_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Восстановить все посты НьюзON (только для владельца)."""
        if update.effective_user.id != self.main_admin_id:
            await update.message.reply_text("⛔ Нет доступа.")
            return
        from handlers.owner_handlers import restore_news_execute
        class DummyQuery:
            def __init__(self, message):
                self.message = message
                self.from_user = message.from_user
            async def answer(self, *a, **kw):
                pass
            async def edit_message_text(self, text, **kwargs):
                await self.message.reply_text(text, **kwargs)
        dummy_query = DummyQuery(update.message)
        await restore_news_execute(dummy_query, context, self.db, self.main_admin_id)

    async def resend_dossier_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Принудительно опубликовать досье пользователя из БД (владелец и разработчик).
        Использование: /resend_dossier <user_id>
        """
        if not context.args:
            await update.message.reply_text("Использование: /resend_dossier <user_id>")
            return

        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ user_id должен быть числом.")
            return

        import html as _html
        from database.db_friend import get_user as _get_reg_user
        from handlers.admin_moderation import _fmt_date, _msk_now
        from handlers.anketa_edit_handlers import ensure_anketa_edit_tables, upsert_anketa_edit, inject_presence
        from config import CHAT_ID, ADMIN_CHAT_ID, DOSSIER_THREAD_ID, DEVELOPER_ID
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton

        # Разрешено: владелец и разработчик
        caller = update.effective_user.id
        if caller != self.main_admin_id and caller != DEVELOPER_ID:
            await update.message.reply_text("⛔ Нет доступа.")
            return

        await update.message.reply_text(
            f"⏳ Ищу данные для user_id={target_id}…\n"
            f"📍 Цель: chat={ADMIN_CHAT_ID} thread={DOSSIER_THREAD_ID}"
        )

        reg_data = await _get_reg_user(target_id)
        if not reg_data:
            await update.message.reply_text(
                f"❌ Пользователь {target_id} не найден в БД регистраций.\n"
                f"Убедись, что ID верный."
            )
            return

        admin_name = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)
        is_returning = bool(reg_data.get('last_exit_at'))
        block_b = "#Возвращение" if is_returning else "#Новый"
        username_str = f"@{reg_data.get('username')}" if reg_data.get('username') else "нет"
        full_name = _html.escape(
            f"{reg_data.get('first_name') or ''} {reg_data.get('last_name') or ''}".strip()
            or reg_data.get('q_name') or '—'
        )
        user_link = f'<a href="tg://user?id={target_id}">{full_name}</a>'
        group_link = f'<a href="https://t.me/c/{str(CHAT_ID).replace("-100", "")}/1">Pulse 4ever</a>'
        applied_at = _fmt_date(reg_data.get('created_at'))
        joined_at = _msk_now()

        card_text = (
            f"#Одобрено (ручная отправка)\n"
            f"{block_b}\n"
            f"Досье восстановлено {admin_name}\n\n"
            f"Группа: {group_link}\n"
            f"Пользователь: {user_link}\n"
            f"Никнейм: {username_str}\n"
            f"ID: <code>{target_id}</code> <b>#user{target_id}</b>\n\n"
            f"<b>Анкета:</b>\n"
            f"Имя: {_html.escape(reg_data.get('q_name') or '—')}\n"
            f"Возраст: {reg_data.get('q_age') or '—'}\n"
            f"Город: {_html.escape(reg_data.get('q_city') or '—')}\n"
            f"Терапия: {_html.escape(reg_data.get('q_therapy') or '—')}\n\n"
            f"📅 Дата заявки: {applied_at}\n"
            f"✅ Дата вступления: {joined_at}"
            + (f"\n🔁 Первое вступление: {_fmt_date(reg_data.get('created_at'))}" if is_returning else "")
        )

        # Добавляем индикатор присутствия — проверяем реальный статус в TG
        _in_chat = False
        try:
            _cm = await context.bot.get_chat_member(CHAT_ID, target_id)
            _in_chat = _cm.status not in ('left', 'kicked', 'banned')
        except Exception as e:
            logger.warning(f"resend_dossier get_chat_member error: {e}")
        try:
            card_text = inject_presence(card_text, in_chat=_in_chat)
        except Exception as e:
            logger.warning(f"resend_dossier inject_presence error: {e}")

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✉️ Написать в ЛС", url=f"tg://user?id={target_id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"anketa_edit_{target_id}"),
            ]
        ])

        # Пробуем найти фото с лицом
        face_photo = None
        try:
            from utils.face_detector import has_human_face
            photos = await context.bot.get_user_profile_photos(target_id, limit=3)
            for photo_size_list in (photos.photos or []):
                try:
                    file = await context.bot.get_file(photo_size_list[-1].file_id)
                    byte_array = await file.download_as_bytearray()
                    if await has_human_face(byte_array):
                        face_photo = photo_size_list[-1].file_id
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"resend_dossier photo check error: {e}")

        # Отправляем напрямую с нормальными ошибками
        try:
            ensure_anketa_edit_tables(self.db)
            if face_photo:
                sent = await context.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    message_thread_id=DOSSIER_THREAD_ID,
                    photo=face_photo,
                    caption=card_text,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                upsert_anketa_edit(self.db, target_id,
                                   dossier_chat_id=sent.chat.id,
                                   dossier_msg_id=sent.message_id,
                                   dossier_is_photo=1,
                                   admin_username=admin_name,
                                   base_text=card_text)
            else:
                no_face_text = card_text + "\n\n<i>(⚠️ ИИ не обнаружил человеческого лица на аватарках)</i>"
                sent = await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    message_thread_id=DOSSIER_THREAD_ID,
                    text=no_face_text,
                    parse_mode="HTML",
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
                upsert_anketa_edit(self.db, target_id,
                                   dossier_chat_id=sent.chat.id,
                                   dossier_msg_id=sent.message_id,
                                   dossier_is_photo=0,
                                   admin_username=admin_name,
                                   base_text=no_face_text)
            await update.message.reply_text(f"✅ Досье для user_id={target_id} опубликовано в ветке Досье (msg_id={sent.message_id}).")
        except Exception as e:
            logger.error(f"resend_dossier send error: {e}")
            await update.message.reply_text(f"❌ Ошибка при отправке в ветку: {e}")

    async def restore_bbs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Восстановить все анкеты BBS (только для владельца)."""
        if update.effective_user.id != self.main_admin_id:
            await update.message.reply_text("⛔ Нет доступа.")
            return
        from handlers.owner_handlers import restore_bbs_execute
        # Эмулируем query для совместимости с restore_bbs_execute
        class DummyQuery:
            def __init__(self, message):
                self.message = message
                self.from_user = message.from_user
            async def answer(self, *a, **kw):
                pass
            async def edit_message_text(self, text, **kwargs):
                await self.message.reply_text(text, **kwargs)
        dummy_query = DummyQuery(update.message)
        await restore_bbs_execute(dummy_query, context, self.db, self.main_admin_id)

    async def restore_last_bbs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Восстановить ПОСЛЕДНЮЮ удаленную анкету BBS (только для владельца)."""
        if update.effective_user.id != self.main_admin_id:
            await update.message.reply_text("⛔ Нет доступа.")
            return
        from handlers.owner_handlers import restore_last_bbs_execute
        # Эмулируем query для совместимости с restore_last_bbs_execute
        class DummyQuery:
            def __init__(self, message):
                self.message = message
                self.from_user = message.from_user
            async def answer(self, *a, **kw):
                pass
            async def edit_message_text(self, text, **kwargs):
                await self.message.reply_text(text, **kwargs)
        dummy_query = DummyQuery(update.message)
        await restore_last_bbs_execute(dummy_query, context, self.db, self.main_admin_id)
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

        # ── Deep link для жалобы BBS: обрабатываем ДО всех проверок регистрации ──
        if context.args and context.args[0].startswith('report_'):
            await _start_command(update, context, self.db, self.target_chat_id)
            return

        # ── Deep link реферал ref1_xxx: токен сохраняем В БД сразу,
        # чтобы он пережил всю регистрационную цепочку (даже если юзер уйдёт и вернётся) ──
        if context.args and context.args[0].startswith('ref1_'):
            token = context.args[0]
            try:
                referrer_id = self.db.get_referrer_by_token(token)
                if referrer_id and referrer_id != user_id:
                    # Сохраняем токен в context (для финализации после регистрации)
                    context.user_data['pending_ref_token'] = token
                    context.user_data['pending_ref_referrer_id'] = referrer_id

                    # Если юзер ещё не в db_friend — создадим запись и сразу впишем referred_by
                    from database.db_friend import get_user as _get_friend_user, create_user, update_user
                    friend_user = await _get_friend_user(user_id)
                    if not friend_user:
                        await create_user(
                            user_id,
                            update.effective_user.username or '',
                            update.effective_user.first_name or '',
                            update.effective_user.last_name or '',
                        )
                    # Записываем referrer_id (integer) — переживёт регистрацию
                    await update_user(user_id, referred_by=referrer_id)
                    logger.info(f"🔗 Реф-токен {token}: юзер {user_id} привязан к {referrer_id}")
            except Exception as e:
                logger.error(f"Ошибка обработки реф-токена {context.args[0]} для {user_id}: {e}")

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

            # 2. Проверяем q_name в PTB-БД (aiogram-БД больше не используется)
            user = await get_user(user_id)
            q_name = user.get('q_name') if user else None

            # Пользователь совсем не регистрировался — нет q_name
            if not q_name:
                # Проверяем: может есть pending-заявка или одобренная (q_name слетел при тестах/сбое)
                pending_app = await get_user_pending_application(user_id)
                if pending_app:
                    await update.message.reply_text("⏳ Твоя анкета ещё на проверке у администраторов. Пожалуйста, подожди!")
                    return

                # Третий fallback: ищем одобренную заявку — значит пользователь был в чате
                approved_app = None
                try:
                    from database.db_friend import db_pool
                    from constants import ApplicationStatus
                    async with db_pool.get_connection() as _db:
                        async with _db.execute(
                            "SELECT * FROM applications WHERE user_id = ? AND status = ? ORDER BY created_at DESC LIMIT 1",
                            (user_id, ApplicationStatus.APPROVED)
                        ) as _cur:
                            from database.db_friend import row_to_dict
                            approved_app = row_to_dict(await _cur.fetchone())
                except Exception as e:
                    logger.error(f"Approved app fallback failed for {user_id}: {e}")

                if approved_app:
                    # Пользователь был одобрен — имя берём из TG-профиля, генерируем ссылку
                    q_name = update.effective_user.first_name
                else:
                    kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton("📝 Подать заявку", callback_data="restart_registration")
                    ]])
                    await update.message.reply_text(
                        "👋 Привет! Ты ещё не зарегистрирован в Pulse 4ever.\n\n"
                        "Нажми кнопку ниже, чтобы подать заявку:",
                        reply_markup=kb
                    )
                    return

            # Проверяем фактическое нахождение в чате (железобетонная проверка)
            from utils.membership import verify_chat_membership
            is_member = await verify_chat_membership(
                context.bot, self.target_chat_id, user_id, db=self.db
            )

            if is_member:
                # Закрываем старые анкеты — статус уже синхронизирован в verify_chat_membership
                try:
                    from database.db_friend import close_user_applications
                    await close_user_applications(user_id)
                except Exception as e:
                    logger.error(f"Failed to close apps for {user_id}: {e}")
                pass  # продолжаем обычный /start
            else:
                # Пользователь НЕ в чате, но q_name есть → возвращение
                tg_status = None
                try:
                    cm = await context.bot.get_chat_member(self.target_chat_id, user_id)
                    tg_status = cm.status
                except Exception:
                    pass

                if tg_status == 'kicked':
                    owner_link = f'<a href="tg://user?id={self.main_admin_id}">владельца чата</a>'
                    await update.message.reply_text(
                        f"🚫 К сожалению, ты был заблокирован в чате Pulse 4ever.\n\n"
                        f"Самостоятельное возвращение невозможно. Если считаешь, что блокировка "
                        f"была ошибочной — напиши {owner_link}, чтобы уточнить возможность возвращения.",
                        parse_mode="HTML"
                    )
                else:
                    name = q_name or update.effective_user.first_name
                    try:
                        from database.db_friend import create_invite_link as _save_invite
                        invite_obj = await context.bot.create_chat_invite_link(
                            self.target_chat_id,
                            member_limit=1,
                            name=f"ret_{user_id}"[:32],
                        )
                        invite_url = invite_obj.invite_link
                        sent = await update.message.reply_text(
                            f"👋 С возвращением, {name}!\n\n"
                            f"Рады снова видеть тебя в Pulse 4ever 🤍\n\n"
                            f"🔗 Твоя персональная ссылка для входа в чат:\n{invite_url}\n\n"
                            f"⚠️ Ссылка одноразовая — действует только для тебя и "
                            f"сгорит сразу после использования."
                        )
                        await _save_invite(user_id, invite_url)
                        logger.info(f"Return invite sent to {user_id}: {invite_url}")
                    except Exception as e:
                        logger.error(f"Error creating return invite for {user_id}: {e}")
                        await update.message.reply_text(
                            "❌ Не удалось создать ссылку для входа. Обратитесь к администратору."
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

    async def tip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /tip <amount> — quick reply tip; delegates to economy_commands"""
        await tip_command(update, context, self.db)

    async def donate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /donate command — delegates to donation_commands"""
        await _donate_command(update, context, self.db)

    async def course_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /курс or /course or /kurs command"""
        await _course_command(update=update, context=context, db=self.db, target_chat_id=self.target_chat_id)

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

    async def mute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /mute command — делегирует moderation.mute_command."""
        from handlers.moderation import mute_command as _mute
        await _mute(update, context, self.db, self.main_admin_id, self.target_chat_id)

    async def unmute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unmute command — делегирует moderation.unmute_command."""
        from handlers.moderation import unmute_command as _unmute
        await _unmute(update, context, self.db, self.main_admin_id, self.target_chat_id)

    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ban command — делегирует moderation.ban_command."""
        from handlers.moderation import ban_command as _ban
        await _ban(update, context, self.db, self.main_admin_id, self.target_chat_id)

    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unban command — делегирует moderation.unban_command."""
        from handlers.moderation import unban_command as _unban
        await _unban(update, context, self.db, self.main_admin_id, self.target_chat_id)

    async def _show_lottery_deeplink(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lottery_id: int):
        """Показать виджет покупки лотереи при переходе по deep link."""
        user = update.effective_user
        
        # Регистрируем если не зарегистрирован
        user_data = self.db.get_user(user.id)
        if not user_data:
            self.db.add_user(user.id, user.username, user.first_name, user.last_name)
        
        # Делегируем в LotteryHandler — он покажет виджет +/−
        await self.lottery_handler.handle_start_lottery(update, context, lottery_id)
