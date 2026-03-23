from utils.helpers import format_number

def build_chat_stats_message(period_name, stats_type, data):
    """
    Собирает ту самую длинную строку статистики для чата.
    data: словарь с посчитанными сообщениями, пульсами и т.д.
    """
    msg = f"📊 СТАТИСТИКА\n{period_name}\n\n"
    msg += f"💬 Всего сообщений: {data['total_messages']}\n"
    msg += f"👥 Активных пользователей: {data['active_users']}\n"
    # ... и так далее ...
    return msg