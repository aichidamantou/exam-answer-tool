@echo off
chcp 65001 >nul
title 考试答题工具
echo.
echo === 考试答题工具 - Windows 启动 ===
echo.
cd /d "%~dp0"
REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python
    echo 请安装 Python 3.9+，并确保 python 命令可用
    pause
    exit /b 1
)
REM 检查依赖
python -c "import webview" >nul 2>&1
if %errorlevel% neq 0 (
    echo [安装依赖] pywebview...
    pip install pywebview
)
python main.py
pause
