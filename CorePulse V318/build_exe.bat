@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%CD%"
set "VPY="
if exist "%ROOT%\.corepulse_runtime_python.txt" set /p VPY=<"%ROOT%\.corepulse_runtime_python.txt"
if not defined VPY set "VPY=%ROOT%\.venv\Scripts\python.exe"
set "APPVER="
for /f "tokens=2 delims== " %%V in ('findstr /B /C:"VERSION = " core\version.py') do set "APPVER=%%~V"
if not defined APPVER set "APPVER=UNKNOWN"
set "EXE=%ROOT%\dist\CorePulse\CorePulse.exe"
set "SELFTEST=%ROOT%\dist\CorePulse_EXE_SELFTEST.json"
set "PROBE=%ROOT%\dist\CorePulse_HELPER_PROBE.json"

if not exist "%VPY%" (
  echo [ERROR] No existe un runtime validado. Ejecuta instalar_dependencias.bat primero.
  pause
  exit /b 1
)

echo ================================================================
echo       COREPULSE V%APPVER% - BUILD EXE + SELF-TEST
echo ================================================================
echo.

"%VPY%" -c "import sys,struct; raise SystemExit(0 if sys.version_info[:2]>=(3,12) and struct.calcsize('P')*8==64 else 1)"
if errorlevel 1 goto :FAIL_RUNTIME

if exist "%ROOT%\build\pyinstaller-work" rmdir /s /q "%ROOT%\build\pyinstaller-work"
if exist "%ROOT%\dist\CorePulse" rmdir /s /q "%ROOT%\dist\CorePulse"
if exist "%SELFTEST%" del /q "%SELFTEST%"
if exist "%PROBE%" del /q "%PROBE%"

echo [1/5] PyInstaller ONEDIR...
"%VPY%" -m PyInstaller --noconfirm --clean --distpath "%ROOT%\dist" --workpath "%ROOT%\build\pyinstaller-work" "%ROOT%\build\CorePulse.spec"
if errorlevel 1 goto :FAIL_BUILD
if not exist "%EXE%" goto :FAIL_NO_EXE

echo.
echo [2/5] Verificando recursos criticos del bundle...
set "LHM_FOUND="
for /f "delims=" %%F in ('dir /s /b "%ROOT%\dist\CorePulse\LibreHardwareMonitorLib.dll" 2^>nul') do if not defined LHM_FOUND set "LHM_FOUND=%%F"
if not defined LHM_FOUND goto :FAIL_LHM
set "HID_FOUND="
for /f "delims=" %%F in ('dir /s /b "%ROOT%\dist\CorePulse\HidSharp.dll" 2^>nul') do if not defined HID_FOUND set "HID_FOUND=%%F"
if not defined HID_FOUND goto :FAIL_LHM
if not exist "%ROOT%\dist\CorePulse\_internal\tools\presentmon\PresentMon.exe" goto :FAIL_PRESENTMON
if not exist "%ROOT%\dist\CorePulse\_internal\Instalar_Speedtest_Ookla.bat" goto :FAIL_SPEEDTEST_SCRIPT
if not exist "%ROOT%\dist\CorePulse\_internal\assets\app_icon.ico" goto :FAIL_ASSET
echo     [OK] LibreHardwareMonitorLib.dll
echo     [OK] HidSharp.dll
echo     [OK] PresentMon.exe
echo     [OK] Instalador Ookla
echo     [OK] assets

echo.
echo [3/5] Ejecutando self-test DENTRO de CorePulse.exe...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process -FilePath '%EXE%' -ArgumentList @('--corepulse-self-test','--output','%SELFTEST%') -Wait -PassThru; exit $p.ExitCode"
if errorlevel 1 goto :FAIL_SELFTEST
if not exist "%SELFTEST%" goto :FAIL_SELFTEST
powershell -NoProfile -ExecutionPolicy Bypass -Command "$j=Get-Content -Raw -LiteralPath '%SELFTEST%' | ConvertFrom-Json; if(-not $j.ready){exit 1}; Write-Host ('     [OK] checks criticos: '+($j.critical_total-$j.critical_failed)+'/'+$j.critical_total)"
if errorlevel 1 goto :FAIL_SELFTEST

echo.
echo [4/5] Probando dispatcher interno del MISMO EXE...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process -FilePath '%EXE%' -ArgumentList @('--corepulse-helper-probe','--output','%PROBE%') -Wait -PassThru; exit $p.ExitCode"
if errorlevel 1 goto :FAIL_HELPER
if not exist "%PROBE%" goto :FAIL_HELPER
powershell -NoProfile -ExecutionPolicy Bypass -Command "$j=Get-Content -Raw -LiteralPath '%PROBE%' | ConvertFrom-Json; if(-not $j.ok -or $j.version -ne '%APPVER%'){exit 1}"
if errorlevel 1 goto :FAIL_HELPER

echo.
echo [5/5] Integridad final...
if exist "%ROOT%\dist\CorePulse\_internal\data" goto :FAIL_MUTABLE_BUNDLE
if exist "%ROOT%\dist\CorePulse\_internal\logs" goto :FAIL_MUTABLE_BUNDLE

echo.
echo ================================================================
echo [OK] COREPULSE.EXE CREADO Y VALIDADO POR SELF-TEST
echo ================================================================
echo Ejecutable: %EXE%
echo Self-test : %SELFTEST%
echo.
echo Nota: RTSS, PawnIO, Ookla CLI y GROQ_API_KEY son capacidades externas.
echo Si no existen en un PC, CorePulse debe mostrar N/A/NO DISPONIBLE sin inventar datos.
echo.
echo Siguiente paso opcional: build_installer.bat
pause
exit /b 0

:FAIL_RUNTIME
echo [ERROR] El runtime de release no usa CPython 3.12+ x64. Ejecuta instalar_dependencias.bat.
goto :ENDFAIL
:FAIL_BUILD
echo [ERROR] PyInstaller fallo.
goto :ENDFAIL
:FAIL_NO_EXE
echo [ERROR] PyInstaller termino sin CorePulse.exe.
goto :ENDFAIL
:FAIL_LHM
echo [ERROR] El bundle no contiene LibreHardwareMonitorLib.dll y/o HidSharp.dll.
goto :ENDFAIL
:FAIL_PRESENTMON
echo [ERROR] PresentMon.exe no fue empaquetado.
goto :ENDFAIL
:FAIL_SPEEDTEST_SCRIPT
echo [ERROR] Instalar_Speedtest_Ookla.bat no fue empaquetado.
goto :ENDFAIL
:FAIL_ASSET
echo [ERROR] Faltan assets esenciales en el bundle.
goto :ENDFAIL
:FAIL_SELFTEST
echo [ERROR] CorePulse.exe fallo su self-test interno.
echo Reporte esperado: %SELFTEST%
if exist "%SELFTEST%" powershell -NoProfile -Command "Get-Content -LiteralPath '%SELFTEST%' -Raw"
goto :ENDFAIL
:FAIL_HELPER
echo [ERROR] El mismo CorePulse.exe no pudo ejecutar su modo interno de helper.
goto :ENDFAIL
:FAIL_MUTABLE_BUNDLE
echo [ERROR] Se detectaron datos/logs mutables dentro de _internal.
echo La build se cancela para proteger historial y rollback entre actualizaciones.
goto :ENDFAIL
:ENDFAIL
echo.
echo La build NO se considera valida. Corrige el error antes de distribuirla.
pause
exit /b 1
