@echo off
chcp 65001 >nul
title 考试答题工具
cd /d "%~dp0"

echo.
echo === 考试答题工具 - Windows启动 ===
echo.

:: 检查便携版Python
if not exist "python\python.exe" (
    echo [下载] 便携版 Python 3.12...
    curl -L -o python.zip "https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip" 2>nul
    if not exist python.zip (
        echo [错误] 下载失败，请检查网络连接
        pause
        exit /b 1
    )
    mkdir python 2>nul
    tar -xf python.zip -C python\
    del python.zip
    :: 启用 pip
    python\python -m pip install --upgrade pip 2>nul
)

:: 安装依赖
if not exist "python\Lib\site-packages\webview" (
    echo [安装] pywebview...
    python\python -m pip install pywebview -q
    echo [安装] pyinstaller...
    python\python -m pip install pyinstaller -q
)

echo [启动] 运行答题工具...
python\python main.py

pause
