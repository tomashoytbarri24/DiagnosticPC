@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "BOOT=%~dp0bootstrap_corepulse.py"
if not exist "%BOOT%" exit /b 2

rem 1) Si el venv local todavía es ejecutable, se repara con su propio Python.
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,12) else 9)" >nul 2>&1
    if not errorlevel 1 (
        "%~dp0.venv\Scripts\python.exe" "%BOOT%"
        exit /b !errorlevel!
    )
)

rem 2) Autoridad de desarrollo: Python 3.12 x64.
where py.exe >nul 2>&1
if not errorlevel 1 (
    py -3.12 -c "import sys,struct; raise SystemExit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')*8==64 else 9)" >nul 2>&1
    if not errorlevel 1 (
        py -3.12 "%BOOT%"
        exit /b !errorlevel!
    )
)

rem 3) Fallback si Python 3.12 es el python.exe principal del sistema.
where python.exe >nul 2>&1
if not errorlevel 1 (
    python "%BOOT%"
    exit /b %errorlevel%
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('No se encontró Python 3.12 x64. Instálalo y vuelve a abrir CorePulse.','CorePulse','OK','Error')" >nul 2>&1
exit /b 3
