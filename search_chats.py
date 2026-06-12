import os
for root, dirs, files in os.walk(r'c:\bot_2\telegram_bot2\api'):
    for f in files:
        if f.endswith('.py'):
            with open(os.path.join(root, f), 'r', encoding='utf-8', errors='ignore') as file:
                lines = file.readlines()
                for i, line in enumerate(lines):
                    if 'api/chats' in line:
                        print(f"Found in {f}:{i+1}: {line.strip()}")
