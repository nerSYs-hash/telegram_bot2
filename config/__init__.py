import os
from dotenv import load_dotenv
load_dotenv()

from config.emojis import *

# Константы из .env (для совместимости с модулями бота Вити)
OWNER_ID = int(os.getenv('MAIN_ADMIN_ID', 0))
CHAT_ID = int(os.getenv('TARGET_CHAT_ID', 0))
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID', 3794322036))
DOSSIER_THREAD_ID = int(os.getenv('DOSSIER_THREAD_ID', 176))
APPLICATIONS_THREAD_ID = int(os.getenv('APPLICATIONS_THREAD_ID', 1))
