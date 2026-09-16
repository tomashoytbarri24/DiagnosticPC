@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "ROOT=%CD%"
set "LOG=%ROOT%\dependency_install.log"
>"%LOG%" echo CorePulse V0.10.2.99w dependency setup - %date% %time%

echo ================================================================
echo     COREPULSE V0.10.2.99w - ENTORNO DE BUILD REPRODUCIBLE
echo ================================================================
echo.

if not exist "%ROOT%\main.py" goto :FAIL_PROJECT
if not exist "%ROOT%\corepulse_launcher.py" goto :FAIL_PROJECT
if not exist "%ROOT%\requirements-win-lock.txt" goto :FAIL_LOCK

set "PYEXE="
if not "%~1"=="" if exist "%~1" set "PYEXE=%~1"

rem La build oficial se fija a Python 3.12 x64: es el runtime probado del proyecto.
if not defined PYEXE for /f "usebackq delims=" %%P in (`py -3.12 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYEXE=%%P"
if not defined PYEXE if exist "C:\Python312\python.exe" set "PYEXE=C:\Python312\python.exe"
if not defined PYEXE for /f "usebackq delims=" %%P in (`where python.exe 2^>nul`) do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE goto :FAIL_PYTHON

"%PYEXE%" -c "import sys,struct; ok=sys.version_info[:2]==(3,12) and struct.calcsize('P')*8==64; print(sys.version.split()[0], str(struct.calcsize('P')*8)+'-bit'); raise SystemExit(0 if ok else 1)" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_PYTHON_VERSION

echo [1/6] Python 3.12 x64: OK

echo [2/6] Recreando venv de build en ruta corta...
set "BUILDVENV=%LOCALAPPDATA%\CorePulse\build\py312"
if "%LOCALAPPDATA%"=="" set "BUILDVENV=%TEMP%\CorePulseBuild\py312"
if exist "%BUILDVENV%" rmdir /s /q "%BUILDVENV%" >>"%LOG%" 2>&1
if exist "%BUILDVENV%" goto :FAIL_VENV
for %%D in ("%BUILDVENV%\..") do if not exist "%%~fD" mkdir "%%~fD" >>"%LOG%" 2>&1
"%PYEXE%" -m venv "%BUILDVENV%" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_VENV
set "VPY=%BUILDVENV%\Scripts\python.exe"
if not exist "%VPY%" goto :FAIL_VENV

echo [3/6] Actualizando herramientas de instalacion...
"%VPY%" -m pip install --upgrade pip setuptools wheel >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_PIP

echo [4/6] Instalando lock de dependencias Windows...
"%VPY%" -m pip install --prefer-binary -r "%ROOT%\requirements-win-lock.txt" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_DEPS

echo [5/6] Verificando runtime y stack profundo de sensores...
"%VPY%" -c "import psutil,customtkinter,PIL,matplotlib,reportlab,platformdirs,send2trash,groq,dotenv,pystray,wmi,win32api,pythoncom,pywintypes,clr,pythonnet; print('Python imports OK')" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_VERIFY
"%VPY%" -c "import HardwareMonitor,pathlib; from HardwareMonitor.Hardware import Computer; p=pathlib.Path(HardwareMonitor.__file__).resolve().parent/'lib'; a=list(p.rglob('LibreHardwareMonitorLib.dll')); h=list(p.rglob('HidSharp.dll')); assert a and h, (p,a,h); c=Computer(); print('HardwareMonitor OK', a[0], h[0])" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_SENSORS

echo [6/6] Compilando fuente y test estatico de integridad EXE...
"%VPY%" -m compileall -q "%ROOT%\core" "%ROOT%\gui" "%ROOT%\performance" "%ROOT%\database" "%ROOT%\main.py" "%ROOT%\corepulse_launcher.py" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_SOURCE
"%VPY%" "%ROOT%\tests\test_exe_runtime_integrity.py" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_SOURCE

echo.
echo ================================================================
echo [OK] ENTORNO V0.10.2.99w VALIDADO
echo ================================================================
echo Python: %VPY%
echo Siguiente paso: build_exe.bat
echo Log: %LOG%
echo.
pause
exit /b 0

:FAIL_PROJECT
echo [ERROR] Ejecuta este BAT desde la carpeta completa de CorePulse.
goto :SHOW
:FAIL_LOCK
echo [ERROR] Falta requirements-win-lock.txt.
goto :SHOW
:FAIL_PYTHON
echo [ERROR] No se encontro Python 3.12 x64.
echo Instala Python 3.12 x64 o pasa su ruta como primer argumento.
goto :SHOW
:FAIL_PYTHON_VERSION
echo [ERROR] Para la build reproducible se requiere Python 3.12 x64 exactamente.
goto :SHOW
:FAIL_VENV
echo [ERROR] No se pudo recrear .venv. Cierra CorePulse/VS Code si lo estan usando.
goto :SHOW
:FAIL_PIP
echo [ERROR] No se pudieron preparar pip/setuptools/wheel.
goto :SHOW
:FAIL_DEPS
echo [ERROR] Fallo la instalacion del lock de dependencias.
goto :SHOW
:FAIL_VERIFY
echo [ERROR] Falta o falla una dependencia incluida en el producto.
goto :SHOW
:FAIL_SENSORS
echo [ERROR] HardwareMonitor/LibreHardwareMonitor no quedo operativo en .venv.
echo No se permite construir un EXE con sensores profundos rotos.
goto :SHOW
:FAIL_SOURCE
echo [ERROR] La fuente o el test estatico de integridad fallo.
goto :SHOW
:SHOW
echo.
echo ---------------- ULTIMAS LINEAS DEL LOG ----------------
powershell -NoProfile -ExecutionPolicy Bypass -Command "if(Test-Path -LiteralPath '%LOG%'){Get-Content -LiteralPath '%LOG%' -Tail 60}"
echo ----------------------------------------------------------
echo Log completo: %LOG%
pause
exit /b 1
