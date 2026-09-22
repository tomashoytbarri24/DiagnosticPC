@echo off
setlocal
cd /d "%~dp0"
echo [CorePulse] Benchmark V10 fue reemplazado por V11 en V173.
echo Ejecutando Probar_Benchmark_GPU_V11.bat...
call Probar_Benchmark_GPU_V11.bat
exit /b %ERRORLEVEL%
