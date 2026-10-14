@echo off
setlocal
title OPUS Agent
chcp 65001 >nul

cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado no PATH.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [*] Criando ambiente virtual...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar .venv
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt

".venv\Scripts\python.exe" main.py %*

pause
