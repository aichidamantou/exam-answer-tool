@echo off
chcp 65001 >nul
title 考试答题工具 - Windows 打包
cd /d "%~dp0"

echo.
echo === 考试答题工具 - Windows 打包 ===
echo.

:: 优先使用便携版 Python（start.bat 下载的）
if exist "python\python.exe" (
    set PYTHON=python\python.exe
    echo [检测] 使用便携版 Python
) else (
    python --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON=python
        echo [检测] 使用系统 Python
    ) else (
        echo [错误] 未检测到 Python
        echo 请先运行 start.bat 自动下载，或安装 Python 3.9+
        pause
        exit /b 1
    )
)

:: 安装 PyInstaller
%PYTHON% -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [安装] PyInstaller (使用清华镜像)...
    %PYTHON% -m pip install pyinstaller -q -i https://pypi.tuna.tsinghua.edu.cn/simple
)

:: 打包
echo [打包] 正在打包为 Windows 单文件程序...
%PYTHON% -m PyInstaller --onefile --windowed --name 考试答题工具 --add-data "modules;modules" --distpath . main.py

echo.
echo 完成！可执行文件: 考试答题工具.exe
pause
