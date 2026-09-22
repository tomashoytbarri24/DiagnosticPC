@echo off
setlocal
cd /d "%~dp0"
echo [CorePulse] Benchmark V15 fue reemplazado por V16 en V184 por cambio de workload visual.
echo Ejecutando Probar_Benchmark_GPU_V16.bat...
call Probar_Benchmark_GPU_V16.bat
exit /b %ERRORLEVEL%
