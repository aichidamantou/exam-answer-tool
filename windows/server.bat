@echo off
chcp 65001 >nul
title Exam Answer Tool - Server Mode
cd /d "%~dp0"

echo.
echo === Exam Answer Tool - Server Mode ===
echo.

:: Try system Python, then embedded Python
set PYEXE=python
python --version 2>nul
if errorlevel 1 (
    if exist "python\python.exe" (
        set PYEXE=python\python.exe
    ) else (
        echo [ERROR] Python not found.
        echo Run start.bat first, or install Python manually.
        pause
        exit /b 1
    )
)

echo [Starting] HTTP server on random port ...
echo [Browser] Will open automatically
echo [Stop]    Close this window or Ctrl+C
echo.

%PYEXE% main.py --server

pause
