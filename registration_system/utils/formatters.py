"""
Модуль для форматирования текста и данных
Содержит функции для форматирования заявок, дат, сообщений и уведомлений
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
import re

from constants import Hashtags


def format_application_text(user: Dict[str, Any], app: Optional[Dict[str, Any]] = None) -> str:
    """Форматирование текста заявки согласно ТЗ"""
    is_returning = user.get('last_exit_at') is not None
    status_tag = "#Возвращение" if is_returning else "#Новый"
    
    text = f"#Новая_заявка\n{status_tag}\n\n"
    text += f"👤 Пользователь: {user.get('first_name', '')} {user.get('last_name', '')}".strip() + "\n"
    
    if user.get('username'):
        text += f"📱 @{user['username']}\n"
    
    text += f"🆔 #user{user['tg_id']}\n\n"
    text += f"📋 Анкета:\n"
    text += f"Имя: {user.get('q_name', '—')}\n"
    text += f"Возраст: {user.get('q_age', '—')}\n"
    text += f"Город: {user.get('q_city', '—')}\n"
    text += f"Терапия: {user.get('q_therapy', '—')}\n\n"
    
    if user.get('birth_date'):
        text += f"📅 Дата рождения: {user['birth_date']}\n"
    
    if user.get('last_rejection_reason'):
        text += f"🚨 Внимание! Пользователь уже подавал заявку.\n"
        text += f"Причина отказа: {user['last_rejection_reason']}\n\n"
    
    if app and app.get('created_at'):
        created = datetime.fromisoformat(app['created_at'])
        text += f"📅 Дата заявки: {created.strftime('%d.%m.%Y %H:%M')}\n"
    
    return text


def format_approval_text(user: Dict[str, Any], app: Dict[str, Any], admin_username: str) -> str:
    """Форматирование текста одобренной заявки согласно ТЗ п.3.3.3"""
    is_returning = user.get('last_exit_at') is not None
    status_tag = "#Возвращение" if is_returning else "#Новый"
    
    # Форматируем дату заявки
    app_date = ""
    if app.get('created_at'):
        created = datetime.fromisoformat(app['created_at'])
        app_date = f"📅 {created.strftime('%d.%m.%Y %H:%M')}"
    
    text = f"#Одобрено\n"
    text += f"{status_tag}\n\n"
    text += f"Заявка одобрена @{admin_username}\n\n"
    text += f"👤 Пользователь: {user.get('first_name', '')} {user.get('last_name', '')}".strip() + "\n"
    
    if user.get('username'):
        text += f"📱 @{user['username']}\n"
    
    text += f"🆔 #user{user['tg_id']}\n\n"
    text += f"📋 Анкета:\n"
    text += f"Имя: {user.get('q_name', '—')}\n"
    text += f"Возраст: {user.get('q_age', '—')}\n"
    text += f"Город: {user.get('q_city', '—')}\n"
    text += f"Терапия: {user.get('q_therapy', '—')}\n\n"
    
    if user.get('birth_date'):
        text += f"📅 Дата рождения: {user['birth_date']}\n\n"
    
    if app_date:
        text += f"{app_date}\n\n"
    
    return text


def format_rejection_text(user: Dict[str, Any], app: Dict[str, Any], admin_username: str, reason: str) -> str:
    """Форматирование текста отклоненной заявки согласно ТЗ п.3.4.2"""
    is_returning = user.get('last_exit_at') is not None
    status_tag = "#Возвращение" if is_returning else "#Новый"
    
    # Форматируем дату заявки
    app_date = ""
    if app.get('created_at'):
        created = datetime.fromisoformat(app['created_at'])
        app_date = f"📅 {created.strftime('%d.%m.%Y %H:%M')}\n"
    
    text = f"#Отказ\n"
    text += f"{status_tag}\n\n"
    text += f"Заявка отклонена @{admin_username}\n\n"
    text += f"👤 Пользователь: {user.get('first_name', '')} {user.get('last_name', '')}".strip() + "\n"
    
    if user.get('username'):
        text += f"📱 @{user['username']}\n"
    
    text += f"🆔 #user{user['tg_id']}\n\n"
    text += f"📋 Анкета:\n"
    text += f"Имя: {user.get('q_name', '—')}\n"
    text += f"Возраст: {user.get('q_age', '—')}\n"
    text += f"Город: {user.get('q_city', '—')}\n"
    text += f"Терапия: {user.get('q_therapy', '—')}\n\n"
    
    if user.get('birth_date'):
        text += f"📅 Дата рождения: {user['birth_date']}\n\n"
    
    if app_date:
        text += app_date
    
    text += f"Причина отклонения: {reason}\n\n"
    
    return text


def format_date(date_str: str, format: str = "%d.%m.%Y %H:%M") -> str:
    """Форматирование даты из ISO формата в читаемый вид"""
    try:
        if not date_str:
            return "—"
        dt = datetime.fromisoformat(date_str)
        return dt.strftime(format)
    except (ValueError, TypeError):
        return date_str or "—"


def format_user_mention(user_id: int, name: Optional[str] = None) -> str:
    """Форматирование упоминания пользователя"""
    if name:
        return f"<a href='tg://user?id={user_id}'>{name}</a>"
    return f"<a href='tg://user?id={user_id}'>пользователь</a>"


def escape_markdown(text: str) -> str:
    """Экранирование специальных символов Markdown"""
    if not text:
        return ""
    
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


def format_rejection_reason(reason: str) -> str:
    """Форматирование причины отказа"""
    if not reason:
        return "Причина не указана"
    return f"Причина отказа: {reason}"


def format_approval_message(user_name: str, invite_link: str) -> str:
    """Форматирование сообщения об одобрении для пользователя"""
    return (
        f"✨ {user_name}, ты на пороге входа в чат **Pulse 4ever**!\n\n"
        f"🔗 Твоя личная одноразовая ссылка:\n"
        f"{invite_link}\n\n"
        f"👉 Перейди по ссылке, чтобы вступить в чат.\n"
        f"Ссылка действует только один раз!"
    )


def format_reminder_message(user_name: str) -> str:
    """Форматирование напоминания о незаконченной анкете"""
    return f"{user_name}, ты не закончил заполнение анкеты, возможно, тебя отвлекли."


def format_welcome_message(name: str) -> str:
    """Форматирование приветственного сообщения"""
    return (
        f"Приветствуем, {name}!\n"
        f"Ты на пороге входа в чат PULSE 4ever 18+\n"
        f"ЗДЕСЬ ТЫ:\n"
        f"🔥Найдёшь друзей МСМ, которые реально поймут\n"
        f"🔥Закрутишь роман или просто приятное общение\n"
        f"🔥Будешь в курсе всего самого интересного\n"
        f"🔥Найдешь интересную информацию, касающуюся темы ВИЧ.\n\n"
        f"Чат не является сообществом ЛГБТ*, не призывает и не пропагандирует никакие нетрадиционные ценности и соблюдает законодательство РФ.\n"
        f"Если ты не являешься мужчиной практикующим секс с мужчиной и ты не достиг 18-летия, незамедлительно прекрати работу с ботом!\n"
        f"*ЛГБТ - запрещено на территории РФ."
    )


def format_rules() -> str:
    """Форматирование правил чата"""
    return (
        "ПРАВИЛА ЧАТА \"PULSE ❣️\"\n\n"
        "При заполнении анкеты, вы подтверждаете:\n"
        "✔️ Положительный статус;\n"
        "✔️ Совершенолетие (18+);\n"
        "✔️ Относитесь к МСМ-группе.\n\n"
        "Если это не про вас — немедленно покиньте чат.\n\n"
        "______________\n\n"
        "❌ Строгие запреты:\n\n"
        "1. ВИЧ- — если знаете о нарушении, сообщите админам.\n"
        "2. Оскорбления, конфликты — никаких разборок и хамства.\n"
        "3. Запрещённые темы: расизм, экстремизм, наркотики,.. насилие, религия, политика.\n"
        "4. ЛГБТ*-атрибутика — даже намёки (флаги, символы и прочее).\n"
        "5. 18+ контент — порно, эротика (включая GIF/анимации).\n"
        "6. Спам, флуд, агрессия, попрошайничество.\n"
        "7. Реклама (в том числе затрагивание тем других чатов, ресурсов) и ссылки — только с разрешения админов.\n"
        "8. Личная информация о третьих лицах без их согласия, в том числе личная переписка и фотографии участников чата!\n"
        "9. Несовершеннолетние — возраст проверяется (при подозрениях или жалобах!)\n"
        "10. Caps Lock — злоупотребление = мут.\n"
        "______________\n\n"
        "Незнание правил не освобождает от ответственности и ведут к бану.\n"
        "*ЛГБТ - запрещено на территории РФ."
    )


def format_invite_friends(name: str) -> str:
    """Форматирование сообщения о приглашении друзей"""
    return (
        f"{name},\n"
        f"Приглашай своих знакомых и друзей в чат Pulse💗💗💗. "
        f"Отправь нашего бота @Pulse_4ever_bot своему \"статусному\" другу!"
    )


def format_blacklist_message(first_name: str, group_name: str, reason: str, owner_mention: str) -> str:
    """Форматирование сообщения о блокировке"""
    return (
        f"{first_name}, мы сожалеем, но ты заблокирован администрацией чата "
        f"{group_name} из-за {reason}. Если ты считаешь, что в ЧС ты попал по ошибке, "
        f"свяжись с администратором {owner_mention}."
    )


def format_journal_profile_update(user_data: dict, changes: list) -> str:
    """Форматирование сообщения об изменении профиля для журнала"""
    text = (
        f"{Hashtags.PROFILE}\n"
        f"<b>Изменение профиля</b>\n"
        f"👤 Пользователь: {user_data.get('first_name', '')} {user_data.get('last_name', '')}\n"
        f"🆔 ID: <code>{user_data.get('tg_id')}</code>\n\n"
    )
    text += "\n".join(changes)
    return text


def format_journal_join(user_data: dict, chat_name: str) -> str:
    """Форматирование сообщения о входе в чат для журнала"""
    date_str = format_date(datetime.now().isoformat())
    
    text = (
        f"{Hashtags.ENTRY}\n"
        f"<b>Вход в чат</b>\n"
        f"👤 Пользователь: {user_data.get('first_name', '')} {user_data.get('last_name', '')}\n"
        f"🆔 ID: <code>{user_data.get('tg_id')}</code>\n"
        f"📱 @{user_data.get('username', 'нет')}\n"
        f"📅 {date_str}\n"
        f"💬 Чат: {chat_name}"
    )
    return text


def format_journal_exit(user_data: dict, chat_name: str, kicked_by: Optional[int] = None) -> str:
    """Форматирование сообщения о выходе из чата для журнала"""
    hashtag = Hashtags.KICK if kicked_by else Hashtags.EXIT
    action = "Исключен" if kicked_by else "Вышел"
    
    date_str = format_date(datetime.now().isoformat())
    
    text = (
        f"{hashtag}\n"
        f"<b>{action} из чата</b>\n"
        f"👤 Пользователь: {user_data.get('first_name', '')} {user_data.get('last_name', '')}\n"
        f"🆔 ID: <code>{user_data.get('tg_id')}</code>\n"
        f"📱 @{user_data.get('username', 'нет')}\n"
        f"📅 {date_str}\n"
        f"💬 Чат: {chat_name}"
    )
    
    if kicked_by:
        text += f"\n👮 Администратор: {kicked_by}"
    
    return text