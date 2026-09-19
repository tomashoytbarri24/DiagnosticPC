@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=%CD%\.venv\Scripts\python.exe"
if not defined PY where py >nul 2>&1 && set "PY=py -3.12"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo [ERROR] No se encontro Python. Ejecuta instalar_dependencias.bat.
  pause
  exit /b 1
)
%PY% quality_gate.py
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo [OK] Quality Gate completado.
) else (
  echo [ERROR] Quality Gate fallo. Revisa la salida anterior.
)
pause
exit /b %RC%
