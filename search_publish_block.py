import os

def search_dir(d):
    for root, dirs, files in os.walk(d):
        if 'node_modules' in root or '.git' in root:
            continue
        for f in files:
            if f.endswith('.jsx') or f.endswith('.js'):
                path = os.path.join(root, f)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                        if 'PublishBlock' in file.read():
                            print(f'Found in: {path}')
                except Exception as e:
                    print(f"Error reading {path}: {e}")

search_dir(r'c:\bot_2\telegram_bot2\Admin_SITE')
