@echo off
chcp 65001 >nul 2>&1
title novel-tts 停止服务
setlocal

echo.
echo 正在查找 novel-tts 服务进程...
echo.

:: 查找占用 8008 端口的进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8008" ^| findstr "LISTENING"') do (
    set PID=%%a
    echo 发现进程 PID: %%a
    echo 正在终止...
    taskkill /F /PID %%a >nul 2>&1
    if errorlevel 1 (
        echo [错误] 无法终止进程 %%a，请尝试以管理员身份运行此脚本。
    ) else (
        echo [成功] 进程 %%a 已终止。
    )
    goto :done
)

:: 查找 uvicorn/python 进程（按窗口标题匹配）
for /f "skip=3 tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq novel-tts 一键启动器" /NH 2^>nul') do (
    set PID=%%a
    echo 发现进程 PID: %%a
echo 正在终止...
    taskkill /F /PID %%a >nul 2>&1
    if errorlevel 1 (
        echo [错误] 无法终止进程 %%a，请尝试以管理员身份运行此脚本。
    ) else (
        echo [成功] 进程 %%a 已终止。
    )
    goto :done
)

echo 未找到运行中的 novel-tts 服务。

:done
echo.
pause
