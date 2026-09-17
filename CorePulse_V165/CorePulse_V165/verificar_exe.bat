@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "EXE=%CD%\dist\CorePulse\CorePulse.exe"
set "REPORT=%CD%\dist\CorePulse_EXE_SELFTEST_MANUAL.json"
if not exist "%EXE%" (
  echo [ERROR] No existe %EXE%
  echo Ejecuta build_exe.bat primero.
  pause
  exit /b 1
)
if exist "%REPORT%" del /q "%REPORT%"
echo Verificando CorePulse.exe sin abrir la interfaz...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process -FilePath '%EXE%' -ArgumentList @('--corepulse-self-test','--output','%REPORT%') -Wait -PassThru; exit $p.ExitCode"
set "RC=%ERRORLEVEL%"
if exist "%REPORT%" powershell -NoProfile -ExecutionPolicy Bypass -Command "$j=Get-Content -Raw -LiteralPath '%REPORT%'|ConvertFrom-Json; Write-Host ('Version: '+$j.version); Write-Host ('Ready: '+$j.ready); Write-Host ('Criticos fallidos: '+$j.critical_failed); $j.items | Where-Object { -not $_.ok } | ForEach-Object { Write-Host (' - '+$_.name+': '+$_.detail) }; $j.warnings | Where-Object { -not $_.ok } | ForEach-Object { Write-Host (' [AVISO] '+$_.name+': '+$_.detail) }"
if not "%RC%"=="0" (
  echo.
  echo [ERROR] El EXE NO supero la validacion. No lo distribuyas.
  echo Reporte: %REPORT%
  pause
  exit /b %RC%
)
echo.
echo [OK] CorePulse.exe supero todos los checks criticos.
echo Reporte: %REPORT%
pause
exit /b 0
