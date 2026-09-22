@echo off
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo ============================================================
echo  CorePulse V184 - Benchmark GPU V16 DirectX 11
echo  Visual cleanup - wall-clock deterministic
echo ============================================================
echo.
"%PY%" tools\probar_benchmark_gpu_v16.py standard
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERROR] La prueba no termino OK.
  echo Envia resultados\benchmark_gpu_v16_ultimo_resultado.json si existe evidencia util.
) else (
  echo [OK] Benchmark V16 completo.
  echo Envia resultados\benchmark_gpu_v16_ultimo_resultado.json y, si puedes, un video.
)
pause
exit /b %RC%
