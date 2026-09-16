@echo off
setlocal
chcp 65001 >nul
title 法学招聘信息中台
cd /d "%~dp0"

rem ── 环境检查 ────────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo [x] 未找到虚拟环境 .venv
    echo     首次使用请执行:
    echo       py -3.13 -m venv .venv
    echo       .venv\Scripts\pip install -e .
    pause
    exit /b 1
)

rem ── 参数：start.bat dev  =  关闭定时采集（调试用） ──────────
if /i "%~1"=="dev" set "APP_DISABLE_SCHEDULER=1"

echo ────────────────────────────────────────────────
echo   法学招聘信息中台    http://127.0.0.1:8642
echo   停止服务：Ctrl+C 或直接关闭本窗口
if defined APP_DISABLE_SCHEDULER echo   模式：调试（定时采集已关闭）
echo ────────────────────────────────────────────────

rem ── 服务起来后自动打开浏览器 ────────────────────────────────
start "" /min cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:8642"

.venv\Scripts\python.exe -m uvicorn app.web.main:create_app --factory --host 127.0.0.1 --port 8642

echo.
echo [i] 服务已退出。
pause
