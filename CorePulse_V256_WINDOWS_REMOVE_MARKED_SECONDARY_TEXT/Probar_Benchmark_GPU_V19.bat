@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)
"%PY%" tools\probar_benchmark_gpu_v19.py standard
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Resultado valido: resultados\benchmark_gpu_v19_ultimo_resultado.json
) else (
  echo La prueba no termino correctamente. Revisa la salida anterior.
)
pause
exit /b %RC%
