@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动考试答题工具...
python main.py
pause
