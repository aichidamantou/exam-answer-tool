@echo off
chcp 65001 >nul
title 考试答题工具
cd /d "%~dp0"

echo.
echo === 考试答题工具 - Windows启动 ===
echo.

set PYDIR=python
set PYEXE=%PYDIR%\python.exe

:: ========== 步骤1: 下载Python ==========
if exist "%PYEXE%" goto :INSTALL_DEPS

echo [1/3] 下载便携版 Python 3.12 ...
if not exist "%PYDIR%" mkdir "%PYDIR%"

curl -L -o python.zip "https://repo.huaweicloud.com/python/3.12.4/python-3.12.4-embed-amd64.zip" 2>nul
if not exist python.zip (
    curl -L -o python.zip "https://mirrors.tuna.tsinghua.edu.cn/python/3.12.4/python-3.12.4-embed-amd64.zip" 2>nul
)
if not exist python.zip (
    curl -L -o python.zip "https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip" 2>nul
)

if not exist python.zip (
    echo [错误] Python下载失败
    pause
    exit /b 1
)

echo [2/3] 解压配置...
tar -xf python.zip -C "%PYDIR%"
del python.zip

:: 删除._pth解除路径限制
if exist "%PYDIR%\python*._pth" del "%PYDIR%\python*._pth" 2>nul

:: pip配置
echo [global] > "%PYDIR%\pip.ini"
echo index-url = https://pypi.tuna.tsinghua.edu.cn/simple >> "%PYDIR%\pip.ini"
echo trusted-host = pypi.tuna.tsinghua.edu.cn >> "%PYDIR%\pip.ini"

:: ========== 步骤2: 安装依赖 ==========
:INSTALL_DEPS
echo [3/3] 安装依赖...
"%PYEXE%" -m pip install pywebview -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>nul

:: ========== 步骤3: 运行程序 ==========
echo.
echo === 启动答题工具 ===
echo 错误日志将写入 exam_tool.log
echo.

"%PYEXE%" main.py 1>exam_tool.log 2>&1
if errorlevel 1 (
    echo [错误] 程序异常退出
    echo 请查看 exam_tool.log 了解详情
    echo.
    type exam_tool.log
    echo.
    pause
    exit /b 1
)
pause
