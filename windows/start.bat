@echo off
chcp 65001 >nul
title Exam Answer Tool
cd /d "%~dp0"

echo.
echo === Exam Answer Tool - Windows Launcher ===
echo.

:: Check system Python first
python --version 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found
    echo Download: https://www.python.org/downloads/
    echo Check "Add Python to PATH" during install
    pause
    exit /b 1
)

:: Check and install pywebview
python -c "import webview" 2>nul
if errorlevel 1 (
    echo [Install] pywebview ...
    pip install pywebview -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>nul
    if errorlevel 1 (
        pip install pywebview -q 2>nul
    )
)

python main.py
if errorlevel 1 (
    echo.
    echo Exit code: %errorlevel%
    echo Check exam_tool.log for details
    if exist exam_tool.log type exam_tool.log
)
pause
