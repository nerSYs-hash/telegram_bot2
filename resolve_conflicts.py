import re

def resolve_conflicts(path, prefer='head'):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = re.compile(
        r'<{7,8}[^\n]*\n(.*?)\n?={7,8}\n?(.*?)\n?>{7,8}[^\n]*\n?',
        re.DOTALL
    )

    def resolver(m):
        head_part = m.group(1)
        return head_part if prefer == 'head' else m.group(2)

    resolved = pattern.sub(resolver, content)
    count = len(pattern.findall(content))

    with open(path, 'w', encoding='utf-8') as f:
        f.write(resolved)
    return count

files = [
    'handlers/callback/__init__.py',
    'handlers/callback/owner_callbacks.py',
    'handlers/callback/callback_router.py',
    'handlers/Stats/stats_controller.py',
]

import os
os.chdir(r'C:\bot_2\telegram_bot2')

for f in files:
    try:
        n = resolve_conflicts(f)
        print(f'OK {n} conflicts: {f}')
    except Exception as e:
        print(f'ERROR {f}: {e}')
