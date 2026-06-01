@echo off
chcp 65001 >nul 2>&1
title novel-tts 一键启动器
setlocal EnableDelayedExpansion

:: ============================================================
:: novel-tts Windows 一键启动器
:: ============================================================

call :banner

:: ---------- 1. 检测 Python ----------
echo [1/5] 正在检测 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 未检测到 Python。请确保 Python 3.11+ 已安装并添加到系统 PATH。
    echo         下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%a in ('python --version 2^>^&1') do echo         %%a

:: ---------- 2. 检测 uvicorn ----------
echo [2/5] 正在检测 uvicorn...
python -m uvicorn --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [警告] 未检测到 uvicorn，正在尝试自动安装依赖...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请手动运行: pip install -r requirements.txt
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%a in ('python -m uvicorn --version 2^>^&1') do echo         %%a

:: ---------- 3. 检测并创建目录 ----------
echo [3/5] 正在检查目录结构...
if not exist "data" mkdir data
if not exist "data\audio" mkdir data\audio
if not exist "data\temp" mkdir data\temp
echo         data\audio  [OK]
echo         data\temp   [OK]

:: ---------- 4. 加载配置（可选） ----------
echo [4/5] 正在加载配置...
if exist "config.bat" (
    call config.bat >nul 2>&1
    echo         已加载 config.bat
) else (
    echo         使用默认配置（config.bat 不存在）
)

:: 默认配置
if "%NOVEL_TTS_HOST%"=="" set NOVEL_TTS_HOST=0.0.0.0
if "%NOVEL_TTS_PORT%"=="" set NOVEL_TTS_PORT=8008
if "%NOVEL_TTS_API_KEY%"=="" set NOVEL_TTS_API_KEY=dev-local-key
if "%NOVEL_TTS_OUTPUT_DIR%"=="" set NOVEL_TTS_OUTPUT_DIR=%CD%\data\audio
if "%NOVEL_TTS_TEMP_DIR%"=="" set NOVEL_TTS_TEMP_DIR=%CD%\data\temp
if "%NOVEL_TTS_DB_URL%"=="" set NOVEL_TTS_DB_URL=sqlite:///%CD%\novel_tts.db
if "%NOVEL_TTS_MAX_CONCURRENT_JOBS%"=="" set NOVEL_TTS_MAX_CONCURRENT_JOBS=1

echo         HOST: %NOVEL_TTS_HOST%
echo         PORT: %NOVEL_TTS_PORT%
echo         API_KEY: %NOVEL_TTS_API_KEY%
echo         OUTPUT_DIR: %NOVEL_TTS_OUTPUT_DIR%

:: ---------- 5. 启动服务 ----------
echo [5/5] 正在启动服务...
echo.
echo ============================================================
echo   服务启动中...请不要关闭此窗口
echo ============================================================
echo.
echo   API 地址: http://%NOVEL_TTS_HOST%:%NOVEL_TTS_PORT%
echo   健康检查: http://%NOVEL_TTS_HOST%:%NOVEL_TTS_PORT%/healthz
echo.
echo   按 Ctrl+C 停止服务
echo.

:: 启动 uvicorn
python -m uvicorn main:app --host %NOVEL_TTS_HOST% --port %NOVEL_TTS_PORT% --log-level info

:: 如果服务退出，暂停一下让用户看到错误信息
echo.
echo 服务已停止。
pause
exit /b

:: ============================================================
:: 函数: banner
:: ============================================================
:banner
echo.
echo    _   ___  ___  ___  ___    _________  _____ __________
echo   ^| \ / / ^|/ (_)/ _ \/ _ \  /_  __/ _ \/ ___// ___/ __ \
echo   ^| \\ V /   / / / , _/ , _/   / / / , _/ (_ / (_ / /_/ /
echo   ^|_^|\\_/_ /_/_^|_^|\\_^|_^|\\_^|   /_/ /_^|^|_^|\\___/\\___/\\____/ TTS
echo.
echo   Windows 一键启动器
echo.
goto :eof
