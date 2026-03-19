import os
import emoji
import re

def generate_emoji_config():
    print("🔍 Собираю эмодзи со всего проекта...")
    total_emojis = set()
    
    # 1. Ищем все уникальные эмодзи
    for root, dirs, files in os.walk('.'):
        if any(ignore in root for ignore in['venv', 'env', '.git', '__pycache__']):
            continue
        for file in files:
            if file.endswith('.py') and file != os.path.basename(__file__):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            for char in line:
                                if emoji.is_emoji(char) and not char.isascii():
                                    total_emojis.add(char)
                except Exception:
                    pass

    # 2. Создаем папку config, если её нет
    os.makedirs('config', exist_ok=True)
    config_path = os.path.join('config', 'emojis.py')

    # 3. Записываем их в красивый Python-файл
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write('"""\n')
        f.write("ФАЙЛ КОНФИГУРАЦИИ ЭМОДЗИ\n")
        f.write("Здесь хранятся все иконки бота.\n")
        f.write("Для замены на анимированные используйте формат:\n")
        f.write("ICON_NAME = '<tg-emoji emoji-id=\"123456789\">💎</tg-emoji>'\n")
        f.write('"""\n\n')

        # Сортируем для красоты
        for em in sorted(total_emojis):
            # Магия: превращаем смайлик в текст (например, 💰 -> :moneybag: -> MONEYBAG)
            name = emoji.demojize(em).strip(':').upper().replace('-', '_')
            name = re.sub(r'[^A-Z0-9_]', '', name) # Убираем мусор
            
            if not name:
                name = f"EMOJI_{ord(em)}"
                
            var_name = f"ICON_{name}"
            
            # Записываем в файл в виде: ICON_MONEYBAG = "💰"
            f.write(f'{var_name} = "{em}"\n')

    print(f"✅ Готово! Найдено {len(total_emojis)} уникальных эмодзи.")
    print(f"📁 Файл создан по пути: {config_path}")

if __name__ == "__main__":
    generate_emoji_config()