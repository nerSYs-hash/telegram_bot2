#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# recover_bot.sh — лечение бота после угона по утёкшему токену.
#
# Что делает:
#   1) deleteWebhook + drop_pending_updates  — выпинываем атакерский webhook,
#      Telegram перестаёт слать апдейты ему и наш polling начинает работать.
#   2) getMe                                  — проверяем, что новый токен живой.
#   3) getWebhookInfo                         — подтверждаем, что webhook пуст.
#   4) Показывает текущие имя/описание/команды бота, чтобы видно было,
#      что атакер поменял (Sherlock / setMyCommands и т.п.).
#   5) Если переданы переменные окружения BOT_NAME / BOT_DESCRIPTION /
#      BOT_SHORT_DESC — восстанавливает их через setMyName / setMyDescription /
#      setMyShortDescription.
#   6) Если задана переменная RESET_COMMANDS=1 — чистит команды (setMyCommands
#      с пустым списком), чтобы атакерские команды пропали.
#
# Не делает: не трогает .env и не рестартит systemd-юнит.
# Это сделай руками после того, как скрипт отработает успешно.
#
# Использование:
#   chmod +x recover_bot.sh
#
#   # минимум — снять webhook и показать состояние:
#   BOT_TOKEN='123456:AAA...' ./recover_bot.sh
#
#   # снять webhook + восстановить имя/описание + сбросить команды:
#   BOT_TOKEN='123456:AAA...' \
#   BOT_NAME='PulseOn' \
#   BOT_DESCRIPTION='Бот сообщества Pulse 4ever.' \
#   BOT_SHORT_DESC='Pulse 4ever' \
#   RESET_COMMANDS=1 \
#       ./recover_bot.sh
# ─────────────────────────────────────────────────────────────────────────────

set -u

TOKEN="${BOT_TOKEN:-${1:-}}"
if [ -z "$TOKEN" ]; then
  echo "❌ BOT_TOKEN не задан. Использование:"
  echo "   BOT_TOKEN='12345:AAA...' ./recover_bot.sh"
  exit 1
fi

API="https://api.telegram.org/bot${TOKEN}"

# ── Утилита: вызвать метод и красиво показать ответ ──────────────────────────
call() {
  local method="$1"; shift
  local title="$1";  shift
  echo "─── ${title} (${method}) ───"
  if command -v jq >/dev/null 2>&1; then
    curl -fsS "${API}/${method}" "$@" | jq .
  else
    curl -fsS "${API}/${method}" "$@"
    echo
  fi
  echo
}

# ── 1. Снимаем webhook ──────────────────────────────────────────────────────
echo "═══ ШАГ 1: deleteWebhook (drop_pending_updates=true)"
call "deleteWebhook?drop_pending_updates=true" "Удалить webhook и очистить очередь"

# ── 2. Проверяем токен ──────────────────────────────────────────────────────
echo "═══ ШАГ 2: getMe — токен живой?"
call "getMe" "Информация о боте"

# ── 3. Подтверждаем, что webhook пуст ───────────────────────────────────────
echo "═══ ШАГ 3: getWebhookInfo — должно быть url пустой"
call "getWebhookInfo" "Webhook info"

# ── 4. Что натворил атакер ──────────────────────────────────────────────────
echo "═══ ШАГ 4: текущие имя / описание / команды"
call "getMyName"             "Имя"
call "getMyDescription"      "Описание (длинное)"
call "getMyShortDescription" "Короткое описание"
call "getMyCommands"         "Команды"

# ── 5. Восстановление (опционально) ─────────────────────────────────────────
RESTORED=0
if [ -n "${BOT_NAME:-}" ]; then
  echo "═══ Восстанавливаем имя: ${BOT_NAME}"
  call "setMyName" "setMyName" --data-urlencode "name=${BOT_NAME}"
  RESTORED=1
fi
if [ -n "${BOT_DESCRIPTION:-}" ]; then
  echo "═══ Восстанавливаем описание"
  call "setMyDescription" "setMyDescription" --data-urlencode "description=${BOT_DESCRIPTION}"
  RESTORED=1
fi
if [ -n "${BOT_SHORT_DESC:-}" ]; then
  echo "═══ Восстанавливаем короткое описание"
  call "setMyShortDescription" "setMyShortDescription" --data-urlencode "short_description=${BOT_SHORT_DESC}"
  RESTORED=1
fi
if [ "${RESET_COMMANDS:-0}" = "1" ]; then
  echo "═══ Сбрасываем команды"
  if command -v jq >/dev/null 2>&1; then
    curl -fsS -X POST -H "Content-Type: application/json" \
         -d '{"commands":[]}' "${API}/setMyCommands" | jq .
  else
    curl -fsS -X POST -H "Content-Type: application/json" \
         -d '{"commands":[]}' "${API}/setMyCommands"
    echo
  fi
  echo
  RESTORED=1
fi

if [ "$RESTORED" = "0" ]; then
  echo "ℹ️  Имя/описание/команды НЕ восстанавливал (не передал BOT_NAME / BOT_DESCRIPTION / BOT_SHORT_DESC / RESET_COMMANDS)."
  echo "   Если атакер их менял — перезапусти скрипт с этими переменными."
fi

echo
echo "✅ Готово. Дальше:"
echo "   1) Обнови /root/dev/.env  → BOT_TOKEN на новый."
echo "   2) Перезапусти сервис      → systemctl restart <твой-юнит>"
echo "   3) Хвост логов             → journalctl -u <юнит> -f --since '1 min ago'"
echo "   4) git pull в проекте      → подтянуть hotfix V1.15.0e (убран хардкод-токен)."
