@echo off
cd /d "c:\bot_2\telegram_bot2\Admin_SITE"
call npm run build > build_log.txt 2>&1
echo Done building
