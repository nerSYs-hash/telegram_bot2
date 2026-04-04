"""
Константы для бота Pulse 4ever
Содержит все статические тексты, статусы и callback data
"""


class UserStatus:
    """Статусы пользователя в системе"""
    NOT_IN_CHAT = "not_in_chat"
    IN_CHAT = "in_chat"
    BLOCKED = "blocked"
    BANNED = "banned"


class ApplicationStatus:
    """Статусы заявок"""
    NEW = "new"
    IN_WORK = "in_work"
    APPROVED = "approved"
    REJECTED = "rejected"


class UserRole:
    """Роли пользователей"""
    USER = "user"
    ADMIN = "admin"
    DEPUTY = "deputy"
    OWNER = "owner"


class RegistrationStates:
    """Состояния FSM для регистрации"""
    WAITING_AGE_CONFIRM = "waiting_age_confirm"
    WAITING_RULES_ACCEPT = "waiting_rules_accept"
    WAITING_APPLY = "waiting_apply"
    WAITING_NAME = "waiting_name"
    WAITING_AGE = "waiting_age"
    WAITING_BIRTH_DATE = "waiting_birth_date"
    WAITING_CITY = "waiting_city"
    WAITING_THERAPY = "waiting_therapy"
    WAITING_REF_CODE = "waiting_ref_code"


class CallbackData:
    """Callback data для инлайн кнопок"""
    AGE_CONFIRM = "age_confirm"
    RULES_ACCEPT = "rules_accept"
    SUBMIT_APP = "submit_app"
    SKIP_REF_CODE = "skip_ref_code"
    CONTINUE_QUESTIONNAIRE = "continue_questionnaire"


class Buttons:
    """Тексты для reply-кнопок"""
    NEW_APPLICATIONS = "📋 Новые заявки"
    ADMINS = "👤 Админы"
    BLACKLIST = "🚫 Черный список"
    CHECK_USER = "🔍 Проверка ника"
    TRIGGERS = "⚡ Триггеры"
    JOURNAL = "📢 Журнал"
    STATISTICS = "📊 Статистика"


class Hashtags:
    """Хештеги для журнала событий"""
    NEW_APPLICATION = "#Новая_заявка"
    PROFILE = "#Профиль"
    PHOTO = "#Фото"
    ACTIVITY = "#Активность"
    JOIN = "#Вход"
    EXIT = "#Выход"
    KICK = "#Исключен"
    REJECT = "#Отказ"
    APPROVED = "#Одобрено"
    BLOCKED = "#Блокировка"
    UNBLOCKED = "#Разблокировка"
    CONTACT_BUTTON = "💬 Написать в ЛС"


class TriggerConditions:
    """Условия срабатывания триггеров"""
    EXACT = "exact"              # Точное совпадение
    CONTAINS = "contains"         # Содержит
    STARTS_WITH = "starts_with"   # Начинается с
    ENDS_WITH = "ends_with"       # Заканчивается на
    WHOLE_WORD = "whole_word"     # Целое слово


class TriggerActions:
    """Действия триггеров"""
    SEND_CHAT_MESSAGE = "send_chat_message"
    SEND_PRIVATE_MESSAGE = "send_private_message"
    DELETE_MESSAGE = "delete_message"
    PIN_MESSAGE = "pin_message"
    MUTE = "mute"
    UNMUTE = "unmute"
    WARNING = "warning"
    ADD_EMOJI = "add_emoji"
    KICK = "kick"
    BAN = "ban"


class TriggerTarget:
    """Цели для действий триггеров"""
    INITIATOR = "initiator"           # На инициатора
    EVERYONE = "everyone"              # На всех в чате
    SPECIFIC_USER = "specific_user"    # На указанного пользователя
    RANDOM_USER = "random_user"        # На случайного пользователя
    ADMINS = "admins"                  # На администраторов
    NOBODY = "nobody"                  # Ни на кого (информационное)


class TriggerScope:
    """Где срабатывает триггер"""
    ALL_CHAT = "all_chat"              # Во всём чате
    SELECTED_TOPICS = "selected_topics" # В выбранных ветках


class TriggerInitiator:
    """Кто может активировать триггер"""
    ALL = "all"
    USERS_ONLY = "users_only"
    ADMINS_ONLY = "admins_only"
    OWNER_ONLY = "owner_only"
    ADMINS_AND_OWNER = "admins_and_owner"


class CumulativeReset:
    """Сброс счётчика нарушений"""
    AFTER_ACTION = "after_action"
    AFTER_PERIOD = "after_period"
    NEVER = "never"


class Messages:
    """Текстовые сообщения бота"""
    
    WELCOME = (
        "Приветствуем, {name}!\n"
        "Ты на пороге входа в чат PULSE 4ever 18+\n"
        "ЗДЕСЬ ТЫ:\n"
        "🔥Найдёшь друзей МСМ, которые реально поймут\n"
        "🔥Закрутишь роман или просто приятное общение\n"
        "🔥Будешь в курсе всего самого интересного\n"
        "🔥Найдешь интересную информацию, касающуюся темы ВИЧ.\n\n"
        "Чат не является сообществом ЛГБТ*, не призывает и не пропагандирует никакие нетрадиционные ценности и соблюдает законодательство РФ.\n"
        "Если ты не являешься мужчиной практикующим секс с мужчиной и ты не достиг 18-летия, незамедлительно прекрати работу с ботом!\n"
        "*ЛГБТ - запрещено на территории РФ."
    )
    
    RULES = (
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
    
    INVITE_FRIENDS = (
        "{name},\n"
        "Приглашай своих знакомых и друзей в чат Pulse💗💗💗. "
        "Отправь нашего бота @Pulse_4ever_bot своему \"статусному\" другу!"
    )
    
    Q_NAME = "А Как тебя зовут?"
    Q_AGE = "Б Сколько тебе лет?"
    Q_BIRTH_DATE = "Е Укажи точную дату своего рождения в формате дд.мм.гггг"
    Q_CITY = "В В каком городе ты проживаешь?"
    Q_THERAPY = "Г Какую терапию ты принимаешь (укажи точное наименование препаратов)?"
    Q_REF_CODE = "Д Реф. код (ник пользователя) - необязательно"
    
    REJECTED = (
        "{name}, к сожалению, анкета содержит недостоверные или неполные данные: {reason}\n"
        "Просьба подать заявку снова."
    )
    
    APPROVED = (
        "{name}, ты на пороге входа в чат Pulse 4ever, "
        "просто используй свою личную ссылку: {link}"
    )
    
    BLACKLISTED = (
        "{first_name}, мы сожалеем, но ты заблокирован администрацией чата "
        "{group_name} из-за {reason}. Если ты считаешь, что в ЧС ты попал по ошибке, "
        "свяжись с администратором {owner_mention}."
    )
    
    REMINDER = "{name}, ты не закончил заполнение анкеты, возможно, тебя отвлекли."
    
    ACTIVE_APPLICATION = (
        "{name}, ты уже подал заявку на вступление и она уже на рассмотрении. "
        "Немного терпения, наши администраторы обязательно обработают ее, а пока ты "
        "можешь отправить нашего бота @Pulse_4ever_Bot своим друзьям или знакомым со \"статусом\"."
    )