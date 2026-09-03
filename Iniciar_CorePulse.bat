@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [CorePulse] Falta el entorno .venv.
    echo Ejecuta instalar_dependencias.bat primero.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
