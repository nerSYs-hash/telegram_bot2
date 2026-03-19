import sys
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- НАСТРОЙКИ ---
BOT_FILE = "bot.py"  # Имя вашего главного файла
WATCH_EXTENSIONS = {".py", ".env"}  # За какими файлами следить
IGNORE_DIRS = {"__pycache__", "venv", ".git", "logs"} # Куда не смотреть
# -----------------

class Restarter(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.start_bot()

    def start_bot(self):
        if self.process:
            print("🛑 Останавливаю бота для обновления...")
            self.process.kill()
            self.process.wait()
        
        print("🚀 Запускаю бота...")
        # Запускаем bot.py как отдельный процесс
        self.process = subprocess.Popen([sys.executable, BOT_FILE])

    def on_modified(self, event):
        if event.is_directory:
            return
        
        filename = event.src_path
        if any(ignored in filename for ignored in IGNORE_DIRS):
            return
        
        # Если изменился .py файл или .env — перезапускаем
        if any(filename.endswith(ext) for ext in WATCH_EXTENSIONS):
            # Важно: БД (.db) мы игнорируем, иначе бот будет перезагружаться от каждого лайка!
            print(f"🔄 Обнаружено изменение в файле: {filename}")
            self.start_bot()

if __name__ == "__main__":
    handler = Restarter()
    observer = Observer()
    observer.schedule(handler, path=".", recursive=True)
    observer.start()
    
    print(f"👀 Наблюдатель запущен. Меняйте файлы, я перезагружу бота сам.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()