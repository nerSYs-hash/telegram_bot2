import sys
import os
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- НАСТРОЙКИ ---
BOT_FILE    = "bot.py"               # PTB-бот (экономика, пульты)
REG_BOT_DIR = "registration_system"  # папка aiogram-бота

WATCH_EXTENSIONS = {".py", ".env"}
IGNORE_DIRS      = {"__pycache__", ".venv", "venv", ".git", "logs"}
# -----------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_python(base: str) -> str:
    """
    Ищет python.exe в порядке приоритета:
      1. .venv/Scripts/python.exe  — если существует И запускается
      2. sys.executable             — тот Python, которым запущен run_auto.py
    """
    candidates = [
        os.path.join(base, '.venv', 'Scripts', 'python.exe'),
        os.path.join(base, 'venv',  'Scripts', 'python.exe'),
    ]
    for p in candidates:
        if not os.path.exists(p):
            continue
        # Проверяем, что файл реально запускается (не AppX-заглушка)
        try:
            result = subprocess.run(
                [p, '--version'],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return p
        except Exception:
            pass
    return sys.executable


_ptb_python = _find_python(BASE_DIR)
_reg_python  = _find_python(os.path.join(BASE_DIR, REG_BOT_DIR))

print(f"🐍 PTB-бот    → {_ptb_python}")
print(f"🐍 Aiogram-бот → {_reg_python}")


def _ensure_deps(python: str, req_file: str):
    """Устанавливает зависимости через python бота, с fallback на sys.executable."""
    if not os.path.exists(req_file):
        return
    for py in [python, sys.executable]:
        try:
            result = subprocess.run(
                [py, '-m', 'pip', 'install', '-q', '-r', req_file],
                timeout=120, capture_output=True, text=True
            )
            if result.returncode == 0:
                return
        except Exception:
            pass
    print(f"⚠️  Не удалось установить зависимости из {req_file}")


class BotProcess:
    def __init__(self, name: str, python: str, script: str, cwd: str):
        self.name    = name
        self.python  = python
        self.script  = script
        self.cwd     = cwd
        self.process = None

    def start(self):
        if self.process and self.process.poll() is None:
            print(f"🛑 [{self.name}] Останавливаю для перезапуска...")
            self.process.kill()
            self.process.wait()
        print(f"🚀 [{self.name}] Запускаю...")
        self.process = subprocess.Popen(
            [self.python, self.script],
            cwd=self.cwd
        )

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.process.wait()


ptb_bot = BotProcess(
    name="PTB-бот",
    python=_ptb_python,
    script=BOT_FILE,
    cwd=BASE_DIR,
)

reg_bot = BotProcess(
    name="Aiogram-бот",
    python=_reg_python,
    script="main.py",
    cwd=os.path.join(BASE_DIR, REG_BOT_DIR),
)


def _belongs_to_reg(path: str) -> bool:
    norm = os.path.normpath(path)
    reg  = os.path.normpath(os.path.join(BASE_DIR, REG_BOT_DIR))
    return norm.startswith(reg)


class Restarter(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if any(ignored in path for ignored in IGNORE_DIRS):
            return
        if not any(path.endswith(ext) for ext in WATCH_EXTENSIONS):
            return
        print(f"🔄 Изменение: {path}")
        if _belongs_to_reg(path):
            print(f"   → Aiogram-бот перезапускается")
            reg_bot.start()
        else:
            print(f"   → PTB-бот перезапускается")
            ptb_bot.start()


if __name__ == "__main__":
    # Устанавливаем зависимости при необходимости
    _ensure_deps(_ptb_python, os.path.join(BASE_DIR, 'requirements.txt'))
    _ensure_deps(_reg_python,  os.path.join(BASE_DIR, REG_BOT_DIR, 'requirements.txt'))

    ptb_bot.start()
    reg_bot.start()

    handler  = Restarter()
    observer = Observer()
    observer.schedule(handler, path=BASE_DIR, recursive=True)
    observer.start()

    print(f"\n👀 Наблюдатель запущен.")
    print(f"   PTB-файлы              → перезапускается PTB-бот")
    print(f"   registration_system/   → перезапускается Aiogram-бот\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹ Останавливаю оба бота...")
        ptb_bot.stop()
        reg_bot.stop()
        observer.stop()
    observer.join()
