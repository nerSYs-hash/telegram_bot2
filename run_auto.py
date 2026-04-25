import sys
import os
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- НАСТРОЙКИ ---
BOT_FILE = "bot.py"  # PTB-бот (основной, единственный)

WATCH_EXTENSIONS = {".py", ".env"}
IGNORE_DIRS      = {"__pycache__", ".venv", "venv", ".git", "logs"}
# -----------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _kill_orphan_bots(script_name: str):
    """Убивает зависшие процессы бота перед запуском."""
    current_pid = os.getpid()
    killed = 0
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                cmdline = proc.info.get('cmdline') or []
                if any(script_name in arg for arg in cmdline):
                    proc.kill()
                    killed += 1
                    print(f"💀 Убит зависший процесс бота PID={proc.info['pid']}")
            except Exception:
                pass
    except ImportError:
        # Fallback: wmic (Windows)
        try:
            result = subprocess.run(
                ['wmic', 'process', 'where',
                 f'commandline like "%{script_name}%"',
                 'get', 'processid', '/format:list'],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                if line.startswith('ProcessId='):
                    pid_str = line.split('=')[1].strip()
                    if pid_str and pid_str.isdigit() and int(pid_str) != current_pid:
                        subprocess.run(['taskkill', '/F', '/PID', pid_str],
                                       capture_output=True, timeout=5)
                        killed += 1
                        print(f"💀 Убит зависший процесс бота PID={pid_str}")
        except Exception as e:
            print(f"⚠️  Не удалось проверить процессы: {e}")
    if killed:
        time.sleep(0.5)  # Даём ОС время освободить порты/соединения


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
        try:
            result = subprocess.run([p, '--version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                return p
        except Exception:
            pass
    return sys.executable


_ptb_python = _find_python(BASE_DIR)

print(f"🐍 PTB-бот → {_ptb_python}")


def _ensure_deps(python: str, req_file: str):
    """Устанавливает зависимости при старте."""
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


class Restarter(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if any(ignored in path for ignored in IGNORE_DIRS):
            return
        if not any(path.endswith(ext) for ext in WATCH_EXTENSIONS):
            return
        print(f"🔄 Изменение: {path} → PTB-бот перезапускается")
        ptb_bot.start()


if __name__ == "__main__":
    _ensure_deps(_ptb_python, os.path.join(BASE_DIR, 'requirements.txt'))

    print("🔍 Проверяю зависшие процессы бота...")
    _kill_orphan_bots(BOT_FILE)

    ptb_bot.start()

    handler  = Restarter()
    observer = Observer()
    observer.schedule(handler, path=BASE_DIR, recursive=True)
    observer.start()

    print(f"\n👀 Наблюдатель запущен. Любое изменение .py/.env → перезапуск PTB-бота\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹ Останавливаю бот...")
        ptb_bot.stop()
        observer.stop()
    observer.join()
