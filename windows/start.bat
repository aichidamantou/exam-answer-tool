@echo off
chcp 65001 >nul
title Exam Answer Tool
cd /d "%~dp0"

echo.
echo === Exam Answer Tool - Windows Launcher ===
echo.

:: Check system Python first
python --version 2>nul
if not errorlevel 1 goto RUN_WITH_PY

:: Fallback to embedded Python if exists
if exist "python\python.exe" (
    echo [Using embedded Python]
    set "PATH=%~dp0python;%~dp0python\Scripts;%PATH%"
    python --version 2>nul
    if not errorlevel 1 goto RUN_WITH_PY
)

:: Download full Python installer
echo [Download] Python 3.12 ...
curl -sL -o python-installer.exe "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
if not exist python-installer.exe (
    curl -sL -o python-installer.exe "https://mirrors.tuna.tsinghua.edu.cn/python/3.12.4/python-3.12.4-amd64.exe"
)
if not exist python-installer.exe (
    echo [ERROR] Download failed, install manually: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [Install] Python (quiet mode)...
python-installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del python-installer.exe
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;%PATH%"
python --version 2>nul
if errorlevel 1 (
    echo [ERROR] Python installation failed
    pause
    exit /b 1
)

:RUN_WITH_PY
echo [Check] pywebview ...
python -c "import webview" 2>nul
if errorlevel 1 (
    echo [Install] setuptools + pywebview ...
    pip install setuptools wheel -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>nul
    pip install pywebview -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>nul
    if errorlevel 1 pip install pywebview -q
)
echo.
python main.py
if errorlevel 1 (
    echo.
    if exist exam_tool.log type exam_tool.log
)
pause
