@echo off
chcp 65001 >nul
title KylinOps

cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python venv not found.
    echo Expected: %~dp0backend\.venv\Scripts\python.exe
    echo Please rebuild the venv first.
    pause
    exit /b 1
)

echo ==========================================
echo   KylinOps - Kylin Ops Agent
echo ==========================================
echo   Wait until you see:
echo       "Application startup complete"
echo   then open this address in your browser:
echo.
echo       http://127.0.0.1:8000
echo.
echo   Account : admin / admin123
echo   Close this window to stop the service.
echo ==========================================
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
