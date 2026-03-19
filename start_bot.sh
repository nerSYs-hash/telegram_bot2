#!/bin/bash

echo "========================================"
echo "  Telegram Bot - Starting..."
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

echo "Python found: $(python3 --version)"
echo ""

# Check if database exists, if not - initialize
if [ ! -f "database/bot_database.db" ]; then
    echo "Initializing database..."
    python3 database/db_manager.py
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to initialize database"
        exit 1
    fi
    echo "Database initialized!"
    echo ""
fi

# Check if dependencies are installed
echo "Checking dependencies..."
if ! python3 -c "import telegram" &> /dev/null; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi
    echo "Dependencies installed!"
    echo ""
fi

echo "Starting bot..."
echo "Press Ctrl+C to stop"
echo ""

# Start the bot
python3 bot.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Bot crashed or stopped with error"
    echo "Check logs/bot.log for details"
    exit 1
fi

echo ""
echo "Bot stopped."
