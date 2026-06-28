@echo off
chcp 65001 >nul
title Exam Answer Tool - Server Mode
cd /d "%~dp0"

echo.
echo === Exam Answer Tool - Server Mode ===
echo.

:: Check Python
python --version 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Run start.bat first.
    pause
    exit /b 1
)

echo [Starting] HTTP server on random port ...
echo [Open] Browser will launch automatically
echo [Close] Press Ctrl+C in this window to stop
echo [Note] Close this window to stop the server
echo.

:: --server flag tells main.py to skip pywebview and auto-open browser
python main.py --server

echo.
echo Server stopped.
pause
