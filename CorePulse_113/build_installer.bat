@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"
set "EXE=%ROOT%\dist\CorePulse\CorePulse.exe"
set "SELFTEST=%ROOT%\dist\CorePulse_EXE_SELFTEST.json"
if not exist "%EXE%" goto :NOEXE
if not exist "%SELFTEST%" goto :NOSELF
powershell -NoProfile -Command "$j=Get-Content -Raw -LiteralPath '%SELFTEST%'|ConvertFrom-Json; if(-not $j.ready){exit 1}"
if errorlevel 1 goto :NOSELF
set "ISCC="
where ISCC.exe >nul 2>&1 && set "ISCC=ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC goto :NOINNO
"%ISCC%" "%ROOT%\installer\CorePulse.iss"
if errorlevel 1 goto :FAIL
echo.
echo [OK] Instalador creado desde un EXE que supero el self-test.
echo     %ROOT%\dist\installer\CorePulse_Setup_V0.10.2.81w.exe
pause
exit /b 0
:NOEXE
echo [ERROR] Primero ejecuta build_exe.bat.
goto :END
:NOSELF
echo [ERROR] No existe un self-test valido. Repite build_exe.bat.
goto :END
:NOINNO
echo [ERROR] No se encontro Inno Setup 6 ^(ISCC.exe^).
goto :END
:FAIL
echo [ERROR] Inno Setup no pudo compilar el instalador.
:END
pause
exit /b 1
