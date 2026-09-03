@echo off
setlocal EnableExtensions DisableDelayedExpansion
title CorePulse - Instalador de dependencias V4
cd /d "%~dp0"

set "LOG=%CD%\logs\dependency_install.log"
if not exist "%CD%\logs" mkdir "%CD%\logs" >nul 2>&1

> "%LOG%" echo CorePulse Dependency Installer V4 - Python 3.12+
>>"%LOG%" echo Inicio: %date% %time%
>>"%LOG%" echo Carpeta: %CD%
>>"%LOG%" echo.

cls
echo ================================================================
echo          COREPULSE - INSTALADOR DE DEPENDENCIAS V4
echo                        PYTHON 3.12+
echo ================================================================
echo.
echo Esta version evita subrutinas fragiles de CMD.
echo La ventana permanecera abierta al finalizar o si ocurre un error.
echo.

if not exist "%CD%\main.py" goto :FAIL_PROJECT

echo [1/9] Buscando Python x64 3.12 o superior...
set "PYEXE="

rem 1) Ruta indicada manualmente
if not "%~1"=="" if exist "%~1" set "PYEXE=%~1"

rem 2) Rutas comunes
if not defined PYEXE if exist "C:\Python316\python.exe" set "PYEXE=C:\Python316\python.exe"
if not defined PYEXE if exist "C:\Python315\python.exe" set "PYEXE=C:\Python315\python.exe"
if not defined PYEXE if exist "C:\Python314\python.exe" set "PYEXE=C:\Python314\python.exe"
if not defined PYEXE if exist "C:\Python313\python.exe" set "PYEXE=C:\Python313\python.exe"
if not defined PYEXE if exist "C:\Python312\python.exe" set "PYEXE=C:\Python312\python.exe"

rem 3) Python Launcher de Windows
if not defined PYEXE for /f "usebackq delims=" %%P in (`py -3.16 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYEXE=%%P"
if not defined PYEXE for /f "usebackq delims=" %%P in (`py -3.15 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYEXE=%%P"
if not defined PYEXE for /f "usebackq delims=" %%P in (`py -3.14 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYEXE=%%P"
if not defined PYEXE for /f "usebackq delims=" %%P in (`py -3.13 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYEXE=%%P"
if not defined PYEXE for /f "usebackq delims=" %%P in (`py -3.12 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYEXE=%%P"

rem 4) Python en PATH
if not defined PYEXE for /f "usebackq delims=" %%P in (`where python.exe 2^>nul`) do if not defined PYEXE set "PYEXE=%%P"
if not defined PYEXE for /f "usebackq delims=" %%P in (`where python3.exe 2^>nul`) do if not defined PYEXE set "PYEXE=%%P"

if not defined PYEXE goto :FAIL_PYTHON_NOT_FOUND

echo     Python seleccionado:
echo     %PYEXE%
>>"%LOG%" echo Python seleccionado: %PYEXE%

"%PYEXE%" -c "import sys,struct; bits=struct.calcsize('P')*8; print('Python',sys.version.split()[0],str(bits)+'-bit'); raise SystemExit(0 if sys.version_info >= (3,12) and bits == 64 else 1)" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_PYTHON_VERSION

for /f "usebackq delims=" %%V in (`"%PYEXE%" -c "import sys; print(sys.version.split()[0])"`) do set "PYVER=%%V"
echo     [OK] Python %PYVER% x64 compatible.
echo.

echo [2/9] Creando un entorno virtual limpio...
if exist "%CD%\.venv" (
    echo     Eliminando .venv anterior...
    rmdir /s /q "%CD%\.venv" >>"%LOG%" 2>&1
)
if exist "%CD%\.venv" goto :FAIL_VENV_REMOVE

"%PYEXE%" -m venv "%CD%\.venv" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_VENV_CREATE
if not exist "%CD%\.venv\Scripts\python.exe" goto :FAIL_VENV_CREATE

set "VPY=%CD%\.venv\Scripts\python.exe"
echo     [OK] .venv creado con Python %PYVER%.
echo.

echo [3/9] Verificando pip...
"%VPY%" -m ensurepip --upgrade >>"%LOG%" 2>&1
"%VPY%" -m pip --version >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_PIP
echo     [OK] pip disponible.

echo     Intentando actualizar pip, setuptools y wheel...
"%VPY%" -m pip install --upgrade pip setuptools wheel >>"%LOG%" 2>&1
if errorlevel 1 (
    echo     [AVISO] No se pudieron actualizar las herramientas.
    echo             Se continuara con la version disponible de pip.
    >>"%LOG%" echo AVISO: fallo la actualizacion de pip/setuptools/wheel; se continua.
) else (
    echo     [OK] Herramientas de instalacion actualizadas.
)
echo.

echo [4/9] Instalando dependencias base...
if exist "%CD%\requirements-base.txt" (
    "%VPY%" -m pip install --prefer-binary -r "%CD%\requirements-base.txt" >>"%LOG%" 2>&1
) else (
    if exist "%CD%\requirements.txt" (
        "%VPY%" -m pip install --prefer-binary -r "%CD%\requirements.txt" >>"%LOG%" 2>&1
    ) else (
        goto :FAIL_REQUIREMENTS_MISSING
    )
)
if errorlevel 1 goto :FAIL_BASE_DEPS
echo     [OK] Dependencias base instaladas.
echo.

echo [5/9] Instalando sensores profundos opcionales...
if exist "%CD%\requirements-sensors.txt" (
    "%VPY%" -m pip install --prefer-binary -r "%CD%\requirements-sensors.txt" >>"%LOG%" 2>&1
    if errorlevel 1 (
        echo     [AVISO] pythonnet/HardwareMonitor no pudieron instalarse.
        echo             CorePulse podra iniciar, pero algunos sensores pueden quedar en N/A.
        >>"%LOG%" echo AVISO: dependencias de sensores profundos no disponibles.
    ) else (
        echo     [OK] Sensores profundos instalados.
    )
) else (
    echo     [INFO] No existe requirements-sensors.txt. Se omite esta etapa.
)
echo.

echo [6/9] Verificando dependencias principales...
"%VPY%" -c "import psutil, customtkinter, PIL, matplotlib, reportlab, platformdirs, send2trash, groq, dotenv; print('Base imports OK')" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_VERIFY_BASE
echo     [OK] Dependencias Python principales correctas.

"%VPY%" -c "import wmi, win32api; print('Windows imports OK')" >>"%LOG%" 2>&1
if errorlevel 1 (
    echo     [AVISO] WMI/pywin32 no importaron correctamente.
    echo             Intentando reparacion...
    "%VPY%" -m pip install --upgrade --force-reinstall pywin32 wmi >>"%LOG%" 2>&1
    "%VPY%" -c "import wmi, win32api; print('Windows imports repaired')" >>"%LOG%" 2>&1
    if errorlevel 1 goto :FAIL_VERIFY_WINDOWS
)
echo     [OK] WMI y pywin32 correctos.
echo.

echo [7/9] Verificando CorePulse...
"%VPY%" -m py_compile "%CD%\main.py" >>"%LOG%" 2>&1
if errorlevel 1 goto :FAIL_COREPULSE
echo     [OK] main.py compila correctamente.
echo.

echo [8/9] Creando Iniciar_CorePulse.bat...
> "%CD%\Iniciar_CorePulse.bat" echo @echo off
>>"%CD%\Iniciar_CorePulse.bat" echo cd /d "%%~dp0"
>>"%CD%\Iniciar_CorePulse.bat" echo if not exist ".venv\Scripts\python.exe" ^(
>>"%CD%\Iniciar_CorePulse.bat" echo   echo ERROR: No existe .venv. Ejecuta primero el instalador de dependencias.
>>"%CD%\Iniciar_CorePulse.bat" echo   pause
>>"%CD%\Iniciar_CorePulse.bat" echo   exit /b 1
>>"%CD%\Iniciar_CorePulse.bat" echo ^)
>>"%CD%\Iniciar_CorePulse.bat" echo ".venv\Scripts\python.exe" "main.py"
>>"%CD%\Iniciar_CorePulse.bat" echo if errorlevel 1 pause
echo     [OK] Iniciar_CorePulse.bat creado.
echo.

echo [9/9] Instalacion terminada.
echo.
echo ================================================================
echo                     INSTALACION COMPLETA
echo ================================================================
echo.
echo Python base : %PYEXE%
echo Python venv : %VPY%
echo Version     : %PYVER%
echo.
echo Para iniciar CorePulse usa:
echo     Iniciar_CorePulse.bat
echo.
echo Log:
echo     %LOG%
echo.
>>"%LOG%" echo.
>>"%LOG%" echo INSTALACION COMPLETA: %date% %time%
pause
exit /b 0

:FAIL_PROJECT
echo [ERROR] Este BAT debe estar dentro de la carpeta principal de CorePulse.
echo         No se encontro main.py.
goto :SHOW_ERROR

:FAIL_PYTHON_NOT_FOUND
echo [ERROR] No se encontro Python x64 3.12 o superior.
echo.
echo Puedes indicar la ruta manualmente, por ejemplo:
echo     %~nx0 C:\Python314\python.exe
goto :SHOW_ERROR

:FAIL_PYTHON_VERSION
echo [ERROR] El Python encontrado no es compatible.
echo         CorePulse requiere Python 3.12+ de 64 bits.
goto :SHOW_ERROR

:FAIL_VENV_REMOVE
echo [ERROR] No se pudo eliminar el .venv anterior.
echo         Cierra CorePulse, VS Code o cualquier consola que lo este usando.
goto :SHOW_ERROR

:FAIL_VENV_CREATE
echo [ERROR] No se pudo crear el entorno virtual .venv.
goto :SHOW_ERROR

:FAIL_PIP
echo [ERROR] El entorno virtual se creo, pero pip no funciona.
goto :SHOW_ERROR

:FAIL_REQUIREMENTS_MISSING
echo [ERROR] No se encontro requirements-base.txt ni requirements.txt.
goto :SHOW_ERROR

:FAIL_BASE_DEPS
echo [ERROR] Fallo la instalacion de las dependencias base.
echo         Revisa al final de esta ventana el error real de pip.
goto :SHOW_ERROR

:FAIL_VERIFY_BASE
echo [ERROR] Las dependencias se instalaron, pero algun import base fallo.
goto :SHOW_ERROR

:FAIL_VERIFY_WINDOWS
echo [ERROR] WMI o pywin32 siguen fallando despues del intento de reparacion.
goto :SHOW_ERROR

:FAIL_COREPULSE
echo [ERROR] main.py no pudo compilarse.
goto :SHOW_ERROR

:SHOW_ERROR
echo.
echo ---------------- ULTIMAS LINEAS DEL LOG ----------------
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path -LiteralPath '%LOG%') { Get-Content -LiteralPath '%LOG%' -Tail 45 }"
echo ----------------------------------------------------------
echo.
echo Log completo:
echo     %LOG%
echo.
echo Esta ventana permanecera abierta.
echo Copia el error mostrado o mandame una captura.
echo.
pause
exit /b 1
