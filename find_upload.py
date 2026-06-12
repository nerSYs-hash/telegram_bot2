import os

def search_dir(d):
    for root, dirs, files in os.walk(d):
        if 'venv' in root or '.git' in root or 'node_modules' in root or 'dist' in root:
            continue
        for f in files:
            if f.endswith('.py') and ('api' in f or 'routes' in f):
                try:
                    with open(os.path.join(root, f), 'r', encoding='utf-8') as file:
                        for i, line in enumerate(file):
                            if 'upload' in line.lower() or 'media' in line.lower() or 'file' in line.lower():
                                if '@app' in line or '@router' in line or 'post' in line:
                                    print(f"{f}:{i+1}: {line.strip()}")
                except Exception:
                    pass

search_dir(r'c:\bot_2\telegram_bot2')
search_dir(r'c:\bot_2\telegram_bot2\api')
