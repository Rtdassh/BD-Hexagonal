@echo off
REM Doble clic para iniciar los 4 motores y la aplicacion
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0iniciar.ps1"
pause
