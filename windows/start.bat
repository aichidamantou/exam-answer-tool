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
    echo [1/4] 下载便携版 Python 3.12 ...
    if not exist "%PYDIR%" mkdir "%PYDIR%"

    :: 华为云镜像
    curl -L -o python.zip "https://repo.huaweicloud.com/python/3.12.4/python-3.12.4-embed-amd64.zip" 2>nul
    if not exist python.zip (
        :: 清华源（备用）
        curl -L -o python.zip "https://mirrors.tuna.tsinghua.edu.cn/python/3.12.4/python-3.12.4-embed-amd64.zip" 2>nul
    )
    if not exist python.zip (
        :: 官方源
        curl -L -o python.zip "https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip" 2>nul
    )

    if not exist python.zip (
        echo [错误] Python下载失败，请检查网络连接
        pause
        exit /b 1
    )

    echo [2/4] 解压...
    tar -xf python.zip -C "%PYDIR%"
    del python.zip

    :: 删除 ._pth 文件解除路径限制（否则 pip 无法工作）
    if exist "%PYDIR%\python*._pth" del "%PYDIR%\python*._pth"
    if exist "%PYDIR%\python312._pth" del "%PYDIR%\python312._pth"

    :: 写入 pip 配置
    echo [global] > "%PYDIR%\pip.ini"
    echo index-url = https://pypi.tuna.tsinghua.edu.cn/simple >> "%PYDIR%\pip.ini"
    echo trusted-host = pypi.tuna.tsinghua.edu.cn >> "%PYDIR%\pip.ini"
)

:: 安装 pip（embed版默认没有pip）
echo [3/4] 安装 pip + 依赖...
if not exist "%PYDIR%\Scripts\pip.exe" (
    "%PYEXE%" -m pip --version >nul 2>&1
    if errorlevel 1 (
        curl -L -o get-pip.py "https://bootstrap.pypa.io/get-pip.py" 2>nul
        if exist get-pip.py (
            "%PYEXE%" get-pip.py -q 2>nul
            del get-pip.py
        )
    )
)

:: 安装 pywebview
"%PYEXE%" -m pip install pywebview -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>nul

:: 捕获错误日志
echo [4/4] 启动程序...
"%PYEXE%" main.py > exam_tool.log 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，请查看 exam_tool.log
    type exam_tool.log
    echo.
    echo 按任意键关闭...
    pause >nul
    exit /b 1
)

pause
