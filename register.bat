@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "_sys\manage.ps1" -Action Register -BaseDir "%~dp0."

endlocal
