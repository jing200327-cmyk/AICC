@echo off
chcp 65001 >nul
title GLM Proxy Server
cd /d "%~dp0"

echo ========================================
echo   GLM Proxy Server
echo   Anthropic API --^> OpenAI (Zhipu GLM)
echo ========================================
echo.

REM Check if venv exists, if not create it
if not exist "venv\Scripts\python.exe" (
    echo [1/2] Creating virtual environment...
    python -m venv venv
    echo.
    echo [2/2] Installing dependencies...
    venv\Scripts\python.exe -m pip install -q -r requirements.txt
    echo.
)

echo Starting proxy server on http://127.0.0.1:18765 ...
echo Upstream model: glm-4-plus
echo.
echo Press Ctrl+C to stop.
echo.

venv\Scripts\python.exe server.py %*
pause
