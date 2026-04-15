#!/bin/bash
# =============================================================
#  Одноразовая настройка сервера для Admin_SITE + api.py
#  Запускать на сервере: bash /root/PulsBot/deploy/server_setup.sh
# =============================================================
set -e

echo "=== [1/6] Установка Node.js 20 ==="
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
node --version && npm --version

echo "=== [2/6] Установка зависимостей FastAPI в venv бота ==="
/root/PulsBot/economybot/venv/bin/pip install fastapi uvicorn -q
echo "fastapi и uvicorn установлены"

echo "=== [3/6] Отключение старого TG-сайта (nginx) ==="
# Убираем старый конфиг из sites-enabled
rm -f /etc/nginx/sites-enabled/default
rm -f /etc/nginx/sites-enabled/pulse-site
rm -f /etc/nginx/sites-enabled/puls-chat
echo "Старые конфиги убраны"

echo "=== [4/6] Установка нового nginx конфига (Admin_SITE) ==="
cp /root/PulsBot/deploy/nginx_puls-chat.conf /etc/nginx/sites-available/puls-chat.ru
ln -sf /etc/nginx/sites-available/puls-chat.ru /etc/nginx/sites-enabled/puls-chat.ru
nginx -t && echo "nginx конфиг OK"

echo "=== [5/6] Первая сборка React ==="
cd /root/PulsBot/Admin_SITE
npm install --silent
npm run build
echo "Сборка OK → файлы в /root/PulsBot/Admin_SITE/dist/"

echo "=== [6/6] Установка и запуск systemd сервиса pulsapi ==="
cp /root/PulsBot/deploy/pulsapi.service /etc/systemd/system/pulsapi.service
systemctl daemon-reload
systemctl enable pulsapi
systemctl restart pulsapi
systemctl reload nginx

echo ""
echo "✅ Готово!"
echo "   Сайт: http://puls-chat.ru"
echo "   API:  http://puls-chat.ru/api/"
echo "   Статус API: systemctl status pulsapi"
