@echo off
setlocal
chcp 65001 >nul
TITLE CorePulse - Configurar Speedtest by Ookla

echo ============================================================
echo   CorePulse - Configurar Speedtest by Ookla (CLI oficial)
echo ============================================================
echo.
echo CorePulse NO incluye ni acepta automaticamente la licencia de Ookla.
echo Este asistente usa winget para instalar el paquete oficial publicado

echo como Ookla.Speedtest.CLI y luego abre la CLI para que TU revises y

echo aceptes sus terminos si corresponde.
echo.

where winget >nul 2>nul
if errorlevel 1 (
    echo [ERROR] winget no esta disponible en este Windows.
    echo Instala "App Installer" desde Microsoft Store y vuelve a intentar.
    echo.
    pause
    exit /b 1
)

echo [1/2] Instalando o actualizando Ookla.Speedtest.CLI desde winget...
winget install --id Ookla.Speedtest.CLI --exact --source winget
if errorlevel 1 (
    echo.
    echo [AVISO] winget no completo la instalacion.
    echo Revisa el mensaje anterior. CorePulse no modifico sus mediciones.
    echo.
    pause
    exit /b 1
)

echo.
echo [2/2] Localizando la CLI oficial y abriendola para su configuracion inicial...
echo Lee los terminos mostrados por Ookla y responde directamente en esta consola.
echo.

set "SPEEDTEST_EXE="
for /f "delims=" %%I in ('where speedtest 2^>nul') do if not defined SPEEDTEST_EXE set "SPEEDTEST_EXE=%%I"

if not defined SPEEDTEST_EXE if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\speedtest.exe" (
    set "SPEEDTEST_EXE=%LOCALAPPDATA%\Microsoft\WinGet\Links\speedtest.exe"
)

if not defined SPEEDTEST_EXE (
    for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Ookla.Speedtest.CLI_*") do (
        if not defined SPEEDTEST_EXE if exist "%%~fD\speedtest.exe" set "SPEEDTEST_EXE=%%~fD\speedtest.exe"
    )
)

if not defined SPEEDTEST_EXE (
    for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$root=Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'; if(Test-Path $root){Get-ChildItem -Path $root -Directory -Filter 'Ookla.Speedtest.CLI_*' -ErrorAction SilentlyContinue ^| ForEach-Object {Get-ChildItem -Path $_.FullName -Filter 'speedtest.exe' -File -Recurse -ErrorAction SilentlyContinue} ^| Select-Object -First 1 -ExpandProperty FullName}"`) do if not defined SPEEDTEST_EXE set "SPEEDTEST_EXE=%%I"
)

if not defined SPEEDTEST_EXE (
    echo [AVISO] La instalacion termino, pero este asistente no pudo resolver speedtest.exe.
    echo CorePulse tambien buscara automaticamente dentro de WinGet al pulsar "Actualizar servidores".
    echo No hace falta reiniciar Windows.
    echo.
    pause
    exit /b 0
)

echo [OK] CLI encontrada:
echo     %SPEEDTEST_EXE%
echo.
"%SPEEDTEST_EXE%" --version
echo.
"%SPEEDTEST_EXE%"

echo.
echo Configuracion terminada. Vuelve a CorePulse y pulsa "Actualizar servidores".
pause
endlocal
