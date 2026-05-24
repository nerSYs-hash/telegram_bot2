"""Генератор записей релиз-нотов для CHANGELOG.md (вспомогательный инструмент)."""

import os
import platform
import subprocess
from datetime import datetime

def get_modified_files_today():
    today = datetime.now().date()
    modified = []
    IGNORE_DIRS =['venv', 'env', '.git', '__pycache__', 'logs', 'database', '.idea', '.vscode']
    
    for root, dirs, files in os.walk('.'):
        dirs[:] =[d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if file.endswith('.py') and file != os.path.basename(__file__):
                filepath = os.path.join(root, file)
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).date()
                if mtime == today:
                    modified.append(os.path.relpath(filepath, '.').replace('\\', '/'))
    return modified

def save_to_changelog(version, post_text):
    """Сохраняет обновление в файл CHANGELOG.md (новое сверху)"""
    changelog_file = "CHANGELOG.md"
    date_str = datetime.now().strftime('%d.%m.%Y %H:%M')
    
    # Формируем новую запись
    new_entry = f"## 📦 Версия {version} ({date_str})\n\n{post_text}\n\n---\n\n"
    
    # Читаем старую историю (если файл уже есть)
    old_content = ""
    if os.path.exists(changelog_file):
        with open(changelog_file, "r", encoding="utf-8") as f:
            old_content = f.read()
    else:
        old_content = "# 📜 Журнал обновлений бота (Changelog)\n\nЗдесь хранится история всех версий и изменений.\n\n---\n\n"
        
    # Записываем всё обратно (Новое обновление будет в самом верху!)
    with open(changelog_file, "w", encoding="utf-8") as f:
        f.write(new_entry + old_content)
        
    print(f"📁 История успешно сохранена в файл {changelog_file}!")

def generate_patchnote():
    draft_file = "patchnote_draft.txt"
    files = get_modified_files_today()
    files_str = "\n".join([f"  - {f}" for f in files]) if files else "  (файлы не менялись)"
    
    template = f"""ШПАРГАЛКА (изменено сегодня):
{files_str}
=================================================
ИНСТРУКЦИЯ: 
1. Напишите ваши обновления после дефисов. 
2. Вы можете добавлять новые дефисы с новой строки.
3. Пустые разделы скрипт удалит сам!
4. Сохраните файл (Ctrl+S) и вернитесь в консоль.
=================================================

📦 ВЕРСИЯ: {datetime.now().strftime('%d.%m.%Y')}

🚀 НОВЫЙ ФУНКЦИОНАЛ:
- 

🎨 ВИЗУАЛ И УДОБСТВО:
- 

🛠 ИСПРАВЛЕНИЯ:
- 

⚙️ ПОД КАПОТОМ:
- 
"""
    with open(draft_file, "w", encoding="utf-8") as f:
        f.write(template)
        
    print("📝 Открываю Блокнот для редактирования...")
    
    if platform.system() == 'Windows':
        os.startfile(draft_file)
    elif platform.system() == 'Darwin':
        subprocess.call(('open', draft_file))
    else:
        subprocess.call(('xdg-open', draft_file))
        
    input("\n👉 Впишите изменения в открывшийся Блокнот, СОХРАНИТЕ его (Ctrl+S), закройте окно и НАЖМИТЕ ENTER здесь...")

    with open(draft_file, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split('\n')
    
    version = ""
    categories = {}
    current_category = None
    
    for line in lines:
        line_stripped = line.strip()
        
        if line_stripped.startswith("📦 ВЕРСИЯ:"):
            version = line_stripped.replace("📦 ВЕРСИЯ:", "").strip()
            continue
            
        if line_stripped and not line_stripped.startswith("-") and not line_stripped.startswith("=") and not line_stripped.startswith("ШПАРГАЛКА") and not line_stripped.startswith("ИНСТРУКЦИЯ") and not line.startswith("  -"):
            if any(emoji in line_stripped for emoji in ["🚀", "🎨", "🛠", "⚙️"]):
                current_category = line_stripped
                categories[current_category] =[]
            continue
            
        if line_stripped.startswith("-") and current_category:
            item = line_stripped[1:].strip()
            if item:
                categories[current_category].append(item)

    post_text = ""
    has_changes = False
    
    for category, items in categories.items():
        if items:
            has_changes = True
            post_text += f"**{category}**\n"
            for item in items:
                post_text += f"▪️ {item}\n"
            post_text += "\n"

    if has_changes:
        # 1. Выводим текст для Телеграма
        tg_post = f"🆕 **ОБНОВЛЕНИЕ БОТА | Версия: {version}**\n\n{post_text}__© Pulse Chat Community 2026 🩵__"
        print("\n\n" + "="*50)
        print(" ✨ СКОПИРУЙТЕ ТЕКСТ НИЖЕ И ВСТАВЬТЕ В TELEGRAM ✨ ")
        print("="*50 + "\n")
        print(tg_post)
        print("\n" + "="*50)
        
        # 2. Сохраняем в историю (журнал)
        save_to_changelog(version, post_text)
    else:
        print("🤷‍♂️ Вы оставили все поля пустыми. Пост не сгенерирован.")
        
    try:
        os.remove(draft_file)
    except:
        pass

if __name__ == "__main__":
    generate_patchnote()