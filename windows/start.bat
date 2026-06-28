@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 考试答题工具
cd /d "%~dp0"

echo.
echo === 考试答题工具 - Windows启动 ===
echo.

set PYDIR=python
set PYEXE=%PYDIR%\python.exe

if not exist "%PYEXE%" (
    echo [下载] 便携版 Python 3.12 ...
    if not exist "%PYDIR%" mkdir "%PYDIR%"

    set DL_OK=0

    :: 1. 华为云镜像
    curl -L -o python.zip "https://repo.huaweicloud.com/python/3.12.4/python-3.12.4-embed-amd64.zip" 2>nul
    if exist python.zip set DL_OK=1

    :: 2. 清华源（备用）
    if not exist python.zip (
        curl -L -o python.zip "https://mirrors.tuna.tsinghua.edu.cn/python/3.12.4/python-3.12.4-embed-amd64.zip" 2>nul
        if exist python.zip set DL_OK=1
    )

    :: 3. 官方源（最后备用）
    if not exist python.zip (
        curl -L -o python.zip "https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip" 2>nul
        if exist python.zip set DL_OK=1
    )

    if not exist python.zip (
        echo.
        echo [错误] Python下载失败
        echo 请手动下载: https://mirrors.tuna.tsinghua.edu.cn/python/3.12.4/
        echo 选择 python-3.12.4-embed-amd64.zip
        echo 解压到 windows\python 目录后重新运行
        pause
        exit /b 1
    )

    echo [解压] Python...
    tar -xf python.zip -C "%PYDIR%"
    del python.zip

    :: 启用pip
    "%PYEXE%" -m pip install --upgrade pip -q 2>nul

    :: 设置pip国内源
    if exist "%PYDIR%\" (
        echo [global] > "%PYDIR%\pip.ini"
        echo index-url = https://pypi.tuna.tsinghua.edu.cn/simple >> "%PYDIR%\pip.ini"
        echo trusted-host = pypi.tuna.tsinghua.edu.cn >> "%PYDIR%\pip.ini"
    )
)

:: 安装依赖
if not exist "%PYDIR%\Lib\site-packages\pywebview\" (
    echo [安装] pywebview (使用清华镜像)...
    "%PYEXE%" -m pip install pywebview -q -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo [启动] 运行答题工具...
"%PYEXE%" main.py

pause
