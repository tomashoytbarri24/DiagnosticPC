@echo off
cd /d "%~dp0"
echo [CorePulse] Benchmark V11 reemplazado por V12 en V175.
call Probar_Benchmark_GPU_V12.bat
exit /b %ERRORLEVEL%
