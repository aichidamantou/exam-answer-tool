@echo off
chcp 65001 >nul
title Exam Answer Tool
cd /d "%~dp0"

echo.
echo === Exam Answer Tool - Windows Launcher ===
echo.

set PYDIR=python
set PYEXE=%PYDIR%\python.exe

if exist "%PYEXE%" goto INSTALL

echo [1/3] Downloading embedded Python ...
if not exist "%PYDIR%" mkdir "%PYDIR%"

curl -sL -o python.zip "https://repo.huaweicloud.com/python/3.12.4/python-3.12.4-embed-amd64.zip"
if not exist python.zip (
    curl -sL -o python.zip "https://mirrors.tuna.tsinghua.edu.cn/python/3.12.4/python-3.12.4-embed-amd64.zip"
)
if not exist python.zip (
    curl -sL -o python.zip "https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip"
)
if not exist python.zip (
    echo [ERROR] Failed to download Python
    pause
    exit /b 1
)

echo [2/3] Extracting ...
tar -xf python.zip -C "%PYDIR%"
del python.zip

:: Remove ._pth to enable full import paths
for %%f in ("%PYDIR%\*._pth") do del "%%f" 2>nul

:: Bootstrap pip
curl -sL -o get-pip.py "https://bootstrap.pypa.io/get-pip.py"
if exist get-pip.py (
    "%PYEXE%" get-pip.py -q 2>nul
    del get-pip.py
)

:INSTALL
echo [3/3] Checking dependencies ...
"%PYEXE%" -m pip install pywebview -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>nul

echo.
echo Starting application ...
echo.
echo NOTE: If the app closes immediately, check exam_tool.log
echo.

"%PYEXE%" main.py 2>exam_tool.log
if errorlevel 1 (
    echo [ERROR] Exit code %errorlevel%
    if exist exam_tool.log (
        echo --- exam_tool.log ---
        type exam_tool.log
    )
    pause
    exit /b 1
)
pause
