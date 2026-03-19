# Маппинг веток форума (на основе ваших скриншотов)
FORUM_TOPICS_MAP = {
    # ID ветки: (эмодзи, название)
    None: ("💬", "Основной чат"),
    26: ("🔸", "НьюзON"),
    3: ("➕", "ПлюсON"),
    35843: ("🎭", "Конкурс \"РомантИк\""),
    8: ("❤️", "BBS"),
    2: ("🎁", "МемасON"),
    15: ("🔥", "ЗадротыON"),
    11: ("🐾", "ПИТОМЦЫ"),
    6: ("🎵", "МузON"),
    24: ("🍰", "КухаркаON"),
    21: ("✅", "CHECK-IN"),
    24359: ("🎬", "КиноON/БукON"),
    102940: ("💓", "PulseON МСК: встречи"),
    23: ("📊", "СтатON"),
    108582: ("💓", "PulseON СПБ: Встречи"),
    220170: ("🤖", "Предложения по чат-боту Pulse"),
    13: ("📋", "ПРАВИЛА"),
}

def get_forum_topic_display_name(thread_id, thread_name=None):
    """Получает красивое отображаемое название ветки"""
    # Проверяем в маппинге
    if thread_id in FORUM_TOPICS_MAP:
        return FORUM_TOPICS_MAP[thread_id]
    
    # Если есть название из БД и это не "Ветка #XXX"
    if thread_name and not thread_name.startswith('Ветка #'):
        emoji = get_emoji_by_keywords(thread_name)
        return (emoji, thread_name)
    
    # Fallback
    if thread_id is None:
        return ("💬", "Основной чат")
    else:
        return ("🧵", f"Ветка #{thread_id}")

def get_emoji_by_keywords(name):
    """Подбирает эмодзи на основе ключевых слов"""
    name_lower = name.lower()
    
    keywords_map = {
        "📰": ["новост", "ньюз", "news"],
        "➕": ["плюс", "plus"],
        "#": ["чат", "chat"],
        "🎭": ["конкурс", "contest"],
        "🎁": ["мем", "meme"],
        "❤️": ["bbs"],
        "🔥": ["задрот", "геймер", "game"],
        "🐾": ["питом", "pet"],
        "🎵": ["музон", "муз", "music"],
        "🍰": ["кухарка", "еда", "food"],
        "✅": ["check"],
        "🎬": ["кино", "бук", "movie"],
        "💓": ["pulse", "встреч", "meet"],
        "📊": ["стат", "stat"],
        "📋": ["правил", "rule"],
        "🤖": ["предложен", "бот", "bot"],
    }
    
    for emoji, keywords in keywords_map.items():
        if any(word in name_lower for word in keywords):
            return emoji
    
    return "🧵"