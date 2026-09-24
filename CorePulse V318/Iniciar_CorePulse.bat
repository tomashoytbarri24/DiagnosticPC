@echo off
setlocal
cd /d "%~dp0"
start "" wscript.exe "%~dp0CorePulse.vbs"
exit /b 0
