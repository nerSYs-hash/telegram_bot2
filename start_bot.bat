@echo off
echo ========================================
echo   Telegram Bot - Starting...
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher
    pause
    exit /b 1
)

echo Python found!
echo.

REM Check if database exists, if not - initialize
if not exist "database\bot_database.db" (
    echo Initializing database...
    python database\db_manager.py
    if errorlevel 1 (
        echo ERROR: Failed to initialize database
        pause
        exit /b 1
    )
    echo Database initialized!
    echo.
)

REM Install dependencies if needed
echo Checking dependencies...
pip show python-telegram-bot >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
    echo Dependencies installed!
    echo.
)

echo Starting bot...
echo Press Ctrl+C to stop
echo.

python bot.py

if errorlevel 1 (
    echo.
    echo ERROR: Bot crashed or stopped with error
    echo Check logs\bot.log for details
)

echo.
echo Bot stopped.
pause
