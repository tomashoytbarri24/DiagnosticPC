@echo off
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo ============================================================
echo  CorePulse V179 - Benchmark GPU V13 DirectX 11
echo  Wall-clock deterministic - sin camara lenta por FPS
echo ============================================================
echo.
"%PY%" tools\probar_benchmark_gpu_v13.py standard
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERROR] La prueba no termino OK.
  echo Envia resultados\benchmark_gpu_v13_ultimo_resultado.json.
) else (
  echo [OK] Benchmark V13 completo.
  echo Envia resultados\benchmark_gpu_v13_ultimo_resultado.json y, si puedes, un video.
)
pause
exit /b %RC%
