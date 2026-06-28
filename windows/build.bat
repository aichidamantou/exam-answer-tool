@echo off
chcp 65001 >nul
title 考试答题工具 - Windows 打包

echo.
echo === 考试答题工具 - Windows 打包 ===
echo.

cd /d "%~dp0"

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 请先安装 Python 3.9+
    pause
    exit /b 1
)

REM 安装 PyInstaller
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [安装] PyInstaller...
    pip install pyinstaller
)

REM 打包
echo [打包] 正在打包为 Windows 单文件程序...
python -m PyInstaller --onefile --windowed --name 考试答题工具 --add-data "modules;modules" --distpath . main.py

echo.
echo 完成！可执行文件在当前目录: 考试答题工具.exe
pause
