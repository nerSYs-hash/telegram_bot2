"""Удаление Python-исходников малого бота (registration_system/)"""
import os
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(BASE, 'registration_system')

# Файлы в корне registration_system/ — удаляем
root_files = [
    'main.py', 'run.py', 'test.py',
    'config.py', 'constants.py', 'database.py',
    '__init__.py', 'bot.log',
]

# Папки — удаляем целиком (Python-код)
dirs_to_delete = ['handlers', 'middlewares', 'utils', 'mnt', '__pycache__']

removed = []

for f in root_files:
    path = os.path.join(REG, f)
    if os.path.exists(path):
        os.remove(path)
        removed.append(f)
        print(f'  удалён файл: {f}')

for d in dirs_to_delete:
    path = os.path.join(REG, d)
    if os.path.exists(path):
        shutil.rmtree(path)
        removed.append(d + '/')
        print(f'  удалена папка: {d}/')

print(f'\nИтого удалено: {len(removed)} объектов')
print('Оставлено: TZ_COMPLIANCE.md, USER_GUIDE.md, pulse_bot.db (бекап), requirements.txt, .venv/, venv/, веб-проект')
