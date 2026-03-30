#!/usr/bin/env bash
# Запускает Mini App API рядом с dev-ботом на сервере.
# Место: /root/dev/start_mini_app_api.sh
# Использование: bash start_mini_app_api.sh [--reload]
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/mini_app_api/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "[WARN] $ENV_FILE не найден. Скопируй mini_app_api/.env.example в mini_app_api/.env и заполни."
fi

RELOAD=""
if [ "$1" = "--reload" ]; then
  RELOAD="--reload"
fi

# Если есть venv — активируем его
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
  PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
  PYTHON="python3"
fi

echo "[INFO] Mini App API: запускаю на порту 8000, env=$SCRIPT_DIR"
"$PYTHON" -m uvicorn mini_app_api.app:app --host 0.0.0.0 --port 8000 $RELOAD
