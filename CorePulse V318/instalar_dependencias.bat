@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "ROOT=%CD%"
set "LOG=%ROOT%\dependency_install.log"
set "RUNTIME_POINTER=%ROOT%\.corepulse_runtime_python.txt"
set "RUNTIME_REPORT=%ROOT%\.corepulse_runtime_validation.json"
>"%LOG%" echo CorePulse V298 auto multi-Python dependency setup - %date% %time%

echo ================================================================
echo        COREPULSE V298 - RUNTIME AUTO MULTI-PYTHON 3.12+ x64
echo ================================================================
echo.

if not exist "%ROOT%\main.py" goto :FAIL_PROJECT
if not exist "%ROOT%\corepulse_launcher.py" goto :FAIL_PROJECT
if not exist "%ROOT%\requirements-runtime-lock.txt" goto :FAIL_LOCK
if not exist "%ROOT%\requirements-runtime-flex.txt" goto :FAIL_LOCK
if not exist "%ROOT%\tools\validate_python_runtime.py" goto :FAIL_PROJECT

set "PYEXE="
if not "%~1"=="" if exist "%~1" set "PYEXE=%~1"

rem 1) Python Launcher: usa el Python 3 por defecto / más nuevo registrado.
if not defined PYEXE for /f "usebackq delims=" %%P in (`py -3 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYEXE=%%P"
rem 2) Rutas comunes para instalaciones manuales.
if not defined PYEXE if exist "C:\Python314\python.exe" set "PYEXE=C:\Python314\python.exe"
if not defined PYEXE if exist "C:\Python313\python.exe" set "PYEXE=C:\Python313\python.exe"
if not defined PYEXE if exist "C:\Python312\python.exe" set "PYEXE=C:\Python312\python.exe"
rem 3) PATH como último recurso.
if not defined PYEXE for /f "usebackq delims=" %%P in (`where python.exe 2^>nul`) do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE goto :FAIL_PYTHON

"%PYEXE%" -c "import sys,struct; ok=sys.version_info[:2]>=(3,12) and struct.calcsize('P')*8==64; print('CPython',sys.version.split()[0],str(struct.calcsize('P')*8)+'-bit',sys.executable); raise SystemExit(0 if ok else 1)" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_PYTHON_VERSION

for /f "usebackq delims=" %%V in (`"%PYEXE%" -c "import sys; print('py'+str(sys.version_info.major)+str(sys.version_info.minor))"`) do set "PYTAG=%%V"
if not defined PYTAG goto :FAIL_PYTHON_VERSION

echo [1/7] Runtime detectado: %PYTAG% x64

echo [2/7] Recreando runtime aislado...
set "BUILDVENV=%LOCALAPPDATA%\CorePulse\runtime\%PYTAG%\v298"
if "%LOCALAPPDATA%"=="" set "BUILDVENV=%TEMP%\CorePulseRuntime\%PYTAG%\v298"
if exist "%BUILDVENV%" rmdir /s /q "%BUILDVENV%" >>"%LOG%" 2>&1
if exist "%BUILDVENV%" goto :FAIL_VENV
for %%D in ("%BUILDVENV%\..") do if not exist "%%~fD" mkdir "%%~fD" >>"%LOG%" 2>&1
"%PYEXE%" -m venv "%BUILDVENV%" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_VENV
set "VPY=%BUILDVENV%\Scripts\python.exe"
if not exist "%VPY%" goto :FAIL_VENV

echo [3/7] Actualizando pip / setuptools / wheel...
"%VPY%" -m pip install --upgrade pip setuptools wheel >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_PIP

echo [4/7] Intentando lock reproducible...
set "RESOLUTION=LOCK"
"%VPY%" -m pip install --prefer-binary -r "%ROOT%\requirements-runtime-lock.txt" >>"%LOG%" 2>&1
if errorlevel 1 (
    echo     Lock exacto no disponible para %PYTAG%. Probando resolucion adaptable...
    >>"%LOG%" echo [INFO] Lock exacto fallo. Iniciando requirements-runtime-flex.txt
    set "RESOLUTION=FLEX"
    "%VPY%" -m pip install --upgrade --prefer-binary -r "%ROOT%\requirements-runtime-flex.txt" >>"%LOG%" 2>&1
    if errorlevel 1 goto :FAIL_DEPS
)

echo [5/7] Validando stack COMPLETO de CorePulse...
"%VPY%" "%ROOT%\tools\validate_python_runtime.py" --output "%RUNTIME_REPORT%" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_VERIFY

echo [6/7] Compilando fuente y pruebas de integridad...
"%VPY%" -m compileall -q "%ROOT%\core" "%ROOT%\gui" "%ROOT%\performance" "%ROOT%\database" "%ROOT%\main.py" "%ROOT%\corepulse_launcher.py" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_SOURCE
"%VPY%" -c "from core.version import VERSION; from core.python_compat import is_supported_python,is_x64; assert VERSION=='298'; assert is_supported_python() and is_x64(); print('Project integrity OK V'+VERSION)" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_SOURCE

echo [7/7] Registrando runtime validado...
>"%RUNTIME_POINTER%" echo %VPY%
if not exist "%RUNTIME_POINTER%" goto :FAIL_POINTER

for /f "usebackq delims=" %%V in (`"%VPY%" -c "import platform; print(platform.python_version())"`) do set "VALIDATED_VERSION=%%V"

echo.
echo ================================================================
echo [OK] COREPULSE V298 VALIDADO EN PYTHON %VALIDATED_VERSION% x64
echo ================================================================
echo Runtime : %VPY%
echo Resolucion de dependencias: %RESOLUTION%
echo Reporte : %RUNTIME_REPORT%
echo.
echo Puedes iniciar con cualquiera de estos comandos:
echo   "%VPY%" "%ROOT%\corepulse_launcher.py"
echo   python "%ROOT%\corepulse_launcher.py"
echo   python "%ROOT%\main.py"
echo Si el segundo/tercer comando usa otro Python sin dependencias, CorePulse
echo se redirige automaticamente a este runtime validado.
echo.
pause
exit /b 0

:FAIL_PROJECT
echo [ERROR] Ejecuta este BAT desde la carpeta completa de CorePulse V298.
goto :SHOW
:FAIL_LOCK
echo [ERROR] Faltan archivos de dependencias lock/flex.
goto :SHOW
:FAIL_PYTHON
echo [ERROR] No se encontro CPython 3.12+ x64.
echo Puedes pasar la ruta como argumento, por ejemplo:
echo instalar_dependencias.bat C:\Python314\python.exe
goto :SHOW
:FAIL_PYTHON_VERSION
echo [ERROR] El Python detectado no es CPython 3.12+ x64.
echo CorePulse no fija un minor maximo, pero requiere 3.12 o superior y 64 bits.
goto :SHOW
:FAIL_VENV
echo [ERROR] No se pudo crear el runtime aislado.
goto :SHOW
:FAIL_PIP
echo [ERROR] No se pudieron preparar pip/setuptools/wheel.
goto :SHOW
:FAIL_DEPS
echo [ERROR] No existe una combinacion instalable del stack completo para este Python.
echo Esa version NO se declara compatible hasta que todas las dependencias existan.
goto :SHOW
:FAIL_VERIFY
echo [ERROR] Las dependencias se instalaron, pero el stack completo no paso validacion.
echo Revisa %RUNTIME_REPORT% y %LOG%.
echo CorePulse NO degradara sensores o funciones para fingir compatibilidad.
goto :SHOW
:FAIL_SOURCE
echo [ERROR] La fuente o el test de integridad fallo con este Python.
goto :SHOW
:FAIL_POINTER
echo [ERROR] No se pudo registrar el runtime validado.
goto :SHOW
:SHOW
echo.
echo ---------------- ULTIMAS LINEAS DEL LOG ----------------
powershell -NoProfile -ExecutionPolicy Bypass -Command "if(Test-Path -LiteralPath '%LOG%'){Get-Content -LiteralPath '%LOG%' -Tail 80}"
echo ----------------------------------------------------------
echo Log completo: %LOG%
pause
exit /b 1
