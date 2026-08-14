@echo off
title FEG FPL Telegram Bot Core
echo ===================================================
echo           FEG FPL BOT CORE INITIALIZING           
echo ===================================================
cd /d "%~dp0"
python run_bot.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Bot stopped with error code %ERRORLEVEL%.
)
pause
