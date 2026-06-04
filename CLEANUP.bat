@echo off
set "PY=%~dp0_sys\env\python\python.exe"
if not exist "%PY%" echo [Error] Portable Python not found. Run INSTALL.bat first. & pause & exit /b 1
"%PY%" "%~dp0_sys\cli\cleanup.py" %*
pause
