import os

def search_dir(d):
    for root, dirs, files in os.walk(d):
        if 'venv' in root or '.git' in root:
            continue
        for f in files:
            if f.endswith('.py'):
                try:
                    with open(os.path.join(root, f), 'r', encoding='utf-8') as file:
                        lines = file.readlines()
                        for i, line in enumerate(lines):
                            if 'register_topic' in line or 'thread_name' in line:
                                print(f"{f}:{i+1}: {line.strip()}")
                except Exception:
                    pass

search_dir(r'c:\bot_2\telegram_bot2')
